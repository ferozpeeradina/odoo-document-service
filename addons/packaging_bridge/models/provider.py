import base64
import hashlib
import json
import uuid
from lxml import etree
from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def decoded(record):
    return base64.b64decode(record.with_context(bin_size=False).content or b'')


class Member(models.Model):
    _name = 'poc.member'
    _description = 'Trusted sandbox tenant membership'
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')
    tenant_key = fields.Char(required=True)
    can_issue = fields.Boolean(default=False)
    active = fields.Boolean(default=True)
    _unique_user = models.Constraint('UNIQUE(user_id)', 'One trusted tenant per sandbox user.')


class Frozen(models.AbstractModel):
    _name = 'poc.frozen'
    _description = 'Immutable provider record'

    def write(self, vals):
        raise AccessError('Frozen provider records cannot be edited.')

    def unlink(self):
        raise AccessError('Frozen provider records cannot be deleted.')


class Template(models.Model):
    _name = 'poc.template'
    _inherit = 'poc.frozen'
    _description = 'Frozen template version'
    key = fields.Char(required=True)
    version = fields.Char(required=True)
    arch_file_id = fields.Many2one('dms.file', required=True)
    arch_hash = fields.Char(required=True)
    view_id = fields.Many2one('ir.ui.view', required=True)
    report_id = fields.Many2one('ir.actions.report', required=True)
    _unique_version = models.Constraint('UNIQUE(key, version)', 'Template version already exists.')

    @api.model
    def _register_template(self, key, version):
        source = self.env.ref('packaging_bridge.contract_document')
        arch = source.arch_db.encode()
        view_key = 'packaging_bridge.frozen_' + uuid.uuid4().hex
        tree = etree.fromstring(arch)
        tree.set('t-name', view_key)
        frozen_arch = etree.tostring(tree, encoding='unicode')
        view = self.env['ir.ui.view'].create({'name': view_key, 'type': 'qweb', 'key': view_key, 'arch_db': frozen_arch})
        report = self.env['ir.actions.report'].create({'name': 'Synthetic frozen CAD contract', 'model': 'poc.version', 'report_type': 'qweb-pdf', 'report_name': view_key})
        file = self.env['poc.provider']._file('template-' + version + '.xml', frozen_arch.encode())
        return self.create({'key': key, 'version': version, 'arch_file_id': file.id, 'arch_hash': digest(frozen_arch.encode()), 'view_id': view.id, 'report_id': report.id})

    def _verify(self):
        self.ensure_one()
        if digest(decoded(self.arch_file_id)) != self.arch_hash or digest(self.view_id.arch_db.encode()) != self.arch_hash:
            raise ValidationError('integrity_failed: frozen template has changed')


class Version(models.Model):
    _name = 'poc.version'
    _inherit = 'poc.frozen'
    _description = 'Immutable document version and business snapshot'
    tenant_key = fields.Char(required=True)
    document_key = fields.Char(required=True)
    project_key = fields.Char(required=True)
    local_document_key = fields.Char()
    version_key = fields.Char(required=True, default=lambda self: str(uuid.uuid4()))
    template_id = fields.Many2one('poc.template')
    template_key = fields.Char()
    template_version = fields.Char()
    snapshot = fields.Json()
    snapshot_hash = fields.Char()
    snapshot_file_id = fields.Many2one('dms.file')
    unsigned_file_id = fields.Many2one('dms.file')
    unsigned_hash = fields.Char()
    content_type = fields.Char(default='application/pdf')
    _unique_version = models.Constraint('UNIQUE(version_key)', 'Version exists.')

    def _descriptor(self):
        self.ensure_one()
        result = {'tenantId': self.tenant_key, 'documentId': self.document_key, 'projectId': self.project_key, 'versionId': self.version_key, 'fixture': True}
        if self.local_document_key:
            result['localDocumentId'] = self.local_document_key
        return result

    def _verify(self):
        self.ensure_one()
        if not self.unsigned_file_id or digest(decoded(self.unsigned_file_id)) != self.unsigned_hash:
            raise ValidationError('integrity_failed: unsigned document changed')
        if self.snapshot_file_id and (digest(decoded(self.snapshot_file_id)) != self.snapshot_hash or digest(canonical(self.snapshot)) != self.snapshot_hash):
            raise ValidationError('integrity_failed: snapshot changed')
        # Existing versions depend on their frozen XML file, not a mutable live view.
        if self.template_id and digest(decoded(self.template_id.arch_file_id)) != self.template_id.arch_hash:
            raise ValidationError('integrity_failed: frozen template snapshot changed')


class Operation(models.Model):
    _name = 'poc.operation'
    _inherit = 'poc.frozen'
    _description = 'Stable provider operation result'
    tenant_key = fields.Char(required=True)
    operation_key = fields.Char(required=True)
    input_hash = fields.Char(required=True)
    result = fields.Json(required=True)
    _unique_operation = models.Constraint('UNIQUE(tenant_key, operation_key)', 'Operation already exists.')


class Envelope(models.Model):
    _name = 'poc.envelope'
    _description = 'Signing association and integrity anchors'
    version_id = fields.Many2one('poc.version', required=True, ondelete='restrict')
    request_id = fields.Many2one('sign.oca.request', required=True, ondelete='restrict')
    expected_hash = fields.Char(required=True)
    active_state_hash = fields.Char()
    expected_items_hash = fields.Char(required=True)
    signer_binding_hash = fields.Char(required=True)
    signed_file_id = fields.Many2one('dms.file')
    signed_hash = fields.Char()
    evidence_file_id = fields.Many2one('dms.file')
    evidence_hash = fields.Char()
    final_state_hash = fields.Char()
    _unique_request = models.Constraint('UNIQUE(request_id)', 'Request already associated.')
    _unique_version = models.Constraint('UNIQUE(version_id)', 'Version already has an envelope.')

    def write(self, vals):
        raise AccessError('Provider integrity anchors are service managed.')

    def unlink(self):
        raise AccessError('Signing evidence cannot be deleted.')

    def _set(self, vals):
        return super().write(vals)

    def _binding(self):
        return [{'id': s.id, 'partner': s.partner_id.id, 'role': s.role_id.id} for s in self.request_id.signer_ids.sorted('id')]

    def _state(self):
        return {'request': self.request_id.id, 'state': self.request_id.state, 'signers': [{'id': s.id, 'signedOn': fields.Datetime.to_string(s.signed_on), 'signatureHash': s.signature_hash or '', 'inalterableHash': s.inalterable_hash or ''} for s in self.request_id.signer_ids.sorted('id')]}

    def _lock(self):
        self.env.cr.execute('SELECT id FROM poc_envelope WHERE id=%s FOR UPDATE', [self.id])
        self.invalidate_recordset()
        self.request_id.invalidate_recordset()
        self.request_id.signer_ids.invalidate_recordset()

    def _verify(self):
        self.ensure_one()
        self.version_id._verify()
        raw = base64.b64decode(self.request_id.with_context(bin_size=False).data or b'')
        if digest(raw) != self.expected_hash or digest(canonical(self.request_id.signatory_data)) != self.expected_items_hash or digest(canonical(self._binding())) != self.signer_binding_hash:
            raise ValidationError('integrity_failed: active signing request changed')
        if self.active_state_hash and digest(canonical(self._state())) != self.active_state_hash:
            raise ValidationError('integrity_failed: signer completion state changed')
        if self.evidence_file_id:
            if digest(decoded(self.signed_file_id)) != self.signed_hash or digest(decoded(self.evidence_file_id)) != self.evidence_hash or digest(canonical(self._state())) != self.final_state_hash:
                raise ValidationError('integrity_failed: completed document or evidence changed')
        return raw

    def _complete(self):
        self._lock()
        raw = self._verify()
        signers = self.request_id.signer_ids
        if self.request_id.state != '2_signed' or len(signers) < 2 or not all(signers.mapped('signed_on')):
            return 'partial' if any(signers.mapped('signed_on')) else 'pending'
        if not self.evidence_file_id:
            if self.request_id.current_hash != hashlib.sha1(raw).hexdigest():
                raise ValidationError('integrity_failed: engine final hash mismatch')
            logs = self.env['sign.oca.request.log'].search([('request_id', '=', self.request_id.id)], order='id')
            cert = {
                'schema': 'packaging-poc-evidence/1', 'synthetic': True,
                'association': self.version_id._descriptor(), 'requestId': str(self.request_id.id),
                'frozenAt': fields.Datetime.to_string(fields.Datetime.now()),
                'hashes': {'unsignedPdfSha256': self.version_id.unsigned_hash, 'signedPdfSha256': digest(raw), 'snapshotSha256': self.version_id.snapshot_hash, 'templateSha256': self.version_id.template_id.arch_hash},
                'signers': [{'signerId': s.id, 'name': s.partner_id.name, 'email': s.partner_id.email, 'signedOnUtc': fields.Datetime.to_string(s.signed_on), 'engineSignatureSha1': s.signature_hash, 'inalterableHash': s.inalterable_hash, 'sequence': s.secure_sequence_number} for s in signers.sorted('id')],
                'audit': [{'id': l.id, 'action': l.action, 'atUtc': fields.Datetime.to_string(l.date), 'userId': l.uid.id, 'partnerId': l.partner_id.id, 'signerId': l.signer_id.id or None, 'ip': l.ip} for l in logs],
                'pins': {'sign': '3b768318bc5eaccb79535337478f49d59d17d0b1', 'dms': '1a3098d1d6bbce6a38d06d9f361db319e7858fa3'},
                'limitations': ['App-level SHA-256 checks; no cryptographic PDF seal or trusted timestamp.', 'Synthetic local accounts; no mailbox verification, OTP or assurance of human identity.', 'Database administrator can rewrite bytes and anchors; external tamper-proof retention is not provided.'],
            }
            evidence = canonical(cert)
            provider = self.env['poc.provider']
            signed = provider._file('signed-' + self.version_id.version_key + '.pdf', raw)
            certificate = provider._file('evidence-' + self.version_id.version_key + '.json', evidence)
            self._set({'signed_file_id': signed.id, 'signed_hash': digest(raw), 'evidence_file_id': certificate.id, 'evidence_hash': digest(evidence), 'final_state_hash': digest(canonical(self._state()))})
        self._verify()
        return 'signed'


class Provider(models.AbstractModel):
    _name = 'poc.provider'
    _description = 'Tenant scoped document service'

    def _member(self, context, issue=False):
        # Caller-supplied tenant IDs are checked against trusted membership.
        member = self.env['poc.member'].sudo().search([('user_id', '=', self.env.uid)], limit=1)
        if not member or member.tenant_key != context.get('tenantId') or (issue and not member.can_issue):
            raise AccessError('tenant_access_denied')
        for key in ('tenantId', 'documentId', 'projectId', 'operationId'):
            if not isinstance(context.get(key), str) or not 0 < len(context[key]) <= 128:
                raise ValidationError('invalid_context')
        return member

    def _file(self, name, data):
        directory = self.env['dms.directory'].sudo().search([('name', '=', 'Packaging POC private frozen artifacts')], limit=1)
        if not directory:
            storage = self.env['dms.storage'].sudo().create({'name': 'Packaging POC database storage', 'save_type': 'database'})
            directory = self.env['dms.directory'].sudo().create({'name': 'Packaging POC private frozen artifacts', 'is_root_directory': True, 'storage_id': storage.id})
        return self.env['dms.file'].sudo().create({'name': name, 'directory_id': directory.id, 'content': base64.b64encode(data)})

    def _version(self, context, version_key):
        v = self.env['poc.version'].sudo().search([('tenant_key', '=', context['tenantId']), ('document_key', '=', context['documentId']), ('project_key', '=', context['projectId']), ('version_key', '=', version_key)], limit=1)
        if not v:
            raise AccessError('document_access_denied')
        v._verify()
        return v

    def _op(self, method, context, input, callback):
        self._member(context, issue=True)
        payload = {'method': method, 'context': context, 'input': input}
        input_hash = digest(canonical(payload))
        lock = int.from_bytes(hashlib.sha256((context['tenantId'] + ':' + context['operationId']).encode()).digest()[:8], 'big', signed=True)
        self.env.cr.execute('SELECT pg_advisory_xact_lock(%s)', [lock])
        ops = self.env['poc.operation'].sudo()
        existing = ops.search([('tenant_key', '=', context['tenantId']), ('operation_key', '=', context['operationId'])], limit=1)
        if existing:
            if existing.input_hash != input_hash:
                raise ValidationError('operation_conflict: operation ID reused with different input')
            return existing.result
        result = callback()
        ops.create({'tenant_key': context['tenantId'], 'operation_key': context['operationId'], 'input_hash': input_hash, 'result': result})
        return result

    def _new_version(self, context, vals):
        return self.env['poc.version'].sudo().create(dict(tenant_key=context['tenantId'], document_key=context['documentId'], project_key=context['projectId'], local_document_key=context.get('localDocumentId'), **vals))

    def _dispatch(self, method, context, input):
        if method == 'template':
            # Public template metadata only; no snapshot or private document data.
            t = self.env['poc.template'].sudo().search([('key', '=', input['id']), ('version', '=', input['version'])], limit=1)
            if not t:
                raise ValidationError('template_not_found')
            t._verify()
            return {'id': t.key, 'version': t.version}
        self._member(context)
        if method == 'upload':
            def upload():
                raw = base64.b64decode(input['contentBase64'], validate=True)
                if len(raw) > 10 * 1024 * 1024 or not raw:
                    raise ValidationError('invalid_upload_size')
                file = self._file(str(uuid.uuid4()) + '-' + input['filename'].split('/')[-1], raw)
                return self._new_version(context, {'unsigned_file_id': file.id, 'unsigned_hash': digest(raw), 'content_type': input['contentType']})._descriptor()
            return self._op(method, context, input, upload)
        if method == 'generate':
            def generate():
                snapshot = input['snapshot']
                if not isinstance(snapshot, dict) or snapshot.get('currency') != 'CAD' or snapshot.get('synthetic') is not True:
                    raise ValidationError('synthetic_CAD_snapshot_required')
                for key in ('customer', 'supplier', 'description', 'quantity', 'totalCents', 'terms'):
                    if key not in snapshot:
                        raise ValidationError('snapshot_field_missing: ' + key)
                t = self.env['poc.template'].sudo().search([('key', '=', input['templateId']), ('version', '=', input['templateVersion'])], limit=1)
                if not t:
                    raise ValidationError('template_not_found')
                t._verify()
                raw = canonical(snapshot)
                snapshot_file = self._file('snapshot-' + str(uuid.uuid4()) + '.json', raw)
                v = self._new_version(context, {'snapshot': snapshot, 'snapshot_hash': digest(raw), 'snapshot_file_id': snapshot_file.id, 'template_id': t.id, 'template_key': t.key, 'template_version': t.version})
                pdf, _ = t.report_id._render_qweb_pdf(t.report_id.id, res_ids=v.ids)
                file = self._file('unsigned-' + v.version_key + '.pdf', pdf)
                # Bypass immutable write internally, never via caller context.
                models.Model.write(v, {'unsigned_file_id': file.id, 'unsigned_hash': digest(pdf)})
                return v._descriptor()
            return self._op(method, context, input, generate)
        if method == 'versions':
            vs = self.env['poc.version'].sudo().search([('tenant_key', '=', context['tenantId']), ('document_key', '=', context['documentId']), ('project_key', '=', context['projectId'])], order='id')
            for v in vs:
                v._verify()
            return [v._descriptor() for v in vs]
        if method == 'signRequest':
            def sign_request():
                v = self._version(context, input['versionId'])
                if v.content_type != 'application/pdf':
                    raise ValidationError('PDF_required')
                existing = self.env['poc.envelope'].sudo().search([('version_id', '=', v.id)], limit=1)
                if existing:
                    raise ValidationError('version_already_has_envelope')
                signers = input['signers']
                if len(signers) != 2 or len({s['email'].lower() for s in signers}) != 2:
                    raise ValidationError('two_distinct_synthetic_signers_required')
                signer_vals = []
                items = {}
                field = self.env.ref('sign_oca.sign_field_signature')
                for n, s in enumerate(signers, 1):
                    if not s['email'].endswith('@example.test'):
                        raise ValidationError('synthetic_email_required')
                    partner = self.env['res.partner'].sudo().search([('email', '=', s['email'])], limit=1)
                    if not partner or partner.name != s['name'] or not partner.user_ids:
                        raise ValidationError('preverified_local_fixture_account_required')
                    role = self.env['sign.oca.role'].sudo().create({'name': 'Synthetic signer ' + str(n) + ' ' + v.version_key})
                    signer_vals.append((0, 0, {'partner_id': partner.id, 'role_id': role.id}))
                    items[str(n)] = {'id': n, 'field_id': field.id, 'field_type': 'signature', 'required': True, 'name': 'Signature ' + str(n), 'role_id': role.id, 'page': 1, 'position_x': 20, 'position_y': 55 + (n - 1) * 16, 'width': 38, 'height': 9, 'value': False, 'default_value': False, 'placeholder': '', 'tabindex': n}
                req = self.env['sign.oca.request'].sudo().create({'name': 'SYNTHETIC CAD ' + context['documentId'], 'data': v.unsigned_file_id.content, 'filename': 'synthetic-contract.pdf', 'signatory_data': items, 'signer_ids': signer_vals, 'record_ref': 'poc.version,' + str(v.id)})
                env = self.env['poc.envelope'].sudo().create({'version_id': v.id, 'request_id': req.id, 'expected_hash': v.unsigned_hash, 'expected_items_hash': digest(canonical(items)), 'signer_binding_hash': 'pending'})
                env._set({'signer_binding_hash': digest(canonical(env._binding()))})
                req.action_send()
                env._set({'active_state_hash': digest(canonical(env._state()))})
                return {'requestId': str(req.id), 'versionId': v.version_key}
            return self._op(method, context, input, sign_request)
        if method in ('update', 'artifacts', 'image'):
            v = self._version(context, input['versionId'])
            envelope = self.env['poc.envelope'].sudo().search([('version_id', '=', v.id)], limit=1)
            if method == 'update':
                if not envelope or str(envelope.request_id.id) != input['requestId']:
                    raise ValidationError('request_association_mismatch')
                return {'status': envelope._complete()}
            if method == 'image':
                if v.content_type not in ('image/png', 'image/jpeg', 'image/webp') or v.local_document_key != context.get('localDocumentId'):
                    raise ValidationError('image_association_mismatch')
                return dict(v._descriptor(), actorId=context['actorId'], localDocumentId=v.local_document_key, contentType=v.content_type, contentBase64=base64.b64encode(decoded(v.unsigned_file_id)).decode())
            if envelope:
                envelope._verify()
            result = [dict(v._descriptor(), kind='document', url='/poc/artifact/' + v.version_key + '/document')]
            if envelope and envelope.evidence_file_id:
                result += [dict(v._descriptor(), kind=kind, url='/poc/artifact/' + v.version_key + '/' + kind) for kind in ('signed_document', 'evidence')]
            return result
        raise ValidationError('unknown_document_service_method')
