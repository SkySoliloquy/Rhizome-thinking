/**
 * Rhizome Thinking - Node Detail View
 */

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
        const versionBadge = node.refined_content_version > 1 ? `<span class="version-badge">v${node.refined_content_version}</span>` : '';
        const lastRefinedText = node.last_refined_at ? `<span class="last-refined">更新于 ${new Date(node.last_refined_at).toLocaleString('zh-CN')}</span>` : '';

        container.innerHTML = `
            <div class="node-detail-container">
                <div class="node-detail-section title-section">
                    <h2>${escapeHtml(node.processed.proposition)}</h2>
                    <div style="font-size: 0.85rem; color: var(--color-text-muted); margin-top: 8px;">
                        节点标题 · ${new Date(node.timestamp).toLocaleDateString('zh-CN')}
                    </div>
                </div>
                <div class="node-detail-section refined-content-section">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <h4>📝 精炼内容 ${versionBadge}</h4>
                        <button class="btn-icon" onclick="windowManager.regenerateRefinedContent('${node.id}')" title="重新生成">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="23 4 23 10 17 10"></polyline>
                                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                            </svg>
                        </button>
                    </div>
                    ${hasRefinedContent 
                        ? `<div class="node-detail-content">${renderMarkdown(node.refined_content)}</div>${lastRefinedText}`
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
                    <ul style="margin-left: var(--spacing-md);">${questionsHtml}</ul>
                </div>
                <div class="node-detail-section">
                    <h4>来源</h4>
                    <div style="font-size: 0.875rem;">
                        ${node.source.type === 'original' ? '原创想法' : escapeHtml(node.source.title || '未指定')}
                        ${node.source.location ? `<br><span style="color: var(--color-text-muted)">${escapeHtml(node.source.location)}</span>` : ''}
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
            </div>
        `;
    },

    renderTags(tags) {
        return ui.renderTagsInOrder(tags, 'node-detail-tag');
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
                        <button class="raw-input-toggle" onclick="windowManager.toggleRawInput('${rawInputId}')">展开</button>
                    </div>
                    <div class="raw-input-expanded" id="${rawInputId}-expanded" style="display: none;">
                        ${escapeHtml(rawInput)}
                        <button class="raw-input-toggle" onclick="windowManager.toggleRawInput('${rawInputId}')">收起</button>
                    </div>
                </div>
            `;
        }
        return `<div class="node-detail-content" style="color: var(--color-text-secondary); font-size: 0.875rem;">${escapeHtml(rawInput)}</div>`;
    },

    getRelationName(relation) {
        const names = { 'support': '支持', 'contradict': '矛盾', 'extend': '延伸', 'source': '来源', 'analogy': '类比' };
        return names[relation] || relation;
    },

    renderError(message) {
        const container = document.getElementById('nodeDetailContent');
        if (container) {
            container.innerHTML = `<div class="empty-state"><p style="color: var(--color-danger)">加载失败: ${escapeHtml(message)}</p></div>`;
        }
    }
};
