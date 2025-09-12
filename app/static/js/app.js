/* State kept in memory for the current session (sid via cookie set by server). */
const state = {
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


/* --- Helpers to add list items (summary/objectives/appreciation/conclusion) --- */
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
  // Summary and Objectives
  const summaryAdd = q('#summary_add');
  if (summaryAdd) summaryAdd.addEventListener('click', ()=> addToList('#summary_input','#summary_list', state.summary));
  
  const objectivesAdd = q('#objectives_add');
  if (objectivesAdd) objectivesAdd.addEventListener('click', ()=> addToList('#objectives_input','#objectives_list', state.objectives));
  
  // Appreciation rating selectors
  const appAccueilRating = q('#app_accueil_rating');
  if (appAccueilRating) appAccueilRating.addEventListener('change', ()=> {
    state.appreciation.accueil = appAccueilRating.value;
  });
  
  const appLogementRating = q('#app_logement_rating');
  if (appLogementRating) appLogementRating.addEventListener('change', ()=> {
    state.appreciation.logement = appLogementRating.value;
  });
  
  const appMoyensRating = q('#app_moyens_rating');
  if (appMoyensRating) appMoyensRating.addEventListener('change', ()=> {
    state.appreciation.moyens = appMoyensRating.value;
  });
  
  const appLogistiqueRating = q('#app_logistique_rating');
  if (appLogistiqueRating) appLogistiqueRating.addEventListener('change', ()=> {
    state.appreciation.logistique = appLogistiqueRating.value;
  });
  
  const appDeroulementRating = q('#app_deroulement_rating');
  if (appDeroulementRating) appDeroulementRating.addEventListener('change', ()=> {
    state.appreciation.deroulement = appDeroulementRating.value;
  });
  
  // Conclusion
  const conclusionText = q('#conclusion_text');
  if (conclusionText) conclusionText.addEventListener('input', ()=> {
    state.conclusion = conclusionText.value;
  });
}

/* --- Wire text inputs for real-time sync --- */
function wireTextInputs(){
  // Training title field
  const trainingTitle = q('#training_title');
  if (trainingTitle) trainingTitle.addEventListener('input', ()=> {
    state.training_title = trainingTitle.value.trim();
  });
  
  // Client fields
  const clientName = q('#client_name');
  if (clientName) clientName.addEventListener('input', ()=> {
    state.client.name = clientName.value.trim();
  });
  
  const clientPhone = q('#client_phone');
  if (clientPhone) clientPhone.addEventListener('input', ()=> {
    state.client.phone = clientPhone.value.trim();
  });
  
  const clientCountry = q('#client_country');
  if (clientCountry) clientCountry.addEventListener('input', ()=> {
    state.client.country = clientCountry.value.trim();
  });
  
  const clientAddress = q('#client_address');
  if (clientAddress) clientAddress.addEventListener('input', ()=> {
    state.client.address = clientAddress.value.trim();
  });

  // Machine fields
  const machineName = q('#machine_name');
  if (machineName) machineName.addEventListener('input', ()=> {
    state.machine.name = machineName.value.trim();
  });
  
  const machineModel = q('#machine_model');
  if (machineModel) machineModel.addEventListener('input', ()=> {
    state.machine.model = machineModel.value.trim();
  });
  
  const machineType = q('#machine_type');
  if (machineType) machineType.addEventListener('input', ()=> {
    state.machine.type = machineType.value.trim();
  });
  
  const machineSerial = q('#machine_serial');
  if (machineSerial) machineSerial.addEventListener('input', ()=> {
    state.machine.serial = machineSerial.value.trim();
  });

  // Trainer fields
  const trainerFullname = q('#trainer_fullname');
  if (trainerFullname) trainerFullname.addEventListener('input', ()=> {
    state.trainer.fullname = trainerFullname.value.trim();
  });
  
  const trainerContacts = q('#trainer_contacts');
  if (trainerContacts) trainerContacts.addEventListener('input', ()=> {
    state.trainer.contacts = trainerContacts.value.trim();
  });
  
  const trainerPlace = q('#trainer_place');
  if (trainerPlace) trainerPlace.addEventListener('input', ()=> {
    state.trainer.place = trainerPlace.value.trim();
  });
  
  const participantsCount = q('#participants_count');
  if (participantsCount) participantsCount.addEventListener('input', ()=> {
    state.trainer.participants_count = Number(participantsCount.value || 0);
  });
  
  const startDate = q('#start_date');
  if (startDate) startDate.addEventListener('change', ()=> {
    state.trainer.start_date = startDate.value;
  });
  
  const endDate = q('#end_date');
  if (endDate) endDate.addEventListener('change', ()=> {
    state.trainer.end_date = endDate.value;
  });
}

/* --- Planning table --- */
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

/* --- File uploads (logo, trainer photo, media[], attendance, excel) --- */
async function uploadFile(file){
  const fd = new FormData(); fd.append('file', file);
  const res = await fetch('/upload', { method: 'POST', body: fd });
  const data = await res.json();
  if(!data.ok){ throw new Error(data.error || 'Upload échoué'); }
  return data.path;
}

/* --- Gallery Management with Drag & Drop --- */
function addImageToGallery(path) {
  console.log('Adding image to gallery:', path);
  const gallery = q('#media_gallery');
  
  if (!gallery) {
    console.error('Gallery element not found');
    return;
  }
  
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
  console.log('Image added to gallery successfully');
}

function removeImageFromGallery(button) {
  const galleryItem = button.closest('.gallery-item');
  const path = galleryItem.dataset.path;
  
  // Remove from state
  const index = state.media_paths.indexOf(path);
  if (index > -1) {
    state.media_paths.splice(index, 1);
  }
  
  // Remove from DOM
  galleryItem.remove();
}

// Make functions globally accessible
window.removeImageFromGallery = removeImageFromGallery;

// Initialize gallery with existing images
function initializeGallery() {
  const gallery = q('#media_gallery');
  if (gallery && state.media_paths.length > 0) {
    // Clear existing content
    gallery.innerHTML = '';
    
    // Add existing images
    state.media_paths.forEach(path => {
      addImageToGallery(path);
    });
  }
}

// Initialize attendance gallery with existing images
function initializeAttendanceGallery() {
  const gallery = q('#attendance_gallery');
  if (gallery && state.attendance_images.length > 0) {
    // Clear existing content
    gallery.innerHTML = '';
    
    // Add existing images
    state.attendance_images.forEach(path => {
      addImageToAttendanceGallery(path);
    });
  }
}

// Add image to attendance gallery
function addImageToAttendanceGallery(path) {
  console.log('Adding image to attendance gallery:', path);
  const gallery = q('#attendance_gallery');
  
  if (!gallery) {
    console.error('Attendance gallery element not found');
    return;
  }
  
  const galleryItem = document.createElement('div');
  galleryItem.className = 'gallery-item';
  galleryItem.draggable = true;
  galleryItem.dataset.path = path;
  
  galleryItem.innerHTML = `
    <img src="${path}" alt="Image d'émargement">
    <button class="remove-btn" onclick="removeImageFromAttendanceGallery(this)">×</button>
    <div class="drag-handle">⋮⋮</div>
  `;
  
  // Drag & Drop events
  galleryItem.addEventListener('dragstart', handleDragStart);
  galleryItem.addEventListener('dragend', handleDragEnd);
  galleryItem.addEventListener('dragover', handleDragOver);
  galleryItem.addEventListener('drop', handleDrop);
  
  gallery.appendChild(galleryItem);
  console.log('Image added to attendance gallery successfully');
}

// Remove image from attendance gallery
function removeImageFromAttendanceGallery(button) {
  const galleryItem = button.closest('.gallery-item');
  const path = galleryItem.dataset.path;
  
  // Remove from state
  const index = state.attendance_images.indexOf(path);
  if (index > -1) {
    state.attendance_images.splice(index, 1);
  }
  
  // Remove from DOM
  galleryItem.remove();
}

// Make functions globally accessible
window.removeImageFromAttendanceGallery = removeImageFromAttendanceGallery;

let draggedElement = null;

function handleDragStart(e) {
  draggedElement = this;
  this.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/html', this.outerHTML);
}

function handleDragEnd(e) {
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
    
    // Reorder in DOM
    if (draggedIndex < targetIndex) {
      this.parentNode.insertBefore(draggedElement, this.nextSibling);
    } else {
      this.parentNode.insertBefore(draggedElement, this);
    }
    
    // Reorder in state
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
      const path = await uploadFile(f); state.client.logo_path = path;
      const preview = q('#client_logo_preview');
      if (preview) preview.src = path;
    });
  }
  
  const trainerPhoto = q('#trainer_photo');
  if (trainerPhoto) {
    trainerPhoto.addEventListener('change', async (e)=>{
      const f = e.target.files[0]; if(!f) return;
      const path = await uploadFile(f); state.trainer.photo_path = path;
      const preview = q('#trainer_photo_preview');
      if (preview) preview.src = path;
    });
  }
  
  const machinePhoto = q('#machine_photo');
  if (machinePhoto) {
    machinePhoto.addEventListener('change', async (e)=>{
      const f = e.target.files[0]; if(!f) return;
      const path = await uploadFile(f); 
      state.machine.photo_path = path;
      const preview = q('#machine_photo_preview');
      if (preview) preview.src = path;
    });
  }
  
  const mediaFiles = q('#media_files');
  if (mediaFiles) {
    mediaFiles.addEventListener('change', async (e)=>{
      const files = Array.from(e.target.files);
      console.log('Uploading', files.length, 'files');
      
      for(const f of files){
        try {
          const path = await uploadFile(f);
          console.log('Uploaded file:', path);
          state.media_paths.push(path);
          addImageToGallery(path);
        } catch (error) {
          console.error('Upload failed:', error);
          alert('Erreur lors de l\'upload: ' + error.message);
        }
      }
      
      // Clear the input
      e.target.value = '';
    });
  }
  
  const attendanceFiles = q('#attendance_files');
  if (attendanceFiles) {
    attendanceFiles.addEventListener('change', async (e)=>{
      const files = Array.from(e.target.files);
      console.log('Uploading', files.length, 'attendance files');
      
      for(const f of files){
        try {
          const path = await uploadFile(f);
          console.log('Uploaded attendance file:', path);
          state.attendance_images.push(path);
          addImageToAttendanceGallery(path);
        } catch (error) {
          console.error('Attendance upload failed:', error);
          alert('Erreur lors de l\'upload: ' + error.message);
        }
      }
      
      // Clear the input
      e.target.value = '';
    });
  }
  
  const excelFile = q('#excel_file');
  if (excelFile) {
    excelFile.addEventListener('change', async (e)=>{
      const f = e.target.files[0]; if(!f) return;
      console.log('DEBUG - Fichier Excel sélectionné:', f.name);
      
      const path = await uploadFile(f);           // upload serveur
      state.excel_path = path;
      console.log('DEBUG - Chemin Excel sauvegardé:', path);
    
      // apercu serveur (10 lignes)
      try{
        console.log('DEBUG - Envoi requête preview-excel...');
        const res = await fetch('/preview-excel', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ excel_path: path })
        });
        const data = await res.json();
        console.log('DEBUG - Réponse preview-excel:', data);
        
        if(data.ok){
          console.log('DEBUG - Affichage prévisualisation avec', data.columns.length, 'colonnes et', data.rows.length, 'lignes');
          renderExcelPreview('#excel_preview', data.columns, data.rows, data.mapping, data.warning);
        }else{
          console.log('DEBUG - Erreur prévisualisation:', data.error);
          renderExcelPreview('#excel_preview', [], [], null, null);
        }
      }catch(err){
        console.error('DEBUG - Erreur lors de la prévisualisation:', err);
        renderExcelPreview('#excel_preview', [], [], null, null);
      }
    });
  }
}

/* --- Collect text inputs into state before analyze --- */
function syncBasics(){
  console.log('DEBUG - Début syncBasics()');
  
  // Training title field
  const trainingTitleEl = q('#training_title');
  console.log('DEBUG - Élément training_title:', trainingTitleEl, 'Valeur:', trainingTitleEl?.value);
  state.training_title = trainingTitleEl?.value?.trim() || '';
  
  // Client fields
  const clientNameEl = q('#client_name');
  console.log('DEBUG - Élément client_name:', clientNameEl, 'Valeur:', clientNameEl?.value);
  state.client.name = clientNameEl?.value?.trim() || '';
  
  const clientPhoneEl = q('#client_phone');
  console.log('DEBUG - Élément client_phone:', clientPhoneEl, 'Valeur:', clientPhoneEl?.value);
  state.client.phone = clientPhoneEl?.value?.trim() || '';
  
  const clientCountryEl = q('#client_country');
  console.log('DEBUG - Élément client_country:', clientCountryEl, 'Valeur:', clientCountryEl?.value);
  state.client.country = clientCountryEl?.value?.trim() || '';
  
  const clientAddressEl = q('#client_address');
  console.log('DEBUG - Élément client_address:', clientAddressEl, 'Valeur:', clientAddressEl?.value);
  state.client.address = clientAddressEl?.value?.trim() || '';

  // Machine fields
  const machineNameEl = q('#machine_name');
  console.log('DEBUG - Élément machine_name:', machineNameEl, 'Valeur:', machineNameEl?.value);
  state.machine.name = machineNameEl?.value?.trim() || '';
  
  const machineModelEl = q('#machine_model');
  console.log('DEBUG - Élément machine_model:', machineModelEl, 'Valeur:', machineModelEl?.value);
  state.machine.model = machineModelEl?.value?.trim() || '';
  
  const machineTypeEl = q('#machine_type');
  console.log('DEBUG - Élément machine_type:', machineTypeEl, 'Valeur:', machineTypeEl?.value);
  state.machine.type = machineTypeEl?.value?.trim() || '';
  
  const machineSerialEl = q('#machine_serial');
  console.log('DEBUG - Élément machine_serial:', machineSerialEl, 'Valeur:', machineSerialEl?.value);
  state.machine.serial = machineSerialEl?.value?.trim() || '';

  // Trainer fields
  const trainerFullnameEl = q('#trainer_fullname');
  console.log('DEBUG - Élément trainer_fullname:', trainerFullnameEl, 'Valeur:', trainerFullnameEl?.value);
  state.trainer.fullname = trainerFullnameEl?.value?.trim() || '';
  
  const trainerContactsEl = q('#trainer_contacts');
  console.log('DEBUG - Élément trainer_contacts:', trainerContactsEl, 'Valeur:', trainerContactsEl?.value);
  state.trainer.contacts = trainerContactsEl?.value?.trim() || '';
  
  const trainerPlaceEl = q('#trainer_place');
  console.log('DEBUG - Élément trainer_place:', trainerPlaceEl, 'Valeur:', trainerPlaceEl?.value);
  state.trainer.place = trainerPlaceEl?.value?.trim() || '';
  
  const participantsCountEl = q('#participants_count');
  console.log('DEBUG - Élément participants_count:', participantsCountEl, 'Valeur:', participantsCountEl?.value);
  state.trainer.participants_count = Number(participantsCountEl?.value || 0);
  
  const startDateEl = q('#start_date');
  console.log('DEBUG - Élément start_date:', startDateEl, 'Valeur:', startDateEl?.value);
  state.trainer.start_date = startDateEl?.value || '';
  
  const endDateEl = q('#end_date');
  console.log('DEBUG - Élément end_date:', endDateEl, 'Valeur:', endDateEl?.value);
  state.trainer.end_date = endDateEl?.value || '';
  
  console.log('DEBUG - State final après syncBasics:', state);
}

/* --- Call /analyze to compute KPIs and save context --- */
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
  const res = await fetch('/analyze', { method:'POST', body: fd });
  const data = await res.json();
  if(data.ok){
    const k = data.kpis || data.kpi || data;
    if(data.kpis){ // from server schema
      const kp = data.kpis.kpi;
      state.kpi = kp;
      state.charts = data.kpis.charts;
      state.top_plus = data.kpis.top_plus;
      state.top_moins = data.kpis.top_moins;
    } else if (data.kpi){
      state.kpi = data.kpi;
      state.charts = data.charts;
      state.top_plus = data.top_plus;
      state.top_moins = data.top_moins;
    }
    // show KPIs
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

/* --- Generate PDF --- */
async function generatePdf(){
  const btn = q('#btn_generate');
  if (!btn) return;
  
  // Sauvegarder le texte original
  const originalText = btn.innerHTML;
  
  // Ajouter le spinner et désactiver le bouton
  btn.innerHTML = '<span class="spinner"></span> Génération en cours...';
  btn.disabled = true;
  btn.classList.add('generating');
  
  try {
    console.log('DEBUG - Début génération PDF...');
    
    // Synchroniser tous les champs de texte avant l'envoi
    syncBasics();
    console.log('DEBUG - State synchronisé:', state);
    
    const res = await fetch('/generate-reportlab', { 
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(state)
    });
    
    if(!res.ok){ 
      throw new Error('Erreur lors de la génération du PDF');
    }
    
    console.log('DEBUG - PDF généré avec succès');
    
    // Récupérer le nom du fichier depuis les headers de la réponse
    const contentDisposition = res.headers.get('content-disposition');
    let filename = 'rapport_nemba.pdf'; // nom par défaut
    console.log('DEBUG - Content-Disposition header:', contentDisposition);
    
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
      console.log('DEBUG - Regex match result:', filenameMatch);
      if (filenameMatch) {
        filename = filenameMatch[1];
        console.log('DEBUG - Nom du fichier récupéré:', filename);
      } else {
        console.log('DEBUG - Aucun nom de fichier trouvé dans le header');
      }
    } else {
      console.log('DEBUG - Pas de header Content-Disposition trouvé');
    }
    
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); 
    a.href = url; 
    a.download = filename;
    document.body.appendChild(a); 
    a.click(); 
    a.remove();
    URL.revokeObjectURL(url);
    
    // Message de succès
    btn.innerHTML = '<span class="success-icon">✓</span> PDF généré !';
    btn.classList.remove('generating');
    btn.classList.add('success');
    
    // Remettre le bouton normal après 2 secondes
    setTimeout(() => {
      btn.innerHTML = originalText;
      btn.disabled = false;
      btn.classList.remove('success');
    }, 2000);
    
  } catch (error) {
    console.error('DEBUG - Erreur génération PDF:', error);
    
    // Message d'erreur
    btn.innerHTML = '<span class="error-icon">✗</span> Erreur';
    btn.classList.remove('generating');
    btn.classList.add('error');
    
    // Remettre le bouton normal après 3 secondes
    setTimeout(() => {
      btn.innerHTML = originalText;
      btn.disabled = false;
      btn.classList.remove('error');
    }, 3000);
    
    alert('Erreur lors de la génération du PDF: ' + error.message);
  }
}


/* --- Inputs binding --- */
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
  // Ouvrir le mode d'emploi dans un nouvel onglet
  window.open('/help', '_blank', 'width=1200,height=800,scrollbars=yes,resizable=yes');
}

function openDeployment(){
  // Ouvrir le guide de déploiement dans un nouvel onglet
  window.open('/deployment', '_blank', 'width=1200,height=800,scrollbars=yes,resizable=yes');
}

function openReset(){
  // Demander confirmation avant de réinitialiser
  if (confirm('Êtes-vous sûr de vouloir réinitialiser la page ? Cela va recharger complètement l\'application et effacer toutes les données saisies.')) {
    // Forcer un rechargement complet sans cache
    window.location.reload(true);
  }
}

function renderExcelPreview(containerSel, columns, rows, mapping, warning){
  console.log('DEBUG - renderExcelPreview appelée avec:', { containerSel, columns: columns?.length, rows: rows?.length, mapping, warning });
  
  const box = q(containerSel);
  if(!columns || columns.length === 0){
    console.log('DEBUG - Aucune colonne, affichage message par défaut');
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

  // Ajouter le message d'avertissement si présent
  let warningHtml = '';
  if(warning){
    warningHtml = `<div class="warning-message" style="background: #fef2f2; border: 2px solid #dc2626; border-radius: 8px; padding: 12px; margin-bottom: 12px; color: #dc2626; font-weight: 600;">
      <strong>⚠️ Attention :</strong> ${warning}
    </div>`;
  }

  console.log('DEBUG - Génération HTML prévisualisation avec', columns.length, 'colonnes et', rows.length, 'lignes');
  box.innerHTML = warningHtml + hint + `<table>${thead}${tbody}</table>`;
  box.classList.remove('hidden');
  console.log('DEBUG - Prévisualisation affichée, classe hidden supprimée');
}

/* --- Preview images when selecting file --- */
// handled in upload listeners by setting .src

document.addEventListener('DOMContentLoaded', ()=>{
  wireLists(); wireTextInputs(); wirePlanning(); wireUploads(); wireBasics();
  initializeGallery(); // Initialize gallery with existing images
  initializeAttendanceGallery(); // Initialize attendance gallery with existing images
});
