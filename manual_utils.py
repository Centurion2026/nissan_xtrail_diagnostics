from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


KNOWN_MODELS = ('X-TRAIL', 'XTRAIL', 'QASHQAI', 'JUKE', 'ARIYA', 'LEAF', 'MICRA', 'NAVARA', 'TOWNSTAR', 'PRIMASTAR')


def load_dotenv(dotenv_path: Path, override: bool = False) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding='utf-8-sig').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].strip()
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value[:1] == value[-1:] and value[:1] in {'"', "'"}:
            value = value[1:-1]
        if override or key not in os.environ:
            os.environ[key] = value


def resolve_manual_pdf(root: Path) -> Path:
    manual_pdf = os.getenv('MANUAL_PDF', '').strip()
    if manual_pdf:
        candidate = Path(manual_pdf)
        if not candidate.is_absolute():
            candidate = root / candidate
        if candidate.exists() and candidate.is_file():
            return candidate
        raise FileNotFoundError(f'MANUAL_PDF points to a missing file: {candidate}')

    pdfs = sorted(path for path in root.glob('*.pdf') if path.is_file())
    if not pdfs:
        raise FileNotFoundError(f'No PDF manuals found in {root}')

    legacy_default = root / 'epower nissan manual.pdf'
    if legacy_default in pdfs:
        return legacy_default
    if len(pdfs) == 1:
        return pdfs[0]

    names = ', '.join(path.name for path in pdfs)
    raise RuntimeError(f'Multiple PDF manuals found. Set MANUAL_PDF in .env to choose one: {names}')


def detect_manual_metadata(first_pages_text: str, pdf_name: str) -> dict[str, Any]:
    compact = ' '.join(first_pages_text.split())
    upper = compact.upper()

    model_pattern = '|'.join(re.escape(model) for model in KNOWN_MODELS)
    manual_title = None

    specific_match = re.search(rf"((?:NISSAN\s+)?(?:{model_pattern})[A-Z0-9\-/ ]*?\s+OWNER'S MANUAL)", upper)
    if specific_match:
        manual_title = re.sub(r'\s+', ' ', specific_match.group(1)).strip()
        if not manual_title.startswith('NISSAN '):
            manual_title = f'NISSAN {manual_title}'
    else:
        generic_match = re.search(r"(NISSAN\s+[A-Z0-9\-/ ]+?\s+OWNER'S MANUAL)", upper)
        if generic_match:
            manual_title = re.sub(r'\s+', ' ', generic_match.group(1)).strip()

    model_match = re.search(r'\[Model:\s*([^\]]+)\]', first_pages_text, re.IGNORECASE)
    model_code = model_match.group(1).strip() if model_match else None

    if manual_title:
        display_title = manual_title.title().replace("Owner'S", "Owner's")
    else:
        display_title = pdf_name

    if manual_title and 'QASHQAI' in manual_title:
        note = (
            f'Detected manual: {display_title}. '
            'Replace the PDF or set MANUAL_PDF if you need X-Trail-specific guidance.'
        )
    elif manual_title and ('X-TRAIL' in manual_title or 'XTRAIL' in manual_title):
        note = f'Detected manual: {display_title}.'
    else:
        note = f'Detected manual source: {display_title}.'

    return {
        'manual_title': display_title,
        'model_code': model_code,
        'manual_note': note,
    }
