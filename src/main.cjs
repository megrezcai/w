const { app, BrowserWindow, ipcMain, safeStorage, dialog } = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const { DEFAULTS, reply, endpointURL } = require('./core.cjs');
let state, file, busy = false;
function save() { const tmp = file + '.tmp'; fs.writeFileSync(tmp, JSON.stringify(state), {mode:0o600}); fs.renameSync(tmp,file); }
function view() { return { settings:state.settings, messages:state.messages, memories:state.memories, hasKey:!!state.key, busy }; }
function keyValue() { return state.key ? safeStorage.decryptString(Buffer.from(state.key,'base64')) : ''; }
function short(value, max) { if (typeof value !== 'string' || value.length > max) throw Error('输入格式或长度不正确。'); return value.trim(); }
app.whenReady().then(() => {
  file = path.join(app.getPath('userData'),'companion.json');
  state = { settings:{...DEFAULTS}, messages:[], memories:[], key:'' };
  if (fs.existsSync(file)) { try { const old = JSON.parse(fs.readFileSync(file,'utf8')); state = {...state,...old, settings:{...DEFAULTS,...old.settings}}; } catch { dialog.showErrorBox('无法读取本地数据','数据文件损坏，已停止启动以保护原文件。'); app.quit(); return; } }
  ipcMain.handle('state', () => view());
  ipcMain.handle('settings', (_, input) => {
    if (busy) throw Error('请等待当前回复完成。');
    const settings = {name:short(input.name,40), persona:short(input.persona,6000), endpoint:short(input.endpoint,500), model:short(input.model,120), voice:!!input.voice};
    if (!settings.name || !settings.persona || !settings.model) throw Error('请填写名字、人设和模型。');
    endpointURL(settings.endpoint);
    let encrypted = state.key;
    if (input.apiKey) { if (!safeStorage.isEncryptionAvailable()) throw Error('系统安全存储不可用，无法保存密钥。'); encrypted = safeStorage.encryptString(short(input.apiKey,4096)).toString('base64'); }
    if (input.clearKey) encrypted = '';
    state.settings = settings; state.key = encrypted; save(); return view();
  });
  ipcMain.handle('chat', async (_, raw) => {
    if (busy) throw Error('正在回复中。');
    const text = short(raw,8000); if (!text) throw Error('请输入消息。'); busy = true;
    try { const content = await reply(state,text,keyValue()); const now = Date.now(); state.messages.push({role:'user', content:text, time:now},{role:'assistant',content,time:Date.now()}); save(); return view(); } finally { busy = false; }
  });
  ipcMain.handle('memory', (_, input) => {
    if (busy) throw Error('请等待回复完成。');
    if (input.action === 'add') { const text = short(input.text,1000); if (!text) throw Error('记忆不能为空。'); if(state.memories.length >= 100) throw Error('最多保存 100 条记忆。'); state.memories.push({id:require('node:crypto').randomUUID(),text}); }
    else if(input.action === 'delete') state.memories = state.memories.filter(m=>m.id !== input.id);
    else throw Error('未知操作。');
    save(); return view();
  });
  ipcMain.handle('clear', () => { if(busy) throw Error('请等待回复完成。'); state.messages=[]; save(); return view(); });
  ipcMain.handle('export', async () => { const result = await dialog.showSaveDialog({defaultPath:'星伴-对话.json',filters:[{name:'JSON',extensions:['json']}]}); if(!result.canceled) fs.writeFileSync(result.filePath,JSON.stringify({messages:state.messages,memories:state.memories},null,2)); return !result.canceled; });
  const win = new BrowserWindow({width:1180,height:820,minWidth:860,minHeight:640,backgroundColor:'#f7f4f0',title:'星伴',webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true}});
  win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  win.webContents.on('will-navigate',e=>e.preventDefault());
  win.loadFile(path.join(__dirname,'index.html'));
});
app.on('window-all-closed',()=>app.quit());
