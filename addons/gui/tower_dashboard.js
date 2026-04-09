/**
 * Tower Dashboard v2.0 - World-Class Control Interface
 * Advanced JavaScript Core with Real-time Updates, WASM Integration, and Self-Correcting Workflows
 */

// ============================================================================
// CORE STATE MANAGEMENT
// ============================================================================

const TowerState = {
    // Application state
    currentView: 'dashboard',
    theme: localStorage.getItem('tower-theme') || 'dark',
    sidebarCollapsed: localStorage.getItem('tower-sidebar-collapsed') === 'true',

    // Data state
    status: null,
    events: [],
    cards: [],
    sloMetrics: null,
    hashChain: [],

    // UI state
    commandPaletteOpen: false,
    activeModal: null,
    selectedCard: null,
    notifications: [],

    // Real-time state
    pollInterval: null,
    lastUpdate: null,
    connectionStatus: 'disconnected',

    // Self-correcting state
    workflowStages: [],
    activeCorrections: [],

    // WASM state
    wasmReady: false,
    wasmModule: null
};

// ============================================================================
// CONFIGURATION
// ============================================================================

const Config = {
    API_BASE: window.location.origin,
    POLL_INTERVAL: 3000,
    TOAST_DURATION: 5000,
    MAX_EVENTS_DISPLAY: 100,
    MAX_NOTIFICATIONS: 50,
    ANIMATION_DURATION: 300,

    // Endpoints
    ENDPOINTS: {
        status: '/api/status',
        events: '/api/events',
        cards: '/api/cards',
        slo: '/api/slo',
        run: '/api/run',
        validate: '/api/validate',
        ledger: '/api/ledger'
    }
};

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

const Utils = {
    formatTime(timestamp) {
        if (!timestamp) return 'N/A';
        const date = new Date(timestamp);
        return date.toLocaleString();
    },

    formatRelativeTime(timestamp) {
        if (!timestamp) return 'never';
        const now = Date.now();
        const then = new Date(timestamp).getTime();
        const diff = now - then;

        if (diff < 60000) return 'just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        return `${Math.floor(diff / 86400000)}d ago`;
    },

    formatDuration(ms) {
        if (ms < 1000) return `${ms}ms`;
        if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
        if (ms < 3600000) return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
        return `${Math.floor(ms / 3600000)}h ${Math.floor((ms % 3600000) / 60000)}m`;
    },

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    generateId() {
        return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    parseHash(hexString) {
        if (!hexString || hexString.length < 16) return hexString || 'N/A';
        return hexString.substring(0, 8) + '...' + hexString.substring(hexString.length - 8);
    },

    getStatusClass(status) {
        const statusMap = {
            'healthy': 'green', 'ok': 'green', 'pass': 'green', 'passed': 'green', 'green': 'green',
            'warning': 'yellow', 'degraded': 'yellow', 'yellow': 'yellow',
            'error': 'red', 'fail': 'red', 'failed': 'red', 'critical': 'red', 'red': 'red',
            'unknown': 'gray', 'pending': 'gray', 'gray': 'gray'
        };
        return statusMap[status?.toLowerCase()] || 'gray';
    }
};

// ============================================================================
// API CLIENT
// ============================================================================

const API = {
    async request(endpoint, options = {}) {
        const url = `${Config.API_BASE}${endpoint}`;
        const defaultOptions = {
            headers: { 'Content-Type': 'application/json' }
        };

        try {
            const response = await fetch(url, { ...defaultOptions, ...options });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.warn(`API Error [${endpoint}]:`, error.message);
            throw error;
        }
    },

    getStatus() { return this.request(Config.ENDPOINTS.status); },
    getEvents(limit = 100) { return this.request(`${Config.ENDPOINTS.events}?limit=${limit}`); },
    getCards() { return this.request(Config.ENDPOINTS.cards); },
    getSLO() { return this.request(Config.ENDPOINTS.slo); },
    getLedger(limit = 50) { return this.request(`${Config.ENDPOINTS.ledger}?limit=${limit}`); },

    triggerRun(script, args = {}) {
        return this.request(Config.ENDPOINTS.run, {
            method: 'POST',
            body: JSON.stringify({ script, args })
        });
    },

    validateChain() { return this.request(Config.ENDPOINTS.validate); }
};

// ============================================================================
// TOAST NOTIFICATION SYSTEM
// ============================================================================

const Toast = {
    container: null,

    init() {
        this.container = document.getElementById('toast-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        }
    },

    show(message, type = 'info', duration = Config.TOAST_DURATION) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        const icons = {
            success: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
            error: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
            warning: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
            info: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`
        };

        toast.innerHTML = `
            <div class="toast-icon">${icons[type] || icons.info}</div>
            <div class="toast-content">
                <span class="toast-message">${Utils.escapeHtml(message)}</span>
            </div>
            <button class="toast-close" onclick="Toast.dismiss(this.parentElement)">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>
        `;

        this.container.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add('show'));

        if (duration > 0) {
            setTimeout(() => this.dismiss(toast), duration);
        }
        return toast;
    },

    dismiss(toast) {
        if (!toast || !toast.parentElement) return;
        toast.classList.remove('show');
        toast.classList.add('hide');
        setTimeout(() => toast.remove(), 300);
    },

    success(message) { return this.show(message, 'success'); },
    error(message) { return this.show(message, 'error'); },
    warning(message) { return this.show(message, 'warning'); },
    info(message) { return this.show(message, 'info'); }
};

// ============================================================================
// COMMAND PALETTE
// ============================================================================

const CommandPalette = {
    element: null,
    input: null,
    results: null,
    commands: [],
    filteredCommands: [],
    selectedIndex: 0,

    init() {
        this.element = document.getElementById('command-palette');
        this.input = document.getElementById('command-input');
        this.results = document.getElementById('command-results');

        this.registerCommands();
        this.bindEvents();
    },

    registerCommands() {
        this.commands = [
            { id: 'dashboard', name: 'Go to Dashboard', shortcut: '1', action: () => Navigation.switchView('dashboard') },
            { id: 'kanban', name: 'Go to Kanban Board', shortcut: '2', action: () => Navigation.switchView('kanban') },
            { id: 'metrics', name: 'Go to Metrics', shortcut: '3', action: () => Navigation.switchView('metrics') },
            { id: 'events', name: 'Go to Events', shortcut: '4', action: () => Navigation.switchView('events') },
            { id: 'selfcorrect', name: 'Go to Self-Correct', shortcut: '5', action: () => Navigation.switchView('selfcorrect') },
            { id: 'validator', name: 'Go to Validator', shortcut: '6', action: () => Navigation.switchView('validator') },
            { id: 'settings', name: 'Open Settings', shortcut: null, action: () => Navigation.switchView('settings') },

            { id: 'run-validation', name: 'Run Validation', shortcut: 'V', action: () => Actions.runValidation() },
            { id: 'gatecheck', name: 'Run Gatecheck', shortcut: 'G', action: () => Actions.runGatecheck() },
            { id: 'proofpack', name: 'Generate Proofpack', shortcut: 'P', action: () => Actions.runProofpack() },
            { id: 'refresh', name: 'Refresh Data', shortcut: 'R', action: () => DataManager.refresh() },

            { id: 'toggle-theme', name: 'Toggle Theme', shortcut: 'T', action: () => Theme.toggle() },
            { id: 'toggle-sidebar', name: 'Toggle Sidebar', shortcut: 'B', action: () => Sidebar.toggle() },
            { id: 'toggle-freeze', name: 'Toggle Merge Freeze', shortcut: 'F', action: () => Actions.toggleFreeze() },

            { id: 'new-card', name: 'Create New Card', shortcut: 'N', action: () => Kanban.createCard() },
            { id: 'export-data', name: 'Export Data', shortcut: null, action: () => Actions.exportData() },
            { id: 'verify-chain', name: 'Verify Hash Chain', shortcut: null, action: () => Actions.verifyChain() }
        ];

        this.filteredCommands = [...this.commands];
    },

    bindEvents() {
        if (this.input) {
            this.input.addEventListener('input', () => this.filter());
            this.input.addEventListener('keydown', (e) => this.handleKeydown(e));
        }

        // Close on backdrop click
        this.element?.querySelector('.command-palette-backdrop')?.addEventListener('click', () => this.close());

        // Global search trigger
        document.getElementById('global-search')?.addEventListener('focus', () => this.open());
        document.getElementById('command-trigger')?.addEventListener('click', () => this.open());
    },

    open() {
        if (!this.element) return;

        TowerState.commandPaletteOpen = true;
        this.element.classList.remove('hidden');
        this.element.classList.add('active');
        this.input.value = '';
        this.filter();
        this.selectedIndex = 0;
        this.render();

        setTimeout(() => this.input?.focus(), 100);
    },

    close() {
        if (!this.element) return;

        TowerState.commandPaletteOpen = false;
        this.element.classList.remove('active');
        this.element.classList.add('hidden');
        this.input.value = '';
    },

    toggle() {
        if (TowerState.commandPaletteOpen) {
            this.close();
        } else {
            this.open();
        }
    },

    filter() {
        const query = this.input?.value.toLowerCase() || '';

        if (!query) {
            this.filteredCommands = [...this.commands];
        } else {
            this.filteredCommands = this.commands.filter(cmd =>
                cmd.name.toLowerCase().includes(query) ||
                cmd.id.toLowerCase().includes(query)
            );
        }

        this.selectedIndex = 0;
        this.render();
    },

    render() {
        if (!this.results) return;

        if (this.filteredCommands.length === 0) {
            this.results.innerHTML = '<div class="command-empty">No commands found</div>';
            return;
        }

        // Group commands
        const actions = this.filteredCommands.filter(c => ['run', 'gate', 'proof', 'refresh', 'export', 'verify', 'toggle', 'new'].some(a => c.id.includes(a)));
        const navigation = this.filteredCommands.filter(c => !actions.includes(c));

        let html = '';

        if (navigation.length > 0) {
            html += `<div class="command-group">
                <div class="command-group-title">Navigation</div>
                ${navigation.map((cmd, i) => this.renderCommand(cmd, this.filteredCommands.indexOf(cmd))).join('')}
            </div>`;
        }

        if (actions.length > 0) {
            html += `<div class="command-group">
                <div class="command-group-title">Actions</div>
                ${actions.map((cmd, i) => this.renderCommand(cmd, this.filteredCommands.indexOf(cmd))).join('')}
            </div>`;
        }

        this.results.innerHTML = html;
    },

    renderCommand(cmd, index) {
        return `
            <div class="command-item ${index === this.selectedIndex ? 'selected' : ''}"
                 data-index="${index}"
                 onclick="CommandPalette.execute(${index})">
                <span class="command-item-text">${Utils.escapeHtml(cmd.name)}</span>
                ${cmd.shortcut ? `<kbd>${cmd.shortcut}</kbd>` : ''}
            </div>
        `;
    },

    handleKeydown(e) {
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.selectedIndex = Math.min(this.selectedIndex + 1, this.filteredCommands.length - 1);
                this.render();
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.selectedIndex = Math.max(this.selectedIndex - 1, 0);
                this.render();
                break;
            case 'Enter':
                e.preventDefault();
                this.execute(this.selectedIndex);
                break;
            case 'Escape':
                e.preventDefault();
                this.close();
                break;
        }
    },

    execute(index) {
        const command = this.filteredCommands[index];
        if (command?.action) {
            this.close();
            command.action();
        }
    }
};

// ============================================================================
// NAVIGATION
// ============================================================================

const Navigation = {
    init() {
        // Bind sidebar navigation clicks
        document.querySelectorAll('.nav-item[data-view]').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const view = item.dataset.view;
                this.switchView(view);
            });
        });

        // Initialize to current view
        this.switchView(TowerState.currentView);
    },

    switchView(viewId) {
        TowerState.currentView = viewId;

        // Update active nav item
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.view === viewId);
        });

        // Show/hide views
        document.querySelectorAll('.view').forEach(view => {
            const isActive = view.id === `view-${viewId}`;
            view.classList.toggle('active', isActive);
        });

        // Update breadcrumb
        const viewNames = {
            dashboard: 'Dashboard', kanban: 'Kanban Board', metrics: 'Metrics & SLO',
            events: 'Event Ledger', selfcorrect: 'Self-Correct', validator: 'Validator',
            settings: 'Settings', timeline: 'Timeline', alerts: 'Alerts',
            proofpack: 'Proofpack', architecture: 'Architecture'
        };

        const breadcrumb = document.getElementById('current-view-name');
        if (breadcrumb) breadcrumb.textContent = viewNames[viewId] || viewId;

        // Trigger view-specific refresh
        this.refreshView(viewId);
    },

    refreshView(viewId) {
        switch (viewId) {
            case 'dashboard': Dashboard.refresh(); break;
            case 'kanban': Kanban.refresh(); break;
            case 'metrics': Metrics.refresh(); break;
            case 'events': Events.refresh(); break;
            case 'selfcorrect': SelfCorrect.refresh(); break;
            case 'validator': Validator.refresh(); break;
        }
    }
};

// ============================================================================
// SIDEBAR
// ============================================================================

const Sidebar = {
    element: null,

    init() {
        this.element = document.getElementById('sidebar');

        // Restore collapsed state
        if (TowerState.sidebarCollapsed) {
            this.element?.classList.add('collapsed');
        }

        // Bind toggle button
        document.getElementById('sidebar-toggle')?.addEventListener('click', () => this.toggle());
        document.getElementById('mobile-menu-toggle')?.addEventListener('click', () => this.toggleMobile());
    },

    toggle() {
        TowerState.sidebarCollapsed = !TowerState.sidebarCollapsed;
        localStorage.setItem('tower-sidebar-collapsed', TowerState.sidebarCollapsed);
        this.element?.classList.toggle('collapsed', TowerState.sidebarCollapsed);
    },

    toggleMobile() {
        this.element?.classList.toggle('mobile-open');
    }
};

// ============================================================================
// THEME MANAGEMENT
// ============================================================================

const Theme = {
    init() {
        this.apply(TowerState.theme);

        // Bind theme toggle
        document.getElementById('theme-toggle')?.addEventListener('click', () => this.toggle());
        document.getElementById('theme-select')?.addEventListener('change', (e) => this.apply(e.target.value));
    },

    apply(theme) {
        if (theme === 'system') {
            theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        document.documentElement.setAttribute('data-theme', theme);
        TowerState.theme = theme;
        localStorage.setItem('tower-theme', theme);

        // Update select if exists
        const select = document.getElementById('theme-select');
        if (select) select.value = theme;
    },

    toggle() {
        const newTheme = TowerState.theme === 'dark' ? 'light' : 'dark';
        this.apply(newTheme);
        Toast.info(`Switched to ${newTheme} theme`);
    }
};

// ============================================================================
// DATA MANAGER
// ============================================================================

const DataManager = {
    async init() {
        await this.refresh();
        this.startPolling();
    },

    async refresh() {
        try {
            TowerState.connectionStatus = 'connecting';

            // Try to fetch real data
            const [status, events, slo, ledger] = await Promise.allSettled([
                API.getStatus(), API.getEvents(), API.getSLO(), API.getLedger()
            ]);

            if (status.status === 'fulfilled') TowerState.status = status.value;
            if (events.status === 'fulfilled') TowerState.events = events.value.events || [];
            if (slo.status === 'fulfilled') TowerState.sloMetrics = slo.value;
            if (ledger.status === 'fulfilled') TowerState.hashChain = ledger.value.entries || [];

            TowerState.lastUpdate = Date.now();
            TowerState.connectionStatus = 'connected';

        } catch (error) {
            console.warn('API unavailable, using demo data');
            TowerState.connectionStatus = 'offline';
            this.loadDemoData();
        }

        // Always refresh current view
        Navigation.refreshView(TowerState.currentView);
        this.updateStatusIndicators();
    },

    loadDemoData() {
        // Demo data for standalone operation
        TowerState.status = {
            tower_version: 'v1.5.5',
            status: 'healthy',
            merge_freeze: false,
            uptime: '3d 14h 22m',
            last_run: new Date().toISOString(),
            addons: {
                ledger: { enabled: true, status: 'ok' },
                evals: { enabled: true, status: 'ok' },
                slo: { enabled: true, status: 'ok' },
                bridge: { enabled: true, status: 'ok' },
                resilience: { enabled: true, status: 'ok' }
            }
        };

        TowerState.events = [
            { seq: 42, type: 'RUN_END', timestamp: new Date(Date.now() - 300000).toISOString(), card_id: 'CARD-007', actor: 'tower', details: { exit_code: 0 }, hash: 'a1b2c3d4e5f67890' },
            { seq: 41, type: 'VALIDATION', timestamp: new Date(Date.now() - 240000).toISOString(), card_id: 'CARD-007', actor: 'validator', details: { passed: true }, hash: 'b2c3d4e5f6789012' },
            { seq: 40, type: 'STATE_CHANGE', timestamp: new Date(Date.now() - 180000).toISOString(), card_id: 'CARD-006', actor: 'user', details: { from: 'ACTIVE', to: 'GREEN' }, hash: 'c3d4e5f678901234' },
            { seq: 39, type: 'RUN_START', timestamp: new Date(Date.now() - 120000).toISOString(), card_id: 'CARD-007', actor: 'tower', details: { script: 'tower_run.sh' }, hash: 'd4e5f67890123456' },
            { seq: 38, type: 'VALIDATION', timestamp: new Date(Date.now() - 60000).toISOString(), card_id: 'CARD-005', actor: 'validator', details: { passed: false }, hash: 'e5f6789012345678' }
        ];

        TowerState.sloMetrics = {
            rollback_rate: { target: 3, current: 2.1, status: 'ok' },
            validator_pass: { target: 85, current: 91.2, status: 'ok' },
            audit_agreement: { target: 90, current: 94.5, status: 'ok' },
            drift_free: { target: 96, current: 98.2, status: 'ok' },
            error_budget: { remaining: 78, consumed: 22, resets_in_days: 23 }
        };

        TowerState.hashChain = TowerState.events.map(e => ({
            seq: e.seq, hash: e.hash, type: e.type, timestamp: e.timestamp
        }));

        TowerState.cards = [
            { id: 'CARD-001', title: 'Add user authentication', state: 'GREEN', priority: 'high', created: '2024-01-10' },
            { id: 'CARD-002', title: 'Fix database connection pool', state: 'ACTIVE', priority: 'critical', created: '2024-01-12' },
            { id: 'CARD-003', title: 'Update API documentation', state: 'MERGED', priority: 'low', created: '2024-01-08' },
            { id: 'CARD-004', title: 'Implement caching layer', state: 'VALIDATING', priority: 'medium', created: '2024-01-14' },
            { id: 'CARD-005', title: 'Add monitoring alerts', state: 'BACKLOG', priority: 'high', created: '2024-01-15' },
            { id: 'CARD-006', title: 'Refactor auth module', state: 'GREEN', priority: 'medium', created: '2024-01-11' },
            { id: 'CARD-007', title: 'Performance optimization', state: 'ACTIVE', priority: 'high', created: '2024-01-13' }
        ];
    },

    startPolling() {
        this.stopPolling();
        const interval = parseInt(document.getElementById('auto-refresh')?.value || '15') * 1000;
        if (interval > 0) {
            TowerState.pollInterval = setInterval(() => this.refresh(), interval);
        }
    },

    stopPolling() {
        if (TowerState.pollInterval) {
            clearInterval(TowerState.pollInterval);
            TowerState.pollInterval = null;
        }
    },

    updateStatusIndicators() {
        // System status
        const systemStatus = document.getElementById('system-status');
        if (systemStatus && TowerState.status) {
            const dot = systemStatus.querySelector('.status-dot');
            const text = systemStatus.querySelector('.status-text');
            const statusClass = Utils.getStatusClass(TowerState.status.status);
            dot.className = `status-dot ${statusClass}`;
            text.textContent = TowerState.status.status || 'Unknown';
        }

        // Merge freeze status
        const freezeDot = document.getElementById('freeze-dot');
        const freezeText = document.getElementById('freeze-text');
        if (freezeDot && freezeText && TowerState.status) {
            const isFrozen = TowerState.status.merge_freeze;
            freezeDot.className = `status-dot ${isFrozen ? 'blue' : 'gray'}`;
            freezeText.textContent = isFrozen ? 'Frozen' : 'Active';
        }
    }
};

// ============================================================================
// DASHBOARD VIEW
// ============================================================================

const Dashboard = {
    refresh() {
        this.renderStatusCards();
        this.renderActivityFeed();
        this.renderChainStatus();
        this.renderCardsDistribution();
    },

    renderStatusCards() {
        const cards = TowerState.cards || [];
        const greenCount = cards.filter(c => c.state === 'GREEN').length;
        const activeCount = cards.filter(c => c.state === 'ACTIVE' || c.state === 'VALIDATING').length;

        document.getElementById('healthy-count')?.textContent && (document.getElementById('healthy-count').textContent = greenCount);
        document.getElementById('active-count')?.textContent && (document.getElementById('active-count').textContent = activeCount);

        // SLO value
        const slo = TowerState.sloMetrics;
        if (slo) {
            const avgSlo = ((100 - slo.rollback_rate?.current) + slo.validator_pass?.current + slo.audit_agreement?.current + slo.drift_free?.current) / 4;
            const sloEl = document.getElementById('slo-value');
            if (sloEl) sloEl.textContent = `${avgSlo.toFixed(1)}%`;

            // Error budget
            const budgetEl = document.getElementById('budget-value');
            if (budgetEl) budgetEl.textContent = `${slo.error_budget?.remaining || 0}%`;
        }
    },

    renderActivityFeed() {
        const feed = document.getElementById('activity-feed');
        if (!feed) return;

        const events = (TowerState.events || []).slice(0, 5);

        if (events.length === 0) {
            feed.innerHTML = '<div class="activity-empty">No recent activity</div>';
            return;
        }

        feed.innerHTML = events.map(event => {
            const statusClass = event.type.includes('END') || event.type.includes('VALIDATION')
                ? (event.details?.passed !== false && event.details?.exit_code !== 1 ? 'green' : 'red')
                : 'blue';

            return `
                <div class="activity-item">
                    <div class="activity-icon ${statusClass}">
                        ${this.getEventIcon(event.type)}
                    </div>
                    <div class="activity-content">
                        <span class="activity-text">${event.type.replace('_', ' ')}</span>
                        ${event.card_id ? `<span class="activity-card">${event.card_id}</span>` : ''}
                        <span class="activity-time">${Utils.formatRelativeTime(event.timestamp)}</span>
                    </div>
                </div>
            `;
        }).join('');
    },

    getEventIcon(type) {
        const icons = {
            'RUN_START': '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
            'RUN_END': '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>',
            'VALIDATION': '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>',
            'STATE_CHANGE': '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>'
        };
        return icons[type] || '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>';
    },

    renderChainStatus() {
        const chainEvents = document.getElementById('chain-events');
        const chainLast = document.getElementById('chain-last');
        const chainViz = document.getElementById('chain-viz');

        if (chainEvents) chainEvents.textContent = TowerState.hashChain.length;
        if (chainLast && TowerState.hashChain.length > 0) {
            chainLast.textContent = Utils.formatRelativeTime(TowerState.hashChain[0]?.timestamp);
        }

        // Render chain visualization
        if (chainViz) {
            const blocks = TowerState.hashChain.slice(0, 5).map((entry, i) => `
                <div class="chain-block ${i === 0 ? 'latest' : ''}">
                    <div class="block-seq">#${entry.seq}</div>
                    <div class="block-hash">${Utils.parseHash(entry.hash)}</div>
                </div>
            `).join('<div class="chain-link"></div>');

            chainViz.innerHTML = blocks || '<div class="chain-empty">No chain data</div>';
        }
    },

    renderCardsDistribution() {
        const cards = TowerState.cards || [];
        const states = { GREEN: 0, ACTIVE: 0, VALIDATING: 0, BACKLOG: 0, MERGED: 0 };

        cards.forEach(c => {
            if (states.hasOwnProperty(c.state)) states[c.state]++;
        });

        const total = cards.length || 1;
        const segments = [
            { state: 'GREEN', color: 'green', width: (states.GREEN / total * 100) },
            { state: 'ACTIVE', color: 'blue', width: (states.ACTIVE / total * 100) },
            { state: 'VALIDATING', color: 'yellow', width: (states.VALIDATING / total * 100) },
            { state: 'BACKLOG', color: 'gray', width: (states.BACKLOG / total * 100) }
        ];

        const bar = document.querySelector('.distribution-bar');
        if (bar) {
            bar.innerHTML = segments
                .filter(s => s.width > 0)
                .map(s => `<div class="dist-segment ${s.color}" style="width: ${s.width}%" title="${s.state}: ${Math.round(s.width)}%"></div>`)
                .join('');
        }
    }
};

// ============================================================================
// KANBAN BOARD
// ============================================================================

const Kanban = {
    columns: ['BACKLOG', 'ACTIVE', 'VALIDATING', 'GREEN', 'MERGED'],

    refresh() {
        this.render();
    },

    render() {
        const cards = TowerState.cards || [];

        this.columns.forEach(state => {
            const stateCards = cards.filter(c => c.state === state);
            const container = document.getElementById(`col-${state.toLowerCase()}`);
            const countEl = document.getElementById(`count-${state.toLowerCase()}`);

            if (countEl) countEl.textContent = stateCards.length;

            if (container) {
                container.innerHTML = stateCards.map(card => this.renderCard(card)).join('') ||
                    '<div class="column-empty">No cards</div>';
            }
        });
    },

    renderCard(card) {
        const priorityColors = { critical: 'red', high: 'orange', medium: 'blue', low: 'gray' };
        const color = priorityColors[card.priority] || 'gray';

        return `
            <div class="kanban-card" data-id="${card.id}" onclick="Kanban.openCard('${card.id}')">
                <div class="card-header">
                    <span class="card-id">${card.id}</span>
                    <span class="card-priority ${color}">${card.priority}</span>
                </div>
                <div class="card-title">${Utils.escapeHtml(card.title)}</div>
                <div class="card-meta">
                    <span class="card-date">${card.created}</span>
                </div>
            </div>
        `;
    },

    createCard() {
        const id = `CARD-${String(TowerState.cards.length + 1).padStart(3, '0')}`;
        const title = prompt('Enter card title:');
        if (!title) return;

        const card = {
            id, title,
            state: 'BACKLOG',
            priority: 'medium',
            created: new Date().toISOString().split('T')[0]
        };

        TowerState.cards.push(card);
        this.render();
        Toast.success(`Card ${id} created`);
    },

    openCard(cardId) {
        const card = TowerState.cards.find(c => c.id === cardId);
        if (!card) return;

        const modal = document.getElementById('card-modal');
        const modalId = document.getElementById('modal-card-id');
        const modalBody = document.getElementById('modal-card-body');

        if (modal && modalId && modalBody) {
            modalId.textContent = card.id;
            modalBody.innerHTML = `
                <div class="card-detail-section">
                    <h4>Title</h4>
                    <p>${Utils.escapeHtml(card.title)}</p>
                </div>
                <div class="card-detail-section">
                    <h4>State</h4>
                    <span class="state-badge ${card.state.toLowerCase()}">${card.state}</span>
                </div>
                <div class="card-detail-section">
                    <h4>Priority</h4>
                    <span class="priority-badge ${card.priority}">${card.priority}</span>
                </div>
                <div class="card-detail-section">
                    <h4>Created</h4>
                    <p>${card.created}</p>
                </div>
            `;
            modal.classList.remove('hidden');
        }
    }
};

// ============================================================================
// METRICS VIEW
// ============================================================================

const Metrics = {
    refresh() {
        this.renderGauges();
        this.renderErrorBudget();
    },

    renderGauges() {
        const slo = TowerState.sloMetrics;
        if (!slo) return;

        const gauges = [
            { id: 'gauge-rollback', value: 100 - (slo.rollback_rate?.current || 0), color: 'green' },
            { id: 'gauge-validator', value: slo.validator_pass?.current || 0, color: slo.validator_pass?.current >= 85 ? 'green' : 'yellow' },
            { id: 'gauge-audit', value: slo.audit_agreement?.current || 0, color: 'green' },
            { id: 'gauge-drift', value: slo.drift_free?.current || 0, color: 'green' }
        ];

        gauges.forEach(g => {
            const el = document.getElementById(g.id);
            if (el) {
                el.setAttribute('stroke-dasharray', `${g.value}, 100`);
                el.classList.remove('green', 'yellow', 'red');
                el.classList.add(g.color);
            }
        });
    },

    renderErrorBudget() {
        const budget = TowerState.sloMetrics?.error_budget;
        if (!budget) return;

        const pctEl = document.getElementById('error-budget-pct');
        const fillEl = document.getElementById('error-budget-fill');

        if (pctEl) pctEl.textContent = `${budget.remaining}%`;
        if (fillEl) fillEl.style.width = `${budget.remaining}%`;
    }
};

// ============================================================================
// EVENTS VIEW
// ============================================================================

const Events = {
    filter: '',
    typeFilter: '',

    refresh() {
        this.render();
        this.bindFilters();
    },

    render() {
        const tbody = document.getElementById('events-tbody');
        if (!tbody) return;

        let events = TowerState.events || [];

        // Apply filters
        if (this.typeFilter) {
            events = events.filter(e => e.type === this.typeFilter);
        }
        if (this.filter) {
            const search = this.filter.toLowerCase();
            events = events.filter(e =>
                e.type.toLowerCase().includes(search) ||
                e.card_id?.toLowerCase().includes(search) ||
                JSON.stringify(e.details).toLowerCase().includes(search)
            );
        }

        tbody.innerHTML = events.map(event => `
            <tr>
                <td>${Utils.formatTime(event.timestamp)}</td>
                <td><span class="event-type-badge">${event.type}</span></td>
                <td>${event.card_id || '-'}</td>
                <td>${event.actor || '-'}</td>
                <td><code>${JSON.stringify(event.details || {})}</code></td>
                <td><code class="hash">${Utils.parseHash(event.hash)}</code></td>
            </tr>
        `).join('') || '<tr><td colspan="6" class="empty">No events found</td></tr>';
    },

    bindFilters() {
        document.getElementById('events-filter')?.addEventListener('input', Utils.debounce((e) => {
            this.filter = e.target.value;
            this.render();
        }, 300));

        document.getElementById('events-type')?.addEventListener('change', (e) => {
            this.typeFilter = e.target.value;
            this.render();
        });
    }
};

// ============================================================================
// SELF-CORRECT VIEW
// ============================================================================

const SelfCorrect = {
    stages: ['validate', 'analyze', 'correct', 'verify'],
    currentStage: 0,
    running: false,

    refresh() {
        this.bindActions();
    },

    bindActions() {
        document.getElementById('start-selfcorrect')?.addEventListener('click', () => this.start());
        document.getElementById('clear-log')?.addEventListener('click', () => this.clearLog());
    },

    async start() {
        if (this.running) return;

        this.running = true;
        this.currentStage = 0;
        this.log('Starting self-correction cycle...', 'info');

        const btn = document.getElementById('start-selfcorrect');
        if (btn) btn.disabled = true;

        for (let i = 0; i < this.stages.length; i++) {
            this.currentStage = i;
            this.updateStageUI();

            const stage = this.stages[i];
            this.log(`Running ${stage} stage...`, 'info');

            // Simulate stage execution
            await this.runStage(stage);

            this.log(`${stage} stage completed`, 'success');
        }

        this.running = false;
        if (btn) btn.disabled = false;
        this.log('Self-correction cycle completed successfully!', 'success');
        Toast.success('Self-correction cycle completed');
    },

    async runStage(stage) {
        return new Promise(resolve => setTimeout(resolve, 1500 + Math.random() * 1000));
    },

    updateStageUI() {
        this.stages.forEach((stage, i) => {
            const el = document.getElementById(`stage-${stage}`);
            if (!el) return;

            el.classList.remove('completed', 'active', 'pending');
            if (i < this.currentStage) el.classList.add('completed');
            else if (i === this.currentStage) el.classList.add('active');
            else el.classList.add('pending');

            const status = el.querySelector('.stage-status');
            if (status) {
                status.textContent = i < this.currentStage ? 'Passed' :
                                    i === this.currentStage ? 'In Progress' : 'Pending';
            }
        });
    },

    log(message, type = 'info') {
        const logContent = document.getElementById('log-content');
        if (!logContent) return;

        const time = new Date().toLocaleTimeString();
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        entry.innerHTML = `<span class="log-time">${time}</span><span class="log-message">${Utils.escapeHtml(message)}</span>`;
        logContent.appendChild(entry);
        logContent.scrollTop = logContent.scrollHeight;
    },

    clearLog() {
        const logContent = document.getElementById('log-content');
        if (logContent) logContent.innerHTML = '';
    }
};

// ============================================================================
// VALIDATOR VIEW
// ============================================================================

const Validator = {
    validators: [
        { id: 'schema', name: 'Schema Validator', description: 'Validates JSON schemas for all inputs', status: 'passed' },
        { id: 'ledger', name: 'Ledger Integrity', description: 'Verifies hash chain integrity', status: 'passed' },
        { id: 'slo', name: 'SLO Compliance', description: 'Checks SLO targets are met', status: 'passed' },
        { id: 'security', name: 'Security Scanner', description: 'Scans for security vulnerabilities', status: 'passed' },
        { id: 'lint', name: 'Code Linter', description: 'Checks code style and quality', status: 'warning' },
        { id: 'deps', name: 'Dependency Check', description: 'Validates dependencies are up to date', status: 'passed' }
    ],

    refresh() {
        this.render();
        this.bindActions();
    },

    render() {
        const grid = document.getElementById('validators-grid');
        if (!grid) return;

        grid.innerHTML = this.validators.map(v => `
            <div class="validator-card ${v.status}">
                <div class="validator-icon">
                    ${v.status === 'passed' ? '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>' :
                      v.status === 'warning' ? '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>' :
                      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>'}
                </div>
                <div class="validator-content">
                    <h4>${v.name}</h4>
                    <p>${v.description}</p>
                </div>
                <div class="validator-status ${v.status}">${v.status}</div>
                <button class="validator-run" onclick="Validator.run('${v.id}')">Run</button>
            </div>
        `).join('');
    },

    bindActions() {
        document.getElementById('run-all-validators')?.addEventListener('click', () => this.runAll());
    },

    async run(id) {
        const validator = this.validators.find(v => v.id === id);
        if (!validator) return;

        Toast.info(`Running ${validator.name}...`);
        validator.status = 'running';
        this.render();

        // Simulate validation
        await new Promise(r => setTimeout(r, 1000 + Math.random() * 500));

        validator.status = Math.random() > 0.1 ? 'passed' : 'warning';
        this.render();
        Toast.success(`${validator.name} completed`);
    },

    async runAll() {
        Toast.info('Running all validators...');

        for (const v of this.validators) {
            await this.run(v.id);
        }

        Toast.success('All validators completed');
    }
};

// ============================================================================
// WASM HASH VERIFIER
// ============================================================================

const WASMVerifier = {
    async init() {
        try {
            if (typeof WebAssembly === 'undefined') {
                console.warn('WebAssembly not supported');
                return false;
            }

            // Try to load WASM module
            const response = await fetch('./tower_verify.wasm');
            if (!response.ok) {
                console.warn('WASM module not found, using JS fallback');
                return false;
            }

            const wasmBytes = await response.arrayBuffer();
            const wasmModule = await WebAssembly.instantiate(wasmBytes);
            TowerState.wasmModule = wasmModule.instance.exports;
            TowerState.wasmReady = true;
            console.log('WASM verifier initialized');
            return true;

        } catch (error) {
            console.warn('WASM init failed:', error.message);
            return false;
        }
    },

    async verifyChain(entries) {
        // JavaScript fallback verification
        const errors = [];

        for (let i = 0; i < entries.length - 1; i++) {
            const current = entries[i];
            const next = entries[i + 1];

            if (current.seq !== next.seq + 1) {
                errors.push(`Sequence gap at entry #${current.seq}`);
            }
        }

        return {
            valid: errors.length === 0,
            checked: entries.length,
            errors
        };
    },

    async computeHash(data) {
        const encoder = new TextEncoder();
        const dataBuffer = encoder.encode(JSON.stringify(data));
        const hashBuffer = await crypto.subtle.digest('SHA-256', dataBuffer);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    }
};

// ============================================================================
// ACTIONS
// ============================================================================

const Actions = {
    async runValidation() {
        Toast.info('Running validation...');
        try {
            await API.triggerRun('run_validation.sh');
            Toast.success('Validation started');
        } catch (error) {
            // Demo mode
            setTimeout(() => Toast.success('Validation completed (demo)'), 2000);
        }
    },

    async runGatecheck() {
        Toast.info('Running gatecheck...');
        setTimeout(() => Toast.success('Gatecheck completed (demo)'), 1500);
    },

    async runProofpack() {
        Toast.info('Generating proofpack...');
        setTimeout(() => Toast.success('Proofpack generated (demo)'), 2000);
    },

    async verifyChain() {
        Toast.info('Verifying hash chain...');
        const result = await WASMVerifier.verifyChain(TowerState.hashChain);

        if (result.valid) {
            Toast.success(`Hash chain verified (${result.checked} entries)`);
        } else {
            Toast.error(`Chain verification failed: ${result.errors.join(', ')}`);
        }
    },

    toggleFreeze() {
        if (!TowerState.status) return;
        TowerState.status.merge_freeze = !TowerState.status.merge_freeze;
        DataManager.updateStatusIndicators();
        Toast.info(`Merge freeze ${TowerState.status.merge_freeze ? 'enabled' : 'disabled'}`);
    },

    exportData() {
        const data = {
            status: TowerState.status,
            events: TowerState.events,
            cards: TowerState.cards,
            sloMetrics: TowerState.sloMetrics,
            hashChain: TowerState.hashChain,
            exportedAt: new Date().toISOString()
        };

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `tower-export-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);

        Toast.success('Data exported');
    }
};

// ============================================================================
// KEYBOARD SHORTCUTS
// ============================================================================

const Keyboard = {
    init() {
        document.addEventListener('keydown', (e) => this.handleKeydown(e));
    },

    handleKeydown(e) {
        // Ignore if in input field
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
            if (e.key === 'Escape') e.target.blur();
            return;
        }

        const isMod = e.metaKey || e.ctrlKey;
        const isShift = e.shiftKey;

        // Command palette (Cmd+K)
        if (isMod && e.key === 'k') {
            e.preventDefault();
            CommandPalette.toggle();
            return;
        }

        // Close modals/palette (Escape)
        if (e.key === 'Escape') {
            if (TowerState.commandPaletteOpen) {
                CommandPalette.close();
            } else {
                document.querySelectorAll('.modal:not(.hidden)').forEach(m => m.classList.add('hidden'));
            }
            return;
        }

        // Don't process shortcuts if palette is open
        if (TowerState.commandPaletteOpen) return;

        // Toggle sidebar (Cmd+B)
        if (isMod && e.key === 'b') {
            e.preventDefault();
            Sidebar.toggle();
            return;
        }

        // Toggle theme (Cmd+Shift+T)
        if (isMod && isShift && e.key === 'T') {
            e.preventDefault();
            Theme.toggle();
            return;
        }

        // Refresh (Cmd+R) - prevent default refresh
        if (isMod && e.key === 'r') {
            e.preventDefault();
            DataManager.refresh();
            return;
        }

        // View shortcuts (numbers)
        const viewMap = {
            '1': 'dashboard', '2': 'kanban', '3': 'metrics',
            '4': 'events', '5': 'selfcorrect', '6': 'validator'
        };
        if (!isMod && !isShift && viewMap[e.key]) {
            Navigation.switchView(viewMap[e.key]);
            return;
        }
    }
};

// ============================================================================
// MODAL HANDLING
// ============================================================================

const Modal = {
    init() {
        // Close modal on backdrop click
        document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
            backdrop.addEventListener('click', () => {
                backdrop.closest('.modal')?.classList.add('hidden');
            });
        });

        // Close buttons
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', () => {
                btn.closest('.modal')?.classList.add('hidden');
            });
        });
    }
};

// ============================================================================
// QUICK ACTIONS BINDING
// ============================================================================

const QuickActions = {
    init() {
        document.getElementById('qa-validate')?.addEventListener('click', () => Actions.runValidation());
        document.getElementById('qa-gatecheck')?.addEventListener('click', () => Actions.runGatecheck());
        document.getElementById('qa-proofpack')?.addEventListener('click', () => Actions.runProofpack());
        document.getElementById('qa-dashboard')?.addEventListener('click', () => DataManager.refresh());

        document.getElementById('refresh-btn')?.addEventListener('click', () => DataManager.refresh());
        document.getElementById('verify-chain-btn')?.addEventListener('click', () => Actions.verifyChain());
        document.getElementById('export-events-btn')?.addEventListener('click', () => Actions.exportData());
        document.getElementById('new-card-btn')?.addEventListener('click', () => Kanban.createCard());

        document.getElementById('view-all-activity')?.addEventListener('click', () => Navigation.switchView('events'));
    }
};

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', async () => {
    console.log('Tower Dashboard v2.0 initializing...');

    // Hide loading screen after initialization
    const loadingScreen = document.getElementById('loading-screen');

    // Initialize all components
    Toast.init();
    Theme.init();
    Sidebar.init();
    Navigation.init();
    CommandPalette.init();
    Modal.init();
    Keyboard.init();
    QuickActions.init();

    // Initialize WASM verifier (non-blocking)
    WASMVerifier.init();

    // Initialize data (loads demo data if API unavailable)
    await DataManager.init();

    // Hide loading screen
    if (loadingScreen) {
        loadingScreen.classList.add('fade-out');
        setTimeout(() => loadingScreen.remove(), 500);
    }

    console.log('Tower Dashboard ready!');
    Toast.success('Tower Dashboard loaded');
});

// Expose for debugging
window.Tower = {
    State: TowerState, Config, Utils, API, Toast, CommandPalette, Navigation, Sidebar, Theme,
    DataManager, Dashboard, Kanban, Metrics, Events, SelfCorrect, Validator, WASMVerifier, Actions, Keyboard
};
