/**
 * Template Builder — 4-step wizard for building signature flow templates.
 *
 * Step 1: Flow details (name, description, active status)
 * Step 2: Signing steps (add, remove, reorder via drag-and-drop)
 * Step 3: Document upload & field placements (reuses PDF.js rendering from placement-editor)
 * Step 4: Review & save
 */
(function () {
  'use strict';

  // ── State ──────────────────────────────────────────────────────────────────

  const state = {
    currentStep: 1,
    totalSteps: 4,
    // Flow
    flowName: '',
    flowDescription: '',
    flowIsActive: true,
    // Steps
    steps: [],
    // Document
    pdfFile: null,
    existingDocumentId: null,
    documentTitle: '',
    // Placements
    placements: [],
    // PDF.js
    pdfDoc: null,
    currentPage: 1,
    totalPages: 0,
    scale: 1.5,
    // Placement editor
    selectedStepTempId: null,
    selectedFieldType: 'signature',
    dragging: null,
    resizing: null,
    dragOffset: { x: 0, y: 0 },
  };

  // ── Reference data ─────────────────────────────────────────────────────────

  let users = [];
  let roles = [];
  let saveUrl = '';
  let flowListUrl = '';
  let csrfToken = '';
  let stepCounter = 0;
  let pdfObjectUrl = null;

  // DOM references for the placement editor
  let canvas, ctx, canvasWrapper, markersLayer;

  // ── Init ────────────────────────────────────────────────────────────────────

  function init() {
    const container = document.getElementById('template-builder-data');
    if (!container) return;

    // Parse reference data from data attributes
    csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    saveUrl = container.dataset.saveUrl || '';
    flowListUrl = container.dataset.flowListUrl || '';

    try {
      users = JSON.parse(container.dataset.users || '[]');
    } catch (e) {
      console.error('Failed to parse users:', e);
    }

    try {
      roles = JSON.parse(container.dataset.roles || '[]');
    } catch (e) {
      console.error('Failed to parse roles:', e);
    }

    // Edit mode: load existing flow data
    let flowData = null;
    try {
      flowData = JSON.parse(container.dataset.flow || 'null');
    } catch (e) {
      console.error('Failed to parse flow data:', e);
    }

    if (flowData) {
      state.flowName = flowData.name || '';
      state.flowDescription = flowData.description || '';
      state.flowIsActive = flowData.is_active !== false;
    }

    // Edit mode: load existing steps
    let stepsData = null;
    try {
      stepsData = JSON.parse(container.dataset.steps || 'null');
    } catch (e) {
      console.error('Failed to parse steps data:', e);
    }

    if (stepsData && stepsData.length > 0) {
      stepsData.forEach(function (s) {
        stepCounter++;
        state.steps.push({
          temp_id: s.id ? String(s.id) : 'temp_' + stepCounter,
          label: s.label || '',
          assignment_type: s.assignment_type || 'role',
          assigned_user: s.assigned_user || '',
          assigned_role: s.assigned_role || '',
          is_required: s.is_required !== false,
        });
      });
    }

    // Edit mode: load existing documents
    let documentsData = null;
    try {
      documentsData = JSON.parse(container.dataset.documents || 'null');
    } catch (e) {
      console.error('Failed to parse documents data:', e);
    }

    if (documentsData && documentsData.length > 0) {
      const doc = documentsData[0];
      state.existingDocumentId = doc.id || null;
      state.documentTitle = doc.title || '';
      if (doc.placements) {
        state.placements = doc.placements.slice();
      }
    }

    // Populate step 1 form fields
    const nameInput = document.getElementById('flow-name');
    const descInput = document.getElementById('flow-description');
    const activeInput = document.getElementById('flow-active');
    if (nameInput) nameInput.value = state.flowName;
    if (descInput) descInput.value = state.flowDescription;
    if (activeInput) activeInput.checked = state.flowIsActive;

    // Render step 2 if we have existing steps
    renderStepsList();

    // Set up wizard navigation
    document.getElementById('wizard-next-btn')?.addEventListener('click', function () {
      if (!validateCurrentStep()) return;
      collectCurrentStepData();
      if (state.currentStep < state.totalSteps) {
        goToStep(state.currentStep + 1);
      }
    });

    document.getElementById('wizard-prev-btn')?.addEventListener('click', function () {
      if (state.currentStep > 1) {
        collectCurrentStepData();
        goToStep(state.currentStep - 1);
      }
    });

    document.getElementById('wizard-save-btn')?.addEventListener('click', save);

    // Add step button
    document.getElementById('add-step-btn')?.addEventListener('click', addStep);

    // Dropzone
    setupDropzone();

    // Change document button
    document.getElementById('change-document-btn')?.addEventListener('click', function () {
      showDropzone();
      state.pdfFile = null;
      state.existingDocumentId = null;
      state.placements = [];
      if (pdfObjectUrl) {
        URL.revokeObjectURL(pdfObjectUrl);
        pdfObjectUrl = null;
      }
      state.pdfDoc = null;
      state.totalPages = 0;
      state.currentPage = 1;
    });

    // Field type selector buttons (within template builder)
    document.querySelectorAll('#wizard-step-3 [data-field-type]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.selectedFieldType = this.dataset.fieldType;
        document.querySelectorAll('#wizard-step-3 [data-field-type]').forEach(function (b) {
          b.classList.toggle('active', b.dataset.fieldType === state.selectedFieldType);
        });
      });
    });

    // Page navigation within template builder
    document.getElementById('prev-page')?.addEventListener('click', function () {
      if (state.currentPage > 1) {
        state.currentPage--;
        renderPage();
      }
    });
    document.getElementById('next-page')?.addEventListener('click', function () {
      if (state.currentPage < state.totalPages) {
        state.currentPage++;
        renderPage();
      }
    });

    // Show initial step
    goToStep(1);
  }

  // ── Wizard Navigation ──────────────────────────────────────────────────────

  function goToStep(n) {
    state.currentStep = n;

    // Hide all panels, show current
    for (let i = 1; i <= state.totalSteps; i++) {
      const panel = document.getElementById('wizard-step-' + i);
      if (panel) {
        if (i === n) {
          panel.classList.remove('d-none');
        } else {
          panel.classList.add('d-none');
        }
      }
    }

    // Update progress bar
    const progressBar = document.getElementById('wizard-progress-bar');
    if (progressBar) {
      const pct = Math.round((n / state.totalSteps) * 100);
      progressBar.style.width = pct + '%';
      progressBar.setAttribute('aria-valuenow', pct);
    }

    // Update step labels
    document.querySelectorAll('.wizard-progress-label[data-step]').forEach(function (label) {
      const stepNum = parseInt(label.dataset.step);
      label.classList.remove('active', 'completed');
      if (stepNum === n) {
        label.classList.add('active');
      } else if (stepNum < n) {
        label.classList.add('completed');
      }
    });

    // Toggle navigation buttons
    const prevBtn = document.getElementById('wizard-prev-btn');
    const nextBtn = document.getElementById('wizard-next-btn');
    const saveBtn = document.getElementById('wizard-save-btn');

    if (prevBtn) prevBtn.classList.toggle('d-none', n <= 1);
    if (nextBtn) nextBtn.classList.toggle('d-none', n >= state.totalSteps);
    if (saveBtn) saveBtn.classList.toggle('d-none', n !== state.totalSteps);

    // Step-specific actions on enter
    if (n === 3) {
      populateStepSelector();
      initPlacementEditor();
    }
    if (n === 4) {
      renderReview();
    }
  }

  // ── Validation ─────────────────────────────────────────────────────────────

  function validateCurrentStep() {
    clearErrors();

    if (state.currentStep === 1) {
      return validateStep1();
    } else if (state.currentStep === 2) {
      return validateStep2();
    } else if (state.currentStep === 3) {
      return validateStep3();
    }
    return true;
  }

  function validateStep1() {
    const name = document.getElementById('flow-name');
    if (!name || !name.value.trim()) {
      showError(name, 'Flow name is required.');
      return false;
    }
    return true;
  }

  function validateStep2() {
    collectStepsData();
    if (state.steps.length === 0) {
      const container = document.getElementById('steps-container');
      showErrorMessage(container, 'At least one signing step is required.');
      return false;
    }
    let valid = true;
    state.steps.forEach(function (step, idx) {
      if (!step.label || !step.label.trim()) {
        const row = document.querySelector('[data-temp-id="' + step.temp_id + '"]');
        if (row) {
          const input = row.querySelector('.step-label');
          showError(input, 'Step label is required.');
        }
        valid = false;
      }
    });
    return valid;
  }

  function validateStep3() {
    if (!state.pdfFile && !state.existingDocumentId) {
      const dropzone = document.getElementById('pdf-dropzone');
      showErrorMessage(dropzone, 'Please upload a PDF document.');
      return false;
    }
    return true;
  }

  function showError(input, msg) {
    if (!input) return;
    input.classList.add('is-invalid');
    const feedback = document.createElement('div');
    feedback.className = 'invalid-feedback';
    feedback.textContent = msg;
    input.parentNode.appendChild(feedback);
  }

  function showErrorMessage(container, msg) {
    if (!container) return;
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger mt-2 validation-error';
    alert.textContent = msg;
    container.parentNode.insertBefore(alert, container.nextSibling);
  }

  function clearErrors() {
    document.querySelectorAll('.is-invalid').forEach(function (el) {
      el.classList.remove('is-invalid');
    });
    document.querySelectorAll('.invalid-feedback').forEach(function (el) {
      el.remove();
    });
    document.querySelectorAll('.validation-error').forEach(function (el) {
      el.remove();
    });
  }

  // ── Data Collection ────────────────────────────────────────────────────────

  function collectCurrentStepData() {
    if (state.currentStep === 1) {
      collectFlowData();
    } else if (state.currentStep === 2) {
      collectStepsData();
    }
  }

  function collectFlowData() {
    const name = document.getElementById('flow-name');
    const desc = document.getElementById('flow-description');
    const active = document.getElementById('flow-active');
    if (name) state.flowName = name.value.trim();
    if (desc) state.flowDescription = desc.value.trim();
    if (active) state.flowIsActive = active.checked;
  }

  function collectStepsData() {
    const rows = document.querySelectorAll('#steps-container .step-row');
    const updatedSteps = [];

    rows.forEach(function (row) {
      const tempId = row.dataset.tempId;
      const label = row.querySelector('.step-label')?.value.trim() || '';
      const assignmentType = row.querySelector('.step-assignment')?.value || 'role';
      const assignedUser = row.querySelector('.step-user-select')?.value || '';
      const assignedRole = row.querySelector('.step-role-select')?.value || '';
      const isRequired = row.querySelector('.step-required')?.checked !== false;

      updatedSteps.push({
        temp_id: tempId,
        label: label,
        assignment_type: assignmentType,
        assigned_user: assignedUser,
        assigned_role: assignedRole,
        is_required: isRequired,
      });
    });

    state.steps = updatedSteps;
  }

  // ── Step 2: Signing Steps ──────────────────────────────────────────────────

  function addStep() {
    stepCounter++;
    state.steps.push({
      temp_id: 'temp_' + stepCounter,
      label: '',
      assignment_type: 'role',
      assigned_user: '',
      assigned_role: '',
      is_required: true,
    });
    renderStepsList();
  }

  function renderStepsList() {
    const container = document.getElementById('steps-container');
    if (!container) return;
    container.innerHTML = '';

    state.steps.forEach(function (step, idx) {
      const row = document.createElement('div');
      row.className = 'step-row d-flex align-items-center gap-2 mb-2 p-2 border rounded bg-white';
      row.dataset.tempId = step.temp_id;
      row.draggable = true;

      // Drag handle
      const dragHandle = document.createElement('span');
      dragHandle.className = 'drag-handle';
      dragHandle.style.cursor = 'grab';
      dragHandle.innerHTML = '<i class="bi bi-grip-vertical fs-5"></i>';
      row.appendChild(dragHandle);

      // Order badge
      const badge = document.createElement('span');
      badge.className = 'badge bg-primary rounded-pill';
      badge.textContent = String(idx + 1);
      row.appendChild(badge);

      // Label input
      const labelInput = document.createElement('input');
      labelInput.type = 'text';
      labelInput.className = 'form-control form-control-sm step-label';
      labelInput.placeholder = 'Step label...';
      labelInput.value = step.label;
      row.appendChild(labelInput);

      // Assignment type select
      const assignSelect = document.createElement('select');
      assignSelect.className = 'form-select form-select-sm step-assignment';
      assignSelect.style.maxWidth = '130px';
      assignSelect.innerHTML =
        '<option value="role">By Role</option>' +
        '<option value="user">Specific User</option>';
      assignSelect.value = step.assignment_type;
      row.appendChild(assignSelect);

      // User select
      const userSelect = document.createElement('select');
      userSelect.className = 'form-select form-select-sm step-user-select';
      userSelect.style.maxWidth = '180px';
      userSelect.style.display = step.assignment_type === 'user' ? '' : 'none';
      userSelect.innerHTML = '<option value="">-- Select User --</option>';
      users.forEach(function (u) {
        const opt = document.createElement('option');
        opt.value = u.id;
        opt.textContent = u.name;
        if (String(u.id) === String(step.assigned_user)) opt.selected = true;
        userSelect.appendChild(opt);
      });
      row.appendChild(userSelect);

      // Role select
      const roleSelect = document.createElement('select');
      roleSelect.className = 'form-select form-select-sm step-role-select';
      roleSelect.style.maxWidth = '150px';
      roleSelect.style.display = step.assignment_type === 'role' ? '' : 'none';
      roleSelect.innerHTML = '<option value="">-- Select Role --</option>';
      roles.forEach(function (r) {
        const opt = document.createElement('option');
        opt.value = r[0];
        opt.textContent = r[1];
        if (String(r[0]) === String(step.assigned_role)) opt.selected = true;
        roleSelect.appendChild(opt);
      });
      row.appendChild(roleSelect);

      // Toggle user/role selects on assignment change
      assignSelect.addEventListener('change', function () {
        const isUser = this.value === 'user';
        userSelect.style.display = isUser ? '' : 'none';
        roleSelect.style.display = isUser ? 'none' : '';
      });

      // Required checkbox
      const checkDiv = document.createElement('div');
      checkDiv.className = 'form-check ms-2';
      const checkInput = document.createElement('input');
      checkInput.type = 'checkbox';
      checkInput.className = 'form-check-input step-required';
      checkInput.checked = step.is_required;
      checkInput.id = 'req-' + step.temp_id;
      const checkLabel = document.createElement('label');
      checkLabel.className = 'form-check-label small';
      checkLabel.htmlFor = 'req-' + step.temp_id;
      checkLabel.textContent = 'Req';
      checkDiv.appendChild(checkInput);
      checkDiv.appendChild(checkLabel);
      row.appendChild(checkDiv);

      // Delete button
      const delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.className = 'btn btn-sm btn-outline-danger ms-auto';
      delBtn.innerHTML = '<i class="bi bi-trash"></i>';
      delBtn.addEventListener('click', function () {
        collectStepsData();
        state.steps = state.steps.filter(function (s) {
          return s.temp_id !== step.temp_id;
        });
        // Remove placements associated with deleted step
        state.placements = state.placements.filter(function (p) {
          return p.step_id !== step.temp_id;
        });
        renderStepsList();
      });
      row.appendChild(delBtn);

      // Drag-and-drop events
      row.addEventListener('dragstart', onStepDragStart);
      row.addEventListener('dragover', onStepDragOver);
      row.addEventListener('dragenter', onStepDragEnter);
      row.addEventListener('dragleave', onStepDragLeave);
      row.addEventListener('drop', onStepDrop);
      row.addEventListener('dragend', onStepDragEnd);

      container.appendChild(row);
    });
  }

  // ── Step 2: Drag-and-drop Reorder ──────────────────────────────────────────

  let dragSrcTempId = null;

  function onStepDragStart(e) {
    collectStepsData();
    dragSrcTempId = this.dataset.tempId;
    this.style.opacity = '0.4';
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', dragSrcTempId);
  }

  function onStepDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }

  function onStepDragEnter(e) {
    e.preventDefault();
    const row = e.currentTarget;
    row.classList.add('border-primary');
  }

  function onStepDragLeave(e) {
    const row = e.currentTarget;
    row.classList.remove('border-primary');
  }

  function onStepDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    const row = e.currentTarget;
    row.classList.remove('border-primary');

    const targetTempId = row.dataset.tempId;
    if (dragSrcTempId === targetTempId) return;

    // Find indices
    const srcIdx = state.steps.findIndex(function (s) { return s.temp_id === dragSrcTempId; });
    const tgtIdx = state.steps.findIndex(function (s) { return s.temp_id === targetTempId; });
    if (srcIdx === -1 || tgtIdx === -1) return;

    // Reorder
    const moved = state.steps.splice(srcIdx, 1)[0];
    state.steps.splice(tgtIdx, 0, moved);
    renderStepsList();
  }

  function onStepDragEnd() {
    this.style.opacity = '1';
    dragSrcTempId = null;
    document.querySelectorAll('#steps-container .step-row').forEach(function (row) {
      row.classList.remove('border-primary');
    });
  }

  // ── Step 3: Document & Placements ──────────────────────────────────────────

  function initPlacementEditor() {
    canvas = document.getElementById('pdf-canvas');
    ctx = canvas ? canvas.getContext('2d') : null;
    canvasWrapper = document.getElementById('canvas-wrapper');
    markersLayer = document.getElementById('markers-layer');

    const editorArea = document.getElementById('placement-editor-section');
    const dropzone = document.getElementById('pdf-dropzone');

    // Determine if we already have a PDF to show
    let pdfSrc = null;

    if (state.pdfFile) {
      if (pdfObjectUrl) URL.revokeObjectURL(pdfObjectUrl);
      pdfObjectUrl = URL.createObjectURL(state.pdfFile);
      pdfSrc = pdfObjectUrl;
    } else if (state.existingDocumentId) {
      // Try to get URL from data attributes
      const container = document.getElementById('template-builder-data');
      let documentsData = null;
      try {
        documentsData = JSON.parse(container.dataset.documents || 'null');
      } catch (e) { /* ignore */ }
      if (documentsData && documentsData.length > 0 && documentsData[0].file_url) {
        pdfSrc = documentsData[0].file_url;
      }
    }

    if (pdfSrc) {
      if (editorArea) editorArea.classList.remove('d-none');
      if (dropzone) dropzone.classList.add('d-none');
      loadPDF(pdfSrc);
    } else {
      if (editorArea) editorArea.classList.add('d-none');
      if (dropzone) dropzone.classList.remove('d-none');
    }

    // Set up marker interaction events
    if (markersLayer) {
      // Remove old listeners to prevent duplicates (re-add fresh)
      markersLayer.removeEventListener('click', onMarkersLayerClick);
      markersLayer.removeEventListener('mousedown', onPointerDown);
      markersLayer.removeEventListener('touchstart', onPointerDown);
      document.removeEventListener('mousemove', onPointerMove);
      document.removeEventListener('touchmove', onPointerMove);
      document.removeEventListener('mouseup', onPointerUp);
      document.removeEventListener('touchend', onPointerUp);

      markersLayer.addEventListener('click', onMarkersLayerClick);
      markersLayer.addEventListener('mousedown', onPointerDown);
      markersLayer.addEventListener('touchstart', onPointerDown, { passive: false });
      document.addEventListener('mousemove', onPointerMove);
      document.addEventListener('touchmove', onPointerMove, { passive: false });
      document.addEventListener('mouseup', onPointerUp);
      document.addEventListener('touchend', onPointerUp);
    }
  }

  function showDropzone() {
    const editorArea = document.getElementById('placement-editor-section');
    const dropzone = document.getElementById('pdf-dropzone');
    if (editorArea) editorArea.classList.add('d-none');
    if (dropzone) dropzone.classList.remove('d-none');
  }

  function setupDropzone() {
    const dropzone = document.getElementById('pdf-dropzone');
    const fileInput = document.getElementById('pdf-file-input');
    if (!dropzone || !fileInput) return;

    // Click to open file picker
    dropzone.addEventListener('click', function () {
      fileInput.click();
    });

    // File input change
    fileInput.addEventListener('change', function () {
      if (this.files && this.files[0]) {
        handleFileSelect(this.files[0]);
      }
    });

    // Drag events
    dropzone.addEventListener('dragover', function (e) {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('border-primary', 'bg-light');
    });

    dropzone.addEventListener('dragleave', function (e) {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('border-primary', 'bg-light');
    });

    dropzone.addEventListener('drop', function (e) {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('border-primary', 'bg-light');
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        handleFileSelect(e.dataTransfer.files[0]);
      }
    });
  }

  function handleFileSelect(file) {
    // Validate file type
    if (file.type !== 'application/pdf') {
      alert('Please select a PDF file.');
      return;
    }

    state.pdfFile = file;
    state.existingDocumentId = null;
    state.documentTitle = file.name;
    state.placements = [];
    state.currentPage = 1;

    // Create object URL and load
    if (pdfObjectUrl) URL.revokeObjectURL(pdfObjectUrl);
    pdfObjectUrl = URL.createObjectURL(file);

    const editorArea = document.getElementById('placement-editor-section');
    const dropzone = document.getElementById('pdf-dropzone');
    if (editorArea) editorArea.classList.remove('d-none');
    if (dropzone) dropzone.classList.add('d-none');

    loadPDF(pdfObjectUrl);
  }

  // ── Step 3: Step Selector ──────────────────────────────────────────────────

  function populateStepSelector() {
    const select = document.getElementById('step-selector');
    if (!select) return;

    select.innerHTML = '<option value="">-- Select Step --</option>';
    state.steps.forEach(function (step, idx) {
      const opt = document.createElement('option');
      opt.value = step.temp_id;
      opt.textContent = 'Step ' + (idx + 1) + ': ' + (step.label || '(unnamed)');
      select.appendChild(opt);
    });

    // Remove old listener to prevent duplicates
    select.removeEventListener('change', onStepSelectorChange);
    select.addEventListener('change', onStepSelectorChange);
  }

  function onStepSelectorChange() {
    state.selectedStepTempId = this.value || null;
  }

  // ── Step 3: PDF Rendering (mirrors placement-editor.js) ────────────────────

  function loadPDF(url) {
    if (!url || typeof pdfjsLib === 'undefined') {
      console.error('PDF.js or PDF URL not available');
      return;
    }

    pdfjsLib.GlobalWorkerOptions.workerSrc =
      'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

    pdfjsLib.getDocument(url).promise.then(function (pdf) {
      state.pdfDoc = pdf;
      state.totalPages = pdf.numPages;
      state.currentPage = 1;
      updatePageInfo();
      renderPage();
    }).catch(function (err) {
      console.error('Failed to load PDF:', err);
    });
  }

  function renderPage() {
    if (!state.pdfDoc || !canvas || !ctx) return;

    state.pdfDoc.getPage(state.currentPage).then(function (page) {
      const viewport = page.getViewport({ scale: state.scale });
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.width = viewport.width + 'px';
      canvas.style.height = viewport.height + 'px';

      if (markersLayer) {
        markersLayer.style.width = viewport.width + 'px';
        markersLayer.style.height = viewport.height + 'px';
      }
      if (canvasWrapper) {
        canvasWrapper.style.width = viewport.width + 'px';
        canvasWrapper.style.height = viewport.height + 'px';
      }

      page.render({ canvasContext: ctx, viewport: viewport }).promise.then(function () {
        renderMarkers();
      });

      updatePageInfo();
    });
  }

  function updatePageInfo() {
    const info = document.getElementById('page-info');
    if (info) info.textContent = state.currentPage + ' / ' + state.totalPages;
  }

  // ── Step 3: Markers (mirrors placement-editor.js, uses temp_id) ────────────

  function renderMarkers() {
    if (!markersLayer) return;

    markersLayer.querySelectorAll('.placement-marker').forEach(function (m) { m.remove(); });

    state.placements.forEach(function (p, idx) {
      if (p.page_number !== state.currentPage) return;

      const stepIdx = state.steps.findIndex(function (s) { return s.temp_id === p.step_id; });
      const step = stepIdx !== -1 ? state.steps[stepIdx] : null;

      const marker = document.createElement('div');
      marker.className = 'placement-marker';
      marker.dataset.index = idx;
      marker.dataset.stepOrder = step ? (stepIdx + 1) : 0;
      marker.style.left = p.x + '%';
      marker.style.top = p.y + '%';
      marker.style.width = p.width + '%';
      marker.style.height = p.height + '%';

      const label = (step ? 'S' + (stepIdx + 1) : '?') + ': ' + (p.field_type || 'sig');
      marker.textContent = label;
      marker.title = (step ? step.label : 'Unknown') + ' — ' + p.field_type;

      // Delete button
      const delBtn = document.createElement('button');
      delBtn.className = 'delete-btn';
      delBtn.innerHTML = '&times;';
      delBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        state.placements.splice(idx, 1);
        renderMarkers();
      });
      marker.appendChild(delBtn);

      // Resize handle
      const handle = document.createElement('div');
      handle.className = 'resize-handle';
      handle.dataset.index = idx;
      marker.appendChild(handle);

      markersLayer.appendChild(marker);
    });
  }

  // ── Step 3: Click-to-place ─────────────────────────────────────────────────

  function onMarkersLayerClick(e) {
    if (e.target !== markersLayer) return;
    if (!state.selectedStepTempId) {
      alert('Please select a signing step first.');
      return;
    }

    const rect = markersLayer.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;

    state.placements.push({
      step_id: state.selectedStepTempId,
      field_type: state.selectedFieldType,
      page_number: state.currentPage,
      x: x,
      y: y,
      width: 20,
      height: 5,
    });

    renderMarkers();
  }

  // ── Step 3: Drag & Resize (mirrors placement-editor.js) ────────────────────

  function onPointerDown(e) {
    const touch = e.touches ? e.touches[0] : e;
    const target = touch.target || e.target;

    if (target.classList.contains('resize-handle')) {
      e.preventDefault();
      state.resizing = parseInt(target.dataset.index);
      return;
    }

    const marker = target.closest('.placement-marker');
    if (marker) {
      e.preventDefault();
      const idx = parseInt(marker.dataset.index);
      state.dragging = idx;

      const rect = markersLayer.getBoundingClientRect();
      const px = ((touch.clientX - rect.left) / rect.width) * 100;
      const py = ((touch.clientY - rect.top) / rect.height) * 100;
      state.dragOffset.x = px - state.placements[idx].x;
      state.dragOffset.y = py - state.placements[idx].y;

      marker.classList.add('dragging');
    }
  }

  function onPointerMove(e) {
    if (state.dragging === null && state.resizing === null) return;
    e.preventDefault();

    const touch = e.touches ? e.touches[0] : e;
    const rect = markersLayer.getBoundingClientRect();
    const px = ((touch.clientX - rect.left) / rect.width) * 100;
    const py = ((touch.clientY - rect.top) / rect.height) * 100;

    if (state.dragging !== null) {
      const p = state.placements[state.dragging];
      p.x = Math.max(0, Math.min(100 - p.width, px - state.dragOffset.x));
      p.y = Math.max(0, Math.min(100 - p.height, py - state.dragOffset.y));
      renderMarkers();
    }

    if (state.resizing !== null) {
      const p = state.placements[state.resizing];
      p.width = Math.max(5, Math.min(100 - p.x, px - p.x));
      p.height = Math.max(2, Math.min(100 - p.y, py - p.y));
      renderMarkers();
    }
  }

  function onPointerUp() {
    if (state.dragging !== null && markersLayer) {
      const marker = markersLayer.querySelector('[data-index="' + state.dragging + '"]');
      if (marker) marker.classList.remove('dragging');
    }
    state.dragging = null;
    state.resizing = null;
  }

  // ── Step 4: Review ─────────────────────────────────────────────────────────

  function renderReview() {
    const container = document.getElementById('review-content');
    if (!container) return;

    let html = '';

    // Flow details
    html += '<div class="mb-4">';
    html += '<h6 class="fw-bold border-bottom pb-2 mb-3">Flow Details</h6>';
    html += '<dl class="row mb-0">';
    html += '<dt class="col-sm-3">Name</dt>';
    html += '<dd class="col-sm-9">' + escapeHtml(state.flowName) + '</dd>';
    html += '<dt class="col-sm-3">Description</dt>';
    html += '<dd class="col-sm-9">' + (state.flowDescription ? escapeHtml(state.flowDescription) : '<span class="text-muted">None</span>') + '</dd>';
    html += '<dt class="col-sm-3">Status</dt>';
    html += '<dd class="col-sm-9">' + (state.flowIsActive
      ? '<span class="badge bg-success">Active</span>'
      : '<span class="badge bg-secondary">Inactive</span>') + '</dd>';
    html += '</dl>';
    html += '</div>';

    // Signing steps
    html += '<div class="mb-4">';
    html += '<h6 class="fw-bold border-bottom pb-2 mb-3">Signing Steps (' + state.steps.length + ')</h6>';
    if (state.steps.length > 0) {
      html += '<ol class="list-group list-group-numbered">';
      state.steps.forEach(function (step) {
        let assignmentLabel = '';
        if (step.assignment_type === 'user') {
          const user = users.find(function (u) { return String(u.id) === String(step.assigned_user); });
          assignmentLabel = user ? user.name : 'Unassigned';
        } else {
          const role = roles.find(function (r) { return String(r[0]) === String(step.assigned_role); });
          assignmentLabel = role ? role[1] : 'Unassigned';
        }
        html += '<li class="list-group-item d-flex justify-content-between align-items-center">';
        html += '<div>';
        html += '<strong>' + escapeHtml(step.label) + '</strong>';
        html += ' <small class="text-muted ms-2">' + escapeHtml(step.assignment_type) + ': ' + escapeHtml(assignmentLabel) + '</small>';
        html += '</div>';
        html += '<div>';
        if (step.is_required) {
          html += '<span class="badge bg-warning text-dark">Required</span>';
        } else {
          html += '<span class="badge bg-light text-dark">Optional</span>';
        }
        html += '</div>';
        html += '</li>';
      });
      html += '</ol>';
    } else {
      html += '<p class="text-muted">No signing steps defined.</p>';
    }
    html += '</div>';

    // Document
    html += '<div class="mb-4">';
    html += '<h6 class="fw-bold border-bottom pb-2 mb-3">Document</h6>';
    if (state.pdfFile) {
      html += '<p><i class="bi bi-file-earmark-pdf me-1 text-danger"></i>' + escapeHtml(state.pdfFile.name);
      html += ' <span class="text-muted">(' + state.totalPages + ' page' + (state.totalPages !== 1 ? 's' : '') + ')</span></p>';
    } else if (state.existingDocumentId) {
      html += '<p><i class="bi bi-file-earmark-pdf me-1 text-danger"></i>' + escapeHtml(state.documentTitle || 'Existing document');
      html += ' <span class="text-muted">(' + state.totalPages + ' page' + (state.totalPages !== 1 ? 's' : '') + ')</span></p>';
    } else {
      html += '<p class="text-muted">No document uploaded.</p>';
    }
    html += '</div>';

    // Placements summary
    html += '<div class="mb-4">';
    html += '<h6 class="fw-bold border-bottom pb-2 mb-3">Field Placements (' + state.placements.length + ')</h6>';
    if (state.placements.length > 0) {
      html += '<table class="table table-sm">';
      html += '<thead><tr><th>Step</th><th>Field Type</th><th>Page</th></tr></thead>';
      html += '<tbody>';

      // Group by step
      const placementsByStep = {};
      state.placements.forEach(function (p) {
        if (!placementsByStep[p.step_id]) {
          placementsByStep[p.step_id] = [];
        }
        placementsByStep[p.step_id].push(p);
      });

      state.steps.forEach(function (step, idx) {
        const stepPlacements = placementsByStep[step.temp_id] || [];
        if (stepPlacements.length === 0) return;
        stepPlacements.forEach(function (p) {
          html += '<tr>';
          html += '<td>Step ' + (idx + 1) + ': ' + escapeHtml(step.label) + '</td>';
          html += '<td><code>' + escapeHtml(p.field_type) + '</code></td>';
          html += '<td>' + p.page_number + '</td>';
          html += '</tr>';
        });
      });

      html += '</tbody></table>';
    } else {
      html += '<p class="text-muted">No field placements defined.</p>';
    }
    html += '</div>';

    container.innerHTML = html;
  }

  // ── Save ───────────────────────────────────────────────────────────────────

  function save() {
    const btn = document.getElementById('wizard-save-btn');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Saving...';
    }

    // Build payload
    const payload = {
      name: state.flowName,
      description: state.flowDescription,
      is_active: state.flowIsActive,
      steps: state.steps.map(function (s, idx) {
        return {
          temp_id: s.temp_id,
          label: s.label,
          order: idx + 1,
          assignment_type: s.assignment_type,
          assigned_user: s.assigned_user || null,
          assigned_role: s.assigned_role || null,
          is_required: s.is_required,
        };
      }),
      placements: state.placements.map(function (p) {
        return {
          step_id: p.step_id,
          field_type: p.field_type,
          page_number: p.page_number,
          x: p.x,
          y: p.y,
          width: p.width,
          height: p.height,
        };
      }),
      existing_document_id: state.existingDocumentId,
      document_title: state.documentTitle,
    };

    // Build FormData
    const formData = new FormData();
    formData.append('payload', JSON.stringify(payload));

    if (state.pdfFile) {
      formData.append('document', state.pdfFile);
    }

    fetch(saveUrl, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken,
      },
      body: formData,
    })
      .then(function (res) {
        if (!res.ok) {
          return res.json().then(function (data) {
            throw { status: res.status, data: data };
          });
        }
        return res.json();
      })
      .then(function (data) {
        if (data.redirect_url) {
          window.location.href = data.redirect_url;
        } else if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Saved';
          setTimeout(function () {
            btn.innerHTML = '<i class="bi bi-save me-1"></i>Save Template';
          }, 2000);
        }
      })
      .catch(function (err) {
        console.error('Save failed:', err);
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="bi bi-save me-1"></i>Save Template';
        }

        let message = 'Failed to save template.';
        if (err && err.data) {
          if (err.data.errors) {
            const errorMessages = [];
            const errors = err.data.errors;
            for (const field in errors) {
              if (errors.hasOwnProperty(field)) {
                const fieldErrors = Array.isArray(errors[field]) ? errors[field] : [errors[field]];
                fieldErrors.forEach(function (msg) {
                  errorMessages.push(field + ': ' + msg);
                });
              }
            }
            if (errorMessages.length > 0) {
              message = errorMessages.join('\n');
            }
          } else if (err.data.error) {
            message = err.data.error;
          } else if (err.data.detail) {
            message = err.data.detail;
          }
        }
        alert(message);
      });
  }

  // ── Utilities ──────────────────────────────────────────────────────────────

  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ── Initialize ─────────────────────────────────────────────────────────────

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
