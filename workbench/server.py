"""Local browser adapter for the same services used by the Tk application."""
import argparse
import json
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from package.service.formula_generation_service import analyze, validate_input, FormulaGenerator, SearchCancelled


class WorkbenchServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address=('127.0.0.1', 8866)):
        if address[0] != '127.0.0.1':
            raise ValueError('Workbench only binds to 127.0.0.1')
        super().__init__(address, Handler)
        self.token = secrets.token_urlsafe(32)
        self.jobs = {}
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.origin = f'http://127.0.0.1:{self.server_port}'
        self.assets = Path(__file__).resolve().parent

    def submit(self, kind, payload):
        if kind == 'analyze':
            payload = validate_input(payload)
        elif kind == 'search':
            import re
            formula = payload.get('formula', '') if isinstance(payload, dict) else ''
            if not isinstance(formula, str) or len(formula) > 100 or not re.fullmatch(r'(?:[A-Z][a-z]?\d*)+', formula):
                raise ValueError('请输入一个简单中性分子式，如 C2H6O')
            tokens = re.findall(r'([A-Z][a-z]?)(\d*)', formula)
            if any(e not in FormulaGenerator().atomic_weights or (n and (int(n) == 0 or int(n) > 1000)) for e, n in tokens):
                raise ValueError('分子式包含未知元素或无效计数')
            payload = {'formula': formula, 'ion_mode': payload.get('ion_mode', 'both')}
            if payload['ion_mode'] not in ('both', 'positive', 'negative'):
                raise ValueError('无效检索离子模式')
        else:
            raise ValueError('未知任务')
        with self.lock:
            if any(j['status'] == 'running' and j['kind'] == kind for j in self.jobs.values()):
                raise ValueError('同类任务正在运行，请等待或取消')
            completed = [key for key, j in self.jobs.items() if j['status'] != 'running']
            for key in completed[:-6]:
                self.jobs.pop(key)
            job_id = secrets.token_hex(12)
            job = {'id': job_id, 'kind': kind, 'status': 'running', 'cancel': threading.Event(), 'created': time.time()}
            self.jobs[job_id] = job
        self.pool.submit(self.run_job, job, payload)
        return job_id

    def run_job(self, job, payload):
        try:
            if job['kind'] == 'analyze':
                result = analyze(payload, job['cancel'])
            else:
                from package.service.formula_search_service import start_search
                result = start_search([payload['formula']], 'PubChem', ion_mode=payload['ion_mode'])
            with self.lock:
                if job['cancel'].is_set():
                    job['status'] = 'cancelled'
                else:
                    job.update(status='success', result=result)
        except Exception as exc:
            with self.lock:
                job.update(status='cancelled' if job['cancel'].is_set() or isinstance(exc, SearchCancelled) else 'error', error=str(exc))

    def server_close(self):
        for job in self.jobs.values():
            job['cancel'].set()
        self.pool.shutdown(wait=False, cancel_futures=True)
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def respond(self, status, data, content_type='application/json; charset=utf-8'):
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode() if content_type.startswith('application/json') else data
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def do_GET(self):
        if not self.valid_host():
            return self.respond(403, {'error': 'Invalid host'})
        path = urlsplit(self.path).path
        if path == '/api/config':
            config = FormulaGenerator().config
            return self.respond(200, {'token': self.server.token, 'adducts': config['adducts'], 'elements': list(config['atomic_weights'])})
        if path.startswith('/api/jobs/'):
            with self.server.lock:
                job = self.server.jobs.get(path.rsplit('/', 1)[-1])
                data = {k: v for k, v in job.items() if k != 'cancel'} if job else None
            return self.respond(200 if data else 404, data or {'error': '任务已过期'})
        assets = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if path not in assets:
            return self.respond(404, {'error': 'Not found'})
        name, mime = assets[path]
        self.respond(200, (self.server.assets / name).read_bytes(), mime)

    def do_POST(self):
        if (not self.valid_host() or self.headers.get('Origin') != self.server.origin or
                self.headers.get('X-Workbench-Token') != self.server.token):
            return self.respond(403, {'error': '本机来源校验失败，请重新打开工作台'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1_000_000:
                return self.respond(413, {'error': '请求须为 1 MB 内 JSON'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.respond(415, {'error': '请求须为 JSON'})
            def invalid_constant(_value):
                raise ValueError('JSON 不能包含 NaN 或 Infinity')
            payload = json.loads(self.rfile.read(length), parse_constant=invalid_constant)
            path = urlsplit(self.path).path
            if path in ('/api/analyze', '/api/search'):
                return self.respond(202, {'id': self.server.submit(path.rsplit('/', 1)[-1], payload)})
            if path.startswith('/api/cancel/'):
                with self.server.lock:
                    job = self.server.jobs.get(path.rsplit('/', 1)[-1])
                    if job:
                        job['cancel'].set()
                        if job['status'] != 'running':
                            job['status'] = 'cancelled'
                            job.pop('result', None)
                return self.respond(200 if job else 404, {'status': 'cancellation_requested' if job else 'missing'})
            self.respond(404, {'error': 'Not found'})
        except (ValueError, TypeError, KeyError) as exc:
            self.respond(400, {'error': str(exc)})


def main():
    parser = argparse.ArgumentParser(description='Mass Finding local workbench')
    parser.add_argument('--port', type=int, default=8866)
    args = parser.parse_args()
    with WorkbenchServer(('127.0.0.1', args.port)) as server:
        print(f'Mass Finding: {server.origin} (Ctrl+C to stop)', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
