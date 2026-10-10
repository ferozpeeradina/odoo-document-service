# Executed inside `odoo shell` on a NEW isolated database only.
import json, secrets
from odoo import Command
accounts = {}
portal = env.ref('base.group_portal')
for key, name, email, tenant, issue in [
    ('issuer', 'Synthetic Document Operator', 'operator@example.test', 'synthetic-a', True),
    ('alice', 'Synthetic Alice Customer', 'alice@example.test', 'synthetic-a', False),
    ('bob', 'Synthetic Bob Supplier', 'bob@example.test', 'synthetic-a', False),
    ('mallory', 'Synthetic Mallory Unrelated', 'mallory@example.test', 'synthetic-c', False),
]:
    password = secrets.token_urlsafe(30)
    user = env['res.users'].with_context(no_reset_password=True).create({'name': name, 'login': email, 'email': email, 'password': password, 'group_ids': [Command.set([portal.id])]})
    env['poc.member'].create({'user_id': user.id, 'tenant_key': tenant, 'can_issue': issue})
    accounts[key] = {'login': email, 'password': password, 'uid': user.id, 'partnerId': user.partner_id.id, 'name': name, 'tenantId': tenant}
# Deactivate default access, and prevent auto-dispatch via cron.
env.ref('base.user_admin').write({'password': secrets.token_urlsafe(40)})
env['ir.cron'].search([]).write({'active': False})
env['ir.mail_server'].search([]).unlink()
env['ir.config_parameter'].set_param('web.base.url', 'http://127.0.0.1:18069')
env['ir.config_parameter'].set_param('web.base.url.freeze', 'True')
env['ir.config_parameter'].set_param('report.url', 'http://127.0.0.1:8069')
env.company.write({'name': 'SYNTHETIC Packaging POC', 'email': 'demo@example.test', 'sign_oca_send_sign_request_copy': False})
template = env['poc.template']._register_template('synthetic-cad-contract', '1')
# Source review and runtime reproduction target: an unguarded OCA request.
# A text field exercises actual OCA action_sign without custom PDF painting.
from odoo.addons.packaging_bridge.models.provider import canonical, digest
snapshot = {'synthetic': True, 'currency': 'CAD', 'customer': 'Synthetic Alder Boxes Ltd', 'supplier': 'Synthetic Birch Packaging Ltd', 'description': '100 demonstration cartons', 'quantity': 100, 'totalCents': 125000, 'terms': 'Synthetic demonstration only; no obligations.'}
provider = env['poc.provider'].with_user(accounts['issuer']['uid'])
ctx = {'tenantId': 'synthetic-a', 'documentId': 'upstream-audit', 'projectId': 'upstream-project', 'operationId': 'upstream-generate-1'}
version = provider._dispatch('generate', ctx, {'templateId': template.key, 'templateVersion': template.version, 'snapshot': snapshot})
v = env['poc.version'].search([('version_key', '=', version['versionId'])])
role = env.ref('sign_oca.sign_role_customer')
field = env.ref('sign_oca.sign_field_text')
items = {'1': {'id': 1, 'field_id': field.id, 'field_type': 'text', 'required': True, 'name': 'Synthetic acknowledgement', 'role_id': role.id, 'page': 1, 'position_x': 20, 'position_y': 55, 'width': 38, 'height': 9, 'value': False, 'default_value': False, 'placeholder': '', 'tabindex': 1}}
req = env['sign.oca.request'].create({'name': 'SYNTHETIC upstream access audit', 'data': v.unsigned_file_id.content, 'signatory_data': items, 'signer_ids': [Command.create({'partner_id': accounts['alice']['partnerId'], 'role_id': role.id})]})
req.action_send()
signer = req.signer_ids
accounts['upstream'] = {'requestId': req.id, 'signerId': signer.id, 'token': signer.access_token, 'versionId': version['versionId']}
accounts['snapshot'] = snapshot
env.cr.commit()
print(json.dumps(accounts))
