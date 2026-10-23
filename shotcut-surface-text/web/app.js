// Copyright (c) 2026. SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
const $=id=>document.getElementById(id), token=location.hash.slice(1);
let info=null, frame=0, points=[], anchors=[], track=null, image=null, imageFrame=-1, imageURL=null, request=0, playing=false, pollTimer=null, toastTimer=null, drawTimer=null, busy=false;
const canvas=$('canvas'), ctx=canvas.getContext('2d');
async function api(path,options={}){
    options.headers={...(options.headers||{}),'X-Surface-Token':token};
    const response=await fetch(path,options);
    if(!response.ok){let e;try{e=await response.json();}catch{e={error:response.statusText};}throw Error(e.error||'请求失败');}
    return response;
}
async function post(path,data){return (await api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})).json();}
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,6500);}
function style(){return {color:$('color').value,size:Number($('size').value)/100,vertical:Number($('vertical').value)/100,aspect:$('aspect').value?Number($('aspect').value):null};}
function enable(){
    for(const id of ['timeline','frame-number','previous','next','play','undo-point','clear-points'])$(id).disabled=!info||busy;
    $('choose').disabled=busy;$('file').disabled=busy;
    $('add-anchor').disabled=points.length!==4||busy;
    $('track').disabled=!anchors.length||busy;
    for(const id of ['export','copy','preview'])$(id).disabled=!track||busy;
}
function dirty(){track=null;$('preview').checked=false;$('tracking-status').textContent='参考帧已改变，请重新分析。';enable();}
function draw(){
    if(!info||!image)return;
    ctx.clearRect(0,0,canvas.width,canvas.height);ctx.drawImage(image,0,0,canvas.width,canvas.height);
    let q=points, tracked=false;
    if(!q.length&&track&&track.frames_data[frame].valid){q=track.frames_data[frame].quad;tracked=true;}
    const scale=canvas.width/1000;
    if(q.length){ctx.strokeStyle=tracked?'#b8eb9b':'#ffe7a1';ctx.lineWidth=2.5*scale;ctx.beginPath();q.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));if(q.length===4)ctx.closePath();ctx.stroke();
        q.forEach(([x,y],i)=>{ctx.fillStyle='#142017';ctx.beginPath();ctx.arc(x,y,13*scale,0,2*Math.PI);ctx.fill();ctx.stroke();ctx.fillStyle='#f2f8ef';ctx.textAlign='center';ctx.textBaseline='middle';ctx.font=`${12*scale}px sans-serif`;ctx.fillText(i+1,x,y);});}
    $('selection-help').textContent=points.length===4?'四角已选好，保存为参考帧后开始跟踪。':`已选 ${points.length}/4 · 下一点：${['左上','右上','右下','左下'][points.length]}`;
    $('frame-status').hidden=!track;
    if(track){const r=track.frames_data[frame];$('frame-status').textContent=r.valid?'● 跟踪有效':'○ '+r.reason;}
}
async function loadFrame(){
    if(!info)return;
    const serial=++request, targetFrame=frame;
    try{
        let response;
        if(track&&$('preview').checked)response=await api('/api/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:frame,text:$('text').value,style:style()})});
        else response=await api('/api/frame?index='+frame);
        const blob=await response.blob();if(serial!==request)return;
        const url=URL.createObjectURL(blob), img=new Image();await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=reject;img.src=url;});
        if(serial!==request){URL.revokeObjectURL(url);return;}
        if(imageURL)URL.revokeObjectURL(imageURL);imageURL=url;image=img;imageFrame=targetFrame;draw();
    }catch(e){if(serial===request)toast(e.message);}
}
function selectFrame(value){
    if(!info)return;request++;frame=Math.max(0,Math.min(info.frames-1,Math.round(Number(value)||0)));
    $('timeline').value=frame;$('frame-number').value=frame;$('time').textContent=(frame*info.fps_den/info.fps_num).toFixed(3)+' s';
    const anchor=anchors.find(a=>a.frame===frame);points=anchor?anchor.quad.map(p=>p.slice()):[];
    enable();clearTimeout(drawTimer);drawTimer=setTimeout(loadFrame,80);
}
async function openFile(file){
    if(!file||busy)return;playing=false;busy=true;enable();$('tracking-status').textContent='正在打开视频，仅在本机读取…';
    try{
        info=await (await api('/api/upload',{method:'POST',headers:{'X-File-Name':encodeURIComponent(file.name)},body:file})).json();
        track=null;anchors=[];points=[];image=null;$('preview').checked=false;canvas.width=info.width;canvas.height=info.height;canvas.hidden=false;$('empty').hidden=true;
        $('filename').textContent=info.name;$('resolution').textContent=`${info.width} × ${info.height} / ${(info.fps_num/info.fps_den).toFixed(3)} fps`;
        $('timeline').max=info.frames-1;$('frame-number').max=info.frames-1;
        $('tracking-status').textContent='滑到清晰的一帧，依次点选表面的四个角。';renderAnchors();selectFrame(0);
    }catch(e){toast(e.message);}finally{busy=false;enable();}
}
function renderAnchors(){
    $('anchors').replaceChildren();$('anchor-count').textContent=anchors.length;
    if(!anchors.length){const p=document.createElement('p');p.className='muted';p.textContent='保存第一个参考帧后，开始自动跟踪。丢失后可在清晰帧添加修正点。';$('anchors').append(p);}
    for(const a of anchors){const item=document.createElement('div');item.className='anchor';const jump=document.createElement('button');jump.textContent=`帧 ${a.frame}`;jump.onclick=()=>selectFrame(a.frame);const remove=document.createElement('button');remove.textContent='×';remove.title='移除此修正点';remove.onclick=()=>{if(busy)return;anchors=anchors.filter(x=>x.frame!==a.frame);dirty();renderAnchors();};item.append(jump,remove);$('anchors').append(item);}
}
canvas.onclick=e=>{
    if(!info||busy)return;if(imageFrame!==frame){toast('本帧正在加载，请等画面更新后再选四角。');return;}if(points.length===4)points=[];
    const r=canvas.getBoundingClientRect();points.push([(e.clientX-r.left)/r.width*info.width,(e.clientY-r.top)/r.height*info.height]);
    enable();draw();
};
$('choose').onclick=()=>$('file').click();$('file').onchange=e=>openFile(e.target.files[0]);
for(const event of ['dragenter','dragover'])$('dropzone').addEventListener(event,e=>{e.preventDefault();$('dropzone').classList.add('dragover');});
$('dropzone').ondragleave=()=>$('dropzone').classList.remove('dragover');$('dropzone').ondrop=e=>{e.preventDefault();$('dropzone').classList.remove('dragover');openFile(e.dataTransfer.files[0]);};
$('undo-point').onclick=()=>{points.pop();enable();draw();};$('clear-points').onclick=()=>{points=[];enable();draw();};
$('add-anchor').onclick=()=>{
    anchors=anchors.filter(a=>a.frame!==frame);anchors.push({frame,quad:points.map(p=>p.slice())});anchors.sort((a,b)=>a.frame-b.frame);dirty();renderAnchors();toast('参考帧已保存。可添加修正点，或直接开始跟踪。');
};
$('timeline').oninput=e=>{playing=false;selectFrame(e.target.value);};$('frame-number').onchange=e=>{playing=false;selectFrame(e.target.value);};
$('previous').onclick=()=>selectFrame(frame-1);$('next').onclick=()=>selectFrame(frame+1);
$('play').onclick=async()=>{
    playing=!playing;$('play').textContent=playing?'停止':'逐帧播放';
    while(playing&&frame<info.frames-1){frame++;$('timeline').value=frame;$('frame-number').value=frame;$('time').textContent=(frame*info.fps_den/info.fps_num).toFixed(3)+' s';points=[];await loadFrame();await new Promise(r=>setTimeout(r,1000*info.fps_den/info.fps_num));}
    playing=false;$('play').textContent='逐帧播放';
};
$('preview').onchange=loadFrame;
for(const id of ['text','color','size','vertical','aspect'])$(id).addEventListener('input',()=>{$('vertical-value').textContent=$('vertical').value+'%';clearTimeout(drawTimer);drawTimer=setTimeout(loadFrame,300);});
$('track').onclick=async()=>{
    playing=false;try{await post('/api/track',{anchors});busy=true;track=null;enable();$('progress').hidden=false;$('cancel').hidden=false;
        const poll=async()=>{try{const s=await (await api('/api/status')).json();$('progress').value=s.progress;$('tracking-status').textContent=`正在分析 ${Math.round(s.progress*100)}%…`;
            if(s.busy){pollTimer=setTimeout(poll,350);return;}
            busy=false;$('cancel').hidden=true;
            if(s.error)throw Error(s.error);
            track=await (await api('/api/tracking')).json();$('preview').checked=true;
            $('tracking-status').textContent=`完成 · 参考帧后 ${track.tracking_lost_frames} 帧丢失。${track.tracking_lost_frames?'请跳到丢失处添加四角修正点，再重新分析。':'可逐帧检查贴合效果，再下载工程。'}`;
            selectFrame(anchors[0].frame);enable();
        }catch(e){busy=false;$('cancel').hidden=true;enable();$('tracking-status').textContent=e.message;toast(e.message);}};await poll();
    }catch(e){busy=false;enable();toast(e.message);}
};
$('cancel').onclick=()=>post('/api/cancel',{}).catch(e=>toast(e.message));
$('copy').onclick=async()=>{try{await navigator.clipboard.writeText(JSON.stringify(track));toast('跟踪数据已复制，可粘贴到 Shotcut 的本滤镜面板。');}catch(e){toast('复制失败：'+e.message);}};
$('export').onclick=async()=>{
    busy=true;playing=false;enable();$('tracking-status').textContent='正在打包工程与原视频，请稍候…';
    try{const r=await post('/api/export',{text:$('text').value,style:style()});location.href='/api/download?id='+r.id+'&token='+encodeURIComponent(token);$('tracking-status').textContent='已开始下载。解压完整目录后，用 Shotcut 打开 surface-text.mlt。';}
    catch(e){toast(e.message);}finally{busy=false;enable();}
};
if(!token)toast('请从双击启动时自动打开的地址进入，以建立本机会话。');
