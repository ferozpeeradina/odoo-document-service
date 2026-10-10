"""TEST-only independent HMAC/freshness verifier and stable-event deduplicator."""
import hashlib,hmac,json,os,pathlib,time
from http.server import BaseHTTPRequestHandler,HTTPServer
r=pathlib.Path('/run/mail')
class Sink(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        status=403
        try:
            raw=self.rfile.read(int(self.headers.get('Content-Length','0')))
            stamp=self.headers['x-dms-timestamp'];signature=self.headers['x-dms-signature']
            key=pathlib.Path('/run/config/callback.key').read_bytes().strip()
            assert abs(time.time()-int(stamp))<=300
            assert hmac.compare_digest(signature,hmac.new(key,stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest())
            payload=json.loads(raw);assert payload['status']=='completed'
            if (r/'fail-callback').exists():status=503
            else:
                p=r/('callback-'+hashlib.sha256(payload['eventId'].encode()).hexdigest()+'.json')
                if not p.exists():
                    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                    with os.fdopen(fd,'w') as f:json.dump(dict(payload=payload,verifiedHmac=True,timestampFresh=True),f)
                else:assert json.loads(p.read_text())['payload']==payload
                status=200
        except Exception:pass
        self.send_response(status);self.end_headers()
HTTPServer(('0.0.0.0',8081),Sink).serve_forever()
