/**
 * Beacon - State Grants Management Solution
 * Main JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {

    // Auto-dismiss alerts after 5 seconds
    document.querySelectorAll('.alert-dismissible').forEach(function(alert) {
        setTimeout(function() {
            var bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }, 5000);
    });

    // Confirm destructive actions
    document.querySelectorAll('[data-confirm]').forEach(function(element) {
        element.addEventListener('click', function(e) {
            if (!confirm(this.dataset.confirm)) {
                e.preventDefault();
            }
        });
    });

    // Enable tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(el) {
        return new bootstrap.Tooltip(el);
    });

    // Auto-save drafts (for application forms)
    var autoSaveForms = document.querySelectorAll('[data-autosave]');
    autoSaveForms.forEach(function(form) {
        var saveInterval = parseInt(form.dataset.autosave) || 60000; // default 60s
        setInterval(function() {
            var formData = new FormData(form);
            formData.append('autosave', 'true');
            fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            }).then(function(response) {
                if (response.ok) {
                    showToast('Draft saved', 'success');
                }
            }).catch(function() {
                // Silent fail for autosave
            });
        }, saveInterval);
    });

    // File upload preview
    document.querySelectorAll('.custom-file-input').forEach(function(input) {
        input.addEventListener('change', function() {
            var fileName = this.files[0] ? this.files[0].name : 'Choose file';
            var label = this.nextElementSibling;
            if (label) label.textContent = fileName;
        });
    });

    // Currency formatting
    document.querySelectorAll('.currency-input').forEach(function(input) {
        input.addEventListener('blur', function() {
            var value = parseFloat(this.value.replace(/[^0-9.]/g, ''));
            if (!isNaN(value)) {
                this.value = value.toFixed(2);
            }
        });
    });

    // Table row click navigation
    document.querySelectorAll('.table-clickable tbody tr[data-href]').forEach(function(row) {
        row.style.cursor = 'pointer';
        row.addEventListener('click', function() {
            window.location.href = this.dataset.href;
        });
    });

});

// Toast notification helper
function showToast(message, type) {
    type = type || 'info';
    var toast = document.createElement('div');
    toast.className = 'position-fixed bottom-0 end-0 p-3';
    toast.style.zIndex = '1080';
    toast.innerHTML =
        '<div class="toast show align-items-center text-white bg-' + type + ' border-0" role="alert">' +
        '  <div class="d-flex">' +
        '    <div class="toast-body">' + message + '</div>' +
        '    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>' +
        '  </div>' +
        '</div>';
    document.body.appendChild(toast);
    setTimeout(function() { toast.remove(); }, 3000);
}

// Format currency values (locale-aware)
function formatCurrency(amount) {
    var lang = document.documentElement.lang || 'en';
    var locale = lang === 'es' ? 'es-US' : 'en-US';
    return new Intl.NumberFormat(locale, {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

// ---------------------------------------------------------------------------
// Loading spinner helpers
// ---------------------------------------------------------------------------

/**
 * Show a spinner inside a button and disable it while an async action runs.
 *
 * Usage (markup):
 *   <button class="btn btn-primary" data-loading-text="Saving...">Save</button>
 *
 * Usage (JS):
 *   var restore = btnLoading(button);
 *   await doWork();
 *   restore();
 */
function btnLoading(btn, text) {
    var original = btn.innerHTML;
    var loadingText = text || btn.dataset.loadingText || 'Loading...';
    btn.disabled = true;
    btn.innerHTML =
        '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>' +
        loadingText;
    return function restore() {
        btn.disabled = false;
        btn.innerHTML = original;
    };
}

// Auto-apply loading state to forms with [data-loading] attribute
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('form[data-loading]').forEach(function(form) {
        form.addEventListener('submit', function() {
            var btn = form.querySelector('[type="submit"]');
            if (btn) btnLoading(btn);
        });
    });

    // Also disable all submit buttons once their form submits (prevent double-click)
    document.querySelectorAll('form').forEach(function(form) {
        form.addEventListener('submit', function() {
            // Slight delay so the form actually submits before disabling
            setTimeout(function() {
                form.querySelectorAll('[type="submit"]').forEach(function(b) {
                    b.disabled = true;
                });
            }, 50);
        });
    });
});

// ---------------------------------------------------------------------------
// Bootstrap 5 client-side form validation
// ---------------------------------------------------------------------------
// Works with forms that have `novalidate` attribute.  Adds the `was-validated`
// Bootstrap class on submit so native constraint messages appear styled.
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('form[novalidate]').forEach(function(form) {
        form.addEventListener('submit', function(e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });
});
