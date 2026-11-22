const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let statusData;
let mediaRecorder, microphoneStream, recordingChunks = [], recordingBlob, previewUrl;
let liveWalkthrough = false;
let walkthroughPhase = 0, walkthroughTimer;

document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => {
  document.querySelectorAll('.tab,.panel').forEach(el => el.classList.remove('active'));
  tab.classList.add('active'); $('#' + tab.dataset.panel).classList.add('active');
}));

function datasetCard(title, badge, description, stats, ready=true) {
  return `<article class="dataset-card ${ready?'ready':''}"><h3>${esc(title)}<span class="badge ${ready?'green':'gray'}">${esc(badge)}</span></h3>
    <p class="muted">${esc(description)}</p>
    <div class="dataset-stats">${stats.map(([value, label]) => `<div><b>${esc(value)}</b><span>${esc(label)}</span></div>`).join('')}</div></article>`;
}

function attachAudioAnimation() {
  document.querySelectorAll('.real-audio').forEach(audio => {
    const card = audio.closest('.audio-item');
    audio.addEventListener('play', () => card.classList.add('is-playing'));
    ['pause', 'ended'].forEach(event => audio.addEventListener(event, () => card.classList.remove('is-playing')));
  });
}

function render(data) {
  statusData = data; $('#studyContext').textContent = data.study_context;
  const activeTools = Object.entries(data.tools || {}).filter(([,v])=>v).map(([k])=>k).join(' · ');
  $('#toolStatus').textContent = activeTools ? `Installed: ${activeTools}` : 'Audio tools unavailable';
  const d = data.datasets;
  const publicResults = data.completed_public_results || [];
  const intake = data.recording_intake || {queued: 0, max_megabytes: 25};
  $('#overviewCards').innerHTML = [
    ['Real SLR70 speech', `${d.slr70.utterances} recordings`, `${d.slr70.hours} hours · ${d.slr70.speakers} speakers`],
    ['Measured models', publicResults.length, 'Completed public-data evaluations'],
    ['Manual recording', 'Ready', intake.queued ? `${intake.queued} queued for review` : 'Start collecting consented samples now'],
    ['Core aim', 'Compare ASR models', 'Measure which system transcribes best']
  ].map(([a,b,c])=>`<article class="metric"><div class="metric-label">${esc(a)}</div><div class="metric-value">${esc(b)}</div><div class="metric-note">${esc(c)}</div></article>`).join('');
  $('#datasetCards').innerHTML = [
    datasetCard('SLR70 Nigerian-English speech', 'READY', 'Real public speech recordings used for the completed model evaluations.', [[d.slr70.utterances, 'recordings'], [d.slr70.speakers, 'speakers'], [`${d.slr70.hours} h`, 'audio']]),
    datasetCard('Manual voice collection', 'READY TO RECORD', 'The recording form is ready now. New consented samples enter a review queue before they are considered for training.', [['Browser microphone', 'capture'], [intake.queued, 'queued'], ['Review first', 'workflow']]),
    datasetCard('System-check fixture', 'AVAILABLE', 'A small synthetic set used only to verify local software components.', [[d.fixture.utterances, 'test items'], ['Local', 'execution'], ['Optional', 'check']]),
  ].join('');
  $('#archiveChecklist').innerHTML = Object.entries(data.slr70_archives || {}).map(([name,ok])=>`<div class="check"><span class="dot ${ok?'ok':''}"></span><b>${esc(name)}</b><span class="muted">${ok?'found':'place in data/public/slr70/raw/'}</span></div>`).join('');
  $('#experimentRows').innerHTML = (data.experiments || []).map(x=>`<tr><td><b>${esc(x.id)}</b><br><span class="muted">${esc(x.file)}</span></td><td>${esc(x.model)}</td><td>${esc(x.mode)}</td><td>${x.seeds}</td><td>${x.hours.length?x.hours.join(', '):'—'}</td><td>${x.lm_rescoring.includes(true)?'Yes':'No'}</td></tr>`).join('');
  $('#publicResultRows').innerHTML = publicResults.length ? publicResults.map(x=>`<tr><td><b>${esc(x.model)}</b></td><td>${x.training_hours ? `${x.training_hours} h` : 'zero-shot'}</td><td>${x.seeds}</td><td>${(x.wer*100).toFixed(2)}%</td><td>${(x.cer*100).toFixed(2)}%</td><td>${(x.wer_ci95[0]*100).toFixed(2)}%–${(x.wer_ci95[1]*100).toFixed(2)}%</td></tr>`).join('') : '<tr><td colspan="6" class="muted">No completed public-model results yet.</td></tr>';
  $('#plots').innerHTML = (data.plots || []).map(url=>`<img src="${esc(url)}?t=${Date.now()}" alt="Fixture evaluation plot">`).join('') || '<p class="muted">Run the system check to create plots.</p>';
  $('#slr70AudioList').innerHTML = (data.slr70_audio || []).map(x=>`<div class="audio-item"><div class="audio-topline"><strong>${esc(x.speaker_id)}</strong><span>${esc(x.gender)} · ${Number(x.duration_seconds).toFixed(1)} sec</span></div><div class="sound-bars" aria-hidden="true">${'<i></i>'.repeat(18)}</div><audio class="real-audio" controls preload="none" src="${esc(x.url)}"></audio><span class="transcript-label">REFERENCE TRANSCRIPT</span><p>${esc(x.transcript)}</p></div>`).join('') || '<p class="muted">No SLR70 audio samples were found.</p>';
  attachAudioAnimation();
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
$('#openLiveDemo').addEventListener('click', () => document.querySelector('[data-panel="live"]').click());
$('#runFixture').addEventListener('click', async () => {
  const button = $('#runFixture'); button.disabled = true; button.textContent = 'System check running…';
  $('#runOutput').textContent = 'Executing local checks for data flow, scoring, intervals, and plots…';
  liveWalkthrough = true; walkthroughPhase = 0;
  document.querySelector('[data-panel="live"]').click();
  refreshLive();
  walkthroughTimer = setInterval(() => {
    walkthroughPhase = Math.min(walkthroughPhase + 1, liveStages.length - 1);
    refreshLive();
  }, 700);
  try {
    if (location.protocol === 'file:' || window.__STATIC_STATUS__) {
      throw new Error('This standalone view is read-only. Run ./scripts/run_fixture.sh in Terminal, then refresh the dashboard build.');
    }
    const response = await fetch('/api/run-fixture', {method:'POST'});
    if (!response.ok) throw new Error('The hosted view is read-only. Run ./scripts/launch_dashboard.sh locally for simulation controls.');
    const result = await response.json();
    $('#runOutput').textContent = result.output || 'System check finished.';
    if (result.status) render(result.status);
  } catch (error) { $('#runOutput').textContent = `System check failed: ${error}`; }
  finally {
    clearInterval(walkthroughTimer); walkthroughPhase = 0; liveWalkthrough = false;
    button.disabled = false; button.textContent = 'Run system check'; refreshLive();
  }
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

const liveStages = [
  ['dataset', 'Real speech is ready', 'SLR70 audio and transcripts are available'],
  ['validate', 'Validate audio', '16 kHz mono and manifest checks'],
  ['split', 'Freeze splits', 'Speaker-disjoint train, dev, and test'],
  ['run', 'Run models', 'Training or zero-shot transcription'],
  ['evaluate', 'Compare transcript to reference', 'WER, CER, intervals, and plots'],
];
function liveClass(state) { return state === 'running' ? 'active' : state === 'needs_attention' ? 'attention' : state === 'complete' ? 'done' : 'waiting'; }
function renderLive(data) {
  $('#liveConnection').textContent = 'LIVE'; $('#liveConnection').className = 'badge green';
  const active = data.active_run, attention = data.attention_run;
  let headline = 'Public-data pipeline is ready'; let detail = 'Completed results are available for Whisper, Wav2Vec2, and the classical baseline.';
  if (data.fixture.active) { headline = 'System check is executing'; detail = 'The local check is validating data flow, splitting, scoring, and plots right now.'; }
  else if (liveWalkthrough) { headline = 'System check completed'; detail = 'The local validation ran successfully; the animation is replaying each checked stage.'; }
  else if (active) { headline = `${active.experiment_id} is running`; detail = `${active.complete_seeds}/${active.expected_seeds} seed outputs saved. ${active.worker ? `${active.worker.cpu_percent}% CPU in use.` : ''}`; }
  else if (attention) { headline = `${attention.experiment_id} needs attention`; detail = 'Its saved record is incomplete and no matching local worker is active. Completed results remain available for the other models.'; }
  $('#liveHeadline').textContent = headline; $('#liveDetail').textContent = detail;
  const stageStates = {dataset: 'complete', validate: 'complete', split: 'complete', run: active ? 'running' : attention ? 'needs_attention' : data.completed_runs ? 'complete' : 'waiting', evaluate: data.completed_runs ? 'complete' : 'waiting'};
  if (data.fixture.active || liveWalkthrough) {
    liveStages.forEach(([key], index) => { stageStates[key] = index < walkthroughPhase ? 'complete' : index === walkthroughPhase ? 'running' : 'waiting'; });
  }
  $('#pipelineSteps').innerHTML = liveStages.map(([key, title, subtitle], index) => `<div class="live-step ${liveClass(stageStates[key])}"><div class="live-node">${index + 1}</div><div><b>${esc(title)}</b><span>${esc(subtitle)}</span></div></div>`).join('');
  $('#liveCompleted').textContent = `${data.completed_runs}/${data.runs.length}`;
  $('#liveQueue').textContent = data.recording_queue;
  $('#liveUpdated').textContent = new Date(data.updated_at).toLocaleTimeString();
  $('#liveRunRows').innerHTML = data.runs.map(run => {
    const worker = run.worker ? `${run.worker.cpu_percent}% CPU · ${esc(run.worker.elapsed)}` : 'No local worker';
    const state = run.state.replaceAll('_', ' ');
    return `<tr><td><b>${esc(run.experiment_id)}</b></td><td>${run.complete_seeds}/${run.expected_seeds || '—'}</td><td><span class="live-chip ${liveClass(run.state)}">${esc(state)}</span></td><td>${worker}</td></tr>`;
  }).join('') || '<tr><td colspan="4" class="muted">No experiment records found.</td></tr>';
}
async function refreshLive() {
  try { const response = await fetch('/api/live', {cache: 'no-store'}); if (!response.ok) throw new Error(); renderLive(await response.json()); }
  catch { $('#liveConnection').textContent = 'OFFLINE'; $('#liveConnection').className = 'badge amber'; }
}
$('#openRealAudio').addEventListener('click', () => document.querySelector('[data-panel="overview"]').click());
setInterval(refreshLive, 2000);
refreshLive();
refresh().catch(async () => {
  try { render(await (await fetch('/status.json')).json()); }
  catch (error) { $('#runOutput').textContent = `Dashboard status failed: ${error}`; }
});

