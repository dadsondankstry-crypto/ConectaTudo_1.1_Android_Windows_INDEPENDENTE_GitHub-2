package br.app.conectatudo.v1;

import android.content.Context;
import android.net.Uri;
import android.net.wifi.WifiManager;
import android.net.DhcpInfo;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.JSONObject;

/** Funções de rede comuns: conexão por IP e busca UDP local. */
public final class Net {
    private Net() {}
    public static final int PORT = 8765, DISCOVERY = 39402;
    public static String cleanIp(String in) {
        in = in == null ? "" : in.trim().replaceFirst("^https?://", "");
        if (in.contains("/")) in = in.substring(0, in.indexOf('/'));
        if (in.contains(":")) in = in.substring(0, in.indexOf(':'));
        if (!in.matches("[0-9A-Za-z.\\-]{1,253}")) throw new IllegalArgumentException("IP/nome inválido");
        return in;
    }
    public static String url(String ip, String path, String pin) {
        String sep = path.contains("?") ? "&" : "?";
        return "http://" + cleanIp(ip) + ":" + PORT + path + sep + "pin=" + Uri.encode(pin);
    }
    public static String read(HttpURLConnection c) throws Exception {
        int code = c.getResponseCode();
        InputStream stream = code >= 200 && code < 300 ? c.getInputStream() : c.getErrorStream();
        if (stream == null) throw new IOException("HTTP " + code);
        try (InputStream in = stream; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] b = new byte[4096]; int n; int total = 0;
            while ((n = in.read(b)) != -1) {
                total += n; if (total > 1024 * 1024) throw new IOException("Resposta muito grande");
                out.write(b, 0, n);
            }
            String text = out.toString("UTF-8");
            if (code < 200 || code >= 300) throw new IOException("HTTP " + code + ": " + text);
            return text;
        } finally { c.disconnect(); }
    }
    public static String get(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(6500); c.setReadTimeout(10000);
        return read(c);
    }
    public static String post(String url, byte[] body) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(6500); c.setReadTimeout(10000); c.setRequestMethod("POST");
        c.setDoOutput(true); c.setFixedLengthStreamingMode(body.length);
        c.setRequestProperty("Content-Type", "text/plain; charset=utf-8");
        try (OutputStream out = c.getOutputStream()) { out.write(body); }
        return read(c);
    }
    public static List<JSONObject> discover(Context context) throws Exception {
        ArrayList<JSONObject> out = new ArrayList<>();
        HashSet<String> seen = new HashSet<>();
        try (DatagramSocket socket = new DatagramSocket()) {
            socket.setBroadcast(true); socket.setSoTimeout(500);
            byte[] req = "CT_DISCOVER_V1".getBytes(StandardCharsets.UTF_8);
            ArrayList<InetAddress> targets = new ArrayList<>();
            targets.add(InetAddress.getByName("255.255.255.255"));
            try {
                WifiManager wifi = (WifiManager) context.getApplicationContext().getSystemService(Context.WIFI_SERVICE);
                DhcpInfo dhcp = wifi != null ? wifi.getDhcpInfo() : null;
                if (dhcp != null) {
                    int b = (dhcp.ipAddress & dhcp.netmask) | ~dhcp.netmask;
                    byte[] bytes = {(byte)(b & 255),(byte)((b>>8)&255),(byte)((b>>16)&255),(byte)((b>>24)&255)};
                    targets.add(InetAddress.getByAddress(bytes));
                }
            } catch (Exception ignored) {}
            for (InetAddress target : targets) {
                try { socket.send(new DatagramPacket(req, req.length, target, DISCOVERY)); }
                catch (Exception ignored) {}
            }
            long deadline = System.currentTimeMillis() + 3000;
            while (System.currentTimeMillis() < deadline) {
                try {
                    byte[] buffer = new byte[2048]; DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
                    socket.receive(packet);
                    JSONObject v = new JSONObject(new String(packet.getData(), 0, packet.getLength(), StandardCharsets.UTF_8));
                    if (v.has("name") && seen.add(packet.getAddress().getHostAddress())) {
                        v.put("ip", packet.getAddress().getHostAddress()); out.add(v);
                    }
                } catch (SocketTimeoutException ignored) {} catch (Exception ignored) {}
            }
        }
        return out;
    }
    public static List<String> ownIps() {
        ArrayList<String> ips = new ArrayList<>();
        try {
            Enumeration<NetworkInterface> ifaces = NetworkInterface.getNetworkInterfaces();
            while (ifaces != null && ifaces.hasMoreElements()) {
                NetworkInterface ni = ifaces.nextElement();
                if (!ni.isUp() || ni.isLoopback()) continue;
                Enumeration<InetAddress> addrs = ni.getInetAddresses();
                while (addrs.hasMoreElements()) {
                    InetAddress ip = addrs.nextElement();
                    if (ip instanceof Inet4Address && !ip.isLoopbackAddress() && !ip.isLinkLocalAddress())
                        ips.add(ip.getHostAddress());
                }
            }
        } catch (Exception ignored) {}
        return ips;
    }
}
