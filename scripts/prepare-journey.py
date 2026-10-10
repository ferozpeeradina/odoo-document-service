#!/usr/bin/env python3
import json
from local_client import ROOT, api, session, fixtures
issuer = session('issuer')
f = fixtures()
ctx = {'tenantId': 'synthetic-a', 'documentId': 'synthetic-cad-contract-final', 'projectId': 'synthetic-project-001', 'operationId': 'contract-generate-final', 'localDocumentId': 'local-contract-001'}
input = {'templateId': 'synthetic-cad-contract', 'templateVersion': '1', 'snapshot': json.loads((ROOT / 'runtime/business.json').read_text())['snapshot']}
result = api(issuer, 'generate', ctx, input)
assert 'data' in result, result
v = result['data']
signctx = dict(ctx, operationId='contract-sign-final')
signinput = {'versionId': v['versionId'], 'signers': [{'name': f[k]['name'], 'email': f[k]['login']} for k in ('alice', 'bob')]}
sign = api(issuer, 'signRequest', signctx, signinput)
assert 'data' in sign, sign
journey = {'context': ctx, 'input': input, 'version': v, 'signContext': signctx, 'signInput': signinput, 'request': sign['data']}
(ROOT / 'runtime/journey.json').write_text(json.dumps(journey))
unsigned = issuer.get('http://127.0.0.1:18069/poc/artifact/' + v['versionId'] + '/document')
assert unsigned.status_code == 200 and unsigned.content.startswith(b'%PDF')
(ROOT / 'artifacts/unsigned-contract.pdf').write_bytes(unsigned.content)
print(json.dumps({'generated': v, 'signatureRequest': sign['data']}, indent=2))
