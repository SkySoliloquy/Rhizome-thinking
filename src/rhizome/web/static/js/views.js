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

// ===== Export for use in app.js =====
window.outlineView = outlineView;
window.epistemicMapView = epistemicMapView;
window.graphView = graphView;
