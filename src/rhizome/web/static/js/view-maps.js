/**
 * Rhizome Thinking - Epistemic Map & Graph Views
 */

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

// ===== Relationship Graph (关系图谱) =====
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

            // Update theme filter
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

        // Tag filter
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

        // Relation type filter
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

        // Add nodes
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

        // Add edges
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

        // Initialize Cytoscape
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

        // Node click event
        this.cy.on('tap', 'node', (evt) => {
            const node = evt.target;
            const nodeId = node.id();
            this.showNodeTooltip(node);
        });

        // Edge hover effect
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

        // Node hover effect
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
