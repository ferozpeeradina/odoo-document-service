# Existing Odoo shell only. Every deliberate mutation is rolled back; no commit.
import base64
import copy
import json
from odoo import models
from odoo.exceptions import ValidationError
from odoo.addons.packaging_bridge.models.provider import canonical, decoded, digest

version = env['poc.version'].search([('document_key', '=', 'synthetic-cad-contract-final')])
assert len(version) == 1
envelope = env['poc.envelope'].search([('version_id', '=', version.id)])
assert envelope.evidence_file_id and envelope.signed_file_id
issuer = env['res.users'].search([('login', '=', 'operator@example.test')], limit=1)
provider = env['poc.provider'].with_user(issuer)
context = dict(version._descriptor(), operationId='tamper-read')

def baseline():
    envelope._verify()
    return {
        'association': version._descriptor(),
        'snapshot': digest(canonical(version.snapshot)),
        'unsigned': digest(decoded(version.unsigned_file_id)),
        'signed': digest(decoded(envelope.signed_file_id)),
        'evidence': digest(decoded(envelope.evidence_file_id)),
        'items': digest(canonical(envelope.request_id.signatory_data)),
        'state': digest(canonical(envelope._state())),
    }

original = baseline()
tests = []
class Restore(Exception):
    pass

def mutation(name, change):
    denied = False
    try:
        with env.cr.savepoint():
            change()
            env.flush_all()
            env.invalidate_all(flush=False)
            try:
                provider._dispatch('artifacts', context, {'versionId': version.version_key})
            except ValidationError as exc:
                denied = str(exc).startswith('integrity_failed:')
            assert denied, name + '_not_detected'
            raise Restore()
    except Restore:
        pass
    env.invalidate_all(flush=False)
    assert baseline() == original, name + '_rollback_mismatch'
    tests.append({'name': name, 'result': 'PASS', 'read': 'integrity_failed', 'restore': 'transaction rollback; all baseline hashes and associations unchanged'})

changed = copy.deepcopy(version.snapshot)
changed['totalCents'] += 1
mutation('stored_snapshot', lambda: models.Model.write(version, {'snapshot': changed}))
items = copy.deepcopy(envelope.request_id.signatory_data)
items['1']['page'] = 999
mutation('stored_signing_fields', lambda: envelope.request_id.write({'signatory_data': items}))
mutation('stored_unsigned_pdf', lambda: version.unsigned_file_id.write({'content': base64.b64encode(b'%PDF tampered unsigned')}))
mutation('stored_template_snapshot', lambda: version.template_id.arch_file_id.write({'content': base64.b64encode(b'<tampered/>')}))
mutation('stored_active_pdf', lambda: envelope.request_id.write({'data': base64.b64encode(b'%PDF tampered active')}))
mutation('stored_completed_pdf', lambda: envelope.signed_file_id.write({'content': base64.b64encode(b'%PDF tampered completed')}))
mutation('stored_frozen_evidence', lambda: envelope.evidence_file_id.write({'content': base64.b64encode(b'{"tampered":true}')}))
mutation('stored_signer_completion', lambda: envelope.request_id.signer_ids[:1].write({'signed_on': False}))
assert provider._dispatch('update', context, {'versionId': version.version_key, 'requestId': str(envelope.request_id.id)}) == {'status': 'signed'}
assert baseline() == original
env.cr.rollback()
print(json.dumps({'tests': tests, 'baseline': original, 'final': 'legitimate signed records unchanged; no mutation committed'}, indent=2))
