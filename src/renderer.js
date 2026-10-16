const api = window.companion;
const $ = s => document.querySelector(s);
let state, pending=false, noticeTimer;
function notify(text){$('#notice').textContent=text;$('#notice').hidden=false;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>$('#notice').hidden=true,6500);}
function element(tag,text,cls){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;}
function render(){
  $('#name').textContent=state.settings.name;
  $('#mode').textContent=state.hasKey?'API 已配置':'演示模式 · 未连接模型';
  const log=$('#messages');log.replaceChildren();
  if(!state.messages.length)log.append(element('div','从一句「你好」开始，慢慢认识彼此。','empty'));
  for(const message of state.messages){const row=element('div',undefined,'message '+message.role);row.append(element('small',message.role==='user'?'你':state.settings.name),element('div',message.content,'bubble'));if(message.role==='user'){const b=element('button','♡ 收藏到记忆','remember');b.onclick=()=>run(async()=>{state=await api.memory({action:'add',text:message.content.slice(0,1000)});render();notify('已收藏到记忆');});row.append(b);}log.append(row);}
  log.scrollTop=log.scrollHeight;
  const memories=$('#memories');memories.replaceChildren();if(!state.memories.length)memories.append(element('p','还没有记忆，收藏一件关于你的小事吧。','empty'));
  for(const memory of state.memories){const card=element('div',undefined,'memory-card');card.append(element('span',memory.text));const del=element('button','删除');del.onclick=()=>run(async()=>{state=await api.memory({action:'delete',id:memory.id});render();});card.append(del);memories.append(card);}
}
async function run(fn){try{await fn();}catch(error){notify(error.message.replace(/^Error invoking remote method '[^']+': (Error: )?/,''));}}
function formFill(){const f=$('#settings-form');for(const [key,value]of Object.entries(state.settings)){if(f.elements[key]){if(typeof value==='boolean')f.elements[key].checked=value;else f.elements[key].value=value;}}f.elements.apiKey.value='';f.elements.clearKey.checked=false;$('#key-status').textContent=state.hasKey?'密钥已使用系统安全存储加密保存。':'未保存密钥，当前为演示模式。';}
for(const tab of document.querySelectorAll('[data-tab]'))tab.onclick=()=>{for(const p of document.querySelectorAll('.page'))p.hidden=p.id!==tab.dataset.tab;for(const b of document.querySelectorAll('[data-tab]'))b.classList.toggle('active',b===tab);$('#heading').textContent=tab.textContent.trim().slice(1).trim();if(tab.dataset.tab==='settings')formFill();};
async function send(text){if(pending||!text.trim())return;pending=true;$('#send').disabled=true;$('#typing').textContent=state.settings.name+'正在想怎么回应你…';$('#typing').hidden=false;try{state=await api.chat(text);$('#message').value='';render();if(state.settings.voice&&'speechSynthesis'in window){speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(state.messages.at(-1).content);u.lang='zh-CN';speechSynthesis.speak(u);}}catch(e){notify(e.message);}finally{pending=false;$('#send').disabled=false;$('#typing').hidden=true;}}
$('#chat-form').onsubmit=e=>{e.preventDefault();send($('#message').value);};
$('#message').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();send($('#message').value);}};
for(const b of document.querySelectorAll('[data-action]'))b.onclick=()=>send(b.dataset.action);
$('#settings-form').onsubmit=e=>{e.preventDefault();run(async()=>{const f=e.target;const data=Object.fromEntries(new FormData(f));data.voice=f.elements.voice.checked;data.clearKey=f.elements.clearKey.checked;state=await api.settings(data);formFill();render();notify('设置已保存');});};
$('#memory-form').onsubmit=e=>{e.preventDefault();run(async()=>{state=await api.memory({action:'add',text:$('#memory-text').value});$('#memory-text').value='';render();});};
$('#clear').onclick=()=>{if(confirm('清空全部聊天记录？收藏的记忆会保留。'))run(async()=>{state=await api.clear();render();});};
$('#export').onclick=()=>run(async()=>{if(await api.export())notify('对话和记忆已导出（不包含密钥）');});
run(async()=>{state=await api.state();render();formFill();});
