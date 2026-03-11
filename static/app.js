const queryEl = document.getElementById('query');
const configBannerEl = document.getElementById('configBanner');
const resultPanelEl = document.getElementById('resultPanel');
const previewPanelEl = document.getElementById('previewPanel');
const matchesPanelEl = document.getElementById('matchesPanel');
const resultTitleEl = document.getElementById('resultTitle');
const severityBadgeEl = document.getElementById('severityBadge');
const resultOverviewEl = document.getElementById('resultOverview');
const resultNextStepsEl = document.getElementById('resultNextSteps');
const notesEl = document.getElementById('notes');
const warningMatchesEl = document.getElementById('warningMatches');
const chunkMatchesEl = document.getElementById('chunkMatches');
const previewTitleEl = document.getElementById('previewTitle');
const previewMetaEl = document.getElementById('previewMeta');
const previewImageEl = document.getElementById('previewImage');
const previewLinkEl = document.getElementById('previewLink');

function renderConfig(config) {
  configBannerEl.className = 'banner';
  configBannerEl.textContent = `Aktivni manual: ${config.manual_title}. Baza: ${config.warning_count} lampica i ${config.chunk_count} sekcija iz priručnika.`;
}

function renderError(message) {
  resultPanelEl.classList.remove('hidden');
  previewPanelEl.classList.add('hidden');
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
    warningMatchesEl.append(card('<h4>Nema direktnog warning pogotka</h4><p>To je očekivano kod pitanja o komandama, potrošnji ili zamjeni dijelova.</p>'));
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
    chunkMatchesEl.append(card('<h4>Nema dovoljno jake reference</h4><p>Pokušaj preciznije: npr. "kako zamijeniti prednju sijalicu" ili "gdje se mijenja prikaz instrument table".</p>'));
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

function renderPreview(preview) {
  if (!preview) {
    previewPanelEl.classList.add('hidden');
    return;
  }

  previewTitleEl.textContent = preview.title;
  previewMetaEl.textContent = `Stranica ${preview.page}. ${preview.caption}`;
  previewImageEl.src = preview.image_url;
  previewImageEl.alt = `Prikaz iz manuala, stranica ${preview.page}`;
  previewLinkEl.href = preview.pdf_url;
  previewPanelEl.classList.remove('hidden');
}

function renderDiagnosis(payload) {
  const { diagnosis, matches, preview } = payload;
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

  for (const note of diagnosis.notes || []) {
    const p = document.createElement('p');
    p.textContent = note;
    notesEl.append(p);
  }

  renderPreview(preview);
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

async function analyzeQuery() {
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

document.getElementById('searchBtn').addEventListener('click', analyzeQuery);
queryEl.addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    analyzeQuery();
  }
});

loadConfig();
