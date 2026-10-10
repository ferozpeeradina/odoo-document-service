#!/usr/bin/env python3
import json, hashlib, requests, sys
from local_client import ROOT, BASE, fixtures, session, rpc, api
j = json.loads((ROOT / 'runtime/journey.json').read_text())
f = fixtures()
issuer = session('issuer')
outsider = session('mallory')
alice = session('alice')
phase = sys.argv[1]
report = {'phase': phase, 'tests': []}
def check(name, value, detail=''):
    assert value, name
    report['tests'].append({'name': name, 'result': 'PASS', 'detail': detail})
def update():
    return api(issuer,'update',j['context'],{'versionId':j['version']['versionId'],'requestId':j['request']['requestId']})
def artifact(kind, client=issuer):
    return client.get(BASE + '/poc/artifact/' + j['version']['versionId'] + '/' + kind)
if phase == 'security':
    targets = json.loads((ROOT / 'runtime/signers.json').read_text())
    check('forged_tenant_read_denied', 'error' in api(outsider,'versions',j['context']))
    ownctx = dict(j['context'], tenantId='synthetic-c')
    check('own_tenant_foreign_version_denied','error' in api(outsider,'artifacts',ownctx,{'versionId':j['version']['versionId']}))
    check('cross_tenant_artifact_download_denied',artifact('document',outsider).status_code==403)
    check('cross_tenant_envelope_download_denied',outsider.get(BASE + '/my/sign/' + j['request']['requestId'] + '/download').status_code == 403)
    target = targets['alice']
    for route in ('content','document'):
        check('cross_recipient_' + route + '_denied',outsider.get(BASE + f"/sign_oca/{route}/{target['signerId']}/{target['token']}",allow_redirects=False).status_code==403)
    check('cross_recipient_sign_denied','error' in rpc(outsider,f"/sign_oca/sign/{target['signerId']}/{target['token']}",{'items':{}}))
    info = rpc(alice,f"/sign_oca/info/{target['signerId']}/{target['token']}")['result']
    changed = json.loads(json.dumps(info['items']))
    changed['1']['page'] = 999
    check('signing_metadata_mutation_rejected','error' in rpc(alice,f"/sign_oca/sign/{target['signerId']}/{target['token']}",{'items':changed}))
    check('missing_required_signature_rejected','error' in rpc(alice,f"/sign_oca/sign/{target['signerId']}/{target['token']}",{'items':info['items']}))
    check('malformed_signature_rejected','error' in rpc(alice,f"/sign_oca/sign/{target['signerId']}/{target['token']}",{'items':dict(info['items'],**{'1':dict(info['items']['1'],value='data:image/png;base64,AAAA')})}))
    check('failed_signatures_leave_pending',update()=={'data':{'status':'pending'}})
    raw = outsider.get(BASE + '/web/content',params={'model':'sign.oca.request','id':j['request']['requestId'],'field':'data'})
    check('direct_binary_route_denied',raw.status_code!=200 or not raw.content.startswith(b'%PDF'))
elif phase == 'partial':
    check('one_signature_is_partial',update()=={'data':{'status':'partial'}})
    for kind in ('signed_document','evidence'):
        check('partial_' + kind + '_unavailable',artifact(kind).status_code == 404)
    check('partial_artifacts_only_unsigned',len(api(issuer,'artifacts',j['context'],{'versionId':j['version']['versionId']})['data'])==1)
elif phase in ('complete','restart','mutated'):
    check('fully_signed_status',update()=={'data':{'status':'signed'}})
    artifacts = api(issuer,'artifacts',j['context'],{'versionId':j['version']['versionId']})['data']
    check('all_three_artifacts_available',{a['kind'] for a in artifacts}=={'document','signed_document','evidence'})
    hashes = {}
    for kind, name in [('document','unsigned-contract.pdf'),('signed_document','signed-contract.pdf'),('evidence','frozen-certificate.json')]:
        response = artifact(kind)
        check(kind + '_retrievable',response.status_code==200)
        hashes[kind] = hashlib.sha256(response.content).hexdigest()
        if phase == 'complete' and kind != 'document':
            (ROOT / 'artifacts' / name).write_bytes(response.content)
        check(kind + '_same_bytes',response.content==(ROOT / 'artifacts' / name).read_bytes())
    certificate = json.loads((ROOT / 'artifacts/frozen-certificate.json').read_text())
    check('certificate_document_association',certificate['association']==j['version'] and certificate['requestId']==j['request']['requestId'])
    check('two_distinct_signers',{s['email'] for s in certificate['signers']}=={'alice@example.test','bob@example.test'} and all(s['signedOnUtc'] for s in certificate['signers']))
    check('audit_has_two_sign_events',len([a for a in certificate['audit'] if a['action']=='sign'])==2)
    check('certificate_hashes_match',certificate['hashes']['unsignedPdfSha256']==hashes['document'] and certificate['hashes']['signedPdfSha256']==hashes['signed_document'])
    check('unsigned_preserved_and_differs_from_signed',hashes['document']!=hashes['signed_document'])
    check('cross_tenant_signed_download_denied',artifact('signed_document',outsider).status_code==403)
    check('cross_tenant_evidence_download_denied',artifact('evidence',outsider).status_code==403)
    report['hashes'] = hashes
else:
    raise SystemExit('unknown phase')
(ROOT / ('artifacts/acceptance-' + phase + '.json')).write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
