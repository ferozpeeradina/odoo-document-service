"""Actual Packaging record shapes against the real HTTP/QWeb transport; synthetic data only."""
import importlib.util,json,subprocess
s=importlib.util.spec_from_file_location('t','tests/http_service.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
head={'Authorization':'Bearer '+(t.ROOT/'service-runtime/tenant-wide.token').read_text().strip()}
checks=[]
def check(name,ok):
 if not ok:raise AssertionError(name)
 checks.append(name);print('PASS '+name)
parties={'business':{'name':'Saved Packaging Business'},'customer':{'name':'Saved Packaging Buyer'},'factory':{'name':'Saved Packaging Supplier'}}
for kind,recordkind in [('purchase_order','purchaseOrders'),('packing_list','shipments'),('invoice','invoices'),('ledger_statement','organisations'),('contract','orders')]:
 d={'status':'approved' if kind!='invoice' else 'draft','approvedBy':'owner','approvedAt':'2026-10-10T00:00:00Z','terms':'Saved approved contract terms','currency':'CAD','lines':[{'description':'Actual schema cartons','quantity':120,'unitPrice':'0.123456','lineTotalCents':1481}],'subtotalCents':1481,'taxCents':0,'totalCents':1481,'taxRates':[{'label':'DEMO ONLY','rate':'0'}],'internalNotes':'PRIVATE_SCHEMA_MARKER'}
 snap={'source':{'kind':recordkind,'id':'schema-source','revision':1,'data':d},'parties':parties,'demonstration':True}
 ctx={'tenantId':'synthetic-wide','documentId':'actual-schema-'+kind,'projectId':'future-project','operationId':'actual-schema-'+kind}
 if kind=='packing_list':
  d['items']=d.pop('lines');d.update({'shippingOption':'Saved ground freight','shippingDate':'2026-10-15','deliveryDate':'2026-10-19'})
 if kind=='ledger_statement':
  snap={'organisation':{'kind':'organisations','id':'factory-source','revision':1,'data':{'type':'factory','name':'Saved Packaging Supplier'}},'currency':'CAD','parties':parties,'demonstration':True,'purchaseOrders':[{'data':d}],'factoryPayments':[{'data':{'amountCents':500,'reference':'Saved deposit'}}],'factoryAdjustments':[],'openingBalanceCents':0,'balanceCents':981,'dateFrom':'2026-10-01','dateTo':'2026-10-31'};ctx.pop('projectId')
 r=t.call('/v1/documents',{'context':ctx,'input':{'templateId':kind,'templateVersion':'2','snapshot':snap}},headers=head)
 check('API snapshot accepted '+kind,r.status_code==200);v=r.json()
 pdf=t.call('/v1/documents/'+ctx['documentId']+'/versions/'+v['versionId']+'/download/document?tenantId=synthetic-wide',headers=head)
 check('authenticated PDF '+kind,pdf.status_code==200 and pdf.content.startswith(b'%PDF'))
 text=subprocess.run(['pdftotext','-','-'],input=pdf.content,capture_output=True,check=True).stdout.decode()
 check('demo label and internal-field exclusion '+kind,'DEMONSTRATION' in text and 'PRIVATE_SCHEMA_MARKER' not in text)
 if kind=='packing_list':check('shipment items and saved shipping fields','Actual schema cartons' in text and 'Saved ground freight' in text and '2026-10-19' in text and 'CAD' not in text)
 elif kind=='ledger_statement':check('factory ledger parties, payments and balances','Saved Packaging Supplier' in text and 'CAD 9.81' in text and 'CAD 5.00' in text and 'Saved Packaging Buyer' not in text)
 else:
  check('decimal unit price and saved rounded totals '+kind,'CAD 0.123456' in text and 'CAD 14.81' in text)
  if kind=='invoice':check('saved draft status and configured tax label','draft' in text and 'DEMO ONLY' in text)
 (t.ROOT/'artifacts'/('schema-'+kind+'.pdf')).write_bytes(pdf.content)
(t.ROOT/'artifacts/packaging-schema-tests.json').write_text(json.dumps({'result':'PASS','checks':checks},indent=2)+'\n')
