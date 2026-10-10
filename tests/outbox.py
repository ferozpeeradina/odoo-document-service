"""Actual failed dispatch and worker crash; output is state/count only."""
import json,os,pathlib,secrets,subprocess,time,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];cmd=['docker','compose','--env-file','/dev/null','-f','compose.service.yaml'];mail=ROOT/'service-runtime/mail-final';checks=[]
def compose(*args):
    p=subprocess.run(cmd+list(args),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    assert p.returncode==0,'isolated compose command'
def shell(script):
    p=subprocess.run(cmd+['exec','-T','odoo','odoo','shell','--config=/run/config/odoo.conf','--no-http'],input=script.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    assert p.returncode==0,'outbox test shell'
    lines=[l[12:] for l in p.stdout.decode(errors='replace').splitlines() if l.startswith('SAFE_RESULT ')]
    return json.loads(lines[-1]) if lines else None
def check(name,ok):
    if not ok:raise AssertionError(name)
    checks.append(name);print('PASS '+name)
def flag(name):
    fd=os.open(mail/name,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
def state(op):return shell("import json\nm=env['document.outbox'].search([('operation','=',%r)],limit=1)\nprint('SAFE_RESULT '+json.dumps(dict(id=m.id,state=m.state,attempts=m.attempts,body=bool(m.body))))"%op)
def queue(op):shell("env['document.outbox']._queue(%r,'alice@example.test','Synthetic recovery','Synthetic outbox test')\nenv.cr.commit()"%op)
try:
    compose('stop','mail');flag('fail-mail');op='failure-test:'+secrets.token_hex(5);queue(op);compose('up','-d','mail')
    failed=None
    for _ in range(5):
        time.sleep(2);failed=state(op)
        if failed['attempts']>0:break
    compose('stop','mail');check('actual failed dispatch retained for bounded retry',failed['state']=='pending' and 1<=failed['attempts']<5)
    (mail/'fail-mail').unlink();compose('up','-d','mail')
    for _ in range(5):
        time.sleep(2);sent=state(op)
        if sent['state']=='sent':break
    check('failed dispatch recovered with stable operation',sent['state']=='sent' and sent['id']==failed['id'] and sent['attempts']>failed['attempts'])
    check('delivered sensitive body cleared',not sent['body'])
    compose('stop','mail');flag('pause-after-claim');op='crash-test:'+secrets.token_hex(5);queue(op);compose('up','-d','mail')
    for _ in range(5):
        time.sleep(2);leased=state(op)
        if leased['state']=='leased' and (mail/('claimed-'+str(leased['id']))).exists():break
    check('worker durably leased before crash',leased['state']=='leased')
    compose('kill','-s','KILL','mail');(mail/'pause-after-claim').unlink()
    # Advance only this synthetic expired lease, avoiding a sixty-second wait.
    shell("from odoo import fields\nimport datetime\nm=env['document.outbox'].search([('operation','=',%r)],limit=1)\nm.write({'next_at':fields.Datetime.now()-datetime.timedelta(seconds=1)})\nenv.cr.commit()"%op)
    compose('up','-d','mail')
    for _ in range(5):
        time.sleep(2);sent=state(op)
        if sent['state']=='sent':break
    check('crashed worker stale lease recovered',sent['state']=='sent' and sent['id']==leased['id'] and sent['attempts']==leased['attempts']+1)
    check('one fake delivery for stable operation',len(list(mail.glob('mail-'+str(sent['id'])+'.json')))==1)
    (ROOT/'artifacts/outbox-tests.json').write_text(json.dumps(dict(result='PASS',checks=checks),indent=2))
except Exception as e:
    print('FAIL '+(str(e) if isinstance(e,AssertionError) else type(e).__name__));sys.exit(1)
finally:
    for name in ('fail-mail','pause-after-claim'):
        p=mail/name
        if p.exists():p.unlink()
