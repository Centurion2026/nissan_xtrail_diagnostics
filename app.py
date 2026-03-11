from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import error, request


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'data'
STATIC_DIR = ROOT / 'static'
MANUAL_CHUNKS_PATH = DATA_DIR / 'manual_chunks.json'
WARNING_LIGHTS_PATH = DATA_DIR / 'warning_lights.json'
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '').strip()
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8000'))


with MANUAL_CHUNKS_PATH.open('r', encoding='utf-8') as fh:
    MANUAL_CHUNKS = json.load(fh)

with WARNING_LIGHTS_PATH.open('r', encoding='utf-8-sig') as fh:
    WARNING_LIGHTS = json.load(fh)


SEVERITY_LABELS = {
    'critical': 'Odmah stati',
    'high': 'Hitno',
    'medium': 'Upozorenje',
    'low': 'Informativno',
}
SEVERITY_ORDER = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
STOPWORDS = {
    'the', 'and', 'for', 'with', 'from', 'that', 'this', 'your', 'about', 'what', 'when', 'while', 'into',
    'kako', 'gdje', 'sta', 'sto', 'problem', 'imam', 'radi', 'nije', 'kada', 'zasto', 'koji',
    'koja', 'lampica', 'slika', 'screenshot', 'auto', 'nissan', 'xtrail', 'trail'
}


def normalize_text(value: str) -> str:
    value = value.lower()
    value = value.replace('e-power', 'epower')
    value = re.sub(r'[^a-z0-9\-\s]', ' ', value)
    value = re.sub(r'\s+', ' ', value)
    return value.strip()



def tokenize(value: str) -> list[str]:
    return [token for token in normalize_text(value).split() if len(token) > 2 and token not in STOPWORDS]



def score_warning(query: str, tokens: set[str], warning: dict[str, Any]) -> float:
    haystack = ' '.join([warning['name'], warning['summary'], warning['driver_action'], *warning.get('aliases', [])])
    normalized = normalize_text(haystack)
    score = 0.0

    for alias in warning.get('aliases', []):
        alias_norm = normalize_text(alias)
        if alias_norm and alias_norm in query:
            score += 6

    name_norm = normalize_text(warning['name'])
    if name_norm in query:
        score += 8

    warning_tokens = set(tokenize(haystack))
    score += len(tokens & warning_tokens) * 1.5
    if any(token in normalized for token in tokens):
        score += 0.5
    return score



def score_chunk(query: str, tokens: set[str], chunk: dict[str, Any]) -> float:
    text = f"{chunk['heading']} {chunk['text']}"
    normalized = normalize_text(text)
    chunk_tokens = set(tokenize(text))
    overlap = tokens & chunk_tokens
    score = len(overlap) * 1.0

    if query and query in normalized:
        score += 10

    for token in tokens:
        if token in normalized:
            score += 0.4

    return score



def rank_results(query_text: str) -> dict[str, Any]:
    normalized_query = normalize_text(query_text)
    tokens = set(tokenize(query_text))

    warning_matches: list[dict[str, Any]] = []
    for warning in WARNING_LIGHTS['warnings']:
        score = score_warning(normalized_query, tokens, warning)
        if score > 0:
            warning_matches.append({**warning, 'score': round(score, 2)})
    warning_matches.sort(key=lambda item: (-item['score'], -SEVERITY_ORDER.get(item['severity'], 0), item['name']))

    chunk_matches: list[dict[str, Any]] = []
    for chunk in MANUAL_CHUNKS['chunks']:
        score = score_chunk(normalized_query, tokens, chunk)
        if score >= 2:
            chunk_matches.append(
                {
                    'chunk_id': chunk['chunk_id'],
                    'page': chunk['page'],
                    'heading': chunk['heading'],
                    'preview': chunk['preview'],
                    'score': round(score, 2),
                }
            )
    chunk_matches.sort(key=lambda item: (-item['score'], item['page']))

    return {
        'warnings': warning_matches[:5],
        'chunks': chunk_matches[:6],
    }



def build_local_diagnosis(query_text: str, ranked: dict[str, Any], image_note: str | None = None) -> dict[str, Any]:
    top_warning = ranked['warnings'][0] if ranked['warnings'] else None
    top_chunk = ranked['chunks'][0] if ranked['chunks'] else None

    if top_warning:
        title = top_warning['name']
        severity = top_warning['severity']
        overview = top_warning['summary']
        next_steps = top_warning['driver_action']
        confidence = 'visoka' if top_warning['score'] >= 8 else 'srednja'
    elif top_chunk:
        title = top_chunk['heading']
        severity = 'medium'
        overview = top_chunk['preview']
        next_steps = 'Pogledaj navedene stranice prirucnika i potvrdi poruku na instrument tabli ili centralnom ekranu.'
        confidence = 'srednja'
    else:
        title = 'Nije pronadjen jasan pogodak'
        severity = 'low'
        overview = 'Upit nije dovoljno precizan da bi se pouzdano povezao sa lampicom ili procedurom iz prirucnika.'
        next_steps = 'Unesi tacan tekst sa ekrana, naziv lampice ili opisi kada se problem pojavljuje.'
        confidence = 'niska'

    notes = []
    if image_note:
        notes.append(image_note)
    notes.append('Baza znanja je generisana iz PDF-a koji je u ovom folderu. Taj PDF se identifikuje kao Qashqai manual, ne X-Trail manual.')

    return {
        'title': title,
        'severity': severity,
        'severity_label': SEVERITY_LABELS[severity],
        'overview': overview,
        'next_steps': next_steps,
        'confidence': confidence,
        'notes': notes,
    }



def warning_catalog_text() -> str:
    lines = []
    for warning in WARNING_LIGHTS['warnings']:
        lines.append(
            f"- {warning['name']} | severity={warning['severity']} | summary={warning['summary']} | action={warning['driver_action']}"
        )
    return '\n'.join(lines)



def call_openai_vision(image_bytes: bytes, mime_type: str, user_query: str, ranked: dict[str, Any]) -> dict[str, Any]:
    top_chunks = ranked['chunks'][:4]
    top_warnings = ranked['warnings'][:4]
    manual_context = '\n'.join(
        f"- page {chunk['page']} | {chunk['heading']} | {chunk['preview']}" for chunk in top_chunks
    ) or 'No manual chunk matches.'
    warning_context = '\n'.join(
        f"- {item['name']} | severity={item['severity']} | action={item['driver_action']}" for item in top_warnings
    ) or warning_catalog_text()

    payload = {
        'model': OPENAI_MODEL,
        'input': [
            {
                'role': 'system',
                'content': [
                    {
                        'type': 'input_text',
                        'text': (
                            'You are a Nissan diagnostic assistant. Analyze uploaded dashboard photos or screenshots and answer in Bosnian/Croatian/Serbian Latin. '
                            'Be precise, short, and safety-first. If uncertain, say so. Prefer the supplied manual context and warning catalog. '
                            'Return strict JSON with keys: detected_item, likely_problem, severity, action, confidence, explanation.'
                        ),
                    }
                ],
            },
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'input_text',
                        'text': (
                            f'User description: {user_query or "No extra description provided."}\n\n'
                            f'Manual context:\n{manual_context}\n\n'
                            f'Warning catalog:\n{warning_context}\n\n'
                            'Identify the warning light, text message, or dashboard state from the image if possible. '
                            'Explain what it most likely means and what the driver should do next.'
                        ),
                    },
                    {
                        'type': 'input_image',
                        'image_url': f'data:{mime_type};base64,{base64.b64encode(image_bytes).decode("ascii")}',
                    },
                ],
            },
        ],
    }

    req = request.Request(
        'https://api.openai.com/v1/responses',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {OPENAI_API_KEY}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    with request.urlopen(req, timeout=90) as response:
        raw = json.loads(response.read().decode('utf-8'))

    text = raw.get('output_text', '').strip()
    if not text:
        for item in raw.get('output', []):
            for content in item.get('content', []):
                if content.get('type') == 'output_text':
                    text += content.get('text', '')

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = {
            'detected_item': 'Nepotpuno parsiran AI odgovor',
            'likely_problem': text or 'AI odgovor nije bio u ocekivanom formatu.',
            'severity': 'medium',
            'action': 'Provjeri rucno rezultat i uporedi ga s referencama iz prirucnika.',
            'confidence': 'srednja',
            'explanation': text,
        }

    severity = str(parsed.get('severity', 'medium')).lower()
    if severity not in SEVERITY_LABELS:
        severity = 'medium'

    return {
        'title': parsed.get('detected_item') or 'Analiza slike',
        'severity': severity,
        'severity_label': SEVERITY_LABELS[severity],
        'overview': parsed.get('likely_problem') or 'Nije vracen opis problema.',
        'next_steps': parsed.get('action') or 'Provjeri preporuke iz prirucnika i kontaktiraj servis ako je potrebno.',
        'confidence': parsed.get('confidence') or 'srednja',
        'notes': [parsed.get('explanation', 'AI analiza slike zasnovana na dostavljenoj slici i lokalnom prirucniku.')],
    }



def parse_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get('Content-Length', '0'))
    body = handler.rfile.read(length)
    return json.loads(body.decode('utf-8')) if body else {}



def parse_multipart_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get('Content-Length', '0'))
    body = handler.rfile.read(length)
    content_type = handler.headers.get('Content-Type', '')
    raw_message = f'Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n'.encode('utf-8') + body
    message = BytesParser(policy=default).parsebytes(raw_message)

    fields: dict[str, Any] = {}
    for part in message.iter_parts():
        disposition = part.get_content_disposition()
        if disposition != 'form-data':
            continue
        name = part.get_param('name', header='content-disposition')
        filename = part.get_filename()
        payload = part.get_payload(decode=True)
        if filename:
            fields[name] = {
                'filename': filename,
                'content_type': part.get_content_type(),
                'content': payload,
            }
        else:
            fields[name] = (payload or b'').decode('utf-8', errors='ignore')
    return fields



def json_response(handler: BaseHTTPRequestHandler, payload: dict[str, Any], status: int = 200) -> None:
    encoded = json.dumps(payload).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(encoded)))
    handler.send_header('Cache-Control', 'no-store')
    handler.end_headers()
    handler.wfile.write(encoded)



def serve_static(handler: BaseHTTPRequestHandler, path: str) -> None:
    target = STATIC_DIR / path.lstrip('/')
    if not target.exists() or not target.is_file():
        handler.send_error(HTTPStatus.NOT_FOUND, 'File not found')
        return

    mime_type, _ = mimetypes.guess_type(str(target))
    data = target.read_bytes()
    handler.send_response(200)
    handler.send_header('Content-Type', f'{mime_type or "application/octet-stream"}; charset=utf-8')
    handler.send_header('Content-Length', str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class NissanDiagnosticHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == '/' or self.path == '/index.html':
            serve_static(self, '/index.html')
            return

        if self.path == '/api/config':
            json_response(
                self,
                {
                    'vision_enabled': bool(OPENAI_API_KEY),
                    'model': OPENAI_MODEL if OPENAI_API_KEY else None,
                    'manual_source': WARNING_LIGHTS['source_manual'],
                    'manual_note': WARNING_LIGHTS['note'],
                    'warning_count': len(WARNING_LIGHTS['warnings']),
                    'chunk_count': MANUAL_CHUNKS['chunk_count'],
                },
            )
            return

        if self.path.startswith('/app.js') or self.path.startswith('/styles.css'):
            serve_static(self, self.path)
            return

        handler_path = self.path.split('?', 1)[0]
        if handler_path.startswith('/static/'):
            serve_static(self, handler_path.replace('/static', '', 1))
            return

        self.send_error(HTTPStatus.NOT_FOUND, 'Not found')

    def do_POST(self) -> None:
        if self.path == '/api/search':
            try:
                payload = parse_json_body(self)
                query_text = str(payload.get('query', '')).strip()
                if not query_text:
                    json_response(self, {'error': 'Unesi opis problema ili naziv lampice.'}, status=400)
                    return
                ranked = rank_results(query_text)
                diagnosis = build_local_diagnosis(query_text, ranked)
                json_response(self, {'diagnosis': diagnosis, 'matches': ranked})
                return
            except json.JSONDecodeError:
                json_response(self, {'error': 'Neispravan JSON payload.'}, status=400)
                return

        if self.path == '/api/analyze-image':
            try:
                form = parse_multipart_body(self)
            except Exception as exc:
                json_response(self, {'error': f'Ne mogu procitati upload: {exc}'}, status=400)
                return

            query_text = str(form.get('query', '')).strip()
            image = form.get('image')
            if not isinstance(image, dict):
                json_response(self, {'error': 'Posalji sliku ili screenshot za analizu.'}, status=400)
                return

            ranked = rank_results(query_text)
            if not OPENAI_API_KEY:
                diagnosis = build_local_diagnosis(
                    query_text,
                    ranked,
                    image_note='OPENAI_API_KEY nije postavljen, pa je analiza slike ogranicena na tekstualni opis koji si unio i lokalnu bazu znanja.',
                )
                json_response(self, {'diagnosis': diagnosis, 'matches': ranked, 'vision_used': False})
                return

            try:
                diagnosis = call_openai_vision(image['content'], image['content_type'], query_text, ranked)
                json_response(self, {'diagnosis': diagnosis, 'matches': ranked, 'vision_used': True})
                return
            except error.HTTPError as exc:
                body = exc.read().decode('utf-8', errors='ignore')
                json_response(self, {'error': f'OpenAI vision poziv nije uspio: {body}'}, status=502)
                return
            except Exception as exc:
                json_response(self, {'error': f'Analiza slike nije uspjela: {exc}'}, status=500)
                return

        self.send_error(HTTPStatus.NOT_FOUND, 'Not found')

    def log_message(self, fmt: str, *args: Any) -> None:
        return


if __name__ == '__main__':
    server = ThreadingHTTPServer((HOST, PORT), NissanDiagnosticHandler)
    print(f'Serving Nissan diagnostic app on http://127.0.0.1:{PORT}')
    server.serve_forever()

