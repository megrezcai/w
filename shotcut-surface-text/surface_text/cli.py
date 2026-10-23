"""Copyright (c) 2026. SPDX-License-Identifier: GPL-3.0-or-later"""
import argparse
import json
from pathlib import Path
from .tracking import track_video
from .exporting import export_bundle, render_preview, title_texture


def main():
    p = argparse.ArgumentParser(description='Shotcut 四角透视字幕与平面跟踪')
    p.add_argument('video')
    p.add_argument('--anchors', help='JSON: [{"frame":24,"quad":[[x,y],...]}]')
    p.add_argument('--track', help='复用已有 tracking.json')
    p.add_argument('--text', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--preview', help='可选 MP4 路径，需要系统 FFmpeg')
    p.add_argument('--font')
    p.add_argument('--color', default='#202020')
    p.add_argument('--size', type=float, default=.18)
    p.add_argument('--vertical', type=float, default=.65)
    p.add_argument('--aspect', type=float)
    a = p.parse_args()
    if a.track:
        track = json.loads(Path(a.track).read_text(encoding='utf-8'))
    elif a.anchors:
        anchors = json.loads(Path(a.anchors).read_text(encoding='utf-8'))
        track = track_video(a.video, anchors, progress=lambda done,total: print(f'\r{done}/{total}',end='',flush=True))
    else:
        p.error('--anchors 或 --track 必须提供一个')
    style = dict(font=a.font, color=a.color, size=a.size, vertical=a.vertical, aspect=a.aspect)
    folder = export_bundle(a.video, track, a.output, a.text, **style)
    if a.preview:
        render_preview(a.video, track, title_texture(track,a.text,**style), a.preview)
    print(f'\n工程已生成：{folder.resolve()}；参考帧后丢失 {track["tracking_lost_frames"]} 帧。')


if __name__ == '__main__':
    main()
