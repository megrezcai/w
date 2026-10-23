.pragma library
// Copyright (c) 2026. SPDX-License-Identifier: GPL-3.0-or-later
function build(text, width, height, fps, duration) {
    var t = JSON.parse(text);
    if (t.schema !== 'shotcut-surface-text/v1') throw Error('不是本工具的跟踪数据。');
    if (t.width !== width || t.height !== height) throw Error('项目分辨率与跟踪视频不一致。');
    if (!(t.fps_den > 0) || Math.abs(t.fps_num / t.fps_den - fps) > 0.0001) throw Error('项目帧率与跟踪视频不一致。');
    if (!Number.isInteger(t.frames) || t.frames < 1 || t.frames > 2000000 || t.frames !== duration || !Array.isArray(t.frames_data) || t.frames_data.length !== t.frames)
        throw Error('字幕片段长度须与完整跟踪视频一致，请使用助手生成的工程。');
    var params = [], last = [[0,0],[width-1,0],[width-1,height-1],[0,height-1]];
    for (var j=0; j<9; j++) params.push([]);
    for (var f=0; f<t.frames; f++) {
        var row = t.frames_data[f];
        if (row.frame !== f || typeof row.valid !== 'boolean') throw Error('帧序列损坏。');
        if (row.valid) {
            var q = row.quad;
            if (!Array.isArray(q) || q.length !== 4) throw Error('四角数据损坏。');
            for (j=0; j<4; j++) {
                if (!Array.isArray(q[j]) || q[j].length !== 2) throw Error('四角坐标损坏。');
                for (var k=0; k<2; k++) {
                    var v=q[j][k], dim=k ? height-1 : width-1;
                    if (typeof v !== 'number' || !isFinite(v) || v < -dim || v > 2*dim) throw Error('坐标无效或过远地离开画面。');
                }
            }
            var area=0;
            for (j=0; j<4; j++) {
                var a=q[j], b=q[(j+1)%4], c=q[(j+2)%4];
                if ((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]) <= 2) throw Error('四角折叠或顺序错误。');
                area += a[0]*b[1]-b[0]*a[1];
            }
            if (area/2 < 100) throw Error('四角面积过小。');
            last=q;
        }
        for (j=0; j<4; j++) for (k=0; k<2; k++) {
            var value=(last[j][k]/(k ? height-1 : width-1)+1)/3;
            params[j*2+k].push(f+'='+value.toFixed(10));
        }
        params[8].push(f+'|='+(row.valid ? 1 : 0));
    }
    return params.map(function(p){return p.join(';');});
}
