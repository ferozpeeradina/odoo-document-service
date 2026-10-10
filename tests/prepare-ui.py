import importlib.util,json,os
s=importlib.util.spec_from_file_location('t','tests/http_service.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
ctx=dict(t.CTX,documentId='otp-browser-contract-final',operationId='otp-browser-generate-final')
v=t.call('/v1/documents',dict(context=ctx,input=dict(templateId='contract',templateVersion='1',snapshot=t.SNAP)))
assert v.status_code==200,'synthetic contract generation'
sign=t.call('/v1/signature-requests',dict(context=dict(ctx,operationId='otp-browser-sign-final'),input=dict(versionId=v.json()['versionId'],signers=[dict(name='Synthetic Alice Customer',email='alice@example.test'),dict(name='Synthetic Bob Supplier',email='bob@example.test')])))
assert sign.status_code==200,'synthetic sign request'
fd=os.open(t.ROOT/'service-runtime/test-association.json',os.O_CREAT|os.O_WRONLY|os.O_TRUNC,0o600)
with os.fdopen(fd,'w') as f:json.dump(dict(context=ctx,versionId=v.json()['versionId'],requestId=sign.json()['requestId']),f)
print('PASS prepared saved synthetic contract for OTP browser journey')
