/**
 * Rhizome Thinking PWA
 * Frontend application for semantic knowledge base
 */

// ===== API Client =====
class APIClient {
    constructor() {
        this.baseURL = window.location.origin;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        if (config.body && typeof config.body === 'object') {
            config.body = JSON.stringify(config.body);
        }

        const response = await fetch(url, config);
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: '请求失败' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return response.json();
    }

    // Nodes
    async createNode(data) {
        return this.request('/api/v1/nodes', {
            method: 'POST',
            body: data
        });
    }

    async getNodes(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/api/v1/nodes?${query}`);
    }

    async getNode(id) {
        return this.request(`/api/v1/nodes/${id}`);
    }

    async deleteNode(id) {
        return this.request(`/api/v1/nodes/${id}`, { method: 'DELETE' });
    }

    // Query
    async query(data) {
        return this.request('/api/v1/query', {
            method: 'POST',
            body: data
        });
    }

    async clusterQuery(data) {
        return this.request('/api/v1/query/cluster', {
            method: 'POST',
            body: data
        });
    }

    async themeQuery(data) {
        return this.request('/api/v1/query/themes', {
            method: 'POST',
            body: data
        });
    }

    async searchKeywords(q, limit = 10) {
        return this.request(`/api/v1/search?q=${encodeURIComponent(q)}&limit=${limit}`);
    }

    // Links
    async createLink(data) {
        return this.request('/api/v1/links', {
            method: 'POST',
            body: data
        });
    }

    async confirmLink(nodeId, targetId) {
        return this.request(`/api/v1/nodes/${nodeId}/links/${targetId}/confirm`, {
            method: 'POST'
        });
    }

    // Stats
    async getStats() {
        return this.request('/api/v1/stats');
    }

    async getRecentActivity(days = 7) {
        return this.request(`/api/v1/stats/recent?days=${days}`);
    }

    // Tags
    async getTags() {
        return this.request('/api/v1/tags');
    }

    // Sources
    async getSources() {
        return this.request('/api/v1/sources');
    }

    async createSource(data) {
        return this.request('/api/v1/sources', {
            method: 'POST',
            body: data
        });
    }

    async updateSource(sourceId, data) {
        return this.request(`/api/v1/sources/${sourceId}`, {
            method: 'PUT',
            body: data
        });
    }

    async deleteSource(sourceId) {
        return this.request(`/api/v1/sources/${sourceId}`, {
            method: 'DELETE'
        });
    }

    // Node update
    async updateNode(id, data) {
        return this.request(`/api/v1/nodes/${id}`, {
            method: 'PUT',
            body: data
        });
    }

    // Precise query
    async preciseQuery(data) {
        return this.request('/api/v1/query/precise', {
            method: 'POST',
            body: data
        });
    }

    // Backups
    async getBackups() {
        return this.request('/api/v1/backups');
    }

    async createBackup() {
        return this.request('/api/v1/backups', {
            method: 'POST'
        });
    }

    async restoreBackup(backupName, confirm) {
        return this.request(`/api/v1/backups/${encodeURIComponent(backupName)}/restore`, {
            method: 'POST',
            body: { confirm }
        });
    }

    async deleteBackup(backupName) {
        return this.request(`/api/v1/backups/${encodeURIComponent(backupName)}`, {
            method: 'DELETE'
        });
    }
}

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
        nodeStatus: {} // nodeId -> 'processing' | 'success' | 'error'
    }
};

// ===== Query Options Storage Manager =====
const queryOptionsStorage = {
    STORAGE_KEY: 'rhizome_query_options',
    
    // Default options
    defaults: {
        timeRange: 'all',
        limitSelect: '20',
        searchMode: 'balanced',  // 改为搜索模式: strict, balanced, explore
        selectedTags: []
    },
    
    // Load options from localStorage
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
    
    // Save options to localStorage
    save(options) {
        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(options));
        } catch (e) {
            console.error('Failed to save query options:', e);
        }
    },
    
    // Reset to defaults
    reset() {
        localStorage.removeItem(this.STORAGE_KEY);
        return { ...this.defaults };
    },
    
    // Get current options from UI
    getFromUI() {
        const timeRange = document.getElementById('timeRange')?.value || this.defaults.timeRange;
        const limitSelect = document.getElementById('limitSelect')?.value || this.defaults.limitSelect;
        
        // 获取搜索模式
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
    
    // Apply options to UI
    applyToUI(options) {
        const timeRangeEl = document.getElementById('timeRange');
        const limitSelectEl = document.getElementById('limitSelect');
        
        if (timeRangeEl) timeRangeEl.value = options.timeRange || this.defaults.timeRange;
        if (limitSelectEl) limitSelectEl.value = options.limitSelect || this.defaults.limitSelect;
        
        // 应用搜索模式
        const searchMode = options.searchMode || this.defaults.searchMode;
        document.querySelectorAll('.search-mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === searchMode);
        });
        updateSearchModeHelp(searchMode);
        
        // Apply tag filters
        if (options.selectedTags && options.selectedTags.length > 0) {
            state.selectedTags = [...options.selectedTags];
            updateTagFilterUI();
        } else {
            state.selectedTags = [];
            updateTagFilterUI();
        }
    }
};

// ===== Multi-Window Manager =====
const windowManager = {
    windows: [],  // Array of window objects
    originNodeId: null,  // The starting node of the exploration path
    
    // Window object structure:
    // { id: string, nodeId: string, isMain: boolean, isOrigin: boolean, windowNumber: number }
    
    openMainWindow(nodeId) {
        // Clear existing windows and open main window
        this.windows = [];
        this.originNodeId = nodeId;

        const mainWindow = {
            id: 'main',
            nodeId: nodeId,
            isMain: true,
            isOrigin: true,
            windowNumber: 0
        };
        this.windows.push(mainWindow);

        // Show modal
        document.getElementById('nodeModal').classList.add('active');

        // Reset title to "节点详情"
        const modalHeader = document.querySelector('#mainWindow .modal-header h3');
        if (modalHeader) {
            modalHeader.textContent = '节点详情';
        }

        // Load main window content
        this.loadWindowContent(mainWindow);

        // Scroll to top after content is loaded
        setTimeout(() => {
            const modalBody = document.getElementById('modalBody');
            if (modalBody) {
                modalBody.scrollTop = 0;
            }
        }, 100);
    },
    
    openSideWindow(nodeId) {
        // Check if window already exists
        const existingWindow = this.windows.find(w => w.nodeId === nodeId);
        if (existingWindow) {
            // Highlight existing window
            this.highlightWindow(existingWindow.id);
            return;
        }

        // Ensure modal is open
        const modal = document.getElementById('nodeModal');
        if (!modal.classList.contains('active')) {
            modal.classList.add('active');
        }

        // Detect mobile portrait mode (screen width < 768px and portrait orientation)
        const isMobilePortrait = window.innerWidth < 768 && window.innerHeight > window.innerWidth;

        // Create new side window
        const windowNumber = this.windows.length;
        const sideWindow = {
            id: `side-${Date.now()}`,
            nodeId: nodeId,
            isMain: false,
            isOrigin: false,
            windowNumber: windowNumber,
            isMobilePopup: isMobilePortrait // Mark as mobile popup
        };
        this.windows.push(sideWindow);

        // Create appropriate DOM based on device type
        if (isMobilePortrait) {
            this.createMobilePopupDOM(sideWindow);
        } else {
            this.createSideWindowDOM(sideWindow);
        }

        // Load content
        this.loadWindowContent(sideWindow);
    },

    createMobilePopupDOM(windowObj) {
        // Create a floating popup overlay for mobile portrait mode
        const popupOverlay = document.createElement('div');
        popupOverlay.className = 'mobile-popup-overlay';
        popupOverlay.id = `overlay-${windowObj.id}`;
        popupOverlay.innerHTML = `
            <div class="mobile-popup" id="${windowObj.id}">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>笔记详情</h3>
                        <div class="window-controls">
                            <button class="window-control-btn close-popup-btn" title="关闭">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <line x1="18" y1="6" x2="6" y2="18"></line>
                                    <line x1="6" y1="6" x2="18" y2="18"></line>
                                </svg>
                            </button>
                        </div>
                    </div>
                    <div class="modal-body">
                        <div class="loading-state">加载中...</div>
                    </div>
                </div>
            </div>
        `;

        // Add event listener for close button
        const closeBtn = popupOverlay.querySelector('.close-popup-btn');
        closeBtn.addEventListener('click', () => this.closeMobilePopup(windowObj.id));

        // Close when clicking overlay background
        popupOverlay.addEventListener('click', (e) => {
            if (e.target === popupOverlay) {
                this.closeMobilePopup(windowObj.id);
            }
        });

        document.body.appendChild(popupOverlay);

        // Prevent body scroll when popup is open
        document.body.style.overflow = 'hidden';
    },

    closeMobilePopup(windowId) {
        const overlay = document.getElementById(`overlay-${windowId}`);
        if (overlay) {
            overlay.remove();
        }

        // Remove from windows array
        const windowIndex = this.windows.findIndex(w => w.id === windowId);
        if (windowIndex > -1) {
            this.windows.splice(windowIndex, 1);
        }

        // Restore body scroll if no more mobile popups
        const hasMobilePopups = this.windows.some(w => w.isMobilePopup);
        if (!hasMobilePopups) {
            document.body.style.overflow = '';
        }
    },
    
    createSideWindowDOM(windowObj) {
        const sideWindowsContainer = document.getElementById('sideWindows');
        
        const windowEl = document.createElement('div');
        windowEl.className = 'side-window';
        windowEl.id = windowObj.id;
        windowEl.innerHTML = `
            <div class="modal-content">
                <div class="window-number">${windowObj.windowNumber}</div>
                <div class="modal-header">
                    <h3>节点详情</h3>
                    <div class="window-controls">
                        <button class="window-control-btn maximize-btn" title="放大">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
                            </svg>
                        </button>
                        <button class="window-control-btn close-side-btn" title="关闭">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="18" y1="6" x2="6" y2="18"></line>
                                <line x1="6" y1="6" x2="18" y2="18"></line>
                            </svg>
                        </button>
                    </div>
                </div>
                <div class="modal-body">
                    <div class="loading-state">加载中...</div>
                </div>
            </div>
        `;
        
        // Add event listeners
        const maximizeBtn = windowEl.querySelector('.maximize-btn');
        const closeBtn = windowEl.querySelector('.close-side-btn');
        
        maximizeBtn.addEventListener('click', () => this.maximizeWindow(windowObj.id));
        closeBtn.addEventListener('click', () => this.closeWindow(windowObj.id));
        
        sideWindowsContainer.appendChild(windowEl);
        
        // Scroll to show new window
        sideWindowsContainer.scrollLeft = sideWindowsContainer.scrollWidth;
    },
    
    async loadWindowContent(windowObj) {
        try {
            const response = await api.getNode(windowObj.nodeId);
            const node = response.node;
            
            const contentHtml = this.buildWindowContent(node, response.related_nodes, windowObj);
            
            if (windowObj.isMain) {
                document.getElementById('modalBody').innerHTML = contentHtml;
            } else {
                const windowEl = document.getElementById(windowObj.id);
                if (windowEl) {
                    windowEl.querySelector('.modal-body').innerHTML = contentHtml;
                    
                    // For mobile popups, attach link click handlers directly
                    if (windowObj.isMobilePopup) {
                        this.attachMobilePopupHandlers(windowEl);
                    }
                }
            }
        } catch (error) {
            console.error('Load window content error:', error);
            const errorHtml = '<div style="padding: 20px; color: var(--color-danger);">加载失败</div>';
            if (windowObj.isMain) {
                document.getElementById('modalBody').innerHTML = errorHtml;
            } else {
                const windowEl = document.getElementById(windowObj.id);
                if (windowEl) {
                    windowEl.querySelector('.modal-body').innerHTML = errorHtml;
                }
            }
        }
    },
    
    attachMobilePopupHandlers(windowEl) {
        // Handle link item clicks to open nested source notes
        windowEl.querySelectorAll('.link-item').forEach(linkItem => {
            const handleLinkClick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                const nodeId = linkItem.dataset.linkNodeId;
                if (nodeId) {
                    console.log('[Mobile Debug] Opening linked node from popup:', nodeId);
                    this.openSideWindow(nodeId);
                }
            };
            
            linkItem.addEventListener('click', handleLinkClick);
            linkItem.addEventListener('touchend', (e) => {
                e.preventDefault();
                handleLinkClick(e);
            });
        });
    },
    
    buildWindowContent(node, relatedNodes, windowObj) {
        const tagsHtml = ui.renderTagsInOrder(node.tags, 'node-detail-tag');

        const questionsHtml = node.processed.open_questions?.length
            ? node.processed.open_questions.map(q => `<li>${escapeHtml(q)}</li>`).join('')
            : '<li style="color: var(--color-text-muted)">无问题记录</li>';

        const linksHtml = relatedNodes?.length
            ? relatedNodes.map(link => `
                <div class="link-item" data-link-node-id="${link.node.id}">
                    <div class="link-proposition">${escapeHtml(link.node.processed.proposition)}</div>
                    <div class="link-meta">
                        <span class="link-relation">${this.getRelationName(link.relation_type)}</span>
                        ${link.reason ? `<span class="link-reason" title="${escapeHtml(link.reason)}">${escapeHtml(link.reason.substring(0, 200))}${link.reason.length > 200 ? '...' : ''}</span>` : ''}
                        <span class="link-strength">强度: ${Math.round(link.strength * 100)}%</span>
                    </div>
                </div>
            `).join('')
            : '<p style="color: var(--color-text-muted)">暂无连接</p>';

        // Add origin indicator if this is the origin window
        const originBadge = windowObj.isOrigin ? '<span class="origin-indicator">起点</span>' : '';

        // Title - always show the short proposition
        const title = node.processed.proposition || '未命名节点';
        
        // Refined content - only show if exists
        const hasRefinedContent = node.refined_content && node.refined_content.trim().length > 0;

        // Raw input collapse/expand logic
        const rawInput = node.raw_input || '';
        const shouldCollapse = rawInput.length > 200;
        const rawInputId = `raw-input-${windowObj.id}-${Date.now()}`;
        const rawInputHtml = shouldCollapse
            ? `<div class="raw-input-container">
                <div class="raw-input-collapsed" id="${rawInputId}-collapsed">
                    ${escapeHtml(rawInput.substring(0, 200))}...
                    <button class="raw-input-toggle" onclick="windowManager.toggleRawInput('${rawInputId}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                        展开
                    </button>
                </div>
                <div class="raw-input-expanded" id="${rawInputId}-expanded" style="display: none;">
                    ${escapeHtml(rawInput)}
                    <button class="raw-input-toggle" onclick="windowManager.toggleRawInput('${rawInputId}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="18 15 12 9 6 15"></polyline>
                        </svg>
                        收起
                    </button>
                </div>
            </div>`
            : `<div class="node-detail-content" style="color: var(--color-text-secondary); font-size: 0.875rem;">${escapeHtml(rawInput)}</div>`;

        return `
            <!-- Title Section -->
            <div class="node-detail-section title-section" style="background: linear-gradient(135deg, var(--color-bg-secondary) 0%, var(--color-bg-tertiary) 100%); border-left: 4px solid var(--color-primary); padding: 20px;">
                <h2 style="font-size: 1.5rem; font-weight: 600; color: var(--color-text-primary); margin: 0 0 8px 0;">${escapeHtml(title)}</h2>
                <div style="font-size: 0.85rem; color: var(--color-text-muted);">
                    节点标题 · ${new Date(node.timestamp).toLocaleDateString('zh-CN')}
                </div>
            </div>

            <!-- Refined Content Section -->
            <div class="node-detail-section refined-content-section">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <h4 style="margin: 0;">📝 精炼内容 ${originBadge}</h4>
                    <div style="display: flex; gap: 8px;">
                        ${hasRefinedContent ? `
                        <button class="btn-icon refined-toggle-btn" onclick="windowManager.toggleRefinedContent(this)" title="收起/展开">
                            <svg class="collapse-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="18 15 12 9 6 15"></polyline>
                            </svg>
                            <svg class="expand-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: none;">
                                <polyline points="6 9 12 15 18 9"></polyline>
                            </svg>
                        </button>
                        ` : ''}
                        <button class="btn-icon" onclick="windowManager.regenerateRefinedContent('${node.id}')" title="重新生成">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="23 4 23 10 17 10"></polyline>
                                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                            </svg>
                        </button>
                    </div>
                </div>
                ${hasRefinedContent 
                    ? `<div class="node-detail-content refined-content md-content refined-content-expandable">${renderMarkdown(node.refined_content)}</div>${node.last_refined_at ? `<div style="font-size: 0.75rem; color: var(--color-text-muted); margin-top: 4px;">更新于 ${new Date(node.last_refined_at).toLocaleString('zh-CN')}</div>` : ''}`
                    : `<div style="color: var(--color-text-muted); padding: 20px; text-align: center; background: var(--color-bg-secondary); border-radius: 8px;">
                        <p>📝 尚未生成精炼内容</p>
                        <p style="font-size: 0.9em; margin-top: 8px;">点击上方"重新生成"按钮创建</p>
                    </div>`
                }
            </div>

            <div class="node-detail-section">
                <h4>标签</h4>
                <div class="node-detail-tags">${tagsHtml}</div>
            </div>

            <div class="node-detail-section">
                <h4>问题</h4>
                <div class="node-detail-content">
                    <ul style="margin-left: var(--spacing-md);">${questionsHtml}</ul>
                </div>
            </div>

            <div class="node-detail-section">
                <h4>来源</h4>
                <div class="node-detail-content" style="font-size: 0.875rem;">
                    ${node.source.type === 'original' ? '原创想法' : node.source.title || '未指定'}
                    ${node.source.location ? `<br><span style="color: var(--color-text-muted)">${node.source.location}</span>` : ''}
                </div>
            </div>

            <div class="node-detail-section">
                <h4>相关连接 (${relatedNodes?.length || 0})</h4>
                ${linksHtml}
            </div>

            <div class="node-detail-section">
                <h4>原始文件</h4>
                ${rawInputHtml}
            </div>

            <div class="node-detail-section">
                <h4>元数据</h4>
                <div style="font-size: 0.75rem; color: var(--color-text-muted);">
                    ID: ${node.id}<br>
                    创建时间: ${new Date(node.timestamp).toLocaleString('zh-CN')}
                    ${node.refined_content_version ? `<br>版本: ${node.refined_content_version}` : ''}
                </div>
            </div>
        `;
    },

    getRelationName(relation) {
        const names = {
            'support': '支持',
            'contradict': '矛盾',
            'extend': '延伸',
            'source': '来源',
            'analogy': '类比'
        };
        return names[relation] || relation;
    },
    
    toggleRawInput(rawInputId) {
        const collapsed = document.getElementById(`${rawInputId}-collapsed`);
        const expanded = document.getElementById(`${rawInputId}-expanded`);
        if (collapsed && expanded) {
            if (collapsed.style.display === 'none') {
                collapsed.style.display = 'block';
                expanded.style.display = 'none';
            } else {
                collapsed.style.display = 'none';
                expanded.style.display = 'block';
            }
        }
    },

    toggleRefinedContent(btn) {
        const section = btn.closest('.refined-content-section');
        const content = section.querySelector('.refined-content-expandable');
        const collapseIcon = btn.querySelector('.collapse-icon');
        const expandIcon = btn.querySelector('.expand-icon');

        if (content.classList.contains('collapsed')) {
            // Expand
            content.classList.remove('collapsed');
            collapseIcon.style.display = 'block';
            expandIcon.style.display = 'none';
        } else {
            // Collapse
            content.classList.add('collapsed');
            collapseIcon.style.display = 'none';
            expandIcon.style.display = 'block';
        }
    },
    
    maximizeWindow(windowId) {
        const windowObj = this.windows.find(w => w.id === windowId);
        if (!windowObj) return;
        
        if (windowObj.isMain) {
            // Already main window
            return;
        }
        
        // Find current main window
        const currentMain = this.windows.find(w => w.isMain);
        if (currentMain) {
            // Convert current main to side window
            currentMain.isMain = false;
            this.createSideWindowDOM(currentMain);
            this.loadWindowContent(currentMain);
        }
        
        // Remove the side window DOM that we're maximizing
        const sideWindowEl = document.getElementById(windowObj.id);
        if (sideWindowEl) {
            sideWindowEl.remove();
        }
        
        // Set this window as main
        windowObj.isMain = true;
        this.loadWindowContent(windowObj);
    },
    
    closeWindow(windowId) {
        const windowIndex = this.windows.findIndex(w => w.id === windowId);
        if (windowIndex === -1) return;
        
        const windowObj = this.windows[windowIndex];
        
        // Handle mobile popup differently
        if (windowObj.isMobilePopup) {
            this.closeMobilePopup(windowId);
            return;
        }
        
        // Remove DOM
        const windowEl = document.getElementById(windowId);
        if (windowEl) {
            windowEl.remove();
        }
        
        // Remove from array
        this.windows.splice(windowIndex, 1);
        
        // If closing main window, close entire modal
        if (windowObj.isMain) {
            // Find another window to promote to main, or close
            const remainingWindow = this.windows.find(w => !w.isMain);
            if (remainingWindow) {
                this.maximizeWindow(remainingWindow.id);
            } else {
                this.closeAll();
            }
        }
    },
    
    closeAll() {
        // Close any mobile popups first
        this.windows.forEach(w => {
            if (w.isMobilePopup) {
                const overlay = document.getElementById(`overlay-${w.id}`);
                if (overlay) {
                    overlay.remove();
                }
            }
        });
        
        this.windows = [];
        this.originNodeId = null;
        document.getElementById('sideWindows').innerHTML = '';
        document.getElementById('nodeModal').classList.remove('active');
        
        // Restore body scroll
        document.body.style.overflow = '';
    },

    openThemeWindow(themeData) {
        const theme = themeData.theme;
        const nodes = themeData.nodes || [];

        // Check if this theme window already exists
        const existingWindow = this.windows.find(w => w.isTheme && w.themeId === theme.id);
        if (existingWindow) {
            // Highlight existing window instead of creating a new one
            this.highlightWindow(existingWindow.id);
            return;
        }

        // Ensure modal is open
        const modal = document.getElementById('nodeModal');
        if (!modal.classList.contains('active')) {
            modal.classList.add('active');
        }

        // Check if there's already a main window
        const hasMainWindow = this.windows.some(w => w.isMain);

        // If no main window exists, make this theme window the main window
        const shouldBeMain = !hasMainWindow;

        // Create new window for theme
        const windowNumber = this.windows.length;
        const themeWindow = {
            id: `theme-${Date.now()}`,
            themeId: theme.id,
            isMain: shouldBeMain,
            isOrigin: shouldBeMain,
            windowNumber: shouldBeMain ? 0 : windowNumber,
            isTheme: true,
            themeData: themeData
        };
        this.windows.push(themeWindow);

        if (shouldBeMain) {
            // Load content into main window
            this.loadThemeWindowContent(themeWindow);
        } else {
            // Create side window DOM
            this.createThemeWindowDOM(themeWindow);
            // Load theme content
            this.loadThemeWindowContent(themeWindow);
        }
    },

    createThemeWindowDOM(windowObj) {
        const sideWindowsContainer = document.getElementById('sideWindows');

        const windowEl = document.createElement('div');
        windowEl.className = 'side-window theme-window';
        windowEl.id = windowObj.id;
        windowEl.innerHTML = `
            <div class="modal-content">
                <div class="window-number">${windowObj.windowNumber}</div>
                <div class="modal-header">
                    <h3>主题详情</h3>
                    <div class="window-controls">
                        <button class="window-control-btn maximize-btn" title="放大">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
                            </svg>
                        </button>
                        <button class="window-control-btn close-side-btn" title="关闭">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="18" y1="6" x2="6" y2="18"></line>
                                <line x1="6" y1="6" x2="18" y2="18"></line>
                            </svg>
                        </button>
                    </div>
                </div>
                <div class="modal-body">
                    <div class="loading-state">加载中...</div>
                </div>
            </div>
        `;

        // Add event listeners
        const maximizeBtn = windowEl.querySelector('.maximize-btn');
        const closeBtn = windowEl.querySelector('.close-side-btn');

        maximizeBtn.addEventListener('click', () => this.maximizeWindow(windowObj.id));
        closeBtn.addEventListener('click', () => this.closeWindow(windowObj.id));

        sideWindowsContainer.appendChild(windowEl);

        // Scroll to show new window
        sideWindowsContainer.scrollLeft = sideWindowsContainer.scrollWidth;
    },

    loadThemeWindowContent(windowObj) {
        const themeData = windowObj.themeData;
        const theme = themeData.theme;
        const nodes = themeData.nodes || [];

        const contentHtml = this.buildThemeWindowContent(theme, nodes, windowObj);

        // Get the modal body element (different for main vs side windows)
        let modalBody;
        if (windowObj.isMain) {
            modalBody = document.getElementById('modalBody');
            // Update main window title for theme
            const modalHeader = document.querySelector('#mainWindow .modal-header h3');
            if (modalHeader) {
                modalHeader.textContent = '主题详情';
            }
        } else {
            const windowEl = document.getElementById(windowObj.id);
            if (windowEl) {
                modalBody = windowEl.querySelector('.modal-body');
            }
        }

        if (modalBody) {
            modalBody.innerHTML = contentHtml;

            // Add event listeners for source node links (with mobile touch support)
            modalBody.querySelectorAll('.source-node-link').forEach(btn => {
                const handleSourceNodeClick = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const nodeId = btn.dataset.nodeId;
                    if (nodeId) {
                        console.log('[Mobile Debug] Opening source node:', nodeId);
                        this.openSideWindow(nodeId);
                    }
                };
                
                // Support both click and touch events for mobile compatibility
                btn.addEventListener('click', handleSourceNodeClick);
                btn.addEventListener('touchend', (e) => {
                    e.preventDefault();
                    handleSourceNodeClick(e);
                });
            });

            // Add event listeners for toggle buttons (with mobile touch support)
            modalBody.querySelectorAll('.source-nodes-toggle').forEach(btn => {
                const handleToggleClick = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const containerId = btn.dataset.containerId;
                    const container = document.getElementById(containerId);
                    const icon = btn.querySelector('svg');
                    if (container) {
                        if (container.style.display === 'none') {
                            container.style.display = 'block';
                            icon.style.transform = 'rotate(180deg)';
                            btn.querySelector('span').textContent = '收起来源';
                        } else {
                            container.style.display = 'none';
                            icon.style.transform = 'rotate(0deg)';
                            btn.querySelector('span').textContent = '展开来源';
                        }
                    }
                };
                
                // Support both click and touch events for mobile compatibility
                btn.addEventListener('click', handleToggleClick);
                btn.addEventListener('touchend', (e) => {
                    e.preventDefault();
                    handleToggleClick(e);
                });
            });
        }
    },

    buildThemeWindowContent(theme, nodes, windowObj) {
        const tagDisplayNames = {
            'definitive': '明确结论',
            'inferred': '推断结论',
            'vague': '模糊感知',
            'needs_thinking': '待思考问题',
            'cross-domain': '跨域连接'
        };

        const tagName = tagDisplayNames[theme.tag] || theme.tag;
        const containerId = `source-nodes-${windowObj.id}`;

        // Build source nodes list (collapsed by default)
        const sourceNodesHtml = nodes.map(node => `
            <div class="source-node-item">
                <div class="source-node-content">${escapeHtml(node.proposition)}</div>
                <button type="button" class="source-node-link" data-node-id="${node.id}">
                    查看笔记
                </button>
            </div>
        `).join('');

        return `
            <div class="node-detail-section">
                <h4>主题内容</h4>
                <div class="node-detail-content" style="font-weight: 500; font-size: 1.1rem; line-height: 1.6;">
                    ${escapeHtml(theme.summary)}
                </div>
            </div>

            <div class="node-detail-section">
                <h4>标签</h4>
                <div class="node-detail-tags">
                    <span class="node-detail-tag tag-${theme.tag}">${tagName}</span>
                </div>
            </div>

            ${theme.keywords?.length ? `
            <div class="node-detail-section">
                <h4>关键词</h4>
                <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                    ${theme.keywords.map(kw => `<span class="keyword-badge">${escapeHtml(kw)}</span>`).join('')}
                </div>
            </div>
            ` : ''}

            <div class="node-detail-section">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <h4 style="margin: 0;">来源笔记 (${nodes.length})</h4>
                    <button type="button" class="source-nodes-toggle" data-container-id="${containerId}">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="transition: transform 0.2s;">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                        <span>展开来源</span>
                    </button>
                </div>
                <div id="${containerId}" class="source-nodes-list" style="display: none;">
                    ${sourceNodesHtml || '<p style="color: var(--color-text-muted);">暂无来源笔记</p>'}
                </div>
            </div>

            <div class="node-detail-section">
                <h4>元数据</h4>
                <div style="font-size: 0.75rem; color: var(--color-text-muted);">
                    ID: ${theme.id}<br>
                    笔记数量: ${theme.node_count}<br>
                    创建时间: ${new Date(theme.created_at).toLocaleString('zh-CN')}
                </div>
            </div>
        `;
    },

    highlightWindow(windowId) {
        const windowEl = document.getElementById(windowId);
        if (windowEl) {
            windowEl.style.animation = 'none';
            windowEl.offsetHeight; // Trigger reflow
            windowEl.style.animation = 'pulse 0.5s ease';
        }
    },

    openCustomWindow(id, title, contentHtml) {
        // Ensure modal is open
        const modal = document.getElementById('nodeModal');
        if (!modal.classList.contains('active')) {
            modal.classList.add('active');
        }

        const windowNumber = this.windows.length;
        const customWindow = {
            id: id,
            isMain: false,
            isOrigin: false,
            windowNumber: windowNumber,
            isCustom: true,
            title: title,
            content: contentHtml
        };
        this.windows.push(customWindow);

        this.createCustomWindowDOM(customWindow, contentHtml);
    },

    createCustomWindowDOM(windowObj, contentHtml) {
        const sideWindowsContainer = document.getElementById('sideWindows');

        const windowEl = document.createElement('div');
        windowEl.className = 'side-window custom-window';
        windowEl.id = windowObj.id;
        windowEl.innerHTML = `
            <div class="modal-content">
                <div class="window-number">${windowObj.windowNumber}</div>
                <div class="modal-header">
                    <h3>${windowObj.title}</h3>
                    <div class="window-controls">
                        <button class="window-control-btn close-side-btn" title="关闭">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="18" y1="6" x2="6" y2="18"></line>
                                <line x1="6" y1="6" x2="18" y2="18"></line>
                            </svg>
                        </button>
                    </div>
                </div>
                <div class="modal-body">
                    ${contentHtml}
                </div>
            </div>
        `;

        const closeBtn = windowEl.querySelector('.close-side-btn');
        closeBtn.addEventListener('click', () => this.closeWindow(windowObj.id));

        sideWindowsContainer.appendChild(windowEl);
        sideWindowsContainer.scrollLeft = sideWindowsContainer.scrollWidth;
    },

    async regenerateRefinedContent(nodeId) {
        const btn = document.querySelector('.refined-content-section .btn-icon[title="重新生成"]');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<div class="spinner" style="width: 16px; height: 16px;"></div>';
        }

        try {
            const response = await fetch(`/api/v1/nodes/${nodeId}/refine`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (!response.ok) throw new Error('重新生成失败');

            const data = await response.json();

            // Reload the current window content
            const windowObj = this.windows.find(w => w.nodeId === nodeId);
            if (windowObj) {
                await this.loadWindowContent(windowObj);
            }

            if (window.ui) {
                window.ui.showToast('✓ 精炼内容已重新生成');
            }
        } catch (error) {
            console.error('Regenerate refined content error:', error);
            if (window.ui) {
                window.ui.showToast('✗ 重新生成失败: ' + error.message, 'error');
            }
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="23 4 23 10 17 10"></polyline>
                    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                </svg>`;
            }
        }
    }
};

// ===== Source Manager =====
const sourceManager = {
    sources: [],
    
    async init() {
        await this.loadSources();
        this.setupEventListeners();
    },
    
    async loadSources() {
        try {
            this.sources = await api.getSources();
            this.renderSourceSelect();
        } catch (error) {
            console.error('Failed to load sources:', error);
            // Fallback to default sources
            this.sources = [
                { id: 'original', name: '原创想法', description: '', is_builtin: true },
                { id: 'book', name: '书籍', description: '', is_builtin: true },
                { id: 'paper', name: '论文', description: '', is_builtin: true },
                { id: 'article', name: '文章', description: '', is_builtin: true }
            ];
            this.renderSourceSelect();
        }
    },
    
    renderSourceSelect() {
        const select = document.getElementById('sourceType');
        if (!select) return;
        
        select.innerHTML = this.sources.map(source => 
            `<option value="${source.id}">${source.name}</option>`
        ).join('');
    },
    
    renderSourceList() {
        const container = document.getElementById('sourceList');
        if (!container) return;
        
        container.innerHTML = this.sources.map(source => `
            <div class="source-item ${source.is_builtin ? 'builtin' : ''}" data-source-id="${source.id}">
                <div class="source-info">
                    <div class="source-name">
                        ${source.is_builtin ? '<span class="source-badge">内置</span>' : ''}
                        <span class="source-name-text">${escapeHtml(source.name)}</span>
                    </div>
                    ${source.description ? `<div class="source-desc">${escapeHtml(source.description)}</div>` : ''}
                </div>
                ${!source.is_builtin ? `
                    <div class="source-actions">
                        <button class="source-action-btn" onclick="sourceManager.startEditSource('${source.id}')">编辑</button>
                        <button class="source-action-btn delete" onclick="sourceManager.deleteSource('${source.id}')">删除</button>
                    </div>
                ` : ''}
            </div>
        `).join('');
    },
    
    startEditSource(sourceId) {
        const source = this.sources.find(s => s.id === sourceId);
        if (!source) return;
        
        const itemEl = document.querySelector(`.source-item[data-source-id="${sourceId}"]`);
        if (!itemEl) return;
        
        const nameEl = itemEl.querySelector('.source-name');
        const actionsEl = itemEl.querySelector('.source-actions');
        
        // Replace name with input field
        nameEl.innerHTML = `
            <input type="text" class="source-edit-input" value="${escapeHtml(source.name)}" id="edit-source-name-${sourceId}">
        `;
        
        // Replace actions with save/cancel buttons
        actionsEl.innerHTML = `
            <button class="source-action-btn save" onclick="sourceManager.saveEditSource('${sourceId}')">保存</button>
            <button class="source-action-btn cancel" onclick="sourceManager.cancelEditSource('${sourceId}')">取消</button>
        `;
        
        // Focus input
        const input = document.getElementById(`edit-source-name-${sourceId}`);
        if (input) {
            input.focus();
            input.select();
            // Enter to save, Escape to cancel
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.saveEditSource(sourceId);
            });
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') this.cancelEditSource(sourceId);
            });
        }
    },
    
    cancelEditSource(sourceId) {
        // Just re-render to restore original state
        this.renderSourceList();
    },
    
    async saveEditSource(sourceId) {
        const input = document.getElementById(`edit-source-name-${sourceId}`);
        if (!input) return;
        
        const newName = input.value.trim();
        const source = this.sources.find(s => s.id === sourceId);
        
        if (!newName) {
            ui.showToast('来源名称不能为空', 'error');
            return;
        }
        
        if (newName === source.name) {
            this.cancelEditSource(sourceId);
            return;
        }
        
        try {
            await api.updateSource(sourceId, { name: newName });
            await this.loadSources();
            this.renderSourceList();
            ui.showToast('来源类型更新成功');
        } catch (error) {
            ui.showToast(`更新失败: ${error.message}`, 'error');
        }
    },
    
    openModal() {
        this.renderSourceList();
        document.getElementById('sourceManagerModal').style.display = 'flex';
    },
    
    closeModal() {
        document.getElementById('sourceManagerModal').style.display = 'none';
        // Clear input fields
        document.getElementById('newSourceName').value = '';
        document.getElementById('newSourceDesc').value = '';
    },
    
    async addSource() {
        const nameInput = document.getElementById('newSourceName');
        const descInput = document.getElementById('newSourceDesc');
        
        const name = nameInput.value.trim();
        if (!name) {
            ui.showToast('请输入来源名称', 'error');
            return;
        }
        
        try {
            await api.createSource({
                name: name,
                description: descInput.value.trim() || null
            });
            
            await this.loadSources();
            this.renderSourceList();
            
            nameInput.value = '';
            descInput.value = '';
            
            ui.showToast('来源类型添加成功');
        } catch (error) {
            ui.showToast(`添加失败: ${error.message}`, 'error');
        }
    },
    
    async deleteSource(sourceId) {
        if (!window.confirm('确定要删除这个来源类型吗？')) return;
        
        try {
            await api.deleteSource(sourceId);
            await this.loadSources();
            this.renderSourceList();
            ui.showToast('来源类型删除成功');
        } catch (error) {
            ui.showToast(`删除失败: ${error.message}`, 'error');
        }
    },
    
    setupEventListeners() {
        // Manage sources button
        const manageBtn = document.getElementById('manageSourcesBtn');
        if (manageBtn) {
            manageBtn.addEventListener('click', () => this.openModal());
        }
        
        // Close modal button
        const closeBtn = document.getElementById('closeSourceManager');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.closeModal());
        }
        
        // Add source button
        const addBtn = document.getElementById('addSourceBtn');
        if (addBtn) {
            addBtn.addEventListener('click', () => this.addSource());
        }
        
        // Close on backdrop click
        const modal = document.getElementById('sourceManagerModal');
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) this.closeModal();
            });
        }
    }
};

// ===== Processing Queue =====
const processingQueue = {
    maxConcurrent: 3,
    tasks: [],
    runningCount: 0,

    addTask(rawInput, data) {
        const taskId = Date.now() + Math.random();
        const task = {
            id: taskId,
            rawInput: rawInput.substring(0, 50) + (rawInput.length > 50 ? '...' : ''),
            status: 'pending', // pending, processing, completed, failed
            progress: 0,
            data: data,
            error: null
        };

        this.tasks.push(task);
        this.renderQueue();
        this.processQueue();

        return taskId;
    },

    async processQueue() {
        while (this.runningCount < this.maxConcurrent && this.tasks.some(t => t.status === 'pending')) {
            const task = this.tasks.find(t => t.status === 'pending');
            if (task) {
                this.runningCount++;
                task.status = 'processing';
                this.renderQueue();
                this.executeTask(task);
            }
        }
    },

    async executeTask(task) {
        try {
            // Simulate progress updates
            const progressInterval = setInterval(() => {
                if (task.progress < 90) {
                    task.progress += Math.random() * 15;
                    if (task.progress > 90) task.progress = 90;
                    this.renderQueue();
                }
            }, 500);

            const response = await api.createNode(task.data);
            clearInterval(progressInterval);
            task.progress = 100;
            task.status = 'completed';
            task.response = response;

            ui.showToast('节点创建成功！');

            // Show potential links if any
            if (response.potential_links && response.potential_links.length > 0) {
                showPotentialLinks(response.node, response.potential_links);
            }

        } catch (error) {
            task.status = 'failed';
            task.error = error.message;
            ui.showToast(`创建失败: ${error.message}`, 'error');
            console.error('Create node error:', error);
        } finally {
            this.runningCount--;
            this.renderQueue();
            this.processQueue();
            this.cleanupOldTasks();
        }
    },

    removeTask(taskId) {
        const task = this.tasks.find(t => t.id === taskId);
        if (task && task.status !== 'processing') {
            this.tasks = this.tasks.filter(t => t.id !== taskId);
            this.renderQueue();
        }
    },

    cleanupOldTasks() {
        // Remove completed tasks older than 5 minutes
        const fiveMinutesAgo = Date.now() - 5 * 60 * 1000;
        this.tasks = this.tasks.filter(t => {
            if (t.status === 'completed' && t.id < fiveMinutesAgo) {
                return false;
            }
            return true;
        });
        this.renderQueue();
    },

    renderQueue() {
        const container = document.getElementById('processingQueue');
        if (!container) return;

        if (this.tasks.length === 0) {
            container.innerHTML = '';
            return;
        }

        container.innerHTML = this.tasks.map(task => {
            let statusIcon = '';
            let progressBar = '';
            let removeBtnClass = '';
            let removeBtn = '';

            switch (task.status) {
                case 'pending':
                    statusIcon = '<svg class="clock" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>';
                    progressBar = `<div class="queue-progress"><div class="queue-progress-bar"><div class="queue-progress-bar-fill" style="width: 0%"></div></div><span class="queue-percent">等待中</span></div>`;
                    break;
                case 'processing':
                    statusIcon = '<div class="spinner"></div>';
                    progressBar = `<div class="queue-progress"><div class="queue-progress-bar"><div class="queue-progress-bar-fill" style="width: ${task.progress}%"></div></div><span class="queue-percent">${Math.round(task.progress)}%</span></div>`;
                    break;
                case 'completed':
                    statusIcon = '<svg class="checkmark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="20 6 9 17 4 12"></polyline></svg>';
                    progressBar = '<span class="queue-percent" style="color: var(--color-success)">已完成</span>';
                    removeBtnClass = ' completed';
                    removeBtn = '';
                    break;
                case 'failed':
                    statusIcon = '<svg class="cross" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
                    progressBar = `<span class="queue-percent" style="color: var(--color-danger)">失败</span>`;
                    break;
            }

            if (task.status !== 'completed') {
                removeBtn = `<button class="queue-remove${removeBtnClass}" onclick="processingQueue.removeTask(${task.id})">&times;</button>`;
            } else {
                removeBtn = `<button class="queue-remove${removeBtnClass}" disabled>&times;</button>`;
            }

            return `
                <div class="queue-item ${task.status}">
                    <div class="queue-status">${statusIcon}</div>
                    <div class="queue-content" title="${escapeHtml(task.rawInput)}">${escapeHtml(task.rawInput)}</div>
                    ${progressBar}
                    ${removeBtn}
                </div>
            `;
        }).join('');
    }
};

// ===== UI Helpers =====
const ui = {
    showToast(message, type = 'success') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 3000);
    },

    showLoading(element, text = '加载中...') {
        element.dataset.originalText = element.innerHTML;
        element.innerHTML = `<span class="loading"></span> ${text}`;
        element.disabled = true;
    },

    hideLoading(element) {
        if (element.dataset.originalText) {
            element.innerHTML = element.dataset.originalText;
            element.disabled = false;
        }
    },

    switchView(viewId, params = null) {
        // Hide all views
        document.querySelectorAll('.view').forEach(view => {
            view.classList.remove('active');
        });

        // Show target view
        const targetView = document.getElementById(viewId);
        if (targetView) {
            targetView.classList.add('active');
        }

        // Update nav (only for main views)
        const mainViews = ['searchView', 'addNodeView', 'outlineView', 'epistemicMapView', 'graphView', 'statsView', 'relationshipManagerView', 'relationshipGraphView'];
        if (mainViews.includes(viewId)) {
            document.querySelectorAll('.nav-item').forEach(item => {
                item.classList.remove('active');
                if (item.dataset.view === viewId) {
                    item.classList.add('active');
                }
            });
        }

        // Store previous view for back navigation
        if (state.currentView && mainViews.includes(state.currentView)) {
            state.previousView = state.currentView;
        }

        state.currentView = viewId;

        // Load view-specific data
        if (viewId === 'statsView') {
            loadStats();
        } else if (viewId === 'outlineView') {
            if (window.outlineView) window.outlineView.init();
        } else if (viewId === 'epistemicMapView') {
            if (window.epistemicMapView) window.epistemicMapView.init();
        } else if (viewId === 'graphView') {
            if (window.graphView) window.graphView.init();
        } else if (viewId === 'relationshipManagerView') {
            if (window.relationshipManagerView) window.relationshipManagerView.init();
        } else if (viewId === 'relationshipGraphView') {
            if (window.relationshipGraphView) window.relationshipGraphView.init();
        } else if (viewId === 'nodeDetailView' && params?.nodeId) {
            if (window.NodeDetailView) window.NodeDetailView.show(params.nodeId);
        } else if (viewId === 'themeDetailView' && params?.themeId) {
            if (window.ThemeDetailView) window.ThemeDetailView.show(params.themeId);
        } else if (viewId === 'themeEvolutionView' && params?.themeId) {
            if (window.themeEvolutionView) window.themeEvolutionView.init(params.themeId);
        } else if (viewId === 'themeConflictView') {
            if (window.themeConflictView) window.themeConflictView.init(params?.themeId);
        }
    },

    formatDate(dateStr) {
        const date = new Date(dateStr);
        const now = new Date();
        const diff = now - date;
        
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        
        if (days === 0) return '今天';
        if (days === 1) return '昨天';
        if (days < 7) return `${days}天前`;
        if (days < 30) return `${Math.floor(days / 7)}周前`;
        
        return date.toLocaleDateString('zh-CN');
    },

    // Fixed tag order for consistent display
    TAG_ORDER: ['definitive', 'inferred', 'vague', 'needs_thinking', 'cross-domain'],

    getTagDisplayName(tag) {
        const names = {
            'definitive': '明确结论',
            'inferred': '推断结论',
            'vague': '模糊感知',
            'needs_thinking': '待思考',
            'cross-domain': '跨域连接'
        };
        return names[tag] || tag;
    },

    getTagColor(tag) {
        // Tag color scheme for visual distinction
        const colors = {
            'definitive': {
                bg: 'rgba(0, 184, 148, 0.15)',
                border: 'rgba(0, 184, 148, 0.3)',
                text: '#00b894'
            },
            'inferred': {
                bg: 'rgba(108, 92, 231, 0.15)',
                border: 'rgba(108, 92, 231, 0.3)',
                text: '#a29bfe'
            },
            'vague': {
                bg: 'rgba(253, 203, 110, 0.15)',
                border: 'rgba(253, 203, 110, 0.3)',
                text: '#fdcb6e'
            },
            'needs_thinking': {
                bg: 'rgba(231, 76, 60, 0.15)',
                border: 'rgba(231, 76, 60, 0.3)',
                text: '#e74c3c'
            },
            'cross-domain': {
                bg: 'rgba(0, 206, 201, 0.15)',
                border: 'rgba(0, 206, 201, 0.3)',
                text: '#00cec9'
            }
        };
        return colors[tag] || {
            bg: 'var(--color-bg-tertiary)',
            border: 'rgba(255, 255, 255, 0.1)',
            text: 'var(--color-text-secondary)'
        };
    },

    renderTag(tag, className = 'node-tag') {
        const color = this.getTagColor(tag);
        const name = this.getTagDisplayName(tag);
        return `<span class="${className}" style="
            background: ${color.bg};
            border: 1px solid ${color.border};
            color: ${color.text};
        ">${name}</span>`;
    },

    renderTagsInOrder(tags, className = 'node-tag') {
        // Render tags in fixed order with empty placeholders for missing tags
        return this.TAG_ORDER.map(tagType => {
            if (tags.includes(tagType)) {
                return this.renderTag(tagType, className);
            } else {
                // Return empty placeholder to maintain layout
                return `<span class="${className} tag-placeholder" style="
                    visibility: hidden;
                    pointer-events: none;
                "></span>`;
            }
        }).join('');
    }
};

// ===== API Instance =====
const api = new APIClient();

// ===== Search Progress Manager =====
const searchProgress = {
    eventSource: null,
    currentStage: 'submitting',
    
    stages: [
        'submitting',
        'loading_themes',
        'llm_reranking',
        'processing_results',
        'complete'
    ],
    
    show() {
        const progressEl = document.getElementById('searchProgress');
        if (progressEl) {
            progressEl.style.display = 'block';
            progressEl.classList.remove('error');
        }
        this.reset();
    },
    
    hide() {
        const progressEl = document.getElementById('searchProgress');
        if (progressEl) {
            // Delay hiding so user can see completion
            setTimeout(() => {
                progressEl.style.display = 'none';
            }, 800);
        }
    },
    
    reset() {
        this.currentStage = 'submitting';
        this.updateProgress(0, '准备搜索', '');
        this.updateSteps('submitting');
    },
    
    updateProgress(percent, message, detail) {
        const fillEl = document.getElementById('progressFill');
        const stageEl = document.getElementById('progressStage');
        const percentEl = document.getElementById('progressPercent');
        const detailEl = document.getElementById('progressDetail');
        
        if (fillEl) fillEl.style.width = `${percent}%`;
        if (stageEl) stageEl.textContent = message;
        if (percentEl) percentEl.textContent = `${percent}%`;
        if (detailEl) detailEl.textContent = detail || '';
    },
    
    updateSteps(activeStage) {
        const steps = document.querySelectorAll('.step');
        const lines = document.querySelectorAll('.step-line');
        
        let foundActive = false;
        let activeIndex = -1;
        
        // Find active index
        steps.forEach((step, index) => {
            const stepName = step.dataset.step;
            if (stepName === activeStage) {
                activeIndex = index;
            }
        });
        
        steps.forEach((step, index) => {
            const stepName = step.dataset.step;
            step.classList.remove('active', 'completed');
            
            if (stepName === activeStage) {
                step.classList.add('active');
                foundActive = true;
            } else if (index < activeIndex) {
                step.classList.add('completed');
            }
        });
        
        // Update lines
        lines.forEach((line, index) => {
            line.classList.remove('active');
            if (index < activeIndex) {
                line.classList.add('active');
            }
        });
    },
    
    setError(message) {
        const progressEl = document.getElementById('searchProgress');
        if (progressEl) {
            progressEl.classList.add('error');
        }
        this.updateProgress(0, '搜索出错', message);
    },
    
    close() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
};

// ===== View Functions =====

// Search View - Streaming with progress
async function performSearch() {
    const input = document.getElementById('searchInput');
    const query = input.value.trim();

    if (!query) {
        ui.showToast('请输入查询内容', 'error');
        return;
    }

    // Close any existing search
    searchProgress.close();
    
    const searchBtn = document.getElementById('searchBtn');
    ui.showLoading(searchBtn);
    searchProgress.show();
    
    try {
        const timeRange = document.getElementById('timeRange').value;
        const limit = parseInt(document.getElementById('limitSelect').value);
        
        // 获取搜索模式
        const activeModeBtn = document.querySelector('.search-mode-btn.active');
        const searchMode = activeModeBtn ? activeModeBtn.dataset.mode : 'balanced';

        const requestData = {
            anchor: query,
            modifiers: {
                time_range: timeRange,
                tags: state.selectedTags,
                limit: limit,
                search_mode: searchMode,
                // 保留 min_similarity 用于向量搜索部分
                min_similarity: 0.3
            }
        };

        // Use streaming search with progress
        await performStreamingSearch(requestData);

    } catch (error) {
        ui.showToast(`查询失败: ${error.message}`, 'error');
        searchProgress.setError(error.message);
        console.error('Search error:', error);
    } finally {
        ui.hideLoading(searchBtn);
        searchProgress.hide();
    }
}

function performStreamingSearch(requestData) {
    return new Promise((resolve, reject) => {
        // Reset the result processed flag for new search
        searchResultProcessed = false;
        
        const query = requestData.anchor;
        const displayLimit = requestData.modifiers?.limit || 20;  // 前端显示限制
        
        console.log('[Mobile Debug] Starting streaming search:', query);
        console.log('[Mobile Debug] Request data:', JSON.stringify(requestData));
        console.log('[Mobile Debug] Display limit:', displayLimit);
        
        // Detect mobile
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        console.log('[Mobile Debug] Is mobile:', isMobile);
        
        // Create EventSource for streaming
        // Note: EventSource doesn't support POST, so we use a workaround
        // by creating a temporary fetch-based stream reader
        
        const url = `${window.location.origin}/api/v1/query/themes/stream/fast`;
        console.log('[Mobile Debug] Fetch URL:', url);
        
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData),
            // Add cache control for mobile
            cache: 'no-cache'
        }).then(response => {
            console.log('[Mobile Debug] Fetch response:', response.status, response.ok);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let chunkCount = 0;
            
            function readStream() {
                reader.read().then(({ done, value }) => {
                    if (done) {
                        console.log('[Mobile Debug] Stream done, total chunks:', chunkCount);
                        searchProgress.close();
                        resolve();
                        return;
                    }
                    
                    chunkCount++;
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop(); // Keep incomplete line in buffer
                    
                    lines.forEach(line => {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6));
                                console.log('[Mobile Debug] Stream data:', data.type, data.percent || '');
                                handleStreamData(data, query, displayLimit);
                            } catch (e) {
                                console.error('[Mobile Debug] Failed to parse stream data:', e, line);
                            }
                        }
                    });
                    
                    readStream();
                }).catch(error => {
                    console.error('[Mobile Debug] Stream read error:', error);
                    searchProgress.close();
                    reject(error);
                });
            }
            
            readStream();
        }).catch(error => {
            // Fallback to non-streaming search if streaming fails
            console.warn('[Mobile Debug] Streaming search failed, falling back:', error);
            performFallbackSearch(requestData).then(resolve).catch(reject);
        });
    });
}

// Track if result has been processed to avoid duplicate toasts
let searchResultProcessed = false;

function handleStreamData(data, query, displayLimit = 20) {
    if (data.type === 'progress') {
        searchProgress.updateProgress(data.percent, data.message, data.detail);
        searchProgress.updateSteps(data.stage);
    } else if (data.type === 'result') {
        // Only process result once to avoid duplicate toasts
        if (!searchResultProcessed) {
            searchResultProcessed = true;
            renderThemeResults(data.results, query, displayLimit, data.total_themes);
            ui.showToast(`找到 ${data.total_themes} 个主题`, 'success');
        }
    } else if (data.type === 'error') {
        throw new Error(data.message);
    }
}

async function performFallbackSearch(requestData) {
    // Fallback to regular API if streaming is not supported
    searchProgress.updateProgress(10, '正在搜索...', '使用传统搜索模式');
    
    try {
        const response = await api.themeQuery(requestData);
        renderThemeResults(response.results, requestData.anchor);
        searchProgress.updateProgress(100, '搜索完成', '');
    } catch (error) {
        throw error;
    }
}

function renderThemeResults(results, query, displayLimit = 20, totalThemes = 0) {
    const container = document.getElementById('searchResults');

    if (!results || results.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>未找到与 "${escapeHtml(query)}" 相关的主题</p>
            </div>
        `;
        return;
    }

    // 计算总主题数
    const actualTotal = totalThemes || results.reduce((sum, cat) => sum + (cat.themes?.length || 0), 0);
    
    // 收集所有主题到一个列表
    let allThemes = [];
    for (const category of results) {
        if (!category.themes || category.themes.length === 0) continue;
        for (const themeData of category.themes) {
            allThemes.push({
                ...themeData,
                tag: category.tag,
                tag_display_name: category.tag_display_name
            });
        }
    }
    
    // 根据匹配分数排序
    allThemes.sort((a, b) => (b.match_score || 0) - (a.match_score || 0));
    
    // 判断是否需要截断
    const shouldTruncate = allThemes.length > displayLimit;
    const themesToShow = shouldTruncate ? allThemes.slice(0, displayLimit) : allThemes;
    const remainingCount = allThemes.length - displayLimit;
    
    // 按分类重新组织要显示的主题
    const categorizedThemes = {};
    for (const theme of themesToShow) {
        if (!categorizedThemes[theme.tag]) {
            categorizedThemes[theme.tag] = {
                tag: theme.tag,
                tag_display_name: theme.tag_display_name,
                themes: []
            };
        }
        categorizedThemes[theme.tag].themes.push(theme);
    }
    
    // 按原始顺序排列分类
    const tagOrder = ["definitive", "inferred", "vague", "needs_thinking", "cross-domain"];
    const orderedCategories = tagOrder
        .map(tag => categorizedThemes[tag])
        .filter(cat => cat !== undefined);

    let html = '<div class="theme-results">';
    
    // 显示结果统计
    if (shouldTruncate) {
        html += `
            <div class="results-summary">
                <span class="results-count">显示前 ${displayLimit} 个结果（共 ${actualTotal} 个）</span>
            </div>
        `;
    }

    for (const category of orderedCategories) {
        html += `
            <div class="theme-category">
                <div class="theme-category-header">
                    <div class="theme-category-title">
                        <span class="tag-badge tag-${category.tag}">${escapeHtml(category.tag_display_name)}</span>
                        <span class="theme-count">${category.themes.length} 个主题</span>
                    </div>
                </div>
                <div class="theme-list">
                    ${category.themes.map((themeData, index) => renderThemeCard(themeData, category.tag, index)).join('')}
                </div>
            </div>
        `;
    }
    
    // 添加"显示全部"按钮
    if (shouldTruncate) {
        html += `
            <div class="show-more-container">
                <button class="show-more-btn" id="showAllResults">
                    <span>显示全部 ${actualTotal} 个结果</span>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M6 9l6 6 6-6"/>
                    </svg>
                </button>
            </div>
        `;
    }

    html += '</div>';
    container.innerHTML = html;
    
    // 添加"显示全部"按钮事件监听
    if (shouldTruncate) {
        const showAllBtn = document.getElementById('showAllResults');
        if (showAllBtn) {
            showAllBtn.addEventListener('click', () => {
                renderAllThemeResults(results, query, actualTotal);
            });
        }
    }

    // Add event listeners for "打开" buttons using event delegation for better mobile support
    container.addEventListener('click', (e) => {
        const btn = e.target.closest('.theme-open-btn');
        if (!btn) return;
        
        e.preventDefault();
        e.stopPropagation();
        console.log('[Mobile Debug] Open button clicked (delegation)');
        
        const themeId = btn.dataset.themeId;
        const card = container.querySelector(`[data-theme-id="${themeId}"]`);
        
        if (card && typeof windowManager !== 'undefined' && windowManager) {
            const themeDataStr = card.dataset.themeData;
            console.log('[Mobile Debug] themeDataStr length:', themeDataStr?.length);
            if (themeDataStr) {
                try {
                    // Try to parse the data
                    let themeData;
                    try {
                        themeData = JSON.parse(themeDataStr);
                    } catch (e) {
                        // Try with entity replacement
                        themeData = JSON.parse(themeDataStr.replace(/&#39;/g, "'"));
                    }
                    console.log('[Mobile Debug] Opening theme window:', themeData?.theme?.id);
                    windowManager.openThemeWindow(themeData);
                } catch (err) {
                    console.error('[Mobile Debug] Failed to parse theme data:', err);
                    ui.showToast('无法打开主题详情', 'error');
                }
            } else {
                console.error('[Mobile Debug] No theme data found');
                ui.showToast('主题数据缺失', 'error');
            }
        } else {
            console.error('[Mobile Debug] Card or windowManager not found:', { 
                hasCard: !!card, 
                windowManagerExists: typeof windowManager !== 'undefined',
                windowManager: !!windowManager 
            });
        }
    });
    
}

// 显示所有主题结果（不截断）
function renderAllThemeResults(results, query, totalThemes) {
    const container = document.getElementById('searchResults');
    
    // 按分类组织主题
    const tagOrder = ["definitive", "inferred", "vague", "needs_thinking", "cross-domain"];
    const tagDisplayNames = {
        "definitive": "明确结论",
        "inferred": "推断结论",
        "vague": "模糊感知",
        "needs_thinking": "待思考问题",
        "cross-domain": "跨域连接"
    };
    
    let html = '<div class="theme-results">';
    
    // 显示结果统计
    html += `
        <div class="results-summary">
            <span class="results-count">显示全部 ${totalThemes} 个结果</span>
            <button class="collapse-btn" id="collapseResults">收起</button>
        </div>
    `;
    
    // 按固定顺序遍历分类
    for (const tag of tagOrder) {
        const category = results.find(r => r.tag === tag);
        if (!category || !category.themes || category.themes.length === 0) continue;
        
        html += `
            <div class="theme-category">
                <div class="theme-category-header">
                    <div class="theme-category-title">
                        <span class="tag-badge tag-${tag}">${escapeHtml(tagDisplayNames[tag])}</span>
                        <span class="theme-count">${category.themes.length} 个主题</span>
                    </div>
                </div>
                <div class="theme-list">
                    ${category.themes.map((themeData, index) => renderThemeCard(themeData, tag, index)).join('')}
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    container.innerHTML = html;
    
    // 添加收起按钮事件
    const collapseBtn = document.getElementById('collapseResults');
    if (collapseBtn) {
        collapseBtn.addEventListener('click', () => {
            // 重新渲染截断版本（使用默认limit）
            renderThemeResults(results, query, 20, totalThemes);
        });
    }
    
    // 添加事件监听（复用之前的逻辑）
    container.addEventListener('click', (e) => {
        const btn = e.target.closest('.theme-open-btn');
        if (!btn) return;
        
        e.preventDefault();
        e.stopPropagation();
        
        const themeId = btn.dataset.themeId;
        const card = container.querySelector(`[data-theme-id="${themeId}"]`);
        
        if (card && typeof windowManager !== 'undefined' && windowManager) {
            const themeDataStr = card.dataset.themeData;
            if (themeDataStr) {
                try {
                    let themeData;
                    try {
                        themeData = JSON.parse(themeDataStr);
                    } catch (e) {
                        themeData = JSON.parse(themeDataStr.replace(/&#39;/g, "'"));
                    }
                    windowManager.openThemeWindow(themeData);
                } catch (err) {
                    console.error('Failed to parse theme data:', err);
                    ui.showToast('无法打开主题详情', 'error');
                }
            }
        }
    });
}

function renderThemeCard(themeData, tag, index) {
    const theme = themeData.theme;
    const themeId = `theme-${tag}-${index}`;

    return `
        <div class="theme-card" data-theme-id="${themeId}" data-theme-data='${JSON.stringify(themeData).replace(/'/g, "&#39;")}'>
            <div class="theme-card-header">
                <div class="theme-summary">${escapeHtml(theme.summary)}</div>
                <div class="theme-meta">
                    <span class="theme-node-count">${theme.node_count} 条笔记</span>
                    <button type="button" class="theme-open-btn" data-theme-id="${themeId}">
                        打开
                    </button>
                </div>
            </div>
        </div>
    `;
}

function renderNodeCard(item, index = 0) {
    const similarityPercent = Math.round(item.similarity * 100);
    const tagsHtml = ui.renderTagsInOrder(item.tags, 'node-tag');
    // 显示排名和相似度
    const rankBadge = index > 0 ? `<span class="node-rank">#${index}</span>` : '';
    
    return `
        <div class="node-card" data-node-id="${item.id}">
            <div class="node-card-header">
                <div class="node-proposition">${escapeHtml(item.proposition)}</div>
                <div class="node-similarity">${rankBadge} ${similarityPercent}%</div>
            </div>
            <div class="node-meta">
                <div class="node-tags">${tagsHtml}</div>
                <span>${ui.formatDate(item.timestamp)}</span>
            </div>
        </div>
    `;
}

// Add Node View
let batchProcessedCount = 0;
let batchTotalCount = 0;

function toggleBatchMode() {
    state.isBatchMode = !state.isBatchMode;
    const batchBtn = document.getElementById('batchModeBtn');
    const batchText = document.getElementById('batchModeText');
    const singleMode = document.getElementById('singleEntryMode');
    const batchMode = document.getElementById('batchEntryMode');

    if (state.isBatchMode) {
        batchText.textContent = '普通模式';
        batchBtn.classList.add('active');
        singleMode.style.display = 'none';
        batchMode.style.display = 'block';
    } else {
        batchText.textContent = '批量模式';
        batchBtn.classList.remove('active');
        singleMode.style.display = 'block';
        batchMode.style.display = 'none';
    }
}

function parseBatchInput(text) {
    // Split by --- separator, filter out empty entries
    return text.split(/---/g)
        .map(s => s.trim())
        .filter(s => s.length > 0);
}

function submitNode() {
    const sourceType = document.getElementById('sourceType').value;
    const sourceTitle = document.getElementById('sourceTitle').value || null;
    const sourceLocation = document.getElementById('sourceLocation').value || null;

    if (state.isBatchMode) {
        // Batch mode
        const batchInput = document.getElementById('batchInput').value.trim();

        if (!batchInput) {
            ui.showToast('请输入内容', 'error');
            return;
        }

        const entries = parseBatchInput(batchInput);

        if (entries.length === 0) {
            ui.showToast('请输入有效内容', 'error');
            return;
        }

        // Show batch progress
        const batchProgress = document.getElementById('batchProgress');
        const batchProgressText = document.getElementById('batchProgressText');
        const batchProgressFill = document.getElementById('batchProgressFill');

        batchProgress.style.display = 'block';
        batchTotalCount = entries.length;
        batchProcessedCount = 0;

        // Add each entry to the processing queue
        entries.forEach((rawInput, index) => {
            const data = {
                raw_input: rawInput,
                source_type: sourceType,
                source_title: sourceTitle,
                source_location: sourceLocation
            };

            processingQueue.addTask(rawInput, data);

            // Update progress after each task is added
            batchProcessedCount++;
            updateBatchProgress();
        });

        // Clear batch input after processing
        document.getElementById('batchInput').value = '';
        document.getElementById('batchFileName').textContent = '';

        ui.showToast(`已添加 ${entries.length} 个任务到处理队列`);

    } else {
        // Single mode
        const rawInput = document.getElementById('rawInput').value.trim();

        if (!rawInput) {
            ui.showToast('请输入内容', 'error');
            return;
        }

        const data = {
            raw_input: rawInput,
            source_type: sourceType,
            source_title: sourceTitle,
            source_location: sourceLocation
        };

        // Add to processing queue
        processingQueue.addTask(rawInput, data);

        // Clear form immediately for next input
        document.getElementById('rawInput').value = '';
    }

    // Clear source title and location only in single mode
    if (!state.isBatchMode) {
        document.getElementById('sourceTitle').value = '';
        document.getElementById('sourceLocation').value = '';
    }
}

function updateBatchProgress() {
    const batchProgressText = document.getElementById('batchProgressText');
    const batchProgressFill = document.getElementById('batchProgressFill');

    batchProgressText.textContent = `正在处理: ${batchProcessedCount}/${batchTotalCount}`;
    const percent = batchTotalCount > 0 ? (batchProcessedCount / batchTotalCount) * 100 : 0;
    batchProgressFill.style.width = `${percent}%`;
}

// Update tag filter UI based on state.selectedTags
function updateTagFilterUI() {
    document.querySelectorAll('.tag-filter').forEach(btn => {
        const tag = btn.dataset.tag;
        if (tag === 'all') {
            btn.classList.toggle('active', state.selectedTags.length === 0);
        } else {
            btn.classList.toggle('active', state.selectedTags.includes(tag));
        }
    });
}

// Update search mode help text
function updateSearchModeHelp(mode) {
    const helpTexts = {
        strict: '精确模式：只返回与搜索词高度相关的结果（2-5个）',
        balanced: '平衡模式：返回与搜索词相关的内容，平衡精确度和召回率（5-10个）',
        explore: '探索模式：广泛发现所有可能相关的内容，包括弱关联（8-15个）'
    };
    const helpEl = document.getElementById('searchModeHelp');
    if (helpEl) {
        helpEl.textContent = helpTexts[mode] || helpTexts.balanced;
    }
}

// Stats View
async function loadStats() {
    const totalNodes = document.getElementById('totalNodes');
    const totalLinks = document.getElementById('totalLinks');
    const confirmedLinks = document.getElementById('confirmedLinks');
    const vectorCount = document.getElementById('vectorCount');
    const tagDist = document.getElementById('tagDistribution');
    
    // Show loading state
    totalNodes.textContent = '...';
    totalLinks.textContent = '...';
    confirmedLinks.textContent = '...';
    vectorCount.textContent = '...';
    tagDist.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--color-text-muted);">加载中...</div>';
    
    try {
        const stats = await api.getStats();
        
        // Check if stats data exists
        if (!stats || !stats.nodes) {
            throw new Error('统计数据格式错误');
        }
        
        document.getElementById('totalNodes').textContent = stats.nodes.total ?? 0;
        document.getElementById('totalLinks').textContent = stats.links?.total ?? 0;
        document.getElementById('confirmedLinks').textContent = stats.links?.confirmed ?? 0;
        document.getElementById('vectorCount').textContent = stats.vector_store?.total_vectors ?? 0;

        // Render tag distribution
        const tags = stats.nodes.tag_distribution || {};
        const tagEntries = Object.entries(tags);
        
        if (tagEntries.length === 0) {
            tagDist.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--color-text-muted);">暂无标签数据</div>';
        } else {
            const maxCount = Math.max(...Object.values(tags), 1);
            tagDist.innerHTML = tagEntries.map(([name, count]) => {
                const percentage = (count / maxCount) * 100;
                return `
                    <div class="tag-bar">
                        <span class="tag-bar-label">${escapeHtml(name)}</span>
                        <div class="tag-bar-track">
                            <div class="tag-bar-fill" style="width: ${percentage}%"></div>
                        </div>
                        <span class="tag-bar-value">${count}</span>
                    </div>
                `;
            }).join('');
        }

    } catch (error) {
        console.error('Load stats error:', error);
        ui.showToast(`加载统计失败: ${error.message}`, 'error');
        
        // Show error state
        totalNodes.textContent = '-';
        totalLinks.textContent = '-';
        confirmedLinks.textContent = '-';
        vectorCount.textContent = '-';
        tagDist.innerHTML = `<div style="text-align: center; padding: 20px; color: var(--color-danger);">加载失败: ${escapeHtml(error.message)}</div>`;
    }
}

// Node Detail - Open in Multi-Window System
function showNodeDetail(nodeId) {
    // Use window manager to open main window
    windowManager.openMainWindow(nodeId);
}

function showPotentialLinks(node, potentialLinks) {
    // Simplified - just log for now
    console.log('Potential links:', potentialLinks);
}

// ===== Utility Functions =====
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Render Markdown to HTML (lightweight, supports common formatting)
 */
function renderMarkdown(text) {
    if (!text) return '';

    let html = escapeHtml(text);

    // Headers: ## text -> <h3>text</h3>, ### text -> <h4>text</h4>
    // Process headers FIRST before other patterns
    html = html.replace(/^#{2}\s+(.+)$/gm, '<h3 class="md-h3">$1</h3>');
    html = html.replace(/^#{3}\s+(.+)$/gm, '<h4 class="md-h4">$1</h4>');

    // Inline code: `text` -> <code>text</code>
    // Process code before bold/italic to avoid conflicts
    html = html.replace(/`(.+?)`/g, '<code class="md-code">$1</code>');

    // Bold: **text** -> <strong>text</strong>
    // Only match when ** is preceded by whitespace/start and followed by whitespace/end/punctuation
    // This avoids matching ** in the middle of words or Chinese text
    html = html.replace(/(^|[\s\(])\*\*(.+?)\*\*([\s\)\.,;:!?]|$)/g, '$1<strong>$2</strong>$3');

    // Italic: *text* -> <em>text</em>
    // Only match single asterisks that are not part of **
    // Require whitespace/start before and whitespace/end/punctuation after
    html = html.replace(/(^|[\s\(])\*(?!\*)(.+?)(?<!\*)\*([\s\)\.,;:!?]|$)/g, '$1<em>$2</em>$3');

    // Bullet list: - text or * text at line start -> <li>text</li>
    html = html.replace(/^[-\*]\s+(.+)$/gm, '<li class="md-li">$1</li>');

    // Numbered list: 1. text -> <li class="md-li">text</li>
    html = html.replace(/^\d+\.\s+(.+)$/gm, '<li class="md-li">$1</li>');

    // Blockquote: > text -> <blockquote>text</blockquote>
    html = html.replace(/^>\s+(.+)$/gm, '<blockquote class="md-blockquote">$1</blockquote>');

    // Split into lines for processing
    const lines = html.split('\n');
    const result = [];
    let currentList = [];
    let currentParagraph = [];

    function flushParagraph() {
        if (currentParagraph.length > 0) {
            const content = currentParagraph.join('<br>');
            result.push('<p class="md-p">' + content + '</p>');
            currentParagraph = [];
        }
    }

    function flushList() {
        if (currentList.length > 0) {
            result.push('<ul class="md-ul">' + currentList.join('') + '</ul>');
            currentList = [];
        }
    }

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();

        if (!line) {
            // Empty line: flush current paragraph
            flushParagraph();
            continue;
        }

        // Check if line is a block element
        if (line.startsWith('<h3') || line.startsWith('<h4') || line.startsWith('<blockquote')) {
            flushParagraph();
            flushList();
            result.push(line);
            continue;
        }

        // Check if line is a list item
        if (line.startsWith('<li class="md-li">')) {
            flushParagraph();
            currentList.push(line);
            continue;
        }

        // Regular line: add to current paragraph
        // If previous was a list, flush it first
        if (currentList.length > 0) {
            flushList();
        }
        currentParagraph.push(line);
    }

    // Flush remaining content
    flushParagraph();
    flushList();

    return result.join('\n');
}

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
        ui.showToast('设置功能开发中...');
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

// ===== Service Worker Registration =====
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/js/sw.js')
            .then(registration => {
                console.log('SW registered:', registration);
                
                // Listen for Service Worker updates
                registration.addEventListener('updatefound', () => {
                    const newWorker = registration.installing;
                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            // New version available
                            showUpdateNotification(newWorker);
                        }
                    });
                });
            })
            .catch(error => {
                console.log('SW registration failed:', error);
            });
        
        // Listen for Service Worker messages
        navigator.serviceWorker.addEventListener('message', (event) => {
            if (event.data.type === 'SYNC_COMPLETED') {
                ui.showToast(event.data.message);
            }
        });
    });
}

// Show update notification
function showUpdateNotification(worker) {
    const toast = document.createElement('div');
    toast.className = 'toast update-toast';
    toast.innerHTML = `
        <span>新版本可用</span>
        <button class="btn-primary" style="padding: 4px 12px; font-size: 0.75rem;">刷新</button>
    `;
    toast.querySelector('button').addEventListener('click', () => {
        worker.postMessage('SKIP_WAITING');
        window.location.reload();
    });
    document.getElementById('toastContainer').appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 100);
}

// ===== PWA Install Prompt (Disabled) =====
// PWA install button functionality has been removed as requested
// The app can still be installed manually via browser menu

// Check if running as installed PWA
function isStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches ||
           window.navigator.standalone === true;
}

// ===== Network Status Monitoring =====
const networkStatus = {
    isOnline: navigator.onLine,
    wasOffline: false,
    
    init() {
        this.createStatusIndicator();
        this.bindEvents();
        this.updateStatus(navigator.onLine);
    },
    
    createStatusIndicator() {
        const indicator = document.createElement('div');
        indicator.id = 'networkStatus';
        indicator.className = 'network-status';
        indicator.innerHTML = `
            <span class="status-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                    <path d="M1 4h22M1 12h22M1 20h22"></path>
                </svg>
            </span>
            <span class="status-text">在线</span>
        `;
        indicator.style.cssText = `
            position: fixed;
            top: calc(var(--header-height) + 8px);
            left: 50%;
            transform: translateX(-50%) translateY(-40px);
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            background: rgba(0, 184, 148, 0.9);
            border-radius: 16px;
            color: white;
            font-size: 0.75rem;
            font-weight: 500;
            z-index: 99;
            opacity: 0;
            transition: all 0.3s ease;
            backdrop-filter: blur(4px);
        `;
        document.body.appendChild(indicator);
    },
    
    bindEvents() {
        window.addEventListener('online', () => {
            this.updateStatus(true);
            this.wasOffline = true;
            
            // Trigger background sync if available
            if ('serviceWorker' in navigator) {
                navigator.serviceWorker.ready.then(reg => {
                    if ('sync' in reg) {
                        reg.sync.register('sync-nodes');
                    }
                });
            }
        });
        
        window.addEventListener('offline', () => {
            this.updateStatus(false);
        });
    },
    
    updateStatus(online) {
        this.isOnline = online;
        const indicator = document.getElementById('networkStatus');
        const icon = indicator.querySelector('.status-icon');
        const text = indicator.querySelector('.status-text');
        
        if (online) {
            indicator.style.background = 'rgba(0, 184, 148, 0.9)';
            text.textContent = this.wasOffline ? '已恢复在线' : '在线';
            icon.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                    <path d="M5 12.55a11 11 0 0 1 14.08 0M1.42 9a16 16 0 0 1 21.16 0M8.53 16.11a6 6 0 0 1 6.95 0M12 20h.01"></path>
                </svg>
            `;
            
            // Auto hide after 3 seconds if coming back online
            if (this.wasOffline) {
                setTimeout(() => this.hideIndicator(), 3000);
            }
        } else {
            indicator.style.background = 'rgba(231, 76, 60, 0.9)';
            text.textContent = '离线模式';
            icon.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                    <line x1="1" y1="1" x2="23" y2="23"></line>
                    <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55M5 12.55a10.94 10.94 0 0 1 5.17-2.39M10.71 5.05A16 16 0 0 1 22.58 9M1.42 9a15.91 15.91 0 0 1 4.7-2.88M8.53 16.11a6 12 6 0 0 1 6.95 0M12 20h.01"></path>
                </svg>
            `;
            this.showIndicator();
            ui.showToast('进入离线模式，部分功能可能受限', 'warning');
        }
    },
    
    showIndicator() {
        const indicator = document.getElementById('networkStatus');
        indicator.style.opacity = '1';
        indicator.style.transform = 'translateX(-50%) translateY(0)';
    },
    
    hideIndicator() {
        const indicator = document.getElementById('networkStatus');
        indicator.style.opacity = '0';
        indicator.style.transform = 'translateX(-50%) translateY(-40px)';
    }
};

// Initialize network status monitoring
networkStatus.init();

// ===== Mobile Touch Optimizations =====
// Add touch feedback to buttons
function addTouchFeedback() {
    const style = document.createElement('style');
    style.textContent = `
        @media (hover: none) {
            button, .nav-item, .tag-filter, .node-card, .source-node-link {
                -webkit-tap-highlight-color: transparent;
            }
            
            button:active, .nav-item:active, .tag-filter:active, 
            .node-card:active, .source-node-link:active {
                transform: scale(0.97);
            }
            
            .search-btn:active {
                transform: translateY(-50%) scale(0.97);
            }
        }
        
        /* Prevent pull-to-refresh on mobile */
        body {
            overscroll-behavior-y: none;
        }
        
        /* Smooth scrolling for iOS */
        .control-panel, .content-area, .search-results {
            -webkit-overflow-scrolling: touch;
        }
    `;
    document.head.appendChild(style);
}

// Initialize touch feedback
addTouchFeedback();

// ===== Standalone Mode Detection =====
if (isStandalone()) {
    document.body.classList.add('standalone-mode');
    console.log('Running as installed PWA');
}

// ===== Splash Screen Management =====
function hideSplashScreen() {
    const splash = document.getElementById('splash-screen');
    if (splash) {
        splash.classList.add('hidden');
        setTimeout(() => {
            splash.remove();
        }, 500);
    }
}

// Hide splash screen when app is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(hideSplashScreen, 1500);
    });
} else {
    setTimeout(hideSplashScreen, 1500);
}

// ===== Mobile Gestures & Interactions =====
const mobileGestures = {
    touchStartX: 0,
    touchStartY: 0,
    touchEndX: 0,
    touchEndY: 0,
    minSwipeDistance: 50,
    
    init() {
        this.bindTouchEvents();
        // Pull to refresh has been disabled as requested
        this.setupSidebarSwipe();
    },
    
    bindTouchEvents() {
        // Prevent zoom on double tap
        let lastTouchEnd = 0;
        document.addEventListener('touchend', (e) => {
            const now = Date.now();
            if (now - lastTouchEnd <= 300) {
                e.preventDefault();
            }
            lastTouchEnd = now;
        }, { passive: false });
    },
    
    // Note: setupPullToRefresh has been removed as requested
    // The search results page no longer supports pull-to-refresh
    
    setupSidebarSwipe() {
        const controlPanel = document.getElementById('controlPanel');
        const menuToggle = document.getElementById('menuToggle');
        if (!controlPanel || !menuToggle) return;
        
        let startX = 0;
        let currentX = 0;
        let isDragging = false;
        
        // Swipe from left edge to open sidebar
        document.addEventListener('touchstart', (e) => {
            const touchX = e.touches[0].clientX;
            
            // Only trigger if touching near left edge (20px)
            if (touchX < 20 && !controlPanel.classList.contains('open')) {
                startX = touchX;
                isDragging = true;
            }
            
            // Or if sidebar is open, allow swiping to close
            if (controlPanel.classList.contains('open') && touchX > 250) {
                startX = touchX;
                isDragging = true;
            }
        }, { passive: true });
        
        document.addEventListener('touchmove', (e) => {
            if (!isDragging) return;
            
            currentX = e.touches[0].clientX;
            const diff = currentX - startX;
            
            if (!controlPanel.classList.contains('open') && diff > 0) {
                // Opening
                const translateX = Math.min(diff - 280, 0);
                controlPanel.style.transform = `translateX(${translateX}px)`;
            } else if (controlPanel.classList.contains('open') && diff < 0) {
                // Closing
                const translateX = Math.max(diff, -280);
                controlPanel.style.transform = `translateX(${translateX}px)`;
            }
        }, { passive: true });
        
        document.addEventListener('touchend', () => {
            if (!isDragging) return;
            
            const diff = currentX - startX;
            
            if (!controlPanel.classList.contains('open')) {
                // Opening
                if (diff > 100) {
                    controlPanel.classList.add('open');
                }
                controlPanel.style.transform = '';
            } else {
                // Closing
                if (diff < -100) {
                    controlPanel.classList.remove('open');
                }
                controlPanel.style.transform = '';
            }
            
            isDragging = false;
        });
    }
};

// Initialize mobile gestures on touch devices
if ('ontouchstart' in window || navigator.maxTouchPoints > 0) {
    mobileGestures.init();
}

// ===== Query Mode Switching =====
function initQueryModeSwitching() {
    const queryModeBtns = document.querySelectorAll('.query-mode-btn');
    const semanticOptions = document.getElementById('semanticSearchOptions');
    const preciseOptions = document.getElementById('preciseSearchOptions');
    const searchInput = document.getElementById('searchInput');
    const batchRefineControl = document.getElementById('batchRefineControl');

    queryModeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            queryModeBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const mode = btn.dataset.mode;
            if (mode === 'semantic') {
                semanticOptions.style.display = 'block';
                preciseOptions.style.display = 'none';
                searchInput.placeholder = '输入语义锚点...';
                if (batchRefineControl) batchRefineControl.style.display = 'none';
                // Exit batch mode if active
                if (state.batchRefineMode) toggleBatchRefineMode();
            } else {
                semanticOptions.style.display = 'none';
                preciseOptions.style.display = 'block';
                searchInput.placeholder = '输入搜索内容（可选）...';
                if (batchRefineControl) batchRefineControl.style.display = 'block';
            }
        });
    });
}

// ===== Precise Query =====
async function performPreciseSearch() {
    const searchInput = document.getElementById('searchInput');
    const propositionQuery = document.getElementById('precisePropositionQuery').value.trim();
    const rawContentQuery = document.getElementById('preciseRawContentQuery').value.trim();
    const startDate = document.getElementById('preciseStartDate').value;
    const endDate = document.getElementById('preciseEndDate').value;
    const sortBy = document.getElementById('preciseSortBy').value;
    const limit = parseInt(document.getElementById('limitSelect').value);

    const searchBtn = document.getElementById('searchBtn');
    ui.showLoading(searchBtn);

    try {
        const requestData = {
            search_mode: 'precise',
            proposition_query: propositionQuery || null,
            raw_content_query: rawContentQuery || null,
            start_date: startDate ? new Date(startDate).toISOString() : null,
            end_date: endDate ? new Date(endDate + 'T23:59:59').toISOString() : null,
            tags: state.selectedTags,
            sort_by: sortBy,
            limit: limit
        };

        const response = await api.preciseQuery(requestData);
        state.searchResults = response.results || [];  // Save results to state
        renderPreciseResults(response.results);
        ui.showToast(`找到 ${response.total} 个结果`);
    } catch (error) {
        ui.showToast(`查询失败: ${error.message}`, 'error');
        console.error('Precise search error:', error);
    } finally {
        ui.hideLoading(searchBtn);
    }
}

function renderPreciseResults(results) {
    const container = document.getElementById('searchResults');

    if (!results || results.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>未找到匹配的节点</p>
            </div>
        `;
        return;
    }

    let html = '<div class="precise-results">';

    results.forEach((item, index) => {
        const tagsHtml = ui.renderTagsInOrder(item.tags, 'node-tag');
        const isSelected = state.batchSelectedNodes.has(item.id);
        const selectedClass = isSelected ? 'batch-selected' : '';
        const statusIcon = getBatchStatusIcon(item.id);
        html += `
            <div class="node-card precise-result ${selectedClass}" data-node-id="${item.id}" style="position: relative;">
                ${statusIcon}
                <div class="node-card-header">
                    <div class="node-proposition">${escapeHtml(item.proposition)}</div>
                </div>
                <div class="node-meta">
                    <div class="node-tags">${tagsHtml}</div>
                    <span>${new Date(item.timestamp).toLocaleString('zh-CN')}</span>
                </div>
                <div class="node-actions" ${state.batchRefineMode ? 'style="display: none;"' : ''}>
                    <button class="action-btn view-btn" data-node-id="${item.id}">查看</button>
                    <button class="action-btn edit-btn" data-node-id="${item.id}">编辑</button>
                    <button class="action-btn delete-btn" data-node-id="${item.id}">删除</button>
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;

    // Normal mode: action buttons (batch mode uses event delegation on container)
    if (!state.batchRefineMode) {
        container.querySelectorAll('.view-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                showNodeDetail(btn.dataset.nodeId);
            });
        });
        container.querySelectorAll('.edit-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                openEditModal(btn.dataset.nodeId);
            });
        });
        container.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                openDeleteModal(btn.dataset.nodeId);
            });
        });
    }
}

function getBatchStatusIcon(nodeId) {
    // First check state for persistent status
    const status = state.batchProgress.nodeStatus[nodeId];
    if (status) {
        const iconMap = {
            success: { class: 'success', text: '✓' },
            error: { class: 'error', text: '✗' },
            processing: { class: 'processing', text: '⟳' }
        };
        const icon = iconMap[status];
        if (icon) {
            return `<div class="batch-status-icon ${icon.class}" data-node-id="${nodeId}">${icon.text}</div>`;
        }
    }

    // Fallback to existing DOM element
    const iconEl = document.querySelector(`.batch-status-icon[data-node-id="${nodeId}"]`);
    if (!iconEl) return '';
    return iconEl.outerHTML;
}

function toggleNodeSelection(nodeId) {
    if (state.batchSelectedNodes.has(nodeId)) {
        state.batchSelectedNodes.delete(nodeId);
    } else {
        state.batchSelectedNodes.add(nodeId);
    }
    updateBatchUI();
    renderPreciseResults(state.searchResults);
}

function updateBatchUI() {
    const count = state.batchSelectedNodes.size;
    const countEl = document.getElementById('batchSelectedCount');
    const confirmBtn = document.getElementById('batchRefineConfirmBtn');
    
    if (countEl) countEl.textContent = `已选择 ${count} 个节点`;
    if (confirmBtn) confirmBtn.disabled = count === 0;
}

function toggleBatchRefineMode() {
    state.batchRefineMode = !state.batchRefineMode;
    const toolbar = document.getElementById('batchRefineToolbar');
    const toggleBtn = document.getElementById('batchRefineToggleBtn');

    if (state.batchRefineMode) {
        toolbar.style.display = 'flex';
        if (toggleBtn) toggleBtn.classList.add('active');
        ui.showToast('批量模式：点击节点进行选择');
    } else {
        toolbar.style.display = 'none';
        if (toggleBtn) toggleBtn.classList.remove('active');
        state.batchSelectedNodes.clear();
        updateBatchUI();
        // Note: We no longer clear status icons here
        // They persist until page refresh or new search
    }

    // Re-render results if available
    if (state.searchResults && state.searchResults.length > 0) {
        renderPreciseResults(state.searchResults);
    }
}

async function confirmBatchRefine() {
    if (state.batchSelectedNodes.size === 0 || state.batchProcessing) return;

    state.batchProcessing = true;
    const confirmBtn = document.getElementById('batchRefineConfirmBtn');
    if (confirmBtn) confirmBtn.disabled = true;

    const nodeIds = Array.from(state.batchSelectedNodes);
    const total = nodeIds.length;

    // Initialize progress tracking
    state.batchProgress = {
        total: total,
        completed: 0,
        failed: 0,
        nodeStatus: {}
    };

    ui.showToast(`开始批量生成，共 ${total} 个节点...`);

    // Mark all as processing and start parallel requests
    nodeIds.forEach(nodeId => {
        state.batchProgress.nodeStatus[nodeId] = 'processing';
        setNodeStatus(nodeId, 'processing');
    });

    // Process all nodes in parallel
    const promises = nodeIds.map(nodeId =>
        fetch(`/api/v1/nodes/${nodeId}/refine`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(response => {
            if (!response.ok) throw new Error('生成失败');
            return { nodeId, success: true };
        })
        .catch(error => {
            console.error(`Batch refine error for ${nodeId}:`, error);
            return { nodeId, success: false, error };
        })
    );

    // Wait for all to complete
    const results = await Promise.allSettled(promises);

    // Update status based on results
    results.forEach((result, index) => {
        const nodeId = nodeIds[index];
        if (result.status === 'fulfilled' && result.value.success) {
            state.batchProgress.nodeStatus[nodeId] = 'success';
            state.batchProgress.completed++;
            setNodeStatus(nodeId, 'success');
        } else {
            state.batchProgress.nodeStatus[nodeId] = 'error';
            state.batchProgress.failed++;
            setNodeStatus(nodeId, 'error');
        }
    });

    state.batchProcessing = false;
    if (confirmBtn) confirmBtn.disabled = false;

    const { completed, failed } = state.batchProgress;
    ui.showToast(`批量生成完成: ${completed} 成功, ${failed} 失败`);

    // Clear selection after completion
    state.batchSelectedNodes.clear();
    updateBatchUI();
}

function setNodeStatus(nodeId, status) {
    const card = document.querySelector(`.node-card[data-node-id="${nodeId}"]`);
    if (!card) return;
    
    // Remove existing status icon
    const existingIcon = card.querySelector('.batch-status-icon');
    if (existingIcon) existingIcon.remove();
    
    // Add new status icon
    const iconMap = {
        success: { class: 'success', text: '✓' },
        error: { class: 'error', text: '✗' },
        processing: { class: 'processing', text: '⟳' }
    };
    
    const icon = iconMap[status];
    if (icon) {
        const iconEl = document.createElement('div');
        iconEl.className = `batch-status-icon ${icon.class}`;
        iconEl.textContent = icon.text;
        iconEl.dataset.nodeId = nodeId;
        card.appendChild(iconEl);
    }
}

// ===== Node Editing =====
let currentEditingNodeId = null;

async function openEditModal(nodeId) {
    try {
        const response = await api.getNode(nodeId);
        const node = response.node;
        currentEditingNodeId = nodeId;

        document.getElementById('editProposition').value = node.processed.proposition;
        document.getElementById('editRawInput').value = node.raw_input;
        document.getElementById('editSourceTitle').value = node.source.title || '';
        document.getElementById('editSourceLocation').value = node.source.location || '';
        document.getElementById('editOpenQuestions').value = (node.processed.open_questions || []).join('\n');

        // Set tags
        document.querySelectorAll('#editTags input[type="checkbox"]').forEach(cb => {
            cb.checked = node.tags.includes(cb.value);
        });

        document.getElementById('nodeEditModal').style.display = 'flex';
    } catch (error) {
        ui.showToast(`加载节点失败: ${error.message}`, 'error');
    }
}

function closeEditModal() {
    document.getElementById('nodeEditModal').style.display = 'none';
    currentEditingNodeId = null;
}

async function saveNodeEdit() {
    if (!currentEditingNodeId) return;

    const tags = Array.from(document.querySelectorAll('#editTags input[type="checkbox"]:checked')).map(cb => cb.value);
    const openQuestions = document.getElementById('editOpenQuestions').value.split('\n').filter(q => q.trim());

    const data = {
        proposition: document.getElementById('editProposition').value.trim(),
        raw_input: document.getElementById('editRawInput').value.trim(),
        tags: tags,
        open_questions: openQuestions,
        source_title: document.getElementById('editSourceTitle').value.trim() || null,
        source_location: document.getElementById('editSourceLocation').value.trim() || null
    };

    try {
        const response = await api.updateNode(currentEditingNodeId, data);
        ui.showToast('节点已更新');
        closeEditModal();

        // Refresh display if the node is currently shown
        refreshNodeDisplay(currentEditingNodeId, response.node);
    } catch (error) {
        ui.showToast(`更新失败: ${error.message}`, 'error');
    }
}

function refreshNodeDisplay(nodeId, node) {
    // Update in search results if present
    const card = document.querySelector(`[data-node-id="${nodeId}"]`);
    if (card) {
        const propEl = card.querySelector('.node-proposition');
        if (propEl) propEl.textContent = node.processed.proposition;
    }

    // Update in modal if open
    if (windowManager.windows.some(w => w.nodeId === nodeId)) {
        const windowObj = windowManager.windows.find(w => w.nodeId === nodeId);
        if (windowObj) {
            windowManager.loadWindowContent(windowObj);
        }
    }
}

// ===== Node Deletion =====
let currentDeletingNodeId = null;

async function openDeleteModal(nodeId) {
    try {
        const response = await api.getNode(nodeId);
        const node = response.node;
        currentDeletingNodeId = nodeId;

        document.getElementById('deleteNodeTitle').textContent = node.processed.proposition;
        document.getElementById('deleteConfirmModal').style.display = 'flex';
    } catch (error) {
        ui.showToast(`加载节点失败: ${error.message}`, 'error');
    }
}

function closeDeleteModal() {
    document.getElementById('deleteConfirmModal').style.display = 'none';
    currentDeletingNodeId = null;
}

async function confirmDeleteNode() {
    if (!currentDeletingNodeId) return;

    try {
        await api.deleteNode(currentDeletingNodeId);
        ui.showToast('节点已删除');
        closeDeleteModal();

        // Remove from display
        const card = document.querySelector(`[data-node-id="${currentDeletingNodeId}"]`);
        if (card) card.remove();

        // Close modal if open
        if (windowManager.windows.some(w => w.nodeId === currentDeletingNodeId)) {
            const windowObj = windowManager.windows.find(w => w.nodeId === currentDeletingNodeId);
            if (windowObj) {
                windowManager.closeWindow(windowObj.id);
            }
        }
    } catch (error) {
        ui.showToast(`删除失败: ${error.message}`, 'error');
    }
}

// ===== Backup Management =====
const backupManager = {
    pendingRestoreName: null,
    pendingDeleteName: null,

    async loadBackups() {
        try {
            const response = await api.getBackups();
            this.renderBackups(response.backups);
        } catch (error) {
            console.error('Failed to load backups:', error);
            document.getElementById('backupList').innerHTML = '<p style="color: var(--color-text-muted);">加载备份列表失败</p>';
        }
    },

    renderBackups(backups) {
        const container = document.getElementById('backupList');
        if (!backups || backups.length === 0) {
            container.innerHTML = '<p style="color: var(--color-text-muted);">暂无备份</p>';
            return;
        }

        // Store backups data for reference
        this.backupsData = backups;

        container.innerHTML = backups.map((backup, index) => {
            return `
            <div class="backup-item" style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px;
                background: var(--color-bg-tertiary);
                border-radius: 8px;
                margin-bottom: 8px;
            " data-backup-index="${index}">
                <div class="backup-info">
                    <div style="font-weight: 500;">${escapeHtml(backup.name)}</div>
                    <div style="font-size: 0.75rem; color: var(--color-text-muted);">
                        ${new Date(backup.created_at).toLocaleString('zh-CN')} · ${backup.node_count} 个节点 · ${backup.size_mb} MB
                    </div>
                </div>
                <div class="backup-actions" style="display: flex; gap: 8px;">
                    <button class="btn-secondary btn-sm backup-download-btn" data-backup-index="${index}">下载</button>
                    <button class="btn-secondary btn-sm backup-restore-btn" data-backup-index="${index}">恢复</button>
                    <button class="btn-danger btn-sm backup-delete-btn" data-backup-index="${index}">删除</button>
                </div>
            </div>
        `}).join('');

        // Attach event listeners after rendering
        this.attachBackupEventListeners();
    },

    attachBackupEventListeners() {
        const container = document.getElementById('backupList');

        // Download buttons
        container.querySelectorAll('.backup-download-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                // Use currentTarget to get the button element, not the clicked child
                const button = e.currentTarget;
                const index = parseInt(button.dataset.backupIndex);
                const backup = this.backupsData[index];
                if (backup) {
                    console.log('[Backup] Download:', backup.name, 'Index:', index);
                    this.downloadBackup(backup.name);
                } else {
                    console.error('[Backup] Download failed - no backup at index:', index);
                }
            });
        });

        // Restore buttons - open confirm modal
        container.querySelectorAll('.backup-restore-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const button = e.currentTarget;
                const index = parseInt(button.dataset.backupIndex);
                const backup = this.backupsData[index];
                if (backup) {
                    console.log('[Backup] Restore:', backup.name, 'Index:', index);
                    this.openRestoreModal(backup.name);
                } else {
                    console.error('[Backup] Restore failed - no backup at index:', index);
                }
            });
        });

        // Delete buttons - open confirm modal
        container.querySelectorAll('.backup-delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const button = e.currentTarget;
                const index = parseInt(button.dataset.backupIndex);
                const backup = this.backupsData[index];
                if (backup) {
                    console.log('[Backup] Delete:', backup.name, 'Index:', index);
                    this.openDeleteModal(backup.name);
                } else {
                    console.error('[Backup] Delete failed - no backup at index:', index);
                }
            });
        });
    },

    openRestoreModal(backupName) {
        this.pendingRestoreName = backupName;
        document.getElementById('restoreBackupName').textContent = backupName;
        document.getElementById('backupRestoreModal').style.display = 'flex';
    },

    closeRestoreModal() {
        document.getElementById('backupRestoreModal').style.display = 'none';
        this.pendingRestoreName = null;
    },

    async confirmRestoreBackup() {
        if (!this.pendingRestoreName) return;

        // Save the name before closing modal (which clears it)
        const backupName = this.pendingRestoreName;
        console.log('[Backup] Confirm restore:', backupName);

        try {
            ui.showToast('正在恢复备份...');
            this.closeRestoreModal();
            await api.restoreBackup(backupName, true);
            ui.showToast('备份恢复成功，页面将刷新');
            setTimeout(() => window.location.reload(), 1500);
        } catch (error) {
            ui.showToast(`恢复备份失败: ${error.message}`, 'error');
        }
    },

    openDeleteModal(backupName) {
        this.pendingDeleteName = backupName;
        document.getElementById('deleteBackupName').textContent = backupName;
        document.getElementById('backupDeleteModal').style.display = 'flex';
    },

    closeDeleteModal() {
        document.getElementById('backupDeleteModal').style.display = 'none';
        this.pendingDeleteName = null;
    },

    async confirmDeleteBackup() {
        if (!this.pendingDeleteName) return;

        // Save the name before closing modal (which clears it)
        const backupName = this.pendingDeleteName;
        console.log('[Backup] Confirm delete:', backupName);

        try {
            this.closeDeleteModal();
            await api.deleteBackup(backupName);
            ui.showToast('备份已删除');
            await this.loadBackups();
        } catch (error) {
            ui.showToast(`删除备份失败: ${error.message}`, 'error');
        }
    },

    async createBackup() {
        try {
            const btn = document.getElementById('createBackupBtn');
            ui.showLoading(btn, '创建中...');
            const response = await api.createBackup();
            ui.showToast('备份创建成功');
            await this.loadBackups();
        } catch (error) {
            ui.showToast(`创建备份失败: ${error.message}`, 'error');
        } finally {
            const btn = document.getElementById('createBackupBtn');
            ui.hideLoading(btn);
        }
    },

    downloadBackup(backupName) {
        window.open(`${api.baseURL}/api/v1/backups/${encodeURIComponent(backupName)}/download`);
    },

    async importBackup(file) {
        if (!file) {
            ui.showToast('请选择备份文件', 'error');
            return;
        }

        if (!file.name.endsWith('.zip')) {
            ui.showToast('请选择 .zip 格式的备份文件', 'error');
            return;
        }

        try {
            ui.showToast('正在上传备份文件...');
            await api.uploadBackup(file);
            ui.showToast('备份导入成功');
            await this.loadBackups();
        } catch (error) {
            ui.showToast(`导入备份失败: ${error.message}`, 'error');
        }
    }
};

// ===== API Client Extensions =====
APIClient.prototype.preciseQuery = async function(data) {
    return this.request('/api/v1/query/precise', {
        method: 'POST',
        body: data
    });
};

APIClient.prototype.updateNode = async function(id, data) {
    return this.request(`/api/v1/nodes/${id}`, {
        method: 'PUT',
        body: data
    });
};

APIClient.prototype.getBackups = async function() {
    return this.request('/api/v1/backups');
};

APIClient.prototype.createBackup = async function() {
    return this.request('/api/v1/backups', { method: 'POST' });
};

APIClient.prototype.restoreBackup = async function(name, confirm = false) {
    return this.request(`/api/v1/backups/${encodeURIComponent(name)}/restore`, {
        method: 'POST',
        body: { confirm }
    });
};

APIClient.prototype.deleteBackup = async function(name) {
    return this.request(`/api/v1/backups/${encodeURIComponent(name)}`, { method: 'DELETE' });
};

APIClient.prototype.uploadBackup = async function(file) {
    const url = `${this.baseURL}/api/v1/backups/upload`;
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(url, {
        method: 'POST',
        body: formData
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: '上传失败' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
};

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

    // Search button behavior is already bound in initApp
    // We just need to update the handleSearch function to support query mode switching

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
});

// ===== Navigation Helpers =====
function showNodeDetailView(nodeId) {
    ui.switchView('nodeDetailView', { nodeId });
}

function showThemeDetailView(themeId) {
    ui.switchView('themeDetailView', { themeId });
}

// ===== Viewport Height Fix for Mobile Browsers =====
function setViewportHeight() {
    const vh = window.innerHeight * 0.01;
    document.documentElement.style.setProperty('--vh', `${vh}px`);
}

setViewportHeight();
window.addEventListener('resize', setViewportHeight);
window.addEventListener('orientationchange', setViewportHeight);

// ===== Prevent iOS Rubber Band Effect =====
if (/iPad|iPhone|iPod/.test(navigator.userAgent)) {
    document.body.addEventListener('touchmove', (e) => {
        if (e.target === document.body) {
            e.preventDefault();
        }
    }, { passive: false });
}

// ===== Haptic Feedback (on supported devices) =====
function hapticFeedback(type = 'light') {
    if ('vibrate' in navigator) {
        const patterns = {
            light: [10],
            medium: [20],
            heavy: [30],
            success: [10, 50, 10],
            error: [50, 100, 50]
        };
        navigator.vibrate(patterns[type] || patterns.light);
    }
}

// Add haptic feedback to buttons
if ('ontouchstart' in window) {
    document.addEventListener('click', (e) => {
        if (e.target.closest('button, .nav-item, .node-card, .tag-filter')) {
            hapticFeedback('light');
        }
    });
}

// ===== Keyboard handling for mobile =====
if ('virtualKeyboard' in navigator) {
    navigator.virtualKeyboard.overlaysContent = true;
}

// Adjust layout when keyboard appears
window.addEventListener('resize', () => {
    const isKeyboardOpen = window.innerHeight < window.outerHeight * 0.8;
    document.body.classList.toggle('keyboard-open', isKeyboardOpen);
});

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
