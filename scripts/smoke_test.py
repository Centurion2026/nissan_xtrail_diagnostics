from pathlib import Path
import json
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app


def main() -> None:
    ranked = app.rank_results('check engine service now')
    diagnosis = app.build_local_diagnosis('check engine service now', ranked)
    assert diagnosis['title'] == 'Malfunction indicator light (MIL)'

    server = ThreadingHTTPServer(('127.0.0.1', 0), app.NissanDiagnosticHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        config = urllib.request.urlopen(f'http://127.0.0.1:{port}/api/config').read().decode('utf-8')
        config_payload = json.loads(config)
        assert config_payload['chunk_count'] > 1000

        req = urllib.request.Request(
            f'http://127.0.0.1:{port}/api/search',
            data=json.dumps({'query': 'low tyre pressure'}).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        payload = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
        assert payload['diagnosis']['title'] == 'Low tyre pressure warning light'
        print('smoke-test-ok')
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
