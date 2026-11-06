"""Interface portátil Windows para ConectaTudo. Sem conta e sem internet externa."""
import http.client
import json
import os
import queue
import socket
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import quote
import urllib.request
import webbrowser
from host import DeviceHost, PORT, discover, local_ips

class App:
    def __init__(self, root):
        self.root = root
        root.title('ConectaTudo 1.1 • Windows')
        root.geometry('685x780')
        root.minsize(560, 630)
        self.host = DeviceHost()
        self.messages = queue.Queue()
        self.peer_ip = tk.StringVar()
        self.peer_pin = tk.StringVar()
        self.send_text = tk.StringVar()
        self.screen = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value='Preparando servidor...')
        self.remote_name = tk.StringVar(value='Não conectado')
        self.progress_label = tk.StringVar(value='📦 Nenhuma transferência ativa')
        self.incoming_label = tk.StringVar(value='')
        self._last_local = 0.0
        self._seen_messages = set()
        self._seen_files = set()
        self._ui()
        try:
            self.host.start()
            self.refresh_status()
        except OSError as e:
            self.status.set('Não foi possível abrir a porta 8765: ' + str(e))
            messagebox.showerror('ConectaTudo', 'Porta 8765 ocupada. Feche outra cópia do programa.\n' + str(e))
        root.after(100, self._pump)
        root.protocol('WM_DELETE_WINDOW', self.close)

    def _ui(self):
        bg = '#121a2b'
        self.root.configure(bg=bg)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=bg)
        style.configure('TLabel', background=bg, foreground='#e8efff', font=('Segoe UI', 10))
        style.configure('Header.TLabel', background=bg, foreground='#6fb0ff', font=('Segoe UI', 17, 'bold'))
        style.configure('TButton', font=('Segoe UI', 10), padding=7)
        style.configure('TEntry', padding=7)
        # Região rolável para caber na tela de 800p do Legion Go com escala de interface.
        container = ttk.Frame(self.root)
        container.pack(fill='both', expand=True)
        canvas = tk.Canvas(container, bg=bg, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(container, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        outer = ttk.Frame(canvas, padding=18)
        window_id = canvas.create_window((0,0), window=outer, anchor='nw')
        outer.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window_id, width=e.width))
        def mousewheel(event):
            canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        canvas.bind_all('<MouseWheel>', mousewheel)
        ttk.Label(outer, text='🔗 ConectaTudo 1.1 • Windows', style='Header.TLabel').pack(anchor='w')
        ttk.Label(outer, text='Rede local • Sem nuvem • Envio de arquivos e tela').pack(anchor='w', pady=(3, 12))
        ttk.Label(outer, text='ESTE COMPUTADOR', font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        self.ips = ttk.Label(outer, text='IP: ...'); self.ips.pack(anchor='w', pady=(6, 2))
        self.pin_label = ttk.Label(outer, text='Código: ...'); self.pin_label.pack(anchor='w')
        ttk.Label(outer, text='Porta: 8765 • Conecte os aparelhos ao mesmo Wi-Fi/hotspot.').pack(anchor='w', pady=(0, 4))
        row = ttk.Frame(outer); row.pack(fill='x', pady=5)
        ttk.Button(row, text='Abrir meu painel no navegador', command=self.open_local).pack(side='left', padx=(0, 5))
        ttk.Button(row, text='Abrir pasta Recebidos', command=self.open_folder).pack(side='left')
        ttk.Checkbutton(outer, text='🖥️ Compartilhar tela deste Windows (com autorização)', variable=self.screen,
                        command=self.toggle_screen).pack(anchor='w', pady=(6, 12))
        ttk.Separator(outer).pack(fill='x', pady=7)
        ttk.Label(outer, text='CONECTAR AO CELULAR OU TABLET', font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        row = ttk.Frame(outer); row.pack(fill='x', pady=5)
        ttk.Label(row, text='IP:').pack(side='left')
        ttk.Entry(row, textvariable=self.peer_ip, width=20).pack(side='left', padx=5, fill='x', expand=True)
        ttk.Label(row, text='Código:').pack(side='left')
        ttk.Entry(row, textvariable=self.peer_pin, width=10).pack(side='left', padx=5)
        row = ttk.Frame(outer); row.pack(fill='x', pady=5)
        ttk.Button(row, text='🔎 Procurar aparelhos', command=self.find_peers).pack(side='left', padx=(0, 6))
        ttk.Button(row, text='Conectar', command=self.connect).pack(side='left', padx=(0, 6))
        ttk.Button(row, text='Abrir painel remoto', command=self.open_remote).pack(side='left')
        ttk.Label(outer, textvariable=self.remote_name).pack(anchor='w', pady=(4, 6))
        row = ttk.Frame(outer); row.pack(fill='x', pady=5)
        ttk.Button(row, text='📤 Enviar arquivos selecionados', command=self.send_files).pack(side='left', padx=(0, 6))
        ttk.Button(row, text='👁️ Ver tela remota', command=self.view_screen).pack(side='left')
        self.progress = ttk.Progressbar(outer, orient='horizontal', mode='determinate', maximum=100)
        self.progress.pack(fill='x', pady=(5, 2))
        ttk.Label(outer, textvariable=self.progress_label, wraplength=590).pack(anchor='w', pady=(0, 4))
        ttk.Label(outer, textvariable=self.incoming_label, wraplength=590).pack(anchor='w', pady=(0, 4))
        ttk.Label(outer, text='MENSAGEM DE TEXTO').pack(anchor='w', pady=(8, 2))
        row = ttk.Frame(outer); row.pack(fill='x')
        ttk.Entry(row, textvariable=self.send_text).pack(side='left', fill='x', expand=True, padx=(0, 6))
        ttk.Button(row, text='Enviar', command=self.send_message).pack(side='left')
        ttk.Label(outer, text='💬 MENSAGENS RECEBIDAS (AUTOMÁTICO)').pack(anchor='w', pady=(9, 4))
        self.inbox = tk.Text(outer, bg='#101e33', fg='#d6ecff', height=5,
                             relief='flat', wrap='word', state='disabled', font=('Segoe UI', 10))
        self.inbox.pack(fill='x')
        ttk.Label(outer, text='ATIVIDADE / INSTRUÇÕES').pack(anchor='w', pady=(9, 4))
        self.log = tk.Text(outer, bg='#0b1020', fg='#dbeafe', insertbackground='white', height=8,
                           relief='flat', wrap='word', state='disabled', font=('Consolas', 9))
        self.log.pack(fill='both', expand=True)
        ttk.Label(outer, textvariable=self.status, wraplength=580).pack(anchor='w', pady=(8, 0))
        self._log('Dica: no celular, informe o IP deste Windows e o código acima. Ou faça o contrário.')
        self._log('Sem câmera? Use IP e código. Internet NÃO é necessária quando ambos estão no mesmo hotspot.')

    def _log(self, msg):
        self.log.configure(state='normal')
        self.log.insert('end', msg + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def _pump(self):
        try:
            while True:
                kind, val = self.messages.get_nowait()
                if kind == 'log': self._log(val)
                elif kind == 'status': self.status.set(val)
                elif kind == 'connected': self.remote_name.set('✅ ' + val)
                elif kind == 'found': self._choose_peer(val)
                elif kind == 'error': messagebox.showerror('ConectaTudo', val)
                elif kind == 'progress':
                    done, total, name, index, count, started = val
                    self.progress['value'] = min(100, done * 100 / max(1,total))
                    seconds = max(.1,time.monotonic() - started)
                    speed = done / seconds
                    eta = (total - done) / speed if speed > 0 else 0
                    self.progress_label.set(f'📤 {index}/{count}: {name} • {self._size(done)} / {self._size(total)} • {done*100/max(1,total):.0f}% • {self._size(speed)}/s • {eta:.0f}s restantes')
                elif kind == 'done':
                    self.progress['value'] = 100
                    self.progress_label.set(val)
        except queue.Empty:
            pass
        if time.monotonic() - self._last_local >= .9:
            self._last_local = time.monotonic()
            self._refresh_local()
        self.root.after(120, self._pump)

    @staticmethod
    def _size(n):
        n=float(n)
        if n<1024:return f'{n:.0f} B'
        if n<1048576:return f'{n/1024:.1f} KB'
        if n<1073741824:return f'{n/1048576:.1f} MB'
        return f'{n/1073741824:.2f} GB'

    def _refresh_local(self):
        with self.host.lock:
            messages=list(self.host.messages)
            files=list(self.host.files)
            transfers=list(self.host.transfers.values())
        for msg in messages:
            key=(msg.get('time'),msg.get('text'))
            if key not in self._seen_messages:
                self._seen_messages.add(key)
                self._log('💬 Recebido: ' + str(msg.get('text',''))[:250])
        for file in files:
            key=(file.get('time'),file.get('name'))
            if key not in self._seen_files:
                self._seen_files.add(key)
                self._log('📥 Arquivo recebido: ' + str(file.get('name','')))
        new_text='\n'.join(time.strftime('%H:%M:%S',time.localtime(m.get('time',0)/1000))+' • '+str(m.get('text','')) for m in messages[-20:])
        if self.inbox.get('1.0','end-1c') != new_text:
            self.inbox.configure(state='normal')
            self.inbox.delete('1.0','end')
            self.inbox.insert('end',new_text)
            self.inbox.see('end')
            self.inbox.configure(state='disabled')
        receiving=[t for t in transfers if t.get('status')=='receiving']
        if receiving:
            t=receiving[-1]
            self.incoming_label.set(f'📥 Recebendo {t["name"]}: {self._size(t["done"])} / {self._size(t["size"])} • {t["done"]*100/max(1,t["size"]):.0f}%')
        else:self.incoming_label.set('')

    def bg(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def refresh_status(self):
        self.ips.config(text='Endereço(s): ' + (', '.join(local_ips()) or '(rede não detectada)'))
        self.pin_label.config(text='Código de acesso (PIN): ' + self.host.pin)
        self.status.set('Servidor ativo na porta 8765 • Arquivos recebidos: ' + str(self.host.folder))

    def toggle_screen(self):
        self.host.sharing_screen = self.screen.get()
        self._log('Tela do Windows: ' + ('COMPARTILHAMENTO ATIVADO' if self.screen.get() else 'parado'))

    def open_local(self):
        webbrowser.open(f'http://127.0.0.1:{PORT}/?pin={self.host.pin}')

    def open_folder(self):
        self.host.folder.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith('win'): os.startfile(str(self.host.folder))
        else: self._log(str(self.host.folder))

    def target(self, path):
        ip = self.peer_ip.get().strip().replace('http://', '').replace('https://', '').split('/')[0].split(':')[0]
        pin = self.peer_pin.get().strip()
        if not ip or len(pin) != 6 or not pin.isdecimal():
            raise ValueError('Digite o IP do outro aparelho e seu código de 6 números.')
        # Bloqueia nomes com prefixos de URL, somente endereço IPv4/hostname local
        if any(x in ip for x in ('@', '?', '#', ' ')):
            raise ValueError('Endereço inválido')
        return ip, pin, f'http://{ip}:{PORT}{path}' + ('&' if '?' in path else '?') + 'pin=' + pin

    def connect(self):
        try: _,_,url = self.target('/api/info')
        except ValueError as e: return messagebox.showwarning('ConectaTudo', str(e))
        def task():
            try:
                with urllib.request.urlopen(url, timeout=7) as response:
                    data = json.load(response)
                self.messages.put(('connected', data.get('name', 'Dispositivo conectado')))
                self.messages.put(('log', 'Conexão confirmada com ' + data.get('name', 'dispositivo')))
            except Exception as e:
                self.messages.put(('error', 'Não conectou. Verifique IP, PIN, hotspot e firewall.\n' + str(e)))
        self.bg(task)

    def find_peers(self):
        self.status.set('Procurando outros dispositivos na mesma rede...')
        self.bg(lambda: self.messages.put(('found', discover(3.2))))

    def _choose_peer(self, data):
        if not data:
            self._log('Nada encontrado na busca automática. Informe IP e código manualmente.'); return
        popup = tk.Toplevel(self.root); popup.title('Dispositivos encontrados'); popup.geometry('440x220')
        lb = tk.Listbox(popup, font=('Segoe UI', 11))
        lb.pack(fill='both', expand=True, padx=10, pady=10)
        for dev in data: lb.insert('end', f"{dev['name']}  —  {dev['ip']}")
        def choose():
            sel = lb.curselection()
            if sel:
                self.peer_ip.set(data[sel[0]]['ip']); popup.destroy()
                self._log('IP preenchido. Digite o PIN mostrado no outro aparelho e clique Conectar.')
        ttk.Button(popup, text='Usar endereço selecionado', command=choose).pack(pady=(0, 8))

    def open_remote(self):
        try: _,_,url = self.target('/')
        except ValueError as e: return messagebox.showwarning('ConectaTudo', str(e))
        webbrowser.open(url)

    def view_screen(self):
        try: _,_,url = self.target('/screen')
        except ValueError as e: return messagebox.showwarning('ConectaTudo', str(e))
        webbrowser.open(url)

    def send_files(self):
        try: ip, pin, _ = self.target('/api/send')
        except ValueError as e: return messagebox.showwarning('ConectaTudo', str(e))
        files = filedialog.askopenfilenames(title='Arquivos para enviar')
        if not files: return
        def task():
            try:
                total = sum(os.path.getsize(x) for x in files)
                done = 0
                started = time.monotonic()
                last_update = 0.0
                for index, file in enumerate(files,1):
                    size = os.path.getsize(file)
                    name = Path(file).name
                    path = '/api/send?pin=' + pin + '&name=' + quote(name)
                    conn = http.client.HTTPConnection(ip, PORT, timeout=240)
                    try:
                        conn.putrequest('POST', path)
                        conn.putheader('Content-Type', 'application/octet-stream')
                        conn.putheader('Content-Length', str(size))
                        conn.endheaders()
                        with open(file, 'rb') as f:
                            while chunk := f.read(128 * 1024):
                                conn.send(chunk)
                                done += len(chunk)
                                now = time.monotonic()
                                if now - last_update > .15 or done == total:
                                    self.messages.put(('progress',(done,total,name,index,len(files),started)))
                                    last_update = now
                        res = conn.getresponse()
                        data = res.read(4096)
                        if res.status != 200: raise IOError(str(data[:300]))
                        self.messages.put(('log','✅ Enviado: '+name+f' ({self._size(size)})'))
                    finally: conn.close()
                self.messages.put(('done',f'✅ Transferência concluída: {len(files)} arquivo(s), {self._size(total)}'))
                self.messages.put(('status','Transferências concluídas.'))
            except Exception as e:
                self.messages.put(('error','Falha na transferência: '+str(e)))
        self.bg(task)

    def send_message(self):
        msg = self.send_text.get().strip()
        if not msg: return
        try: _,_,url = self.target('/api/message')
        except ValueError as e: return messagebox.showwarning('ConectaTudo', str(e))
        self.send_text.set('')
        def task():
            try:
                req = urllib.request.Request(url, data=msg.encode(), method='POST',
                                             headers={'Content-Type': 'text/plain; charset=utf-8'})
                with urllib.request.urlopen(req, timeout=9) as res: res.read()
                self.messages.put(('log', '✉️ ' + msg[:180]))
            except Exception as e:
                self.messages.put(('error', 'Mensagem não enviada: ' + str(e)))
        self.bg(task)

    def close(self):
        try: self.host.stop()
        except Exception: pass
        self.root.destroy()

if __name__ == '__main__':
    root = tk.Tk(); App(root); root.mainloop()
