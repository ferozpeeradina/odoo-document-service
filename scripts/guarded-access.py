#!/usr/bin/env python3
import json, requests
from local_client import ROOT, BASE, fixtures, session, rpc
f = fixtures()['upstream']
outsider = session('mallory')
alice = session('alice')
anonymous = requests.Session()
report = {'scope': 'Guarded OCA routes', 'tests': []}
def check(name, passed, detail):
    assert passed, name
    report['tests'].append({'name': name, 'result': 'PASS', 'detail': detail})
check('unrelated_request_download_denied', outsider.get(BASE + f"/my/sign/{f['requestId']}/download").status_code == 403, 'Exact request ownership enforced')
for route in ('document', 'content'):
    path = f"/sign_oca/{route}/{f['signerId']}/{f['token']}"
    check('anonymous_' + route + '_denied', anonymous.get(BASE + path, allow_redirects=False).status_code == 303, 'Login required before loading private data')
    check('forwarded_' + route + '_denied', outsider.get(BASE + path, allow_redirects=False).status_code == 403, 'Logged-in unrelated account cannot use recipient bearer link')
for route in ('info', 'sign'):
    path = f"/sign_oca/{route}/{f['signerId']}/{f['token']}"
    params = {'items': {}} if route == 'sign' else {}
    check('forwarded_' + route + '_denied', 'error' in rpc(outsider, path, params), 'Recipient account binding enforced for JSON-RPC')
    check('anonymous_' + route + '_denied', 'error' in rpc(anonymous, path, params), 'Anonymous JSON-RPC denied')
leaked = json.loads((ROOT / 'runtime/upstream-leaked.json').read_text())['attachmentUrl']
revoked = anonymous.get(BASE + leaked)
check('legacy_attachment_token_revoked', revoked.status_code != 200 or not revoked.content.startswith(b'%PDF'), 'Previously leaked upstream attachment bearer token revoked by install hook')
check('recipient_still_downloads_own_request', alice.get(BASE + f"/my/sign/{f['requestId']}/download").status_code == 200, 'Existing OCA request remains usable by exact recipient')
(ROOT / 'artifacts/guarded-access.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
