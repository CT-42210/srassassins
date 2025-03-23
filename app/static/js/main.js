document.addEventListener('DOMContentLoaded', function() {
    // Obfuscation toggle for secure content
    const obfuscationToggle = document.getElementById('obfuscation-toggle');
    if (obfuscationToggle) {
        const secureSection = document.querySelector('.secure-section');
        
        // Initialize as blurred if toggle is not checked
        if (!obfuscationToggle.checked && secureSection) {
            secureSection.classList.add('blurred');
        }
        
        // Toggle blur on click
        obfuscationToggle.addEventListener('change', function() {
            if (secureSection) {
                if (this.checked) {
                    secureSection.classList.remove('blurred');
                } else {
                    secureSection.classList.add('blurred');
                }
            }
        });
    }
    
    // Admin dashboard confirmation modals
    const adminForms = document.querySelectorAll('.admin-action-form');
    adminForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const confirmCheckbox = this.querySelector('input[name="confirmation"]');
            if (confirmCheckbox && !confirmCheckbox.checked) {
                e.preventDefault();
                alert('Please confirm this action by checking the confirmation box.');
            }
        });
    });
    
    // File upload preview
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        const previewContainer = document.querySelector(`#${input.id}-preview`);
        if (previewContainer) {
            input.addEventListener('change', function() {
                previewContainer.innerHTML = '';
                
                if (this.files && this.files[0]) {
                    const file = this.files[0];
                    const fileExt = file.name.split('.').pop().toLowerCase();
                    
                    if (['jpg', 'jpeg', 'png', 'gif'].includes(fileExt)) {
                        // Image preview
                        const img = document.createElement('img');
                        img.classList.add('img-fluid', 'rounded', 'mt-2');
                        img.file = file;
                        previewContainer.appendChild(img);
                        
                        const reader = new FileReader();
                        reader.onload = (function(aImg) {
                            return function(e) {
                                aImg.src = e.target.result;
                            };
                        })(img);
                        reader.readAsDataURL(file);
                    } else if (['mp4', 'mov'].includes(fileExt)) {
                        // Video preview
                        const video = document.createElement('video');
                        video.classList.add('img-fluid', 'rounded', 'mt-2');
                        video.controls = true;
                        previewContainer.appendChild(video);
                        
                        const reader = new FileReader();
                        reader.onload = (function(aVideo) {
                            return function(e) {
                                aVideo.src = e.target.result;
                            };
                        })(video);
                        reader.readAsDataURL(file);
                    }
                    
                    // Show file info
                    const fileInfo = document.createElement('div');
                    fileInfo.classList.add('mt-2');
                    fileInfo.innerHTML = `
                        <small class="text-muted">
                            <strong>File:</strong> ${file.name}<br>
                            <strong>Size:</strong> ${(file.size / (1024 * 1024)).toFixed(2)} MB
                        </small>
                    `;
                    previewContainer.appendChild(fileInfo);
                }
            });
        }
    });
    
    // Auto-close alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const closeButton = alert.querySelector('.btn-close');
            if (closeButton) {
                closeButton.click();
            }
        }, 5000);
    });
    
    // Enable tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Admin dashboard tabs
    const adminTabs = document.querySelectorAll('.admin-tab-link');
    if (adminTabs.length > 0) {
        adminTabs.forEach(tab => {
            tab.addEventListener('click', function(e) {
                e.preventDefault();
                
                // Get the target section
                const targetId = this.getAttribute('href').substring(1);
                const targetSection = document.getElementById(targetId);
                
                // Hide all sections
                document.querySelectorAll('.admin-tab-content').forEach(section => {
                    section.classList.add('d-none');
                });
                
                // Show target section
                if (targetSection) {
                    targetSection.classList.remove('d-none');
                }
                
                // Update active tab
                document.querySelectorAll('.admin-tab-link').forEach(t => {
                    t.classList.remove('active');
                });
                this.classList.add('active');
            });
        });
        
        // Activate first tab by default
        adminTabs[0].click();
    }
});

/**
 * Applies loading state to submit buttons when forms are submitted
 * Usage: Add class "loading-form" to any form that should show loading state
 */
function initFormLoadingIndicators() {
  const loadingForms = document.querySelectorAll('.loading-form');

  loadingForms.forEach(form => {
    form.addEventListener('submit', function() {
      const submitButton = this.querySelector('button[type="submit"]');
      if (submitButton) {
        const originalText = submitButton.innerHTML;
        submitButton.disabled = true;
        submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Submitting...';
      }
    });
  });
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  initFormLoadingIndicators();
});

