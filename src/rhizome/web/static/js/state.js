/**
 * Rhizome Thinking - App State & Query Options Storage
 */

// ===== App State =====
const state = {
    currentView: 'searchView',
    selectedTags: [],
    searchResults: [],
    isLoading: false,
    isBatchMode: false,
    batchRefineMode: false,
    batchSelectedNodes: new Set(),
    batchProcessing: false,
    batchProgress: {
        total: 0,
        completed: 0,
        failed: 0,
        nodeStatus: {}
    }
};

// ===== Query Options Storage Manager =====
const queryOptionsStorage = {
    STORAGE_KEY: 'rhizome_query_options',

    defaults: {
        timeRange: 'all',
        limitSelect: '20',
        searchMode: 'balanced',
        selectedTags: []
    },

    load() {
        try {
            const stored = localStorage.getItem(this.STORAGE_KEY);
            if (stored) {
                return JSON.parse(stored);
            }
        } catch (e) {
            console.error('Failed to load query options:', e);
        }
        return { ...this.defaults };
    },

    save(options) {
        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(options));
        } catch (e) {
            console.error('Failed to save query options:', e);
        }
    },

    reset() {
        localStorage.removeItem(this.STORAGE_KEY);
        return { ...this.defaults };
    },

    getFromUI() {
        const timeRange = document.getElementById('timeRange')?.value || this.defaults.timeRange;
        const limitSelect = document.getElementById('limitSelect')?.value || this.defaults.limitSelect;
        let searchMode = this.defaults.searchMode;
        const activeModeBtn = document.querySelector('.search-mode-btn.active');
        if (activeModeBtn) {
            searchMode = activeModeBtn.dataset.mode;
        }
        return {
            timeRange,
            limitSelect,
            searchMode,
            selectedTags: [...state.selectedTags]
        };
    },

    applyToUI(options) {
        const timeRangeEl = document.getElementById('timeRange');
        const limitSelectEl = document.getElementById('limitSelect');
        if (timeRangeEl) timeRangeEl.value = options.timeRange || this.defaults.timeRange;
        if (limitSelectEl) limitSelectEl.value = options.limitSelect || this.defaults.limitSelect;
        const searchMode = options.searchMode || this.defaults.searchMode;
        document.querySelectorAll('.search-mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === searchMode);
        });
        updateSearchModeHelp(searchMode);
        if (options.selectedTags && options.selectedTags.length > 0) {
            state.selectedTags = [...options.selectedTags];
            updateTagFilterUI();
        } else {
            state.selectedTags = [];
            updateTagFilterUI();
        }
    }
};
