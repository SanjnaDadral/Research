/**
 * Enhanced Analysis Form Handler
 * Manages: Upload, Processing, Loading States, Error Handling, Real-time Feedback
 */

class AnalysisHandler {
  constructor() {
    this.isProcessing = false;
    this.currentFile = null;
    this.init();
  }

  init() {
    // Get form elements
    this.methodTabs = document.querySelectorAll(".method-tab");
    this.methodContents = document.querySelectorAll("[data-method]");
    this.submitBtn = document.getElementById("submitBtn");
    this.pdfInput = document.getElementById("pdfFile");
    this.textInput = document.getElementById("textContent");
    this.urlInput = document.getElementById("urlInput");
    this.form = document.getElementById("analyzeForm");
    this.fourBoxesContainer = document.getElementById("fourBoxesAnimation");

    if (!this.form) return;

    // Event listeners for method tabs - use onclick instead of click to avoid issues
    this.methodTabs.forEach((tab) => {
      tab.addEventListener("click", (e) => {
        const method = tab.dataset.method;
        if (method) this.switchMethodByName(method);
      });
    });

    if (this.pdfInput) {
      this.pdfInput.addEventListener("change", (e) => this.handleFileSelect(e));
    }

    if (this.form) {
      this.form.addEventListener("submit", (e) => this.handleSubmit(e));
    }

    // Drag and drop for PDF
    if (this.pdfInput) {
      const dropZone =
        document.querySelector(".file-upload-area") ||
        document.getElementById("uploadZone");
      if (dropZone) {
        dropZone.addEventListener("dragover", (e) => this.handleDragOver(e));
        dropZone.addEventListener("dragleave", (e) => this.handleDragLeave(e));
        dropZone.addEventListener("drop", (e) => this.handleFileDrop(e));
      }
    }
  }

  switchMethodByName(method) {
    // Remove active class from all tabs
    this.methodTabs.forEach((t) => t.classList.remove("active"));

    // Add active to matching tab
    const matchingTab = document.querySelector(
      `.method-tab[data-method="${method}"]`,
    );
    if (matchingTab) matchingTab.classList.add("active");

    // Hide all contents
    this.methodContents.forEach((content) => (content.style.display = "none"));

    // Show selected content
    const content = document.querySelector(`[data-method="${method}"]`);
    if (content) {
      content.style.display = "block";
      content.style.animation = "fadeIn 0.3s ease-in";
    }

    // Update hidden input
    const inputTypeEl = document.getElementById("inputType");
    if (inputTypeEl) inputTypeEl.value = method;
  }

  switchMethod(tab) {
    // Remove active class from all tabs
    this.methodTabs.forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");

    // Hide all contents
    this.methodContents.forEach((content) => (content.style.display = "none"));

    // Show selected content
    const method = tab.dataset.method;
    const content = document.querySelector(`[data-method="${method}"]`);
    if (content) {
      content.style.display = "block";
      // Add animation
      content.style.animation = "fadeIn 0.3s ease-in";
    }

    // Update hidden input
    const inputTypeEl = document.getElementById("inputType");
    if (inputTypeEl) inputTypeEl.value = method;
  }

  handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    this.currentFile = file;
    this.validateFile(file);
  }

  handleFileFromInput() {
    const pdfInput = document.getElementById("pdfFile");
    if (pdfInput && pdfInput.files[0]) {
      this.currentFile = pdfInput.files[0];
      this.validateFile(this.currentFile);
    }
  }

  validateFile(file) {
    const maxSize = 45 * 1024 * 1024; // 45MB
    const errors = [];

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      errors.push("⚠️ Only PDF files are supported");
    }

    if (file.size > maxSize) {
      errors.push(`⚠️ File size exceeds ${maxSize / (1024 * 1024)}MB limit`);
    }

    if (file.size < 1000) {
      errors.push("⚠️ File appears to be empty");
    }

    if (errors.length > 0) {
      this.showError(errors.join("\n"));
      this.pdfInput.value = "";
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
      this.handleFileSelect({ target: { files: files } });
    }
  }

  async handleSubmit(event) {
    event.preventDefault();

    if (this.isProcessing) {
      this.showError("Analysis already in progress. Please wait.");
      return;
    }

    // Get selected method
    const activeTab = document.querySelector(".method-tab.active");
    const inputType = activeTab?.dataset.method;

    if (!inputType) {
      this.showError("Please select an input method");
      return;
    }

    // Validate input
    if (!this.validateInput(inputType)) {
      return;
    }

    // Prepare form data
    const formData = new FormData();
    formData.append("input_type", inputType);

    if (inputType === "pdf") {
      if (!this.currentFile) {
        this.showError("Please select a PDF file");
        return;
      }
      formData.append("pdf_file", this.currentFile);
    } else if (inputType === "text") {
      const text = this.textInput.value.trim();
      if (!text) {
        this.showError("Please enter text content");
        return;
      }
      formData.append("text_content", text);
    } else if (inputType === "url") {
      const url = this.urlInput.value.trim();
      if (!url) {
        this.showError("Please enter a URL");
        return;
      }
      formData.append("url_input", url);
    }

    // Submit
    await this.submitAnalysis(formData);
  }

  validateInput(inputType) {
    if (inputType === "pdf") {
      if (!this.currentFile) {
        this.showError("❌ No PDF file selected");
        return false;
      }
    } else if (inputType === "text") {
      const text = this.textInput.value.trim();
      if (text.length < 50) {
        this.showError("❌ Text must be at least 50 characters");
        return false;
      }
    } else if (inputType === "url") {
      const url = this.urlInput.value.trim();
      if (!url.startsWith("http")) {
        this.showError("❌ Please enter a valid URL (starting with http)");
        return false;
      }
    }
    return true;
  }

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
        // 🔥 IMPORTANT: Remove CSRF header when using FormData + file upload
        // Django will still accept it because we have @csrf_exempt
      });

      let data;
      try {
        data = await response.json();
      } catch (e) {
        clearInterval(simulationInterval);
        this.showError("Server returned invalid response");
        return;
      }

      clearInterval(simulationInterval);

      if (!response.ok || !data.success) {
        this.showError(data.error || "Analysis failed. Please try again.");
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
        `Network error: ${error.message || "Please check your connection"}`,
      );
    } finally {
      this.isProcessing = false;
      this.enableForm();
    }
  }
  // async submitAnalysis(formData) {
  //   this.isProcessing = true;
  //   this.disableForm();
  //   this.showFourBoxesAnimation();

  //   let currentStep = 1;
  //   this.updateFourBoxes(currentStep);

  //   const simulationInterval = setInterval(() => {
  //     if (currentStep < 3) {
  //       currentStep++;
  //       this.updateFourBoxes(currentStep);
  //     } else {
  //       clearInterval(simulationInterval);
  //     }
  //   }, 4500);

  //   try {
  //     const response = await fetch("/analyze/", {
  //       method: "POST",
  //       body: formData,
  //       credentials: "same-origin",
  //       headers: {
  //         "X-CSRFToken": this.getCsrfToken(),
  //         "X-Requested-With": "XMLHttpRequest",
  //       },
  //     });

  //     let data;

  //     try {
  //       data = await response.json();
  //     } catch (e) {
  //       clearInterval(simulationInterval);
  //       this.showError("Server returned invalid response");
  //       return;
  //     }

  //     clearInterval(simulationInterval);

  //     if (!response.ok || !data.success) {
  //       this.showError(data.error || "Analysis failed");
  //       return;
  //     }

  //     // complete animation
  //     this.updateFourBoxes(3);
  //     this.updateFourBoxes(4);

  //     this.showSuccess(data);

  //     setTimeout(() => {
  //       window.location.href = data.redirect_url;
  //     }, 1000);

  //   } catch (error) {
  //     clearInterval(simulationInterval);
  //     console.error("Analysis error:", error);
  //     this.showError(`Network error: ${error.message}`);
  //   } finally {
  //     this.isProcessing = false;
  //     this.enableForm();
  //   }
  // }
  // async submitAnalysis(formData) {
  //   this.isProcessing = true;
  //   this.disableForm();
  //   this.showFourBoxesAnimation();

  //   // Start simulated progress to prevent "stuck" feeling
  //   let currentStep = 1;
  //   this.updateFourBoxes(currentStep);

  //   // Auto-advance simulation
  //   const simulationInterval = setInterval(() => {
  //     if (currentStep < 3) {
  //       currentStep++;
  //       this.updateFourBoxes(currentStep);
  //     } else {
  //       clearInterval(simulationInterval);
  //     }
  //   }, 4500); // Advance every 4.5 seconds

  //   // try {
  //   //   const response = await fetch("/analyze/", {
  //   //     method: "POST",
  //   //     body: formData,
  //   //     headers: {
  //   //       "X-CSRFToken": this.getCsrfToken(),
  //   //       "X-Requested-With": "XMLHttpRequest",
  //   //     },
  //   //   });

  //   //   const data = await response.json();
  //   //   clearInterval(simulationInterval); // Stop simulation once we have real data

  //   //   if (!response.ok || !data.success) {
  //   //     this.showError(data.error || "Analysis failed");
  //   //     return;
  //   //   }

  //     // Fill to complete immediately on success
  //     this.updateFourBoxes(3);
  //     this.updateFourBoxes(4);

  //     // Show success
  //     this.showSuccess(data);

  //     // Redirect
  //     setTimeout(() => {
  //       window.location.href = data.redirect_url;
  //     }, 1000);
  //   } catch (error) {
  //     console.error("Analysis error:", error);
  //     this.showError(`Network error: ${error.message}`);
  //   } finally {
  //     this.isProcessing = false;
  //     this.enableForm();
  //   }
  // }

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

  showFourBoxesAnimation() {
    if (this.fourBoxesContainer) {
      this.fourBoxesContainer.style.display = "block";
    }
  }

  updateProgress(message, percent) {
    // Legacy function - kept for compatibility
  }

  showProgress() {
    // Legacy function - replaced by showFourBoxesAnimation
  }

  showError(message, details = null, isDuplicate = false) {
    const errorDiv =
      document.getElementById("errorMessage") || this.createErrorDiv();
    errorDiv.innerHTML = `
            <i class="fas fa-exclamation-circle"></i>
            <span>${message}</span>
        `;

    if (isDuplicate) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-sm btn-primary ms-3";
      btn.textContent = "📄 View Analysis";
      btn.onclick = () => {
        // Find duplicate ID and redirect
      };
      errorDiv.appendChild(btn);
    }

    errorDiv.style.display = "block";
    errorDiv.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  showSuccess(data) {
    // Hide error message first
    const errorDiv = document.getElementById("errorMessage");
    if (errorDiv) {
      errorDiv.style.display = "none";
    }

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
            align-items: center;
            gap: 1rem;
        `;
    this.form.parentNode.insertBefore(div, this.form);
    return div;
  }

  disableForm() {
    if (this.form) {
      this.form.querySelectorAll("input, textarea, button").forEach((el) => {
        if (el !== this.submitBtn) {
          el.disabled = true;
        }
      });
    }
    if (this.submitBtn) {
      this.submitBtn.disabled = true;
      this.submitBtn.innerHTML =
        '<i class="fas fa-spinner fa-spin me-2"></i>Analyzing...';
    }
  }

  enableForm() {
    if (this.form) {
      this.form.querySelectorAll("input, textarea, button").forEach((el) => {
        el.disabled = false;
      });
    }
    if (this.submitBtn) {
      this.submitBtn.disabled = false;
      this.submitBtn.innerHTML =
        '<i class="fas fa-magic me-2"></i>Analyze Paper';
    }
  }

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

// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  new AnalysisHandler();
});

// Add fade-in animation
const style = document.createElement("style");
style.textContent = `
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
`;
document.head.appendChild(style);
