from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from manual_utils import detect_manual_metadata, load_dotenv, resolve_manual_pdf


load_dotenv(ROOT / '.env')
PDF_PATH = resolve_manual_pdf(ROOT)
OUTPUT_DIR = ROOT / 'data'
PAGES_PATH = OUTPUT_DIR / 'manual_pages.json'
CHUNKS_PATH = OUTPUT_DIR / 'manual_chunks.json'

MAX_CHUNK_CHARS = 1200


@dataclass
class ManualPage:
    page: int
    preview: str
    text: str


@dataclass
class ManualChunk:
    chunk_id: str
    page: int
    heading: str
    text: str
    preview: str


def normalize_text(raw: str) -> str:
    raw = raw.replace('\x00', ' ')
    raw = raw.replace('\r', '\n')
    raw = re.sub(r'[ \t]+', ' ', raw)
    raw = re.sub(r'\n{3,}', '\n\n', raw)
    return raw.strip()


def looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) < 4 or len(stripped) > 90:
        return False
    if stripped.startswith('GUID-') or stripped.startswith('[Model:'):
        return False
    letters = [ch for ch in stripped if ch.isalpha()]
    if not letters:
        return False
    uppercase_ratio = sum(1 for ch in letters if ch.isupper()) / len(letters)
    title_case = stripped[:1].isupper() and stripped.count(' ') < 10
    return uppercase_ratio > 0.7 or (
        title_case
        and any(token in stripped.lower() for token in ('warning', 'indicator', 'system', 'mode', 'display', 'gauge'))
    )


def build_chunks(page_number: int, text: str) -> list[ManualChunk]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    chunks: list[ManualChunk] = []
    current_heading = f'Page {page_number}'
    buffer: list[str] = []
    chunk_index = 1

    def flush() -> None:
        nonlocal buffer, chunk_index
        if not buffer:
            return
        chunk_text = ' '.join(buffer).strip()
        if not chunk_text:
            buffer = []
            return
        preview = chunk_text[:180].strip()
        chunks.append(
            ManualChunk(
                chunk_id=f'p{page_number:03d}-c{chunk_index:02d}',
                page=page_number,
                heading=current_heading,
                text=chunk_text,
                preview=preview,
            )
        )
        chunk_index += 1
        buffer = []

    for line in lines:
        if looks_like_heading(line):
            flush()
            current_heading = line
            continue

        candidate = ' '.join(buffer + [line]).strip()
        if len(candidate) > MAX_CHUNK_CHARS:
            flush()
        buffer.append(line)

    flush()
    return chunks


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    reader = PdfReader(str(PDF_PATH))
    preview_text = '\n'.join((reader.pages[idx].extract_text() or '') for idx in range(min(3, len(reader.pages))))
    metadata = detect_manual_metadata(preview_text, PDF_PATH.name)

    pages: list[ManualPage] = []
    chunks: list[ManualChunk] = []

    for idx, page in enumerate(reader.pages, start=1):
        text = normalize_text(page.extract_text() or '')
        preview = text[:180].strip()
        pages.append(ManualPage(page=idx, preview=preview, text=text))
        chunks.extend(build_chunks(idx, text))

    pages_payload = {
        'source_pdf': PDF_PATH.name,
        'source_pdf_path': str(PDF_PATH),
        'manual_title': metadata['manual_title'],
        'model_code': metadata['model_code'],
        'manual_note': metadata['manual_note'],
        'page_count': len(pages),
        'pages': [asdict(page) for page in pages],
    }
    chunks_payload = {
        'source_pdf': PDF_PATH.name,
        'source_pdf_path': str(PDF_PATH),
        'manual_title': metadata['manual_title'],
        'model_code': metadata['model_code'],
        'manual_note': metadata['manual_note'],
        'chunk_count': len(chunks),
        'chunks': [asdict(chunk) for chunk in chunks],
    }

    PAGES_PATH.write_text(json.dumps(pages_payload, ensure_ascii=True, indent=2), encoding='utf-8')
    CHUNKS_PATH.write_text(json.dumps(chunks_payload, ensure_ascii=True, indent=2), encoding='utf-8')

    print(f"Using manual: {metadata['manual_title']} ({PDF_PATH.name})")
    print(f'Wrote {len(pages)} pages to {PAGES_PATH}')
    print(f'Wrote {len(chunks)} chunks to {CHUNKS_PATH}')


if __name__ == '__main__':
    main()
