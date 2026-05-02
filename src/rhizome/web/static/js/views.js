/**
 * Rhizome Thinking - Visualization Views Module
 * Contains Outline View, Epistemic Map, and Graph View implementations
 */

// ===== Outline View (大纲视图) =====
const outlineView = {
    currentSort: 'time',
    
    async init() {
        this.bindEvents();
        await this.loadOutline();
    },
    
    bindEvents() {
        const sortSelect = document.getElementById('outlineSort');
        const refreshBtn = document.getElementById('refreshOutline');
        
        if (sortSelect) {
            sortSelect.addEventListener('change', (e) => {
                this.currentSort = e.target.value;
                this.loadOutline();
            });
        }
        
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadOutline());
        }
    },
    
    async loadOutline() {
        const contentEl = document.getElementById('outlineContent');
        const totalEl = document.getElementById('outlineTotal');
        const isolatedEl = document.getElementById('outlineIsolated');
        const highConnEl = document.getElementById('outlineHighConn');
        
        if (!contentEl) return;
        
        contentEl.innerHTML = '<div class="empty-state"><p>加载中...</p></div>';
        
        try {
            const response = await fetch(`/api/v1/outline?sort_by=${this.currentSort}`);
            if (!response.ok) throw new Error('加载失败');
            
            const data = await response.json();
            
            // Update stats
            if (totalEl) totalEl.textContent = data.stats.total_nodes;
            if (isolatedEl) isolatedEl.textContent = data.stats.isolated_nodes;
            if (highConnEl) highConnEl.textContent = data.stats.high_connection_nodes;
            
            // Render content
            if (data.months.length === 0) {
                contentEl.innerHTML = `
                    <div class="empty-state">
                        <p>暂无节点</p>
                    </div>
                `;
                return;
            }
            
            let html = '';
            data.months.forEach(month => {
                html += `
                    <div class="outline-month">
                        <div class="outline-month-header">
                            <span>${month.display_name}</span>
                            <span class="outline-month-count">${month.node_count} 个节点</span>
                        </div>
                `;
                
                month.nodes.forEach(node => {
                    const tagColors = {
                        'definitive': '#00b894',
                        'inferred': '#a29bfe',
                        'vague': '#fdcb6e',
                        'needs_thinking': '#e74c3c',
                        'cross-domain': '#00cec9'
                    };
                    const primaryTag = node.tags[0] || 'vague';
                    const tagColor = tagColors[primaryTag] || '#95a5a6';
                    
                    const isolatedClass = node.is_isolated ? 'isolated' : '';
                    const highConnClass = node.link_count >= 3 ? 'high-connections' : '';
                    
                    html += `
                        <div class="outline-node ${isolatedClass} ${highConnClass}" data-node-id="${node.id}">
                            <div class="outline-node-content">
                                <div class="outline-node-text">${this.escapeHtml(node.proposition)}</div>
                                <div class="outline-node-meta">
                                    <span style="color: ${tagColor}">${this.getTagName(primaryTag)}</span>
                                    <span class="outline-node-links">
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                                            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                                        </svg>
                                        ${node.link_count}
                                    </span>
                                    <span>${new Date(node.timestamp).toLocaleDateString('zh-CN')}</span>
                                </div>
                            </div>
                        </div>
                    `;
                });
                
                html += '</div>';
            });
            
            contentEl.innerHTML = html;
            
            // Add click handlers
            contentEl.querySelectorAll('.outline-node').forEach(nodeEl => {
                nodeEl.addEventListener('click', () => {
                    const nodeId = nodeEl.dataset.nodeId;
                    if (window.windowManager) {
                        window.windowManager.openMainWindow(nodeId);
                    }
                });
            });
            
        } catch (error) {
            console.error('Outline view error:', error);
            contentEl.innerHTML = `
                <div class="empty-state">
                    <p style="color: var(--color-danger)">加载失败: ${error.message}</p>
                </div>
            `;
        }
    },
    
    getTagName(tag) {
        const names = {
            'definitive': '明确结论',
            'inferred': '推断结论',
            'vague': '模糊感知',
            'needs_thinking': '待思考',
            'cross-domain': '跨域连接'
        };
        return names[tag] || tag;
    },
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// ===== Epistemic Map (认知地图) =====
const epistemicMapView = {
    cy: null,
    
    async init() {
        this.bindEvents();
        await this.loadMap();
    },
    
    bindEvents() {
        const refreshBtn = document.getElementById('refreshEpistemicMap');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadMap());
        }
        
        // Handle window resize
        window.addEventListener('resize', () => {
            if (this.cy) {
                this.cy.resize();
                this.cy.fit();
            }
        });
    },
    
    async loadMap() {
        const container = document.getElementById('epistemicMapCanvas');
        if (!container) return;
        
        container.innerHTML = '<div class="empty-state"><p>加载中...</p></div>';
        
        try {
            const response = await fetch('/api/v1/epistemic-map');
            if (!response.ok) throw new Error('加载失败');
            
            const data = await response.json();
            
            if (data.nodes.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <p>暂无节点</p>
                    </div>
                `;
                return;
            }
            
            // Clear container
            container.innerHTML = '';
            
            // Prepare Cytoscape elements
            const elements = data.nodes.map(node => ({
                data: {
                    id: node.id,
                    label: node.proposition.substring(0, 80) + (node.proposition.length > 80 ? '...' : ''),
                    fullText: node.proposition,
                    tag: node.tags[0] || 'vague',
                    linkCount: node.link_count,
                    clusterName: node.cluster_name
                },
                position: {
                    x: node.x * 800,
                    y: (1 - node.y) * 500  // Flip Y so high certainty is at top
                }
            }));
            
            // Initialize Cytoscape
            this.cy = cytoscape({
                container: container,
                elements: elements,
                style: [
                    {
                        selector: 'node',
                        style: {
                            'background-color': ele => this.getTagColor(ele.data('tag')),
                            'width': 15,
                            'height': 15,
                            'label': 'data(label)',
                            'font-size': '10px',
                            'color': '#e8e8f0',
                            'text-background-color': '#1a1a2e',
                            'text-background-opacity': 0.8,
                            'text-background-padding': '2px',
                            'text-valign': 'bottom',
                            'text-halign': 'center',
                            'text-margin-y': 5
                        }
                    }
                ],
                layout: {
                    name: 'preset'
                },
                minZoom: 0.3,
                maxZoom: 3,
                wheelSensitivity: 0.3
            });
            
            // Add interaction
            this.cy.on('tap', 'node', (evt) => {
                const node = evt.target;
                const nodeId = node.id();
                if (window.windowManager) {
                    window.windowManager.openMainWindow(nodeId);
                }
            });
            
            // Add tooltip on hover
            this.cy.on('mouseover', 'node', (evt) => {
                const node = evt.target;
                node.animate({
                    style: { 'width': 20, 'height': 20 }
                }, { duration: 200 });
            });
            
            this.cy.on('mouseout', 'node', (evt) => {
                const node = evt.target;
                node.animate({
                    style: { 'width': 15, 'height': 15 }
                }, { duration: 200 });
            });
            
            // Fit to view
            this.cy.fit(50);
            
        } catch (error) {
            console.error('Epistemic map error:', error);
            container.innerHTML = `
                <div class="empty-state">
                    <p style="color: var(--color-danger)">加载失败: ${error.message}</p>
                </div>
            `;
        }
    },
    
    getTagColor(tag) {
        const colors = {
            'definitive': '#00b894',
            'inferred': '#a29bfe',
            'vague': '#fdcb6e',
            'needs_thinking': '#e74c3c',
            'cross-domain': '#00cec9'
        };
        return colors[tag] || '#95a5a6';
    },
    
    destroy() {
        if (this.cy) {
            this.cy.destroy();
            this.cy = null;
        }
    }
};

// ===== Graph View (关系图) =====
const graphView = {
    cy: null,
    
    async init() {
        this.bindEvents();
        await this.loadGraph();
    },
    
    bindEvents() {
        const filterSelect = document.getElementById('graphFilter');
        const relationSelect = document.getElementById('graphRelationFilter');
        const refreshBtn = document.getElementById('refreshGraph');
        
        const reload = () => this.loadGraph();
        
        if (filterSelect) filterSelect.addEventListener('change', reload);
        if (relationSelect) relationSelect.addEventListener('change', reload);
        if (refreshBtn) refreshBtn.addEventListener('click', reload);
        
        // Handle window resize
        window.addEventListener('resize', () => {
            if (this.cy) {
                this.cy.resize();
            }
        });
    },
    
    async loadGraph() {
        const container = document.getElementById('graphCanvas');
        if (!container) return;
        
        const filterSelect = document.getElementById('graphFilter');
        const relationSelect = document.getElementById('graphRelationFilter');
        
        const includeUnconfirmed = filterSelect?.value === 'all';
        const relationFilter = relationSelect?.value || '';
        
        container.innerHTML = '<div class="empty-state"><p>加载中...</p></div>';
        
        try {
            let url = `/api/v1/graph?include_unconfirmed=${includeUnconfirmed}`;
            if (relationFilter) {
                url += `&relation_filter=${relationFilter}`;
            }
            
            const response = await fetch(url);
            if (!response.ok) throw new Error('加载失败');
            
            const data = await response.json();
            
            if (data.nodes.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <p>暂无节点</p>
                    </div>
                `;
                return;
            }
            
            // Clear container
            container.innerHTML = '';
            
            // Prepare elements
            const elements = [];
            
            // Add nodes
            data.nodes.forEach(node => {
                elements.push({
                    data: {
                        id: node.id,
                        label: node.label,
                        fullText: node.full_text,
                        color: node.is_isolated ? '#bdc3c7' : node.tag_color
                    }
                });
            });
            
            // Add edges
            data.edges.forEach(edge => {
                elements.push({
                    data: {
                        id: `${edge.source}-${edge.target}`,
                        source: edge.source,
                        target: edge.target,
                        relationName: edge.relation_name,
                        strength: edge.strength,
                        width: edge.width,
                        color: edge.color
                    }
                });
            });
            
            // Initialize Cytoscape
            this.cy = cytoscape({
                container: container,
                elements: elements,
                style: [
                    {
                        selector: 'node',
                        style: {
                            'background-color': 'data(color)',
                            'width': ele => ele.degree() > 0 ? 15 + Math.min(ele.degree() * 2, 15) : 12,
                            'height': ele => ele.degree() > 0 ? 15 + Math.min(ele.degree() * 2, 15) : 12,
                            'label': 'data(label)',
                            'font-size': '9px',
                            'color': '#e8e8f0',
                            'text-background-color': '#1a1a2e',
                            'text-background-opacity': 0.8,
                            'text-background-padding': '2px',
                            'text-valign': 'bottom',
                            'text-halign': 'center',
                            'text-margin-y': 5,
                            'border-width': 1,
                            'border-color': '#2d2d44'
                        }
                    },
                    {
                        selector: 'edge',
                        style: {
                            'width': 'data(width)',
                            'line-color': 'data(color)',
                            'target-arrow-color': 'data(color)',
                            'target-arrow-shape': 'triangle',
                            'curve-style': 'bezier',
                            'label': 'data(relationName)',
                            'font-size': '8px',
                            'color': '#a0a0b0',
                            'text-background-color': '#1a1a2e',
                            'text-background-opacity': 0.9,
                            'text-background-padding': '2px',
                            'arrow-scale': 0.8
                        }
                    }
                ],
                layout: {
                    name: 'cose',
                    padding: 20,
                    nodeRepulsion: 400000,
                    edgeElasticity: 100,
                    nestingFactor: 5,
                    gravity: 80,
                    numIter: 1000,
                    initialTemp: 200,
                    coolingFactor: 0.95,
                    minTemp: 1.0
                },
                minZoom: 0.2,
                maxZoom: 3,
                wheelSensitivity: 0.3
            });
            
            // Add interactions
            this.cy.on('tap', 'node', (evt) => {
                const node = evt.target;
                const nodeId = node.id();
                if (window.windowManager) {
                    window.windowManager.openMainWindow(nodeId);
                }
            });
            
            // Highlight on hover
            this.cy.on('mouseover', 'node', (evt) => {
                const node = evt.target;
                node.neighborhood().edges().animate({
                    style: { 'line-opacity': 1, 'width': ele => ele.data('width') * 1.5 }
                }, { duration: 200 });
            });
            
            this.cy.on('mouseout', 'node', (evt) => {
                const node = evt.target;
                node.neighborhood().edges().animate({
                    style: { 'line-opacity': 0.6, 'width': 'data(width)' }
                }, { duration: 200 });
            });
            
            // Set initial edge opacity
            this.cy.edges().style('line-opacity', 0.6);
            
        } catch (error) {
            console.error('Graph view error:', error);
            container.innerHTML = `
                <div class="empty-state">
                    <p style="color: var(--color-danger)">加载失败: ${error.message}</p>
                </div>
            `;
        }
    },
    
    destroy() {
        if (this.cy) {
            this.cy.destroy();
            this.cy = null;
        }
    }
};

// ===== Relationship Manager (关系管理 - 待确认建议) =====
const relationshipManagerView = {
    suggestions: [],
    currentPage: 1,
    pageSize: 10,
    totalPages: 1,
    currentFilter: 'all',

    async init() {
        this.bindEvents();
        await this.loadSuggestions();
    },

    bindEvents() {
        const refreshBtn = document.getElementById('refreshSuggestions');
        const filterSelect = document.getElementById('suggestionFilter');
        const prevBtn = document.getElementById('prevPage');
        const nextBtn = document.getElementById('nextPage');

        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadSuggestions());
        }
        if (filterSelect) {
            filterSelect.addEventListener('change', (e) => {
                this.currentFilter = e.target.value;
                this.currentPage = 1;
                this.loadSuggestions();
            });
        }
        if (prevBtn) {
            prevBtn.addEventListener('click', () => this.goToPage(this.currentPage - 1));
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.goToPage(this.currentPage + 1));
        }
    },

    async loadSuggestions() {
        const contentEl = document.getElementById('suggestionsContent');
        const statsEl = document.getElementById('suggestionsStats');

        if (!contentEl) return;

        contentEl.innerHTML = '<div class="empty-state"><p>加载中...</p></div>';

        try {
            const response = await fetch('/api/v1/graph?include_unconfirmed=true');
            if (!response.ok) throw new Error('加载失败');

            const data = await response.json();

            // 筛选未确认的连接建议
            this.suggestions = data.edges.filter(edge => !edge.confirmed) || [];

            // 更新统计
            if (statsEl) {
                statsEl.innerHTML = `
                    <span>待确认: <strong>${this.suggestions.length}</strong></span>
                    <span>当前页: <strong>${this.currentPage}</strong>/${this.totalPages}</span>
                `;
            }

            // 计算总页数
            this.totalPages = Math.ceil(this.suggestions.length / this.pageSize) || 1;

            if (this.suggestions.length === 0) {
                contentEl.innerHTML = `
                    <div class="empty-state">
                        <p>暂无待确认的关系建议</p>
                    </div>
                `;
                this.updatePagination();
                return;
            }

            this.renderSuggestions();

        } catch (error) {
            console.error('Relationship manager error:', error);
            contentEl.innerHTML = `
                <div class="empty-state">
                    <p style="color: var(--color-danger)">加载失败: ${error.message}</p>
                </div>
            `;
        }
    },

    renderSuggestions() {
        const contentEl = document.getElementById('suggestionsContent');

        // 分页
        const start = (this.currentPage - 1) * this.pageSize;
        const end = start + this.pageSize;
        const pageSuggestions = this.suggestions.slice(start, end);

        let html = '<div class="suggestions-list">';

        pageSuggestions.forEach((suggestion, index) => {
            const relationTypeName = this.getRelationTypeName(suggestion.relation_type);
            const confidenceColor = this.getConfidenceColor(suggestion.confidence || suggestion.strength);
            const strengthPercent = Math.round((suggestion.strength || 0) * 100);

            html += `
                <div class="suggestion-card" data-source="${suggestion.source}" data-target="${suggestion.target}">
                    <div class="suggestion-header">
                        <span class="suggestion-type" style="background: ${this.getRelationColor(suggestion.relation_type)}">
                            ${relationTypeName}
                        </span>
                        <span class="suggestion-confidence" style="color: ${confidenceColor}">
                            置信度: ${Math.round((suggestion.confidence || suggestion.strength || 0) * 100)}%
                        </span>
                    </div>
                    <div class="suggestion-nodes">
                        <div class="suggestion-node source">
                            <span class="node-label">来源</span>
                            <span class="node-text">${this.escapeHtml(suggestion.source_text || suggestion.source)}</span>
                        </div>
                        <div class="suggestion-arrow">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="5" y1="12" x2="19" y2="12"></line>
                                <polyline points="12 5 19 12 12 19"></polyline>
                            </svg>
                        </div>
                        <div class="suggestion-node target">
                            <span class="node-label">目标</span>
                            <span class="node-text">${this.escapeHtml(suggestion.target_text || suggestion.target)}</span>
                        </div>
                    </div>
                    <div class="suggestion-meta">
                        <div class="suggestion-strength">
                            <span>关联强度:</span>
                            <div class="strength-bar">
                                <div class="strength-fill" style="width: ${strengthPercent}%; background: ${confidenceColor}"></div>
                            </div>
                            <span>${strengthPercent}%</span>
                        </div>
                        ${suggestion.reason ? `
                            <div class="suggestion-reason">
                                <span>原因:</span>
                                <p>${this.escapeHtml(suggestion.reason)}</p>
                            </div>
                        ` : ''}
                    </div>
                    <div class="suggestion-actions">
                        <button class="btn-confirm" onclick="relationshipManagerView.confirmLink('${suggestion.source}', '${suggestion.target}')">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="20 6 9 17 4 12"></polyline>
                            </svg>
                            确认
                        </button>
                        <button class="btn-reject" onclick="relationshipManagerView.rejectLink('${suggestion.source}', '${suggestion.target}')">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="18" y1="6" x2="6" y2="18"></line>
                                <line x1="6" y1="6" x2="18" y2="18"></line>
                            </svg>
                            拒绝
                        </button>
                        <button class="btn-view-source" onclick="relationshipManagerView.viewNode('${suggestion.source}')">
                            查看来源
                        </button>
                        <button class="btn-view-target" onclick="relationshipManagerView.viewNode('${suggestion.target}')">
                            查看目标
                        </button>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        contentEl.innerHTML = html;

        this.updatePagination();
    },

    updatePagination() {
        const prevBtn = document.getElementById('prevPage');
        const nextBtn = document.getElementById('nextPage');
        const pageInfo = document.getElementById('pageInfo');

        if (prevBtn) {
            prevBtn.disabled = this.currentPage <= 1;
        }
        if (nextBtn) {
            nextBtn.disabled = this.currentPage >= this.totalPages;
        }
        if (pageInfo) {
            pageInfo.textContent = `${this.currentPage} / ${this.totalPages}`;
        }
    },

    goToPage(page) {
        if (page < 1 || page > this.totalPages) return;
        this.currentPage = page;
        this.renderSuggestions();
    },

    async confirmLink(sourceId, targetId) {
        try {
            const response = await fetch(`/api/v1/nodes/${sourceId}/links/${targetId}/confirm`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (!response.ok) throw new Error('确认失败');

            // 移除已确认的建议
            this.suggestions = this.suggestions.filter(s =>
                !(s.source === sourceId && s.target === targetId)
            );

            this.totalPages = Math.ceil(this.suggestions.length / this.pageSize) || 1;
            if (this.currentPage > this.totalPages) {
                this.currentPage = this.totalPages;
            }

            this.renderSuggestions();

            // 更新统计
            const statsEl = document.getElementById('suggestionsStats');
            if (statsEl) {
                statsEl.innerHTML = `
                    <span>待确认: <strong>${this.suggestions.length}</strong></span>
                    <span>当前页: <strong>${this.currentPage}</strong>/${this.totalPages}</span>
                `;
            }

            if (window.ui) {
                window.ui.showToast('关系已确认');
            }
        } catch (error) {
            console.error('Confirm link error:', error);
            if (window.ui) {
                window.ui.showToast(`确认失败: ${error.message}`, 'error');
            }
        }
    },

    async rejectLink(sourceId, targetId) {
        if (!window.confirm('确定要拒绝这个关系建议吗？')) return;

        try {
            const response = await fetch(`/api/v1/nodes/${sourceId}/links/${targetId}`, {
                method: 'DELETE'
            });

            if (!response.ok) throw new Error('拒绝失败');

            // 移除已拒绝的建议
            this.suggestions = this.suggestions.filter(s =>
                !(s.source === sourceId && s.target === targetId)
            );

            this.totalPages = Math.ceil(this.suggestions.length / this.pageSize) || 1;
            if (this.currentPage > this.totalPages) {
                this.currentPage = this.totalPages;
            }

            this.renderSuggestions();

            // 更新统计
            const statsEl = document.getElementById('suggestionsStats');
            if (statsEl) {
                statsEl.innerHTML = `
                    <span>待确认: <strong>${this.suggestions.length}</strong></span>
                    <span>当前页: <strong>${this.currentPage}</strong>/${this.totalPages}</span>
                `;
            }

            if (window.ui) {
                window.ui.showToast('关系已拒绝');
            }
        } catch (error) {
            console.error('Reject link error:', error);
            if (window.ui) {
                window.ui.showToast(`拒绝失败: ${error.message}`, 'error');
            }
        }
    },

    viewNode(nodeId) {
        if (window.windowManager) {
            window.windowManager.openMainWindow(nodeId);
        }
    },

    getRelationTypeName(type) {
        const names = {
            'support': '支持',
            'contradict': '矛盾',
            'extend': '延伸',
            'source': '来源',
            'analogy': '类比'
        };
        return names[type] || type;
    },

    getRelationColor(type) {
        const colors = {
            'support': 'rgba(0, 184, 148, 0.2)',
            'contradict': 'rgba(231, 76, 60, 0.2)',
            'extend': 'rgba(108, 92, 231, 0.2)',
            'source': 'rgba(253, 203, 110, 0.2)',
            'analogy': 'rgba(0, 206, 201, 0.2)'
        };
        return colors[type] || 'rgba(149, 165, 166, 0.2)';
    },

    getConfidenceColor(confidence) {
        if (confidence >= 0.8) return '#00b894';
        if (confidence >= 0.6) return '#fdcb6e';
        if (confidence >= 0.4) return '#e67e22';
        return '#e74c3c';
    },

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// ===== Relationship Graph (关系图谱 - 可视化) =====
const relationshipGraphView = {
    cy: null,
    currentFilter: {
        tag: 'all',
        theme: 'all',
        relationType: 'all'
    },
    nodes: [],
    edges: [],

    async init() {
        this.bindEvents();
        await this.loadGraph();
    },

    bindEvents() {
        const tagFilter = document.getElementById('relGraphTagFilter');
        const themeFilter = document.getElementById('relGraphThemeFilter');
        const relationFilter = document.getElementById('relGraphRelationFilter');
        const refreshBtn = document.getElementById('refreshRelGraph');
        const layoutBtn = document.getElementById('relGraphLayoutBtn');

        if (tagFilter) {
            tagFilter.addEventListener('change', (e) => {
                this.currentFilter.tag = e.target.value;
                this.filterAndRender();
            });
        }
        if (themeFilter) {
            themeFilter.addEventListener('change', (e) => {
                this.currentFilter.theme = e.target.value;
                this.filterAndRender();
            });
        }
        if (relationFilter) {
            relationFilter.addEventListener('change', (e) => {
                this.currentFilter.relationType = e.target.value;
                this.filterAndRender();
            });
        }
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadGraph());
        }
        if (layoutBtn) {
            layoutBtn.addEventListener('click', () => this.relayout());
        }

        window.addEventListener('resize', () => {
            if (this.cy) {
                this.cy.resize();
            }
        });
    },

    async loadGraph() {
        const container = document.getElementById('relationshipGraphCanvas');
        if (!container) return;

        container.innerHTML = '<div class="empty-state"><p>加载中...</p></div>';

        try {
            const [graphResponse, themesResponse] = await Promise.all([
                fetch('/api/v1/graph?include_unconfirmed=true'),
                fetch('/api/v1/themes')
            ]);

            if (!graphResponse.ok) throw new Error('加载图谱失败');

            const graphData = await graphResponse.json();
            const themesData = themesResponse.ok ? await themesResponse.json() : { themes: [] };

            this.nodes = graphData.nodes || [];
            this.edges = graphData.edges || [];

            // 更新主题筛选器
            this.updateThemeFilter(themesData.themes || []);

            if (this.nodes.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <p>暂无节点</p>
                    </div>
                `;
                return;
            }

            this.filterAndRender();

        } catch (error) {
            console.error('Relationship graph error:', error);
            container.innerHTML = `
                <div class="empty-state">
                    <p style="color: var(--color-danger)">加载失败: ${error.message}</p>
                </div>
            `;
        }
    },

    updateThemeFilter(themes) {
        const select = document.getElementById('relGraphThemeFilter');
        if (!select) return;

        const currentValue = select.value;
        select.innerHTML = '<option value="all">所有主题</option>' +
            themes.map(t => `<option value="${t.id}">${this.escapeHtml(t.summary.substring(0, 50))}...</option>`).join('');
        select.value = currentValue || 'all';
    },

    filterAndRender() {
        let filteredNodes = [...this.nodes];
        let filteredEdges = [...this.edges];

        // 标签筛选
        if (this.currentFilter.tag !== 'all') {
            const nodeIds = new Set(
                filteredNodes
                    .filter(n => n.tags && n.tags.includes(this.currentFilter.tag))
                    .map(n => n.id)
            );
            filteredNodes = filteredNodes.filter(n => nodeIds.has(n.id));
            filteredEdges = filteredEdges.filter(e =>
                nodeIds.has(e.source) && nodeIds.has(e.target)
            );
        }

        // 关系类型筛选
        if (this.currentFilter.relationType !== 'all') {
            filteredEdges = filteredEdges.filter(e =>
                e.relation_type === this.currentFilter.relationType
            );
            const connectedNodeIds = new Set();
            filteredEdges.forEach(e => {
                connectedNodeIds.add(e.source);
                connectedNodeIds.add(e.target);
            });
            filteredNodes = filteredNodes.filter(n => connectedNodeIds.has(n.id));
        }

        this.renderGraph(filteredNodes, filteredEdges);
        this.updateStats(filteredNodes.length, filteredEdges.length);
    },

    renderGraph(nodes, edges) {
        const container = document.getElementById('relationshipGraphCanvas');
        if (!container) return;

        container.innerHTML = '';

        const elements = [];

        // 添加节点
        nodes.forEach(node => {
            elements.push({
                data: {
                    id: node.id,
                    label: node.label || node.proposition?.substring(0, 30) + '...' || node.id,
                    fullText: node.full_text || node.proposition || '',
                    color: node.tag_color || this.getTagColor(node.tags?.[0]),
                    tag: node.tags?.[0] || 'vague',
                    linkCount: node.link_count || 0
                }
            });
        });

        // 添加边
        edges.forEach((edge, index) => {
            elements.push({
                data: {
                    id: `edge-${index}`,
                    source: edge.source,
                    target: edge.target,
                    relationName: edge.relation_name || this.getRelationTypeName(edge.relation_type),
                    relationType: edge.relation_type,
                    strength: edge.strength || 0.5,
                    color: edge.color || this.getRelationEdgeColor(edge.relation_type),
                    confirmed: edge.confirmed
                }
            });
        });

        // 初始化 Cytoscape
        this.cy = cytoscape({
            container: container,
            elements: elements,
            style: [
                {
                    selector: 'node',
                    style: {
                        'background-color': 'data(color)',
                        'width': ele => 15 + Math.min((ele.data('linkCount') || 0) * 2, 20),
                        'height': ele => 15 + Math.min((ele.data('linkCount') || 0) * 2, 20),
                        'label': 'data(label)',
                        'font-size': '10px',
                        'color': '#e8e8f0',
                        'text-background-color': '#1a1a2e',
                        'text-background-opacity': 0.8,
                        'text-background-padding': '3px',
                        'text-valign': 'bottom',
                        'text-halign': 'center',
                        'text-margin-y': 5,
                        'border-width': 2,
                        'border-color': '#2d2d44'
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'width': ele => 1 + (ele.data('strength') || 0.5) * 4,
                        'line-color': 'data(color)',
                        'target-arrow-color': 'data(color)',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        'label': 'data(relationName)',
                        'font-size': '8px',
                        'color': '#a0a0b0',
                        'text-background-color': '#1a1a2e',
                        'text-background-opacity': 0.9,
                        'text-background-padding': '2px',
                        'arrow-scale': 0.8,
                        'line-opacity': ele => ele.data('confirmed') ? 1 : 0.5,
                        'line-style': ele => ele.data('confirmed') ? 'solid' : 'dashed'
                    }
                }
            ],
            layout: {
                name: 'cose',
                padding: 30,
                nodeRepulsion: 400000,
                edgeElasticity: 100,
                nestingFactor: 5,
                gravity: 80,
                numIter: 1000,
                initialTemp: 200,
                coolingFactor: 0.95,
                minTemp: 1.0
            },
            minZoom: 0.1,
            maxZoom: 4,
            wheelSensitivity: 0.3
        });

        // 节点点击事件
        this.cy.on('tap', 'node', (evt) => {
            const node = evt.target;
            const nodeId = node.id();
            this.showNodeTooltip(node);
        });

        // 边的悬停效果
        this.cy.on('mouseover', 'edge', (evt) => {
            const edge = evt.target;
            edge.animate({
                style: { 'line-opacity': 1, 'width': edge.data('strength') * 6 }
            }, { duration: 200 });
        });

        this.cy.on('mouseout', 'edge', (evt) => {
            const edge = evt.target;
            edge.animate({
                style: {
                    'line-opacity': edge.data('confirmed') ? 1 : 0.5,
                    'width': 1 + edge.data('strength') * 4
                }
            }, { duration: 200 });
        });

        // 节点的悬停效果
        this.cy.on('mouseover', 'node', (evt) => {
            const node = evt.target;
            node.animate({
                style: { 'border-color': '#ffffff' }
            }, { duration: 200 });
        });

        this.cy.on('mouseout', 'node', (evt) => {
            const node = evt.target;
            node.animate({
                style: { 'border-color': '#2d2d44' }
            }, { duration: 200 });
        });
    },

    showNodeTooltip(node) {
        const data = node.data();
        if (window.windowManager) {
            window.windowManager.openMainWindow(data.id);
        }
    },

    relayout() {
        if (this.cy) {
            const layout = this.cy.layout({
                name: 'cose',
                padding: 30,
                nodeRepulsion: 400000,
                edgeElasticity: 100,
                nestingFactor: 5,
                gravity: 80,
                numIter: 1000,
                initialTemp: 200,
                coolingFactor: 0.95,
                minTemp: 1.0,
                animate: true,
                animationDuration: 500
            });
            layout.run();
        }
    },

    updateStats(nodeCount, edgeCount) {
        const statsEl = document.getElementById('relGraphStats');
        if (statsEl) {
            statsEl.innerHTML = `
                <span>节点: <strong>${nodeCount}</strong></span>
                <span>连接: <strong>${edgeCount}</strong></span>
            `;
        }
    },

    getTagColor(tag) {
        const colors = {
            'definitive': '#00b894',
            'inferred': '#a29bfe',
            'vague': '#fdcb6e',
            'needs_thinking': '#e74c3c',
            'cross-domain': '#00cec9'
        };
        return colors[tag] || '#95a5a6';
    },

    getRelationEdgeColor(type) {
        const colors = {
            'support': '#00b894',
            'contradict': '#e74c3c',
            'extend': '#6c5ce7',
            'source': '#fdcb6e',
            'analogy': '#00cec9'
        };
        return colors[type] || '#95a5a6';
    },

    getRelationTypeName(type) {
        const names = {
            'support': '支持',
            'contradict': '矛盾',
            'extend': '延伸',
            'source': '来源',
            'analogy': '类比'
        };
        return names[type] || type;
    },

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    destroy() {
        if (this.cy) {
            this.cy.destroy();
            this.cy = null;
        }
    }
};

// ===== Node Detail View (节点详情视图) =====
const NodeDetailView = {
    currentNodeId: null,
    isEditingRefined: false,

    async show(nodeId) {
        this.currentNodeId = nodeId;
        await this.loadNode(nodeId);
    },

    async loadNode(nodeId) {
        try {
            const response = await fetch(`/api/v1/nodes/${nodeId}`);
            if (!response.ok) throw new Error('加载失败');

            const data = await response.json();
            const node = data.node;
            const relatedNodes = data.related_nodes;

            this.render(node, relatedNodes);
        } catch (error) {
            console.error('Node detail error:', error);
            this.renderError(error.message);
        }
    },

    render(node, relatedNodes) {
        const container = document.getElementById('nodeDetailContent');
        if (!container) return;

        const hasRefinedContent = node.refined_content && node.refined_content.trim().length > 0;

        const tagsHtml = this.renderTags(node.tags);

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

        const rawInputHtml = this.renderCollapsibleRawInput(node.raw_input, node.id);

        // Evolution badge
        const versionBadge = node.refined_content_version > 1
            ? `<span class="version-badge">v${node.refined_content_version}</span>`
            : '';

        const lastRefinedText = node.last_refined_at
            ? `<span class="last-refined">更新于 ${new Date(node.last_refined_at).toLocaleString('zh-CN')}</span>`
            : '';

        // Refined content display
        const refinedContentHtml = hasRefinedContent
            ? `<div class="refined-content-text">${escapeHtml(node.refined_content)}</div>${lastRefinedText}`
            : `<div class="refined-content-empty" style="color: var(--color-text-muted); padding: 20px; text-align: center; background: var(--color-bg-secondary); border-radius: 8px;">
                <p>📝 尚未生成精炼内容</p>
                <p style="font-size: 0.9em; margin-top: 8px;">点击上方"重新生成"按钮创建精炼版本</p>
            </div>`;

        // Format refined content with markdown-like styling
        const formatRefinedContent = (content) => {
            if (!content) return '';
            return content
                .replace(/## (.*)/g, '<h5 style="color: var(--color-primary); margin: 16px 0 8px 0; font-size: 1rem;">$1</h5>')
                .replace(/\n\n/g, '</p><p>')
                .replace(/^/, '<p>')
                .replace(/$/, '</p>')
                .replace(/<p>- (.*?)<\/p>/g, '<li>$1</li>')
                .replace(/(<li>.*<\/li>)/s, '<ul style="margin: 8px 0; padding-left: 20px;">$1</ul>');
        };

        const formattedRefinedContent = hasRefinedContent 
            ? formatRefinedContent(node.refined_content) 
            : '';

        container.innerHTML = `
            <div class="node-detail-container">
                <!-- Title Section (Most Prominent) -->
                <div class="node-detail-section title-section" style="background: linear-gradient(135deg, var(--color-bg-secondary) 0%, var(--color-bg-tertiary) 100%); border-left: 4px solid var(--color-primary);">
                    <div class="section-header" style="border-bottom: none;">
                        <h2 style="font-size: 1.5rem; font-weight: 600; color: var(--color-text-primary); margin: 0;">${escapeHtml(node.processed.proposition)}</h2>
                    </div>
                    <div style="font-size: 0.85rem; color: var(--color-text-muted); margin-top: 8px;">
                        节点标题 · ${new Date(node.timestamp).toLocaleDateString('zh-CN')}
                    </div>
                </div>

                <!-- Refined Content Section -->
                <div class="node-detail-section refined-content-section">
                    <div class="section-header">
                        <h4>📝 精炼内容 ${versionBadge}</h4>
                        <div class="section-actions">
                            <button class="btn-icon" id="regenerateRefinedBtn" title="重新生成">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="23 4 23 10 17 10"></polyline>
                                    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                                </svg>
                            </button>
                            ${hasRefinedContent ? `<button class="btn-icon" id="editRefinedBtn" title="编辑">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                                </svg>
                            </button>` : ''}
                        </div>
                    </div>
                    <div id="refinedContentDisplay" class="refined-content-display" style="line-height: 1.8;">
                        ${hasRefinedContent ? formattedRefinedContent : refinedContentHtml}
                    </div>
                    <div id="refinedContentEditor" class="refined-content-editor" style="display: none;">
                        <textarea id="refinedContentTextarea" rows="10" style="font-family: inherit; line-height: 1.6;">${hasRefinedContent ? escapeHtml(node.refined_content) : ''}</textarea>
                        <div class="editor-actions">
                            <button class="btn-secondary btn-sm" id="cancelRefinedEdit">取消</button>
                            <button class="btn-primary btn-sm" id="saveRefinedEdit">保存</button>
                        </div>
                    </div>
                </div>

                <!-- Tags Section -->
                <div class="node-detail-section">
                    <h4>标签</h4>
                    <div class="node-detail-tags">${tagsHtml}</div>
                </div>

                <!-- Questions Section -->
                <div class="node-detail-section">
                    <h4>开放问题</h4>
                    <ul class="questions-list">${questionsHtml}</ul>
                </div>

                <!-- Source Section -->
                <div class="node-detail-section">
                    <h4>来源</h4>
                    <div class="source-info">
                        ${node.source.type === 'original' ? '原创想法' : escapeHtml(node.source.title || '未指定')}
                        ${node.source.location ? `<span class="source-location">${escapeHtml(node.source.location)}</span>` : ''}
                    </div>
                </div>

                <!-- Related Links Section -->
                <div class="node-detail-section">
                    <h4>相关连接 (${relatedNodes?.length || 0})</h4>
                    <div class="links-list">${linksHtml}</div>
                </div>

                <!-- Raw Input Section (Collapsible) -->
                <div class="node-detail-section">
                    <h4>原始输入</h4>
                    ${rawInputHtml}
                </div>

                <!-- Metadata Section -->
                <div class="node-detail-section metadata-section">
                    <h4>元数据</h4>
                    <div class="metadata-content">
                        <span>ID: ${node.id}</span>
                        <span>创建时间: ${new Date(node.timestamp).toLocaleString('zh-CN')}</span>
                        ${node.refined_content_version ? `<span>版本: ${node.refined_content_version}</span>` : ''}
                    </div>
                </div>
            </div>
        `;

        this.attachEventListeners(node);
    },

    renderTags(tags) {
        const tagColors = {
            'definitive': '#00b894',
            'inferred': '#a29bfe',
            'vague': '#fdcb6e',
            'needs_thinking': '#e74c3c',
            'cross-domain': '#00cec9'
        };

        const tagNames = {
            'definitive': '明确结论',
            'inferred': '推断结论',
            'vague': '模糊感知',
            'needs_thinking': '待思考',
            'cross-domain': '跨域连接'
        };

        return tags.map(tag => `
            <span class="node-tag" style="background: ${tagColors[tag] || '#95a5a6'}20; color: ${tagColors[tag] || '#95a5a6'}; border: 1px solid ${tagColors[tag] || '#95a5a6'}40;">
                ${tagNames[tag] || tag}
            </span>
        `).join('');
    },

    renderCollapsibleRawInput(rawInput, nodeId) {
        if (!rawInput) return '<p style="color: var(--color-text-muted)">无原始输入</p>';

        const shouldCollapse = rawInput.length > 200;
        const rawInputId = `raw-input-${nodeId}`;

        if (shouldCollapse) {
            return `
                <div class="raw-input-container">
                    <div class="raw-input-collapsed" id="${rawInputId}-collapsed">
                        ${escapeHtml(rawInput.substring(0, 200))}...
                        <button class="raw-input-toggle" onclick="NodeDetailView.toggleRawInput('${rawInputId}')">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="6 9 12 15 18 9"></polyline>
                            </svg>
                            展开
                        </button>
                    </div>
                    <div class="raw-input-expanded" id="${rawInputId}-expanded" style="display: none;">
                        ${escapeHtml(rawInput)}
                        <button class="raw-input-toggle" onclick="NodeDetailView.toggleRawInput('${rawInputId}')">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="18 15 12 9 6 15"></polyline>
                            </svg>
                            收起
                        </button>
                    </div>
                </div>
            `;
        }

        return `<div class="raw-input-text">${escapeHtml(rawInput)}</div>`;
    },

    toggleRawInput(rawInputId) {
        const collapsed = document.getElementById(`${rawInputId}-collapsed`);
        const expanded = document.getElementById(`${rawInputId}-expanded`);
        if (collapsed && expanded) {
            const isCollapsed = collapsed.style.display !== 'none';
            collapsed.style.display = isCollapsed ? 'none' : 'block';
            expanded.style.display = isCollapsed ? 'block' : 'none';
        }
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

    attachEventListeners(node) {
        // Regenerate button
        const regenerateBtn = document.getElementById('regenerateRefinedBtn');
        if (regenerateBtn) {
            regenerateBtn.addEventListener('click', () => this.regenerateRefinedContent(node.id));
        }

        // Edit button
        const editBtn = document.getElementById('editRefinedBtn');
        if (editBtn) {
            editBtn.addEventListener('click', () => this.toggleEditMode());
        }

        // Cancel edit
        const cancelBtn = document.getElementById('cancelRefinedEdit');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.toggleEditMode(false));
        }

        // Save edit
        const saveBtn = document.getElementById('saveRefinedEdit');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveRefinedContent(node.id));
        }

        // Link items
        document.querySelectorAll('.link-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const nodeId = item.dataset.linkNodeId;
                if (nodeId && window.windowManager) {
                    window.windowManager.openSideWindow(nodeId);
                }
            });
        });
    },

    toggleEditMode(show = null) {
        const display = document.getElementById('refinedContentDisplay');
        const editor = document.getElementById('refinedContentEditor');

        if (show === null) {
            this.isEditingRefined = !this.isEditingRefined;
        } else {
            this.isEditingRefined = show;
        }

        if (display && editor) {
            display.style.display = this.isEditingRefined ? 'none' : 'block';
            editor.style.display = this.isEditingRefined ? 'block' : 'none';
        }
    },

    async regenerateRefinedContent(nodeId) {
        const btn = document.getElementById('regenerateRefinedBtn');
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

            // Reload the node to show updated content
            await this.loadNode(nodeId);

            if (window.ui) {
                window.ui.showToast('精炼内容已重新生成');
            }
        } catch (error) {
            console.error('Regenerate error:', error);
            if (window.ui) {
                window.ui.showToast(`重新生成失败: ${error.message}`, 'error');
            }
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="23 4 23 10 17 10"></polyline>
                        <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                    </svg>
                `;
            }
        }
    },

    async saveRefinedContent(nodeId) {
        const textarea = document.getElementById('refinedContentTextarea');
        if (!textarea) return;

        const refinedContent = textarea.value.trim();
        if (!refinedContent) {
            if (window.ui) {
                window.ui.showToast('精炼内容不能为空', 'error');
            }
            return;
        }

        const saveBtn = document.getElementById('saveRefinedEdit');
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.textContent = '保存中...';
        }

        try {
            const response = await fetch(`/api/v1/nodes/${nodeId}/refined-content`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refined_content: refinedContent })
            });

            if (!response.ok) throw new Error('保存失败');

            const data = await response.json();

            // Reload the node to show updated content
            await this.loadNode(nodeId);

            if (window.ui) {
                window.ui.showToast('精炼内容已更新');
            }
        } catch (error) {
            console.error('Save error:', error);
            if (window.ui) {
                window.ui.showToast(`保存失败: ${error.message}`, 'error');
            }
        } finally {
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.textContent = '保存';
            }
        }
    },

    renderError(message) {
        const container = document.getElementById('nodeDetailContent');
        if (container) {
            container.innerHTML = `
                <div class="empty-state">
                    <p style="color: var(--color-danger)">加载失败: ${escapeHtml(message)}</p>
                </div>
            `;
        }
    }
};

// ===== Theme Detail View (主题详情视图) =====
const ThemeDetailView = {
    currentThemeId: null,

    async show(themeId) {
        this.currentThemeId = themeId;
        await this.loadTheme(themeId);
    },

    async loadTheme(themeId) {
        try {
            // Load theme details, nodes, and related themes in parallel
            const [themeResponse, nodesResponse, relatedResponse] = await Promise.all([
                fetch(`/api/v1/themes/${themeId}`),
                fetch(`/api/v1/themes/${themeId}/nodes`),
                fetch(`/api/v1/themes/${themeId}/related`)
            ]);

            if (!themeResponse.ok) throw new Error('加载主题失败');

            const themeData = await themeResponse.json();
            const nodesData = await nodesResponse.json();
            const relatedData = await relatedResponse.ok ? await relatedResponse.json() : [];

            this.render(themeData, nodesData, relatedData);
        } catch (error) {
            console.error('Theme detail error:', error);
            this.renderError(error.message);
        }
    },

    render(themeData, nodes, relatedThemes) {
        const container = document.getElementById('themeDetailContent');
        if (!container) return;

        const theme = themeData.theme;

        // Evolution status badge
        const evolutionBadges = {
            'stable': { text: '稳定', color: '#00b894' },
            'evolving': { text: '演进中', color: '#fdcb6e' },
            'merged': { text: '已合并', color: '#a29bfe' },
            'deprecated': { text: '已弃用', color: '#e74c3c' }
        };
        const evolutionBadge = evolutionBadges[theme.evolution_status] || evolutionBadges['stable'];

        // Keywords
        const keywordsHtml = theme.keywords?.length
            ? theme.keywords.map(kw => `<span class="keyword-tag">${escapeHtml(kw)}</span>`).join('')
            : '<span style="color: var(--color-text-muted)">无关键词</span>';

        // Associated nodes with relationship strength
        const nodesHtml = nodes?.length
            ? nodes.map(node => `
                <div class="theme-node-item" data-node-id="${node.id}">
                    <div class="theme-node-content">
                        <div class="theme-node-proposition">${escapeHtml(node.proposition)}</div>
                        <div class="theme-node-meta">
                            <span class="relationship-strength" style="--strength: ${node.relationship_strength};">
                                关联度: ${Math.round(node.relationship_strength * 100)}%
                            </span>
                            <span class="node-tag-small">${this.getTagName(node.tags[0])}</span>
                        </div>
                    </div>
                    <button class="btn-icon view-node-btn" data-node-id="${node.id}" title="查看笔记">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                            <circle cx="12" cy="12" r="3"></circle>
                        </svg>
                    </button>
                </div>
            `).join('')
            : '<p style="color: var(--color-text-muted)">暂无关联笔记</p>';

        // Related themes
        const relatedHtml = relatedThemes?.length
            ? relatedThemes.map(related => `
                <div class="related-theme-item" data-theme-id="${related.id}">
                    <div class="related-theme-content">
                        <div class="related-theme-summary">${escapeHtml(related.summary)}</div>
                        <div class="related-theme-meta">
                            <span class="tag-badge tag-${related.tag}">${this.getTagName(related.tag)}</span>
                            <span class="shared-nodes">${related.shared_count} 个共享笔记</span>
                            <span class="similarity-score">相似度: ${Math.round(related.similarity_score * 100)}%</span>
                        </div>
                    </div>
                    <button class="btn-icon view-theme-btn" data-theme-id="${related.id}" title="查看主题">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                            <circle cx="12" cy="12" r="3"></circle>
                        </svg>
                    </button>
                </div>
            `).join('')
            : '<p style="color: var(--color-text-muted)">暂无相关主题</p>';

        container.innerHTML = `
            <div class="theme-detail-container">
                <!-- Theme Header -->
                <div class="theme-detail-header">
                    <div class="theme-title-section">
                        <h3>${escapeHtml(theme.summary)}</h3>
                        <span class="evolution-badge" style="background: ${evolutionBadge.color}20; color: ${evolutionBadge.color}; border: 1px solid ${evolutionBadge.color}40;">
                            ${evolutionBadge.text}
                        </span>
                    </div>
                    <div class="theme-meta-header">
                        <span class="theme-tag badge-${theme.tag}">${this.getTagName(theme.tag)}</span>
                        <span class="theme-stats">${theme.node_count} 个笔记 · v${theme.version}</span>
                    </div>
                </div>

                <!-- Keywords Section -->
                <div class="theme-detail-section">
                    <h4>关键词</h4>
                    <div class="keywords-list">${keywordsHtml}</div>
                </div>

                <!-- Associated Nodes Section -->
                <div class="theme-detail-section">
                    <div class="section-header">
                        <h4>关联笔记 (${nodes?.length || 0})</h4>
                        <span class="section-hint">按关联度排序</span>
                    </div>
                    <div class="theme-nodes-list">${nodesHtml}</div>
                </div>

                <!-- Related Themes Section -->
                <div class="theme-detail-section">
                    <div class="section-header">
                        <h4>相关主题 (${relatedThemes?.length || 0})</h4>
                        <span class="section-hint">基于共享笔记</span>
                    </div>
                    <div class="related-themes-list">${relatedHtml}</div>
                </div>

                <!-- Metadata Section -->
                <div class="theme-detail-section metadata-section">
                    <h4>元数据</h4>
                    <div class="metadata-content">
                        <span>ID: ${theme.id}</span>
                        <span>创建时间: ${new Date(theme.created_at).toLocaleString('zh-CN')}</span>
                        <span>更新时间: ${new Date(theme.updated_at).toLocaleString('zh-CN')}</span>
                    </div>
                </div>
            </div>
        `;

        this.attachEventListeners();
    },

    attachEventListeners() {
        // View node buttons
        document.querySelectorAll('.view-node-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const nodeId = btn.dataset.nodeId;
                if (nodeId && window.windowManager) {
                    window.windowManager.openSideWindow(nodeId);
                }
            });
        });

        // Theme node item click
        document.querySelectorAll('.theme-node-item').forEach(item => {
            item.addEventListener('click', () => {
                const nodeId = item.dataset.nodeId;
                if (nodeId && window.windowManager) {
                    window.windowManager.openSideWindow(nodeId);
                }
            });
        });

        // View theme buttons
        document.querySelectorAll('.view-theme-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const themeId = btn.dataset.themeId;
                if (themeId) {
                    this.loadTheme(themeId);
                }
            });
        });

        // Related theme item click
        document.querySelectorAll('.related-theme-item').forEach(item => {
            item.addEventListener('click', () => {
                const themeId = item.dataset.themeId;
                if (themeId) {
                    this.loadTheme(themeId);
                }
            });
        });
    },

    getTagName(tag) {
        const names = {
            'definitive': '明确结论',
            'inferred': '推断结论',
            'vague': '模糊感知',
            'needs_thinking': '待思考',
            'cross-domain': '跨域连接'
        };
        return names[tag] || tag;
    },

    renderError(message) {
        const container = document.getElementById('themeDetailContent');
        if (container) {
            container.innerHTML = `
                <div class="empty-state">
                    <p style="color: var(--color-danger)">加载失败: ${escapeHtml(message)}</p>
                </div>
            `;
        }
    }
};

// ===== Theme Evolution View (主题演化视图) =====
const themeEvolutionView = {
    currentThemeId: null,
    evolutionData: null,
    suggestions: [],
    
    async init(themeId) {
        this.currentThemeId = themeId;
        await this.loadEvolutionData();
        this.bindEvents();
    },
    
    bindEvents() {
        const container = document.getElementById('themeEvolutionContent');
        if (!container) return;
        
        // Apply suggestion buttons
        container.querySelectorAll('.apply-suggestion-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const suggestionId = e.currentTarget.dataset.suggestionId;
                this.applySuggestion(suggestionId);
            });
        });
        
        // Reject suggestion buttons
        container.querySelectorAll('.reject-suggestion-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const suggestionId = e.currentTarget.dataset.suggestionId;
                this.rejectSuggestion(suggestionId);
            });
        });
        
        // Rollback version buttons
        container.querySelectorAll('.rollback-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const version = parseInt(e.currentTarget.dataset.version);
                this.rollbackToVersion(version);
            });
        });
        
        // View conflict detail buttons
        container.querySelectorAll('.view-conflict-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const suggestionId = e.currentTarget.dataset.suggestionId;
                this.showConflictDetail(suggestionId);
            });
        });
        
        // Toggle diff buttons
        container.querySelectorAll('.toggle-diff-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const version = e.currentTarget.dataset.version;
                this.toggleVersionDiff(version);
            });
        });
        
        // Refresh button
        const refreshBtn = document.getElementById('refreshEvolutionBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadEvolutionData());
        }
        
        // Analyze button
        const analyzeBtn = document.getElementById('analyzeEvolutionBtn');
        if (analyzeBtn) {
            analyzeBtn.addEventListener('click', () => this.analyzeEvolution());
        }
    },
    
    async loadEvolutionData() {
        const container = document.getElementById('themeEvolutionContent');
        const headerEl = document.getElementById('evolutionThemeHeader');
        
        if (!container) return;
        
        container.innerHTML = '<div class="empty-state"><p>加载中...</p></div>';
        
        try {
            // Load evolution history
            const historyResponse = await fetch(`/api/v1/themes/${this.currentThemeId}/evolution`);
            if (!historyResponse.ok) throw new Error('加载演化历史失败');
            this.evolutionData = await historyResponse.json();
            
            // Load pending suggestions
            const suggestionsResponse = await fetch(`/api/v1/themes/evolution/suggestions?status=pending&theme_id=${this.currentThemeId}`);
            if (!suggestionsResponse.ok) throw new Error('加载建议失败');
            const suggestionsData = await suggestionsResponse.json();
            this.suggestions = suggestionsData.suggestions || [];
            
            // Load conflicts
            const conflictsResponse = await fetch(`/api/v1/themes/${this.currentThemeId}/conflicts`);
            if (!conflictsResponse.ok) throw new Error('加载冲突失败');
            this.conflictsData = await conflictsResponse.json();
            
            // Update header
            if (headerEl) {
                headerEl.innerHTML = `
                    <div class="evolution-theme-info">
                        <h3>主题演化历史</h3>
                        <div class="evolution-meta">
                            <span class="version-badge">版本 ${this.evolutionData.current_version}</span>
                            <span class="status-badge status-${this.evolutionData.evolution_status}">
                                ${this.getStatusName(this.evolutionData.evolution_status)}
                            </span>
                        </div>
                    </div>
                `;
            }
            
            this.render();
            
        } catch (error) {
            console.error('Theme evolution load error:', error);
            container.innerHTML = `
                <div class="empty-state">
                    <p style="color: var(--color-danger)">加载失败: ${error.message}</p>
                </div>
            `;
        }
    },
    
    render() {
        const container = document.getElementById('themeEvolutionContent');
        if (!container) return;
        
        let html = '<div class="evolution-container">';
        
        // Pending suggestions section
        if (this.suggestions.length > 0) {
            html += this.renderPendingSuggestions();
        }
        
        // Conflicts section
        if (this.conflictsData && this.conflictsData.total_conflicts > 0) {
            html += this.renderConflicts();
        }
        
        // Timeline section
        html += this.renderTimeline();
        
        html += '</div>';
        container.innerHTML = html;
        
        // Re-bind events after render
        this.bindEvents();
    },
    
    renderPendingSuggestions() {
        return `
            <div class="evolution-section suggestions-section">
                <h4 class="section-title">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
                        <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                        <polyline points="2 17 12 22 22 17"></polyline>
                    </svg>
                    待处理的演进建议 (${this.suggestions.length})
                </h4>
                <div class="suggestions-list">
                    ${this.suggestions.map(s => this.renderSuggestionCard(s)).join('')}
                </div>
            </div>
        `;
    },
    
    renderSuggestionCard(suggestion) {
        const conflictTypeName = this.getConflictTypeName(suggestion.conflict_type);
        const hasSummaryChange = suggestion.suggested_summary && suggestion.suggested_summary !== this.getCurrentSummary();
        const hasTagChange = suggestion.suggested_tag && suggestion.suggested_tag !== this.getCurrentTag();
        
        return `
            <div class="suggestion-card" data-suggestion-id="${suggestion.id}">
                <div class="suggestion-header">
                    <span class="conflict-type-badge type-${suggestion.conflict_type}">${conflictTypeName}</span>
                    <span class="suggestion-date">${new Date(suggestion.created_at).toLocaleString('zh-CN')}</span>
                </div>
                <div class="suggestion-body">
                    <div class="suggestion-reason">${this.escapeHtml(suggestion.reason)}</div>
                    ${hasSummaryChange ? `
                        <div class="diff-row">
                            <div class="diff-label">核心命题:</div>
                            <div class="diff-content">
                                <div class="diff-old">${this.escapeHtml(this.getCurrentSummary())}</div>
                                <div class="diff-arrow">→</div>
                                <div class="diff-new">${this.escapeHtml(suggestion.suggested_summary)}</div>
                            </div>
                        </div>
                    ` : ''}
                    ${hasTagChange ? `
                        <div class="diff-row">
                            <div class="diff-label">标签:</div>
                            <div class="diff-content">
                                <div class="diff-old">${this.getTagName(this.getCurrentTag())}</div>
                                <div class="diff-arrow">→</div>
                                <div class="diff-new">${this.getTagName(suggestion.suggested_tag)}</div>
                            </div>
                        </div>
                    ` : ''}
                    ${suggestion.affected_node_ids.length > 0 ? `
                        <div class="affected-nodes">
                            <div class="affected-label">影响节点:</div>
                            <div class="affected-list">
                                ${suggestion.affected_node_ids.map(id => `
                                    <span class="affected-node-tag" data-node-id="${id}">${id.substring(0, 8)}...</span>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
                <div class="suggestion-actions">
                    <button class="btn-primary apply-suggestion-btn" data-suggestion-id="${suggestion.id}">
                        应用
                    </button>
                    <button class="btn-secondary reject-suggestion-btn" data-suggestion-id="${suggestion.id}">
                        拒绝
                    </button>
                </div>
            </div>
        `;
    },
    
    renderConflicts() {
        const conflicts = this.conflictsData.conflicts || [];
        return `
            <div class="evolution-section conflicts-section">
                <h4 class="section-title">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                        <line x1="12" y1="9" x2="12" y2="13"></line>
                        <line x1="12" y1="17" x2="12.01" y2="17"></line>
                    </svg>
                    检测到的冲突 (${this.conflictsData.total_conflicts})
                </h4>
                <div class="conflicts-list">
                    ${conflicts.map(c => this.renderConflictCard(c)).join('')}
                </div>
            </div>
        `;
    },
    
    renderConflictCard(conflict) {
        const conflictTypeName = this.getConflictTypeName(conflict.conflict_type);
        
        return `
            <div class="conflict-card" data-conflict-id="${conflict.id}">
                <div class="conflict-header">
                    <span class="conflict-type-badge type-${conflict.conflict_type}">${conflictTypeName}</span>
                </div>
                <div class="conflict-body">
                    <div class="conflict-reason">${this.escapeHtml(conflict.reason)}</div>
                    ${conflict.affected_node_ids.length > 0 ? `
                        <div class="conflict-affected">
                            <span class="affected-count">影响 ${conflict.affected_node_ids.length} 个节点</span>
                            <button class="btn-link view-conflict-btn" data-suggestion-id="${conflict.id}">
                                查看详情
                            </button>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    },
    
    renderTimeline() {
        const history = this.evolutionData.history || [];
        
        if (history.length === 0) {
            return `
                <div class="evolution-section timeline-section">
                    <h4 class="section-title">演化历史</h4>
                    <div class="empty-state">
                        <p>暂无演化历史</p>
                    </div>
                </div>
            `;
        }
        
        return `
            <div class="evolution-section timeline-section">
                <h4 class="section-title">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
                        <circle cx="12" cy="12" r="10"></circle>
                        <polyline points="12 6 12 12 16 14"></polyline>
                    </svg>
                    演化历史 (${history.length} 个版本)
                </h4>
                <div class="timeline">
                    ${history.slice().reverse().map((version, index) => this.renderTimelineItem(version, index === 0)).join('')}
                </div>
            </div>
        `;
    },
    
    renderTimelineItem(version, isLatest) {
        return `
            <div class="timeline-item ${isLatest ? 'latest' : ''}" data-version="${version.version}">
                <div class="timeline-marker">
                    <div class="timeline-dot"></div>
                    <div class="timeline-line"></div>
                </div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <span class="version-label">版本 ${version.version}</span>
                        <span class="timeline-date">${new Date(version.updated_at).toLocaleString('zh-CN')}</span>
                        ${isLatest ? '<span class="latest-badge">当前</span>' : ''}
                    </div>
                    <div class="timeline-body">
                        <div class="version-summary">${this.escapeHtml(version.summary)}</div>
                        <div class="version-tag">${this.getTagName(version.tag)}</div>
                        ${version.reason ? `<div class="version-reason">原因: ${this.escapeHtml(version.reason)}</div>` : ''}
                    </div>
                    <div class="timeline-actions">
                        ${!isLatest ? `
                            <button class="btn-link rollback-btn" data-version="${version.version}">
                                回滚到此版本
                            </button>
                            <button class="btn-link toggle-diff-btn" data-version="${version.version}">
                                对比差异
                            </button>
                        ` : ''}
                    </div>
                    <div class="version-diff" id="diff-${version.version}" style="display: none;">
                        <!-- Diff content loaded dynamically -->
                    </div>
                </div>
            </div>
        `;
    },
    
    async applySuggestion(suggestionId) {
        try {
            const response = await fetch(`/api/v1/themes/evolution/suggestions/${suggestionId}/apply`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ confirm: true })
            });
            
            if (!response.ok) throw new Error('应用建议失败');
            
            const result = await response.json();
            if (result.success) {
                this.showToast('演进建议已应用', 'success');
                await this.loadEvolutionData();
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            this.showToast(`应用失败: ${error.message}`, 'error');
        }
    },
    
    async rejectSuggestion(suggestionId) {
        try {
            const response = await fetch(`/api/v1/themes/evolution/suggestions/${suggestionId}/reject`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reason: '' })
            });
            
            if (!response.ok) throw new Error('拒绝建议失败');
            
            const result = await response.json();
            if (result.success) {
                this.showToast('演进建议已拒绝', 'success');
                await this.loadEvolutionData();
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            this.showToast(`拒绝失败: ${error.message}`, 'error');
        }
    },
    
    async rollbackToVersion(version) {
        if (!confirm(`确定要回滚到版本 ${version} 吗？当前版本将被保存到历史记录中。`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/v1/themes/${this.currentThemeId}/rollback/${version}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ confirm: true })
            });
            
            if (!response.ok) throw new Error('回滚失败');
            
            const result = await response.json();
            if (result.success) {
                this.showToast(`已回滚到版本 ${version}`, 'success');
                await this.loadEvolutionData();
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            this.showToast(`回滚失败: ${error.message}`, 'error');
        }
    },
    
    async analyzeEvolution() {
        const analyzeBtn = document.getElementById('analyzeEvolutionBtn');
        if (analyzeBtn) {
            analyzeBtn.disabled = true;
            analyzeBtn.innerHTML = '<span class="loading"></span> 分析中...';
        }
        
        try {
            const response = await fetch(`/api/v1/themes/${this.currentThemeId}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ include_nodes: true })
            });
            
            if (!response.ok) throw new Error('分析失败');
            
            const result = await response.json();
            if (result.success) {
                this.showToast(`分析完成，生成 ${result.suggestions_generated} 条建议`, 'success');
                await this.loadEvolutionData();
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            this.showToast(`分析失败: ${error.message}`, 'error');
        } finally {
            if (analyzeBtn) {
                analyzeBtn.disabled = false;
                analyzeBtn.innerHTML = '分析演进';
            }
        }
    },
    
    showConflictDetail(suggestionId) {
        const suggestion = this.suggestions.find(s => s.id === suggestionId);
        if (!suggestion) return;
        
        // Show in a modal or side panel
        if (window.windowManager) {
            const content = this.buildConflictDetailContent(suggestion);
            windowManager.openCustomWindow(`conflict-${suggestionId}`, '冲突详情', content);
        }
    },
    
    buildConflictDetailContent(suggestion) {
        return `
            <div class="conflict-detail">
                <div class="detail-row">
                    <label>冲突类型:</label>
                    <span>${this.getConflictTypeName(suggestion.conflict_type)}</span>
                </div>
                <div class="detail-row">
                    <label>原因:</label>
                    <p>${this.escapeHtml(suggestion.reason)}</p>
                </div>
                <div class="detail-row">
                    <label>建议的核心命题:</label>
                    <p>${this.escapeHtml(suggestion.suggested_summary || '无变化')}</p>
                </div>
                <div class="detail-row">
                    <label>建议的标签:</label>
                    <p>${suggestion.suggested_tag ? this.getTagName(suggestion.suggested_tag) : '无变化'}</p>
                </div>
                <div class="detail-row">
                    <label>影响节点:</label>
                    <div class="affected-nodes-list">
                        ${suggestion.affected_node_ids.map(id => `
                            <span class="node-tag" data-node-id="${id}">${id}</span>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
    },
    
    toggleVersionDiff(version) {
        const diffEl = document.getElementById(`diff-${version}`);
        if (!diffEl) return;
        
        if (diffEl.style.display === 'none') {
            // Load and show diff
            this.loadVersionDiff(version, diffEl);
            diffEl.style.display = 'block';
        } else {
            diffEl.style.display = 'none';
        }
    },
    
    loadVersionDiff(version, container) {
        const versionData = this.evolutionData.history.find(v => v.version === version);
        const currentData = this.evolutionData.history.find(v => v.version === this.evolutionData.current_version);
        
        if (!versionData || !currentData) return;
        
        container.innerHTML = `
            <div class="diff-container">
                <div class="diff-header">
                    <span>版本 ${version} → 版本 ${this.evolutionData.current_version}</span>
                </div>
                ${versionData.summary !== currentData.summary ? `
                    <div class="diff-section">
                        <div class="diff-section-title">核心命题变化</div>
                        <div class="diff-old">${this.escapeHtml(versionData.summary)}</div>
                        <div class="diff-new">${this.escapeHtml(currentData.summary)}</div>
                    </div>
                ` : ''}
                ${versionData.tag !== currentData.tag ? `
                    <div class="diff-section">
                        <div class="diff-section-title">标签变化</div>
                        <div class="diff-old">${this.getTagName(versionData.tag)}</div>
                        <div class="diff-new">${this.getTagName(currentData.tag)}</div>
                    </div>
                ` : ''}
            </div>
        `;
    },
    
    getCurrentSummary() {
        if (!this.evolutionData || !this.evolutionData.history) return '';
        const current = this.evolutionData.history.find(v => v.version === this.evolutionData.current_version);
        return current ? current.summary : '';
    },
    
    getCurrentTag() {
        if (!this.evolutionData || !this.evolutionData.history) return '';
        const current = this.evolutionData.history.find(v => v.version === this.evolutionData.current_version);
        return current ? current.tag : '';
    },
    
    getStatusName(status) {
        const names = {
            'stable': '稳定',
            'evolving': '演化中',
            'merged': '已合并',
            'deprecated': '已废弃'
        };
        return names[status] || status;
    },
    
    getConflictTypeName(type) {
        const names = {
            'definition_change': '定义变化',
            'scope_expansion': '范围扩展',
            'scope_reduction': '范围缩减',
            'tag_mismatch': '标签不匹配',
            'semantic_drift': '语义漂移',
            'node_conflict': '节点冲突',
            'merge_suggested': '建议合并',
            'split_suggested': '建议拆分'
        };
        return names[type] || type;
    },
    
    getTagName(tag) {
        const names = {
            'definitive': '明确结论',
            'inferred': '推断结论',
            'vague': '模糊感知',
            'needs_thinking': '待思考',
            'cross-domain': '跨域连接'
        };
        return names[tag] || tag;
    },
    
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
    
    showToast(message, type = 'success') {
        if (window.ui && window.ui.showToast) {
            window.ui.showToast(message, type);
        }
    }
};

// ===== Theme Conflict View (主题冲突视图) =====
const themeConflictView = {
    conflicts: [],
    currentThemeId: null,
    
    async init(themeId) {
        this.currentThemeId = themeId;
        await this.loadConflicts();
        this.bindEvents();
    },
    
    bindEvents() {
        const container = document.getElementById('themeConflictContent');
        if (!container) return;
        
        container.querySelectorAll('.resolve-conflict-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const conflictId = e.currentTarget.dataset.conflictId;
                this.resolveConflict(conflictId);
            });
        });
        
        container.querySelectorAll('.view-node-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const nodeId = e.currentTarget.dataset.nodeId;
                if (window.windowManager) {
                    window.windowManager.openSideWindow(nodeId);
                }
            });
        });
        
        const refreshBtn = document.getElementById('refreshConflictsBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadConflicts());
        }
    },
    
    async loadConflicts() {
        const container = document.getElementById('themeConflictContent');
        if (!container) return;
        
        container.innerHTML = '<div class="empty-state"><p>加载中...</p></div>';
        
        try {
            // Load all pending suggestions as conflicts
            const response = await fetch('/api/v1/themes/evolution/suggestions?status=pending');
            if (!response.ok) throw new Error('加载冲突失败');
            
            const data = await response.json();
            this.conflicts = data.suggestions || [];
            
            // Filter by theme if specified
            if (this.currentThemeId) {
                this.conflicts = this.conflicts.filter(c => c.theme_id === this.currentThemeId);
            }
            
            this.render();
            
        } catch (error) {
            console.error('Theme conflict load error:', error);
            container.innerHTML = `
                <div class="empty-state">
                    <p style="color: var(--color-danger)">加载失败: ${error.message}</p>
                </div>
            `;
        }
    },
    
    render() {
        const container = document.getElementById('themeConflictContent');
        if (!container) return;
        
        if (this.conflicts.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                    </div>
                    <p>暂无冲突</p>
                    <p style="color: var(--color-text-muted); font-size: 0.875rem;">所有主题都处于一致状态</p>
                </div>
            `;
            return;
        }
        
        // Group conflicts by type
        const groupedConflicts = this.groupByType(this.conflicts);
        
        let html = '<div class="conflicts-container">';
        
        // Summary stats
        html += `
            <div class="conflicts-summary">
                <div class="summary-stat">
                    <span class="stat-value">${this.conflicts.length}</span>
                    <span class="stat-label">待处理冲突</span>
                </div>
                <div class="summary-stat">
                    <span class="stat-value">${Object.keys(groupedConflicts).length}</span>
                    <span class="stat-label">冲突类型</span>
                </div>
            </div>
        `;
        
        // Conflicts by type
        for (const [type, conflicts] of Object.entries(groupedConflicts)) {
            html += `
                <div class="conflict-group">
                    <h4 class="conflict-group-title">
                        <span class="conflict-type-badge type-${type}">${this.getConflictTypeName(type)}</span>
                        <span class="conflict-count">${conflicts.length}</span>
                    </h4>
                    <div class="conflict-list">
                        ${conflicts.map(c => this.renderConflictDetail(c)).join('')}
                    </div>
                </div>
            `;
        }
        
        html += '</div>';
        container.innerHTML = html;
        
        this.bindEvents();
    },
    
    renderConflictDetail(conflict) {
        return `
            <div class="conflict-detail-card" data-conflict-id="${conflict.id}">
                <div class="conflict-detail-header">
                    <div class="conflict-theme-info">
                        <span class="conflict-theme-id">主题: ${conflict.theme_id.substring(0, 8)}...</span>
                        <span class="conflict-date">${new Date(conflict.created_at).toLocaleString('zh-CN')}</span>
                    </div>
                </div>
                <div class="conflict-detail-body">
                    <div class="conflict-reason">${this.escapeHtml(conflict.reason)}</div>
                    
                    ${conflict.suggested_summary ? `
                        <div class="conflict-change">
                            <div class="change-label">建议的核心命题:</div>
                            <div class="change-content">${this.escapeHtml(conflict.suggested_summary)}</div>
                        </div>
                    ` : ''}
                    
                    ${conflict.suggested_tag ? `
                        <div class="conflict-change">
                            <div class="change-label">建议的标签:</div>
                            <div class="change-content">
                                <span class="tag-badge tag-${conflict.suggested_tag}">${this.getTagName(conflict.suggested_tag)}</span>
                            </div>
                        </div>
                    ` : ''}
                    
                    ${conflict.affected_node_ids.length > 0 ? `
                        <div class="conflict-affected-nodes">
                            <div class="affected-header">
                                <span class="affected-title">影响节点 (${conflict.affected_node_ids.length})</span>
                            </div>
                            <div class="affected-nodes-grid">
                                ${conflict.affected_node_ids.map(id => `
                                    <button class="node-chip view-node-btn" data-node-id="${id}">
                                        ${id.substring(0, 8)}...
                                    </button>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
                <div class="conflict-detail-actions">
                    <button class="btn-primary resolve-conflict-btn" data-conflict-id="${conflict.id}">
                        应用建议
                    </button>
                    <button class="btn-secondary" onclick="themeEvolutionView.rejectSuggestion('${conflict.id}')">
                        忽略
                    </button>
                </div>
            </div>
        `;
    },
    
    groupByType(conflicts) {
        return conflicts.reduce((groups, conflict) => {
            const type = conflict.conflict_type;
            if (!groups[type]) {
                groups[type] = [];
            }
            groups[type].push(conflict);
            return groups;
        }, {});
    },
    
    async resolveConflict(conflictId) {
        await themeEvolutionView.applySuggestion(conflictId);
        await this.loadConflicts();
    },
    
    getConflictTypeName(type) {
        return themeEvolutionView.getConflictTypeName(type);
    },
    
    getTagName(tag) {
        return themeEvolutionView.getTagName(tag);
    },
    
    escapeHtml(text) {
        return themeEvolutionView.escapeHtml(text);
    }
};

// ===== Export for use in app.js =====
window.outlineView = outlineView;
window.epistemicMapView = epistemicMapView;
window.graphView = graphView;
window.themeEvolutionView = themeEvolutionView;
window.themeConflictView = themeConflictView;
window.NodeDetailView = NodeDetailView;
window.ThemeDetailView = ThemeDetailView;
window.relationshipManagerView = relationshipManagerView;
window.relationshipGraphView = relationshipGraphView;
