# Coordinator executes only on a separately installed production database.
import secrets,os
if os.environ.get('DOCUMENT_SERVICE_MODE')!='production':raise ValueError('production configuration required')
env['ir.config_parameter'].set_param('ir_attachment.location','db')
for key in ('purchase_order','packing_list','invoice','ledger_statement','contract'):
    if not env['poc.template'].search([('key','=',key),('version','=','1')]):env['poc.template']._register_service(key)
env.ref('base.user_admin').write({'password':secrets.token_urlsafe(40)})
env['ir.cron'].search([]).write({'active':False})
env['ir.mail_server'].search([]).unlink()
for key,value in [('web.base.url',os.environ['PUBLIC_ORIGIN']),('web.base.url.freeze','True'),('report.url','http://127.0.0.1:8069')]:env['ir.config_parameter'].set_param(key,value)
env.company.write({'sign_oca_send_sign_request_copy':False})
env['ir.attachment'].force_storage()
env.cr.commit()
