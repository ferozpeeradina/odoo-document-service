import fs from 'node:fs/promises';
import { chromium } from 'playwright';
const base='http://127.0.0.1:18079';
const a=JSON.parse(await fs.readFile('service-runtime/test-association.json','utf8'));
const token=(await fs.readFile('service-runtime/service.token','utf8')).trim();
const checks=[];
function check(name,value){if(!value)throw new Error(name);checks.push(name);console.log('PASS '+name);}
async function codeFor(email,after){
  for(let i=0;i<25;i++){
    const files=await fs.readdir('service-runtime/mail-final');
    const mails=[];
    for(const f of files.filter(f=>f.startsWith('mail-')&&f.endsWith('.json'))){
      const m=JSON.parse(await fs.readFile('service-runtime/mail-final/'+f,'utf8'));
      if(m.id>after&&m.recipient===email&&m.operation.startsWith('otp:'))mails.push(m);
    }
    mails.sort((a,b)=>b.id-a.id);
    if(mails.length)return mails[0].body.match(/Verification code: (\d{6})/)[1];
    await new Promise(r=>setTimeout(r,1000));
  }
  throw new Error('fake mailbox delivery timeout');
}
const browser=await chromium.launch({headless:true});
try{
  const anonymous=await browser.newContext();
  check('invitation locator discloses no recipient',(await anonymous.request.get(base+'/recipient/'+a.requestId)).status()===200);
  const bad=await anonymous.request.post(base+'/recipient/'+a.requestId+'/verify',{data:{email:'alice@example.test',code:'000000'}});
  check('no challenge denies verification',bad.status()===403);
  const contexts=[];let aliceSigningURL;
  for(const [i,email] of ['alice@example.test','bob@example.test'].entries()){
    const context=await browser.newContext(); contexts.push(context);
    await context.route('**/*',route=>{const u=new URL(route.request().url());return ['127.0.0.1','localhost'].includes(u.hostname)||['blob:','data:'].includes(u.protocol)?route.continue():route.abort();});
    const page=await context.newPage();
    const errorTypes=[];page.on('pageerror',()=>errorTypes.push('browser_error'));
    page.on('response',r=>{if(r.status()>=400)console.log('HTTP diagnostic '+r.status()+' '+(new URL(r.url()).pathname.startsWith('/web/')?new URL(r.url()).pathname:new URL(r.url()).pathname.split('/').slice(0,3).join('/')));});
    await page.goto(base+'/recipient/'+a.requestId);
    await page.locator('input[name=email]').fill(email);
    const existing=(await fs.readdir('service-runtime/mail-final')).filter(f=>/^mail-\d+\.json$/.test(f)).map(f=>Number(f.match(/\d+/)[0]));
    const after=Math.max(0,...existing);
    await page.getByRole('button',{name:'Email verification code'}).click();
    const code=await codeFor(email,after);
    const invalid=await context.request.post(base+'/recipient/'+a.requestId+'/verify',{data:{email,code:'invalid'}});
    check('incorrect code denied '+i,invalid.status()===403);
    await page.locator('input[name=code]').fill(code);
    const verifiedResponse=page.waitForResponse(r=>r.url().endsWith('/verify'));
    await page.getByRole('button',{name:'Verify and sign'}).click();
    const vr=await verifiedResponse;console.log('Verification HTTP status '+vr.status());
    await page.waitForLoadState('networkidle');
    check('OTP opens existing OCA UI '+i,await page.locator('#sign_oca_button').count()===1);
    const signingURL=page.url();
    check('forwarded signing URL blocked '+i,(await anonymous.request.get(signingURL,{maxRedirects:0})).status()!==200);
    const replay=await anonymous.request.post(base+'/recipient/'+a.requestId+'/verify',{data:{email,code},maxRedirects:0});
    check('OTP is single use '+i,replay.status()===403);
    if(i===0)aliceSigningURL=signingURL;
    if(i===1){const unrelated=await context.newPage();const r=await unrelated.goto(aliceSigningURL);check('other verified recipient cannot use signer URL',r.status()===403);await unrelated.close();}
    const cookies=await context.cookies();
    check('session cookie secure HttpOnly SameSite '+i,cookies.some(c=>c.name==='session_id'&&c.httpOnly&&c.secure&&c.sameSite==='Strict'));
    const frame=page.frameLocator('iframe');
    try{await frame.locator(`[data-field="${i+1}"]`).click({timeout:30000});}catch(e){console.log('UI diagnostic '+JSON.stringify({browserErrors:errorTypes.length,iframes:await page.locator('iframe').count(),fields:await frame.locator('[data-field]').count(),pdfPages:await frame.locator('.page').count()}));throw e;}
    await page.getByRole('button',{name:/adopt|sign|apply/i}).last().click();
    const signedResponse=page.waitForResponse(r=>new URL(r.url()).pathname.startsWith('/sign_oca/sign/'),{timeout:25000});
    await page.locator('#sign_oca_button').click();
    const sr=await signedResponse; check('OCA signing transport accepted '+i,sr.status()===200);
    await page.locator('#sign_oca_button').waitFor({state:'detached',timeout:15000});
    await page.waitForLoadState('networkidle');
    check('OCA browser signature accepted '+i,await page.locator('#sign_oca_button').count()===0);
    const status=await anonymous.request.post(base+'/v1/signature-requests/'+a.requestId+'/status',{headers:{Authorization:'Bearer '+token},data:{context:{...a.context,operationId:'status-ui'},input:{versionId:a.versionId}}});
    const data=await status.json();
    check('completion state after signer '+i,status.status()===200&&data.status===(i===0?'partial':'completed'));
    if(i===0){
      const arts=await anonymous.request.get(base+`/v1/documents/${a.context.documentId}/versions/${a.versionId}/artifacts?tenantId=${a.context.tenantId}`,{headers:{Authorization:'Bearer '+token}});
      check('partial has no final artifacts',(await arts.json()).length===1);
    }
  }
  await anonymous.close();for(const c of contexts)await c.close();
  await fs.writeFile('artifacts/otp-ui-tests.json',JSON.stringify({result:'PASS',checks},null,2));
}catch(e){console.log('FAIL '+(e.message.includes('http')||e.message.includes('Call log')?'browser journey (details withheld)':e.message));process.exitCode=1;}
finally{await browser.close();}
