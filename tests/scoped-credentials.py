import importlib.util,json,sys
s=importlib.util.spec_from_file_location('t','tests/http_service.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
try:
    b={'Authorization':'Bearer '+(t.ROOT/'service-runtime/tenant-b.token').read_text().strip()}
    a=json.loads((t.ROOT/'service-runtime/test-association.json').read_text());p='/v1/documents/'+a['context']['documentId']+'/versions/'+a['versionId']
    t.check('individually registered second credential works',t.call('/v1/templates/contract/versions/1',headers=b).status_code==200)
    t.check('second credential cannot impersonate first tenant',t.call(p+'/artifacts?tenantId=synthetic-a',headers=b).status_code==403)
    t.check('second tenant cannot read first tenant version',t.call(p+'/download/signed_document?tenantId=synthetic-b&projectId=project-b',headers=b).status_code==403)
    t.check('first credential cannot claim second tenant',t.call('/v1/documents/other/versions?tenantId=synthetic-b&projectId=project-b').status_code==403)
    t.check('allowed operator cannot claim unregistered project',t.call('/v1/documents/other/versions?tenantId=synthetic-b&projectId=project-a',headers=b).status_code==403)
    (t.ROOT/'artifacts/credential-tests.json').write_text(json.dumps(dict(result='PASS',checks=t.checks),indent=2))
except Exception as e:
    print('FAIL '+(str(e) if isinstance(e,AssertionError) else type(e).__name__));sys.exit(1)
