# New isolated database only; never prints principal passwords or credentials.
import pathlib, secrets
from odoo import Command
from odoo.addons.packaging_bridge.models.provider import digest
env['ir.config_parameter'].set_param('ir_attachment.location','db')
user=env['res.users'].with_context(no_reset_password=True).create(dict(name='Synthetic Document Operator',login='operator@example.test',email='operator@example.test',password=secrets.token_urlsafe(40),group_ids=[Command.set([env.ref('base.group_portal').id])]))
env['poc.member'].create(dict(user_id=user.id,tenant_key='synthetic-a',can_issue=True))
env['document.credential'].create(dict(token_hash=digest(pathlib.Path('/run/config/service.token').read_bytes().strip()),user_id=user.id,tenant='synthetic-a',projects=['project-a']))
for key in ('purchase_order','packing_list','invoice','ledger_statement','contract'): env['poc.template']._register_service(key)
env.ref('base.user_admin').write({'password':secrets.token_urlsafe(40)})
env['ir.cron'].search([]).write({'active':False})
env['ir.mail_server'].search([]).unlink()
env['ir.config_parameter'].set_param('web.base.url','https://documents.agentfleet.services')
env['ir.config_parameter'].set_param('web.base.url.freeze','True')
env['ir.config_parameter'].set_param('report.url','http://127.0.0.1:8069')
env.company.write(dict(name='Synthetic Document Service',email='operator@example.test',sign_oca_send_sign_request_copy=False))
env['ir.attachment'].force_storage()
env.cr.commit()
