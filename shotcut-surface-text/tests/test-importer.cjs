// Copyright (c) 2026. SPDX-License-Identifier: GPL-3.0-or-later
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'..'),context={};vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root,'shotcut-filter/Track.js'),'utf8').replace(/^\.pragma library\s*/,''),context);
const fixture=JSON.parse(fs.readFileSync(path.join(__dirname,'generated-fixture.json'),'utf8')),t=fixture.track;
const run=x=>context.build(JSON.stringify(x),t.width,t.height,t.fps_num/t.fps_den,t.frames);
const actual=run(t);for(let i=0;i<9;i++)assert.equal(actual[i],fixture.animations[String(i)]);
assert.throws(()=>context.build(JSON.stringify(t),t.width,t.height,25,t.frames),/帧率/);
assert.throws(()=>context.build(JSON.stringify(t),t.width,t.height,24,t.frames-1),/长度/);
const broken=JSON.parse(JSON.stringify(t));broken.frames_data[4].quad=[[0,0],[640,360],[640,0],[0,360]];
assert.throws(()=>run(broken),/四角/);
console.log('QML importer: all 9 animations match Python; invalid FPS, duration and folded corners rejected.');
