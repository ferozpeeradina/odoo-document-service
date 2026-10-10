"""Coordinator-only: consume injected files, produce separate mode-600 runtime. No dotenv."""
import os,pathlib,shutil
from cryptography import x509
from cryptography.hazmat.primitives import serialization
r=pathlib.Path(os.environ['SERVICE_RUNTIME_DIR']).resolve()
if r.exists() and any(r.iterdir()):raise SystemExit('Use an empty separate production runtime directory')
r.mkdir(mode=0o700,parents=True,exist_ok=True)
inputs={'DB_PASSWORD_FILE':'db.password','ODOO_MASTER_PASSWORD_FILE':'master.password','SERVICE_CREDENTIAL_FILE':'service.token','MAIL_WORKER_CREDENTIAL_FILE':'worker.token','SEAL_PRIVATE_KEY_FILE':'seal.key','SEAL_CERTIFICATE_FILE':'seal.crt','RESEND_API_KEY_FILE':'resend.key','SEAL_AUTH_TOKEN_FILE':'seal.token','DMS_CALLBACK_SECRET_FILE':'callback.key'}
for variable,name in inputs.items():
    src=pathlib.Path(os.environ[variable]);data=src.read_bytes()
    if not data:raise SystemExit('Empty injected file: '+variable)
    if name.endswith('.password') and any(c in data.strip() for c in (b'\n',b'\r')):raise SystemExit('Configuration secret must be one line')
    fd=os.open(r/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:f.write(data)
cert=x509.load_pem_x509_certificate((r/'seal.crt').read_bytes())
key=serialization.load_pem_private_key((r/'seal.key').read_bytes(),password=None)
if b'TEST' in cert.subject.rfc4514_string().encode().upper():raise SystemExit('TEST seal certificate cannot provision production')
if key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)!=cert.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo):raise SystemExit('Seal key and cert do not match')
db=os.environ.get('SERVICE_DB_NAME','document_service_production')
if not db.replace('_','').isalnum() or db=='document_service_test':raise SystemExit('Use a separate production database name')
conf='''[options]
admin_passwd = %s
db_host = db
db_user = odoo
db_password = %s
db_name = %s
dbfilter = ^%s$
list_db = False
addons_path = /usr/lib/python3/dist-packages/odoo/addons,/mnt/sign,/mnt/dms,/mnt/addons
data_dir = /var/lib/odoo
http_interface = 0.0.0.0
http_port = 8069
workers = 0
max_cron_threads = 0
proxy_mode = True
log_level = critical
smtp_server = 127.0.0.1
smtp_port = 1
limit_time_real = 120
'''%((r/'master.password').read_text().strip(),(r/'db.password').read_text().strip(),db,db)
fd=os.open(r/'odoo.conf',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:f.write(conf)
print('Production runtime prepared from injected files; acceptance gate remains separate')
