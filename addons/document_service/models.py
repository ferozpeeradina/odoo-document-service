import base64, datetime, hashlib, json, os, secrets, pathlib
import requests
from odoo import fields, models, Command
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.packaging_bridge.models.provider import canonical, digest, decoded

def fixture():
    mode=os.environ.get('DOCUMENT_SERVICE_MODE')
    if mode=='test': return True
    if mode=='production' and os.environ.get('PRODUCTION_ACCEPTED')=='yes': return False
    raise AccessError('service_mode_not_accepted')
def seal_call(path,payload):
    try:
        r=requests.post('http://sealer:8080/'+path,json=payload,headers={'Authorization':'Bearer '+pathlib.Path('/run/config/seal.token').read_text().strip()},timeout=45)
        if r.status_code!=200: raise ValueError()
        return r.json()
    except Exception as e: raise ValidationError('integrity_failed: independent seal unavailable or invalid') from e

class Credential(models.Model):
    _name='document.credential'
    _description='Individually scoped service credential hash'
    token_hash=fields.Char(required=True)
    user_id=fields.Many2one('res.users',required=True)
    tenant=fields.Char(required=True)
    projects=fields.Json(required=True)
    tenant_wide=fields.Boolean(default=False)
    active=fields.Boolean(default=True)
    _unique_token=models.Constraint('UNIQUE(token_hash)','Credential exists')

class Challenge(models.Model):
    _name='document.challenge'
    _description='Request and recipient mailbox challenge'
    signer_id=fields.Many2one('sign.oca.request.signer',required=True)
    version_id=fields.Many2one('poc.version',required=True)
    code_hash=fields.Char(required=True)
    recipient_email=fields.Char()
    recipient_name=fields.Char()
    expires=fields.Datetime(required=True)
    attempts=fields.Integer(default=0)
    used=fields.Boolean(default=False)
    verified_at=fields.Datetime()

class Outbox(models.Model):
    _name='document.outbox'
    _description='Small durable mail outbox with bounded lease recovery'
    operation=fields.Char(required=True)
    recipient=fields.Char(required=True)
    subject=fields.Char(required=True)
    body=fields.Text()
    kind=fields.Selection([('mail','Mail'),('callback','Callback')],default='mail')
    envelope_id=fields.Many2one('poc.envelope')
    state=fields.Selection([('pending','Pending'),('leased','Leased'),('sent','Sent'),('failed','Failed')],default='pending')
    attempts=fields.Integer(default=0)
    lease=fields.Char()
    next_at=fields.Datetime(default=fields.Datetime.now)
    _unique_op=models.Constraint('UNIQUE(operation)','Mail operation exists')
    def _queue(self,operation,recipient,subject,body):
        if not self.sudo().search([('operation','=',operation)]):
            self.sudo().create(dict(operation=operation,recipient=recipient,subject=subject,body=body))

class Version(models.Model):
    _inherit='poc.version'
    actor_key=fields.Char()
    project_key=fields.Char(required=False)
    def _presentation(self):
        from .presentation import presentation
        return presentation(self.snapshot,self.template_key)
    def _descriptor(self): return dict(super()._descriptor(),projectId=self.project_key or None,fixture=fixture())

class Template(models.Model):
    _inherit='poc.template'
    def _register_service(self,key):
        import uuid
        from lxml import etree
        source=self.env.ref('document_service.'+key)
        tree=etree.fromstring(source.arch_db.encode()); view_key='document_service.frozen_'+uuid.uuid4().hex; tree.set('t-name',view_key)
        arch=etree.tostring(tree,encoding='unicode')
        view=self.env['ir.ui.view'].create(dict(name=view_key,type='qweb',key=view_key,arch_db=arch))
        report=self.env['ir.actions.report'].create(dict(name=key,model='poc.version',report_type='qweb-pdf',report_name=view_key))
        f=self.env['poc.provider']._file('template-'+key+'-1.xml',arch.encode())
        return self.create(dict(key=key,version='1',view_id=view.id,report_id=report.id,arch_file_id=f.id,arch_hash=digest(arch.encode())))

class Envelope(models.Model):
    _inherit='poc.envelope'
    local_request_key=fields.Char()
    def _binding(self):
        return [dict(item,email=s.partner_id.email,name=s.partner_id.name) for item,s in zip(super()._binding(),self.request_id.signer_ids.sorted('id'))]
    def _verify(self):
        raw=super()._verify()
        if self.evidence_file_id:
            evidence=json.loads(decoded(self.evidence_file_id))
            seal_call('verify',{'pdf':base64.b64encode(decoded(self.signed_file_id)).decode(),'evidence':evidence})
            m=evidence['manifest']; v=self.version_id
            if m.get('template')!=dict(id=v.template_key,version=v.template_version) or m['association']!=v._descriptor() or m['hashes']['snapshotSha256']!=v.snapshot_hash or m['hashes']['templateSha256']!=v.template_id.arch_hash or m['hashes']['unsignedPdfSha256']!=v.unsigned_hash:
                raise ValidationError('integrity_failed: signed manifest association changed')
        return raw
    def _complete(self):
        self._lock(); raw=self._verify(); signers=self.request_id.signer_ids
        if self.request_id.state!='2_signed' or not all(signers.mapped('signed_on')):
            return 'partial' if any(signers.mapped('signed_on')) else 'pending'
        if not self.evidence_file_id:
            events=[]
            for s in signers.sorted('id'):
                c=self.env['document.challenge'].sudo().search([('signer_id','=',s.id),('version_id','=',self.version_id.id),('used','=',True)],order='verified_at desc',limit=1)
                if not c: raise ValidationError('verified_recipient_required')
                if c.recipient_email!=s.partner_id.email or c.recipient_name!=s.partner_id.name: raise ValidationError('integrity_failed: verified identity changed')
                events.append(dict(signerId=s.id,name=c.recipient_name,email=c.recipient_email,verifiedAtUtc=fields.Datetime.to_string(c.verified_at),signedOnUtc=fields.Datetime.to_string(s.signed_on),engineSignatureSha1=s.signature_hash))
            if self.request_id.current_hash!=hashlib.sha1(raw).hexdigest(): raise ValidationError('integrity_failed: engine final hash')
            v=self.version_id
            logs=self.env['sign.oca.request.log'].sudo().search([('request_id','=',self.request_id.id),('action','=','sign')],order='id')
            manifest=dict(template=dict(id=v.template_key,version=v.template_version),source={k:v.snapshot.get('source',{}).get(k) for k in ('kind','id','revision')},audit=[dict(action=l.action,atUtc=fields.Datetime.to_string(l.date),partnerId=l.partner_id.id,signerId=l.signer_id.id) for l in logs],schema='document-service-evidence/1',fixture=fixture(),association=v._descriptor(),requestId=str(self.request_id.id),frozenAt=fields.Datetime.to_string(fields.Datetime.now()),verifiedRecipients=events,hashes=dict(snapshotSha256=v.snapshot_hash,templateSha256=v.template_id.arch_hash,unsignedPdfSha256=v.unsigned_hash),seal=dict(identity='Service seal distinct from recipients',trust='Self-signed TEST certificate' if fixture() else 'Injected service certificate; trust determined externally',timestamp='No trusted timestamp'))
            result=seal_call('seal',dict(pdf=base64.b64encode(raw).decode(),manifest=manifest))
            pdf=base64.b64decode(result['pdf']); evidence=canonical(result['evidence']); p=self.env['poc.provider']
            signed=p._file('sealed-'+v.version_key+'.pdf',pdf); cert=p._file('evidence-'+v.version_key+'.json',evidence)
            self._set(dict(signed_file_id=signed.id,signed_hash=digest(pdf),evidence_file_id=cert.id,evidence_hash=digest(evidence),final_state_hash=digest(canonical(self._state()))))
        self._verify()
        if self.local_request_key:
            box=self.env['document.outbox'].sudo(); op='completion:'+self.version_id.version_key
            if not box.search([('operation','=',op)]):
                v=self.version_id
                payload=dict(eventId=op,tenantId=v.tenant_key,documentId=v.document_key,versionId=v.version_key,signatureRequestId=self.local_request_key,status='completed')
                box.create(dict(operation=op,kind='callback',envelope_id=self.id,recipient='callback',subject='completion',body=canonical(payload).decode()))
        return 'completed'

class Provider(models.AbstractModel):
    _inherit='poc.provider'
    def _member(self,context,issue=False):
        member=self.env['poc.member'].sudo().search([('user_id','=',self.env.uid)],limit=1)
        if not member or member.tenant_key!=context.get('tenantId') or (issue and not member.can_issue): raise AccessError('tenant_access_denied')
        for key in ('tenantId','documentId','operationId'):
            if not isinstance(context.get(key),str) or not 0<len(context[key])<=128: raise ValidationError('invalid_context')
        project=context.get('projectId')
        if project is not None and (not isinstance(project,str) or not 0<len(project)<=128): raise ValidationError('invalid_project')
        return member
    def _new_version(self,context,vals):
        return super()._new_version(dict(context,projectId=context.get('projectId')),dict(vals,actor_key=context.get('actorId')))
    def _version(self,context,version_key):
        v=super()._version(context,version_key)
        if context.get('localDocumentId') and context['localDocumentId']!=v.local_document_key: raise AccessError('local_document_association_denied')
        return v
    def _dispatch(self,method,context,input):
        fixture(); context=dict(context,projectId=context.get('projectId'))
        if method=='versions':
            self._member(context)
            vs=self.env['poc.version'].sudo().search([('tenant_key','=',context['tenantId']),('document_key','=',context['documentId']),('project_key','=',context.get('projectId') or False)],order='id')
            for v in vs: v._verify()
            return [v._descriptor() for v in vs]
        if method=='image':
            v=self._version(context,input['versionId'])
            if not v.actor_key or v.actor_key!=context.get('actorId'): raise AccessError('image_actor_association_denied')
        if method=='upload':
            import io
            from PIL import Image
            raw=base64.b64decode(input['contentBase64'],validate=True)
            mime=input['contentType']
            if mime=='application/pdf':
                if not raw.startswith(b'%PDF-'): raise ValidationError('invalid_pdf')
            elif mime in ('image/png','image/jpeg','image/webp'):
                if not context.get('actorId') or not context.get('localDocumentId'): raise ValidationError('image_context_required')
                try:
                    image=Image.open(io.BytesIO(raw)); expected={'image/png':'PNG','image/jpeg':'JPEG','image/webp':'WEBP'}[mime]
                    if image.format!=expected: raise ValueError()
                    image.verify()
                except Exception as e: raise ValidationError('invalid_image') from e
            else: raise ValidationError('unsupported_content_type')
        if method=='generate' and input.get('templateId') in ('purchase_order','packing_list','invoice','ledger_statement','contract'):
            def generate():
                snap=input['snapshot']; key=input['templateId']
                if not isinstance(snap,dict): raise ValidationError('snapshot_required')
                if key=='ledger_statement':
                    if not all(k in snap for k in ('organisation','invoices','receipts','allocations','adjustments')): raise ValidationError('prerequisite_missing: saved ledger records')
                else:
                    src=snap.get('source',{})
                    if not all(k in src for k in ('kind','id','revision','data')): raise ValidationError('prerequisite_missing: saved source')
                    project=snap.get('project') or {}
                    if project and project.get('id')!=context.get('projectId'): raise AccessError('snapshot_project_mismatch')
                    if snap.get('tenantId',context['tenantId'])!=context['tenantId']: raise AccessError('snapshot_tenant_mismatch')
                    data=src['data']; parties=snap.get('parties',{})
                    required=['business','factory'] if key=='purchase_order' else ['business','customer']
                    if not all(isinstance(parties.get(k),dict) and parties[k].get('name') for k in required): raise ValidationError('prerequisite_missing: saved normalized parties')
                    if key in ('purchase_order','packing_list','invoice') and not data.get('lines'): raise ValidationError('prerequisite_missing: saved lines')
                    if key in ('purchase_order','invoice') and 'totalCents' not in data: raise ValidationError('prerequisite_missing: saved total')
                    if key=='contract' and not (src['kind']=='orders' and data.get('status')=='approved' and data.get('approvedBy') and data.get('approvedAt') and isinstance(data.get('terms'),str) and data.get('terms').strip()): raise ValidationError('prerequisite_missing: approved order terms')
                t=self.env['poc.template'].sudo().search([('key','=',key),('version','=',input['templateVersion'])],limit=1)
                if not t: raise ValidationError('template_not_found')
                t._verify(); raw=canonical(snap); f=self._file('snapshot-'+secrets.token_hex(16)+'.json',raw)
                v=self._new_version(context,dict(snapshot=snap,snapshot_hash=digest(raw),snapshot_file_id=f.id,template_id=t.id,template_key=t.key,template_version=t.version))
                pdf,_=t.report_id._render_qweb_pdf(t.report_id.id,res_ids=v.ids); file=self._file('unsigned-'+v.version_key+'.pdf',pdf)
                models.Model.write(v,dict(unsigned_file_id=file.id,unsigned_hash=digest(pdf)))
                return v._descriptor()
            return self._op(method,context,input,generate)
        if method=='signRequest':
            # Serialize both the version and operation; different operation IDs cannot race.
            self._member(context,issue=True)
            self.env.cr.execute('SELECT pg_advisory_xact_lock(%s)',[int.from_bytes(hashlib.sha256(input['versionId'].encode()).digest()[:8],'big',signed=True)])
            for s in input['signers']:
                email=s['email'].strip().lower()
                if fixture() and not email.endswith('@example.test'): raise ValidationError('test_recipient_required')
                if '@' not in email or len(email)>254: raise ValidationError('invalid_recipient')
                partner=self.env['res.partner'].sudo().search([('email','=',email)],limit=1)
                if not partner:
                    user=self.env['res.users'].sudo().with_context(no_reset_password=True).create(dict(name=s['name'],login='recipient-'+secrets.token_hex(16),email=email,password=secrets.token_urlsafe(40),group_ids=[Command.set([self.env.ref('base.group_portal').id])]))
                    partner=user.partner_id
                if partner.name!=s['name'] or not partner.user_ids or not all(u.share for u in partner.user_ids): raise ValidationError('recipient_principal_conflict')
            # Existing POC validation is reused with a narrowly substituted generic implementation below.
            return self._sign_request(context,input)
        return super()._dispatch(method,context,input)
    def _sign_request(self,context,input):
        def create():
            v=self._version(context,input['versionId'])
            if v.content_type!='application/pdf' or not v.template_id: raise ValidationError('generated_pdf_required')
            if self.env['poc.envelope'].sudo().search([('version_id','=',v.id)]): raise ValidationError('version_already_has_envelope')
            signers=input['signers']
            if not 1<=len(signers)<=2 or len({s['email'].lower() for s in signers})!=len(signers): raise ValidationError('distinct_recipients_required')
            vals=[]; items={}; field=self.env.ref('sign_oca.sign_field_signature')
            for n,s in enumerate(signers,1):
                partner=self.env['res.partner'].sudo().search([('email','=',s['email'].lower())],limit=1)
                role=self.env['sign.oca.role'].sudo().create({'name':'Recipient '+str(n)+' '+v.version_key})
                vals.append(Command.create(dict(partner_id=partner.id,role_id=role.id)))
                items[str(n)]=dict(id=n,field_id=field.id,field_type='signature',required=True,name='Signature '+str(n),role_id=role.id,page=1,position_x=20,position_y=55+(n-1)*16,width=38,height=9,value=False,default_value=False,placeholder='',tabindex=n)
            req=self.env['sign.oca.request'].sudo().create(dict(name=context['documentId'],data=v.unsigned_file_id.content,filename='document.pdf',signatory_data=items,signer_ids=vals,record_ref='poc.version,'+str(v.id)))
            e=self.env['poc.envelope'].sudo().create(dict(local_request_key=context['operationId'],version_id=v.id,request_id=req.id,expected_hash=v.unsigned_hash,expected_items_hash=digest(canonical(items)),signer_binding_hash='pending'))
            e._set(dict(signer_binding_hash=digest(canonical(e._binding())))); req.action_send(); e._set(dict(active_state_hash=digest(canonical(e._state()))))
            for s in req.signer_ids:
                self.env['document.outbox']._queue('invite:'+str(s.id),s.partner_id.email,'Document invitation',os.environ['PUBLIC_ORIGIN']+'/recipient/'+str(req.id))
            return dict(requestId=str(req.id),versionId=v.version_key)
        return self._op('signRequest',context,input,create)

def verified_grant(env,signer):
    fixture()
    from odoo.http import request
    try:
        grant=request.session.get('document_grant') or {}
        e=env['poc.envelope'].sudo().search([('request_id','=',signer.request_id.id)],limit=1)
        if not e: raise AccessError('unmanaged_request_denied')
        c=env['document.challenge'].sudo().browse(grant.get('challenge',0)).exists()
        if grant.get('signer')!=signer.id or grant.get('version')!=e.version_id.id or grant.get('expires',0)<fields.Datetime.now().timestamp() or not c or not c.used or c.signer_id!=signer or c.version_id!=e.version_id or c.recipient_email!=signer.partner_id.email or c.recipient_name!=signer.partner_id.name:
            raise AccessError('verified_grant_required')
    except (RuntimeError,AttributeError): raise AccessError('verified_grant_required')

class Signer(models.Model):
    _inherit='sign.oca.request.signer'
    def action_sign(self,*args,**kwargs):
        self.ensure_one(); verified_grant(self.env,self)
        result=super().action_sign(*args,**kwargs)
        envelope=self.env['poc.envelope'].sudo().search([('request_id','=',self.request_id.id)],limit=1)
        if envelope and self.request_id.state=='2_signed': envelope._complete()
        return result

class Binary(models.AbstractModel):
    _inherit='ir.binary'
    def _find_record(self,*args,**kwargs):
        record=super()._find_record(*args,**kwargs)
        doc=None
        if record._name=='sign.oca.request': doc=record.sudo()
        elif record._name=='sign.oca.request.signer': doc=record.sudo().request_id
        elif record._name=='ir.attachment' and record.sudo().res_model=='sign.oca.request': doc=self.env['sign.oca.request'].sudo().browse(record.sudo().res_id)
        if doc:
            member=self.env['poc.member'].sudo().search([('user_id','=',self.env.uid),('can_issue','=',True)],limit=1)
            if not member:
                s=doc.signer_ids.filtered(lambda s:s.partner_id==self.env.user.partner_id)
                if not s: raise AccessError('verified_grant_required')
                verified_grant(self.env,s[:1])
        return record
