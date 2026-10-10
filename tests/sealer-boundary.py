import json,subprocess,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[1];c=['docker','compose','--env-file','/dev/null','-f','compose.service.yaml']
checks=[]
def check(n,v):
    if not v:raise AssertionError(n)
    checks.append(n);print('PASS '+n)
try:
    code="import requests; a=requests.post('http://sealer:8080/seal',json={},timeout=3); b=requests.post('http://sealer:8080/seal',json={},headers={'Authorization':'Bearer invalid'},timeout=3); assert a.status_code==b.status_code==403"
    p=subprocess.run(c+['exec','-T','odoo','python3','-c',code],capture_output=True,timeout=15);check('unauthenticated and wrong sealer credential denied',p.returncode==0)
    records=json.loads(subprocess.run(c+['ps','--format','json','sealer'],capture_output=True,check=True).stdout);record=records[0] if isinstance(records,list) else records
    info=json.loads(subprocess.run(['docker','inspect',record['Name']],capture_output=True,check=True).stdout)[0]
    ip=next(v['IPAddress'] for k,v in info['NetworkSettings']['Networks'].items() if k.endswith('_sealing'))
    p=subprocess.run(c+['exec','-T','db','bash','-c','timeout 2 bash -c "echo > /dev/tcp/'+ip+'/8080" >/dev/null 2>&1'],capture_output=True,timeout=10);check('DB network cannot reach sealer',p.returncode!=0)
    p=subprocess.run(c+['exec','-T','odoo','python3','-c',"import pathlib;assert not pathlib.Path('/run/seal/key.pem').exists()"],capture_output=True,timeout=10);check('private sealing key not mounted in Odoo',p.returncode==0)
    (root/'artifacts/sealer-boundary-tests.json').write_text(json.dumps(dict(result='PASS',checks=checks),indent=2))
except Exception as e:print('FAIL '+(str(e) if isinstance(e,AssertionError) else type(e).__name__));sys.exit(1)
