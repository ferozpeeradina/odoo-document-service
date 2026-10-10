from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import consteq
from odoo.addons.sign_oca.controllers.main import PortalSign

class GuardedPortalSign(PortalSign):
    def _recipient(self, signer_id, access_token):
        signer = request.env['sign.oca.request.signer'].sudo().browse(signer_id).exists()
        if not signer or not signer.access_token or not consteq(signer.access_token, access_token) or request.env.user.partner_id != signer.partner_id:
            raise AccessError('recipient_identity_mismatch')
        envelope = request.env['poc.envelope'].sudo().search([('request_id', '=', signer.request_id.id)], limit=1)
        if envelope:
            envelope._verify()
        return signer

    @http.route(auth='user')
    def get_sign_oca_access(self, signer_id, access_token, **kwargs):
        try:
            self._recipient(signer_id, access_token)
        except AccessError:
            return request.make_response('access_denied', status=403)
        except ValidationError:
            return request.make_response('integrity_failed', status=409)
        return super().get_sign_oca_access(signer_id, access_token, **kwargs)

    @http.route(auth='user')
    def get_sign_oca_content_access(self, signer_id, access_token):
        try:
            self._recipient(signer_id, access_token)
        except AccessError:
            return request.make_response('access_denied', status=403)
        except ValidationError:
            return request.make_response('integrity_failed', status=409)
        return super().get_sign_oca_content_access(signer_id, access_token)

    @http.route(auth='user')
    def get_sign_oca_info_access(self, signer_id, access_token):
        signer = self._recipient(signer_id, access_token)
        return signer.get_info(access_token=False)

    @http.route(auth='user')
    def get_sign_oca_sign_access(self, signer_id, access_token, items, latitude=False, longitude=False):
        signer = self._recipient(signer_id, access_token)
        return signer.action_sign(items, latitude=latitude, longitude=longitude)

    @http.route()
    def portal_download_signed(self, request_id, **kw):
        doc = request.env['sign.oca.request'].sudo().browse(request_id).exists()
        if not doc:
            return request.not_found()
        envelope = request.env['poc.envelope'].sudo().search([('request_id', '=', doc.id)], limit=1)
        member = request.env['poc.member'].sudo().search([('user_id', '=', request.env.uid)], limit=1)
        owns = request.env.user.partner_id in doc.signer_ids.partner_id
        issues = envelope and member and member.can_issue and member.tenant_key == envelope.version_id.tenant_key
        if not owns and not issues:
            return request.make_response('access_denied', status=403)
        try:
            if envelope:
                envelope._verify()
            # Return bytes directly; never mint a bypassing attachment token.
            return http.Stream.from_binary_field(doc, 'data').get_response(mimetype='application/pdf')
        except ValidationError:
            return request.make_response('integrity_failed', status=409)
