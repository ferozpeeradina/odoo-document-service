// Same saved synthetic journey as prepare-journey.py, through DocumentService.
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import { OdooDocumentService } from '../adapter/OdooDocumentService.ts';
const f = JSON.parse(await fs.readFile('runtime/accounts.json', 'utf8'));
const business = JSON.parse(await fs.readFile('runtime/business.json', 'utf8'));
const base = 'http://127.0.0.1:18069';
const auth = await fetch(base + '/web/session/authenticate', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,params:{db:'packaging_poc',login:f.issuer.login,password:f.issuer.password}})});
assert.equal((await auth.json()).result.uid, f.issuer.uid);
const cookie = auth.headers.getSetCookie().map(c => c.split(';')[0]).filter(c => c.startsWith('session_id=')).at(-1)!;
const transport: typeof fetch = (url, init) => {
  const headers = new Headers(init?.headers); headers.set('Cookie', cookie);
  return fetch(url, {...init, headers});
};
const dms = new OdooDocumentService(base, transport);
const context = {tenantId:'synthetic-a',documentId:'synthetic-cad-contract-final',projectId:'synthetic-project-001',operationId:'contract-generate-final',localDocumentId:'local-contract-001'};
const input = {templateId:'synthetic-cad-contract',templateVersion:'1',snapshot:business.snapshot};
const version = await dms.generate(context, input);
const signContext = {...context,operationId:'contract-sign-final'};
const signInput = {versionId:version.versionId,signers:['alice','bob'].map(k => ({name:f[k].name,email:f[k].login}))};
const request = await dms.signRequest(signContext, signInput);
await fs.writeFile('runtime/journey.json',JSON.stringify({context,input,version,signContext,signInput,request}));
const artifact = (await dms.artifacts(context,version.versionId)).find(a => a.kind === 'document')!;
const response = await transport(artifact.url);
assert.equal(response.status,200);
const bytes = Buffer.from(await response.arrayBuffer());
assert.equal(bytes.subarray(0,4).toString(),'%PDF');
await fs.writeFile('artifacts/unsigned-contract.pdf',bytes);
console.log('Saved synthetic snapshot generated and signature request prepared through TypeScript DocumentService; unsigned PDF retrieved.');
