/**
 * Rhizome Thinking - Theme Evolution & Conflict Views
 */

// ===== Theme Evolution View =====
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

        container.querySelectorAll('.apply-suggestion-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const suggestionId = e.currentTarget.dataset.suggestionId;
                this.applySuggestion(suggestionId);
            });
        });

        container.querySelectorAll('.reject-suggestion-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const suggestionId = e.currentTarget.dataset.suggestionId;
                this.rejectSuggestion(suggestionId);
            });
        });

        container.querySelectorAll('.rollback-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const version = parseInt(e.currentTarget.dataset.version);
                this.rollbackToVersion(version);
            });
        });

        container.querySelectorAll('.view-conflict-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const suggestionId = e.currentTarget.dataset.suggestionId;
                this.showConflictDetail(suggestionId);
            });
        });

        container.querySelectorAll('.toggle-diff-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const version = e.currentTarget.dataset.version;
                this.toggleVersionDiff(version);
            });
        });

        const refreshBtn = document.getElementById('refreshEvolutionBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadEvolutionData());
        }

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
            const [historyResponse, suggestionsResponse, conflictsResponse] = await Promise.all([
                fetch(`/api/v1/themes/${this.currentThemeId}/evolution`),
                fetch(`/api/v1/themes/evolution/suggestions?status=pending&theme_id=${this.currentThemeId}`),
                fetch(`/api/v1/themes/${this.currentThemeId}/conflicts`)
            ]);

            if (!historyResponse.ok) throw new Error('加载演化历史失败');
            this.evolutionData = await historyResponse.json();

            if (!suggestionsResponse.ok) throw new Error('加载建议失败');
            const suggestionsData = await suggestionsResponse.json();
            this.suggestions = suggestionsData.suggestions || [];

            if (!conflictsResponse.ok) throw new Error('加载冲突失败');
            this.conflictsData = await conflictsResponse.json();

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
            container.innerHTML = `<div class="empty-state"><p style="color: var(--color-danger)">加载失败: ${error.message}</p></div>`;
        }
    },

    render() {
        const container = document.getElementById('themeEvolutionContent');
        if (!container) return;

        let html = '<div class="evolution-container">';

        if (this.suggestions.length > 0) {
            html += this.renderPendingSuggestions();
        }

        if (this.conflictsData && this.conflictsData.total_conflicts > 0) {
            html += this.renderConflicts();
        }

        html += this.renderTimeline();
        html += '</div>';
        container.innerHTML = html;

        this.bindEvents();
    },

    renderPendingSuggestions() {
        return `
            <div class="evolution-section suggestions-section">
                <h4 class="section-title">待处理的演进建议 (${this.suggestions.length})</h4>
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
                </div>
                <div class="suggestion-actions">
                    <button class="btn-primary apply-suggestion-btn" data-suggestion-id="${suggestion.id}">应用</button>
                    <button class="btn-secondary reject-suggestion-btn" data-suggestion-id="${suggestion.id}">拒绝</button>
                </div>
            </div>
        `;
    },

    renderConflicts() {
        const conflicts = this.conflictsData.conflicts || [];
        return `
            <div class="evolution-section conflicts-section">
                <h4 class="section-title">检测到的冲突 (${this.conflictsData.total_conflicts})</h4>
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
                            <button class="btn-link view-conflict-btn" data-suggestion-id="${conflict.id}">查看详情</button>
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
                    <div class="empty-state"><p>暂无演化历史</p></div>
                </div>
            `;
        }

        return `
            <div class="evolution-section timeline-section">
                <h4 class="section-title">演化历史 (${history.length} 个版本)</h4>
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
                            <button class="btn-link rollback-btn" data-version="${version.version}">回滚到此版本</button>
                            <button class="btn-link toggle-diff-btn" data-version="${version.version}">对比差异</button>
                        ` : ''}
                    </div>
                    <div class="version-diff" id="diff-${version.version}" style="display: none;"></div>
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
        if (!confirm(`确定要回滚到版本 ${version} 吗？`)) return;

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

        if (window.windowManager) {
            const content = this.buildConflictDetailContent(suggestion);
            windowManager.openCustomWindow(`conflict-${suggestionId}`, '冲突详情', content);
        }
    },

    buildConflictDetailContent(suggestion) {
        return `
            <div class="conflict-detail">
                <div class="detail-row"><label>冲突类型:</label><span>${this.getConflictTypeName(suggestion.conflict_type)}</span></div>
                <div class="detail-row"><label>原因:</label><p>${this.escapeHtml(suggestion.reason)}</p></div>
                <div class="detail-row"><label>建议的核心命题:</label><p>${this.escapeHtml(suggestion.suggested_summary || '无变化')}</p></div>
                <div class="detail-row"><label>建议的标签:</label><p>${suggestion.suggested_tag ? this.getTagName(suggestion.suggested_tag) : '无变化'}</p></div>
            </div>
        `;
    },

    toggleVersionDiff(version) {
        const diffEl = document.getElementById(`diff-${version}`);
        if (!diffEl) return;

        if (diffEl.style.display === 'none') {
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
                <div class="diff-header"><span>版本 ${version} → 版本 ${this.evolutionData.current_version}</span></div>
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
        const names = { 'stable': '稳定', 'evolving': '演化中', 'merged': '已合并', 'deprecated': '已废弃' };
        return names[status] || status;
    },

    getConflictTypeName(type) {
        const names = {
            'definition_change': '定义变化', 'scope_expansion': '范围扩展', 'scope_reduction': '范围缩减',
            'tag_mismatch': '标签不匹配', 'semantic_drift': '语义漂移', 'node_conflict': '节点冲突',
            'merge_suggested': '建议合并', 'split_suggested': '建议拆分'
        };
        return names[type] || type;
    },

    getTagName(tag) {
        const names = { 'definitive': '明确结论', 'inferred': '推断结论', 'vague': '模糊感知', 'needs_thinking': '待思考', 'cross-domain': '跨域连接' };
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

// ===== Theme Conflict View =====
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
            const response = await fetch('/api/v1/themes/evolution/suggestions?status=pending');
            if (!response.ok) throw new Error('加载冲突失败');

            const data = await response.json();
            this.conflicts = data.suggestions || [];

            if (this.currentThemeId) {
                this.conflicts = this.conflicts.filter(c => c.theme_id === this.currentThemeId);
            }

            this.render();

        } catch (error) {
            console.error('Theme conflict load error:', error);
            container.innerHTML = `<div class="empty-state"><p style="color: var(--color-danger)">加载失败: ${error.message}</p></div>`;
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

        const groupedConflicts = this.groupByType(this.conflicts);

        let html = '<div class="conflicts-container">';
        html += `
            <div class="conflicts-summary">
                <div class="summary-stat"><span class="stat-value">${this.conflicts.length}</span><span class="stat-label">待处理冲突</span></div>
                <div class="summary-stat"><span class="stat-value">${Object.keys(groupedConflicts).length}</span><span class="stat-label">冲突类型</span></div>
            </div>
        `;

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
                </div>
                <div class="conflict-detail-actions">
                    <button class="btn-primary resolve-conflict-btn" data-conflict-id="${conflict.id}">应用建议</button>
                    <button class="btn-secondary" onclick="themeEvolutionView.rejectSuggestion('${conflict.id}')">忽略</button>
                </div>
            </div>
        `;
    },

    groupByType(conflicts) {
        return conflicts.reduce((groups, conflict) => {
            const type = conflict.conflict_type;
            if (!groups[type]) groups[type] = [];
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
