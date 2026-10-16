const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('companion', Object.fromEntries(['state','settings','chat','memory','clear','export'].map(channel=>[channel,(input)=>ipcRenderer.invoke(channel,input)])));
