from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import unicodedata
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import fitz

from manual_utils import load_dotenv, resolve_manual_pdf


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
DATA_DIR = ROOT / 'data'
STATIC_DIR = ROOT / 'static'
PREVIEW_DIR = STATIC_DIR / 'previews'
PREVIEW_DIR.mkdir(exist_ok=True)
MANUAL_PAGES_PATH = DATA_DIR / 'manual_pages.json'
MANUAL_CHUNKS_PATH = DATA_DIR / 'manual_chunks.json'
WARNING_LIGHTS_PATH = DATA_DIR / 'warning_lights.json'
MANUAL_PDF_PATH = resolve_manual_pdf(ROOT)
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8000'))

with MANUAL_PAGES_PATH.open('r', encoding='utf-8') as fh:
    MANUAL_PAGES = json.load(fh)

with MANUAL_CHUNKS_PATH.open('r', encoding='utf-8') as fh:
    MANUAL_CHUNKS = json.load(fh)

with WARNING_LIGHTS_PATH.open('r', encoding='utf-8-sig') as fh:
    WARNING_LIGHTS = json.load(fh)

MANUAL_DOC = fitz.open(str(MANUAL_PDF_PATH))
PAGE_LOOKUP = {page['page']: page for page in MANUAL_PAGES['pages']}
MANUAL_TITLE = MANUAL_PAGES.get('manual_title') or MANUAL_PAGES.get('source_pdf') or MANUAL_PDF_PATH.name
MANUAL_NOTE = MANUAL_PAGES.get('manual_note') or 'Aktivni manual je lokalno učitan.'
MANUAL_SOURCE = MANUAL_PAGES.get('source_pdf') or MANUAL_PDF_PATH.name

SEVERITY_LABELS = {
    'critical': 'Odmah provjeri',
    'high': 'Važno',
    'medium': 'Pronađena referenca',
    'low': 'Prijedlog',
}
SEVERITY_ORDER = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
STOPWORDS = {
    'the', 'and', 'for', 'with', 'from', 'that', 'this', 'your', 'about', 'what', 'when', 'while', 'into',
    'kako', 'gdje', 'gde', 'sta', 'sto', 'problem', 'imam', 'radi', 'nije', 'kada', 'zasto', 'koji',
    'koja', 'koje', 'koga', 'slika', 'screenshot', 'auto', 'nissan', 'xtrail', 'trail', 'molim', 'trebam',
    'nalazi', 'nalaze', 'li', 'se', 'je', 'su', 'da', 'na', 'u', 'za', 'od', 'do', 'po', 'ili'
}
PHRASE_SYNONYMS = {
    'svjetla za maglu': 'fog light fog lights front fog light rear fog light',
    'svetla za maglu': 'fog light fog lights front fog light rear fog light',
    'maglenke': 'fog light fog lights',
    'zadnja maglenka': 'rear fog light rear fog lights',
    'prednja maglenka': 'front fog light front fog lights',
    'grijanje sjedista': 'seat heater heated seat heated seats',
    'grejanje sedista': 'seat heater heated seat heated seats',
    'zadnji brisac': 'rear wiper rear window wiper',
    'prednji brisaci': 'front wiper front wipers windscreen wiper',
    'instrument tabla': 'meter screen meter display vehicle information display instrument panel display view',
    'instrument table': 'meter screen meter display vehicle information display instrument panel display view',
    'promjena instrument table': 'change display view meter screen view vehicle information display',
    'promjena prikaza': 'change display view screen view meter display',
    'promjena prikaza instrument table': 'change display view meter screen view vehicle information display',
    'mijenjati instrument tablu': 'change display view meter screen view vehicle information display',
    'menjati instrument tablu': 'change display view meter screen view vehicle information display',
    'potrosnja goriva': 'fuel economy fuel consumption average fuel consumption eco drive report',
    'potrosnja benzina': 'fuel economy fuel consumption average fuel consumption petrol fuel',
    'koliko trosi': 'fuel economy fuel consumption average fuel economy average fuel consumption',
    'koliko benzina trosi': 'fuel economy fuel consumption petrol fuel',
    'eco drive report': 'fuel economy average fuel consumption history current fuel economy',
    'prednja sijalica': 'headlight bulb front bulb headlight bulb replacement bulb replacement',
    'prednje sijalice': 'headlight bulb front bulb headlight bulb replacement bulb replacement',
    'zamjena sijalice': 'bulb replacement replacing bulb changing bulb',
    'zamjena prednje sijalice': 'headlight bulb front bulb headlight bulb replacement replacing bulb',
    'zamijeniti prednju sijalicu': 'headlight bulb front bulb headlight bulb replacement replacing bulb',
    'zamjeniti prednju sijalicu': 'headlight bulb front bulb headlight bulb replacement replacing bulb',
    'promijeniti prednju sijalicu': 'headlight bulb front bulb headlight bulb replacement replacing bulb',
    'prednji far': 'headlight front light low beam high beam',
    'reset servisa': 'maintenance service oil control system service due maintenance screen reset service',
    'reset servis': 'maintenance service oil control system service due maintenance screen reset service',
    'servis reset': 'maintenance service oil control system service due maintenance screen reset service',
    'jezik displeja': 'display settings unit language personal display vehicle information display',
    'promjena jezika displeja': 'display settings unit language personal display vehicle information display',
    'language display': 'display settings unit language vehicle information display',
    'lane assist': 'steering assist lane assist emergency lane assist driver assistance lane',
    'ukljuciti lane assist': 'steering assist lane assist emergency lane assist driver assistance settings',
    'iskljuciti lane assist': 'steering assist lane assist emergency lane assist driver assistance settings',
    'duga svjetla': 'high beam headlight high beam assist',
    'kratka svjetla': 'low beam headlight headlights',
    'parkirna kocnica': 'parking brake electronic parking brake',
    'retrovizor': 'door mirror outside mirror mirror',
}
WORD_SYNONYMS = {
    'svjetla': 'light lights lighting headlight headlights lamp switch',
    'svetla': 'light lights lighting headlight headlights lamp switch',
    'farovi': 'headlight headlights',
    'maglu': 'fog',
    'magla': 'fog',
    'brisac': 'wiper',
    'brisaci': 'wipers wiper',
    'volan': 'steering wheel',
    'grijanje': 'heater heating climate control',
    'grejanje': 'heater heating climate control',
    'klima': 'air conditioner climate control',
    'sjedista': 'seat seats',
    'sedista': 'seat seats',
    'prtljaznik': 'luggage luggage room back door tailgate',
    'gepek': 'luggage room back door tailgate',
    'migavac': 'turn signal indicator',
    'prekidac': 'switch control button',
    'dugme': 'button switch control',
    'kamera': 'camera around view',
    'senzor': 'sensor sensors',
    'tempomat': 'cruise control',
    'maglenka': 'fog light',
    'instrument': 'meter instrument panel display cluster',
    'tabla': 'panel cluster display meter',
    'tablu': 'panel cluster display meter',
    'prikaz': 'display screen view',
    'promjena': 'change switch settings',
    'mijenjati': 'change adjust settings switch',
    'menjati': 'change adjust settings switch',
    'potrosnja': 'consumption economy fuel economy fuel consumption',
    'goriva': 'fuel economy consumption',
    'benzina': 'fuel petrol consumption',
    'trosi': 'consumption economy use',
    'koliko': 'average current report information',
    'sijalica': 'bulb lamp light headlight bulb replacement',
    'sijalicu': 'bulb lamp light headlight bulb replacement',
    'sijalice': 'bulb lamp light headlight bulb replacement',
    'zamjena': 'replacement replacing change',
    'zamijeniti': 'replace replacement changing',
    'zamjeniti': 'replace replacement changing',
    'promijeniti': 'change replace replacement',
    'prednja': 'front headlight headlamp',
    'prednje': 'front headlight headlamp',
    'far': 'headlight headlamp',
    'farovi': 'headlights headlamps',
    'resetovati': 'reset maintenance service',
    'reset': 'reset settings service',
    'servis': 'maintenance service oil control',
    'displeja': 'display screen meter',
    'displej': 'display screen meter',
    'jezik': 'language unit language settings',
    'lane': 'lane steering assist',
    'assist': 'assist assistance steering assist lane assist',
    'ukljuciti': 'turn on enable settings',
    'uključiti': 'turn on enable settings',
    'iskljuciti': 'turn off disable settings',
    'isključiti': 'turn off disable settings',
}
LOCATION_HINTS = {'gdje', 'gde', 'nalazi', 'nalaze', 'locirano', 'where', 'find', 'nalazim'}
INFO_HINTS = {'koliko', 'potrosnja', 'trosi', 'average', 'report', 'promjena', 'mijenjati', 'menjati', 'zamjena', 'zamijeniti', 'zamjeniti', 'promijeniti', 'sijalica', 'sijalicu', 'reset', 'resetovati', 'servis', 'jezik', 'displej', 'lane', 'assist', 'ukljuciti', 'iskljuciti'}


def strip_diacritics(value: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFKD', value) if not unicodedata.combining(ch))



def normalize_text(value: str) -> str:
    value = strip_diacritics(value.lower())
    value = value.replace('e-power', 'epower')
    value = re.sub(r'[^a-z0-9\-\s]', ' ', value)
    value = re.sub(r'\s+', ' ', value)
    return value.strip()



def clean_excerpt(value: str) -> str:
    value = re.sub(r'\s+', ' ', value).strip()
    return value[:220].strip()



def clean_heading(value: str) -> str:
    cleaned = re.sub(r'GUID-[A-Z0-9\-]+', '', value, flags=re.IGNORECASE)
    cleaned = re.sub(r'MEVHT33[A-Z0-9\-]+', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' -_')
    if not cleaned:
        return 'Manual referenca'
    if re.fullmatch(r'[A-Z0-9\-]{6,}', cleaned):
        return 'Manual referenca'
    return cleaned



def friendly_query_title(query_text: str, fallback: str) -> str:
    normalized = normalize_text(query_text)
    if any(token in normalized for token in ('sijalic', 'bulb', 'headlight', 'headlamp', 'far')):
        return 'Zamjena prednje sijalice / headlight bulb'
    if any(token in normalized for token in ('reset servis', 'reset servisa', 'servis reset', 'oil control', 'service due')):
        return 'Reset servisnog intervala'
    if any(token in normalized for token in ('jezik', 'language', 'display settings', 'unit language')):
        return 'Jezik displeja / Display Settings'
    if any(token in normalized for token in ('lane assist', 'steering assist', 'emergency lane assist')):
        return 'Lane Assist / Steering Assist'
    if any(token in normalized for token in ('instrument', 'tabla', 'tablu', 'prikaz', 'display', 'meter')):
        return 'Promjena prikaza instrument table'
    if any(token in normalized for token in ('potrosnja', 'trosi', 'goriva', 'benzina', 'economy', 'consumption')):
        return 'Potrošnja goriva / ECO Drive Report'
    return fallback



def tokenize(value: str) -> list[str]:
    return [token for token in normalize_text(value).split() if len(token) > 2 and token not in STOPWORDS]



def expand_query(value: str) -> str:
    normalized = normalize_text(value)
    extras: list[str] = []
    for phrase, synonyms in PHRASE_SYNONYMS.items():
        if phrase in normalized:
            extras.extend(synonyms.split())
    for token in normalized.split():
        mapped = WORD_SYNONYMS.get(token)
        if mapped:
            extras.extend(mapped.split())
    if normalized.startswith('gdje ') or normalized.startswith('gde '):
        extras.extend(['location', 'switch', 'control'])
    return ' '.join(part for part in [value, ' '.join(extras)] if part).strip()



def is_location_query(value: str) -> bool:
    tokens = set(normalize_text(value).split())
    return bool(tokens & LOCATION_HINTS)



def is_info_query(value: str) -> bool:
    tokens = set(normalize_text(value).split())
    return bool(tokens & INFO_HINTS)



def score_warning(query: str, tokens: set[str], warning: dict[str, Any], location_mode: bool) -> float:
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
    if location_mode:
        score *= 0.55
    return score



def score_chunk(query: str, tokens: set[str], chunk: dict[str, Any], location_mode: bool) -> float:
    text = f"{chunk['heading']} {chunk['text']}"
    normalized = normalize_text(text)
    chunk_tokens = set(tokenize(text))
    overlap = tokens & chunk_tokens
    score = len(overlap) * 1.2

    if query and query in normalized:
        score += 10

    for token in tokens:
        if token in normalized:
            score += 0.45

    if location_mode:
        score += 1.5
    return score



def score_page(query: str, tokens: set[str], page: dict[str, Any], location_mode: bool, info_mode: bool) -> float:
    text = page.get('text', '')
    normalized = normalize_text(text)
    page_tokens = set(tokenize(text))
    overlap = tokens & page_tokens
    score = len(overlap) * 0.9

    if query and query in normalized:
        score += 8

    for token in tokens:
        if token in normalized:
            score += 0.25

    if location_mode:
        score += 1.0
    if info_mode:
        score += 1.0

    return score
def choose_best_chunk(chunks: list[dict[str, Any]], info_mode: bool) -> dict[str, Any] | None:
    if not chunks:
        return None
    best = chunks[0]
    if not info_mode:
        return best

    if best['heading'] in {'Manual referenca', 'NOTE:', 'Page 15', 'Page 26', 'Page 29'} and len(chunks) > 1:
        runner_up = chunks[1]
        if runner_up['score'] >= best['score'] - 1.5:
            return runner_up

    if best['heading'].startswith('Stranica ') and len(chunks) > 1:
        runner_up = chunks[1]
        if runner_up['score'] >= best['score'] - 1.0:
            return runner_up

    return best



def rank_results(query_text: str) -> dict[str, Any]:
    expanded_query = expand_query(query_text)
    normalized_query = normalize_text(expanded_query)
    tokens = set(tokenize(expanded_query))
    location_mode = is_location_query(query_text)
    info_mode = is_info_query(query_text)

    warning_matches: list[dict[str, Any]] = []
    for warning in WARNING_LIGHTS['warnings']:
        score = score_warning(normalized_query, tokens, warning, location_mode)
        if score > 0:
            warning_matches.append({**warning, 'score': round(score, 2)})
    warning_matches.sort(key=lambda item: (-item['score'], -SEVERITY_ORDER.get(item['severity'], 0), item['name']))
    if location_mode or info_mode:
        warning_matches = [item for item in warning_matches if item['score'] >= 2.5]

    chunk_matches: list[dict[str, Any]] = []
    for chunk in MANUAL_CHUNKS['chunks']:
        score = score_chunk(normalized_query, tokens, chunk, location_mode)
        if score >= 2:
            chunk_matches.append(
                {
                    'chunk_id': chunk['chunk_id'],
                    'page': chunk['page'],
                    'heading': clean_heading(chunk['heading']),
                    'preview': clean_excerpt(chunk['preview']),
                    'score': round(score, 2),
                }
            )
    chunk_matches.sort(key=lambda item: (-item['score'], item['page']))

    if len(chunk_matches) < 3:
        page_matches: list[dict[str, Any]] = []
        for page in MANUAL_PAGES['pages']:
            score = score_page(normalized_query, tokens, page, location_mode, info_mode)
            if score >= 2.2:
                page_matches.append(
                    {
                        'chunk_id': f"page-{page['page']}",
                        'page': page['page'],
                        'heading': f"Stranica {page['page']}",
                        'preview': clean_excerpt(page.get('preview', '')),
                        'score': round(score, 2),
                    }
                )
        page_matches.sort(key=lambda item: (-item['score'], item['page']))
        seen = {item['page'] for item in chunk_matches}
        for item in page_matches:
            if item['page'] in seen:
                continue
            chunk_matches.append(item)
            seen.add(item['page'])
            if len(chunk_matches) >= 6:
                break

    return {
        'expanded_query': expanded_query,
        'location_mode': location_mode,
        'info_mode': info_mode,
        'warnings': warning_matches[:5],
        'chunks': chunk_matches[:6],
    }



def pick_reference(ranked: dict[str, Any]) -> dict[str, Any] | None:
    location_mode = ranked.get('location_mode', False)
    info_mode = ranked.get('info_mode', False)
    top_chunk = choose_best_chunk(ranked['chunks'], info_mode)
    top_warning = ranked['warnings'][0] if ranked['warnings'] else None

    if top_chunk and (location_mode or info_mode or not top_warning or top_chunk['score'] >= top_warning['score']):
        page_info = PAGE_LOOKUP.get(top_chunk['page'], {})
        return {
            'page': top_chunk['page'],
            'title': top_chunk['heading'],
            'caption': clean_excerpt(page_info.get('preview', top_chunk['preview'])),
            'source': 'manual_chunk',
        }

    if top_warning and top_warning.get('manual_pages'):
        page = int(top_warning['manual_pages'][0])
        page_info = PAGE_LOOKUP.get(page, {})
        return {
            'page': page,
            'title': top_warning['name'],
            'caption': clean_excerpt(page_info.get('preview', top_warning['summary'])),
            'source': 'warning_catalog',
        }

    return None



def build_local_diagnosis(query_text: str, ranked: dict[str, Any], reference: dict[str, Any] | None) -> dict[str, Any]:
    location_mode = ranked.get('location_mode', False)
    info_mode = ranked.get('info_mode', False)
    top_warning = ranked['warnings'][0] if ranked['warnings'] else None
    top_chunk = choose_best_chunk(ranked['chunks'], info_mode)

    if reference and (location_mode or info_mode):
        title = friendly_query_title(query_text, reference['title'])
        severity = 'low'
        overview = f"Najrelevantniji pogodak za tvoj upit pronađen je na stranici {reference['page']} u lokalnom Nissan manualu."
        next_steps = 'Pogledaj prikaz iz PDF-a ispod i po potrebi otvori punu stranicu manuala.'
        confidence = 'visoka' if top_chunk and top_chunk['score'] >= 6 else 'srednja'
    elif top_warning:
        title = top_warning['name']
        severity = top_warning['severity']
        overview = top_warning['summary']
        next_steps = top_warning['driver_action']
        confidence = 'visoka' if top_warning['score'] >= 8 else 'srednja'
    elif top_chunk:
        title = top_chunk['heading']
        severity = 'medium'
        overview = top_chunk['preview']
        next_steps = 'Pogledaj prikaz iz PDF-a i uporedi ga sa komandama ili porukom koju tražiš.'
        confidence = 'srednja'
    else:
        title = 'Nije pronađen jasan pogodak'
        severity = 'low'
        overview = 'Upit nije dovoljno precizan da bi se pouzdano povezao sa dijelom vozila ili procedurom iz priručnika.'
        next_steps = 'Pokušaj preciznije: npr. "gdje su prednja svjetla za maglu" ili "kako uključiti zadnji brisač".'
        confidence = 'niska'

    notes = [f'Aktivni manual: {MANUAL_TITLE}.', MANUAL_NOTE]
    if ranked.get('expanded_query') and normalize_text(ranked['expanded_query']) != normalize_text(query_text):
        notes.append('Upit je proširen lokalnim sinonimima kako bi pretraga bolje pogodila engleski manual.')
    if reference:
        notes.append(f"Najrelevantnija stranica za prikaz: {reference['page']}.")

    return {
        'title': title,
        'severity': severity,
        'severity_label': SEVERITY_LABELS[severity],
        'overview': overview,
        'next_steps': next_steps,
        'confidence': confidence,
        'notes': notes,
    }



def preview_terms(query_text: str, ranked: dict[str, Any], reference: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    terms.extend(tokenize(expand_query(query_text)))
    terms.extend(tokenize(reference['title']))
    top_chunk = ranked['chunks'][0] if ranked['chunks'] else None
    if top_chunk:
        terms.extend(tokenize(top_chunk['heading']))
    unique: list[str] = []
    for term in terms:
        if len(term) < 4 or term in unique:
            continue
        unique.append(term)
    return unique[:10]



def render_preview_image(page_number: int, terms: list[str]) -> str:
    fingerprint = hashlib.sha1(f'{page_number}|{"|".join(terms)}'.encode('utf-8')).hexdigest()[:16]
    filename = f'page-{page_number}-{fingerprint}.png'
    target = PREVIEW_DIR / filename
    if target.exists():
        return f'/previews/{filename}'

    page = MANUAL_DOC.load_page(page_number - 1)
    rects: list[fitz.Rect] = []
    for term in terms:
        rects.extend(page.search_for(term))
        if len(rects) >= 6:
            break

    clip = None
    scale = 1.35
    if rects:
        clip = fitz.Rect(rects[0])
        for rect in rects[1:6]:
            clip |= rect
        margin_x = max(90, clip.width * 0.8)
        margin_y = max(120, clip.height * 1.4)
        clip = fitz.Rect(clip.x0 - margin_x, clip.y0 - margin_y, clip.x1 + margin_x, clip.y1 + margin_y)
        clip &= page.rect
        scale = 2.2

    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
    target.write_bytes(pixmap.tobytes('png'))
    return f'/previews/{filename}'



def build_preview_payload(query_text: str, ranked: dict[str, Any]) -> dict[str, Any] | None:
    reference = pick_reference(ranked)
    if not reference:
        return None
    terms = preview_terms(query_text, ranked, reference)
    image_url = render_preview_image(reference['page'], terms)
    return {
        'title': friendly_query_title(query_text, reference['title']),
        'page': reference['page'],
        'caption': reference['caption'],
        'image_url': image_url,
        'pdf_url': f'/manual.pdf#page={reference["page"]}',
        'source': reference['source'],
    }



def parse_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get('Content-Length', '0'))
    body = handler.rfile.read(length)
    return json.loads(body.decode('utf-8')) if body else {}



def json_response(handler: BaseHTTPRequestHandler, payload: dict[str, Any], status: int = 200) -> None:
    encoded = json.dumps(payload).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(encoded)))
    handler.send_header('Cache-Control', 'no-store')
    handler.end_headers()
    handler.wfile.write(encoded)



def serve_file(handler: BaseHTTPRequestHandler, target: Path) -> None:
    if not target.exists() or not target.is_file():
        handler.send_error(HTTPStatus.NOT_FOUND, 'File not found')
        return
    mime_type, _ = mimetypes.guess_type(str(target))
    data = target.read_bytes()
    handler.send_response(200)
    handler.send_header('Content-Type', mime_type or 'application/octet-stream')
    handler.send_header('Content-Length', str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)



def serve_static(handler: BaseHTTPRequestHandler, path: str) -> None:
    serve_file(handler, STATIC_DIR / path.lstrip('/'))


class NissanDiagnosticHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path in {'/', '/index.html'}:
            serve_static(self, '/index.html')
            return

        if path == '/api/config':
            json_response(
                self,
                {
                    'mode': 'local-manual',
                    'manual_title': MANUAL_TITLE,
                    'manual_source': MANUAL_SOURCE,
                    'manual_note': MANUAL_NOTE,
                    'warning_count': len(WARNING_LIGHTS['warnings']),
                    'chunk_count': MANUAL_CHUNKS['chunk_count'],
                },
            )
            return

        if path == '/manual.pdf':
            serve_file(self, MANUAL_PDF_PATH)
            return

        if path.startswith('/previews/'):
            serve_file(self, PREVIEW_DIR / path.split('/previews/', 1)[1])
            return

        static_target = STATIC_DIR / path.lstrip('/')
        if static_target.exists() and static_target.is_file():
            serve_file(self, static_target)
            return

        self.send_error(HTTPStatus.NOT_FOUND, 'Not found')

    def do_POST(self) -> None:
        if self.path == '/api/search':
            try:
                payload = parse_json_body(self)
                query_text = str(payload.get('query', '')).strip()
                if not query_text:
                    json_response(self, {'error': 'Unesi pitanje ili naziv komande koju tražiš u vozilu.'}, status=400)
                    return
                ranked = rank_results(query_text)
                reference = pick_reference(ranked)
                preview = build_preview_payload(query_text, ranked)
                diagnosis = build_local_diagnosis(query_text, ranked, reference)
                json_response(self, {'diagnosis': diagnosis, 'matches': ranked, 'preview': preview})
                return
            except json.JSONDecodeError:
                json_response(self, {'error': 'Neispravan JSON payload.'}, status=400)
                return
            except Exception as exc:
                json_response(self, {'error': f'Greška pri pretrazi manuala: {exc}'}, status=500)
                return

        self.send_error(HTTPStatus.NOT_FOUND, 'Not found')

    def log_message(self, fmt: str, *args: Any) -> None:
        return


if __name__ == '__main__':
    server = ThreadingHTTPServer((HOST, PORT), NissanDiagnosticHandler)
    print(f'Serving Nissan manual assistant on http://127.0.0.1:{PORT}')
    server.serve_forever()





