"""Local-only Ollama client. No cloud fallback, credentials, or external libraries."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

class ModelError(RuntimeError):
    pass

class Ollama:
    def __init__(self, base='http://127.0.0.1:11434', model='caseforge-npc', timeout=180):
        url = urllib.parse.urlparse(base)
        if url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost', '::1') or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
            raise ValueError('模型地址仅支持本机 HTTP，如 http://127.0.0.1:11434')
        self.base, self.model, self.timeout = base.rstrip('/'), model, timeout
        # Explicit loopback bypass: local requests must not be routed to an HTTP proxy.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _request(self, path, data=None):
        req = urllib.request.Request(self.base + path, data=None if data is None else json.dumps(data, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json'})
        try:
            with self.opener.open(req, timeout=self.timeout) as r:
                return json.load(r)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            if isinstance(exc, urllib.error.HTTPError):
                detail = exc.read(1000).decode('utf-8', 'replace')
            else:
                detail = str(exc)
            raise ModelError(f'Ollama 请求失败：{detail}。请启动 Ollama 并运行 python setup_model.py。') from exc

    def status(self):
        result = self._request('/api/tags')
        names = [m['name'] for m in result.get('models', [])]
        return {'models': names, 'model': self.model, 'ready': any(n == self.model or n == self.model + ':latest' for n in names)}

    def complete(self, system, payload, schema, *, temperature=0.2, tokens=768, context=8192):
        data = self._request('/api/chat', {
            'model': self.model, 'stream': False, 'think': False, 'keep_alive': '10m',
            'messages': [{'role': 'system', 'content': system + '\n只输出符合格式的 JSON。/no_think'},
                         {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}],
            'format': schema,
            'options': {'temperature': temperature, 'num_ctx': context, 'num_predict': tokens},
        })
        content = data.get('message', {}).get('content', '')
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.S).strip()
        try:
            value = json.loads(content)
            if not isinstance(value, dict):
                raise ValueError('输出不是对象')
            return value
        except ValueError as exc:
            raise ModelError('模型未生成完整 JSON；可换更大模型或缩短输入。') from exc
