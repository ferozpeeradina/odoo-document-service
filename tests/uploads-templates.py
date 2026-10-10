import base64,copy,importlib.util,json,sys
s=importlib.util.spec_from_file_location('t','tests/http_service.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
try:
    for key in ('purchase_order','packing_list','invoice','ledger_statement'):
        snapshot=copy.deepcopy(t.SNAP)
        if key=='ledger_statement':snapshot=dict(synthetic=True,organisation=dict(name='Synthetic organisation'),invoices=[dict(id='invoice-1',totalCents=125000,currency='CAD',date='2026-10-10')],receipts=[],allocations=[],adjustments=[])
        else:snapshot['source']['kind']=key
        c=dict(t.CTX,documentId='template-'+key,operationId='generate-'+key)
        r=t.call('/v1/documents',dict(context=c,input=dict(templateId=key,templateVersion='1',snapshot=snapshot)))
        t.check('QWeb renders '+key,r.status_code==200)
        v=r.json()['versionId'];r=t.call('/v1/documents/'+c['documentId']+'/versions/'+v+'/download/document?tenantId=synthetic-a')
        t.check('PDF bytes '+key,r.status_code==200 and r.content.startswith(b'%PDF'))
    # Stable PNG supplied by the test, validated by Pillow in Odoo.
    png='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC'
    c=dict(t.CTX,documentId='image-test',operationId='image-upload',actorId='synthetic-actor',localDocumentId='local-image')
    inp=dict(filename='synthetic.png',contentType='image/png',contentBase64=png)
    r=t.call('/v1/uploads',dict(context=c,input=inp));t.check('validated image upload',r.status_code==200)
    version=r.json()['versionId'];t.check('image upload replay identical',t.call('/v1/uploads',dict(context=c,input=inp)).json()==r.json())
    path='/v1/documents/image-test/versions/'+version+'/image?tenantId=synthetic-a&localDocumentId=local-image&actorId='
    r=t.call(path+'synthetic-actor');t.check('image exact actor and local association',r.status_code==200 and r.json()['contentBase64']==png)
    t.check('wrong image actor denied',t.call(path+'unrelated-actor').status_code==403)
    t.check('wrong image local record denied',t.call(path.replace('local-image','other')+'synthetic-actor').status_code==403)
    t.check('nonimage bytes rejected',t.call('/v1/uploads',dict(context=dict(c,operationId='bad-image'),input=dict(inp,contentBase64=base64.b64encode(b'not an image').decode()))).status_code==409)
    p=dict(context=dict(t.CTX,documentId='bad-project-snapshot',operationId='bad-project-snapshot'),input=dict(templateId='contract',templateVersion='1',snapshot=dict(t.SNAP,project=dict(id='other'))))
    t.check('snapshot project association enforced',t.call('/v1/documents',p).status_code==403)
    (t.ROOT/'artifacts/uploads-template-tests.json').write_text(json.dumps(dict(result='PASS',checks=t.checks),indent=2))
except Exception as e:
    print('FAIL '+(str(e) if isinstance(e,AssertionError) else type(e).__name__));sys.exit(1)
