"""Rotate only the isolated TEST sealer, preserve old actual HTTP artifact bytes, then restore."""
import datetime,hashlib,importlib.util,json,os,pathlib,subprocess,time
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
s=importlib.util.spec_from_file_location('t','tests/http_service.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
r=t.ROOT/'service-runtime';a=json.loads((t.ROOT/'artifacts/final-evidence.json').read_text())['manifest']['association'];url='/v1/documents/'+a['documentId']+'/versions/'+a['versionId']+'/download/signed_document?tenantId='+a['tenantId']
before=t.call(url);assert before.status_code==200
key=rsa.generate_private_key(public_exponent=65537,key_size=2048);name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'TEST rotated HTTP seal')]);now=datetime.datetime.now(datetime.timezone.utc)
cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(days=365)).add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True).sign(key,hashes.SHA256())
for file,data in [('rotation-test.key',key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())),('rotation-test.crt',cert.public_bytes(serialization.Encoding.PEM))]:
 fd=os.open(r/file,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
 with os.fdopen(fd,'wb') as f:f.write(data)
override=r/'rotation-test.yaml';override.write_text('services:\n  sealer:\n    volumes: !override\n      - ./service:/service:ro\n      - ./service-runtime/rotation-test.key:/run/seal/key.pem:ro\n      - ./service-runtime/rotation-test.crt:/run/seal/cert.pem:ro\n      - ./service-runtime/trusted-certs:/run/seal/trusted:ro\n      - ./service-runtime/seal.token:/run/seal/auth.token:ro\n')
cmd=['docker','compose','--env-file','/dev/null','-f','compose.service.yaml']
def launch(extra):
 p=subprocess.run(cmd+extra+['up','-d','--force-recreate','sealer'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90)
 assert p.returncode==0,'isolated sealer restart failed (output withheld)'
checks=[]
try:
 launch(['-f',str(override)])
 for _ in range(30):
  after=t.call(url)
  if after.status_code==200:break
  time.sleep(2)
 assert after.status_code==200 and after.content==before.content;checks.append('actual old signed-PDF HTTP download survives changed active key/certificate');print('PASS '+checks[-1])
 evidence=t.call(url.replace('/signed_document?','/evidence?'));assert evidence.status_code==200;checks.append('actual old evidence HTTP download survives changed active key/certificate');print('PASS '+checks[-1])
finally:launch([])
(t.ROOT/'artifacts/rotation-http-tests.json').write_text(json.dumps({'result':'PASS','checks':checks},indent=2)+'\n')
