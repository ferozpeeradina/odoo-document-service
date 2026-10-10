#!/usr/bin/env python3
"""Generate sandbox-only credentials. Never read an .env file."""
import pathlib, secrets
root = pathlib.Path(__file__).resolve().parents[1]
runtime = root / 'runtime'
runtime.mkdir(exist_ok=True)
p = runtime / 'db.password'
if not p.exists():
    p.write_text(secrets.token_urlsafe(32))
    p.chmod(0o600)
# This locally generated file is the only credential input.
password = p.read_text().strip()
conf = runtime / 'odoo.conf'
if not conf.exists():
    conf.write_text(f'''[options]
admin_passwd = {secrets.token_urlsafe(32)}
db_host = db
db_port = 5432
db_user = odoo
db_password = {password}
db_name = packaging_poc
dbfilter = ^packaging_poc$
list_db = False
addons_path = /usr/lib/python3/dist-packages/odoo/addons,/mnt/sign,/mnt/dms,/mnt/poc-addons
data_dir = /var/lib/odoo
http_interface = 0.0.0.0
http_port = 8069
workers = 0
max_cron_threads = 0
proxy_mode = False
smtp_server = 127.0.0.1
smtp_port = 1
limit_time_cpu = 120
limit_time_real = 240
log_level = warn
''')
    conf.chmod(0o644)  # container odoo uid must read; sandbox credentials only
print('Sandbox configuration ready; credentials not printed.')
