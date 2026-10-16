from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from splitframe.server import ROOT, Studio, handler


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.studio = Studio(self.temp.name)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler(self.studio))
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        for job in self.studio.jobs.values():
            job['cancel'].set()
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.temp.cleanup()

    def post(self, path, body):
        request = Request(self.base + path, data=json.dumps(body).encode(), headers={'X-Splitframe': 'local-studio', 'Content-Type': 'application/json'})
        return json.load(urlopen(request, timeout=30))

    def test_file_allowlist_origin_and_mutation_header(self):
        for path in ['/.git/config', '/run.py', '/workspace/private.mp4']:
            with self.assertRaises(HTTPError) as failure:
                urlopen(self.base + path)
            self.assertEqual(failure.exception.code, 404)
        request = Request(self.base + '/api/demo', data=b'{}', headers={'X-Splitframe': 'local-studio', 'Origin': 'https://foreign.example'})
        with self.assertRaises(HTTPError) as failure:
            urlopen(request)
        self.assertEqual(failure.exception.code, 403)
        with self.assertRaises(HTTPError):
            urlopen(Request(self.base + '/api/demo', data=b'{}'))

    def test_real_upload_probe_and_byte_range(self):
        source = (ROOT / 'demo/top.mp4').read_bytes()
        request = Request(self.base + '/api/upload?name=sample.mp4', data=source, headers={'X-Splitframe': 'local-studio'})
        asset = json.load(urlopen(request, timeout=30))
        self.assertEqual(asset['duration'], 8)
        response = urlopen(Request(self.base + asset['url'], headers={'Range': 'bytes=0-99'}))
        self.assertEqual(response.status, 206)
        self.assertEqual(response.read(), source[:100])
        self.assertEqual(response.headers['Content-Range'], f'bytes 0-99/{len(source)}')

    def test_plan_and_render_end_to_end(self):
        sources = self.post('/api/demo', {})
        self.assertEqual(self.post('/api/demo', {}), sources)
        self.assertEqual(len(self.studio.assets), 2)
        body = {'top': sources['top']['id'], 'bottom': sources['bottom']['id'], 'options': {'clip': 3, 'length': 'shortest', 'size': '540', 'audio': 'bottom'}}
        recipe = self.post('/api/plan', body)
        self.assertEqual(recipe['audio'], 'none')
        job = self.post('/api/render', body)
        deadline = time.monotonic() + 30
        while job['status'] == 'rendering' and time.monotonic() < deadline:
            time.sleep(.1)
            job = json.load(urlopen(self.base + '/api/jobs/' + job['id']))
        self.assertEqual(job['status'], 'complete', job)
        manifest = json.load(urlopen(self.base + job['manifest']))
        self.assertEqual(len(manifest['files']), 1)
        self.assertFalse(manifest['files'][0]['audio'])
        self.assertEqual(urlopen(self.base + job['files'][0]['url']).status, 200)


if __name__ == '__main__':
    unittest.main()
