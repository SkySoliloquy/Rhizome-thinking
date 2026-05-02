/**
 * Rhizome Thinking - Outline View
 */

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
