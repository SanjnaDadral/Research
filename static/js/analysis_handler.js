/**
 * Enhanced Analysis Form Handler
 * Fixed: input_type detection, file sync, CSRF, error handling
 */

class AnalysisHandler {
  constructor() {
    this.isProcessing = false;
    this.currentFile = null;
    this.init();
  }

  init() {
    this.methodTabs = document.querySelectorAll(".method-tab");
    this.methodContents = document.querySelectorAll("[data-method]");
    this.submitBtn = document.getElementById("submitBtn");
    this.pdfInput = document.getElementById("pdfFile");
    this.textInput = document.getElementById("textContent");
    this.urlInput = document.getElementById("urlInput");
    this.form = document.getElementById("analyzeForm");
    this.fourBoxesContainer = document.getElementById("fourBoxesAnimation");

    if (!this.form) return;

    // Method tabs (only if they exist)
    this.methodTabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const method = tab.dataset.method;
        if (method) this.switchMethodByName(method);
      });
    });

    // File input change
    if (this.pdfInput) {
      this.pdfInput.addEventListener("change", (e) => this.handleFileSelect(e));
    }

    // Form submit
    this.form.addEventListener("submit", (e) => this.handleSubmit(e));

    // Drag and drop
    const dropZone =
      document.querySelector(".file-upload-area") ||
      document.getElementById("uploadZone");

    if (dropZone && this.pdfInput) {
      dropZone.addEventListener("dragover", (e) => this.handleDragOver(e));
      dropZone.addEventListener("dragleave", (e) => this.handleDragLeave(e));
      dropZone.addEventListener("drop", (e) => this.handleFileDrop(e));
    }
  }

  // ─── Method Switching ────────────────────────────────────────────────────────

  switchMethodByName(method) {
    this.methodTabs.forEach((t) => t.classList.remove("active"));

    const matchingTab = document.querySelector(
      `.method-tab[data-method="${method}"]`,
    );
    if (matchingTab) matchingTab.classList.add("active");

    this.methodContents.forEach((c) => (c.style.display = "none"));

    const content = document.querySelector(`[data-method="${method}"]`);
    if (content) {
      content.style.display = "block";
      content.style.animation = "fadeIn 0.3s ease-in";
    }

    const inputTypeEl = document.getElementById("inputType");
    if (inputTypeEl) inputTypeEl.value = method;
  }

  // ─── File Handling ───────────────────────────────────────────────────────────

  handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    this.currentFile = file;
    this.validateFile(file);
  }

  handleDragOver(event) {
    event.preventDefault();
    event.currentTarget.style.borderColor = "var(--primary)";
    event.currentTarget.style.backgroundColor = "rgba(99, 102, 241, 0.05)";
  }

  handleDragLeave(event) {
    event.currentTarget.style.borderColor = "var(--border-color)";
    event.currentTarget.style.backgroundColor = "transparent";
  }

  handleFileDrop(event) {
    event.preventDefault();
    event.currentTarget.style.borderColor = "var(--border-color)";
    event.currentTarget.style.backgroundColor = "transparent";

    const files = event.dataTransfer.files;
    if (files.length > 0) {
      this.pdfInput.files = files;
      this.currentFile = files[0];
      this.validateFile(this.currentFile);

      // Update file name display
      const fileSelected = document.getElementById("fileSelected");
      if (fileSelected) {
        fileSelected.style.display = "block";
        fileSelected.innerText = files[0].name;
      }
    }
  }

  validateFile(file) {
    const maxSize = 45 * 1024 * 1024;
    const errors = [];

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      errors.push("⚠️ Only PDF files are supported");
    }
    if (file.size > maxSize) {
      errors.push(`⚠️ File size exceeds 45MB limit`);
    }
    if (file.size < 1000) {
      errors.push("⚠️ File appears to be empty");
    }

    if (errors.length > 0) {
      this.showError(errors.join("<br>"));
      if (this.pdfInput) this.pdfInput.value = "";
      this.currentFile = null;
      return false;
    }

    this.showFileInfo(file);
    return true;
  }

  showFileInfo(file) {
    const fileInfo = document.getElementById("fileInfo");
    if (fileInfo) {
      const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
      fileInfo.innerHTML = `
        <div style="color: var(--text-secondary); font-size: 0.9rem;">
          <i class="fas fa-check-circle" style="color: #22c55e;"></i>
          <strong>${file.name}</strong> (${sizeMB}MB)
        </div>
      `;
    }

    // Also update fileSelected div if present (upload.html)
    const fileSelected = document.getElementById("fileSelected");
    if (fileSelected) {
      fileSelected.style.display = "block";
      fileSelected.innerText = file.name;
    }
  }

  // ─── Form Submit ─────────────────────────────────────────────────────────────

  async handleSubmit(event) {
    event.preventDefault();

    if (this.isProcessing) {
      this.showError("Analysis already in progress. Please wait.");
      return;
    }

    // ✅ FIX: Read input_type from hidden field directly — don't rely on tabs
    const inputTypeEl =
      document.querySelector('[name="input_type"]') ||
      document.getElementById("inputType");
    const inputType = inputTypeEl?.value || "pdf";

    // ✅ FIX: Sync currentFile from input in case it was set before JS init
    if (inputType === "pdf" && !this.currentFile && this.pdfInput?.files[0]) {
      this.currentFile = this.pdfInput.files[0];
    }

    if (!this.validateInput(inputType)) return;

    // Build FormData
    const formData = new FormData();
    formData.append("input_type", inputType);

    if (inputType === "pdf") {
      formData.append("pdf_file", this.currentFile);
    } else if (inputType === "text") {
      formData.append("text_content", this.textInput?.value?.trim() || "");
    } else if (inputType === "url") {
      formData.append("url_input", this.urlInput?.value?.trim() || "");
    }

    await this.submitAnalysis(formData);
  }

  validateInput(inputType) {
    if (inputType === "pdf") {
      if (!this.currentFile) {
        this.showError("❌ Please select a PDF file first");
        return false;
      }
    } else if (inputType === "text") {
      const text = this.textInput?.value?.trim() || "";
      if (text.length < 50) {
        this.showError("❌ Text must be at least 50 characters");
        return false;
      }
    } else if (inputType === "url") {
      const url = this.urlInput?.value?.trim() || "";
      if (!url.startsWith("http")) {
        this.showError("❌ Please enter a valid URL (starting with http)");
        return false;
      }
    }
    return true;
  }

  // ─── API Call ────────────────────────────────────────────────────────────────

  async submitAnalysis(formData) {
    this.isProcessing = true;
    this.disableForm();
    this.showFourBoxesAnimation();

    let currentStep = 1;
    this.updateFourBoxes(currentStep);

    const simulationInterval = setInterval(() => {
      if (currentStep < 3) {
        currentStep++;
        this.updateFourBoxes(currentStep);
      } else {
        clearInterval(simulationInterval);
      }
    }, 4500);

    try {
      const response = await fetch("/analyze/", {
        method: "POST",
        body: formData,
        credentials: "same-origin",
        headers: {
          // ✅ Send CSRF token — safe with FormData (do NOT set Content-Type)
          "X-CSRFToken": this.getCsrfToken(),
        },
      });

      clearInterval(simulationInterval);

      let data;
      try {
        data = await response.json();
      } catch (e) {
        this.showError(
          "❌ Server returned an invalid response. Please try again.",
        );
        return;
      }

      if (!response.ok || !data.success) {
        this.showError(data.error || "❌ Analysis failed. Please try again.");
        return;
      }

      // Success
      this.updateFourBoxes(4);
      this.showSuccess(data);

      setTimeout(() => {
        window.location.href = data.redirect_url;
      }, 800);
    } catch (error) {
      clearInterval(simulationInterval);
      console.error("Analysis error:", error);
      this.showError(
        `❌ Network error: ${error.message || "Please check your connection"}`,
      );
    } finally {
      this.isProcessing = false;
      this.enableForm();
    }
  }

  // ─── Animation ───────────────────────────────────────────────────────────────

  showFourBoxesAnimation() {
    if (this.fourBoxesContainer) {
      this.fourBoxesContainer.style.display = "block";
    }
  }

  updateFourBoxes(step) {
    if (!this.fourBoxesContainer) return;

    const boxes = this.fourBoxesContainer.querySelectorAll(".box");
    boxes.forEach((box, index) => {
      if (index + 1 < step) {
        box.classList.remove("active");
        box.classList.add("completed");
        const icon = box.querySelector("i");
        if (icon) icon.className = "fas fa-check";
      } else if (index + 1 === step) {
        box.classList.add("active");
        box.classList.remove("completed");
      } else {
        box.classList.remove("active", "completed");
      }
    });
  }

  // ─── UI Feedback ─────────────────────────────────────────────────────────────

  showError(message) {
    const errorDiv =
      document.getElementById("errorMessage") || this.createErrorDiv();
    errorDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> <span>${message}</span>`;
    errorDiv.style.display = "block";
    errorDiv.scrollIntoView({ behavior: "smooth", block: "center" });

    // Hide four boxes animation on error
    if (this.fourBoxesContainer) {
      this.fourBoxesContainer.style.display = "none";
    }
  }

  showSuccess(data) {
    const errorDiv = document.getElementById("errorMessage");
    if (errorDiv) errorDiv.style.display = "none";

    const successDiv = document.getElementById("successMessage");
    if (successDiv) {
      successDiv.innerHTML = `
        <i class="fas fa-check-circle" style="color: #22c55e;"></i>
        <div style="flex: 1;">
          <strong>✅ Analysis Complete!</strong>
          <p style="margin-bottom: 0; font-size: 0.9rem; color: var(--text-secondary);">
            Redirecting to results...
          </p>
        </div>
      `;
      successDiv.style.display = "flex";
      successDiv.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  createErrorDiv() {
    const div = document.createElement("div");
    div.id = "errorMessage";
    div.style.cssText = `
      display: none;
      background: rgba(239, 68, 68, 0.1);
      border-left: 4px solid #dc2626;
      color: #dc2626;
      padding: 1rem;
      border-radius: 8px;
      margin-bottom: 1rem;
      gap: 1rem;
    `;
    this.form.parentNode.insertBefore(div, this.form);
    return div;
  }

  disableForm() {
    if (this.submitBtn) {
      this.submitBtn.disabled = true;
      this.submitBtn.innerHTML =
        '<i class="fas fa-spinner fa-spin me-2"></i>Analyzing...';
    }
    if (this.pdfInput) this.pdfInput.disabled = true;
  }

  enableForm() {
    if (this.submitBtn) {
      this.submitBtn.disabled = false;
      this.submitBtn.innerHTML =
        '<i class="fas fa-magic me-2"></i>Analyze Paper';
    }
    if (this.pdfInput) this.pdfInput.disabled = false;
  }

  // ─── CSRF ────────────────────────────────────────────────────────────────────

  getCsrfToken() {
    return (
      document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
      document.cookie
        .split("; ")
        .find((row) => row.startsWith("csrftoken="))
        ?.split("=")[1] ||
      ""
    );
  }
}

// ─── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  new AnalysisHandler();
});

// Fade-in animation
const style = document.createElement("style");
style.textContent = `
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
  }
`;
document.head.appendChild(style);
