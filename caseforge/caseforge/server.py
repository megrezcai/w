"""Loopback authoring console and game API; SQLite saves chapter snapshots per session."""
import copy
from contextlib import closing
import json
import secrets
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from .engine import Engine
from .schema import load, validate
from .llm import Ollama, ModelError
from .importer import compile_chapter

class App:
    def __init__(self, resources, data_dir, *, demo=False, strict=False, model='caseforge-npc', base='http://127.0.0.1:11434'):
        self.resources, self.data_dir = Path(resources), Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / 'chapters').mkdir(exist_ok=True)
        self.db = self.data_dir / 'sessions.sqlite3'
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, chapter TEXT NOT NULL, state TEXT NOT NULL, debug TEXT NOT NULL)')
        self.demo, self.strict, self.model_name, self.base = demo, strict, model, base
        self.token = secrets.token_urlsafe(32)
        self.locks, self.lock = {}, threading.Lock()

    def session_lock(self, sid):
        with self.lock:
            return self.locks.setdefault(sid, threading.RLock())

    def model(self):
        return None if self.demo else Ollama(self.base, self.model_name)

    def chapters(self):
        result = {}
        for folder in [self.resources / 'chapters', self.data_dir / 'chapters']:
            for file in folder.glob('*.json'):
                if file.name.endswith('.schema.json'):
                    continue
                try:
                    c = load(file)
                    result[c['id']] = c
                except (ValueError, OSError):
                    continue
        return result

    def read(self, sid):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            row = conn.execute('SELECT chapter,state,debug FROM sessions WHERE id=?', (sid,)).fetchone()
        if row is None:
            raise KeyError('会话不存在')
        return tuple(json.loads(x) for x in row)

    def write(self, sid, chapter, state, debug):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute('INSERT OR REPLACE INTO sessions VALUES (?,?,?,?)', (sid, *[json.dumps(x, ensure_ascii=False) for x in [chapter, state, debug]]))

    def view(self, chapter, state):
        c = next(c for c in chapter['characters'] if c['id'] == state['character_id'])
        return {'chapter': chapter['title'], 'character': c['name'], 'turn': state['turn'], 'history': state['history'],
                'facts': [{'id': s['id'], 'text': s['truth']} for s in c['secrets'] if s['id'] in state['disclosed']],
                'inventory': [e for e in chapter['evidence'] if e['id'] in state['inventory']],
                'offers': [{'id': o['id'], 'title': o['title'], 'description': o['description']} for o in chapter['offers'] if o['id'] in state['available_offers']],
                'committed': state['committed'], 'fulfilled': state['fulfilled'], 'broken': state['broken']}

    def api(self, method, path, body):
        if method == 'GET' and path == '/api/status':
            try:
                status = Ollama(self.base, self.model_name, timeout=3).status()
            except ModelError as exc:
                status = {'ready': False, 'models': [], 'error': str(exc)}
            return dict(status, backend='demo' if self.demo else 'ollama', strict=self.strict, selected_model=self.model_name)
        if method == 'POST' and path == '/api/config':
            if body.get('backend') not in ('demo', 'ollama') or type(body.get('strict')) is not bool:
                raise ValueError('连接设置无效')
            model = body.get('model', 'caseforge-npc')
            if not isinstance(model, str) or not 1 <= len(model) <= 100:
                raise ValueError('模型名称无效')
            self.demo, self.strict, self.model_name = body['backend'] == 'demo', body['strict'], model
            return {'ok': True}
        if method == 'GET' and path == '/api/chapters':
            return [{'id': c['id'], 'title': c['title'], 'public_brief': c['public_brief'], 'characters': [{'id': x['id'], 'name': x['name']} for x in c['characters']]} for c in self.chapters().values()]
        if method == 'POST' and path == '/api/compile':
            return compile_chapter(self.model(), body.get('text', ''))
        if method == 'POST' and path == '/api/chapters':
            chapter = validate(body.get('chapter'))
            file = self.data_dir / 'chapters' / (chapter['id'] + '.json')
            temp = file.with_suffix('.tmp')
            with self.lock:
                temp.write_text(json.dumps(chapter, ensure_ascii=False, indent=2), encoding='utf-8')
                temp.replace(file)
            return {'ok': True, 'id': chapter['id']}
        if method == 'POST' and path == '/api/sessions':
            chapters = self.chapters()
            chapter = chapters.get(body.get('chapter_id'))
            if chapter is None:
                raise ValueError('章节不存在')
            engine = Engine(chapter, self.model(), self.strict)
            state = engine.new_session(body.get('character_id'), body.get('inventory'), body.get('available_offers'))
            sid = secrets.token_hex(16)
            self.write(sid, chapter, state, {})
            return {'session_id': sid, **self.view(chapter, state)}
        # /api/sessions/{id}, /turn, /world, /debug, /export
        parts = path.strip('/').split('/')
        if len(parts) in (3, 4) and parts[:2] == ['api', 'sessions']:
            sid = parts[2]
            if len(sid) != 32 or any(c not in '0123456789abcdef' for c in sid):
                raise ValueError('会话 ID 无效')
            with self.session_lock(sid):
                chapter, state, debug = self.read(sid)
                engine = Engine(chapter, self.model(), self.strict)
                action = parts[3] if len(parts) == 4 else ''
                if method == 'GET' and not action:
                    return {'session_id': sid, **self.view(chapter, state)}
                if method == 'GET' and action == 'debug':
                    return debug
                if method == 'GET' and action == 'export':
                    # Player transcript intentionally omits undisclosed chapter truth.
                    return {'session_id': sid, **self.view(chapter, state)}
                if method == 'POST' and action == 'turn':
                    new, reply, debug = engine.turn(state, body.get('text'), body.get('evidence_ids'), body.get('offer_ids'))
                    self.write(sid, chapter, new, debug)
                    return dict(reply, state=self.view(chapter, new))
                if method == 'POST' and action == 'world':
                    new = engine.world_event(state, acquired=body.get('acquired'), unlocked_offers=body.get('unlocked_offers'), fulfilled=body.get('fulfilled'), broken=body.get('broken'))
                    self.write(sid, chapter, new, debug)
                    return self.view(chapter, new)
        raise KeyError('接口不存在')


def make_server(app, host='127.0.0.1', port=8765):
    if host not in ('127.0.0.1', 'localhost'):
        raise ValueError('此开发控制台仅允许监听本机')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # Never log player messages.

        def send(self, status, data, mime='application/json; charset=utf-8'):
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def handle_request(self):
            path = urlparse(self.path).path
            # Reject remote sites and DNS rebinding before exposing author/game APIs.
            expected = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            if self.headers.get('Host') not in expected:
                return self.send(403, {'error': '只允许本机访问'})
            try:
                if self.command == 'GET' and path in ('/', '/app.js', '/style.css'):
                    name = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}[path]
                    data = (app.resources / 'caseforge' / 'web' / name).read_bytes()
                    if path == '/':
                        data = data.replace(b'__TOKEN__', app.token.encode())
                    return self.send(200, data, {'/':'text/html; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8'}[path])
                if self.headers.get('X-Caseforge-Token') != app.token:
                    return self.send(403, {'error': '请从本机控制台取得访问令牌，参见 docs/API.md'})
                body = {}
                if self.command == 'POST':
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 1_000_000:
                        raise ValueError('请求为空或超过 1MB')
                    body = json.loads(self.rfile.read(length))
                    if not isinstance(body, dict):
                        raise ValueError('请求需要 JSON 对象')
                return self.send(200, app.api(self.command, path, body))
            except KeyError as exc:
                return self.send(404, {'error': str(exc)})
            except (ValueError, TypeError, ModelError) as exc:
                return self.send(400, {'error': str(exc)})
            except Exception:
                return self.send(500, {'error': '内部错误，请检查章节或备份 data 目录后重试。'})

        do_GET = handle_request
        do_POST = handle_request
    return ThreadingHTTPServer((host, port), Handler)
