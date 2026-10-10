import importlib.util,json,pathlib,re,sys,time,subprocess
s=importlib.util.spec_from_file_location('t','tests/http_service.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
cmd=['docker','compose','--env-file','/dev/null','-f','compose.service.yaml','exec','-T','odoo','odoo','shell','--config=/run/config/odoo.conf','--no-http']
def shell(code):
    p=subprocess.run(cmd,input=code.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    assert p.returncode==0,'isolated OTP test mutation'
def latest_id():
    files=list((t.ROOT/'service-runtime/mail-final').glob('mail-*.json'))
    return max([int(p.stem.split('-')[1]) for p in files]+[0])
def capture(after):
    for _ in range(25):
        for p in (t.ROOT/'service-runtime/mail-final').glob('mail-*.json'):
            m=json.loads(p.read_text())
            if m['id']>after and m['recipient']=='alice@example.test' and m['operation'].startswith('otp:'):
                return re.search(r'Verification code: (\d{6})',m['body']).group(1)
        time.sleep(1)
    raise AssertionError('fake OTP delivery')
try:
    # Pending envelope has not been used by the legitimate UI acceptance journey.
    c=dict(t.CTX,documentId='otp-negative-contract',operationId='otp-negative-generate')
    v=t.call('/v1/documents',dict(context=c,input=dict(templateId='contract',templateVersion='1',snapshot=t.SNAP))).json()['versionId']
    envelope=t.call('/v1/signature-requests',dict(context=dict(c,operationId='otp-negative-sign'),input=dict(versionId=v,signers=[dict(name='Synthetic Alice Customer',email='alice@example.test'),dict(name='Synthetic Bob Supplier',email='bob@example.test')]))).json()
    req=envelope['requestId'];path='/recipient/'+req
    after=latest_id();r=t.call(path+'/otp',{'email':'alice@example.test'},headers={});t.check('OTP challenge dispatched',r.status_code==200);code=capture(after)
    t.check('code bound to exact recipient',t.call(path+'/verify',{'email':'bob@example.test','code':code},headers={}).status_code==403)
    t.check('code bound to exact request',t.call('/recipient/999999/verify',{'email':'alice@example.test','code':code},headers={}).status_code==403)
    shell("from odoo import fields\nimport datetime\nc=env['document.challenge'].search([('signer_id.request_id','=',%s)],order='id desc',limit=1)\nc.write({'expires':fields.Datetime.now()-datetime.timedelta(seconds=1)})\nenv.cr.commit()"%req)
    t.check('expired code rejected',t.call(path+'/verify',{'email':'alice@example.test','code':code},headers={}).status_code==403)
    after=latest_id();t.call(path+'/otp',{'email':'alice@example.test'},headers={});code=capture(after)
    for i in range(5):t.check('wrong OTP bounded attempt '+str(i),t.call(path+'/verify',{'email':'alice@example.test','code':'not-a-code'},headers={}).status_code==403)
    t.check('correct code locked out after attempt bound',t.call(path+'/verify',{'email':'alice@example.test','code':code},headers={}).status_code==403)
    t.check('third bounded OTP issuance',t.call(path+'/otp',{'email':'alice@example.test'},headers={}).status_code==200)
    t.check('issuance rate limited',t.call(path+'/otp',{'email':'alice@example.test'},headers={}).status_code==429)
    t.check('unrelated mailbox gets generic locator flow',t.call(path+'/otp',{'email':'mallory@example.test'},headers={}).status_code==200)
    (t.ROOT/'artifacts/otp-negative-tests.json').write_text(json.dumps(dict(result='PASS',checks=t.checks),indent=2))
except Exception as e:
    print('FAIL '+(str(e) if isinstance(e,AssertionError) else type(e).__name__));sys.exit(1)
