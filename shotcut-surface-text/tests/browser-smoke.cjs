// Development-only CDP integration, requires local Chromium with port 9223.
// Copyright (c) 2026. SPDX-License-Identifier: GPL-3.0-or-later
const fs=require('node:fs');
(async()=>{
const pages=await(await fetch('http://127.0.0.1:9223/json/list')).json(),page=pages.find(p=>p.url.startsWith('http://127.0.0.1:8765/'));
if(!page)throw Error('Assistant browser page missing');
const ws=new WebSocket(page.webSocketDebuggerUrl);await new Promise(r=>ws.onopen=r);
let id=0,pending=new Map();ws.onmessage=e=>{const r=JSON.parse(e.data);if(r.id&&pending.has(r.id)){const {resolve,reject}=pending.get(r.id);pending.delete(r.id);r.error?reject(Error(JSON.stringify(r.error))):resolve(r.result);}};
const call=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params}));});
async function evaluate(expression){const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
let ready=false;
for(let i=0;i<100;i++){
 try {ready=await evaluate(`document.readyState==='complete' && typeof imageFrame==='number' && !!document.getElementById('file')`);} catch {}
 if(ready)break;
 await new Promise(r=>setTimeout(r,50));
}
if(!ready)throw Error('Current assistant page did not finish loading');
const doc=await call('DOM.getDocument');const input=await call('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'#file'});
await call('DOM.setFileInputFiles',{nodeId:input.nodeId,files:[process.argv[2]]});
await evaluate(`(async()=>{for(let i=0;i<200;i++){if(info&&!busy)return;await new Promise(r=>setTimeout(r,50));}throw Error('Upload timed out: '+document.getElementById('toast').textContent)})()`);
await evaluate('selectFrame(24)');
await evaluate(`(async()=>{for(let i=0;i<100;i++){if(image&&imageFrame===24)return;await new Promise(r=>setTimeout(r,50));}throw Error('Frame missing')})()`);
// Click four actual canvas coordinates, exercising CSS-to-video coordinate conversion.
const rect=await evaluate(`(()=>{const r=canvas.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})()`);
for(const [x,y] of [[565,402],[1516,537],[1519,843],[552,718]]){
 const mx=rect.x+x/1920*rect.w,my=rect.y+y/1080*rect.h;
 await call('Input.dispatchMouseEvent',{type:'mousePressed',x:mx,y:my,button:'left',clickCount:1});
 await call('Input.dispatchMouseEvent',{type:'mouseReleased',x:mx,y:my,button:'left',clickCount:1});
}
await evaluate(`if(points.length!==4)throw Error('Selection failed');document.getElementById('add-anchor').click();document.getElementById('track').click();`);
await evaluate(`(async()=>{for(let i=0;i<400;i++){if(track&&!busy)return {frames:track.frames,lost:track.tracking_lost_frames};if(!busy&&document.getElementById('tracking-status').textContent.includes('失败'))throw Error('Tracking failed');await new Promise(r=>setTimeout(r,50));}throw Error('Tracking timed out: '+document.getElementById('tracking-status').textContent)})()`).then(console.log);
await evaluate(`selectFrame(36);`);
await evaluate(`new Promise(r=>setTimeout(r,600))`);
const result=await evaluate(`(async()=>{const r=await post('/api/export',{text:document.getElementById('text').value,style:style()});const response=await api('/api/download?id='+r.id);const blob=await response.blob();if(blob.size<3000000)throw Error('Export too small');return {archiveBytes:blob.size,title:document.title,anchors:anchors.length};})()`);
console.log(result);
const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(process.argv[3],Buffer.from(shot.data,'base64'));
ws.close();
})().catch(e=>{console.error(e);process.exit(1)});
