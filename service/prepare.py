"""Generate isolated TEST runtime only. Never uses POC runtime or dotenv."""
import os, pathlib, secrets, json
root = pathlib.Path(__file__).resolve().parents[1]
r = root / 'service-runtime'
r.mkdir(mode=0o700, exist_ok=True)
def save(name, value):
    p = r / name
    if not p.exists():
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f: f.write(value)
save('db.password', secrets.token_urlsafe(32))
save('service.token', secrets.token_urlsafe(40))
save('worker.token', secrets.token_urlsafe(40))
save('seal.token', secrets.token_urlsafe(40))
save('callback.key', secrets.token_urlsafe(40))
(r/'mail-final').mkdir(mode=0o700,exist_ok=True)
save('backup.key', secrets.token_urlsafe(40))
save('odoo.conf', '''[options]
admin_passwd = %s
db_host = db
db_user = odoo
db_password = %s
db_name = document_service_test
dbfilter = ^document_service_test$
list_db = False
addons_path = /usr/lib/python3/dist-packages/odoo/addons,/mnt/sign,/mnt/dms,/mnt/addons
data_dir = /var/lib/odoo
http_interface = 0.0.0.0
http_port = 8069
workers = 0
max_cron_threads = 0
proxy_mode = True
smtp_server = 127.0.0.1
smtp_port = 1
limit_time_real = 120
log_level = critical
''' % (secrets.token_urlsafe(32), (r/'db.password').read_text().strip()))
# TEST certificate is generated once; private key only mounted into sealer.
if not (r/'seal.key').exists():
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import datetime
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'TEST ONLY Document Service Seal')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(days=365)).add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True).add_extension(x509.KeyUsage(True,True,False,False,False,True,True,False,False), critical=True).sign(key,hashes.SHA256())
    save('seal.key', key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode())
    save('seal.crt', cert.public_bytes(serialization.Encoding.PEM).decode())
(r/'trusted-certs').mkdir(mode=0o700,exist_ok=True)
(r/'trusted-certs'/'initial.crt').write_bytes((r/'seal.crt').read_bytes())
print('Isolated TEST runtime prepared (secret files mode 600).')
