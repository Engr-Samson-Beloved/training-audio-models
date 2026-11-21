const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let statusData;
let mediaRecorder, microphoneStream, recordingChunks = [], recordingBlob, previewUrl;

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
  const publicResults = data.completed_public_results || [];
  $('#publicResultRows').innerHTML = publicResults.length ? publicResults.map(x=>`<tr><td><b>${esc(x.model)}</b></td><td>${x.training_hours ? `${x.training_hours} h` : 'zero-shot'}</td><td>${x.seeds}</td><td>${(x.wer*100).toFixed(2)}%</td><td>${(x.cer*100).toFixed(2)}%</td><td>${(x.wer_ci95[0]*100).toFixed(2)}%–${(x.wer_ci95[1]*100).toFixed(2)}%</td></tr>`).join('') : '<tr><td colspan="6" class="muted">No completed public-model results yet.</td></tr>';
  $('#plots').innerHTML = data.plots.map(url=>`<img src="${esc(url)}?t=${Date.now()}" alt="Fixture evaluation plot">`).join('') || '<p class="muted">Run the fixture simulation to create plots.</p>';
  $('#audioList').innerHTML = data.audio.map(x=>`<div class="audio-item"><strong>${esc(x.utterance_id)}</strong><span>${esc(x.transcript)}</span><audio controls preload="none" src="${esc(x.url)}"></audio></div>`).join('');
  const intake = data.recording_intake || {queued: 0, max_megabytes: 25};
  $('#recordQueue').textContent = `${intake.queued} PENDING REVIEW`;
  $('#recordLimit').textContent = intake.max_megabytes;
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

function recordingStatus(message, kind='') { $('#recordStatus').textContent = message; $('#recordStatus').className = `record-status ${kind}`; }
function resetRecording() {
  recordingBlob = undefined; recordingChunks = [];
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = undefined; $('#recordPreview').hidden = true; $('#recordPreview').removeAttribute('src');
  $('#submitRecording').disabled = true; $('#discardRecording').disabled = true; $('#startRecording').disabled = !$('#consentAck').checked;
}
function stopMicrophone() { if (microphoneStream) microphoneStream.getTracks().forEach(track => track.stop()); microphoneStream = undefined; }
async function startRecording() {
  resetRecording();
  try {
    microphoneStream = await navigator.mediaDevices.getUserMedia({audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true}});
    const type = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm';
    mediaRecorder = new MediaRecorder(microphoneStream, {mimeType: type});
    mediaRecorder.ondataavailable = event => { if (event.data.size) recordingChunks.push(event.data); };
    mediaRecorder.onstop = () => {
      recordingBlob = new Blob(recordingChunks, {type: mediaRecorder.mimeType || 'audio/webm'});
      previewUrl = URL.createObjectURL(recordingBlob); $('#recordPreview').src = previewUrl; $('#recordPreview').hidden = false;
      $('#submitRecording').disabled = false; $('#discardRecording').disabled = false; $('#startRecording').disabled = !$('#consentAck').checked;
      $('#stopRecording').disabled = true; recordingStatus(`Recorded ${(recordingBlob.size / 1024 / 1024).toFixed(2)} MB. Listen, then submit for review.`,'success'); stopMicrophone();
    };
    mediaRecorder.start(); $('#startRecording').disabled = true; $('#stopRecording').disabled = false; recordingStatus('Recording in progress. Read the transcript exactly.','recording');
  } catch (error) { stopMicrophone(); recordingStatus(`Microphone access failed: ${error.message || error}`,'error'); }
}
$('#consentAck').addEventListener('change', event => { $('#startRecording').disabled = !event.target.checked || Boolean(mediaRecorder && mediaRecorder.state === 'recording'); if (!event.target.checked) recordingStatus('Consent acknowledgement is required before recording.'); });
$('#startRecording').addEventListener('click', startRecording);
$('#stopRecording').addEventListener('click', () => { if (mediaRecorder && mediaRecorder.state === 'recording') mediaRecorder.stop(); });
$('#discardRecording').addEventListener('click', () => { resetRecording(); recordingStatus('Recording discarded. You can make a new recording.'); });
$('#recordForm').addEventListener('submit', async event => {
  event.preventDefault();
  if (!recordingBlob) return recordingStatus('Record a voice sample before submitting.','error');
  const form = new FormData(event.currentTarget); form.set('audio', recordingBlob, 'recording.webm');
  const button = $('#submitRecording'); button.disabled = true; recordingStatus('Uploading securely to the local review queue...');
  try {
    const response = await fetch('/api/recordings', {method: 'POST', body: form}); const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Upload failed.');
    recordingStatus(`Submitted as ${result.recording_id}. Status: pending review.`, 'success'); event.currentTarget.reset(); resetRecording(); await refresh();
  } catch (error) { button.disabled = false; recordingStatus(error.message || 'Upload failed.','error'); }
});
refresh().catch(async () => {
  try { render(await (await fetch('/status.json')).json()); }
  catch (error) { $('#runOutput').textContent = `Dashboard status failed: ${error}`; }
});

