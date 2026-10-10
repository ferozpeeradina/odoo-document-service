"""Register one tenant/operator and scoped credential, without printing secret values."""
import argparse, hashlib, os, pathlib, secrets, subprocess
p=argparse.ArgumentParser();p.add_argument('--tenant',required=True);p.add_argument('--operator',required=True);p.add_argument('--project',action='append',default=[]);p.add_argument('--tenant-wide',action='store_true');p.add_argument('--credential-file',required=True);p.add_argument('--production-runtime-dir');a=p.parse_args()
path=pathlib.Path(a.credential_file)
if not path.exists():
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(40))
if path.stat().st_mode&0o077:raise SystemExit('Credential file must have mode 600')
h=hashlib.sha256(path.read_bytes().strip()).hexdigest()
script='''import secrets
from odoo import Command
user=env['res.users'].search([('login','=',%r)],limit=1)
if not user:
    user=env['res.users'].with_context(no_reset_password=True).create(dict(name=%r,login=%r,email=%r,password=secrets.token_urlsafe(40),group_ids=[Command.set([env.ref('base.group_portal').id])]))
if not user.share:raise ValueError('operator must be a dedicated portal principal')
member=env['poc.member'].search([('user_id','=',user.id)],limit=1)
if member and member.tenant_key!=%r:raise ValueError('operator tenant conflict')
if not member:env['poc.member'].create(dict(user_id=user.id,tenant_key=%r,can_issue=True))
existing=env['document.credential'].search([('token_hash','=',%r)])
if existing and (existing.user_id!=user or existing.tenant!=%r or existing.projects!=%r or existing.tenant_wide!=%r):raise ValueError('credential scope conflict')
if not existing:env['document.credential'].create(dict(token_hash=%r,user_id=user.id,tenant=%r,projects=%r,tenant_wide=%r))
env.cr.commit()
'''%(a.operator,a.operator,a.operator,a.operator,a.tenant,a.tenant,h,a.tenant,(a.project or ['tenant-scope']) if a.tenant_wide else a.project,a.tenant_wide,h,a.tenant,(a.project or ['tenant-scope']) if a.tenant_wide else a.project,a.tenant_wide)
cmd=['docker','compose','--env-file','/dev/null','-f','compose.service.yaml']
if a.production_runtime_dir:
    os.environ['PRODUCTION_RUNTIME_DIR']=a.production_runtime_dir
    cmd+=['-f','compose.production.yaml']
cmd+=['exec','-T','odoo','odoo','shell','--config=/run/config/odoo.conf','--no-http']
r=subprocess.run(cmd,input=script.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
if r.returncode:raise SystemExit('FAIL tenant registration (details withheld)')
print('PASS scoped tenant/operator credential registered; credential remains in mode-600 file')
