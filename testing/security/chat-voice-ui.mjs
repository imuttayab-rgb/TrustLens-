/** Chat/recording/player regression against the built app with synthetic HTTP/media. */
import {resolve} from 'node:path';
import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import fs from 'node:fs';
const artifactDir=resolve(process.env.AUDIT_OUT || 'security-evidence');fs.mkdirSync(artifactDir,{recursive:true});
process.env.TMPDIR=process.env.AUDIT_BROWSER_TMP || resolve(artifactDir,'browser-temp');fs.mkdirSync(process.env.TMPDIR,{recursive:true});
const root=resolve(process.env.TRUSTLENS_ROOT || '.');
const require=createRequire(root+'/testing/e2e/package.json');const {chromium:pw,expect}=require('@playwright/test');
const chromium=process.env.AUDIT_CHROMIUM_MODULE?((m)=>m.default||m)(require(process.env.AUDIT_CHROMIUM_MODULE)):null;
const child=spawn(process.execPath,[root+'/apps/web/node_modules/next/dist/bin/next','start','--port','3100','--hostname','127.0.0.1'],{cwd:root+'/apps/web',env:{...process.env,NEXT_TELEMETRY_DISABLED:'1'},stdio:['ignore','pipe','pipe']});
let ready=false;child.stdout.on('data',d=>{process.stdout.write(d);if(d.toString().includes('Ready'))ready=true;});child.stderr.on('data',d=>process.stderr.write(d));child.on('exit',code=>console.log('Next server exit',code));
for(let i=0;i<160&&!ready;i++)await new Promise(r=>setTimeout(r,250));
let browser;
try {
 browser=await pw.launch({executablePath:chromium?await chromium.executablePath():undefined,args:[...(chromium?chromium.args:[]),'--no-proxy-server','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream'],headless:true});
 const context=await browser.newContext({viewport:{width:1280,height:900},permissions:['microphone']});
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR',e.message);});page.on('console',m=>{if(m.type()==='error')console.log('BROWSER',m.text());});
 const buyer='10000000-0000-0000-0000-000000000001',seller='10000000-0000-0000-0000-000000000002',cid='10000000-0000-0000-0000-000000000003';
 let messages=[{id:'10000000-0000-0000-0000-000000000004',conversationId:cid,senderId:buyer,body:'Original test message',kind:'text',createdAt:new Date().toISOString(),readAt:null,editableUntil:new Date(Date.now()+60000).toISOString(),deleted:false},{id:'10000000-0000-0000-0000-000000000005',conversationId:cid,senderId:seller,body:'Earlier seller message',kind:'text',createdAt:new Date(Date.now()-120000).toISOString(),readAt:null,editableUntil:new Date(Date.now()-60000).toISOString(),deleted:false}];
 let saved=[],closed=false,voiceUploads=0,played=0;let recorded=null;let uploadKeys=[];
 const conversation=()=>({id:cid,listingId:null,listingTitle:'Test listing',counterpartName:'Synthetic seller',counterpartUserId:seller,lastMessageAt:new Date().toISOString(),lastMessagePreview:'Test message',unreadCount:0,createdAt:new Date().toISOString(),muted:false,counterpartSellerHandle:null,counterpartRiskLevel:null,counterpartScore:null,serverNow:new Date().toISOString(),canSend:!closed,readOnly:closed,closesAt:closed?new Date(Date.now()-1000).toISOString():null,listingStatus:closed?'SOLD':'ACTIVE'});
 await page.route('**/api/v1/**',async route=>{
   const req=route.request(),url=new URL(req.url()),path=url.pathname.replace('/api/v1',''),method=req.method();
   const reply=data=>route.fulfill({status:200,contentType:'application/json',headers:{'access-control-allow-origin':'http://127.0.0.1:3100','access-control-allow-credentials':'true'},body:JSON.stringify({data})});
   if(method==='OPTIONS')return route.fulfill({status:204,headers:{'access-control-allow-origin':'http://127.0.0.1:3100','access-control-allow-credentials':'true','access-control-allow-methods':'GET,POST,PATCH,DELETE','access-control-allow-headers':'authorization,content-type'}});
   if(path==='/me')return reply({id:buyer,email:'test@example.test',fullName:'Test buyer',roles:['BUYER'],permissions:[],status:'ACTIVE'});
   if(path==='/auth/refresh')return reply({accessToken:'synthetic-ui-test'});
   if(path==='/me/profile')return reply({id:buyer,userId:buyer,username:'testbuyer',publicName:'Test buyer',displayName:'Test buyer',handle:'testbuyer',profileUrl:'/profile/testbuyer',photoUrl:null,photoMatched:true,nameVerified:true,score:null,riskLevel:null,verification:{identity:true,phone:true,email:true},canInteract:true,initialized:true});
   if(path==='/me/conversations'&&method==='GET')return reply([conversation()]);
   if(path===`/me/conversations/${cid}`)return reply(conversation());
   if(path.endsWith('/timeline'))return reply({items:messages,nextCursor:null,serverNow:new Date().toISOString()});
   if(path.endsWith('/clear/undo')){messages=saved;return reply({});}
   if(path.endsWith('/clear')){saved=messages;messages=[];return reply({undoToken:'test-token',undoUntil:new Date(Date.now()+10000).toISOString()});}
   if(path.includes('/chat-messages/')&&method==='PATCH'){const b=req.postDataJSON();messages=messages.map(m=>m.id===path.split('/')[3]?{...m,body:b.body,editedAt:new Date().toISOString()}:m);return reply({});}
   if(path.includes('/chat-messages/')&&method==='DELETE'){messages=messages.map(m=>m.id===path.split('/')[3]?{...m,body:'This message was deleted',deleted:true}:m);return reply({});}
   if(path.endsWith('/voice')){voiceUploads++;uploadKeys.push(url.searchParams.get('clientId'));recorded=req.postDataBuffer();fs.writeFileSync(resolve(artifactDir,'recorded.webm'),recorded);if(voiceUploads===1)return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Synthetic upload interruption'})});for(let n=0;n<2;n++)messages.push({id:'voice-'+n,conversationId:cid,senderId:buyer,body:'Voice message',kind:'voice',createdAt:new Date().toISOString(),editableUntil:new Date(Date.now()+60000).toISOString(),voice:{duration:1.6,waveform:[.2,.5,.8,.3,.6,.9,.2,.5]}});return reply({conversationId:cid,message:{id:'voice-0'}});}
   if(path.endsWith('/audio'))return route.fulfill({status:200,contentType:'audio/webm',body:recorded});
   if(path.endsWith('/played')){played++;return reply({playedAt:new Date().toISOString()});}
   if(path.endsWith('/support'))return reply({reportId:'synthetic-support-case'});
   if(path==='/me/conversations'&&method==='POST'){const b=req.postDataJSON();messages.push({id:crypto.randomUUID(),conversationId:cid,senderId:buyer,body:b.body,kind:'text',createdAt:new Date().toISOString(),editableUntil:new Date(Date.now()+60000).toISOString()});return reply({conversationId:cid,message:messages.at(-1)});}
   if(path.includes('notification'))return reply([]);
   if(path.includes('categories')||path.includes('locations'))return reply([]);
   return route.fulfill({status:404,contentType:'application/json',body:JSON.stringify({detail:'Synthetic test route not used'})});
 });
 await page.goto(`http://127.0.0.1:3100/messages/${cid}`);
 await expect(page.getByText('Original test message',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Edit',exact:true}).click();await page.getByRole('textbox',{name:'Edit message text'}).fill('Edited test message');await page.getByRole('button',{name:'Save edit'}).click();await expect(page.getByText('Edited test message',{exact:true})).toBeVisible();
 page.on('dialog',dialog=>dialog.accept());
 await page.getByRole('button',{name:'Clear my chat'}).click();await expect(page.getByText('No messages in your current chat history.')).toBeVisible();await page.getByRole('button',{name:/Undo \(/}).click();await expect(page.getByText('Edited test message',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Record voice message'}).click();await expect(page.getByRole('button',{name:'Pause recording'})).toBeVisible();await page.waitForTimeout(1100);await page.getByRole('button',{name:'Pause recording'}).click();await expect(page.getByRole('button',{name:'Resume recording'})).toBeVisible();await page.getByRole('button',{name:'Resume recording'}).click();await page.waitForTimeout(500);await page.getByRole('button',{name:'Preview',exact:true}).click();await expect(page.getByRole('button',{name:'Send voice',exact:true})).toBeVisible();await page.getByRole('button',{name:'Send voice',exact:true}).click();await expect(page.getByText('Upload interrupted. Your recording is ready to retry.',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Send voice',exact:true}).click();await expect.poll(()=>voiceUploads).toBe(2);if(uploadKeys[0]!==uploadKeys[1])throw new Error('Voice retry key changed');
 await page.getByRole('button',{name:'Play voice message',exact:true}).first().click();await expect.poll(()=>played).toBeGreaterThan(0);const player=page.locator('[aria-label="Voice player"]');await expect(player).toBeVisible();await player.getByRole('button',{name:'1×',exact:true}).click();await expect(player.getByRole('button',{name:'1.5×',exact:true})).toBeVisible();await player.getByRole('button',{name:'1.5×',exact:true}).click();await expect(player.getByRole('button',{name:'2×',exact:true})).toBeVisible();await expect.poll(()=>played).toBeGreaterThan(1);
 await page.locator('a[href="/messages"]').first().click();await expect(player).toBeVisible();await page.locator(`a[href="/messages/${cid}"]`).first().click();await expect(player).toBeVisible();await player.getByRole('button',{name:'Close voice player'}).click();
 await page.getByRole('textbox',{name:'Message',exact:true}).fill('New UI message');await page.getByRole('button',{name:'Send message',exact:true}).click();await expect(page.getByText('New UI message',{exact:true})).toBeVisible();
 closed=true;await page.reload();await expect(page.getByText('This conversation is read-only.',{exact:true})).toBeVisible();await expect(page.getByRole('textbox',{name:'Message',exact:true})).toHaveCount(0);await page.getByRole('button',{name:'Report issue / support',exact:true}).click();await page.getByLabel('Describe what happened').fill('Synthetic delayed delivery complaint');await page.getByRole('button',{name:'Submit issue'}).click();await expect(page.getByText('synthetic-support-case',{exact:true})).toBeVisible();
 await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Close dialog'}).click();await expect(page.getByText('This conversation is read-only.',{exact:true})).toBeVisible();
 if(errors.length)throw new Error('Browser exceptions: '+errors.join('; '));
 console.log('UI PASS: edit, clear, undo, native microphone record/pause/resume/preview/upload retry, speed, sequential playback, player across navigation, text send, read-only, support, mobile layout.');
} finally {if(browser)await browser.close();child.kill('SIGTERM');}
