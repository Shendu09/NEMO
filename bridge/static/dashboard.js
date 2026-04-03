/**
 * NEMO-OS Dashboard Frontend
 * Real-time monitoring and action approval interface
 */

let auditLogChart = null;
let allAuditEntries = [];

// Auto-refresh interval (2 seconds)
const REFRESH_INTERVAL = 2000;

/**
 * Initialize dashboard on page load
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('[Dashboard] Initializing...');
    
    // Set up event listeners
    document.getElementById('refresh-btn').addEventListener('click', () => {
        refreshAuditLog();
        refreshStats();
    });

    document.getElementById('risk-filter').addEventListener('change', filterAuditLog);
    document.getElementById('audit-search').addEventListener('input', filterAuditLog);

    // Initial load
    refreshAuditLog();
    refreshStats();

    // Auto-refresh every 2 seconds
    setInterval(() => {
        refreshAuditLog();
        refreshStats();
    }, REFRESH_INTERVAL);

    console.log('[Dashboard] Ready');
});

/**
 * Fetch and display audit log
 */
async function refreshAuditLog() {
    try {
        const riskFilter = document.getElementById('risk-filter').value;
        const url = `/api/audit-log?limit=100${riskFilter ? `&risk=${riskFilter}` : ''}`;
        
        const response = await fetch(url);
        const data = await response.json();

        if (!response.ok) {
            displayError('Failed to fetch audit log', 'audit-log');
            return;
        }

        allAuditEntries = data.entries || [];
        displayAuditLog(allAuditEntries);
        updateStatusIndicator('online');

    } catch (error) {
        console.error('[Dashboard] Audit log fetch error:', error);
        displayError(`Error: ${error.message}`, 'audit-log');
        updateStatusIndicator('offline');
    }
}

/**
 * Display audit log entries in the UI
 */
function displayAuditLog(entries) {
    const container = document.getElementById('audit-log');

    if (!entries || entries.length === 0) {
        container.innerHTML = '<div class="alert alert-info">No audit log entries yet</div>';
        return;
    }

    let html = '';
    entries.forEach(entry => {
        const timestamp = new Date(entry.timestamp).toLocaleString();
        const riskLevel = entry.risk_level || 'UNKNOWN';
        const riskBadgeColor = {
            'LOW': 'success',
            'MEDIUM': 'warning',
            'HIGH': 'danger'
        }[riskLevel] || 'secondary';

        html += `
            <div class="audit-entry ${riskLevel}">
                <div class="audit-entry-header">
                    <span class="audit-entry-action">${escapeHtml(entry.action)}</span>
                    <span class="audit-entry-risk badge bg-${riskBadgeColor}">${riskLevel}</span>
                </div>
                <div class="audit-entry-details">
                    <span class="audit-entry-time">${timestamp}</span>
                    <span class="ms-2">User: <span class="audit-entry-user">${escapeHtml(entry.user_id)}</span></span>
                    <span class="ms-2">Target: <code>${escapeHtml(entry.target)}</code></span>
                    <span class="ms-2 badge ${entry.allowed ? 'bg-success' : 'bg-danger'}">
                        ${entry.allowed ? 'Allowed' : 'Denied'}
                    </span>
                </div>
                <div class="mt-2 text-muted small">
                    <em>${escapeHtml(entry.reason)}</em>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

/**
 * Filter audit log by search/risk level
 */
function filterAuditLog() {
    const searchText = document.getElementById('audit-search').value.toLowerCase();
    const riskFilter = document.getElementById('risk-filter').value;

    let filtered = allAuditEntries;

    if (searchText) {
        filtered = filtered.filter(entry =>
            entry.action.toLowerCase().includes(searchText) ||
            entry.user_id.toLowerCase().includes(searchText) ||
            entry.target.toLowerCase().includes(searchText) ||
            entry.reason.toLowerCase().includes(searchText)
        );
    }

    if (riskFilter) {
        filtered = filtered.filter(entry => entry.risk_level === riskFilter);
    }

    displayAuditLog(filtered);
}

/**
 * Fetch and display statistics
 */
async function refreshStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();

        if (!response.ok) {
            console.error('[Dashboard] Stats fetch failed:', stats);
            return;
        }

        // Update stats cards
        document.getElementById('stat-total').textContent = stats.total_actions || 0;
        document.getElementById('stat-success').textContent = `${stats.success_rate || 0}%`;
        document.getElementById('stat-low').textContent = `LOW: ${stats.by_risk?.LOW || 0}`;
        document.getElementById('stat-medium').textContent = `MED: ${stats.by_risk?.MEDIUM || 0}`;
        document.getElementById('stat-high').textContent = `HIGH: ${stats.by_risk?.HIGH || 0}`;

        // Update charts
        updateRiskChart(stats.by_risk || {});
        updateTopActions(stats.by_action || {});

    } catch (error) {
        console.error('[Dashboard] Stats fetch error:', error);
    }
}

/**
 * Update risk level chart
 */
function updateRiskChart(byRisk) {
    const ctx = document.getElementById('risk-chart');
    
    if (!ctx) return;

    const data = {
        labels: ['LOW', 'MEDIUM', 'HIGH'],
        datasets: [{
            label: 'Actions by Risk Level',
            data: [
                byRisk.LOW || 0,
                byRisk.MEDIUM || 0,
                byRisk.HIGH || 0
            ],
            backgroundColor: [
                '#198754',  // green for LOW
                '#ffc107',  // yellow for MEDIUM
                '#dc3545'   // red for HIGH
            ],
            borderColor: [
                '#155724',
                '#e0a800',
                '#c82333'
            ],
            borderWidth: 2
        }]
    };

    if (auditLogChart) {
        auditLogChart.data = data;
        auditLogChart.update();
    } else {
        auditLogChart = new Chart(ctx, {
            type: 'doughnut',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
}

/**
 * Update top actions list
 */
function updateTopActions(byAction) {
    const container = document.getElementById('top-actions');

    if (!byAction || Object.keys(byAction).length === 0) {
        container.innerHTML = '<p class="text-muted">No actions recorded yet</p>';
        return;
    }

    // Sort by count descending
    const sorted = Object.entries(byAction)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10);

    let html = '';
    sorted.forEach(([action, count]) => {
        html += `
            <div class="action-item">
                <span><code>${escapeHtml(action)}</code></span>
                <span class="action-count">${count}</span>
            </div>
        `;
    });

    container.innerHTML = html;
}

/**
 * Update status indicator
 */
function updateStatusIndicator(status) {
    const indicator = document.getElementById('status-indicator');
    if (status === 'online') {
        indicator.className = 'badge bg-success';
        indicator.textContent = '● ONLINE';
    } else {
        indicator.className = 'badge bg-danger';
        indicator.textContent = '● OFFLINE';
    }
}

/**
 * Display error message in container
 */
function displayError(message, containerId) {
    const container = document.getElementById(containerId);
    container.innerHTML = `<div class="alert alert-danger">${escapeHtml(message)}</div>`;
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}
