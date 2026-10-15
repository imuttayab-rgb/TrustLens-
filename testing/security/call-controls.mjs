/** Actual call controls with deterministic API/media adapters; no hardware audio claim. */
import fs from 'node:fs';
import http from 'node:http';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
const root=resolve(process.env.TRUSTLENS_ROOT || '.');
const dir=resolve(process.env.AUDIT_OUT || 'security-evidence');fs.mkdirSync(dir,{recursive:true});
const req=createRequire(root+'/apps/web/package.json');
const viteRequire=createRequire(createRequire(req.resolve('vitest/package.json')).resolve('vite/package.json'));
const {build}=viteRequire('esbuild');
const chromium=process.env.AUDIT_CHROMIUM_MODULE?((m)=>m.default||m)(req(process.env.AUDIT_CHROMIUM_MODULE)):null;
const {chromium:pw,expect}=createRequire(root+'/testing/e2e/package.json')('@playwright/test');
const mocks={
 'livekit-client':`
 export const Track={Kind:{Audio:'audio'},Source:{Microphone:'microphone'}};
 export const AudioPresets={speech:{}};
 export const RoomEvent=new Proxy({}, {get:(_,key)=>key});
 export async function createLocalAudioTrack(){const media=new EventTarget();media.getSettings=()=>({deviceId:'mic1'});const t={mediaStreamTrack:media,isMuted:false,stop(){window.fixture.stopped++},async mute(){this.isMuted=true},async unmute(){this.isMuted=false},async getRTCStatsReport(){return new Map()}};return t;}
 export class Room {
   constructor(){this.handlers={};this.state='disconnected';this.canPlaybackAudio=true;this.ids={audioinput:'mic1',audiooutput:'default'};window.fixture.room=this;this.localParticipant={publishTrack:async()=>{this.emitAudio();}};}
   on(e,f){(this.handlers[e]??=[]).push(f);return this;} emit(e,...a){this.handlers[e]?.forEach(f=>f(...a));}
   emitAudio(){const a=document.createElement('audio');a.dataset.testCallAudio='true';a.play=()=>Promise.resolve();document.body.append(a);this.emit('TrackSubscribed',{kind:'audio',attach:()=>a,detach:()=>[a],getRTCStatsReport:async()=>new Map()});}
   async connect(){this.state='connected';window.fixture.connects++;}
   removeAllListeners(){this.handlers={};}
   async disconnect(){this.state='disconnected';window.fixture.disconnects++;}
   async startAudio(){this.canPlaybackAudio=true;}
   getActiveDevice(k){return this.ids[k];}
   async switchActiveDevice(k,id){window.fixture.switches.push([k,id]);if(id==='denied')throw new DOMException('Denied','NotAllowedError');if(id==='unavailable')return false;if(id==='slow')await new Promise(r=>window.fixture.resolveSwitch=r);this.ids[k]=id;this.emit('ActiveDeviceChanged',k,id);return true;}
 }
 `,
 '@/features/profile':`
 const row=()=>({...window.fixture.call,serverNow:new Date().toISOString()});
 export async function profileRequest(path,init={}){const f=window.fixture;
 if(path==='/me/calls/config')return {enabled:true,pushPublicKey:''};
 if(path.startsWith('/me/calls/active'))return f.call?row():null;
 if(path==='/me/calls'&&init.method==='POST'){const body=JSON.parse(init.body);f.call={id:body.callId,conversationId:body.conversationId,direction:'outgoing',counterpartName:'Test member',listingTitle:'Test listing',state:'connecting',owned:true,canAnswer:false,remoteMuted:false,createdAt:new Date().toISOString(),connectedAt:new Date().toISOString()};return row();}
 if(path.endsWith('/join'))return {url:'ws://test.invalid',token:'test'};
 if(path.endsWith('/actions')){const b=JSON.parse(init.body);if(['end','failed'].includes(b.action)){const r={...row(),state:'ended',reason:'ended'};f.call=null;return r;}return {...row(),state:'active'};}
 return [];}
 `,
 '@/lib/auth/use-session':`const data={id:'fixture-user'};export const useSession=()=>({data});`,
 '../components/VoicePlayback':`export const useVoicePlayer=()=>({stop(){}});export const voiceTime=(n)=>'0:'+String(Math.floor(n)).padStart(2,'0');`,
 'next/link':`import React from 'react';export default function Link(p){return <a {...p}/>}`,
};
mocks['./VoicePlayback'] = mocks['../components/VoicePlayback'];
await build({stdin:{contents:`import React from 'react';import {createRoot} from 'react-dom/client';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import {VoiceCallProvider,useVoiceCalls} from '${root}/apps/web/src/features/messaging/components/VoiceCalls.tsx';function Start(){const calls=useVoiceCalls();return <button onClick={()=>calls.start('fixture-chat')} disabled={!calls.available}>Start test call</button>}const q=new QueryClient({defaultOptions:{queries:{retry:false}}});createRoot(document.getElementById('app')).render(<QueryClientProvider client={q}><VoiceCallProvider><Start/></VoiceCallProvider></QueryClientProvider>);`,resolveDir:root+'/apps/web',loader:'tsx'},bundle:true,format:'iife',outfile:dir+'/harness.js',jsx:'automatic',plugins:[{name:'fixtures',setup(b){b.onResolve({filter:/.*/},a=>a.path in mocks?{path:a.path,namespace:'fixture'}:undefined);b.onLoad({filter:/.*/,namespace:'fixture'},a=>({contents:mocks[a.path],loader:'tsx',resolveDir:root+'/apps/web'}));}}]});
const fixture=`window.fixture={call:null,stopped:0,connects:0,disconnects:0,switches:[]};
 const d=(kind,deviceId,label)=>({kind,deviceId,label,groupId:'test',toJSON(){return this}});
 Object.defineProperty(navigator.mediaDevices,'enumerateDevices',{value:async()=>[d('audioinput','mic1','Built-in microphone'),d('audioinput','mic2','Headset microphone'),d('audiooutput','speaker','Computer speakers'),d('audiooutput','headset','Bluetooth headset'),d('audiooutput','denied','Permission denied device'),d('audiooutput','unavailable','Disconnected speaker'),d('audiooutput','slow','Slow switch device')]});
 Object.defineProperty(navigator.mediaDevices,'selectAudioOutput',{value:async()=>d('audiooutput','headset','Bluetooth headset')});
 if(location.search.includes('unsupported'))delete HTMLMediaElement.prototype.setSinkId;
 `;
const server=http.createServer((req,res)=>{if(req.url==='/style.css'){res.setHeader('Content-Type','text/css');const css=root+'/apps/web/.next/static/css';res.end(fs.readdirSync(css).filter(n=>n.endsWith('.css')).map(n=>fs.readFileSync(css+'/'+n,'utf8')).join('\n'));return;}if(req.url==='/harness.js'){res.setHeader('Content-Type','application/javascript');res.end(fs.readFileSync(dir+'/harness.js'));return;}res.setHeader('Content-Type','text/html');res.end(`<html><head><link rel="stylesheet" href="/style.css"></head><body><div id="app"></div><script>${fixture}</script><script src="/harness.js"></script></body></html>`);});await new Promise(r=>server.listen(3112,'127.0.0.1',r));
let browser;
try{
 process.env.TMPDIR=process.env.AUDIT_BROWSER_TMP || resolve(dir,'browser-temp');fs.mkdirSync(process.env.TMPDIR,{recursive:true});
 browser=await pw.launch({executablePath:chromium?await chromium.executablePath():undefined,args:[...(chromium?chromium.args:[]),'--no-proxy-server'],headless:true});
 const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:3112');await page.getByRole('button',{name:'Start test call'}).click();
 await page.getByRole('button',{name:'Audio settings',exact:true}).click();
 await expect(page.getByLabel('Call microphone',{exact:true})).toBeEnabled({timeout:10000});
 await page.getByLabel('Call microphone',{exact:true}).selectOption('mic2');await expect(page.getByLabel('Call microphone',{exact:true})).toHaveValue('mic2');
 await page.getByRole('button',{name:'Mute microphone',exact:true}).click();await expect(page.getByRole('button',{name:'Unmute microphone',exact:true})).toBeVisible();
 await page.getByLabel('Call microphone',{exact:true}).selectOption('mic1');await expect(page.getByRole('button',{name:'Unmute microphone',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Unmute microphone',exact:true}).click();
 await page.getByLabel('Call speaker',{exact:true}).selectOption('speaker');await expect(page.getByLabel('Call speaker',{exact:true})).toHaveValue('speaker');
 await page.getByRole('button',{name:'Choose another speaker / headset',exact:true}).click();await expect(page.getByLabel('Call speaker',{exact:true})).toHaveValue('headset');
 await page.setViewportSize({width:390,height:844});await expect(page.getByRole('button',{name:'End call',exact:true})).toBeVisible();expect((await page.locator('section[aria-label="Voice call"]').boundingBox()).width).toBeLessThan(390);await page.screenshot({path:dir+'/call-mobile.png'});await page.setViewportSize({width:1280,height:900});
 await page.getByLabel('Call speaker',{exact:true}).selectOption('denied');await expect(page.getByRole('alert')).toContainText('permission was not granted');await expect(page.getByLabel('Call speaker',{exact:true})).toHaveValue('headset');
 await page.getByLabel('Call speaker',{exact:true}).selectOption('unavailable');await expect(page.getByRole('alert')).toContainText('could not be changed');await expect(page.getByLabel('Call speaker',{exact:true})).toHaveValue('headset');
 await page.getByRole('button',{name:'Mute call sound',exact:true}).click();await expect.poll(()=>page.evaluate(()=>[...document.querySelectorAll('audio[data-test-call-audio]')].every(n=>n.muted))).toBe(true);
 await page.evaluate(()=>window.fixture.room.emitAudio());await expect.poll(()=>page.evaluate(()=>[...document.querySelectorAll('audio[data-test-call-audio]')].every(n=>n.muted))).toBe(true);
 await page.getByRole('button',{name:'Minimize call',exact:true}).click();await expect(page.getByRole('button',{name:'Audio settings',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'End call',exact:true})).toBeVisible();expect(await page.evaluate(()=>window.fixture.disconnects)).toBe(0);
 await page.getByRole('button',{name:'Expand call',exact:true}).click();await page.getByRole('button',{name:'Unmute call sound',exact:true}).click();await expect.poll(()=>page.evaluate(()=>[...document.querySelectorAll('audio[data-test-call-audio]')].every(n=>!n.muted))).toBe(true);
 await page.getByLabel('Call speaker',{exact:true}).selectOption('slow');await expect(page.getByText('Changing audio device…')).toBeVisible();await page.getByRole('button',{name:'End call',exact:true}).click();await page.evaluate(()=>window.fixture.resolveSwitch());await expect(page.getByRole('button',{name:'End call',exact:true})).toHaveCount(0);await expect(page.locator('audio[data-test-call-audio]')).toHaveCount(0);
 expect(await page.evaluate(()=>window.fixture.disconnects)).toBe(1);
 await page.goto('http://127.0.0.1:3112?unsupported');await page.getByRole('button',{name:'Start test call'}).click();await page.getByRole('button',{name:'Audio settings',exact:true}).click();await expect(page.getByText('This browser controls the speaker automatically.',{exact:false})).toBeVisible();await expect(page.getByLabel('Call speaker',{exact:true})).toHaveCount(0);await page.getByRole('button',{name:'End call',exact:true}).click();
 expect(errors).toEqual([]);
 console.log('CALL_CONTROLS_UI_PASS: microphone/speaker selection; browser picker; permission denial and false-result rollback; mute preserved during input selection; receive-sound mute and newly attached tracks; minimize retains room and end button; end during pending switch; cleanup; unsupported-browser guidance. Real React component, test media adapter (no live SFU or hardware audio verification).');
} finally {if(browser)await browser.close();await new Promise(r=>server.close(r));}
