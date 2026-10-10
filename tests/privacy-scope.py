import copy,importlib.util,json,os,subprocess,sys
s=importlib.util.spec_from_file_location('t','tests/http_service.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
head={'Authorization':'Bearer '+(t.ROOT/'service-runtime/tenant-wide.token').read_text().strip()}
checks=[]
def check(name,ok):
    if not ok:raise AssertionError(name)
    checks.append(name);print('PASS '+name)
try:
    for key in ('purchase_order','packing_list','invoice','ledger_statement','contract'):
        d=dict(status='approved',approvedBy='owner',approvedAt='2026-10-10',date='2026-10-10',number='SAVED-123',currency='CAD',totalCents=125000,terms='Owner approved saved terms.',lines=[dict(description='Saved useful cartons',quantity=100,unitPriceCents=1250,totalCents=125000,factoryCost='PRIVATE_COST_MARKER',internalNotes='PRIVATE_LINE_MARKER')],internalNotes='PRIVATE_NOTES_MARKER',factoryId='PRIVATE_ID_MARKER',margin='PRIVATE_MARGIN_MARKER',supplier='PRIVATE_SUPPLIER_MARKER',taxConfigurationFixture=True)
        parties=dict(business=dict(name='Saved Business',email='business@example.test',id='PRIVATE_PARTY_ID_MARKER'),customer=dict(name='Saved Customer'),factory=dict(name='PRIVATE_FACTORY_NAME_MARKER'))
        snap=dict(source=dict(kind='orders',id='order-saved',revision=3,data=d),project=dict(id='future-project',data=dict(demonstration=True,notes='PRIVATE_PROJECT_MARKER')),parties=parties,demonstration=True)
        ctx=dict(tenantId='synthetic-wide',documentId='privacy-flags-'+key,operationId='privacy-flags-'+key,projectId='future-project')
        if key=='ledger_statement':
            snap=dict(organisation=dict(id='organisation-1',data=dict(name='Saved Customer',notes='PRIVATE_ORG_MARKER')),parties=parties,demonstration=True,dateFrom='2026-10-01',dateTo='2026-10-10',openingBalanceCents=0,balanceCents=125000,invoices=[dict(id='invoice-1',data=d)],receipts=[],allocations=[],adjustments=[]);ctx.pop('projectId')
        if key=='packing_list': snap['demonstration']=False;snap['source']['data']['taxConfigurationFixture']=False
        if key=='invoice': snap['demonstration']=False;snap['project']['data']['demonstration']=False
        if key=='contract': snap['demonstration']=False;snap['project']['data']['demonstration']=False;snap['source']['data']['taxConfigurationFixture']=False;snap['source']['data']['evidenceMode']='fixture'
        if key=='ledger_statement': snap['demonstration']=False;snap['evidenceMode']='fixture'
        r=t.call('/v1/documents',dict(context=ctx,input=dict(templateId=key,templateVersion='1',snapshot=snap)),headers=head);check('realistic snapshot accepted '+key,r.status_code==200)
        v=r.json();check('absent ledger project preserved',key!='ledger_statement' or v.get('projectId') is None)
        pdf=t.call('/v1/documents/'+ctx['documentId']+'/versions/'+v['versionId']+'/download/document?tenantId=synthetic-wide',headers=head)
        out=subprocess.run(['pdftotext','-','-'],input=pdf.content,capture_output=True,check=True).stdout.decode()
        check('document type and canonical demonstration label '+key,key.replace('_',' ').title() in out and 'DEMONSTRATION' in out)
        for marker in ('PRIVATE_COST_MARKER','PRIVATE_LINE_MARKER','PRIVATE_NOTES_MARKER','PRIVATE_ID_MARKER','PRIVATE_MARGIN_MARKER','PRIVATE_SUPPLIER_MARKER','PRIVATE_PARTY_ID_MARKER','PRIVATE_PROJECT_MARKER','PRIVATE_ORG_MARKER'):
            check('PDF privacy '+key+' '+marker,marker not in out)
        if key!='purchase_order':check('customer PDF excludes factory '+key,'PRIVATE_FACTORY_NAME_MARKER' not in out)
        if key=='packing_list':check('packing list omits commercial amounts','CAD' not in out and '1250' not in out)
        elif key!='ledger_statement':check('saved amounts and approved terms '+key,'CAD 1250.00' in out)
        if key not in ('ledger_statement',):check('saved line description and quantity '+key,'Saved useful cartons' in out and '100' in out)
        if key=='contract':
            draft=copy.deepcopy(snap);draft['source']['data']['status']='draft'
            check('draft contract rejected',t.call('/v1/documents',dict(context=dict(ctx,operationId='draft-negative'),input=dict(templateId=key,templateVersion='1',snapshot=draft)),headers=head).status_code==409)
            check('approved saved terms rendered','Owner approved saved terms.' in out)
    check('tenant-wide credential cannot claim other tenant',t.call('/v1/documents/other/versions?tenantId=synthetic-a&projectId=future-project',headers=head).status_code==403)
    (t.ROOT/'artifacts/privacy-scope-tests.json').write_text(json.dumps(dict(result='PASS',checks=checks),indent=2))
except Exception as e:
    print('FAIL '+(str(e) if isinstance(e,AssertionError) else type(e).__name__));sys.exit(1)
