# Nissan e-POWER Manual Asistent

Lokalna web aplikacija za pretragu Nissan X-Trail e-POWER priručnika na bosanskom jeziku.

Korisnik postavlja pitanje kao što su:

- `gdje su svjetla za maglu`
- `kako uključiti zadnji brisač`
- `gdje je grijanje sjedišta`
- `šta znači brake warning light`

Aplikacija zatim:

1. proširi upit lokalnim sinonimima
2. pronađe najrelevantnije sekcije u manualu
3. prikaže rezultat i izrez iz PDF priručnika gdje se traženi dio nalazi
4. ponudi link na punu PDF stranicu

## Aktivni manual

Projekt je trenutno podešen na službeni Nissan PDF `nissan-xtrail-epower-2024-ht33-e1-4wd.pdf`, odnosno **Nissan X-Trail Owner's Manual** za HT33 e-POWER 2024 4WD modele.

Ako želiš promijeniti manual:

1. ubaci drugi PDF u root projekta
2. postavi `MANUAL_PDF` u `.env`
3. pokreni `python scripts/extract_manual.py`

## Funkcije

- lokalna pretraga manuala bez cloud servisa
- bosanski upiti sa lokalnim sinonimima za engleski manual
- pronalazak najrelevantnije stranice i sekcije
- generisanje PNG prikaza iz PDF manuala
- otvaranje pune PDF stranice iz preglednika
- lokalna warning light baza za dijagnostičke upite

## Struktura repoa

- `app.py` - Python HTTP server i API
- `manual_utils.py` - učitavanje `.env`, izbor PDF-a i detekcija metadata manuala
- `static/` - frontend i generisani preview PNG fajlovi
- `data/manual_pages.json` - tekst manuala po stranicama
- `data/manual_chunks.json` - segmentirani manual za pretragu
- `data/warning_lights.json` - warning light baza
- `scripts/extract_manual.py` - ekstrakcija iz PDF-a
- `scripts/smoke_test.py` - osnovni smoke test

## Lokalno pokretanje

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Aplikacija radi na [http://localhost:8000](http://localhost:8000).

## Environment varijable

Aplikacija automatski učitava `.env` iz root foldera.

Primjer `.env`:

```bash
MANUAL_PDF=nissan-xtrail-epower-2024-ht33-e1-4wd.pdf
HOST=0.0.0.0
PORT=8000
```

Kad promijeniš `MANUAL_PDF` ili zamijeniš PDF, ponovo pokreni:

```bash
python scripts/extract_manual.py
```

## Test

```bash
python scripts/smoke_test.py
```

## Autor

A. Catovic
