/**
 * Rhizome Thinking - Search Module
 */

// Track if result has been processed to avoid duplicate toasts
let searchResultProcessed = false;

// Search View - Streaming with progress
async function performSearch() {
    const input = document.getElementById('searchInput');
    const query = input.value.trim();

    if (!query) {
        ui.showToast('请输入查询内容', 'error');
        return;
    }

    // Close any existing search
    searchProgress.close();
    
    const searchBtn = document.getElementById('searchBtn');
    ui.showLoading(searchBtn);
    searchProgress.show();
    
    try {
        const timeRange = document.getElementById('timeRange').value;
        const limit = parseInt(document.getElementById('limitSelect').value);
        
        // 获取搜索模式
        const activeModeBtn = document.querySelector('.search-mode-btn.active');
        const searchMode = activeModeBtn ? activeModeBtn.dataset.mode : 'balanced';

        const requestData = {
            anchor: query,
            modifiers: {
                time_range: timeRange,
                tags: state.selectedTags,
                limit: limit,
                search_mode: searchMode,
                // 保留 min_similarity 用于向量搜索部分
                min_similarity: 0.3
            }
        };

        // Use streaming search with progress
        await performStreamingSearch(requestData);

    } catch (error) {
        ui.showToast(`查询失败: ${error.message}`, 'error');
        searchProgress.setError(error.message);
        console.error('Search error:', error);
    } finally {
        ui.hideLoading(searchBtn);
        searchProgress.hide();
    }
}

function performStreamingSearch(requestData) {
    return new Promise((resolve, reject) => {
        // Reset the result processed flag for new search
        searchResultProcessed = false;
        
        const query = requestData.anchor;
        const displayLimit = requestData.modifiers?.limit || 20;  // 前端显示限制
        
        console.log('[Mobile Debug] Starting streaming search:', query);
        console.log('[Mobile Debug] Request data:', JSON.stringify(requestData));
        console.log('[Mobile Debug] Display limit:', displayLimit);
        
        // Detect mobile
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        console.log('[Mobile Debug] Is mobile:', isMobile);
        
        // Create EventSource for streaming
        // Note: EventSource doesn't support POST, so we use a workaround
        // by creating a temporary fetch-based stream reader
        
        const url = `${window.location.origin}/api/v1/query/themes/stream/fast`;
        console.log('[Mobile Debug] Fetch URL:', url);
        
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData),
            // Add cache control for mobile
            cache: 'no-cache'
        }).then(response => {
            console.log('[Mobile Debug] Fetch response:', response.status, response.ok);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let chunkCount = 0;
            
            function readStream() {
                reader.read().then(({ done, value }) => {
                    if (done) {
                        console.log('[Mobile Debug] Stream done, total chunks:', chunkCount);
                        searchProgress.close();
                        resolve();
                        return;
                    }
                    
                    chunkCount++;
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop(); // Keep incomplete line in buffer
                    
                    lines.forEach(line => {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6));
                                console.log('[Mobile Debug] Stream data:', data.type, data.percent || '');
                                handleStreamData(data, query, displayLimit);
                            } catch (e) {
                                console.error('[Mobile Debug] Failed to parse stream data:', e, line);
                            }
                        }
                    });
                    
                    readStream();
                }).catch(error => {
                    console.error('[Mobile Debug] Stream read error:', error);
                    searchProgress.close();
                    reject(error);
                });
            }
            
            readStream();
        }).catch(error => {
            // Fallback to non-streaming search if streaming fails
            console.warn('[Mobile Debug] Streaming search failed, falling back:', error);
            performFallbackSearch(requestData).then(resolve).catch(reject);
        });
    });
}

function handleStreamData(data, query, displayLimit = 20) {
    if (data.type === 'progress') {
        searchProgress.updateProgress(data.percent, data.message, data.detail);
        searchProgress.updateSteps(data.stage);
    } else if (data.type === 'result') {
        // Only process result once to avoid duplicate toasts
        if (!searchResultProcessed) {
            searchResultProcessed = true;
            renderThemeResults(data.results, query, displayLimit, data.total_themes);
            ui.showToast(`找到 ${data.total_themes} 个主题`, 'success');
        }
    } else if (data.type === 'error') {
        throw new Error(data.message);
    }
}

async function performFallbackSearch(requestData) {
    // Fallback to regular API if streaming is not supported
    searchProgress.updateProgress(10, '正在搜索...', '使用传统搜索模式');
    
    try {
        const response = await api.themeQuery(requestData);
        renderThemeResults(response.results, requestData.anchor);
        searchProgress.updateProgress(100, '搜索完成', '');
    } catch (error) {
        throw error;
    }
}

function renderThemeResults(results, query, displayLimit = 20, totalThemes = 0) {
    const container = document.getElementById('searchResults');

    if (!results || results.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>未找到与 "${escapeHtml(query)}" 相关的主题</p>
            </div>
        `;
        return;
    }

    // 计算总主题数
    const actualTotal = totalThemes || results.reduce((sum, cat) => sum + (cat.themes?.length || 0), 0);
    
    // 收集所有主题到一个列表
    let allThemes = [];
    for (const category of results) {
        if (!category.themes || category.themes.length === 0) continue;
        for (const themeData of category.themes) {
            allThemes.push({
                ...themeData,
                tag: category.tag,
                tag_display_name: category.tag_display_name
            });
        }
    }
    
    // 根据匹配分数排序
    allThemes.sort((a, b) => (b.match_score || 0) - (a.match_score || 0));
    
    // 判断是否需要截断
    const shouldTruncate = allThemes.length > displayLimit;
    const themesToShow = shouldTruncate ? allThemes.slice(0, displayLimit) : allThemes;
    const remainingCount = allThemes.length - displayLimit;
    
    // 按分类重新组织要显示的主题
    const categorizedThemes = {};
    for (const theme of themesToShow) {
        if (!categorizedThemes[theme.tag]) {
            categorizedThemes[theme.tag] = {
                tag: theme.tag,
                tag_display_name: theme.tag_display_name,
                themes: []
            };
        }
        categorizedThemes[theme.tag].themes.push(theme);
    }
    
    // 按原始顺序排列分类
    const tagOrder = ["definitive", "inferred", "vague", "needs_thinking", "cross-domain"];
    const orderedCategories = tagOrder
        .map(tag => categorizedThemes[tag])
        .filter(cat => cat !== undefined);

    let html = '<div class="theme-results">';
    
    // 显示结果统计
    if (shouldTruncate) {
        html += `
            <div class="results-summary">
                <span class="results-count">显示前 ${displayLimit} 个结果（共 ${actualTotal} 个）</span>
            </div>
        `;
    }

    for (const category of orderedCategories) {
        html += `
            <div class="theme-category">
                <div class="theme-category-header">
                    <div class="theme-category-title">
                        <span class="tag-badge tag-${category.tag}">${escapeHtml(category.tag_display_name)}</span>
                        <span class="theme-count">${category.themes.length} 个主题</span>
                    </div>
                </div>
                <div class="theme-list">
                    ${category.themes.map((themeData, index) => renderThemeCard(themeData, category.tag, index)).join('')}
                </div>
            </div>
        `;
    }
    
    // 添加"显示全部"按钮
    if (shouldTruncate) {
        html += `
            <div class="show-more-container">
                <button class="show-more-btn" id="showAllResults">
                    <span>显示全部 ${actualTotal} 个结果</span>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M6 9l6 6 6-6"/>
                    </svg>
                </button>
            </div>
        `;
    }

    html += '</div>';
    container.innerHTML = html;
    
    // 添加"显示全部"按钮事件监听
    if (shouldTruncate) {
        const showAllBtn = document.getElementById('showAllResults');
        if (showAllBtn) {
            showAllBtn.addEventListener('click', () => {
                renderAllThemeResults(results, query, actualTotal);
            });
        }
    }

    // Add event listeners for "打开" buttons using event delegation for better mobile support
    container.addEventListener('click', (e) => {
        const btn = e.target.closest('.theme-open-btn');
        if (!btn) return;
        
        e.preventDefault();
        e.stopPropagation();
        console.log('[Mobile Debug] Open button clicked (delegation)');
        
        const themeId = btn.dataset.themeId;
        const card = container.querySelector(`[data-theme-id="${themeId}"]`);
        
        if (card && typeof windowManager !== 'undefined' && windowManager) {
            const themeDataStr = card.dataset.themeData;
            console.log('[Mobile Debug] themeDataStr length:', themeDataStr?.length);
            if (themeDataStr) {
                try {
                    // Try to parse the data
                    let themeData;
                    try {
                        themeData = JSON.parse(themeDataStr);
                    } catch (e) {
                        // Try with entity replacement
                        themeData = JSON.parse(themeDataStr.replace(/&#39;/g, "'"));
                    }
                    console.log('[Mobile Debug] Opening theme window:', themeData?.theme?.id);
                    windowManager.openThemeWindow(themeData);
                } catch (err) {
                    console.error('[Mobile Debug] Failed to parse theme data:', err);
                    ui.showToast('无法打开主题详情', 'error');
                }
            } else {
                console.error('[Mobile Debug] No theme data found');
                ui.showToast('主题数据缺失', 'error');
            }
        } else {
            console.error('[Mobile Debug] Card or windowManager not found:', { 
                hasCard: !!card, 
                windowManagerExists: typeof windowManager !== 'undefined',
                windowManager: !!windowManager 
            });
        }
    });
    
}

// 显示所有主题结果（不截断）
function renderAllThemeResults(results, query, totalThemes) {
    const container = document.getElementById('searchResults');
    
    // 按分类组织主题
    const tagOrder = ["definitive", "inferred", "vague", "needs_thinking", "cross-domain"];
    const tagDisplayNames = {
        "definitive": "明确结论",
        "inferred": "推断结论",
        "vague": "模糊感知",
        "needs_thinking": "待思考问题",
        "cross-domain": "跨域连接"
    };
    
    let html = '<div class="theme-results">';
    
    // 显示结果统计
    html += `
        <div class="results-summary">
            <span class="results-count">显示全部 ${totalThemes} 个结果</span>
            <button class="collapse-btn" id="collapseResults">收起</button>
        </div>
    `;
    
    // 按固定顺序遍历分类
    for (const tag of tagOrder) {
        const category = results.find(r => r.tag === tag);
        if (!category || !category.themes || category.themes.length === 0) continue;
        
        html += `
            <div class="theme-category">
                <div class="theme-category-header">
                    <div class="theme-category-title">
                        <span class="tag-badge tag-${tag}">${escapeHtml(tagDisplayNames[tag])}</span>
                        <span class="theme-count">${category.themes.length} 个主题</span>
                    </div>
                </div>
                <div class="theme-list">
                    ${category.themes.map((themeData, index) => renderThemeCard(themeData, tag, index)).join('')}
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    container.innerHTML = html;
    
    // 添加收起按钮事件
    const collapseBtn = document.getElementById('collapseResults');
    if (collapseBtn) {
        collapseBtn.addEventListener('click', () => {
            // 重新渲染截断版本（使用默认limit）
            renderThemeResults(results, query, 20, totalThemes);
        });
    }
    
    // 添加事件监听（复用之前的逻辑）
    container.addEventListener('click', (e) => {
        const btn = e.target.closest('.theme-open-btn');
        if (!btn) return;
        
        e.preventDefault();
        e.stopPropagation();
        
        const themeId = btn.dataset.themeId;
        const card = container.querySelector(`[data-theme-id="${themeId}"]`);
        
        if (card && typeof windowManager !== 'undefined' && windowManager) {
            const themeDataStr = card.dataset.themeData;
            if (themeDataStr) {
                try {
                    let themeData;
                    try {
                        themeData = JSON.parse(themeDataStr);
                    } catch (e) {
                        themeData = JSON.parse(themeDataStr.replace(/&#39;/g, "'"));
                    }
                    windowManager.openThemeWindow(themeData);
                } catch (err) {
                    console.error('Failed to parse theme data:', err);
                    ui.showToast('无法打开主题详情', 'error');
                }
            }
        }
    });
}

function renderThemeCard(themeData, tag, index) {
    const theme = themeData.theme;
    const themeId = `theme-${tag}-${index}`;

    return `
        <div class="theme-card" data-theme-id="${themeId}" data-theme-data='${JSON.stringify(themeData).replace(/'/g, "&#39;")}'>
            <div class="theme-card-header">
                <div class="theme-summary">${escapeHtml(theme.summary)}</div>
                <div class="theme-meta">
                    <span class="theme-node-count">${theme.node_count} 条笔记</span>
                    <button type="button" class="theme-open-btn" data-theme-id="${themeId}">
                        打开
                    </button>
                </div>
            </div>
        </div>
    `;
}

function renderNodeCard(item, index = 0) {
    const similarityPercent = Math.round(item.similarity * 100);
    const tagsHtml = ui.renderTagsInOrder(item.tags, 'node-tag');
    // 显示排名和相似度
    const rankBadge = index > 0 ? `<span class="node-rank">#${index}</span>` : '';
    
    return `
        <div class="node-card" data-node-id="${item.id}">
            <div class="node-card-header">
                <div class="node-proposition">${escapeHtml(item.proposition)}</div>
                <div class="node-similarity">${rankBadge} ${similarityPercent}%</div>
            </div>
            <div class="node-meta">
                <div class="node-tags">${tagsHtml}</div>
                <span>${ui.formatDate(item.timestamp)}</span>
            </div>
        </div>
    `;
}
