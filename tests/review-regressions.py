import copy,importlib.util,json,subprocess
s=importlib.util.spec_from_file_location('t','tests/http_service.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
checks=[]
def check(name,ok):
 if not ok:raise AssertionError(name)
 checks.append(name);print('PASS '+name)
ctx=dict(t.CTX,documentId='review-image',operationId='review-image',actorId='synthetic-actor',localDocumentId='local-image')
png='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC'
r=t.call('/v1/uploads',{'context':ctx,'input':{'filename':'synthetic.png','contentType':'image/png','contentBase64':png}})
check('fresh associated image uploaded',r.status_code==200);v=r.json()
check('generic authenticated image download denied',t.call('/v1/documents/review-image/versions/'+v['versionId']+'/download/document?tenantId=synthetic-a').status_code==403)
check('bound image route remains usable',t.call('/v1/documents/review-image/versions/'+v['versionId']+'/image?tenantId=synthetic-a&actorId=synthetic-actor&localDocumentId=local-image').status_code==200)
head={'Authorization':'Bearer '+(t.ROOT/'service-runtime/tenant-wide.token').read_text().strip()}
ctx={'tenantId':'synthetic-wide','documentId':'review-contract','projectId':'future-project','operationId':'review-contract-generate'}
snap=copy.deepcopy(t.SNAP);snap['project']={'id':'future-project'}
r=t.call('/v1/documents',{'context':ctx,'input':{'templateId':'contract','templateVersion':'2','snapshot':snap}},headers=head)
check('fresh approved contract generated',r.status_code==200);v=r.json();ctx['operationId']='sign-whitespace-review'
r=t.call('/v1/signature-requests',{'context':ctx,'input':{'versionId':v['versionId'],'signers':[{'name':'Whitespace Test Recipient','email':'  Whitespace@Example.Test  '}]}},headers=head)
check('normalized email creates signing request',r.status_code==200)
check('normalized email retry returns same request',t.call('/v1/signature-requests',{'context':ctx,'input':{'versionId':v['versionId'],'signers':[{'name':'Whitespace Test Recipient','email':'whitespace@example.test'}]}},headers=head).json()==r.json())
snap={'organisation':{'id':'ledger-organisation','data':{'type':'customer','name':'Required Ledger Customer','internalNotes':'PRIVATE_LEDGER_MARKER'}},'currency':'CAD','invoices':[],'receipts':[],'allocations':[],'adjustments':[],'openingBalanceCents':0,'balanceCents':0}
ctx={'tenantId':'synthetic-wide','documentId':'ledger-required-party','operationId':'ledger-required-party'}
r=t.call('/v1/documents',{'context':ctx,'input':{'templateId':'ledger_statement','templateVersion':'2','snapshot':snap}},headers=head)
check('ledger accepts required organisation without optional parties',r.status_code==200)
v=r.json();check('no-project result matches optional TypeScript field','projectId' not in v)
pdf=t.call('/v1/documents/'+ctx['documentId']+'/versions/'+v['versionId']+'/download/document?tenantId=synthetic-wide',headers=head)
text=subprocess.run(['pdftotext','-','-'],input=pdf.content,capture_output=True,check=True).stdout.decode()
check('required ledger identity rendered with private field exclusion','Required Ledger Customer' in text and 'PRIVATE_LEDGER_MARKER' not in text)
(t.ROOT/'artifacts/review-regression-tests.json').write_text(json.dumps({'result':'PASS','checks':checks},indent=2)+'\n')
