"""Focused HTTP contract tests. Only named assertions shown, no payloads/secrets."""
import concurrent.futures, json, pathlib, requests, time
ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:18079'
TOKEN=(ROOT/'service-runtime/service.token').read_text().strip()
HEAD={'Authorization':'Bearer '+TOKEN}
CTX=dict(tenantId='synthetic-a',documentId='contract-test',projectId='project-a',operationId='generate-contract-1')
SNAP=dict(synthetic=True,parties=dict(business=dict(name='Synthetic Business'),customer=dict(name='Synthetic Alder Boxes Ltd'),factory=dict(name='Synthetic Factory')),demonstration=True,source=dict(kind='orders',id='saved-contract-1',revision=1,data=dict(date='2026-10-10',customer='Synthetic Alder Boxes Ltd',supplier='Synthetic Birch Packaging Ltd',currency='CAD',lines=[dict(description='Saved demonstration cartons',quantity=100,totalCents=125000)],totalCents=125000,terms='Demonstration only. No commercial obligations.',status='approved',approvedBy='synthetic-owner',approvedAt='2026-10-10T00:00:00Z')),project=dict(id='project-a',name='Synthetic Packaging project'))
checks=[]
def check(name,value):
    if not value: raise AssertionError(name)
    checks.append(name); print('PASS '+name)
def call(path,payload=None,headers=HEAD):
    return requests.request('POST' if payload is not None else 'GET',BASE+path,headers=headers,json=payload,timeout=120)
def main():
    for _ in range(45):
        try:
            if call('/v1/templates/contract/versions/1').status_code==200: break
        except requests.RequestException: pass
        time.sleep(2)
    check('missing credential denied',call('/v1/templates/contract/versions/1',headers={}).status_code==403)
    check('wrong credential denied',call('/v1/templates/contract/versions/1',headers={'Authorization':'Bearer invalid'}).status_code==403)
    for key in ('purchase_order','packing_list','invoice','ledger_statement','contract'):
        check('template '+key,call('/v1/templates/'+key+'/versions/1').json()==dict(id=key,version='1'))
    for path in ('/web/login','/web/session/authenticate','/web/database/manager','/poc/api','/web/content/1'):
        check('public native route blocked '+path,call(path,{}).status_code==403)
    payload=dict(context=CTX,input=dict(templateId='contract',templateVersion='1',snapshot=SNAP))
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:call('/v1/documents',payload),range(2)))
    check('concurrent generation succeeds',all(r.status_code==200 for r in results))
    version=results[0].json(); check('concurrent generation one immutable version',version==results[1].json())
    check('fixture labelled',version['fixture'] is True)
    wrong=dict(payload,context=dict(CTX,tenantId='synthetic-b'))
    check('wrong tenant denied',call('/v1/documents',wrong).status_code==403)
    check('wrong project denied',call('/v1/documents',dict(payload,context=dict(CTX,projectId='other'))).status_code==403)
    altered=dict(payload,input=dict(payload['input'],snapshot=dict(SNAP,illustrative=True)))
    check('operation replay conflict',call('/v1/documents',altered).status_code==409)
    v=version['versionId']; read='/v1/documents/contract-test/versions/'+v
    check('one persisted version',len(call('/v1/documents/contract-test/versions?tenantId=synthetic-a').json())==1)
    check('cross document version denied',call('/v1/documents/other/versions/'+v+'/artifacts?tenantId=synthetic-a').status_code==403)
    no_terms=json.loads(json.dumps(payload)); no_terms['context']['operationId']='bad-terms'; no_terms['input']['snapshot']['source']['data'].pop('terms')
    check('contract missing approved terms rejected',call('/v1/documents',no_terms).status_code==409)
    sign=dict(context=dict(CTX,operationId='sign-1'),input=dict(versionId=v,signers=[dict(name='Synthetic Alice Customer',email='alice@example.test'),dict(name='Synthetic Bob Supplier',email='bob@example.test')]))
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:call('/v1/signature-requests',sign),range(2)))
    check('concurrent sign request succeeds',all(r.status_code==200 for r in results))
    envelope=results[0].json();check('concurrent sign request one request',envelope==results[1].json())
    status=dict(context=dict(CTX,operationId='status-1'),input=dict(versionId=v))
    check('pending status',call('/v1/signature-requests/'+envelope['requestId']+'/status',status).json()=={'status':'pending'})
    check('stale request rejected',call('/v1/signature-requests/999999/status',status).status_code==409)
    arts=call(read+'/artifacts?tenantId=synthetic-a').json()
    check('no premature signed artifacts',[a['kind'] for a in arts]==['document'])
    check('public HTTPS download metadata',arts[0]['url'].startswith('https://documents.agentfleet.services/v1/') and TOKEN not in arts[0]['url'])
    check('anonymous artifact denied',call(read+'/download/document?tenantId=synthetic-a',headers={}).status_code==403)
    check('signed artifact unavailable',call(read+'/download/signed_document?tenantId=synthetic-a').status_code==404)
    pdf=call(read+'/download/document?tenantId=synthetic-a')
    check('QWeb PDF downloadable',pdf.status_code==200 and pdf.content.startswith(b'%PDF'))
    (ROOT/'artifacts/http-tests.json').write_text(json.dumps(dict(result='PASS',checks=checks),indent=2))
if __name__=='__main__':
    try:main()
    except Exception as e:
        print('FAIL '+(str(e) if isinstance(e,AssertionError) else type(e).__name__))
        raise SystemExit(1)
