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
    ranked = app.rank_results('gdje su svjetla za maglu')
    assert ranked['chunks'], 'Expected manual chunk matches for Bosnian location query.'

    preview = app.build_preview_payload('gdje su svjetla za maglu', ranked)
    assert preview is not None
    assert preview['page'] > 0
    assert preview['image_url'].startswith('/previews/')
    preview_file = ROOT / 'static' / 'previews' / Path(preview['image_url']).name
    assert preview_file.exists(), preview_file

    bulb_ranked = app.rank_results('kako zamijeniti prednju sijalicu')
    bulb_ref = app.pick_reference(bulb_ranked)
    assert bulb_ref is not None
    assert bulb_ref['page'] >= 440

    service_ranked = app.rank_results('kako resetovati servis')
    service_ref = app.pick_reference(service_ranked)
    assert service_ref is not None
    assert service_ref['page'] >= 103

    language_ranked = app.rank_results('gdje se mijenja jezik displeja')
    language_ref = app.pick_reference(language_ranked)
    assert language_ref is not None
    assert language_ref['page'] >= 98

    lane_ranked = app.rank_results('kako ukljuciti lane assist')
    lane_ref = app.pick_reference(lane_ranked)
    assert lane_ref is not None
    assert lane_ref['page'] >= 99

    instrument_ranked = app.rank_results('kako mijenjati instrument tablu')
    instrument_ref = app.pick_reference(instrument_ranked)
    assert instrument_ref is not None
    assert instrument_ref['page'] == 85

    fuel_ranked = app.rank_results('koliko trosi ovaj auto benzina')
    fuel_ref = app.pick_reference(fuel_ranked)
    assert fuel_ref is not None
    assert fuel_ref['page'] == 88

    server = ThreadingHTTPServer(('127.0.0.1', 0), app.NissanDiagnosticHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        config = urllib.request.urlopen(f'http://127.0.0.1:{port}/api/config').read().decode('utf-8')
        config_payload = json.loads(config)
        assert config_payload['mode'] == 'local-manual'
        assert config_payload['chunk_count'] > 1000
        hero_response = urllib.request.urlopen(f'http://127.0.0.1:{port}/xtrail-hero.jpg')
        assert hero_response.status == 200

        req = urllib.request.Request(
            f'http://127.0.0.1:{port}/api/search',
            data=json.dumps({'query': 'gdje su svjetla za maglu'}).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        payload = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
        assert payload['preview']['page'] > 0
        assert 'manual' in payload['diagnosis']['notes'][0].lower()
        print('smoke-test-ok')
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
