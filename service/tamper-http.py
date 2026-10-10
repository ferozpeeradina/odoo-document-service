# Synthetic committed corruption with guaranteed restore, actual authenticated HTTP.
import base64,json,os,pathlib,requests
from odoo.addons.packaging_bridge.models.provider import canonical,digest,decoded
if os.environ.get('DOCUMENT_SERVICE_MODE')!='test':raise ValueError('TEST only')
e=env['poc.envelope'].search([('evidence_file_id','!=',False)],order='id desc',limit=1);v=e.version_id
url='http://ingress:8069/v1/documents/'+v.document_key+'/versions/'+v.version_key+'/download/signed_document?tenantId='+v.tenant_key
headers={'Authorization':'Bearer '+pathlib.Path('/run/config/service.token').read_text().strip()}
def status():return requests.get(url,headers=headers,timeout=60).status_code
assert status()==200
checks=[]
def test(label,corrupt,restore):
    try:
        corrupt();env.cr.commit();env.invalidate_all()
        assert status()==409,label
        checks.append(label)
    finally:
        restore();env.cr.commit();env.invalidate_all()
        assert status()==200,'baseline restore'
original_snapshot=v.snapshot; original_snapshot_hash=v.snapshot_hash; original_snapshot_file=v.snapshot_file_id.content
changed=dict(original_snapshot,corruption=True)
def snap_change():env.cr.execute('UPDATE poc_version SET snapshot=%s WHERE id=%s',[json.dumps(changed),v.id])
def snap_restore():env.cr.execute('UPDATE poc_version SET snapshot=%s,snapshot_hash=%s WHERE id=%s',[json.dumps(original_snapshot),original_snapshot_hash,v.id]);v.snapshot_file_id.write({'content':original_snapshot_file})
test('HTTP rejects saved snapshot mutation',snap_change,snap_restore)
unsigned=v.unsigned_file_id.content
test('HTTP rejects unsigned PDF mutation',lambda:v.unsigned_file_id.write({'content':base64.b64encode(decoded(v.unsigned_file_id)+b'corrupt')}),lambda:v.unsigned_file_id.write({'content':unsigned}))
arch=v.template_id.arch_file_id.content
test('HTTP rejects frozen template XML mutation',lambda:v.template_id.arch_file_id.write({'content':base64.b64encode(decoded(v.template_id.arch_file_id)+b'corrupt')}),lambda:v.template_id.arch_file_id.write({'content':arch}))
items=e.request_id.signatory_data
def fields_change():e.request_id.write({'signatory_data':dict(items,corrupt={})})
test('HTTP rejects signing field mutation',fields_change,lambda:e.request_id.write({'signatory_data':items}))
active=e.request_id.with_context(bin_size=False).data
test('HTTP rejects active OCA PDF mutation',lambda:e.request_id.write({'data':base64.b64encode(base64.b64decode(active)+b'corrupt')}),lambda:e.request_id.write({'data':active}))
signed=e.signed_file_id.content; signed_hash=e.signed_hash
changed_pdf=decoded(e.signed_file_id)+b'corrupt'
def pdf_change():e.signed_file_id.write({'content':base64.b64encode(changed_pdf)});e._set({'signed_hash':digest(changed_pdf)})
def pdf_restore():e.signed_file_id.write({'content':signed});e._set({'signed_hash':signed_hash})
test('HTTP rejects changed PDF bytes AND database hash anchor using independent seal',pdf_change,pdf_restore)
evidence=e.evidence_file_id.content;evidence_hash=e.evidence_hash
manifest=json.loads(decoded(e.evidence_file_id));manifest['manifest']['requestId']='corrupt';changed_evidence=canonical(manifest)
def evidence_change():e.evidence_file_id.write({'content':base64.b64encode(changed_evidence)});e._set({'evidence_hash':digest(changed_evidence)})
def evidence_restore():e.evidence_file_id.write({'content':evidence});e._set({'evidence_hash':evidence_hash})
test('HTTP rejects changed evidence bytes AND database hash anchor using signed manifest',evidence_change,evidence_restore)
def snap_both():
    snap_change();v.snapshot_file_id.write({'content':base64.b64encode(canonical(changed))});env.cr.execute('UPDATE poc_version SET snapshot_hash=%s WHERE id=%s',[digest(canonical(changed)),v.id])
test('HTTP rejects changed snapshot bytes AND anchors using signed manifest',snap_both,snap_restore)
state=e.request_id.signer_ids[0];signed_on=state.signed_on
test('HTTP rejects signer completion mutation',lambda:state.write({'signed_on':False}),lambda:state.write({'signed_on':signed_on}))
print('SAFE_RESULT '+json.dumps(dict(result='PASS',checks=checks)))
