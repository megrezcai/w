const {test}=require('node:test');
const assert=require('node:assert/strict');
const {DEFAULTS,context,endpointURL,reply}=require('../src/core.cjs');
const state=()=>({settings:{...DEFAULTS},memories:[{text:'喜欢热可可'}],messages:[]});
test('上下文包含角色、主动记忆及最近40条消息',()=>{const s=state();s.messages=Array.from({length:50},(_,i)=>({role:i%2?'assistant':'user',content:String(i)}));const c=context(s,'你好');assert.equal(c.length,42);assert.match(c[0].content,/喜欢热可可/);assert.equal(c[1].content,'10');assert.equal(c.at(-1).content,'你好');});
test('无密钥明确使用演示模式，不访问网络',async()=>{const text=await reply(state(),'抱抱','',()=>{throw Error('不应请求');});assert.match(text,/演示模式/);assert.match(text,/拥抱/);});
test('兼容API发送认证和上下文并解析回复',async()=>{let called=false;const result=await reply(state(),'你好','test-key',async(url,opts)=>{called=true;assert.equal(url,'https://api.openai.com/v1/chat/completions');assert.equal(opts.headers.Authorization,'Bearer test-key');assert.equal(opts.redirect,'error');const body=JSON.parse(opts.body);assert.equal(body.model,'gpt-4o-mini');assert.equal(body.messages.at(-1).content,'你好');return {ok:true,json:async()=>({choices:[{message:{content:'你好呀'}}]})};});assert.ok(called);assert.equal(result,'你好呀');});
test('接口错误与空回复不能伪装为成功',async()=>{await assert.rejects(reply(state(),'a','key',async()=>({ok:false,status:401})),/401/);await assert.rejects(reply(state(),'a','key',async()=>({ok:true,json:async()=>({choices:[]})})),/未返回文字/);});
test('接口限制HTTPS，支持本机开发，拒绝嵌入凭据',()=>{assert.throws(()=>endpointURL('http://example.com/v1'),/HTTPS/);assert.throws(()=>endpointURL('https://user:pass@example.com/v1'),/用户名/);assert.equal(endpointURL('http://localhost:1234/v1/'),'http://localhost:1234/v1/chat/completions');});
