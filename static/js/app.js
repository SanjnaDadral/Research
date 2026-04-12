// ===================================
// PaperAIzer - Enhanced JavaScript
// Clean Professional Design
// ===================================

let currentAnalysisData = null;

document.addEventListener("DOMContentLoaded", function () {
  initInputMethodToggle();
  initFileUpload();
  initAnalyzeForm();
  initDeleteButtons();
  initExportButtons();
  initEmailModal();
  initSearchLibrary();
  initToasts();

  // Auto-dismiss server messages
  const serverMessages = document.querySelectorAll(".server-message");
  serverMessages.forEach((msg) => {
    setTimeout(() => {
      msg.style.transition = "opacity 0.3s ease";
      msg.style.opacity = "0";
      setTimeout(() => msg.remove(), 300);
    }, 5000);
  });
});

// ============ INPUT METHOD TOGGLE ============
function initInputMethodToggle() {
  const methodBtns = document.querySelectorAll(".method-tab");
  const inputPanels = document.querySelectorAll(".input-panel");

  if (!methodBtns.length || !inputPanels.length) return;

  methodBtns.forEach((btn) => {
    btn.addEventListener("click", function () {
      const method = this.dataset.method;

      methodBtns.forEach((b) => b.classList.remove("active"));
      this.classList.add("active");

      inputPanels.forEach((panel) => {
        panel.classList.remove("active");
        if (panel.dataset.method === method) {
          panel.classList.add("active");
        }
      });
    });
  });
}

// ============ FILE UPLOAD ============
function initFileUpload() {
  const fileUpload = document.querySelector(".file-upload");
  const fileInput = document.querySelector("#pdfFile");
  const fileNameDisplay = document.querySelector("#fileNameDisplay");

  if (!fileUpload || !fileInput) return;

  fileUpload.addEventListener("click", (e) => {
    if (e.target !== fileInput) {
      fileInput.click();
    }
  });

  fileUpload.addEventListener("dragover", (e) => {
    e.preventDefault();
    e.stopPropagation();
    fileUpload.classList.add("dragover");
  });

  fileUpload.addEventListener("dragleave", (e) => {
    e.preventDefault();
    e.stopPropagation();
    fileUpload.classList.remove("dragover");
  });

  fileUpload.addEventListener("drop", (e) => {
    e.preventDefault();
    e.stopPropagation();
    fileUpload.classList.remove("dragover");

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      if (file.type === "application/pdf" || file.name.endsWith(".pdf")) {
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        fileInput.files = dataTransfer.files;
        updateFileName(file.name, file.size);
      } else {
        showToast("Please select a PDF file", "error");
      }
    }
  });

  fileInput.addEventListener("change", function (e) {
    e.stopPropagation();
    if (this.files && this.files.length > 0) {
      const file = this.files[0];
      if (file.type === "application/pdf" || file.name.endsWith(".pdf")) {
        updateFileName(file.name, file.size);
      } else {
        showToast("Please select a PDF file", "error");
        this.value = "";
      }
    }
  });

  function updateFileName(name, bytes = 0) {
    if (fileNameDisplay) {
      const sizeMb = bytes ? (bytes / (1024 * 1024)).toFixed(2) : null;
      fileNameDisplay.textContent = sizeMb
        ? `Selected: ${name} (${sizeMb} MB)`
        : `Selected: ${name}`;
      fileNameDisplay.style.display = "block";
    }
  }
}

// ============ LOADING OVERLAY ============
function showLoadingOverlay() {
  const overlay = document.getElementById("loadingOverlay");
  if (overlay) {
    overlay.style.display = "flex";
    animateLoadingSteps();
  }
}

function hideLoadingOverlay() {
  const overlay = document.getElementById("loadingOverlay");
  if (overlay) {
    overlay.style.display = "none";
    resetLoadingSteps();
  }
}


function animateLoadingSteps() {
  const steps = ["step1", "step2", "step3", "step4"];
  let currentStep = 0;

  const interval = setInterval(() => {
    // Reset all steps to inactive first for a looping effect
    steps.forEach((step, idx) => {
      const el = document.getElementById(step);
      if (el) {
        if (idx < currentStep % steps.length) {
          el.classList.add("completed");
          el.classList.remove("active");
        } else if (idx === currentStep % steps.length) {
          el.classList.add("active");
          el.classList.remove("completed");
        } else {
          el.classList.remove("active", "completed");
        }
      }
    });
    currentStep++;
  }, 2000);

  return interval;
}

function resetLoadingSteps() {
  const steps = ["step1", "step2", "step3", "step4"];
  steps.forEach((step) => {
    const stepEl = document.getElementById(step);
    if (stepEl) {
      stepEl.classList.remove("active");
    }
  });
}

// ============ ANALYZE FORM ============
function initAnalyzeForm() {
  const form = document.getElementById("analyzeForm");
  if (!form) return;

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    e.stopPropagation();

    const submitBtn = document.getElementById("analyzeBtn");
    const btnText = document.getElementById("btnText");
    const statusBox = document.getElementById("analysisStatus");

    function setStatus(message, kind = "info") {
      if (!statusBox) return;
      statusBox.className = `analysis-status ${kind}`;
      statusBox.innerHTML = `<i class="fas fa-${kind === "success" ? "check-circle" : kind === "error" ? "exclamation-circle" : "info-circle"}"></i> ${escapeHtml(message)}`;
      statusBox.classList.remove("d-none");
    }

    function resetButton() {
      submitBtn.disabled = false;
      btnText.textContent = "Analyze with AI";
    }

    const inputType =
      document.querySelector(".method-tab.active")?.dataset.method;
    const formData = new FormData();
    formData.append("input_type", inputType);

    if (inputType === "pdf") {
      const fileInput = document.querySelector("#pdfFile");
      if (!fileInput.files || fileInput.files.length === 0) {
        showToast("Please select a PDF file", "error");
        return;
      }
      formData.append("pdf_file", fileInput.files[0]);
    } else if (inputType === "text") {
      const textContent = document.querySelector("#textContent")?.value.trim();
      if (!textContent || textContent.length < 50) {
        showToast("Text content must be at least 50 characters", "error");
        return;
      }
      formData.append("text_content", textContent);
    } else if (inputType === "url") {
      const urlInput = document.querySelector("#urlInput")?.value.trim();
      if (!urlInput) {
        showToast("Please enter a URL", "error");
        return;
      }
      formData.append("url_input", urlInput);
    }
    if (submitBtn) {
      submitBtn.disabled = true;
    }

    if (btnText) {
      btnText.innerHTML = '<span class="loading-spinner"></span> Analyzing...';
    }
    // submitBtn.disabled = true;
    // btnText.innerHTML = '<span class="loading-spinner"></span> Analyzing...';
    // setStatus(
    //   "Analysis in progress... Extracting and analyzing content, please wait.",
    //   "info",
    // );

    showLoadingOverlay();

    try {
      const controller = new AbortController();
      const timeoutMs = 300000;
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

      const response = await fetch("/analyze/", {
        method: "POST",
        body: formData,
        signal: controller.signal,
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
        },
      });

      clearTimeout(timeoutId);

      const data = await response.json();

      if (data.success) {
        currentAnalysisData = data.analysis;
        showToast("Analysis completed successfully!", "success");
        setStatus(
          "Analysis completed successfully. View the results below.",
          "success",
        );

        displayResultsWithTabs(data.analysis);
        scrollToResults();
      } else if (data.requires_login || response.status === 401) {
        showToast("Please log in to analyze documents", "warning");
        setStatus("Please log in to continue analyzing documents", "warning");
        setTimeout(() => {
          window.location.href = "/login/?next=" + encodeURIComponent("/");
        }, 1500);
      } else {
        showToast(data.error || "Analysis failed", "error");
        setStatus(data.error || "Analysis failed. Please try again.", "error");
      }
    } catch (error) {
      console.error("Error:", error);
      if (error.name === "AbortError") {
        showToast("Request timed out. Try a smaller file.", "error");
        setStatus(
          "Request timed out after 5 minutes. Please try a smaller file.",
          "error",
        );
      } else {
        showToast("An error occurred during analysis", "error");
        setStatus("An unexpected error occurred. Please try again.", "error");
      }
    } finally {
      hideLoadingOverlay();
      resetButton();
    }
  });
}

// ============ DISPLAY RESULTS WITH TABS ============
function displayResultsWithTabs(analysis) {
  const container = document.querySelector(".result-container");
  if (!container) return;

  const keywords = analysis.keywords || [];
  const links = analysis.extracted_links || [];
  const refs = analysis.references || [];
  const methodology = analysis.methodology || [];
  const technologies = analysis.technologies || [];
  const authors = analysis.authors || [];
  const stats = analysis.statistics || { word_count: 0, unique_words: 0 };
  const dsn = analysis.dataset_names || [];
  const dsl = analysis.dataset_links || [];
  const plag = analysis.plagiarism || {};
  const vis = analysis.visual_assets || {};
  const methSummary = analysis.methodology_summary || "";
  const extractedImages = analysis.extracted_images || [];
  const conclusion = analysis.conclusion || "";
  const datasetSection = analysis.dataset_section || "";

  const keywordsHtml = keywords.length
    ? keywords
      .map((kw) => `<span class="keyword-badge">${escapeHtml(kw)}</span>`)
      .join("")
    : '<span class="text-muted">No keywords extracted</span>';

  const methodologyHtml = methodology.length
    ? methodology
      .map((m) => `<span class="keyword-badge">${escapeHtml(m)}</span>`)
      .join("")
    : '<span class="text-muted">Methodology not detected</span>';

  const techHtml = technologies.length
    ? technologies
      .map((t) => `<span class="keyword-badge">${escapeHtml(t)}</span>`)
      .join("")
    : '<span class="text-muted">No specific technologies detected</span>';

  const linksHtml = links.slice(0, 15).length
    ? links
      .slice(0, 15)
      .map(
        (link) =>
          `<li><a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(link)}</a></li>`,
      )
      .join("")
    : '<li class="text-muted">No links found</li>';

  const refsHtml = refs.length
    ? refs
      .slice(0, 20)
      .map(
        (ref) => `
            <div class="reference-item">
                <div class="reference-title">${escapeHtml(ref)}</div>
            </div>
        `,
      )
      .join("")
    : '<p class="text-muted">No references found</p>';

  const authorsHtml = authors.length
    ? authors
      .map((a) => `<span class="keyword-badge">${escapeHtml(a)}</span>`)
      .join(" ")
    : '<span class="text-muted">Authors not detected</span>';

  const datasetsHtml = dsn.length
    ? dsn
      .map((n) => `<span class="keyword-badge">${escapeHtml(n)}</span>`)
      .join("")
    : '<span class="text-muted">No datasets mentioned</span>';

  const datasetLinksHtml = dsl.length
    ? dsl
      .slice(0, 10)
      .map(
        (link) =>
          `<li><a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(link)}</a></li>`,
      )
      .join("")
    : '<li class="text-muted">No dataset links found</li>';

  const noticeBlock = analysis.notice
    ? `<div class="analysis-status warning mb-3">
            <i class="fas fa-exclamation-triangle"></i>
            ${escapeHtml(analysis.notice)}
        </div>`
    : "";

  const plagScore = plag.similarity_percent || 0;
  const plagClass = plagScore < 25 ? "low" : plagScore < 50 ? "medium" : "high";
  const plagNote = plag.note || "Similarity check completed";
  const plagLabel =
    plagScore < 25 ? "Low Risk" : plagScore < 50 ? "Medium Risk" : "High Risk";

  const plagiarismHtml = `
        <div class="plagiarism-card mb-3">
            <div class="d-flex align-items-center justify-content-between mb-2">
                <h5 class="mb-0 d-flex align-items-center gap-2">
                    <i class="fas fa-shield-alt" style="color: var(--primary);"></i>
                    Plagiarism Check
                </h5>
                <span class="badge-custom">${plagScore}% - ${plagLabel}</span>
            </div>
            <div class="plagiarism-bar mb-2">
                <div class="plagiarism-bar-fill ${plagClass}" style="width: ${plagScore}%"></div>
            </div>
            <p class="text-muted small mb-0">${escapeHtml(plagNote)}</p>
            ${plag.matches && plag.matches.length
      ? `
                <div class="mt-3">
                    <small class="text-secondary fw-bold">Similar Documents:</small>
                    <ul class="link-list mt-2 small">
                        ${plag.matches
        .slice(0, 5)
        .map(
          (m) =>
            `<li>${escapeHtml(m.title)} — ${m.similarity_percent}% match</li>`,
        )
        .join("")}
                    </ul>
                </div>
            `
      : ""
    }
        </div>
    `;

  const visualTotal =
    (vis.figure_mentions || 0) +
    (vis.table_mentions || 0) +
    (vis.graph_chart_plot_mentions || 0);
  const hasVisualContent = visualTotal > 0;

  container.innerHTML = `
        <div class="card result-card" style="width: 100%; max-width: 100%; overflow-x: hidden;">
            ${noticeBlock}
            ${plagiarismHtml}
            
            <div class="result-header">
                <div class="result-header-info">
                    <h2 class="result-title">${escapeHtml(analysis?.title || "Untitled Document")}</h2>
                    <div class="result-meta">
                        <span class="badge-custom ${analysis.input_type}">
                            <i class="fas fa-${analysis.input_type === "pdf" ? "file-pdf" : analysis.input_type === "text" ? "file-alt" : "globe"}"></i>
                            ${analysis.input_type.toUpperCase()}
                        </span>
                        <span>
                            <i class="far fa-calendar"></i>
                            ${analysis.created_at}
                        </span>
                        ${analysis.publication_year
      ? `
                            <span>
                                <i class="far fa-clock"></i>
                                ${analysis.publication_year}
                            </span>
                        `
      : ""
    }
                    </div>
                </div>
                <div class="result-actions">
                    <button class="btn-secondary-custom" onclick="exportDocument(${analysis.document_id}, 'pdf')">
                        <i class="fas fa-file-pdf"></i> PDF
                    </button>
                    <button class="btn-secondary-custom" onclick="exportDocument(${analysis.document_id}, 'txt')">
                        <i class="fas fa-file-alt"></i> TXT
                    </button>
                    <button class="btn-secondary-custom" onclick="openEmailModal(${analysis.document_id})">
                        <i class="fas fa-envelope"></i> Email
                    </button>
                </div>
            </div>
            
            <!-- Result Tabs -->
            <div class="result-tabs" id="resultTabs">
                <button class="result-tab active" data-tab="overview">
                    <i class="fas fa-home"></i> Overview
                </button>
                <button class="result-tab" data-tab="abstract">
                    <i class="fas fa-file-alt"></i> Abstract
                </button>
                <button class="result-tab" data-tab="summary">
                    <i class="fas fa-list"></i> Summary
                </button>
                <button class="result-tab" data-tab="methodology">
                    <i class="fas fa-cogs"></i> Methodology
                </button>
                <button class="result-tab" data-tab="dataset">
                    <i class="fas fa-database"></i> Dataset
                </button>
                <button class="result-tab" data-tab="results">
                    <i class="fas fa-chart-line"></i> Results
                </button>
                <button class="result-tab" data-tab="conclusion">
                    <i class="fas fa-flag-checkered"></i> Conclusion
                </button>
                <button class="result-tab" data-tab="keywords">
                    <i class="fas fa-tags"></i> Keywords
                </button>
                <button class="result-tab" data-tab="technology">
                    <i class="fas fa-microchip"></i> Technology
                </button>
                <button class="result-tab" data-tab="plagiarism">
                    <i class="fas fa-shield-alt"></i> Plagiarism
                </button>
                <button class="result-tab" data-tab="visuals">
                    <i class="fas fa-chart-bar"></i> Visuals
                </button>
                <button class="result-tab" data-tab="references">
                    <i class="fas fa-book"></i> References
                </button>
                <button class="result-tab" data-tab="links">
                    <i class="fas fa-link"></i> Links
                </button>
                <button class="result-tab" data-tab="statistics">
                    <i class="fas fa-chart-pie"></i> Statistics
                </button>
            </div>
            
            <!-- Tab Contents -->
            <div class="tab-contents">
                <!-- Overview Tab -->
                <div class="result-content active" id="tab-overview">
                    ${authors.length
      ? `
                    <div class="mb-3">
                        <h5 class="section-title">
                            <i class="fas fa-users"></i> Authors
                        </h5>
                        <div class="keyword-container">${authorsHtml}</div>
                    </div>
                    `
      : ""
    }
                    
                    ${analysis.goal
      ? `
                    <div class="mb-3">
                        <h5 class="section-title">
                            <i class="fas fa-bullseye"></i> Main Purpose / Goal
                        </h5>
                        <p class="section-content">${escapeHtml(analysis.goal)}</p>
                    </div>
                    `
      : ""
    }
                    
                    ${analysis.impact
      ? `
                    <div class="mb-3">
                        <h5 class="section-title">
                            <i class="fas fa-star"></i> Impact
                        </h5>
                        <p class="section-content">${escapeHtml(analysis.impact)}</p>
                    </div>
                    `
      : ""
    }
                    
                    <div class="row g-2">
                        <div class="col-6 col-md-3">
                            <div class="stat-card">
                                <div class="stat-value">${methodology.length}</div>
                                <div class="stat-label">Methods</div>
                            </div>
                        </div>
                        <div class="col-6 col-md-3">
                            <div class="stat-card">
                                <div class="stat-value">${technologies.length}</div>
                                <div class="stat-label">Technologies</div>
                            </div>
                        </div>
                        <div class="col-6 col-md-3">
                            <div class="stat-card">
                                <div class="stat-value">${visualTotal}</div>
                                <div class="stat-label">Visuals</div>
                            </div>
                        </div>
                        <div class="col-6 col-md-3">
                            <div class="stat-card">
                                <div class="stat-value">${refs.length}</div>
                                <div class="stat-label">References</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Abstract Tab -->
                <div class="result-content" id="tab-abstract">
                    <h5 class="section-title">
                        <i class="fas fa-file-alt"></i> Abstract
                    </h5>
                    ${analysis.abstract
      ? `
                    <div class="section-content" style="background: var(--bg-secondary); padding: 1rem; border-radius: var(--radius); border-left: 3px solid var(--primary);">
                        ${escapeHtml(analysis.abstract)}
                    </div>
                    `
      : '<span class="text-muted">Abstract not found in document</span>'
    }
                </div>
                
                <!-- Summary Tab -->
                <div class="result-content" id="tab-summary">
                    <h5 class="section-title">
                        <i class="fas fa-list"></i> Summary
                    </h5>
                    ${analysis.summary
      ? `
                    <div class="section-content" style="background: var(--bg-secondary); padding: 1rem; border-radius: var(--radius); border-left: 3px solid var(--success);">
                        ${escapeHtml(analysis.summary)}
                    </div>
                    `
      : '<span class="text-muted">Summary could not be generated</span>'
    }
                </div>
                
                <!-- Methodology Tab -->
                <div class="result-content" id="tab-methodology">
                    <h5 class="section-title">
                        <i class="fas fa-cogs"></i> Methodology
                    </h5>
                    <div class="keyword-container mb-2">${methodologyHtml}</div>
                    ${methSummary
      ? `
                    <h6 class="text-secondary mb-2" style="font-size: 0.85rem;">Methodology Details:</h6>
                    <div class="section-content" style="background: var(--bg-secondary); padding: 1rem; border-radius: var(--radius); border-left: 3px solid var(--secondary);">
                        ${escapeHtml(methSummary)}
                    </div>
                    `
      : ""
    }
                </div>
                
                <!-- Dataset Tab -->
                <div class="result-content" id="tab-dataset">
                    <h5 class="section-title">
                        <i class="fas fa-database"></i> Dataset Information
                    </h5>
                    <div class="row g-3">
                        <div class="col-md-6">
                            <h6 class="text-secondary mb-2" style="font-size: 0.85rem;">Dataset Names</h6>
                            <div class="keyword-container">${datasetsHtml}</div>
                        </div>
                        <div class="col-md-6">
                            <h6 class="text-secondary mb-2" style="font-size: 0.85rem;">Dataset Links</h6>
                            ${dsl.length ? `<ul class="link-list">${datasetLinksHtml}</ul>` : '<p class="text-muted">No dataset links found</p>'}
                        </div>
                    </div>
                    ${datasetSection
      ? `
                    <div class="mt-3">
                        <h6 class="text-secondary mb-2" style="font-size: 0.85rem;">Dataset Section:</h6>
                        <div class="section-content" style="background: var(--bg-secondary); padding: 1rem; border-radius: var(--radius); border-left: 3px solid var(--accent); max-height: 300px; overflow-y: auto;">
                            ${escapeHtml(datasetSection)}
                        </div>
                    </div>
                    `
      : ""
    }
                </div>
                
                <!-- Results Tab -->
                <div class="result-content" id="tab-results">
                    <h5 class="section-title">
                        <i class="fas fa-chart-line"></i> Results & Findings
                    </h5>
                    ${analysis.impact
      ? `
                    <div class="mb-3">
                        <h6 class="text-secondary mb-2" style="font-size: 0.85rem;">Key Findings:</h6>
                        <div class="section-content" style="background: var(--bg-secondary); padding: 1rem; border-radius: var(--radius); border-left: 3px solid var(--success);">
                            ${escapeHtml(analysis.impact)}
                        </div>
                    </div>
                    `
      : ""
    }
                    ${hasVisualContent
      ? `
                    <div class="visual-grid">
                        <div class="visual-card">
                            <i class="fas fa-image"></i>
                            <div class="count">${vis.figure_mentions || 0}</div>
                            <div class="label">Figures</div>
                        </div>
                        <div class="visual-card">
                            <i class="fas fa-table"></i>
                            <div class="count">${vis.table_mentions || 0}</div>
                            <div class="label">Tables</div>
                        </div>
                        <div class="visual-card">
                            <i class="fas fa-chart-line"></i>
                            <div class="count">${vis.graph_chart_plot_mentions || 0}</div>
                            <div class="label">Charts & Plots</div>
                        </div>
                    </div>
                    `
      : '<p class="text-muted">No visual elements detected</p>'
    }
                </div>
                
                <!-- Conclusion Tab -->
                <div class="result-content" id="tab-conclusion">
                    <h5 class="section-title">
                        <i class="fas fa-flag-checkered"></i> Conclusion
                    </h5>
                    ${conclusion
      ? `
                    <div class="section-content" style="background: var(--bg-secondary); padding: 1rem; border-radius: var(--radius); border-left: 3px solid var(--accent);">
                        ${escapeHtml(conclusion)}
                    </div>
                    `
      : '<span class="text-muted">Conclusion section not found in document</span>'
    }
                </div>
                
                <!-- Keywords Tab -->
                <div class="result-content" id="tab-keywords">
                    <h5 class="section-title">
                        <i class="fas fa-tags"></i> Keywords
                    </h5>
                    <div class="keyword-container">${keywordsHtml}</div>
                </div>
                
                <!-- Technology Tab -->
                <div class="result-content" id="tab-technology">
                    <h5 class="section-title">
                        <i class="fas fa-microchip"></i> Technologies & Tools
                    </h5>
                    <div class="keyword-container">${techHtml}</div>
                </div>
                
                <!-- Plagiarism Tab -->
                <div class="result-content" id="tab-plagiarism">
                    <div class="plagiarism-card">
                        <div class="plagiarism-score mb-2">
                            <div class="plagiarism-percentage">${plagScore}%</div>
                            <div>
                                <div style="font-weight: 600; color: var(--text-primary);">Similarity Score</div>
                                <small class="text-muted">${plagScore < 25 ? "Low similarity - Original work" : plagScore < 50 ? "Moderate similarity - Review recommended" : "High similarity - Requires review"}</small>
                            </div>
                        </div>
                        <div class="plagiarism-bar mb-2">
                            <div class="plagiarism-bar-fill ${plagClass}" style="width: ${plagScore}%"></div>
                        </div>
                        <p class="text-muted mb-0">${escapeHtml(plagNote)}</p>
                        ${plag.matches && plag.matches.length
      ? `
                            <div class="mt-3">
                                <h6 class="text-secondary mb-2" style="font-size: 0.85rem;">Similar Documents:</h6>
                                <div class="reference-list">
                                    ${plag.matches
        .slice(0, 10)
        .map(
          (m) => `
                                        <div class="reference-item">
                                            <div class="reference-title">${escapeHtml(m.title)}</div>
                                            <div class="reference-authors">${m.similarity_percent}% match</div>
                                        </div>
                                    `,
        )
        .join("")}
                                </div>
                            </div>
                        `
      : '<p class="text-muted mt-2">No similar documents found in your library.</p>'
    }
                    </div>
                </div>
                
                <!-- Visuals Tab -->
                <div class="result-content" id="tab-visuals">
                    <h5 class="section-title">
                        <i class="fas fa-images"></i> Visual Elements
                    </h5>
                    ${hasVisualContent
      ? `
                    <div class="visual-grid">
                        <div class="visual-card">
                            <i class="fas fa-image"></i>
                            <div class="count">${vis.figure_mentions || 0}</div>
                            <div class="label">Figures</div>
                        </div>
                        <div class="visual-card">
                            <i class="fas fa-table"></i>
                            <div class="count">${vis.table_mentions || 0}</div>
                            <div class="label">Tables</div>
                        </div>
                        <div class="visual-card">
                            <i class="fas fa-chart-line"></i>
                            <div class="count">${vis.graph_chart_plot_mentions || 0}</div>
                            <div class="label">Charts & Plots</div>
                        </div>
                    </div>
                    ${vis.pdf_embedded_image_objects !== undefined &&
        vis.pdf_embedded_image_objects > 0
        ? `
                    <div class="mt-3 p-2" style="background: var(--bg-secondary); border-radius: var(--radius); border-left: 3px solid var(--primary);">
                        <small class="text-muted">
                            <strong>Note:</strong> The PDF contains approximately ${vis.pdf_embedded_image_objects} embedded image objects.
                        </small>
                    </div>
                    `
        : ""
      }
                    `
      : `
                    <div class="empty-state" style="padding: 2rem;">
                        <i class="fas fa-chart-bar" style="font-size: 2rem;"></i>
                        <p class="text-muted mt-2">No visual elements detected in this document</p>
                    </div>
                    `
    }
                    
                    ${extractedImages.length
      ? `
                    <div class="mt-4">
                        <h6 class="section-title">
                            <i class="fas fa-images"></i> Extracted Images (${extractedImages.length})
                        </h6>
                        <p class="text-muted small mb-2">Click on an image to view full size</p>
                        <div class="row g-2">
                            ${extractedImages
        .map(
          (img) => `
                                <div class="col-6 col-md-4 col-lg-3">
                                    <div class="extracted-image-card" style="border: 1px solid var(--border-color); border-radius: var(--radius); overflow: hidden; cursor: pointer; transition: var(--transition);" onclick="window.open('${escapeHtml(img.url)}', '_blank')" onmouseover="this.style.borderColor='var(--primary)'" onmouseout="this.style.borderColor='var(--border-color)'">
                                        <img src="${escapeHtml(img.url)}" alt="Extracted from page ${img.page}" style="width: 100%; height: 150px; object-fit: cover; display: block;" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><rect fill=%22%23f1f5f9%22 width=%22100%22 height=%22100%22/><text x=%2250%22 y=%2255%22 text-anchor=%22middle%22 fill=%22%2394a3b8%22 font-size=%2212%22>Image</text></svg>'">
                                        <div style="padding: 0.5rem; background: var(--bg-secondary); font-size: 0.8rem; text-align: center;">
                                            <i class="fas fa-file-pdf"></i> Page ${img.page}
                                        </div>
                                    </div>
                                </div>
                            `,
        )
        .join("")}
                        </div>
                    </div>
                    `
      : ""
    }
                </div>
                
                <!-- References Tab -->
                <div class="result-content" id="tab-references">
                    <h5 class="section-title">
                        <i class="fas fa-book"></i> References (${refs.length})
                    </h5>
                    <div class="reference-list">${refsHtml}</div>
                </div>
                
                <!-- Links Tab -->
                <div class="result-content" id="tab-links">
                    <h5 class="section-title">
                        <i class="fas fa-link"></i> Extracted Links (${links.length})
                    </h5>
                    <ul class="link-list">${linksHtml}</ul>
                </div>
                
                <!-- Statistics Tab -->
                <div class="result-content" id="tab-statistics">
                    <h5 class="section-title">
                        <i class="fas fa-chart-pie"></i> Document Statistics
                    </h5>
                    <div class="row g-2">
                        <div class="col-6 col-md-3">
                            <div class="stat-card">
                                <div class="stat-value">${(stats.word_count || 0).toLocaleString()}</div>
                                <div class="stat-label">Total Words</div>
                            </div>
                        </div>
                        <div class="col-6 col-md-3">
                            <div class="stat-card">
                                <div class="stat-value">${(stats.unique_words || 0).toLocaleString()}</div>
                                <div class="stat-label">Unique Words</div>
                            </div>
                        </div>
                        <div class="col-6 col-md-3">
                            <div class="stat-card">
                                <div class="stat-value">${links.length}</div>
                                <div class="stat-label">Links Found</div>
                            </div>
                        </div>
                        <div class="col-6 col-md-3">
                            <div class="stat-card">
                                <div class="stat-value">${refs.length}</div>
                                <div class="stat-label">References</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

  initResultTabs();
}

function initResultTabs() {
  const tabs = document.querySelectorAll(".result-tab");
  const contents = document.querySelectorAll(".result-content");

  tabs.forEach((tab) => {
    tab.addEventListener("click", function () {
      const tabId = this.dataset.tab;

      tabs.forEach((t) => t.classList.remove("active"));
      this.classList.add("active");

      contents.forEach((content) => {
        content.classList.remove("active");
        if (content.id === `tab-${tabId}`) {
          content.classList.add("active");
        }
      });
    });
  });
}

function scrollToResults() {
  setTimeout(() => {
    const container = document.querySelector(".result-container");
    if (container) {
      container.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, 300);
}

// ============ DELETE BUTTONS ============
function initDeleteButtons() {
  // Prevent double popup: logic is now handled uniquely by specific pages like library.html
}

function showDeleteConfirmation(documentId, btnElement) {
  const modalHtml = `
        <div class="modal fade" id="deleteConfirmModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered modal-sm">
                <div class="modal-content">
                    <div class="modal-body text-center py-4">
                        <div class="confirm-modal-icon">
                            <i class="fas fa-trash-alt"></i>
                        </div>
                        <h5 class="mb-2">Delete Document?</h5>
                        <p class="confirm-modal-text">
                            This action cannot be undone.
                        </p>
                        <div class="d-flex gap-2 justify-content-center">
                            <button type="button" class="btn-secondary-custom" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn-danger-confirm" id="confirmDeleteBtn">Delete</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

  const existingModal = document.getElementById("deleteConfirmModal");
  if (existingModal) {
    existingModal.remove();
  }

  document.body.insertAdjacentHTML("beforeend", modalHtml);

  const modal = new bootstrap.Modal(
    document.getElementById("deleteConfirmModal"),
  );
  modal.show();

  document
    .getElementById("confirmDeleteBtn")
    .addEventListener("click", async function () {
      modal.hide();

      try {
        const formData = new FormData();
        const response = await fetch(`/delete/${documentId}/`, {
          method: "POST",
          body: formData,
          headers: {
            "X-CSRFToken": getCookie("csrftoken"),
          },
        });

        // Parse JSON response to check success
        const data = await response.json();

        if (data.success) {
          showToast("Document deleted successfully", "success");
          const card = btnElement.closest(".library-card");
          if (card) {
            card.style.transition = "opacity 0.3s ease";
            card.style.opacity = "0";
            setTimeout(() => card.remove(), 300);
          } else {
            // If no card found, redirect to library after a short delay
            setTimeout(() => {
              window.location.href = '/library/';
            }, 500);
          }
        } else if (response.status === 401) {
          showToast("Please log in to delete documents", "warning");
          window.location.href = "/login/";
        } else {
          throw new Error(data.error || "Delete failed");
        }
      } catch (error) {
        showToast("Failed to delete document: " + error.message, "error");
      }
    });

  document
    .getElementById("deleteConfirmModal")
    .addEventListener("hidden.bs.modal", function () {
      this.remove();
    });
}

// ============ EXPORT BUTTONS ============
function initExportButtons() {
  // Export buttons are dynamically created in displayResultsWithTabs
  // This function ensures event delegation is ready
  document.addEventListener("click", function (e) {
    if (e.target.classList && e.target.classList.contains("btn-export")) {
      const documentId = e.target.dataset.documentId;
      const format = e.target.dataset.format;
      if (documentId && format) {
        exportDocument(documentId, format);
      }
    }
    if (e.target.classList && e.target.classList.contains("btn-email")) {
      const documentId = e.target.dataset.documentId;
      if (documentId) {
        openEmailModal(documentId);
      }
    }
  });
}

// ============ EXPORT ============
async function exportDocument(documentId, format) {
  showToast(`Generating ${format.toUpperCase()} report...`, "info");

  try {
    const response = await fetch(`/export/${documentId}/${format}/`, {
      method: "GET",
      credentials: "include",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
    });

    if (response.ok) {
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `analysis_report_${documentId}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();

      showToast("Download started!", "success");
    } else if (response.status === 401) {
      showToast("Please log in to download", "warning");
      window.location.href = "/login/";
    } else {
      throw new Error(`Export failed: ${response.status}`);
    }
  } catch (error) {
    console.error("Export error:", error);
    showToast("Failed to export document: " + error.message, "error");
  }
}

// ============ EMAIL MODAL ============
function openEmailModal(documentId) {
  const modal = new bootstrap.Modal(document.getElementById("emailModal"));
  document.getElementById("emailDocumentId").value = documentId;
  modal.show();
}

function initEmailModal() {
  const form = document.getElementById("emailForm");
  if (!form) return;

  form.addEventListener("submit", async function (e) {
    e.preventDefault();

    const documentId = document.getElementById("emailDocumentId").value;
    const email = document.getElementById("emailInput").value;
    const exportFormat = document.getElementById("emailFormat")?.value || "pdf";

    try {
      const formData = new FormData();
      formData.append("email", email);
      formData.append("export_format", exportFormat);

      const response = await fetch(`/email/${documentId}/`, {
        method: "POST",
        body: formData,
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
        },
      });

      const data = await response.json();

      if (data.success) {
        showToast("Email sent successfully!", "success");
        bootstrap.Modal.getInstance(
          document.getElementById("emailModal"),
        ).hide();
        form.reset();
      } else {
        showToast(data.error || "Failed to send email", "error");
      }
    } catch (error) {
      showToast("Failed to send email. Please try again.", "error");
    }
  });
}

// ============ SEARCH LIBRARY ============
function initSearchLibrary() {
  const searchInput = document.getElementById("librarySearch");
  const typeFilters = document.querySelectorAll(".filter-tab");

  if (searchInput) {
    let searchTimeout;
    searchInput.addEventListener("input", function () {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => updateLibrary(), 500);
    });
  }

  typeFilters.forEach((filter) => {
    filter.addEventListener("click", function (e) {
      e.preventDefault();
      typeFilters.forEach((f) => f.classList.remove("active"));
      this.classList.add("active");
      updateLibrary();
    });
  });

  async function updateLibrary() {
    const searchQuery = searchInput ? searchInput.value : "";
    const typeFilter =
      document.querySelector(".filter-tab.active")?.dataset.type || "";

    const params = new URLSearchParams();
    if (searchQuery) params.append("q", searchQuery);
    if (typeFilter) params.append("type", typeFilter);

    try {
      const response = await fetch(`/library/?${params.toString()}`, {
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
      });

      const html = await response.text();
      const temp = document.createElement("div");
      temp.innerHTML = html;

      const newGrid = temp.querySelector(".library-grid");
      const libraryGrid = document.querySelector(".library-grid");

      if (newGrid && libraryGrid) {
        libraryGrid.innerHTML = newGrid.innerHTML;
        initDeleteButtons();
      }
    } catch (error) {
      console.error("Search error:", error);
    }
  }
}

// ============ TOASTS ============
function initToasts() {
  window.showToast = function (message, type = "info") {
    const container =
      document.querySelector(".toast-container") || createToastContainer();

    const iconMap = {
      success: "check-circle",
      error: "exclamation-circle",
      warning: "exclamation-triangle",
      info: "info-circle",
    };

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `
            <i class="fas fa-${iconMap[type] || "info-circle"}"></i>
            <span>${escapeHtml(message)}</span>
        `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.animation = "slideInRight 0.25s ease reverse";
      setTimeout(() => toast.remove(), 250);
    }, 4000);
  };

  function createToastContainer() {
    const container = document.createElement("div");
    container.className = "toast-container";
    document.body.appendChild(container);
    return container;
  }
}

// ============ UTILITIES ============
function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// Expose functions to window
window.exportDocument = exportDocument;
window.openEmailModal = openEmailModal;
window.showToast = window.showToast;
