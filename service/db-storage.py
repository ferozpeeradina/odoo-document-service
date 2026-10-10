env['ir.config_parameter'].set_param('ir_attachment.location','db')
env['ir.attachment'].force_storage()
env.cr.commit()
print('SAFE_RESULT database_attachment_storage_enabled')
