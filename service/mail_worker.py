"""Outbox consumer. Delivery occurs after claim transaction commits. No logs."""
import json, os, pathlib, time, hmac, hashlib
import requests
r=pathlib.Path('/run/mail')
mode=os.environ.get('DOCUMENT_SERVICE_MODE')
def atomic_capture(m):
    p=r/('mail-'+str(m['id'])+'.json')
    if not p.exists():
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f: json.dump(m,f)
while True:
    try:
        token=pathlib.Path('/run/config/worker.token').read_text().strip()
        headers={'Authorization':'Bearer '+token}
        resp=requests.post('http://odoo:8069/internal/mail/claim',headers=headers,json={},timeout=10)
        m=resp.json()
        if not m.get('id'): time.sleep(2); continue
        sent=False
        if mode=='test' and (r/'pause-after-claim').exists():
            marker=r/('claimed-'+str(m['id']))
            fd=os.open(marker,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as f:f.write('claimed')
            for _ in range(30):
                if not (r/'pause-after-claim').exists():break
                time.sleep(1)
        try:
            if m.get('kind')=='callback':
                raw=m['body'].encode();stamp=str(int(time.time()));key=pathlib.Path('/run/config/callback.key').read_bytes().strip()
                signature=hmac.new(key,stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
                if mode=='test':
                    response=requests.post('http://callback:8081',data=raw,headers={'Content-Type':'application/json','x-dms-timestamp':stamp,'x-dms-signature':signature},timeout=10)
                    sent=response.status_code==200
                elif mode=='production' and os.environ.get('PRODUCTION_ACCEPTED')=='yes':
                    response=requests.post(os.environ['DMS_CALLBACK_URL'],data=raw,headers={'Content-Type':'application/json','x-dms-timestamp':stamp,'x-dms-signature':signature},timeout=20,allow_redirects=False)
                    sent=200<=response.status_code<300
            elif mode=='test':
                if (r/'fail-mail').exists(): raise ValueError()
                atomic_capture(m); sent=True
            elif mode=='production' and os.environ.get('PRODUCTION_ACCEPTED')=='yes':
                key=pathlib.Path(os.environ['RESEND_API_KEY_FILE']).read_text().strip()
                result=requests.post('https://api.resend.com/emails',headers={'Authorization':'Bearer '+key,'Idempotency-Key':m['operation']},json={'from':'feroz@agentfleet.services','to':[m['recipient']],'subject':m['subject'],'text':m['body']},timeout=20)
                sent=result.status_code in (200,201)
        except Exception: pass
        requests.post('http://odoo:8069/internal/mail/ack',headers=headers,json=dict(id=m['id'],lease=m['lease'],sent=sent),timeout=10)
    except Exception: time.sleep(3)
