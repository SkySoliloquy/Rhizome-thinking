/**
 * Rhizome Thinking - Main Application Entry Point
 *
 * This file initializes the application and binds global event listeners.
 * All functionality has been split into modular files:
 *   state.js, api-client.js, ui-utils.js, window-manager.js,
 *   source-manager.js, processing-queue.js, search.js,
 *   node-operations.js, node-edit-delete.js, backup-manager.js,
 *   settings-update.js, mobile-pwa.js
 */

// ===== Event Listeners =====
document.addEventListener('DOMContentLoaded', () => {
    // Initialize source manager
    sourceManager.init();

    // Load saved query options
    const savedOptions = queryOptionsStorage.load();
    queryOptionsStorage.applyToUI(savedOptions);

    // Navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            ui.switchView(item.dataset.view);
        });
    });

    // Search - support both click and touch for mobile
    const searchBtn = document.getElementById('searchBtn');
    const searchInput = document.getElementById('searchInput');

    const handleSearch = (e) => {
        e.preventDefault();
        e.stopPropagation();
        console.log('[Mobile Debug] Search triggered');

        // Check query mode
        const activeMode = document.querySelector('.query-mode-btn.active')?.dataset.mode;
        if (activeMode === 'precise') {
            performPreciseSearch();
        } else {
            performSearch();
        }
    };

    searchBtn.addEventListener('click', handleSearch);
    searchBtn.addEventListener('touchend', (e) => {
        e.preventDefault();
        handleSearch(e);
    });

    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const activeMode = document.querySelector('.query-mode-btn.active')?.dataset.mode;
            if (activeMode === 'precise') {
                performPreciseSearch();
            } else {
                performSearch();
            }
        }
    });
    // Also handle mobile "Go" button on virtual keyboard
    searchInput.addEventListener('keyup', (e) => {
        if (e.key === 'Enter') {
            const activeMode = document.querySelector('.query-mode-btn.active')?.dataset.mode;
            if (activeMode === 'precise') {
                performPreciseSearch();
            } else {
                performSearch();
            }
        }
    });

    // Tag filters
    document.querySelectorAll('.tag-filter').forEach(btn => {
        btn.addEventListener('click', () => {
            const tag = btn.dataset.tag;

            // Handle "all" tag specially
            if (tag === 'all') {
                document.querySelectorAll('.tag-filter').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                state.selectedTags = [];
            } else {
                document.querySelector('.tag-filter[data-tag="all"]')?.classList.remove('active');
                if (btn.classList.contains('active')) {
                    btn.classList.remove('active');
                    state.selectedTags = state.selectedTags.filter(t => t !== tag);
                } else {
                    btn.classList.add('active');
                    state.selectedTags.push(tag);
                }
            }

            // Save options after tag change
            const currentOptions = queryOptionsStorage.getFromUI();
            queryOptionsStorage.save(currentOptions);
        });
    });

    // Search mode buttons
    document.querySelectorAll('.search-mode-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active from all buttons
            document.querySelectorAll('.search-mode-btn').forEach(b => b.classList.remove('active'));
            // Add active to clicked button
            btn.classList.add('active');
            // Update help text
            updateSearchModeHelp(btn.dataset.mode);
            // Save options after mode change
            const currentOptions = queryOptionsStorage.getFromUI();
            queryOptionsStorage.save(currentOptions);
        });
    });

    // Time range change
    const timeRangeEl = document.getElementById('timeRange');
    if (timeRangeEl) {
        timeRangeEl.addEventListener('change', () => {
            const currentOptions = queryOptionsStorage.getFromUI();
            queryOptionsStorage.save(currentOptions);
        });
    }

    // Limit select change
    const limitSelectEl = document.getElementById('limitSelect');
    if (limitSelectEl) {
        limitSelectEl.addEventListener('change', () => {
            const currentOptions = queryOptionsStorage.getFromUI();
            queryOptionsStorage.save(currentOptions);
        });
    }

    // Reset options button
    const resetBtn = document.getElementById('resetOptionsBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            const defaults = queryOptionsStorage.reset();
            queryOptionsStorage.applyToUI(defaults);
            ui.showToast('查询选项已重置为默认值');
        });
    }

    // Submit node
    document.getElementById('submitNodeBtn').addEventListener('click', submitNode);

    // Batch mode toggle (add node page)
    document.getElementById('batchModeBtn').addEventListener('click', toggleBatchMode);

    // Batch refine toggle (search results)
    const batchRefineToggleBtn = document.getElementById('batchRefineToggleBtn');
    if (batchRefineToggleBtn) {
        batchRefineToggleBtn.addEventListener('click', toggleBatchRefineMode);
    }

    // Batch refine confirm/cancel
    const batchRefineConfirmBtn = document.getElementById('batchRefineConfirmBtn');
    if (batchRefineConfirmBtn) {
        batchRefineConfirmBtn.addEventListener('click', confirmBatchRefine);
    }

    const batchRefineCancelBtn = document.getElementById('batchRefineCancelBtn');
    if (batchRefineCancelBtn) {
        batchRefineCancelBtn.addEventListener('click', toggleBatchRefineMode);
    }

    // Batch file upload
    document.getElementById('batchFile').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (event) => {
                document.getElementById('batchInput').value = event.target.result;
                document.getElementById('batchFileName').textContent = file.name;
            };
            reader.readAsText(file);
        }
    });

    // Modal close - close entire multi-window system
    document.getElementById('closeModal').addEventListener('click', () => {
        windowManager.closeAll();
    });

    // Multi-window container click delegation for link items
    document.getElementById('nodeModal').addEventListener('click', (e) => {
        // Handle link item clicks to open in side window
        const linkItem = e.target.closest('.link-item');
        if (linkItem) {
            const nodeId = linkItem.dataset.linkNodeId;
            if (nodeId) {
                e.stopPropagation();
                windowManager.openSideWindow(nodeId);
            }
        }

        // Close modal when clicking outside windows
        if (e.target.id === 'nodeModal' || e.target.classList.contains('multi-window-container')) {
            windowManager.closeAll();
        }
    });

    // Settings button
    document.getElementById('settingsBtn').addEventListener('click', () => {
        openSettingsModal();
    });

    // Menu toggle for mobile sidebar
    document.getElementById('menuToggle').addEventListener('click', () => {
        const panel = document.getElementById('controlPanel');
        panel.classList.toggle('open');
    });

    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', (e) => {
        const panel = document.getElementById('controlPanel');
        const menuBtn = document.getElementById('menuToggle');
        if (panel.classList.contains('open') &&
            !panel.contains(e.target) &&
            !menuBtn.contains(e.target)) {
            panel.classList.remove('open');
        }
    });

    // Event delegation for batch refine mode on search results
    const searchResultsContainer = document.getElementById('searchResults');
    if (searchResultsContainer) {
        searchResultsContainer.addEventListener('click', (e) => {
            if (!state.batchRefineMode) return;

            // Find the closest node card
            const card = e.target.closest('.node-card');
            if (card && card.dataset.nodeId) {
                e.preventDefault();
                e.stopPropagation();
                toggleNodeSelection(card.dataset.nodeId);
            }
        });
    }
});

// ===== Event Listeners for New Features =====
document.addEventListener('DOMContentLoaded', () => {
    // Query mode switching
    initQueryModeSwitching();

    // Edit modal
    document.getElementById('closeEditModal')?.addEventListener('click', closeEditModal);
    document.getElementById('cancelEditBtn')?.addEventListener('click', closeEditModal);
    document.getElementById('saveNodeBtn')?.addEventListener('click', saveNodeEdit);

    // Delete modal
    document.getElementById('closeDeleteModal')?.addEventListener('click', closeDeleteModal);
    document.getElementById('cancelDeleteBtn')?.addEventListener('click', closeDeleteModal);
    document.getElementById('confirmDeleteBtn')?.addEventListener('click', confirmDeleteNode);

    // Backup management
    document.getElementById('createBackupBtn')?.addEventListener('click', () => backupManager.createBackup());
    document.getElementById('refreshBackupsBtn')?.addEventListener('click', () => backupManager.loadBackups());

    // Import backup button
    const importBackupBtn = document.getElementById('importBackupBtn');
    const importBackupInput = document.getElementById('importBackupInput');
    if (importBackupBtn && importBackupInput) {
        importBackupBtn.addEventListener('click', () => {
            importBackupInput.click();
        });
        importBackupInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                backupManager.importBackup(file);
            }
            // Reset input to allow selecting the same file again
            e.target.value = '';
        });
    }

    // Backup restore modal
    document.getElementById('closeRestoreModal')?.addEventListener('click', () => backupManager.closeRestoreModal());
    document.getElementById('cancelRestoreBtn')?.addEventListener('click', () => backupManager.closeRestoreModal());
    document.getElementById('confirmRestoreBtn')?.addEventListener('click', () => backupManager.confirmRestoreBackup());

    // Backup delete modal
    document.getElementById('closeBackupDeleteModal')?.addEventListener('click', () => backupManager.closeDeleteModal());
    document.getElementById('cancelBackupDeleteBtn')?.addEventListener('click', () => backupManager.closeDeleteModal());
    document.getElementById('confirmBackupDeleteBtn')?.addEventListener('click', () => backupManager.confirmDeleteBackup());

    // Close modals on backdrop click
    document.getElementById('nodeEditModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'nodeEditModal') closeEditModal();
    });
    document.getElementById('deleteConfirmModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'deleteConfirmModal') closeDeleteModal();
    });
    document.getElementById('backupRestoreModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'backupRestoreModal') backupManager.closeRestoreModal();
    });
    document.getElementById('backupDeleteModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'backupDeleteModal') backupManager.closeDeleteModal();
    });

    // Back buttons for detail views
    document.getElementById('backFromNodeDetail')?.addEventListener('click', () => {
        const previousView = state.previousView || 'searchView';
        ui.switchView(previousView);
    });

    document.getElementById('backFromThemeDetail')?.addEventListener('click', () => {
        const previousView = state.previousView || 'searchView';
        ui.switchView(previousView);
    });

    // Settings modal
    document.getElementById('closeSettingsModal')?.addEventListener('click', closeSettingsModal);
    document.getElementById('checkUpdateBtn')?.addEventListener('click', checkForUpdates);
    document.getElementById('confirmUpdateBtn')?.addEventListener('click', performUpdate);
    document.getElementById('settingsModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'settingsModal') closeSettingsModal();
    });
});

// ===== Navigation Helpers =====
function showNodeDetailView(nodeId) {
    ui.switchView('nodeDetailView', { nodeId });
}

function showThemeDetailView(themeId) {
    ui.switchView('themeDetailView', { themeId });
}

// ===== Theme Evolution Navigation =====
function openThemeEvolutionView(themeId) {
    if (!themeId) {
        ui.showToast('请先选择一个主题', 'error');
        return;
    }
    ui.switchView('themeEvolutionView', { themeId });
}

function openThemeConflictView(themeId = null) {
    ui.switchView('themeConflictView', { themeId });
}

function goBackFromEvolution() {
    if (state.previousView) {
        ui.switchView(state.previousView);
    } else {
        ui.switchView('searchView');
    }
}

// Expose navigation functions globally
window.openThemeEvolutionView = openThemeEvolutionView;
window.openThemeConflictView = openThemeConflictView;
window.goBackFromEvolution = goBackFromEvolution;
