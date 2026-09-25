/**
 * Prescription Reader Frontend Application
 * Interacts with FastAPI backend.
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const dropZoneIdle = document.getElementById('dropZoneIdle');
  const sampleActionWrapper = document.getElementById('sampleActionWrapper');
  const loadSampleBtn = document.getElementById('loadSampleBtn');
  
  const previewArea = document.getElementById('previewArea');
  const imagePreview = document.getElementById('imagePreview');
  const fileName = document.getElementById('fileName');
  const fileSize = document.getElementById('fileSize');
  const changeImageBtn = document.getElementById('changeImageBtn');
  const analyzeBtn = document.getElementById('analyzeBtn');

  const uploadCard = document.getElementById('uploadCard');
  const loadingCard = document.getElementById('loadingCard');
  const errorCard = document.getElementById('errorCard');
  const errorTitle = document.getElementById('errorTitle');
  const errorMessage = document.getElementById('errorMessage');
  const dismissErrorBtn = document.getElementById('dismissErrorBtn');

  const resultsSection = document.getElementById('resultsSection');
  const summaryText = document.getElementById('summaryText');
  const medicineCountBadge = document.getElementById('medicineCountBadge');
  const medicineGrid = document.getElementById('medicineGrid');
  const resetBtn = document.getElementById('resetBtn');
  const printBtn = document.getElementById('printBtn');

  let currentFile = null;

  // --- File Drop & Selection Handlers ---

  // Trigger file browser on click
  dropZone.addEventListener('click', (e) => {
    // Prevent re-triggering if sample button or child button was clicked
    if (e.target.closest('#loadSampleBtn') || e.target.closest('.preview-actions')) return;
    fileInput.click();
  });

  // Keyboard accessibility for dropzone
  dropZone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInput.click();
    }
  });

  // Drag and drop events
  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('drag-active');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('drag-active');
    }, false);
  });

  dropZone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files && files.length > 0) {
      handleSelectedFile(files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleSelectedFile(e.target.files[0]);
    }
  });

  // Change image button
  changeImageBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    hideError();
    fileInput.value = '';
    fileInput.click();
  });

  // Try with sample button
  loadSampleBtn.addEventListener('click', async (e) => {
    e.stopPropagation();
    try {
      showLoading(true, "Loading sample prescription image...");
      hideError();
      const response = await fetch('/api/sample-prescription');
      if (!response.ok) {
        throw new Error('Unable to load sample prescription image.');
      }
      const blob = await response.blob();
      const file = new File([blob], 'sample_prescription.png', { type: 'image/png' });
      showLoading(false);
      handleSelectedFile(file);
    } catch (err) {
      showLoading(false);
      showError('Sample Unavailable', err.message || 'Could not load sample image.');
    }
  });

  /**
   * Validates and displays the selected image file
   */
  function handleSelectedFile(file) {
    if (!file.type.startsWith('image/')) {
      showError('Invalid File Type', 'Please upload an image file (JPG, PNG, WEBP, or similar).');
      return;
    }

    // 15MB limit check
    if (file.size > 15 * 1024 * 1024) {
      showError('File Too Large', 'Please upload an image smaller than 15 MB.');
      return;
    }

    currentFile = file;
    hideError();
    resultsSection.classList.add('hidden');

    // Display metadata
    fileName.textContent = file.name;
    fileSize.textContent = formatBytes(file.size);

    // Read and show preview
    const reader = new FileReader();
    reader.onload = (e) => {
      imagePreview.src = e.target.result;
      dropZoneIdle.classList.add('hidden');
      sampleActionWrapper.classList.add('hidden');
      previewArea.classList.remove('hidden');
    };
    reader.readAsDataURL(file);
  }

  // --- API Call & Analysis ---

  analyzeBtn.addEventListener('click', async () => {
    if (!currentFile) {
      showError('No File Selected', 'Please upload or select a prescription image first.');
      return;
    }

    // Prepare UI for processing
    hideError();
    resultsSection.classList.add('hidden');
    showLoading(true, "Reading prescription and analyzing details...");

    analyzeBtn.disabled = true;
    analyzeBtn.classList.add('btn-disabled');

    try {
      // Fast client-side optimization to avoid uploading massive multi-megabyte camera photos
      const uploadFile = await compressImageClientSide(currentFile);
      const formData = new FormData();
      formData.append('file', uploadFile);

      const response = await fetch('/api/analyze', {
        method: 'POST',
        body: formData
      });

      let data;
      try {
        data = await response.json();
      } catch (parseErr) {
        data = { detail: response.statusText || `Server returned error (${response.status})` };
      }

      if (!response.ok) {
        // Handle rate limit with automated countdown
        if (response.status === 429) {
          const waitSeconds = data.retry_after || 25;
          showLoading(false);
          startAutoRetryCountdown(waitSeconds);
          return;
        }
        throw new Error(data.detail || `Server error (${response.status})`);
      }

      // Clear any pending retry timer and render
      clearInterval(retryCountdownTimer);
      renderResults(data);

    } catch (err) {
      console.error('Prescription processing error:', err);
      let title = "Reading Failed";
      const msg = err.message || "";
      if (msg.includes("temporarily busy") || msg.includes("rate limit")) {
        title = "Service Busy";
      } else if (msg.toLowerCase().includes("network") || msg.toLowerCase().includes("internet") || msg.includes("11001")) {
        title = "Connection Issue";
      }
      showError(
        title,
        msg || "An unexpected error occurred while analyzing the prescription."
      );
    } finally {
      showLoading(false);
      analyzeBtn.disabled = false;
      analyzeBtn.classList.remove('btn-disabled');
    }
  });

  /**
   * Populates results UI with plain language summary and medicine cards
   */
  function renderResults(data) {
    const medicines = data.medicines || [];

    // 1. Plain-Language Summary
    summaryText.textContent = data.summary || "No summary provided by the model.";

    // 2. Medicine count badge
    medicineCountBadge.textContent = `${medicines.length} medicine${medicines.length === 1 ? '' : 's'} identified`;

    // 3. Clear existing medicine cards
    medicineGrid.innerHTML = '';

    if (medicines.length === 0) {
      const emptyNote = document.createElement('div');
      emptyNote.className = 'card';
      emptyNote.style.textAlign = 'center';
      emptyNote.style.padding = '2rem';
      emptyNote.innerHTML = `
        <p style="color: var(--text-muted); font-size: 1rem;">
          No specific prescription medicines could be detected in this image. Please ensure the prescription is clearly visible and well-lit.
        </p>
      `;
      medicineGrid.appendChild(emptyNote);
    } else {
      // Create card for each medicine
      medicines.forEach((med, index) => {
        const card = createMedicineCard(med, index + 1);
        medicineGrid.appendChild(card);
      });
    }

    // Reveal results and scroll smoothly
    resultsSection.classList.remove('hidden');
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  /**
   * Formats an individual medicine card HTML element
   */
  function createMedicineCard(med, index) {
    const card = document.createElement('article');
    card.className = 'medicine-card';

    const isNameUnclear = isUnclear(med.name);

    card.innerHTML = `
      <div class="med-card-header">
        <div class="med-name-group">
          <div class="pill-icon-box" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z"/>
              <path d="m8.5 8.5 7 7"/>
            </svg>
          </div>
          <div>
            <h3 class="med-name">
              ${escapeHtml(med.name)}
            </h3>
          </div>
        </div>
        <span class="med-tag">Medication #${index}</span>
      </div>

      <div class="med-details-grid">
        ${renderDetailItem("Dosage", med.dosage, "💊")}
        ${renderDetailItem("Frequency", med.frequency, "🕒")}
        ${renderDetailItem("Duration", med.duration, "📅")}
        ${renderDetailItem("Special Instructions", med.instructions, "ℹ️", true)}
      </div>
    `;

    return card;
  }

  /**
   * Helper to render a detail field with unclear badge if ambiguous
   */
  function renderDetailItem(label, value, icon, isFullSpan = false) {
    const unclear = isUnclear(value);
    const spanClass = isFullSpan ? 'detail-span-full' : '';
    const wrapperClass = unclear ? 'unclear-item-wrapper' : '';

    let contentHtml = '';
    if (unclear) {
      contentHtml = `
        <span class="unclear-tag">
          <svg class="unclear-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          ${escapeHtml(value || "unclear — please confirm with your pharmacist")}
        </span>
      `;
    } else {
      contentHtml = `<span class="detail-value">${escapeHtml(value || 'Not specified')}</span>`;
    }

    return `
      <div class="med-detail-item ${spanClass} ${wrapperClass}">
        <span class="detail-label">
          <span>${icon}</span>
          ${label}
        </span>
        ${contentHtml}
      </div>
    `;
  }

  /**
   * Checks whether a field was flagged as unclear
   */
  function isUnclear(text) {
    if (!text) return true;
    const lower = text.toLowerCase();
    return lower.includes('unclear') || lower.includes('confirm with your pharmacist') || lower.includes('illegible');
  }

  // --- Reset & Print Controls ---

  resetBtn.addEventListener('click', () => {
    currentFile = null;
    fileInput.value = '';
    imagePreview.src = '';
    previewArea.classList.add('hidden');
    dropZoneIdle.classList.remove('hidden');
    sampleActionWrapper.classList.remove('hidden');
    resultsSection.classList.add('hidden');
    hideError();
    uploadCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });

  printBtn.addEventListener('click', () => {
    window.print();
  });

  dismissErrorBtn.addEventListener('click', () => {
    hideError();
  });

  // --- UI Helpers ---

  let loadingInterval = null;

  function showLoading(show, message = "Reading prescription...") {
    if (show) {
      clearInterval(loadingInterval);
      const titleEl = loadingCard.querySelector('.loading-title');
      const subtextEl = loadingCard.querySelector('.loading-subtext');
      
      const stages = [
        { title: "Uploading Prescription...", sub: "Optimizing image for fast analysis." },
        { title: "Scanning Doctor Handwriting...", sub: "Deciphering notes, drug names, and handwriting." },
        { title: "Cross-Referencing Medications...", sub: "Validating clinical dosages and treatment schedules." },
        { title: "Formulating Patient Instructions...", sub: "Finalizing clear, plain-language directions." }
      ];
      
      let step = 0;
      titleEl.textContent = stages[0].title;
      subtextEl.textContent = stages[0].sub;
      
      loadingInterval = setInterval(() => {
        step = (step + 1) % stages.length;
        titleEl.textContent = stages[step].title;
        subtextEl.textContent = stages[step].sub;
      }, 1300);

      loadingCard.classList.remove('hidden');
      uploadCard.classList.add('hidden');
    } else {
      clearInterval(loadingInterval);
      loadingCard.classList.add('hidden');
      uploadCard.classList.remove('hidden');
    }
  }

  function showError(title, message) {
    errorTitle.textContent = title;
    errorMessage.textContent = message;
    errorCard.classList.remove('hidden');
    errorCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  let retryCountdownTimer = null;

  function startAutoRetryCountdown(seconds) {
    clearInterval(retryCountdownTimer);
    let remaining = seconds;
    showError(
      "Service Busy (Cooldown)",
      `Service traffic is high. Automatically retrying in ${remaining}s...`
    );
    retryCountdownTimer = setInterval(() => {
      remaining--;
      if (remaining <= 0) {
        clearInterval(retryCountdownTimer);
        hideError();
        analyzeBtn.click();
      } else {
        errorMessage.textContent = `Service traffic is high. Automatically retrying in ${remaining}s...`;
      }
    }, 1000);
  }

  function hideError() {
    clearInterval(retryCountdownTimer);
    errorCard.classList.add('hidden');
  }

  async function compressImageClientSide(file) {
    if (!file || !file.type.startsWith('image/') || file.size < 250 * 1024) {
      return file;
    }
    return new Promise((resolve) => {
      const img = new Image();
      const objectUrl = URL.createObjectURL(file);

      const cleanup = () => {
        try {
          URL.revokeObjectURL(objectUrl);
        } catch (_) {}
      };

      img.onload = () => {
        cleanup();
        const MAX_DIM = 1600;
        let width = img.width;
        let height = img.height;

        if (width > MAX_DIM || height > MAX_DIM) {
          if (width > height) {
            height = Math.round((height * MAX_DIM) / width);
            width = MAX_DIM;
          } else {
            width = Math.round((width * MAX_DIM) / height);
            height = MAX_DIM;
          }
        }

        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);

        canvas.toBlob((blob) => {
          if (blob && blob.size < file.size) {
            resolve(new File([blob], file.name.replace(/\.[^/.]+$/, "") + ".jpg", { type: "image/jpeg" }));
          } else {
            resolve(file);
          }
        }, 'image/jpeg', 0.85);
      };

      img.onerror = () => {
        cleanup();
        resolve(file);
      };

      img.src = objectUrl;
    });
  }

  function formatBytes(bytes, decimals = 1) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  }

  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
});
