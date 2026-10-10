"""Isolated cryptographic service. Private key never enters Odoo/DB."""
import base64, hashlib, io, json, logging, hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from pyhanko.sign import signers
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko.keys import load_cert_from_pemder
from pyhanko_certvalidator import ValidationContext
logging.disable(logging.CRITICAL)
KEY='/run/seal/key.pem'; CERT='/run/seal/cert.pem'
from verify import canonical, verify as verify_artifacts
def verify(pdf,evidence): return verify_artifacts(pdf,evidence,CERT,"/run/seal/trusted")
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        body=b'{"ready":true}' if self.path=='/health' else b'{}'
        self.send_response(200 if self.path=='/health' else 404)
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_POST(self):
        if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+open('/run/seal/auth.token').read().strip()):
            self.send_response(403);self.end_headers();return
        try:
            n=int(self.headers.get('Content-Length','0')); assert 0<n<30*1024*1024
            data=json.loads(self.rfile.read(n)); pdf=base64.b64decode(data['pdf'],validate=True)
            if self.path=='/seal':
                signer=signers.SimpleSigner.load(KEY,CERT)
                out=io.BytesIO()
                signers.PdfSigner(signers.PdfSignatureMetadata(field_name='DocumentServiceSeal',reason='Service integrity seal; recipient identities are in signed evidence; no trusted timestamp'),signer=signer).sign_pdf(IncrementalPdfFileWriter(io.BytesIO(pdf)),output=out)
                pdf=out.getvalue(); manifest=data['manifest']
                manifest.setdefault('seal',{})['certificateSha256']=x509.load_pem_x509_certificate(open(CERT,'rb').read()).fingerprint(hashes.SHA256()).hex()
                manifest['hashes']['signedPdfSha256']=hashlib.sha256(pdf).hexdigest()
                key=serialization.load_pem_private_key(open(KEY,'rb').read(),password=None)
                evidence={'manifest':manifest,'algorithm':'RSASSA-PKCS1-v1_5-SHA256','signature':base64.b64encode(key.sign(canonical(manifest),padding.PKCS1v15(),hashes.SHA256())).decode()}
                verify(pdf,evidence)
                result={'pdf':base64.b64encode(pdf).decode(),'evidence':evidence}
            elif self.path=='/verify':
                verify(pdf,data['evidence']); result={'valid':True}
            else: raise ValueError()
            body=canonical(result); self.send_response(200)
        except Exception:
            body=b'{"error":"seal_verification_failed"}'; self.send_response(409)
        self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
HTTPServer(('0.0.0.0',8080),Handler).serve_forever()
