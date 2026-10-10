"""Local ingress relay. Destination is fixed; no arbitrary proxying or logs."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import requests

class Relay(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Signing bearer links must never reach HTTP access logs.

    def proxy(self):
        if not self.path.startswith('/') or self.path.startswith('//'):
            self.send_error(400)
            return
        length = int(self.headers.get('Content-Length', '0'))
        if length > 12 * 1024 * 1024:
            self.send_error(413)
            return
        headers = {k: v for k, v in self.headers.items() if k.lower() not in ('connection', 'transfer-encoding')}
        try:
            response = requests.request(self.command, 'http://odoo:8069' + self.path, headers=headers, data=self.rfile.read(length) if length else None, timeout=240, allow_redirects=False)
        except requests.RequestException:
            self.send_error(502)
            return
        self.send_response(response.status_code)
        for key, value in response.headers.items():
            if key.lower() not in ('content-length', 'content-encoding', 'transfer-encoding', 'connection', 'set-cookie'):
                self.send_header(key, value)
        for cookie in response.raw.headers.getlist('Set-Cookie'):
            self.send_header('Set-Cookie', cookie)
        self.send_header('Content-Length', str(len(response.content)))
        self.end_headers()
        self.wfile.write(response.content)

    do_GET = proxy
    do_POST = proxy
    do_HEAD = proxy

ThreadingHTTPServer(('0.0.0.0', 8069), Relay).serve_forever()
