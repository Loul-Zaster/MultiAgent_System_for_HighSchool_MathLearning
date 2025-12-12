// OCR Progress Modal Controller
const OCRProgress = {
    modal: null,
    progressBar: null,
    percentage: null,
    fileInfo: null,
    timeRemaining: null,
    currentAction: null,
    startTime: null,
    currentStep: 'upload',

    init() {
        this.modal = document.getElementById('ocrProgressModal');
        this.progressBar = document.getElementById('ocrProgressBar');
        this.percentage = document.getElementById('ocrProgressPercentage');
        this.fileInfo = document.getElementById('ocrFileInfo');
        this.timeRemaining = document.getElementById('ocrTimeRemaining');
        this.currentAction = document.getElementById('ocrCurrentAction');
    },

    show(fileName, fileSize) {
        if (!this.modal) this.init();

        // Reset state
        this.startTime = Date.now();
        this.currentStep = 'upload';
        this.setProgress(0);

        // Set file info
        const sizeMB = (fileSize / (1024 * 1024)).toFixed(2);
        this.fileInfo.textContent = `${fileName} • ${sizeMB} MB`;

        // Show modal
        this.modal.classList.remove('hidden');

        // Start upload phase
        this.setStep('upload', 'Uploading file...', 0);
    },

    hide() {
        if (this.modal) {
            this.modal.classList.add('hidden');
        }
    },

    setProgress(percent) {
        if (this.progressBar) {
            this.progressBar.style.width = `${percent}%`;
        }
        if (this.percentage) {
            this.percentage.textContent = `${Math.round(percent)}%`;
        }

        // Update estimated time
        if (this.startTime && percent > 0 && percent < 100) {
            const elapsed = (Date.now() - this.startTime) / 1000;
            const total = (elapsed / percent) * 100;
            const remaining = Math.max(0, total - elapsed);

            if (this.timeRemaining) {
                this.timeRemaining.textContent = `Estimated: ~${Math.ceil(remaining)}s`;
            }
        }
    },

    setStep(step, action, progress) {
        this.currentStep = step;

        // Update action text
        if (this.currentAction) {
            this.currentAction.textContent = action;
        }

        // Update step indicators
        const steps = document.querySelectorAll('.step');
        steps.forEach(stepEl => {
            const stepName = stepEl.dataset.step;
            stepEl.classList.remove('active', 'completed');

            if (stepName === step) {
                stepEl.classList.add('active');
            } else if (this.isStepBefore(stepName, step)) {
                stepEl.classList.add('completed');
            }
        });

        // Update progress
        this.setProgress(progress);
    },

    isStepBefore(step1, step2) {
        const order = ['upload', 'processing', 'extracting', 'complete'];
        return order.indexOf(step1) < order.indexOf(step2);
    },

    // Convenience methods for each step
    startUpload() {
        this.setStep('upload', 'Uploading file to server...', 10);
    },

    startProcessing() {
        this.setStep('processing', 'Processing OCR with AI...', 30);
    },

    updateProcessing(percent) {
        // Progress from 30% to 75%
        const scaledPercent = 30 + (percent * 0.45);
        this.setStep('processing', 'Processing OCR with AI...', scaledPercent);
    },

    startExtracting() {
        this.setStep('extracting', 'Extracting text content...', 80);
    },

    complete() {
        this.setStep('complete', 'OCR completed successfully!', 100);

        // Auto-hide after 1.5 seconds
        setTimeout(() => {
            this.hide();
        }, 1500);
    },

    error(message) {
        if (this.currentAction) {
            this.currentAction.textContent = `Error: ${message}`;
            this.currentAction.style.color = '#ef4444';
        }

        // Hide after 3 seconds
        setTimeout(() => {
            this.hide();
        }, 3000);
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    OCRProgress.init();
});
