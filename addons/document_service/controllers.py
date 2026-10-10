import base64, datetime, hashlib, html, json, os, secrets, pathlib, re
from urllib.parse import quote, urlencode
from psycopg2 import errors as pg_errors
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import consteq
from odoo.addons.packaging_bridge.models.provider import decoded, digest

def answer(value,status=200): return request.make_json_response(value,status=status,headers=[('Cache-Control','no-store')])
def credential():
    from .models import fixture
    fixture()
    auth=request.httprequest.headers.get('Authorization','')
    if not auth.startswith('Bearer ') or len(auth)>300: raise AccessError('credential_required')
    c=request.env['document.credential'].sudo().search([('token_hash','=',digest(auth[7:].encode())),('active','=',True)],limit=1)
    if not c: raise AccessError('credential_invalid')
    request.update_env(user=c.user_id.id)
    return c

def body():
    data=request.httprequest.get_json(silent=True)
    if not isinstance(data,dict): raise ValidationError('invalid_input')
    return data

def context(c,data,document=None,version=None):
    ctx=dict(data.get('context',data))
    if document: ctx['documentId']=document
    ctx.setdefault('operationId','read')
    if version:
        v=request.env['poc.version'].sudo().search([('version_key','=',version),('tenant_key','=',c.tenant),('document_key','=',ctx.get('documentId'))],limit=1)
        if not v: raise AccessError('association_denied')
        ctx.setdefault('projectId',v.project_key or None)
    if 'projectId' not in ctx and document:
        vs=request.env['poc.version'].sudo().search([('tenant_key','=',c.tenant),('document_key','=',document)])
        projects=set(vs.mapped('project_key'))
        if len(projects)==1: ctx['projectId']=next(iter(projects)) or None
    if ctx.get('tenantId')!=c.tenant or (not c.tenant_wide and ctx.get('projectId') not in c.projects): raise AccessError('scope_denied')
    return {k:ctx[k] for k in ('tenantId','documentId','projectId','operationId','localDocumentId','actorId') if k in ctx}

class REST(http.Controller):
    @http.route(['/v1/uploads','/v1/documents','/v1/signature-requests','/v1/signature-requests/<string:request_id>/status','/v1/templates/<string:template_id>/versions/<string:template_version>','/v1/documents/<string:document_id>/versions','/v1/documents/<string:document_id>/versions/<string:version_id>/artifacts','/v1/documents/<string:document_id>/versions/<string:version_id>/image','/v1/documents/<string:document_id>/versions/<string:version_id>/download/<string:kind>'],type='http',auth='public',csrf=False,methods=['GET','POST'],save_session=False)
    def api(self,request_id=None,template_id=None,template_version=None,document_id=None,version_id=None,kind=None,**kw):
        try:
            c=credential(); path=request.httprequest.path; verb=request.httprequest.method
            data=body() if verb=='POST' else dict(request.httprequest.args)
            inp=data.get('input',data); provider=request.env['poc.provider']
            if template_id:
                if verb!='GET': raise ValidationError('method_not_allowed')
                return answer(provider._dispatch('template',{},dict(id=template_id,version=template_version)))
            if verb=='POST':
                method='upload' if path=='/v1/uploads' else 'generate' if path=='/v1/documents' else 'update' if request_id else 'signRequest'
                ctx=context(c,data,version=inp.get('versionId'))
                if request_id: inp=dict(inp,requestId=request_id)
            else:
                ctx=context(c,data,document_id,version_id)
                method='image' if path.endswith('/image') else 'artifacts' if version_id else 'versions'; inp={'versionId':version_id}
            with request.env.cr.savepoint():
                if kind:
                    if verb!='GET': raise ValidationError('method_not_allowed')
                    provider._member(ctx); v=provider._version(ctx,version_id)
                    e=request.env['poc.envelope'].sudo().search([('version_id','=',v.id)],limit=1)
                    if e: e._verify()
                    if kind=='document': f=v.unsigned_file_id; mime=v.content_type
                    elif kind in ('signed_document','evidence') and e and e.evidence_file_id:
                        f=e.signed_file_id if kind=='signed_document' else e.evidence_file_id; mime='application/pdf' if kind=='signed_document' else 'application/json'
                    else: return answer({'error':'artifact_unavailable'},404)
                    return request.make_response(decoded(f),headers=[('Content-Type',mime),('Cache-Control','no-store'),('Content-Disposition','attachment; filename="'+kind+('.json"' if kind=='evidence' else '.pdf"'))])
                result=provider._dispatch(method,ctx,inp)
                if method=='artifacts':
                    for a in result:
                        a['url']=os.environ['PUBLIC_ORIGIN']+'/v1/documents/'+quote(a['documentId'],safe='')+'/versions/'+quote(a['versionId'],safe='')+'/download/'+a['kind']+'?'+urlencode({'tenantId':a['tenantId']})
            return answer(result)
        except (pg_errors.SerializationFailure, pg_errors.DeadlockDetected): raise
        except pg_errors.UniqueViolation:
            request.env.cr.execute("DO $$ BEGIN RAISE EXCEPTION 'document_operation_retry' USING ERRCODE = '40001'; END $$")
        except AccessError: return answer({'error':'access_denied'},403)
        except ValidationError as e:
            code=str(e).split(':')[0]
            return answer({'error':code if re.fullmatch('[a-z_]+',code) else 'validation_failed'},409)
        except (ValueError,KeyError,TypeError): return answer({'error':'invalid_input'},400)
        except Exception: return answer({'error':'service_failure'},503)

def otp_hash(code):
    salt=secrets.token_hex(16)
    return salt+'$'+hashlib.pbkdf2_hmac('sha256',code.encode(),bytes.fromhex(salt),200000).hex()
def otp_verify(code,stored):
    salt,value=stored.split('$')
    return consteq(value,hashlib.pbkdf2_hmac('sha256',code.encode(),bytes.fromhex(salt),200000).hex())

class Recipient(http.Controller):
    @http.route('/recipient/<int:request_id>',type='http',auth='public',methods=['GET'])
    def landing(self,request_id,**kw):
        # Request locator conveys no recipient information or authentication.
        return request.make_response('<!doctype html><title>Verify your mailbox</title><h1>Verify your mailbox</h1><form method="post" action="/recipient/'+str(request_id)+'/otp"><input name="email" type="email" required><button>Email verification code</button></form>',headers=[('Cache-Control','no-store')])
    @http.route('/recipient/<int:request_id>/otp',type='http',auth='public',csrf=False,methods=['POST'])
    def otp(self,request_id,**kw):
        try:
            from .models import fixture
            fixture()
            data=request.httprequest.get_json(silent=True) or request.httprequest.form
            email=str(data.get('email','')).strip().lower()
            request.env.cr.execute('SELECT pg_advisory_xact_lock(%s)',[request_id])
            e=request.env['poc.envelope'].sudo().search([('request_id','=',request_id)],limit=1)
            s=e.request_id.signer_ids.filtered(lambda s:s.partner_id.email.lower()==email) if e else None
            if s and not s.signed_on:
                e._verify(); now=fields.Datetime.now(); challenges=request.env['document.challenge'].sudo()
                recent=challenges.search_count([('signer_id','=',s.id),('create_date','>',now-datetime.timedelta(minutes=15))])
                if recent>=3: return answer({'error':'rate_limited'},429)
                code=str(secrets.randbelow(1000000)).zfill(6)
                c=challenges.create(dict(signer_id=s.id,version_id=e.version_id.id,code_hash=otp_hash(code),recipient_email=s.partner_id.email,recipient_name=s.partner_id.name,expires=now+datetime.timedelta(minutes=5)))
                request.env['document.outbox']._queue('otp:'+str(c.id),email,'Document mailbox verification','Verification code: '+code+'\nExpires in five minutes. Request '+str(request_id))
            return request.make_response('<form method="post" action="/recipient/'+str(request_id)+'/verify"><input name="email" type="email" value="'+html.escape(email,quote=True)+'" required><input name="code" autocomplete="one-time-code" required><button>Verify and sign</button></form>',headers=[('Cache-Control','no-store')])
        except Exception: return answer({'error':'verification_unavailable'},409)
    @http.route('/recipient/<int:request_id>/verify',type='http',auth='public',csrf=False,methods=['POST'])
    def verify(self,request_id,**kw):
        from .models import fixture
        try: fixture()
        except AccessError: return answer({'error':'service_mode_not_accepted'},403)
        data=request.httprequest.get_json(silent=True) or request.httprequest.form
        email=str(data.get('email','')).strip().lower(); code=str(data.get('code',''))
        request.env.cr.execute('SELECT pg_advisory_xact_lock(%s)',[request_id])
        e=request.env['poc.envelope'].sudo().search([('request_id','=',request_id)],limit=1)
        s=e.request_id.signer_ids.filtered(lambda s:s.partner_id.email.lower()==email) if e else None
        if not s: return answer({'error':'verification_failed'},403)
        c=request.env['document.challenge'].sudo().search([('signer_id','=',s.id),('version_id','=',e.version_id.id)],order='id desc',limit=1)
        if not c or c.recipient_email!=email or c.recipient_name!=s.partner_id.name or c.used or c.attempts>=5 or c.expires<fields.Datetime.now(): return answer({'error':'verification_failed'},403)
        c.write({'attempts':c.attempts+1})
        if not otp_verify(code,c.code_hash): return answer({'error':'verification_failed'},403)
        e._verify(); now=fields.Datetime.now(); c.write(dict(used=True,verified_at=now))
        user=s.partner_id.user_ids.filtered('share')[:1]
        if not user: return answer({'error':'verification_failed'},403)
        request.session.logout(keep_db=True)
        request.session['pre_uid']=user.id; request.session['pre_login']=user.login
        request.session.finalize(request.env)
        request.session['document_grant']=dict(signer=s.id,version=e.version_id.id,challenge=c.id,expires=(now+datetime.timedelta(minutes=20)).timestamp())
        request.update_env(user=user.id)
        return request.redirect('/sign_oca/document/'+str(s.id)+'/'+s.access_token,code=303)

class MailQueue(http.Controller):
    @http.route('/internal/mail/<string:action>',type='http',auth='public',csrf=False,methods=['POST'],save_session=False)
    def mail(self,action):
        try:
            auth=request.httprequest.headers.get('Authorization','')
            if not consteq(auth,'Bearer '+pathlib.Path('/run/config/worker.token').read_text().strip()): raise AccessError('worker_denied')
            data=body(); box=request.env['document.outbox'].sudo(); now=fields.Datetime.now()
            if action=='claim':
                request.env.cr.execute("SELECT id FROM document_outbox WHERE state IN ('pending','leased') AND attempts<5 AND next_at<=%s ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1",[now])
                row=request.env.cr.fetchone()
                if not row: return answer({})
                m=box.browse(row[0])
                if m.kind=='callback': m.envelope_id._verify()
                lease=secrets.token_hex(20); m.write(dict(state='leased',lease=lease,attempts=m.attempts+1,next_at=now+datetime.timedelta(seconds=60)))
                return answer(dict(id=m.id,operation=m.operation,recipient=m.recipient,subject=m.subject,body=m.body,lease=lease,kind=m.kind))
            m=box.browse(int(data['id'])).exists()
            if not m or m.state!='leased' or not consteq(m.lease,data['lease']): raise AccessError('lease_denied')
            if data.get('sent'): m.write(dict(state='sent',body=False,lease=False))
            else: m.write(dict(state='failed' if m.attempts>=5 else 'pending',lease=False,next_at=now+datetime.timedelta(seconds=min(300,2**m.attempts))))
            return answer({'ok':True})
        except Exception: return answer({'error':'mail_operation_failed'},403)

from odoo.addons.packaging_sign_guard.controllers.signing import GuardedPortalSign
from .models import verified_grant
class VerifiedPortal(GuardedPortalSign):
    def _recipient(self,signer_id,access_token):
        s=super()._recipient(signer_id,access_token); verified_grant(request.env,s); return s
    @http.route()
    def portal_download_signed(self,request_id,**kw):
        doc=request.env['sign.oca.request'].sudo().browse(request_id).exists()
        s=doc.signer_ids.filtered(lambda s:s.partner_id==request.env.user.partner_id) if doc else None
        member=request.env['poc.member'].sudo().search([('user_id','=',request.env.uid),('can_issue','=',True)],limit=1)
        if not member:
            try:
                if not s: raise AccessError('grant_required')
                verified_grant(request.env,s[:1])
            except AccessError: return answer({'error':'access_denied'},403)
        return super().portal_download_signed(request_id,**kw)
