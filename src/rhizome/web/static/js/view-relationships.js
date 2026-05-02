/**
 * Rhizome Thinking - Relationship Manager View
 */

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

            // Filter unconfirmed edges
            this.suggestions = data.edges.filter(edge => !edge.confirmed) || [];

            // Update stats
            if (statsEl) {
                statsEl.innerHTML = `
                    <span>待确认: <strong>${this.suggestions.length}</strong></span>
                    <span>当前页: <strong>${this.currentPage}</strong>/${this.totalPages}</span>
                `;
            }

            // Calculate total pages
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

        // Pagination
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

            // Remove confirmed suggestion
            this.suggestions = this.suggestions.filter(s =>
                !(s.source === sourceId && s.target === targetId)
            );

            this.totalPages = Math.ceil(this.suggestions.length / this.pageSize) || 1;
            if (this.currentPage > this.totalPages) {
                this.currentPage = this.totalPages;
            }

            this.renderSuggestions();

            // Update stats
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

            // Remove rejected suggestion
            this.suggestions = this.suggestions.filter(s =>
                !(s.source === sourceId && s.target === targetId)
            );

            this.totalPages = Math.ceil(this.suggestions.length / this.pageSize) || 1;
            if (this.currentPage > this.totalPages) {
                this.currentPage = this.totalPages;
            }

            this.renderSuggestions();

            // Update stats
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
