/**
 * Rhizome Thinking - Multi-Window Manager
 */

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
