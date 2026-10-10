from odoo import http
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request
from ..models.provider import decoded

class DocumentAPI(http.Controller):
    @http.route('/poc/api', type='jsonrpc', auth='user', methods=['POST'])
    def api(self, method, context=None, input=None):
        try:
            with request.env.cr.savepoint():
                result = request.env['poc.provider']._dispatch(method, context or {}, input or {})
            return {'data': result}
        except AccessError:
            return {'error': {'code': 'access_denied', 'message': 'Document access denied'}}
        except ValidationError as exc:
            return {'error': {'code': str(exc).split(':')[0], 'message': str(exc)}}
        except (ValueError, KeyError, TypeError):
            return {'error': {'code': 'invalid_input', 'message': 'Invalid document input'}}

    @http.route('/poc/artifact/<string:version_key>/<string:kind>', type='http', auth='user', methods=['GET'])
    def artifact(self, version_key, kind):
        v = request.env['poc.version'].sudo().search([('version_key', '=', version_key)], limit=1)
        if not v:
            return request.not_found()
        context = dict(v._descriptor(), operationId='artifact-read')
        try:
            request.env['poc.provider']._member(context)
            v._verify()
            envelope = request.env['poc.envelope'].sudo().search([('version_id', '=', v.id)], limit=1)
            if envelope:
                envelope._verify()
            if kind == 'document':
                file = v.unsigned_file_id
                mimetype = v.content_type
            elif kind in ('signed_document', 'evidence') and envelope and envelope.evidence_file_id:
                file = envelope.signed_file_id if kind == 'signed_document' else envelope.evidence_file_id
                mimetype = 'application/pdf' if kind == 'signed_document' else 'application/json'
            else:
                return request.not_found()
            return request.make_response(decoded(file), headers=[('Content-Type', mimetype), ('Cache-Control', 'no-store'), ('Content-Disposition', 'attachment; filename="' + kind + ('.json"' if kind == 'evidence' else '.pdf"'))])
        except AccessError:
            return request.make_response('access_denied', status=403)
        except ValidationError:
            return request.make_response('integrity_failed', status=409)
