"""Loopback-only studio; upload IDs never become arbitrary filesystem paths."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import parse_qs, unquote, urlparse

from .engine import RenderError, plan, probe, render

ROOT = Path(__file__).resolve().parents[1]
MAX_UPLOAD = 250 * 1024 * 1024


class Studio:
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.assets = {}
        self.jobs = {}
        self.lock = threading.Lock()
        self.demo = None

    def public_asset(self, key):
        asset = self.assets[key]
        return {'id': key, **asset['meta'], 'url': '/media/' + key}

    def add(self, path, name=None):
        meta = probe(path)
        if name:
            meta['name'] = name[:120]
        with self.lock:
            if len(self.assets) >= 20:
                raise RenderError('Session source limit reached. Restart the studio for another session.')
            key = secrets.token_hex(12)
            self.assets[key] = {'path': Path(path).resolve(), 'meta': meta}
        return self.public_asset(key)

    def inputs(self, body):
        try:
            return self.assets[body['top']], self.assets[body['bottom']]
        except (KeyError, TypeError):
            raise RenderError('Choose both video sources first.')

    def start(self, body):
        top, bottom = self.inputs(body)
        options = body.get('options', {})
        recipe = plan(top['meta'], bottom['meta'], options)
        with self.lock:
            if any(job['status'] == 'rendering' for job in self.jobs.values()):
                raise RenderError('A render is already running. Finish or cancel it first.')
            if len(self.jobs) >= 30:
                raise RenderError('Session render limit reached. Restart the studio for another session.')
            key = secrets.token_hex(12)
            job = {'id': key, 'status': 'rendering', 'completed': 0, 'total': len(recipe['segments']), 'files': [], 'cancel': threading.Event()}
            self.jobs[key] = job
        def work():
            try:
                def progress(done, total):
                    job.update(completed=done, total=total)
                result = render(top['path'], bottom['path'], self.workspace / ('render-' + key), options, cancel=job['cancel'], progress=progress)
                job.update(status='complete', files=[{'name': item['name'], 'url': f'/output/{key}/{item["name"]}', 'duration': item['verifiedDuration']} for item in result['files']], manifest=f'/output/{key}/manifest.json')
            except Exception as error:
                job.update(status='cancelled' if job['cancel'].is_set() else 'failed', error=str(error) if isinstance(error, (RenderError, FileExistsError)) else 'Render failed. Check the local workspace diagnostics.')
        threading.Thread(target=work, daemon=True).start()
        return self.job(key)

    def job(self, key):
        return {name: value for name, value in self.jobs[key].copy().items() if name != 'cancel'}


def handler(studio):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def trusted(self, mutation=False):
            expected = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != expected:
                return False
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + expected:
                return False
            if mutation and self.headers.get('X-Splitframe') != 'local-studio':
                return False
            return True

        def reply(self, status, data):
            body = json.dumps(data, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def file(self, path, download=False):
            path = Path(path)
            if not path.is_file():
                return self.reply(404, {'error': 'File not found.'})
            size = path.stat().st_size
            start, end, status = 0, size - 1, 200
            requested = self.headers.get('Range')
            if requested:
                match = re.fullmatch(r'bytes=(\d+)-(\d*)', requested)
                if not match:
                    return self.reply(416, {'error': 'Unsupported byte range.'})
                start = int(match[1]); end = min(int(match[2]) if match[2] else size - 1, size - 1)
                if start > end or start >= size:
                    return self.reply(416, {'error': 'Byte range outside file.'})
                status = 206
            self.send_response(status)
            self.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            self.send_header('Content-Length', str(end - start + 1))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; media-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            if status == 206:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            if download:
                self.send_header('Content-Disposition', f'attachment; filename="{path.name}"')
            self.end_headers()
            try:
                with path.open('rb') as source:
                    source.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        chunk = source.read(min(65536, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except ConnectionError:
                pass

        def do_GET(self):
            if not self.trusted():
                return self.reply(403, {'error': 'Local studio origin required.'})
            path = urlparse(self.path).path
            static = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
            if path in static:
                return self.file(ROOT / 'web' / static[path])
            if path.startswith('/media/'):
                asset = studio.assets.get(path.removeprefix('/media/'))
                return self.file(asset['path']) if asset else self.reply(404, {'error': 'Unknown source.'})
            if path.startswith('/api/jobs/'):
                key = path.removeprefix('/api/jobs/')
                return self.reply(200, studio.job(key)) if key in studio.jobs else self.reply(404, {'error': 'Unknown render.'})
            match = re.fullmatch(r'/output/([a-f0-9]{24})/(clip-\d{3}\.mp4|manifest\.json)', path)
            if match and match[1] in studio.jobs and studio.jobs[match[1]]['status'] == 'complete':
                return self.file(studio.workspace / ('render-' + match[1]) / match[2], download=True)
            return self.reply(404, {'error': 'Route not found.'})

        def do_POST(self):
            if not self.trusted(mutation=True):
                return self.reply(403, {'error': 'Local studio request required.'})
            self.connection.settimeout(60)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                path = urlparse(self.path).path
                if self.headers.get('Transfer-Encoding'):
                    raise RenderError('Chunked uploads are not supported.')
                if path == '/api/upload':
                    if not 1 <= length <= MAX_UPLOAD or len(studio.assets) >= 20:
                        raise RenderError('Choose a file under 250 MiB; at most 20 sources per session.')
                    name = parse_qs(urlparse(self.path).query).get('name', ['video.mp4'])[0]
                    extension = Path(name).suffix.lower()
                    if extension not in {'.mp4', '.mov', '.webm', '.mkv'}:
                        raise RenderError('Unsupported video file type.')
                    target = studio.workspace / (secrets.token_hex(16) + extension)
                    remaining = length
                    with target.open('xb') as output:
                        while remaining:
                            chunk = self.rfile.read(min(65536, remaining))
                            if not chunk:
                                raise RenderError('Upload ended before the file was complete.')
                            output.write(chunk); remaining -= len(chunk)
                    return self.reply(201, studio.add(target, Path(name).name))
                if not 0 <= length <= 32768:
                    raise RenderError('Request body too large.')
                body = json.loads(self.rfile.read(length) or b'{}')
                if not isinstance(body, dict):
                    raise RenderError('Request must be a JSON object.')
                if path == '/api/demo':
                    if studio.demo is None:
                        studio.demo = {'top': studio.add(ROOT / 'demo/top.mp4'), 'bottom': studio.add(ROOT / 'demo/bottom.mp4')}
                    return self.reply(200, studio.demo)
                if path == '/api/plan':
                    top, bottom = studio.inputs(body)
                    return self.reply(200, plan(top['meta'], bottom['meta'], body.get('options', {})))
                if path == '/api/render':
                    return self.reply(202, studio.start(body))
                if path == '/api/cancel':
                    key = body.get('id')
                    if key not in studio.jobs:
                        raise RenderError('Unknown render.')
                    studio.jobs[key]['cancel'].set()
                    return self.reply(200, studio.job(key))
                return self.reply(404, {'error': 'Route not found.'})
            except (ValueError, OSError, KeyError) as error:
                return self.reply(400, {'error': str(error) if isinstance(error, RenderError) else 'Invalid or unreadable input.'})
            except Exception:
                return self.reply(500, {'error': 'Could not process this video. Verify FFmpeg and FFprobe are installed.'})
    return Handler


def serve(port=8840, workspace='workspace'):
    studio = Studio(workspace)
    server = ThreadingHTTPServer(('127.0.0.1', port), handler(studio))
    print(f'Splitframe: http://127.0.0.1:{server.server_port} · files stay in {studio.workspace.name}/')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for job in studio.jobs.values():
            job['cancel'].set()
        server.server_close()
