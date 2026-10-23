"""Portable Shotcut projects, title textures, and projective previews.
Copyright (c) 2026. SPDX-License-Identifier: GPL-3.0-or-later
"""
from pathlib import Path
import json
import math
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .tracking import validate_quad


def font_path():
    candidates = [Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/msyh.ttc',
                  Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/simhei.ttf',
                  Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),
                  Path('/System/Library/Fonts/PingFang.ttc')]
    for p in candidates:
        if p.exists():
            return str(p)
    raise ValueError("未找到中文字体，请通过 --font 指定可用的 TTF/TTC/OTF 字体。")


def title_texture(track, text, color='#202020', size=.18, vertical=.65, aspect=None, font=None):
    if not text.strip() or len(text) > 2000:
        raise ValueError("字幕不能为空，最多 2000 个字符。")
    if not .03 <= float(size) <= .6 or not 0 <= float(vertical) <= 1:
        raise ValueError("字号或垂直位置超出允许范围。")
    q = np.float32(track['anchors'][0]['quad'])
    if aspect is None:
        aspect = (np.linalg.norm(q[1]-q[0]) + np.linalg.norm(q[2]-q[3])) / (np.linalg.norm(q[3]-q[0]) + np.linalg.norm(q[2]-q[1]))
    if not .2 <= float(aspect) <= 12:
        raise ValueError("表面宽高比必须在 0.2 到 12 之间。")
    # Render at 2x the conceptual plane resolution before stretching to profile.
    pw, ph = 1600, max(160, round(1600 / float(aspect)))
    image = Image.new('RGBA', (pw, ph), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    fp = font or font_path()
    font_size = max(8, round(ph * float(size)))
    while True:
        ft = ImageFont.truetype(fp, font_size)
        box = draw.multiline_textbbox((0, 0), text, font=ft, spacing=round(font_size*.2), align='center')
        tw, th = box[2]-box[0], box[3]-box[1]
        if (tw <= pw*.88 and th <= ph*.88) or font_size <= 8:
            break
        font_size -= 2
    x = (pw-tw)/2 - box[0]
    y = min(max(ph*float(vertical)-th/2, ph*.04), ph*.96-th) - box[1]
    draw.multiline_text((x, y), text, font=ft, fill=color, spacing=round(font_size*.2), align='center')
    return image.resize((track['width'], track['height']), Image.Resampling.LANCZOS)


def validate_track(t):
    if t.get('schema') != 'shotcut-surface-text/v1':
        raise ValueError('跟踪数据格式不支持。')
    w, h, n = t['width'], t['height'], t['frames']
    if not all(isinstance(x, int) for x in (w, h, n)) or not 2 <= w <= 16384 or not 2 <= h <= 16384 or not 1 <= n <= 2_000_000:
        raise ValueError('非法视频尺寸或帧数。')
    if len(t['frames_data']) != n or t['fps_den'] <= 0 or not 1 <= t['fps_num']/t['fps_den'] <= 240:
        raise ValueError('帧数或帧率不匹配。')
    for i, row in enumerate(t['frames_data']):
        if row['frame'] != i or not isinstance(row['valid'], bool):
            raise ValueError('帧编号必须连续，valid 必须为布尔值。')
        if row['valid']:
            validate_quad(row['quad'], w, h)


def animations(track):
    validate_track(track)
    dimensions = (track['width']-1, track['height']-1)
    params = {str(i): [] for i in range(9)}
    last_q = [[0, 0], [dimensions[0], 0], list(dimensions), [0, dimensions[1]]]
    for row in track['frames_data']:
        f = row['frame']
        if row['valid']:
            last_q = row['quad']
        for i, point in enumerate(last_q):
            for j, value in enumerate(point):
                params[str(i*2+j)].append(f'{f}={((value/dimensions[j])+1)/3:.10f}')
        # Discrete visibility prevents a lost interval from fading across frames.
        params['8'].append(f'{f}|={1 if row["valid"] else 0}')
    return {name: ';'.join(values) for name, values in params.items()}


def write_mlt(folder, track, source_name):
    """Relative resources: the XML producer resolves these against the MLT file."""
    n, w, h = track['frames'], track['width'], track['height']
    root = ET.Element('mlt', {'LC_NUMERIC':'C', 'version':'7.24.0', 'producer':'tractor'})
    ET.SubElement(root, 'profile', dict(description='Surface Text', width=str(w), height=str(h),
        frame_rate_num=str(track['fps_num']), frame_rate_den=str(track['fps_den']), progressive='1',
        sample_aspect_num='1', sample_aspect_den='1', display_aspect_num=str(w//math.gcd(w,h)),
        display_aspect_den=str(h//math.gcd(w,h)), colorspace='709'))
    def prop(node, name, value):
        ET.SubElement(node, 'property', name=name).text = str(value)
    black = ET.SubElement(root, 'producer', id='black', **{'in':'0', 'out':str(n-1)})
    prop(black, 'mlt_service', 'color'); prop(black, 'resource', '0'); prop(black, 'length', n)
    source = ET.SubElement(root, 'chain', id='source', **{'in':'0', 'out':str(n-1)})
    prop(source, 'mlt_service', 'avformat'); prop(source, 'resource', source_name)
    prop(source, 'shotcut:producer', 1)
    title = ET.SubElement(root, 'producer', id='title', **{'in':'0', 'out':str(n-1)})
    prop(title, 'mlt_service', 'qimage'); prop(title, 'resource', 'title.png')
    prop(title, 'length', n); prop(title, 'eof', 'loop'); prop(title, 'ttl', n)
    prop(title, 'shotcut:producer', 1)
    filt = ET.SubElement(title, 'filter', **{'in':'0', 'out':str(n-1)})
    prop(filt, 'mlt_service', 'frei0r.surfacepin'); prop(filt, 'shotcut:filter', 'surface_text')
    for name, value in animations(track).items():
        prop(filt, name, value)
    for name, producer in [('background','black'),('video','source'),('subtitles','title')]:
        pl = ET.SubElement(root, 'playlist', id=name)
        if name != 'background':
            prop(pl, 'shotcut:name', 'V1 · 原视频' if name=='video' else 'V2 · 透视字幕')
            prop(pl, 'shotcut:video', 1)
        ET.SubElement(pl, 'entry', producer=producer, **{'in':'0','out':str(n-1)})
    tractor = ET.SubElement(root, 'tractor', id='tractor', **{'in':'0','out':str(n-1),'shotcut':'1'})
    prop(tractor, 'shotcut', 1)
    prop(tractor, 'shotcut:name', 'Timeline')
    for name in ('background','video','subtitles'):
        ET.SubElement(tractor, 'track', producer=name)
    mix = ET.SubElement(tractor, 'transition', **{'in':'0','out':str(n-1)})
    for k,v in [('mlt_service','mix'),('a_track',0),('b_track',1),('always_active',1),('sum',1)]: prop(mix,k,v)
    for b in (1,2):
        blend = ET.SubElement(tractor, 'transition', **{'in':'0','out':str(n-1)})
        # Shotcut disables the bottom video's blend on load. The title must
        # composite against V1 itself, not against the background track.
        for k,v in [('mlt_service','qtblend'),('a_track',0 if b==1 else 1),('b_track',b),('compositing',0),('disable',1 if b==1 else 0)]: prop(blend,k,v)
    ET.indent(root, space='  ')
    ET.ElementTree(root).write(Path(folder)/'surface-text.mlt', encoding='utf-8', xml_declaration=True)


def export_bundle(source, track, destination, text, **style):
    validate_track(track)
    folder = Path(destination)
    if folder.exists() and any(folder.iterdir()):
        raise ValueError('输出目录不是空目录，请选择新的目录以保留已有文件。')
    folder.mkdir(parents=True, exist_ok=True)
    source_name = 'source' + (Path(source).suffix.lower() or '.mp4')
    title = title_texture(track, text, **style)
    title.save(folder / 'title.png')
    shutil.copy2(source, folder / source_name)
    (folder / 'tracking.json').write_text(json.dumps(track, ensure_ascii=False), encoding='utf-8')
    (folder / 'subtitle.txt').write_text(text, encoding='utf-8')
    write_mlt(folder, track, source_name)
    (folder / '先看这里.txt').write_text('先安装 SurfacePin 插件，再用 Shotcut 打开 surface-text.mlt。\nV1 是原视频，V2 是带逐帧透视的独立透明字幕。原声保留。\n请保留整个目录，或在 Shotcut 另存项目时一并保留素材。\ntracking.json 可用于重新导入；subtitle.txt 记录字幕内容。\n字幕为栅格图层，改文字需在助手中重生成；四角关键帧可在滤镜中编辑。\n', encoding='utf-8-sig')
    return folder


def composite_frame(frame, rgba, row):
    if not row['valid']:
        return frame.copy()
    h, w = frame.shape[:2]
    src = np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
    H = cv2.getPerspectiveTransform(src, np.float32(row['quad']))
    image = np.asarray(rgba).astype(np.float32)/255.
    image[:,:,:3] *= image[:,:,3:4]
    warped = cv2.warpPerspective(image, H, (w,h), flags=cv2.INTER_LINEAR)
    out = warped[:,:,:3][:,:,::-1]*255 + frame.astype(np.float32)*(1-warped[:,:,3:4])
    return np.uint8(np.clip(np.rint(out), 0, 255))


def render_preview(source, track, rgba, output):
    """Optional CLI preview; requires FFmpeg, not required by the Windows GUI."""
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise ValueError('预览视频导出需要 FFmpeg；Shotcut 工程导出不需要它。')
    args = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-n', '-f','rawvideo','-pix_fmt','bgr24',
            '-s',f'{track["width"]}x{track["height"]}', '-r',f'{track["fps_num"]}/{track["fps_den"]}',
            '-i','-', '-i',str(source), '-map','0:v','-map','1:a?', '-c:v','libx264', '-preset','fast',
            '-crf','19','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(output)]
    p = subprocess.Popen(args, stdin=subprocess.PIPE)
    cap = cv2.VideoCapture(str(source))
    try:
        for row in track['frames_data']:
            ok, frame = cap.read()
            if not ok: raise ValueError('预览解码失败。')
            p.stdin.write(composite_frame(frame, rgba, row).tobytes())
        p.stdin.close()
        if p.wait() != 0: raise ValueError('FFmpeg 预览编码失败。')
    finally:
        cap.release()
        if p.poll() is None:
            p.terminate(); p.wait()
