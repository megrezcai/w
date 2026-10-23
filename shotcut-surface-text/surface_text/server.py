"""Local browser assistant; files stay on this machine.
Copyright (c) 2026. SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import shutil
import tempfile
import threading
import urllib.parse
import webbrowser
import zipfile
import cv2
from .tracking import video_info, read_frame, track_video
from .exporting import export_bundle, title_texture, composite_frame

ROOT = Path(__file__).resolve().parents[1]


class State:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.source = None
        self.info = None
        self.track = None
        self.busy = False
        self.progress = 0
        self.error = None
        self.cancel = threading.Event()
        self.lock = threading.Lock()
        self.exports = {}

    def snapshot(self):
        with self.lock:
            return dict(info=self.info, busy=self.busy, progress=self.progress, error=self.error,
                        tracked=self.track is not None,
                        lost_frames=self.track['tracking_lost_frames'] if self.track else None)


def handler_class(state, token):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, fmt, *args):
            pass

        def send_bytes(self, data, kind='application/json; charset=utf-8', code=200, name=None):
            # A rejected POST may have an unread request body. Never let its
            # bytes be interpreted as the next HTTP request on a keepalive socket.
            if code >= 400:
                self.close_connection = True
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if self.close_connection:
                self.send_header('Connection', 'close')
            if name:
                self.send_header('Content-Disposition', f'attachment; filename="{name}"')
            self.end_headers()
            self.wfile.write(data)

        def json(self, obj, code=200):
            self.send_bytes(json.dumps(obj, ensure_ascii=False).encode('utf-8'), code=code)

        def authorized(self):
            expected = f'127.0.0.1:{self.server.server_port}'
            origin = self.headers.get('Origin')
            if self.headers.get('Host') != expected or (origin and origin != 'http://' + expected):
                self.json(dict(error='请求来源无效。'),403); return False
            supplied = self.headers.get('X-Surface-Token','')
            url = urllib.parse.urlsplit(self.path)
            if url.path == '/api/download' and not supplied:
                supplied = urllib.parse.parse_qs(url.query).get('token',[''])[0]
            if not secrets.compare_digest(supplied, token):
                self.json(dict(error='会话令牌无效，请使用启动时打开的地址。'),403); return False
            return True

        def body(self):
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 1_000_000:
                raise ValueError('请求过大或为空。')
            return json.loads(self.rfile.read(length))

        def do_GET(self):
            url = urllib.parse.urlsplit(self.path)
            if url.path in ('/','/app.js','/style.css'):
                name = {'/':'index.html','/app.js':'app.js','/style.css':'style.css'}[url.path]
                kind = {'/':'text/html; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8'}[url.path]
                self.send_bytes((ROOT/'web'/name).read_bytes(),kind); return
            if not self.authorized(): return
            try:
                q = urllib.parse.parse_qs(url.query)
                if url.path == '/api/status':
                    self.json(state.snapshot())
                elif url.path == '/api/frame':
                    with state.lock:
                        source, info = state.source, state.info
                    if not source: raise ValueError('请先选择视频。')
                    index = int(q.get('index',['0'])[0])
                    if not 0 <= index < info['frames']: raise ValueError('帧超出范围。')
                    image = read_frame(source,index)
                    if image.shape[1] > 1280:
                        image = cv2.resize(image,(1280,round(image.shape[0]*1280/image.shape[1])))
                    ok, data = cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,90])
                    if not ok: raise ValueError('图像编码失败。')
                    self.send_bytes(data.tobytes(),'image/jpeg')
                elif url.path == '/api/tracking':
                    with state.lock: track = state.track
                    if track is None: raise ValueError('请先完成跟踪。')
                    self.json(track)
                elif url.path == '/api/download':
                    with state.lock: file = state.exports.get(q.get('id',[''])[0])
                    if file is None: raise ValueError('下载不存在，请重新生成工程。')
                    self.send_response(200)
                    self.send_header('Content-Type','application/zip')
                    self.send_header('Content-Length',str(file.stat().st_size))
                    self.send_header('Content-Disposition','attachment; filename="surface-text-project.zip"')
                    self.end_headers()
                    with file.open('rb') as stream:
                        shutil.copyfileobj(stream,self.wfile,1024*1024)
                else:
                    self.json(dict(error='接口不存在。'),404)
            except (ValueError,KeyError,TypeError,OSError) as e:
                self.json(dict(error=str(e)),400)

        def do_POST(self):
            if not self.authorized(): return
            path = urllib.parse.urlsplit(self.path).path
            try:
                if path == '/api/upload':
                    self.upload(); return
                body = self.body()
                if path == '/api/track':
                    with state.lock:
                        if state.busy: raise ValueError('当前任务尚未结束。')
                        if not state.source: raise ValueError('请先打开视频。')
                        anchors = body['anchors']
                        if not isinstance(anchors,list) or not 1 <= len(anchors) <= 100:
                            raise ValueError('参考点数量应在 1–100 之间。')
                        source = state.source
                        state.busy=True; state.error=None; state.progress=0; state.track=None; state.cancel.clear()
                    def work():
                        def progress(done,total):
                            with state.lock: state.progress=done/total
                        try:
                            result = track_video(source,anchors,progress,state.cancel.is_set)
                            with state.lock: state.track=result
                        except Exception as e:
                            with state.lock: state.error=str(e)
                        finally:
                            with state.lock: state.busy=False
                    threading.Thread(target=work,daemon=True).start()
                    self.json(dict(started=True))
                elif path == '/api/cancel':
                    state.cancel.set(); self.json(dict(cancelled=True))
                elif path == '/api/preview':
                    with state.lock: source, track = state.source, state.track
                    if track is None: raise ValueError('请先完成跟踪。')
                    index = int(body['index'])
                    if not 0 <= index < track['frames']: raise ValueError('帧超出范围。')
                    texture = title_texture(track,body['text'],**self.style(body))
                    image = composite_frame(read_frame(source,index),texture,track['frames_data'][index])
                    if image.shape[1] > 1280:
                        image = cv2.resize(image,(1280,round(image.shape[0]*1280/image.shape[1])))
                    ok, data = cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,90])
                    if not ok: raise ValueError('预览编码失败。')
                    self.send_bytes(data.tobytes(),'image/jpeg')
                elif path == '/api/export':
                    with state.lock:
                        if state.busy: raise ValueError('当前任务尚未结束。')
                        if state.track is None: raise ValueError('请先完成跟踪。')
                        track, source = state.track, state.source
                        state.busy=True
                    try:
                        ident = secrets.token_hex(12)
                        folder = state.directory / ('project-' + ident)
                        export_bundle(source,track,folder,body['text'],**self.style(body))
                        archive = folder.with_suffix('.zip')
                        # Source videos are already compressed. Store avoids a second costly encode.
                        with zipfile.ZipFile(archive,'w',zipfile.ZIP_STORED) as z:
                            for p in folder.iterdir(): z.write(p,'surface-text-project/'+p.name)
                        with state.lock: state.exports[ident]=archive
                        self.json(dict(id=ident))
                    finally:
                        with state.lock: state.busy=False
                else:
                    self.json(dict(error='接口不存在。'),404)
            except Exception as e:
                self.json(dict(error=str(e)),400)

        @staticmethod
        def style(body):
            d = body.get('style',{})
            return {k:d[k] for k in ('color','size','vertical','aspect') if k in d and d[k] is not None}

        def upload(self):
            size = int(self.headers.get('Content-Length','0'))
            if not 0 < size <= 8*1024**3:
                raise ValueError('请选择不超过 8 GB 的视频。')
            name = urllib.parse.unquote(self.headers.get('X-File-Name','video.mp4'))
            ext = Path(name).suffix.lower()
            if ext not in ('.mp4','.mov','.mkv','.avi','.m4v','.webm'):
                raise ValueError('请选择 MP4/MOV/MKV/AVI/M4V/WebM 视频。')
            with state.lock:
                if state.busy: raise ValueError('当前任务尚未结束。')
                state.busy=True
            folder = state.directory / secrets.token_hex(10)
            folder.mkdir()
            source = folder/('source'+ext)
            try:
                with source.open('wb') as f:
                    remaining=size
                    while remaining:
                        chunk=self.rfile.read(min(remaining,1024*1024))
                        if not chunk: raise ValueError('视频传输不完整。')
                        f.write(chunk); remaining-=len(chunk)
                info=video_info(source)
                info['name']=Path(name).name
                with state.lock:
                    state.source=source;state.info=info;state.track=None;state.error=None;state.progress=0
                self.json(info)
            except Exception:
                shutil.rmtree(folder,ignore_errors=True)
                raise
            finally:
                with state.lock: state.busy=False
    return Handler


def main():
    p=argparse.ArgumentParser(description='Shotcut 透视字幕本地助手')
    p.add_argument('--no-browser',action='store_true')
    p.add_argument('--port',type=int,default=0)
    args=p.parse_args()
    token=secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix='shotcut-surface-text-') as directory:
        state=State(directory)
        server=ThreadingHTTPServer(('127.0.0.1',args.port),handler_class(state,token))
        address=f'http://127.0.0.1:{server.server_port}/#{token}'
        print('Shotcut 透视字幕助手：'+address,flush=True)
        print('请保留此窗口；关闭后本次临时文件会删除。请先下载生成的工程。',flush=True)
        if not args.no_browser: webbrowser.open(address)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally:
            state.cancel.set(); server.server_close()


if __name__ == '__main__':
    main()
