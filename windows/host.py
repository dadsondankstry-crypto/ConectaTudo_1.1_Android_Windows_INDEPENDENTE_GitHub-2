"""ConectaTudo LAN HTTP protocol v1 - Windows host, offline, no cloud."""
import json
import os
import re
import secrets
import socket
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit
from io import BytesIO

PORT = 8765
DISCOVERY_PORT = 39402
DISCOVERY_REQUEST = b'CT_DISCOVER_V1'
MAX_FILE = 20 * 1024**3
MAX_MESSAGE = 65536


def local_ips():
    found = set()
    try:
        import psutil
        for interface, addrs in psutil.net_if_addrs().items():
            for a in addrs:
                if a.family == socket.AF_INET and not a.address.startswith(('127.', '169.254.')):
                    found.add(a.address)
    except Exception:
        pass
    try:
        for a in socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET):
            if a[4][0] != '127.0.0.1':
                found.add(a[4][0])
    except OSError:
        pass
    return sorted(found)


def safe_name(s):
    s = (s or 'arquivo').replace('\\', '/').split('/')[-1]
    s = ''.join(c for c in s if c >= ' ' and c not in '<>:"/\\|?*')
    return s[:160].strip(' .') or 'arquivo'


def unique_path(folder, name):
    base = safe_name(name)
    stem, ext = os.path.splitext(base)
    for idx in range(10000):
        label = base if idx == 0 else f'{stem} ({idx}){ext}'
        p = folder / label
        if not p.exists() and not (folder / ('.' + label + '.part')).exists():
            return p
    raise OSError('Muitos arquivos com o mesmo nome')


class DeviceHost:
    def __init__(self, folder=None, name=None):
        self.name = name or ('Windows • ' + socket.gethostname())
        self.pin = str(secrets.randbelow(900000) + 100000)
        self.folder = Path(folder or (Path.home() / 'Downloads' / 'ConectaTudo'))
        self.folder.mkdir(parents=True, exist_ok=True)
        self.messages = deque(maxlen=150)
        self.files = deque(maxlen=80)
        self.transfers = {}
        self.lock = threading.Lock()
        self.sharing_screen = False
        self.httpd = None
        self.discover_sock = None
        self.running = False

    def start(self):
        if self.running:
            return
        self.httpd = ThreadingHTTPServer(('0.0.0.0', PORT), self._make_handler())
        self.httpd.daemon_threads = True
        self.running = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        threading.Thread(target=self._discover_loop, daemon=True).start()

    def stop(self):
        self.running = False
        self.sharing_screen = False
        if self.discover_sock:
            try: self.discover_sock.close()
            except OSError: pass
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None

    def _discover_loop(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.discover_sock = s
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('', DISCOVERY_PORT))
            s.settimeout(1.5)
            while self.running:
                try:
                    data, origin = s.recvfrom(1024)
                    if data != DISCOVERY_REQUEST:
                        continue
                    info = {'name': self.name, 'platform': 'windows', 'port': PORT}
                    s.sendto(json.dumps(info).encode(), origin)
                except socket.timeout:
                    pass
                except OSError:
                    if not self.running: break
        except OSError:
            pass
        finally:
            s.close()

    def _make_handler(self):
        host = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, fmt, *args):
                pass  # sem logs com PIN em texto

            def reply(self, status, body, typ='application/json; charset=utf-8', extra=None):
                if isinstance(body, str):
                    body = body.encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', typ)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Access-Control-Allow-Origin', 'null')
                if extra:
                    for k,v in extra.items(): self.send_header(k, v)
                self.end_headers()
                try: self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError): pass

            def json(self, status, data):
                self.reply(status, json.dumps(data, ensure_ascii=False).encode('utf-8'))

            def parse(self):
                u = urlsplit(self.path)
                q = parse_qs(u.query, keep_blank_values=True)
                return u.path, {k: v[0] for k,v in q.items()}

            def auth(self, q):
                return secrets.compare_digest(q.get('pin', ''), host.pin)

            def do_GET(self):
                path, q = self.parse()
                if path in ('/', '/screen'):
                    try:
                        body = (Path(__file__).resolve().parent / 'painel.html').read_bytes()
                    except FileNotFoundError:
                        # PyInstaller onefile
                        import sys
                        body = (Path(getattr(sys, '_MEIPASS', '.')) / 'painel.html').read_bytes()
                    self.reply(200, body, 'text/html; charset=utf-8')
                    return
                if not self.auth(q):
                    self.json(403, {'error': 'Código de acesso inválido'})
                    return
                if path == '/api/info':
                    self.json(200, {'name': host.name, 'platform': 'windows', 'version': '1.1', 'screen': host.sharing_screen})
                elif path == '/api/messages':
                    with host.lock: data = list(host.messages)
                    self.json(200, {'messages': data})
                elif path == '/api/files':
                    with host.lock: data = list(host.files)
                    self.json(200, {'files': data})
                elif path == '/api/transfers':
                    with host.lock: data = list(host.transfers.values())[-20:]
                    self.json(200, {'transfers': data})
                elif path == '/api/download':
                    file = safe_name(q.get('name', ''))
                    # downloads limitados aos arquivos recebidos nesta sessão
                    with host.lock: known = any(x['name'] == file for x in host.files)
                    p = host.folder / file
                    if not known or not p.is_file():
                        self.json(404, {'error': 'Arquivo não encontrado'}); return
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/octet-stream')
                    self.send_header('Content-Length', str(p.stat().st_size))
                    self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + quote(file))
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    try:
                        with p.open('rb') as f:
                            while data := f.read(131072): self.wfile.write(data)
                    except (ConnectionError, OSError): pass
                elif path == '/api/screen.jpg':
                    if not host.sharing_screen:
                        self.json(409, {'error': 'Tela não está sendo compartilhada'})
                        return
                    try:
                        from PIL import ImageGrab
                        image = ImageGrab.grab(all_screens=True)
                        image.thumbnail((1600, 1000))
                        b = BytesIO(); image.convert('RGB').save(b, format='JPEG', quality=76, optimize=False)
                        self.reply(200, b.getvalue(), 'image/jpeg')
                    except Exception as e:
                        self.json(500, {'error': 'Falha na captura de tela: ' + str(e)[:100]})
                else:
                    self.json(404, {'error': 'Rota desconhecida'})

            def do_POST(self):
                path, q = self.parse()
                if not self.auth(q):
                    self.json(403, {'error': 'PIN inválido'}); return
                try: n = int(self.headers.get('Content-Length', '-1'))
                except ValueError: n = -1
                if n < 0:
                    self.json(411, {'error': 'Content-Length necessário'}); return
                if path == '/api/message':
                    if n > MAX_MESSAGE:
                        self.json(413, {'error': 'Texto muito grande'}); return
                    text = self.rfile.read(n).decode('utf-8', errors='replace').strip()
                    if not text:
                        self.json(400, {'error': 'Texto vazio'}); return
                    with host.lock:
                        host.messages.append({'text': text, 'who': 'Outro dispositivo', 'time': int(time.time() * 1000)})
                    self.json(200, {'ok': True})
                elif path == '/api/send':
                    if n > MAX_FILE:
                        self.json(413, {'error': 'Arquivo maior que 20 GB'}); return
                    filename = safe_name(q.get('name', 'arquivo'))
                    transfer_id = str(time.time_ns())
                    temp = None
                    try:
                        with host.lock:
                            dst = unique_path(host.folder, filename)
                            host.transfers[transfer_id] = {'name': filename, 'size': n, 'done': 0, 'status': 'receiving'}
                            if len(host.transfers) > 30:
                                for old in list(host.transfers)[:10]: host.transfers.pop(old, None)
                        temp = dst.with_name('.' + dst.name + '.part')
                        left = n
                        last_update = 0.0
                        with temp.open('xb') as f:
                            while left > 0:
                                chunk = self.rfile.read(min(128 * 1024, left))
                                if not chunk: raise IOError('Conexão interrompida')
                                f.write(chunk); left -= len(chunk)
                                now = time.monotonic()
                                if now - last_update > .14 or left == 0:
                                    with host.lock:
                                        host.transfers[transfer_id]['done'] = n - left
                                    last_update = now
                        os.replace(temp, dst)
                        with host.lock:
                            host.files.appendleft({'name': dst.name, 'size': n, 'time': int(time.time() * 1000)})
                            host.transfers[transfer_id].update(done=n, status='complete')
                        self.json(200, {'ok': True, 'name': dst.name})
                    except Exception as e:
                        try:
                            if temp is not None: temp.unlink(missing_ok=True)
                        except Exception: pass
                        with host.lock:
                            host.transfers[transfer_id]['status'] = 'error'
                        self.json(500, {'error': str(e)[:150]})
                else:
                    self.json(404, {'error': 'Rota desconhecida'})

        return Handler


def discover(timeout=3.0):
    results = []
    seen = set()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.settimeout(0.35)
        targets = ['255.255.255.255']
        try:
            import psutil
            for addrs in psutil.net_if_addrs().values():
                for a in addrs:
                    if a.family == socket.AF_INET and a.broadcast:
                        targets.append(a.broadcast)
        except Exception:
            pass
        for ip in set(targets):
            try: s.sendto(DISCOVERY_REQUEST, (ip, DISCOVERY_PORT))
            except OSError: pass
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                data, addr = s.recvfrom(2048)
                info = json.loads(data)
                if 'name' in info and addr[0] not in seen:
                    seen.add(addr[0]); info['ip'] = addr[0]; results.append(info)
            except (socket.timeout, ValueError, UnicodeDecodeError):
                pass
    finally:
        s.close()
    return results
