import base64
import io
from PIL import Image
from odoo import models
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.packaging_bridge.models.provider import canonical, digest

class RecipientGuard(models.Model):
    _inherit = 'sign.oca.request.signer'

    def action_sign(self, items, access_token=False, latitude=False, longitude=False):
        self.ensure_one()
        if self.env.user._is_public() or self.env.user.partner_id != self.partner_id:
            raise AccessError('recipient_identity_mismatch')
        envelope = self.env['poc.envelope'].sudo().search([('request_id', '=', self.request_id.id)], limit=1)
        if envelope:
            envelope._lock()
            envelope._verify()
        # OCA accepts an entire field object. Keep metadata server-owned, allowing
        # only values for this recipient's existing fields to reach the engine.
        clean = dict(self.request_id.signatory_data)
        for key, original in self.request_id.signatory_data.items():
            if original['role_id'] != self.role_id.id:
                continue
            supplied = items.get(key)
            if not supplied or any(supplied.get(k) != v for k, v in original.items() if k != 'value'):
                raise ValidationError('signing_field_metadata_changed')
            value = supplied.get('value')
            if original['required'] and not value:
                raise ValidationError('required_signature_missing')
            if original['field_type'] == 'signature' and value:
                try:
                    if not value.startswith('data:image/png;base64,'):
                        raise ValueError()
                    raw = base64.b64decode(value.split(',', 1)[1], validate=True)
                    if len(raw) > 1024 * 1024:
                        raise ValueError()
                    image = Image.open(io.BytesIO(raw))
                    if image.format != 'PNG':
                        raise ValueError()
                    image.verify()
                except Exception as exc:
                    raise ValidationError('invalid_signature_image') from exc
            clean[key] = dict(original, value=value)
        result = super().action_sign(clean, access_token=False, latitude=latitude, longitude=longitude)
        if envelope:
            pdf = base64.b64decode(self.request_id.with_context(bin_size=False).data)
            envelope._set({'expected_hash': digest(pdf), 'expected_items_hash': digest(canonical(self.request_id.signatory_data)), 'active_state_hash': digest(canonical(envelope._state()))})
        return result
