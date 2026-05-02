/**
 * Rhizome Thinking - Node Operations (Submit, Batch, Precise Search)
 */

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
