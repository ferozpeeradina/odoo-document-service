import importlib.util, json, hashlib, pathlib, sys
s=importlib.util.spec_from_file_location('t','tests/http_service.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
sys.path.insert(0,str(t.ROOT/'service'));from verify import verify
a=json.loads((t.ROOT/'service-runtime/test-association.json').read_text());c=a['context'];v=a['versionId'];p='/v1/documents/'+c['documentId']+'/versions/'+v
checks=[]
def check(name,ok):
    if not ok:raise AssertionError(name)
    checks.append(name);print('PASS '+name)
try:
    r=t.call('/v1/signature-requests/'+a['requestId']+'/status',dict(context=dict(c,operationId='complete-check'),input=dict(versionId=v)))
    check('completion persisted',r.status_code==200 and r.json()=={'status':'completed'})
    r=t.call(p+'/artifacts?tenantId='+c['tenantId']);check('three artifacts after completion',r.status_code==200 and {x['kind'] for x in r.json()}=={'document','signed_document','evidence'})
    downloaded={}
    for kind in ('document','signed_document','evidence'):
        url=p+'/download/'+kind+'?tenantId='+c['tenantId'];r=t.call(url)
        check('authenticated download '+kind,r.status_code==200)
        check('wrong tenant download blocked '+kind,t.call(p+'/download/'+kind+'?tenantId=synthetic-b').status_code==403)
        check('anonymous download blocked '+kind,t.call(url,headers={}).status_code==403)
        downloaded[kind]=r.content
    cert=t.ROOT/'service-runtime/seal.crt'; evidence=json.loads(downloaded['evidence']);pdf=downloaded['signed_document']
    verify(pdf,evidence,str(cert));check('independent PDF and evidence signatures',True)
    check('sealed PDF differs from unsigned',pdf!=downloaded['document'])
    m=evidence['manifest'];check('two exact verified recipients',{s['email'] for s in m['verifiedRecipients']}=={'alice@example.test','bob@example.test'})
    check('exact association',m['association']['versionId']==v and m['association']['projectId']==c['projectId'] and m['association']['tenantId']==c['tenantId'])
    check('service seal TEST limitations explicit',m['fixture'] is True and 'TEST' in m['seal']['trust'] and m['seal']['timestamp']=='No trusted timestamp')
    for label,changed_pdf,changed_evidence in [('PDF tamper',pdf+b'corruption',evidence),('evidence tamper',pdf,dict(evidence,manifest=dict(m,requestId='changed')))]:
        try:verify(changed_pdf,changed_evidence,str(cert));ok=False
        except Exception:ok=True
        check('offline rejects '+label,ok)
    if sys.argv[1:] == ['restart']:
        for kind,raw in downloaded.items():
            suffix='.json' if kind=='evidence' else '.pdf'
            check('restart byte identity '+kind,raw==(t.ROOT/'artifacts'/('final-'+kind+suffix)).read_bytes())
    else:
        for kind,raw in downloaded.items():
            (t.ROOT/'artifacts'/('final-'+kind+('.json' if kind=='evidence' else '.pdf'))).write_bytes(raw)
        (t.ROOT/'artifacts/verification-public.crt').write_bytes(cert.read_bytes())
    (t.ROOT/'artifacts'/('restart-tests.json' if sys.argv[1:] else 'artifact-tests.json')).write_text(json.dumps(dict(result='PASS',checks=checks,hashes={kind:hashlib.sha256(raw).hexdigest() for kind,raw in downloaded.items()}),indent=2))
except Exception as e:
    print('FAIL '+(str(e) if isinstance(e,AssertionError) else type(e).__name__));sys.exit(1)
