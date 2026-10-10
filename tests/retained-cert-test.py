"""Retained public pin tests; synthetic fixtures and newly generated TEST keys only."""
import datetime,json,pathlib,tempfile
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from service.verify import verify
root=pathlib.Path(__file__).resolve().parents[1];pdf=(root/'artifacts/final-signed_document.pdf').read_bytes();evidence=json.loads((root/'artifacts/final-evidence.json').read_text());old=root/'artifacts/verification-public.crt'
checks=[]
def check(name,ok):
 if not ok:raise AssertionError(name)
 checks.append(name);print('PASS '+name)
with tempfile.TemporaryDirectory() as d:
 p=pathlib.Path(d);key=rsa.generate_private_key(public_exponent=65537,key_size=2048);name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'TEST rotated public certificate')]);now=datetime.datetime.now(datetime.timezone.utc)
 cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(days=1)).sign(key,hashes.SHA256());active=p/'active.crt';active.write_bytes(cert.public_bytes(serialization.Encoding.PEM));pins=p/'trusted';pins.mkdir();(pins/'previous.crt').write_bytes(old.read_bytes())
 verify(pdf,evidence,active,pins);check('historical PDF and evidence verified with a different active certificate',True)
 try:verify(pdf,evidence,active)
 except AssertionError:check('unretained signing certificate rejected',True)
 else:raise AssertionError('unretained signing certificate rejected')
 altered=json.loads(json.dumps(evidence));altered['manifest']['seal']['certificateSha256']=cert.fingerprint(hashes.SHA256()).hex()
 try:verify(pdf,altered,active,pins)
 except AssertionError:check('wrong recorded certificate identity rejected',True)
 else:raise AssertionError('wrong recorded certificate identity rejected')
 verify(pdf,evidence,old);check('original standalone pinned-certificate verification preserved',True)
(root/'artifacts/retained-certificate-tests.json').write_text(json.dumps({'result':'PASS','checks':checks},indent=2)+'\n')
