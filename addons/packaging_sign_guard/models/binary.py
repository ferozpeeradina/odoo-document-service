from odoo import models
from odoo.exceptions import AccessError

class GuardedSigningBinary(models.Model):
    _inherit = 'ir.binary'

    def _find_record(self, xmlid=None, res_model='ir.attachment', res_id=None, access_token=None, field=None):
        record = super()._find_record(xmlid=xmlid, res_model=res_model, res_id=res_id, access_token=access_token, field=field)
        doc = None
        if record._name == 'sign.oca.request':
            doc = record.sudo()
        elif record._name == 'sign.oca.request.signer':
            doc = record.sudo().request_id
        elif record._name == 'ir.attachment' and record.sudo().res_model == 'sign.oca.request':
            doc = self.env['sign.oca.request'].sudo().browse(record.sudo().res_id).exists()
        if doc:
            envelope = self.env['poc.envelope'].sudo().search([('request_id', '=', doc.id)], limit=1)
            member = self.env['poc.member'].sudo().search([('user_id', '=', self.env.uid)], limit=1)
            owns = not self.env.user._is_public() and self.env.user.partner_id in doc.signer_ids.partner_id
            issues = envelope and member and member.can_issue and member.tenant_key == envelope.version_id.tenant_key
            if not owns and not issues:
                raise AccessError('signing_binary_access_denied')
            if envelope:
                envelope._verify()
        return record
