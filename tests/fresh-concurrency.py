import importlib.util, concurrent.futures, json
s=importlib.util.spec_from_file_location('t','tests/http_service.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
for _ in range(30):
    try:
        if t.call('/v1/templates/contract/versions/1').status_code==200:break
    except Exception:pass
    t.time.sleep(1)
ctx=dict(t.CTX,documentId='fresh-race-contract-3',operationId='fresh-race-generate-3')
payload=dict(context=ctx,input=dict(templateId='contract',templateVersion='1',snapshot=t.SNAP))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:t.call('/v1/documents',payload),range(2)))
t.check('fresh concurrent generation both succeed',all(r.status_code==200 for r in results))
t.check('fresh concurrent generation identical result',results[0].json()==results[1].json())
v=results[0].json()['versionId'];sign=dict(context=dict(ctx,operationId='fresh-race-sign-3'),input=dict(versionId=v,signers=[dict(name='Synthetic Alice Customer',email='alice@example.test'),dict(name='Synthetic Bob Supplier',email='bob@example.test')]))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:t.call('/v1/signature-requests',sign),range(2)))
t.check('fresh concurrent signing both succeed',all(r.status_code==200 for r in results))
t.check('fresh concurrent signing identical result',results[0].json()==results[1].json())
t.check('fresh exactly one version',len(t.call('/v1/documents/fresh-race-contract-3/versions?tenantId=synthetic-a').json())==1)
(t.ROOT/'artifacts/concurrency-tests.json').write_text(json.dumps(dict(result='PASS',checks=t.checks),indent=2))
