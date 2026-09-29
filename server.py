"""Local web server. Scientific data comes only from the selected read-only bundle."""
import argparse
import base64
import datetime
import gzip
import json
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from pathlib import Path
from plotly.offline import get_plotlyjs
from atlas_engine import AtlasEngine, MODE_LABELS
from configuration import APP, settings

VERSION = '1.0.0'
ENGINE = None
OUTPUT = None
LOCK = threading.Lock()
PLOTLY_JS = None
STATIC = {'/': 'index.html', '/index.html': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}

class Handler(BaseHTTPRequestHandler):
    def local_request(self):
        allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        host = self.headers.get('Host', '')
        origin = self.headers.get('Origin')
        return host in allowed and (not origin or origin == f'http://{host}')

    def respond(self, status, data, content_type='application/json; charset=utf-8'):
        if not isinstance(data, bytes):
            data = json.dumps(data, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        if len(data) > 4096 and 'gzip' in self.headers.get('Accept-Encoding', ''):
            data = gzip.compress(data, compresslevel=3)
            self.send_header('Content-Encoding', 'gzip')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; worker-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.local_request():
            return self.respond(403, {'error': 'Open the app at its localhost address.'})
        path = urlparse(self.path).path
        try:
            if path == '/api/health':
                return self.respond(200, {'app': 'horta-lookup', 'version': VERSION, 'ready': True,
                    'data_root': str(ENGINE.bundle.root), 'output_root': str(OUTPUT), 'bundle_id': ENGINE.bundle.bundle_id})
            if path == '/api/config':
                return self.respond(200, {'datasets': ENGINE.datasets, 'mode_labels': MODE_LABELS, 'version': VERSION,
                    'default_dataset': ENGINE.bundle.default_dataset, 'data_root': str(ENGINE.bundle.root), 'bundle_id': ENGINE.bundle.bundle_id})
            if path == '/plotly.min.js':
                return self.respond(200, PLOTLY_JS, 'application/javascript; charset=utf-8')
            if path == '/meshes.json':
                return self.respond(200, ENGINE.bundle.path(ENGINE.bundle.atlas['meshes']).read_bytes())
            if path in STATIC:
                p = APP / 'web' / STATIC[path]
                kind = {'.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css'}[p.suffix]
                return self.respond(200, p.read_bytes(), kind + '; charset=utf-8')
            return self.respond(404, {'error': 'Not found'})
        except (OSError, ValueError):
            traceback.print_exc()
            return self.respond(503, {'error': 'Cannot read an app or shared data file. Check the drive connection and restart the app.'})

    def do_POST(self):
        if not self.local_request():
            return self.respond(403, {'error': 'Use the local app page.'})
        path = urlparse(self.path).path
        if path not in ('/api/check', '/api/save'):
            return self.respond(404, {'error': 'Not found'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length < 4096:
                raise ValueError('Invalid request size.')
            req = json.loads(self.rfile.read(length))
            if not isinstance(req, dict) or not isinstance(req.get('dataset'), str) or not isinstance(req.get('mode'), str):
                raise ValueError('Choose a dataset, transform and three coordinates.')
            dataset, xyz, mode = req.get('dataset'), req.get('xyz'), req.get('mode')
            with LOCK:
                result = ENGINE.check(dataset, xyz, mode)
            if path == '/api/save':
                now = datetime.datetime.now(datetime.timezone.utc)
                # Do not use an arbitrary dataset string as a filesystem path.
                target = OUTPUT / now.strftime('%Y%m%dT%H%M%S%fZ')
                target.mkdir(parents=True)
                result.update(saved_at_utc=now.isoformat(), app_version=VERSION)
                pictures = result.pop('slices')
                for picture in pictures:
                    (target / (picture['title'].lower() + '.png')).write_bytes(base64.b64decode(picture['image'].split(',', 1)[1]))
                (target / 'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
                (target / 'README.md').write_text(
                    f'# Horta coordinate check\n\nDataset: {dataset}. Transform: {result["transform_label"]}.\n\n'
                    f'Horta XYZ: {xyz}. CCF AP/DV/ML: {result["ccf_ap_dv_ml_um"]}.\n\n'
                    f'Atlas region: {result["atlas_name"]}. Inside MRN: {result["inside_mrn"]}.\n\n'
                    f'{result["note"]}\n\n{result["caveat"]}\n\n'
                    f'Reproduce using Horta Lookup v{VERSION}, data bundle {ENGINE.bundle.bundle_id}, and the input and mode in result.json.\n'
                    'Source: https://github.com/edwardyan95/horta-lookup\n', encoding='utf-8')
                return self.respond(200, {'saved_to': str(target)})
            return self.respond(200, result)
        except (ValueError, TypeError, KeyError) as e:
            return self.respond(400, {'error': str(e)})
        except Exception:
            traceback.print_exc()
            return self.respond(500, {'error': 'Lookup failed. Check the shared drive and local server log. No alternative transform was applied.'})

    def log_message(self, fmt, *args):
        pass

def main():
    global ENGINE, OUTPUT, PLOTLY_JS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root')
    parser.add_argument('--output-root')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    cfg = settings(args.data_root, args.output_root, args.port)
    if not cfg['data_root']:
        parser.error('Select the data folder with Configure data folder.cmd, or pass --data-root.')
    ENGINE = AtlasEngine(cfg['data_root'])
    OUTPUT = Path(cfg['output_root'])
    PLOTLY_JS = get_plotlyjs().encode()
    server = ThreadingHTTPServer(('127.0.0.1', cfg['port']), Handler)
    print(f'Horta Lookup ready: http://127.0.0.1:{cfg["port"]}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
