# Nissan e-POWER Diagnostic App

Web aplikacija za Nissan e-POWER dijagnostiku sa dva ulaza:

- tekstualni opis problema, poruke sa ekrana ili tražene komande
- upload slike ili screenshot-a instrument table

Aplikacija zatim vraća najbliži dijagnostički zaključak, hitnost, preporučenu narednu radnju i reference iz lokalnog priručnika.

## Važna napomena

PDF koji se trenutno nalazi u ovom repou je `epower nissan manual.pdf`, ali se u samom dokumentu identifikuje kao **Nissan Qashqai Owner's Manual**. Znači: aplikacija trenutno koristi taj manual kao bazu znanja. Ako želiš pravi X-Trail e-POWER asistent, zamijeni PDF odgovarajućim X-Trail priručnikom i pokreni:

```bash
python scripts/extract_manual.py
```

## Funkcije

- pretraga po simptomu, lampici ili tekstu sa ekrana
- ranking relevantnih sekcija iz priručnika
- lokalna baza ključnih warning light stavki
- upload slike ili screenshot-a
- vision analiza slike preko OpenAI API-ja ako postoji `OPENAI_API_KEY`
- fallback režim bez vision-a: radi samo iz teksta i lokalnog manuala

## Struktura repoa

- `app.py` - Python HTTP server i API
- `static/` - frontend
- `data/manual_pages.json` - tekst manuala po stranicama
- `data/manual_chunks.json` - segmentirani manual za pretragu
- `data/warning_lights.json` - kurirana warning light baza
- `scripts/extract_manual.py` - ekstrakcija iz PDF-a
- `scripts/smoke_test.py` - osnovni smoke test
- `.github/workflows/ci.yml` - GitHub Actions CI
- `Dockerfile` - univerzalni deploy za Render/Railway/Fly.io i slične servise
- `render.yaml` - Render blueprint
- `.env.example` - primjer environment varijabli

## Lokalno pokretanje

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Aplikacija radi na [http://localhost:8000](http://localhost:8000).

## Environment varijable

Kopiraj `.env.example` u `.env` ili postavi varijable ručno:

```bash
set OPENAI_API_KEY=your_key_here
set OPENAI_MODEL=gpt-4.1-mini
set HOST=0.0.0.0
set PORT=8000
```

Ako `OPENAI_API_KEY` nije postavljen, upload slike se i dalje prihvata, ali bez stvarne vizuelne analize slike.

## GitHub spremno

Repo je pripremljen za GitHub sa:

- `.gitignore`
- `LICENSE`
- `README.md`
- `.env.example`
- GitHub Actions CI workflow-om
- smoke test skriptom
- Docker deploy fajlovima

## Kako objaviti na GitHub

Pošto na ovom računaru `git` trenutno nije dostupan u terminalu, push ne mogu završiti iz ovog okruženja. Kad instaliraš Git ili otvoriš folder u okruženju gdje Git postoji, koristi:

```bash
git init
git add .
git commit -m "Initial commit: Nissan e-POWER diagnostic app"
git branch -M main
git remote add origin https://github.com/TVOJ_USERNAME/TVOJ_REPO.git
git push -u origin main
```

## Deploy opcija 1: Render

Najjednostavnije za ovaj repo.

1. Push repo na GitHub.
2. Na Renderu izaberi `New +` -> `Blueprint` ili `Web Service`.
3. Poveži GitHub repo.
4. Ako koristiš `render.yaml`, Render će sam prepoznati Docker deploy.
5. U Render environment varijable dodaj `OPENAI_API_KEY` ako želiš vision analizu.

## Deploy opcija 2: Railway

1. Push repo na GitHub.
2. Na Railway izaberi `Deploy from GitHub repo`.
3. Railway će koristiti `Dockerfile`.
4. Dodaj `OPENAI_API_KEY` u Variables.

## Deploy opcija 3: Docker ručno

```bash
docker build -t nissan-epower-diagnostic .
docker run -p 8000:8000 --env OPENAI_API_KEY=your_key_here nissan-epower-diagnostic
```

## CI provjera lokalno

```bash
python -m py_compile app.py scripts/extract_manual.py scripts/smoke_test.py
python scripts/smoke_test.py
```

## Šta trebaš uraditi prije javnog objavljivanja

- zamijeni Qashqai PDF pravim X-Trail e-POWER manualom ako želiš tačnu bazu
- postavi svoj GitHub repo URL u komandama iznad
- po želji promijeni naziv Render servisa u `render.yaml`
- dodaj pravi `OPENAI_API_KEY` na hosting platformi, ne u repo
