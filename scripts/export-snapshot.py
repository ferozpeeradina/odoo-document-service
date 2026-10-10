# Read-only recovery of the already saved immutable synthetic snapshot.
# Run in the existing Odoo shell; redirect stdout to runtime/business.json.
import json
version = env['poc.version'].search([('document_key', '=', 'upstream-audit')], limit=1)
assert version and version.snapshot.get('synthetic') is True
version._verify()
print(json.dumps({'snapshot': version.snapshot}))
