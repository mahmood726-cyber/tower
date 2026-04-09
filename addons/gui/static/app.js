// Tower GUI - Frontend JavaScript

// Toast notifications
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// API helpers
async function apiCall(url, method = 'GET', body = null) {
    try {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };

        if (body) {
            options.body = JSON.stringify(body);
        }

        const response = await fetch(url, options);
        const data = await response.json();

        return data;
    } catch (error) {
        console.error('API Error:', error);
        return { success: false, error: error.message };
    }
}

// Navigation
function viewCard(cardId) {
    window.location.href = `/card/${cardId}`;
}

// Actions
async function runValidate() {
    showToast('Running validation...', 'info');

    const result = await apiCall('/api/actions/validate', 'POST');

    if (result.success) {
        showToast('Validation completed successfully', 'success');
    } else {
        showToast(`Validation failed: ${result.error || 'Unknown error'}`, 'error');
    }
}

async function runGatecheck(cardId) {
    showToast(`Running gatecheck for ${cardId}...`, 'info');

    const result = await apiCall(`/api/actions/gatecheck/${cardId}`, 'POST');

    if (result.success) {
        showToast(`Gatecheck passed for ${cardId}`, 'success');
        // Reload to show updated state
        setTimeout(() => window.location.reload(), 1000);
    } else {
        showToast(`Gatecheck failed: ${result.error || result.stderr || 'Unknown error'}`, 'error');
    }
}

async function runDashboard() {
    showToast('Regenerating dashboard...', 'info');

    const result = await apiCall('/api/actions/dashboard', 'POST');

    if (result.success) {
        showToast('Dashboard regenerated', 'success');
    } else {
        showToast(`Dashboard generation failed: ${result.error || 'Unknown error'}`, 'error');
    }
}

async function activateFreeze() {
    const reason = prompt('Enter freeze reason:');
    if (!reason) return;

    showToast('Activating merge freeze...', 'info');

    const result = await apiCall('/api/actions/freeze', 'POST', { reason });

    if (result.success) {
        showToast('Merge freeze activated', 'success');
        setTimeout(() => window.location.reload(), 1000);
    } else {
        showToast(`Failed to activate freeze: ${result.error || 'Unknown error'}`, 'error');
    }
}

async function unfreeze() {
    if (!confirm('Are you sure you want to clear the merge freeze?')) return;

    showToast('Clearing merge freeze...', 'info');

    const result = await apiCall('/api/actions/unfreeze', 'POST');

    if (result.success) {
        showToast('Merge freeze cleared', 'success');
        setTimeout(() => window.location.reload(), 1000);
    } else {
        showToast(`Failed to clear freeze: ${result.error || 'Unknown error'}`, 'error');
    }
}

// Auto-refresh (every 30 seconds on main page)
if (window.location.pathname === '/') {
    setInterval(() => {
        // Silently check for updates
        fetch('/api/status')
            .then(res => res.json())
            .then(data => {
                // Could update UI here without full reload
                console.log('Status check:', data);
            })
            .catch(err => console.error('Auto-refresh failed:', err));
    }, 30000);
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Escape to go back
    if (e.key === 'Escape' && window.location.pathname !== '/') {
        window.location.href = '/';
    }

    // R to refresh
    if (e.key === 'r' && !e.ctrlKey && !e.metaKey && document.activeElement.tagName !== 'INPUT') {
        window.location.reload();
    }
});

// Page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('Tower GUI loaded');
});
