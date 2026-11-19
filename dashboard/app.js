const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let statusData;

document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => {
  document.querySelectorAll('.tab,.panel').forEach(el => el.classList.remove('active'));
  tab.classList.add('active'); $('#' + tab.dataset.panel).classList.add('active');
}));

function datasetCard(name, title, data, primary=false) {
  const ready = data.ready;
  return `<article class="dataset-card ${ready?'ready':''}"><h3>${title}<span class="badge ${ready?'green':'gray'}">${ready?'READY':'WAITING'}</span></h3>
    <p class="muted">${primary?'Primary report dataset':'Development and pipeline validation only'}</p>
    <div class="dataset-stats"><div><b>${data.utterances}</b><span>utterances</span></div><div><b>${data.speakers}</b><span>speakers</span></div><div><b>${data.hours}</b><span>hours</span></div></div>
    <span class="badge ${primary?'green':'amber'}">${primary?'ORIGINAL CORPUS':'NOT ORIGINAL RESULTS'}</span></article>`;
}

function render(data) {
  statusData = data; $('#warningText').textContent = data.warning;
  const activeTools = Object.entries(data.tools).filter(([,v])=>v).map(([k])=>k).join(' · ');
  $('#toolStatus').textContent = activeTools ? `Installed: ${activeTools}` : 'Audio tools unavailable';
  const d = data.datasets;
  $('#overviewCards').innerHTML = [
    ['Fixture', d.fixture.ready?'Ready':'Waiting', `${d.fixture.utterances} synthetic records`],
    ['SLR70 public', d.slr70.ready?'Ready':'Archives needed', d.slr70.ready?`${d.slr70.hours} hours imported`:'0 public results'],
    ['Original corpus', d.original.ready?'Ready':'Recordings needed', 'Primary report evidence'],
    ['Experiments', data.experiments.length, 'Independent configurations']
  ].map(([a,b,c])=>`<article class="metric"><div class="metric-label">${esc(a)}</div><div class="metric-value">${esc(b)}</div><div class="metric-note">${esc(c)}</div></article>`).join('');
  $('#datasetCards').innerHTML = datasetCard('fixture','Tiny fixture',d.fixture) + datasetCard('slr70','OpenSLR SLR70',d.slr70) + datasetCard('original','Group 2 recordings',d.original,true);
  $('#archiveChecklist').innerHTML = Object.entries(data.slr70_archives).map(([name,ok])=>`<div class="check"><span class="dot ${ok?'ok':''}"></span><b>${esc(name)}</b><span class="muted">${ok?'found':'place in data/public/slr70/raw/'}</span></div>`).join('');
  $('#experimentRows').innerHTML = data.experiments.map(x=>`<tr><td><b>${esc(x.id)}</b><br><span class="muted">${esc(x.file)}</span></td><td>${esc(x.model)}</td><td>${esc(x.mode)}</td><td>${x.seeds}</td><td>${x.hours.length?x.hours.join(', '):'—'}</td><td>${x.lm_rescoring.includes(true)?'Yes':'No'}</td></tr>`).join('');
  $('#plots').innerHTML = data.plots.map(url=>`<img src="${esc(url)}?t=${Date.now()}" alt="Fixture evaluation plot">`).join('') || '<p class="muted">Run the fixture simulation to create plots.</p>';
  $('#audioList').innerHTML = data.audio.map(x=>`<div class="audio-item"><strong>${esc(x.utterance_id)}</strong><span>${esc(x.transcript)}</span><audio controls preload="none" src="${esc(x.url)}"></audio></div>`).join('');
}

async function refresh() {
  if (window.__STATIC_STATUS__) { render(window.__STATIC_STATUS__); return; }
  let response = await fetch('/api/status', {cache:'no-store'});
  if (!response.ok) response = await fetch('/status.json', {cache:'no-store'});
  render(await response.json());
}
$('#refresh').addEventListener('click', refresh);
$('#runFixture').addEventListener('click', async () => {
  const button = $('#runFixture'); button.disabled = true; button.textContent = 'Running simulation…';
  $('#runOutput').textContent = 'Executing the dependency-free fixture pipeline…';
  try {
    if (location.protocol === 'file:' || window.__STATIC_STATUS__) {
      throw new Error('This standalone view is read-only. Run ./scripts/run_fixture.sh in Terminal, then refresh the dashboard build.');
    }
    const response = await fetch('/api/run-fixture', {method:'POST'});
    if (!response.ok) throw new Error('The hosted view is read-only. Run ./scripts/launch_dashboard.sh locally for simulation controls.');
    const result = await response.json();
    $('#runOutput').textContent = result.output || 'Simulation finished.';
    if (result.status) render(result.status);
    document.querySelector('[data-panel="results"]').click();
  } catch (error) { $('#runOutput').textContent = `Simulation failed: ${error}`; }
  finally { button.disabled = false; button.textContent = 'Run fixture simulation'; }
});
refresh().catch(async () => {
  try { render(await (await fetch('/status.json')).json()); }
  catch (error) { $('#runOutput').textContent = `Dashboard status failed: ${error}`; }
});

