"""Offline verification uses ONLY exported bytes and a separately pinned public cert."""
import base64, hashlib, io, json, logging
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko.keys import load_cert_from_pemder
from pyhanko_certvalidator import ValidationContext
logging.disable(logging.CRITICAL)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def verify(pdf,evidence,cert_path):
    cert=x509.load_pem_x509_certificate(open(cert_path,'rb').read())
    cert.public_key().verify(base64.b64decode(evidence['signature'],validate=True),canonical(evidence['manifest']),padding.PKCS1v15(),hashes.SHA256())
    assert evidence['manifest']['hashes']['signedPdfSha256']==hashlib.sha256(pdf).hexdigest()
    reader=PdfFileReader(io.BytesIO(pdf));assert len(reader.embedded_signatures)==1
    sig=reader.embedded_signatures[0]; root=load_cert_from_pemder(cert_path)
    assert sig.signer_cert.dump()==root.dump()
    result=validate_pdf_signature(sig,signer_validation_context=ValidationContext(trust_roots=[root],allow_fetching=False))
    assert result.intact and result.valid and result.trusted and result.coverage.name=='ENTIRE_FILE'
if __name__=='__main__':
    import sys
    try:
        verify(open(sys.argv[1],'rb').read(),json.load(open(sys.argv[2])),sys.argv[3]);print('PASS: independent PDF and evidence signatures (pinned certificate; no trusted timestamp)')
    except Exception:
        print('FAIL: independent artifact verification');sys.exit(1)
