import hashlib,json,os,pathlib,subprocess,time,sys
root=pathlib.Path(__file__).resolve().parents[1];a=json.loads((root/'service-runtime/test-association.json').read_text());mail=root/'service-runtime/mail-final';c=['docker','compose','--env-file','/dev/null','-f','compose.service.yaml'];op='completion:'+a['versionId'];checks=[]
payload=dict(eventId=op,tenantId=a['context']['tenantId'],documentId=a['context']['documentId'],versionId=a['versionId'],signatureRequestId='otp-browser-sign-final',status='completed')
def sh(code):
    p=subprocess.run(c+['exec','-T','odoo','odoo','shell','--config=/run/config/odoo.conf','--no-http'],input=code.encode(),capture_output=True,timeout=30)
    assert p.returncode==0,'callback shell'
    lines=[l[12:] for l in p.stdout.decode(errors='replace').splitlines() if l.startswith('SAFE_RESULT ')];return json.loads(lines[-1]) if lines else None
def check(n,v):
    if not v:raise AssertionError(n)
    checks.append(n);print('PASS '+n)
def state():return sh("import json\nm=env['document.outbox'].search([('operation','=',%r)])\nprint('SAFE_RESULT '+json.dumps({'count':len(m),'state':m.state,'attempts':m.attempts,'local':m.envelope_id.local_request_key,'complete':bool(m.envelope_id.evidence_file_id)}))"%op)
def requeue():sh("import json\nm=env['document.outbox'].search([('operation','=',%r)])\nm.write({'state':'pending','attempts':0,'body':%r,'next_at':__import__('datetime').datetime.utcnow()})\nenv.cr.commit()"%(op,json.dumps(payload,sort_keys=True,separators=(',',':'))))
try:
    negative="import requests,hmac,hashlib,time;raw=b'{}';stamp=str(int(time.time())-600);key=open('/run/config/callback.key','rb').read().strip();sig=hmac.new(key,stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest();assert requests.post('http://callback:8081',data=raw,headers={'x-dms-timestamp':stamp,'x-dms-signature':sig},timeout=5).status_code==403;assert requests.post('http://callback:8081',data=raw,headers={'x-dms-timestamp':str(int(time.time())),'x-dms-signature':'invalid'},timeout=5).status_code==403"
    result=subprocess.run(c+['exec','-T','mail','python3','-c',negative],capture_output=True,timeout=15)
    check('fake callback rejects wrong HMAC and stale timestamp',result.returncode==0)
    current=state();check('callback queued after verified final artifacts',current['count']==1 and current['complete'] and current['local']==payload['signatureRequestId'])
    check('no callback for pending request',sh("import json\nprint('SAFE_RESULT '+json.dumps(env['document.outbox'].search_count([('kind','=','callback'),('envelope_id.version_id.document_key','=','contract-test')])))")==0)
    fd=os.open(mail/'fail-callback',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd);requeue()
    for _ in range(8):
        time.sleep(1);st=state()
        if st['attempts']>0 and st['state']=='pending':break
    check('fake callback failure retained for bounded retry',st['attempts']>0 and st['state']=='pending')
    (mail/'fail-callback').unlink()
    for _ in range(8):
        time.sleep(1);st=state()
        if st['state']=='sent':break
    check('callback recovery succeeds',st['state']=='sent')
    path=mail/('callback-'+hashlib.sha256(op.encode()).hexdigest()+'.json');got=json.loads(path.read_text())
    check('exact stable event and local request association',got['payload']==payload)
    check('independent fake sink checks HMAC and freshness',got['verifiedHmac'] and got['timestampFresh'])
    requeue()
    for _ in range(8):
        time.sleep(1);st=state()
        if st['state']=='sent':break
    check('duplicate delivery safely accepted with stable identity',st['state']=='sent' and json.loads(path.read_text())==got and st['count']==1)
    (root/'artifacts/callback-tests.json').write_text(json.dumps(dict(result='PASS',checks=checks),indent=2))
except Exception as e:print('FAIL '+(str(e) if isinstance(e,AssertionError) else type(e).__name__));sys.exit(1)
finally:
    p=mail/'fail-callback'
    if p.exists():p.unlink()
