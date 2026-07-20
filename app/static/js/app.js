// ----- Version check: force reload propre si la version serveur change -----
(async function ensureFreshAssets(){
  try {
    const root = (document.querySelector('meta[name="app-root"]')?.content || '').replace(/\/+$/, '');
    const vUrl = `${root}/version`;
    const v = await fetch(vUrl, { cache: 'no-store' }).then(r => r.text());

    const KEY = 'appVersion';
    const prev = localStorage.getItem(KEY);

    if (prev && prev !== v) {
      // On met à jour les URLs des assets en ajoutant ?v=<nouvelle version>
      const bump = (url) => {
        try {
          const u = new URL(url, window.location.href);
          u.searchParams.set('v', v);
          return u.toString();
        } catch { return url; }
      };

      // MàJ <link rel="stylesheet"> et <script> déjà présents
      document.querySelectorAll('link[rel="stylesheet"]').forEach(el => {
        el.href = bump(el.href);
      });
      document.querySelectorAll('script[src]').forEach(el => {
        el.src = bump(el.src);
      });

      // Recharge douce de la page pour tout recompiler proprement
      const u = new URL(window.location.href);
      u.searchParams.set('v', v);
      localStorage.setItem(KEY, v);
      window.location.replace(u.toString());
      return;
    }

    // Première visite ou version identique → pose/maintient la version
    if (!prev) localStorage.setItem(KEY, v);
  } catch (e) {
    // en cas d'erreur réseau, on n'empêche pas l'app de fonctionner
    console.warn('Version check failed:', e);
  }
})();

/* ===== Root path & URL helpers (respecte FastAPI root_path) ===== */
function appRoot() {
  const m = document.querySelector('meta[name="app-root"]');
  return (m?.content || '').replace(/\/+$/, ''); // ex: "/neembacoaching" ou ""
}

// Construit une URL backend en respectant root_path
function endpoint(p = '') {
  const root = appRoot();
  if (!p) return root || '/';
  if (/^https?:\/\//i.test(p)) return p; // déjà absolu
  if (p.startsWith('/')) return `${root}${p}`;
  return `${root}/${p}`;
}

// Normalise une URL /static/... renvoyée par le backend → préfixe root_path si besoin
function normalizeStatic(p) {
  const root = appRoot();
  if (!p) return p;
  if (p.startsWith(root + '/static/')) return p;
  if (p.startsWith('/static/')) return root + p;
  return p; // déjà OK (relatif/absolu)
}

/* ===== State ===== */
/* State kept in memory for the current session (sid via cookie set by server). */
const state = {
  training_type: "",
  training_title: "",
  client: { name:"", phone:"", country:"", address:"", logo_path:null },
  machine: { name:"", model:"", type:"", serial:"", photo_path:null },
  trainer: { fullname:"", contacts:"", place:"", participants_count:1, photo_path:null, start_date:"", end_date:"" },
  summary: [], objectives: [], planning: [],
  excel_path: null,
  media_paths: [],
  appreciation: {
    accueil: "",
    logement: "",
    moyens: "",
    logistique: "",
    deroulement: ""
  },
  conclusion: "", attendance_images: [],
  kpi: null, charts: null, top_plus: [], top_moins: []
};

/* ===== DOM helpers ===== */
function q(sel){ return document.querySelector(sel); }
function qa(sel){ return Array.from(document.querySelectorAll(sel)); }

function stepIndex(){ return qa('.wizard .step').findIndex(s=>s.classList.contains('active'))+1; }
function goToStep(n){
  const steps = qa('.wizard .step');
  const tabs = qa('.wizard .steps li');
  steps.forEach(s => s.classList.remove('active'));
  tabs.forEach(t => t.classList.remove('active'));
  steps[n-1].classList.add('active');
  tabs[n-1].classList.add('active');
  window.scrollTo({top:0, behavior:'smooth'});
}

/* ===== Lists / Appreciation / Conclusion ===== */
function addToList(inputSel, listSel, targetArr){
  const inp = q(inputSel);
  const txt = inp.value.trim();
  if(!txt) return;
  targetArr.push(txt);
  const li = document.createElement('li'); li.textContent = txt;
  q(listSel).appendChild(li);
  inp.value = '';
}

function wireLists(){
  // Summary & Objectives
  const summaryAdd = q('#summary_add');
  if (summaryAdd) summaryAdd.addEventListener('click', ()=> addToList('#summary_input','#summary_list', state.summary));

  const objectivesAdd = q('#objectives_add');
  if (objectivesAdd) objectivesAdd.addEventListener('click', ()=> addToList('#objectives_input','#objectives_list', state.objectives));

  // Appreciation ratings
  const appAccueilRating = q('#app_accueil_rating');
  if (appAccueilRating) appAccueilRating.addEventListener('change', ()=> { state.appreciation.accueil = appAccueilRating.value; });

  const appLogementRating = q('#app_logement_rating');
  if (appLogementRating) appLogementRating.addEventListener('change', ()=> { state.appreciation.logement = appLogementRating.value; });

  const appMoyensRating = q('#app_moyens_rating');
  if (appMoyensRating) appMoyensRating.addEventListener('change', ()=> { state.appreciation.moyens = appMoyensRating.value; });

  const appLogistiqueRating = q('#app_logistique_rating');
  if (appLogistiqueRating) appLogistiqueRating.addEventListener('change', ()=> { state.appreciation.logistique = appLogistiqueRating.value; });

  const appDeroulementRating = q('#app_deroulement_rating');
  if (appDeroulementRating) appDeroulementRating.addEventListener('change', ()=> { state.appreciation.deroulement = appDeroulementRating.value; });

  // Conclusion
  const conclusionText = q('#conclusion_text');
  if (conclusionText) conclusionText.addEventListener('input', ()=> { state.conclusion = conclusionText.value; });
}

/* ===== Text inputs binding ===== */
function wireTextInputs(){
  const trainingType = q('#training_type');
  if (trainingType) trainingType.addEventListener('input', ()=> { state.training_type = trainingType.value.trim(); });

  const trainingTitle = q('#training_title');
  if (trainingTitle) trainingTitle.addEventListener('input', ()=> { state.training_title = trainingTitle.value.trim(); });

  const clientName = q('#client_name');
  if (clientName) clientName.addEventListener('input', ()=> { state.client.name = clientName.value.trim(); });

  const clientPhone = q('#client_phone');
  if (clientPhone) clientPhone.addEventListener('input', ()=> { state.client.phone = clientPhone.value.trim(); });

  const clientCountry = q('#client_country');
  if (clientCountry) clientCountry.addEventListener('input', ()=> { state.client.country = clientCountry.value.trim(); });

  const clientAddress = q('#client_address');
  if (clientAddress) clientAddress.addEventListener('input', ()=> { state.client.address = clientAddress.value.trim(); });

  const machineName = q('#machine_name');
  if (machineName) machineName.addEventListener('input', ()=> { state.machine.name = machineName.value.trim(); });

  const machineModel = q('#machine_model');
  if (machineModel) machineModel.addEventListener('input', ()=> { state.machine.model = machineModel.value.trim(); });

  const machineType = q('#machine_type');
  if (machineType) machineType.addEventListener('input', ()=> { state.machine.type = machineType.value.trim(); });

  const machineSerial = q('#machine_serial');
  if (machineSerial) machineSerial.addEventListener('input', ()=> { state.machine.serial = machineSerial.value.trim(); });

  const trainerFullname = q('#trainer_fullname');
  if (trainerFullname) trainerFullname.addEventListener('input', ()=> { state.trainer.fullname = trainerFullname.value.trim(); });

  const trainerContacts = q('#trainer_contacts');
  if (trainerContacts) trainerContacts.addEventListener('input', ()=> { state.trainer.contacts = trainerContacts.value.trim(); });

  const trainerPlace = q('#trainer_place');
  if (trainerPlace) trainerPlace.addEventListener('input', ()=> { state.trainer.place = trainerPlace.value.trim(); });

  const participantsCount = q('#participants_count');
  if (participantsCount) participantsCount.addEventListener('input', ()=> { state.trainer.participants_count = Number(participantsCount.value || 0); });

  const startDate = q('#start_date');
  if (startDate) startDate.addEventListener('change', ()=> { state.trainer.start_date = startDate.value; });

  const endDate = q('#end_date');
  if (endDate) endDate.addEventListener('change', ()=> { state.trainer.end_date = endDate.value; });
}

/* ===== Planning table ===== */
function addPlanRow(){
  const task = q('#plan_task').value.trim();
  const start = q('#plan_start').value;
  const end = q('#plan_end').value;
  const notes = q('#plan_notes').value.trim();
  if(!task && !start && !end) return;

  const row = { task, start, end, notes };
  state.planning.push(row);

  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="pre">${task}</td>
    <td>${start || ''}</td>
    <td>${end || ''}</td>
    <td class="pre">${notes}</td>
    <td><button class="btn small danger">×</button></td>
  `;
  tr.querySelector('button').onclick = ()=>{
    tr.remove();
    state.planning = state.planning.filter(p => !(p.task===task && p.start===start && p.end===end && p.notes===notes));
  };
  q('#planning_table tbody').appendChild(tr);

  // reset
  q('#plan_task').value = '';
  q('#plan_start').value = '';
  q('#plan_end').value = '';
  q('#plan_notes').value = '';
}
function wirePlanning(){
  const planAdd = q('#plan_add');
  if (planAdd) planAdd.addEventListener('click', addPlanRow);
}

/* ===== Uploads (logo, trainer photo, machine, media[], attendance, excel) ===== */
async function uploadFile(file){
  const fd = new FormData(); fd.append('file', file);
  const res = await fetch(endpoint('/upload'), { method: 'POST', body: fd });
  const data = await res.json();
  if(!data.ok){ throw new Error(data.error || 'Upload échoué'); }
  data.path = normalizeStatic(data.path);
  return data.path;
}

function addImageToGallery(path) {
  path = normalizeStatic(path);
  const gallery = q('#media_gallery');
  if (!gallery) { console.error('Gallery element not found'); return; }

  const galleryItem = document.createElement('div');
  galleryItem.className = 'gallery-item';
  galleryItem.draggable = true;
  galleryItem.dataset.path = path;

  galleryItem.innerHTML = `
    <img src="${path}" alt="Image de formation">
    <button class="remove-btn" onclick="removeImageFromGallery(this)">×</button>
    <div class="drag-handle">⋮⋮</div>
  `;

  // Drag & Drop events
  galleryItem.addEventListener('dragstart', handleDragStart);
  galleryItem.addEventListener('dragend', handleDragEnd);
  galleryItem.addEventListener('dragover', handleDragOver);
  galleryItem.addEventListener('drop', handleDrop);

  gallery.appendChild(galleryItem);
}

function removeImageFromGallery(button) {
  const galleryItem = button.closest('.gallery-item');
  const path = galleryItem.dataset.path;
  const index = state.media_paths.indexOf(path);
  if (index > -1) state.media_paths.splice(index, 1);
  galleryItem.remove();
}
window.removeImageFromGallery = removeImageFromGallery;

function initializeGallery() {
  const gallery = q('#media_gallery');
  if (gallery && state.media_paths.length > 0) {
    gallery.innerHTML = '';
    state.media_paths.forEach(path => addImageToGallery(path));
  }
}

function initializeAttendanceGallery() {
  const gallery = q('#attendance_gallery');
  if (gallery && state.attendance_images.length > 0) {
    gallery.innerHTML = '';
    state.attendance_images.forEach(path => addImageToAttendanceGallery(path));
  }
}

function addImageToAttendanceGallery(path) {
  path = normalizeStatic(path);
  const gallery = q('#attendance_gallery');
  if (!gallery) { console.error('Attendance gallery element not found'); return; }

  const galleryItem = document.createElement('div');
  galleryItem.className = 'gallery-item';
  galleryItem.draggable = true;
  galleryItem.dataset.path = path;

  galleryItem.innerHTML = `
    <img src="${path}" alt="Image d'émargement">
    <button class="remove-btn" onclick="removeImageFromAttendanceGallery(this)">×</button>
    <div class="drag-handle">⋮⋮</div>
  `;

  galleryItem.addEventListener('dragstart', handleDragStart);
  galleryItem.addEventListener('dragend', handleDragEnd);
  galleryItem.addEventListener('dragover', handleDragOver);
  galleryItem.addEventListener('drop', handleDrop);

  gallery.appendChild(galleryItem);
}

function removeImageFromAttendanceGallery(button) {
  const galleryItem = button.closest('.gallery-item');
  const path = galleryItem.dataset.path;
  const index = state.attendance_images.indexOf(path);
  if (index > -1) state.attendance_images.splice(index, 1);
  galleryItem.remove();
}
window.removeImageFromAttendanceGallery = removeImageFromAttendanceGallery;

let draggedElement = null;
function handleDragStart(e) {
  draggedElement = this;
  this.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/html', this.outerHTML);
}
function handleDragEnd() {
  this.classList.remove('dragging');
  draggedElement = null;
}
function handleDragOver(e) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
}
function handleDrop(e) {
  e.preventDefault();
  if (draggedElement && draggedElement !== this) {
    const gallery = q('#media_gallery');
    const items = Array.from(gallery.querySelectorAll('.gallery-item'));
    const draggedIndex = items.indexOf(draggedElement);
    const targetIndex = items.indexOf(this);

    // Reorder DOM
    if (draggedIndex < targetIndex) {
      this.parentNode.insertBefore(draggedElement, this.nextSibling);
    } else {
      this.parentNode.insertBefore(draggedElement, this);
    }
    // Reorder state
    const draggedPath = draggedElement.dataset.path;
    state.media_paths.splice(draggedIndex, 1);
    state.media_paths.splice(targetIndex, 0, draggedPath);
  }
}

function wireUploads(){
  const clientLogo = q('#client_logo');
  if (clientLogo) {
    clientLogo.addEventListener('change', async (e)=>{
      const f = e.target.files[0]; if(!f) return;
      const path = await uploadFile(f);
      state.client.logo_path = path;
      const preview = q('#client_logo_preview');
      if (preview) preview.src = normalizeStatic(path);
    });
  }

  const trainerPhoto = q('#trainer_photo');
  if (trainerPhoto) {
    trainerPhoto.addEventListener('change', async (e)=>{
      const f = e.target.files[0]; if(!f) return;
      const path = await uploadFile(f);
      state.trainer.photo_path = path;
      const preview = q('#trainer_photo_preview');
      if (preview) preview.src = normalizeStatic(path);
    });
  }

  const machinePhoto = q('#machine_photo');
  if (machinePhoto) {
    machinePhoto.addEventListener('change', async (e)=>{
      const f = e.target.files[0]; if(!f) return;
      const path = await uploadFile(f);
      state.machine.photo_path = path;
      const preview = q('#machine_photo_preview');
      if (preview) preview.src = normalizeStatic(path);
    });
  }

  const mediaFiles = q('#media_files');
  if (mediaFiles) {
    mediaFiles.addEventListener('change', async (e)=>{
      const files = Array.from(e.target.files);
      for(const f of files){
        try {
          const path = await uploadFile(f);
          state.media_paths.push(path);
          addImageToGallery(path);
        } catch (error) {
          console.error('Upload failed:', error);
          alert('Erreur lors de l\'upload: ' + error.message);
        }
      }
      e.target.value = '';
    });
  }

  const attendanceFiles = q('#attendance_files');
  if (attendanceFiles) {
    attendanceFiles.addEventListener('change', async (e)=>{
      const files = Array.from(e.target.files);
      for(const f of files){
        try {
          const path = await uploadFile(f);
          state.attendance_images.push(path);
          addImageToAttendanceGallery(path);
        } catch (error) {
          console.error('Attendance upload failed:', error);
          alert('Erreur lors de l\'upload: ' + error.message);
        }
      }
      e.target.value = '';
    });
  }

  const excelFile = q('#excel_file');
  if (excelFile) {
    excelFile.addEventListener('change', async (e)=>{
      const f = e.target.files[0]; if(!f) return;
      const path = await uploadFile(f);
      state.excel_path = path;

      // aperçu serveur (10 lignes)
      try{
        const res = await fetch(endpoint('/preview-excel'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ excel_path: path })
        });
        const data = await res.json();
        if(data.ok){
          renderExcelPreview('#excel_preview', data.columns, data.rows, data.mapping, data.warning);
        }else{
          renderExcelPreview('#excel_preview', [], [], null, null);
        }
      }catch(err){
        console.error('DEBUG - Erreur lors de la prévisualisation:', err);
        renderExcelPreview('#excel_preview', [], [], null, null);
      }
    });
  }
}

/* ===== Sync before analyze ===== */
function syncBasics(){
  const trainingTitleEl = q('#training_title'); state.training_title = trainingTitleEl?.value?.trim() || '';

  const clientNameEl = q('#client_name'); state.client.name = clientNameEl?.value?.trim() || '';
  const clientPhoneEl = q('#client_phone'); state.client.phone = clientPhoneEl?.value?.trim() || '';
  const clientCountryEl = q('#client_country'); state.client.country = clientCountryEl?.value?.trim() || '';
  const clientAddressEl = q('#client_address'); state.client.address = clientAddressEl?.value?.trim() || '';

  const machineNameEl = q('#machine_name'); state.machine.name = machineNameEl?.value?.trim() || '';
  const machineModelEl = q('#machine_model'); state.machine.model = machineModelEl?.value?.trim() || '';
  const machineTypeEl = q('#machine_type'); state.machine.type = machineTypeEl?.value?.trim() || '';
  const machineSerialEl = q('#machine_serial'); state.machine.serial = machineSerialEl?.value?.trim() || '';

  const trainerFullnameEl = q('#trainer_fullname'); state.trainer.fullname = trainerFullnameEl?.value?.trim() || '';
  const trainerContactsEl = q('#trainer_contacts'); state.trainer.contacts = trainerContactsEl?.value?.trim() || '';
  const trainerPlaceEl = q('#trainer_place'); state.trainer.place = trainerPlaceEl?.value?.trim() || '';
  const participantsCountEl = q('#participants_count'); state.trainer.participants_count = Number(participantsCountEl?.value || 0);
  const startDateEl = q('#start_date'); state.trainer.start_date = startDateEl?.value || '';
  const endDateEl = q('#end_date'); state.trainer.end_date = endDateEl?.value || '';
}

/* ===== Analyze ===== */
async function doAnalyze(){
  syncBasics();
  const payload = {
    client: state.client,
    machine: state.machine,
    trainer: state.trainer,
    summary: state.summary,
    objectives: state.objectives,
    planning: state.planning,
    appreciation: state.appreciation,
    conclusion: state.conclusion,
    media_paths: state.media_paths,
    attendance_images: state.attendance_images,
    excel_path: state.excel_path
  };
  const fd = new FormData();
  fd.append('payload', JSON.stringify(payload));
  const res = await fetch(endpoint('/analyze'), { method:'POST', body: fd });
  const data = await res.json();
  if(data.ok){
    if(data.kpis){
      state.kpi = data.kpis.kpi;
      state.charts = data.kpis.charts;
      state.top_plus = data.kpis.top_plus;
      state.top_moins = data.kpis.top_moins;
    } else if (data.kpi){
      state.kpi = data.kpi;
      state.charts = data.charts;
      state.top_plus = data.top_plus;
      state.top_moins = data.top_moins;
    }
    if(state.kpi){
      q('#kpi_in').textContent = state.kpi.moy_in;
      q('#kpi_out').textContent = state.kpi.moy_out;
      q('#kpi_evo').textContent = `${state.kpi.evolution} pts (${state.kpi.evolution_pct}%)`;
      q('#kpi_interp').textContent = state.kpi.interpretation;
      q('#kpi_box').classList.remove('hidden');
    }
    alert('Analyse terminée. Vous pouvez ouvrir l\'aperçu ou passer à l\'étape suivante.');
  } else {
    alert('Erreur analyse: ' + (data.error || ''));
  }
}

/* ===== Generate PDF ===== */
async function generatePdf(){
  const btn = q('#btn_generate');
  if (!btn) return;

  const originalText = btn.innerHTML;
  btn.innerHTML = '<span class="spinner"></span> Génération en cours...';
  btn.disabled = true;
  btn.classList.add('generating');

  try {
    syncBasics();
    const res = await fetch(endpoint('/generate-reportlab'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(state)
    });

    if(!res.ok){
      let msg = 'Erreur lors de la génération du PDF';
      try { const j = await res.json(); if (j?.error) msg = j.error; } catch {}
      throw new Error(msg);
    }

    const contentDisposition = res.headers.get('content-disposition');
    let filename = 'rapport_liugong.pdf';
    if (contentDisposition) {
      const m = contentDisposition.match(/filename="?([^"]+)"?/);
      if (m) filename = m[1];
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);

    btn.innerHTML = '<span class="success-icon">✓</span> PDF généré !';
    btn.classList.remove('generating'); btn.classList.add('success');
    setTimeout(() => {
      btn.innerHTML = originalText;
      btn.disabled = false;
      btn.classList.remove('success');
    }, 2000);

  } catch (error) {
    console.error('DEBUG - Erreur génération PDF:', error);
    btn.innerHTML = '<span class="error-icon">✗</span> Erreur';
    btn.classList.remove('generating'); btn.classList.add('error');
    setTimeout(() => {
      btn.innerHTML = originalText;
      btn.disabled = false;
      btn.classList.remove('error');
    }, 3000);
    alert('Erreur lors de la génération du PDF: ' + error.message);
  }
}

/* ===== Buttons / Navigation ===== */
function wireBasics(){
  const btnAnalyze = q('#btn_analyze');
  if (btnAnalyze) btnAnalyze.addEventListener('click', doAnalyze);

  const btnGenerate = q('#btn_generate');
  if (btnGenerate) btnGenerate.addEventListener('click', generatePdf);

  const btnHelp = q('#btn-help');
  if (btnHelp) btnHelp.addEventListener('click', openHelp);

  const btnDeployment = q('#btn-deployment');
  if (btnDeployment) btnDeployment.addEventListener('click', openDeployment);

  const btnReset = q('#btn-reset');
  if (btnReset) btnReset.addEventListener('click', openReset);
}

function openHelp(){
  window.open(endpoint('/help'), '_blank', 'width=1200,height=800,scrollbars=yes,resizable=yes');
}
function openDeployment(){
  window.open(endpoint('/deployment'), '_blank', 'width=1200,height=800,scrollbars=yes,resizable=yes');
}
function openReset(){
  if (confirm('Êtes-vous sûr de vouloir réinitialiser la page ? Cela va recharger complètement l\'application et effacer toutes les données saisies.')) {
    window.location.reload(true);
  }
}

/* ===== Excel preview ===== */
function renderExcelPreview(containerSel, columns, rows, mapping, warning){
  const box = q(containerSel);
  if(!columns || columns.length === 0){
    box.innerHTML = '<div class="hint">Aucun aperçu disponible.</div>';
    box.classList.remove('hidden');
    return;
  }
  let thead = '<thead><tr>' + columns.map(c=>`<th>${c}</th>`).join('') + '</tr></thead>';
  let tbody = '<tbody>' + rows.map(r => {
    return '<tr>' + columns.map(c => `<td>${(r[c] ?? '')}</td>`).join('') + '</tr>';
  }).join('') + '</tbody>';

  let hint = '';
  if(mapping){
    const parts = [];
    if(mapping.name) parts.push(`Stagiaire → <code>${mapping.name}</code>`);
    if(mapping.in)   parts.push(`Test_In → <code>${mapping.in}</code>`);
    if(mapping.out)  parts.push(`Test_Out → <code>${mapping.out}</code>`);
    if(parts.length) hint = `<div class="hint">Détection colonnes : ${parts.join(' • ')}</div>`;
  }

  let warningHtml = '';
  if(warning){
    warningHtml = `<div class="warning-message" style="background: #fef2f2; border: 2px solid #dc2626; border-radius: 8px; padding: 12px; margin-bottom: 12px; color: #dc2626; font-weight: 600;">
      <strong>⚠️ Attention :</strong> ${warning}
    </div>`;
  }

  box.innerHTML = warningHtml + hint + `<table>${thead}${tbody}</table>`;
  box.classList.remove('hidden');
}

/* ===== Init ===== */
document.addEventListener('DOMContentLoaded', ()=>{
  wireLists(); wireTextInputs(); wirePlanning(); wireUploads(); wireBasics();
  initializeGallery();
  initializeAttendanceGallery();
});
