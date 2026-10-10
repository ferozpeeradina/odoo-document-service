# Odoo shell; output is redirected into ignored runtime/signers.json.
import json
request = env['poc.envelope'].search([], order='id desc', limit=1).request_id
result = {}
for signer in request.signer_ids:
    key = signer.partner_id.email.split('@')[0]
    result[key] = {'signerId': signer.id, 'token': signer.access_token}
print(json.dumps(result))
