"""Allowlisted public ingress; no native password/admin/DB authentication."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import requests
class Ingress(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def proxy(self):
        path = self.path.split('?',1)[0]
        allowed = path.startswith(('/v1/', '/recipient/', '/sign_oca/', '/web/assets/', '/web/static/', '/sign/static/', '/sign_oca/static/', '/web/sign/get_fonts/')) or path in ('/web/session/get_session_info','/web/webclient/translations','/web/webclient/load_menus','/web/webclient/bootstrap_translations','/web/webclient/version_info','/web/sign/get_fonts','/logo.png','/web/binary/company_logo')
        if not allowed or self.command not in ('GET','POST','HEAD'):
            self.send_error(403); return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length < 0 or length > 15*1024*1024: raise ValueError()
            headers={k:v for k,v in self.headers.items() if k.lower() not in ('host','connection','transfer-encoding','x-forwarded-for','x-forwarded-host','x-forwarded-proto')}
            headers.update({'X-Forwarded-Proto':'https','X-Forwarded-Host':'documents.agentfleet.services'})
            r=requests.request(self.command,'http://odoo:8069'+self.path, headers=headers,data=self.rfile.read(length),timeout=125,allow_redirects=False)
            self.send_response(r.status_code)
            for k,v in r.headers.items():
                if k.lower() not in ('set-cookie','connection','content-length','content-encoding','transfer-encoding'): self.send_header(k,v)
            for c in r.raw.headers.getlist('Set-Cookie'):
                self.send_header('Set-Cookie', c + ('; Secure; SameSite=Strict' if 'secure' not in c.lower() else '; SameSite=Strict'))
            self.send_header('Content-Length',str(len(r.content)))
            self.send_header('Cache-Control','no-store')
            self.end_headers(); self.wfile.write(r.content)
        except Exception:
            self.send_error(502)
    do_GET=proxy
    do_POST=proxy
    do_HEAD=proxy
ThreadingHTTPServer(('0.0.0.0',8069),Ingress).serve_forever()
