const queryEl = document.getElementById('query');
const imageEl = document.getElementById('image');
const imageMetaEl = document.getElementById('imageMeta');
const configBannerEl = document.getElementById('configBanner');
const resultPanelEl = document.getElementById('resultPanel');
const matchesPanelEl = document.getElementById('matchesPanel');
const resultTitleEl = document.getElementById('resultTitle');
const severityBadgeEl = document.getElementById('severityBadge');
const resultOverviewEl = document.getElementById('resultOverview');
const resultNextStepsEl = document.getElementById('resultNextSteps');
const notesEl = document.getElementById('notes');
const warningMatchesEl = document.getElementById('warningMatches');
const chunkMatchesEl = document.getElementById('chunkMatches');

function renderConfig(config) {
  const mode = config.vision_enabled
    ? `Vision analiza je uključena preko modela ${config.model}.`
    : 'Vision analiza nije aktivna dok ne postaviš OPENAI_API_KEY u okruženje servera.';

  configBannerEl.className = 'banner';
  configBannerEl.textContent = `${mode} Baza: ${config.warning_count} lampica i ${config.chunk_count} sekcija iz priručnika. Napomena: ${config.manual_note}`;
}

function renderError(message) {
  resultPanelEl.classList.remove('hidden');
  matchesPanelEl.classList.add('hidden');
  resultTitleEl.textContent = 'Greška';
  severityBadgeEl.textContent = 'Provjeri unos';
  severityBadgeEl.className = 'badge medium';
  resultOverviewEl.textContent = message;
  resultNextStepsEl.textContent = '';
  notesEl.innerHTML = '';
}

function card(html) {
  const node = document.createElement('article');
  node.className = 'card';
  node.innerHTML = html;
  return node;
}

function renderMatches(matches) {
  warningMatchesEl.innerHTML = '';
  chunkMatchesEl.innerHTML = '';

  if (!matches.warnings.length) {
    warningMatchesEl.append(card('<h4>Nema direktnog pogotka</h4><p>Pokušaj unijeti tačan naziv lampice ili tekst poruke sa ekrana.</p>'));
  }

  for (const item of matches.warnings) {
    warningMatchesEl.append(
      card(`
        <h4>${item.name}</h4>
        <p>${item.summary}</p>
        <p class="meta">Prioritet: ${item.severity}. Stranice: ${item.manual_pages.join(', ')}. Score: ${item.score}</p>
      `),
    );
  }

  if (!matches.chunks.length) {
    chunkMatchesEl.append(card('<h4>Nema relevantne reference</h4><p>Upit je previše općenit ili nije pronađen u priručniku.</p>'));
  }

  for (const item of matches.chunks) {
    chunkMatchesEl.append(
      card(`
        <h4>${item.heading}</h4>
        <p>${item.preview}</p>
        <p class="meta">Stranica ${item.page}. Score: ${item.score}</p>
      `),
    );
  }

  matchesPanelEl.classList.remove('hidden');
}

function renderDiagnosis(payload) {
  const { diagnosis, matches, vision_used: visionUsed } = payload;
  resultPanelEl.classList.remove('hidden');
  resultTitleEl.textContent = diagnosis.title;
  severityBadgeEl.textContent = diagnosis.severity_label;
  severityBadgeEl.className = `badge ${diagnosis.severity}`;
  resultOverviewEl.textContent = diagnosis.overview;
  resultNextStepsEl.textContent = `Preporuka: ${diagnosis.next_steps}`;
  notesEl.innerHTML = '';

  const confidence = document.createElement('p');
  confidence.textContent = `Pouzdanost procjene: ${diagnosis.confidence}.`;
  notesEl.append(confidence);

  if (typeof visionUsed === 'boolean') {
    const mode = document.createElement('p');
    mode.textContent = visionUsed
      ? 'Slika je analizirana uz vision model.'
      : 'Slika nije vizuelno analizirana; korišten je samo tekstualni opis i lokalna baza znanja.';
    notesEl.append(mode);
  }

  for (const note of diagnosis.notes || []) {
    const p = document.createElement('p');
    p.textContent = note;
    notesEl.append(p);
  }

  renderMatches(matches);
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || 'Nepoznata greška.');
  }
  return data;
}

async function loadConfig() {
  try {
    const config = await fetchJson('/api/config');
    renderConfig(config);
  } catch (error) {
    configBannerEl.textContent = error.message;
  }
}

async function analyzeText() {
  const query = queryEl.value.trim();
  try {
    const payload = await fetchJson('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });
    renderDiagnosis(payload);
  } catch (error) {
    renderError(error.message);
  }
}

async function analyzeImage() {
  const file = imageEl.files[0];
  if (!file) {
    renderError('Odaberi sliku ili screenshot prije analize slike.');
    return;
  }

  const form = new FormData();
  form.append('query', queryEl.value.trim());
  form.append('image', file);

  try {
    const payload = await fetchJson('/api/analyze-image', {
      method: 'POST',
      body: form,
    });
    renderDiagnosis(payload);
  } catch (error) {
    renderError(error.message);
  }
}

imageEl.addEventListener('change', () => {
  const file = imageEl.files[0];
  imageMetaEl.textContent = file
    ? `${file.name} | ${(file.size / 1024 / 1024).toFixed(2)} MB | ${file.type || 'nepoznat tip'}`
    : 'Nema odabrane slike.';
});

document.getElementById('searchBtn').addEventListener('click', analyzeText);
document.getElementById('analyzeBtn').addEventListener('click', analyzeImage);

loadConfig();
