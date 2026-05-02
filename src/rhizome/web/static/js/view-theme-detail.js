/**
 * Rhizome Thinking - Theme Detail View
 */

const ThemeDetailView = {
    currentThemeId: null,

    async show(themeId) {
        this.currentThemeId = themeId;
        await this.loadTheme(themeId);
    },

    async loadTheme(themeId) {
        try {
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

        const evolutionBadges = {
            'stable': { text: '稳定', color: '#00b894' },
            'evolving': { text: '演进中', color: '#fdcb6e' },
            'merged': { text: '已合并', color: '#a29bfe' },
            'deprecated': { text: '已弃用', color: '#e74c3c' }
        };
        const evolutionBadge = evolutionBadges[theme.evolution_status] || evolutionBadges['stable'];

        const keywordsHtml = theme.keywords?.length
            ? theme.keywords.map(kw => `<span class="keyword-tag">${escapeHtml(kw)}</span>`).join('')
            : '<span style="color: var(--color-text-muted)">无关键词</span>';

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
                <div class="theme-detail-section">
                    <h4>关键词</h4>
                    <div class="keywords-list">${keywordsHtml}</div>
                </div>
                <div class="theme-detail-section">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <h4 style="margin: 0;">关联笔记 (${nodes?.length || 0})</h4>
                        <span style="font-size: 0.75rem; color: var(--color-text-muted);">按关联度排序</span>
                    </div>
                    <div class="theme-nodes-list">${nodesHtml}</div>
                </div>
                <div class="theme-detail-section">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <h4 style="margin: 0;">相关主题 (${relatedThemes?.length || 0})</h4>
                        <span style="font-size: 0.75rem; color: var(--color-text-muted);">基于共享笔记</span>
                    </div>
                    <div class="related-themes-list">${relatedHtml}</div>
                </div>
                <div class="theme-detail-section metadata-section">
                    <h4>元数据</h4>
                    <div style="font-size: 0.75rem; color: var(--color-text-muted);">
                        <span>ID: ${theme.id}</span><br>
                        <span>创建时间: ${new Date(theme.created_at).toLocaleString('zh-CN')}</span><br>
                        <span>更新时间: ${new Date(theme.updated_at).toLocaleString('zh-CN')}</span>
                    </div>
                </div>
            </div>
        `;

        this.attachEventListeners();
    },

    attachEventListeners() {
        document.querySelectorAll('.view-node-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const nodeId = btn.dataset.nodeId;
                if (nodeId && window.windowManager) {
                    window.windowManager.openSideWindow(nodeId);
                }
            });
        });

        document.querySelectorAll('.theme-node-item').forEach(item => {
            item.addEventListener('click', () => {
                const nodeId = item.dataset.nodeId;
                if (nodeId && window.windowManager) {
                    window.windowManager.openSideWindow(nodeId);
                }
            });
        });

        document.querySelectorAll('.view-theme-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const themeId = btn.dataset.themeId;
                if (themeId) {
                    this.loadTheme(themeId);
                }
            });
        });

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
            container.innerHTML = `<div class="empty-state"><p style="color: var(--color-danger)">加载失败: ${escapeHtml(message)}</p></div>`;
        }
    }
};
