/**
 * Rhizome Thinking - UI Helpers & Utilities
 */

const ui = {
    showToast(message, type = 'success') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 3000);
    },

    showLoading(element, text = '加载中...') {
        element.dataset.originalText = element.innerHTML;
        element.innerHTML = `<span class="loading"></span> ${text}`;
        element.disabled = true;
    },

    hideLoading(element) {
        if (element.dataset.originalText) {
            element.innerHTML = element.dataset.originalText;
            element.disabled = false;
        }
    },

    switchView(viewId, params = null) {
        document.querySelectorAll('.view').forEach(view => {
            view.classList.remove('active');
        });

        const targetView = document.getElementById(viewId);
        if (targetView) {
            targetView.classList.add('active');
        }

        const mainViews = ['searchView', 'addNodeView', 'outlineView', 'epistemicMapView', 'graphView', 'statsView', 'relationshipManagerView', 'relationshipGraphView'];
        if (mainViews.includes(viewId)) {
            document.querySelectorAll('.nav-item').forEach(item => {
                item.classList.remove('active');
                if (item.dataset.view === viewId) {
                    item.classList.add('active');
                }
            });
        }

        if (state.currentView && mainViews.includes(state.currentView)) {
            state.previousView = state.currentView;
        }

        state.currentView = viewId;

        if (viewId === 'statsView') {
            loadStats();
        } else if (viewId === 'outlineView') {
            if (window.outlineView) window.outlineView.init();
        } else if (viewId === 'epistemicMapView') {
            if (window.epistemicMapView) window.epistemicMapView.init();
        } else if (viewId === 'graphView') {
            if (window.graphView) window.graphView.init();
        } else if (viewId === 'relationshipManagerView') {
            if (window.relationshipManagerView) window.relationshipManagerView.init();
        } else if (viewId === 'relationshipGraphView') {
            if (window.relationshipGraphView) window.relationshipGraphView.init();
        } else if (viewId === 'nodeDetailView' && params?.nodeId) {
            if (window.NodeDetailView) window.NodeDetailView.show(params.nodeId);
        } else if (viewId === 'themeDetailView' && params?.themeId) {
            if (window.ThemeDetailView) window.ThemeDetailView.show(params.themeId);
        } else if (viewId === 'themeEvolutionView' && params?.themeId) {
            if (window.themeEvolutionView) window.themeEvolutionView.init(params.themeId);
        } else if (viewId === 'themeConflictView') {
            if (window.themeConflictView) window.themeConflictView.init(params?.themeId);
        }
    },

    formatDate(dateStr) {
        const date = new Date(dateStr);
        const now = new Date();
        const diff = now - date;

        const days = Math.floor(diff / (1000 * 60 * 60 * 24));

        if (days === 0) return '今天';
        if (days === 1) return '昨天';
        if (days < 7) return `${days}天前`;
        if (days < 30) return `${Math.floor(days / 7)}周前`;

        return date.toLocaleDateString('zh-CN');
    },

    TAG_ORDER: ['definitive', 'inferred', 'vague', 'needs_thinking', 'cross-domain'],

    getTagDisplayName(tag) {
        const names = {
            'definitive': '明确结论',
            'inferred': '推断结论',
            'vague': '模糊感知',
            'needs_thinking': '待思考',
            'cross-domain': '跨域连接'
        };
        return names[tag] || tag;
    },

    getTagColor(tag) {
        const colors = {
            'definitive': {
                bg: 'rgba(0, 184, 148, 0.15)',
                border: 'rgba(0, 184, 148, 0.3)',
                text: '#00b894'
            },
            'inferred': {
                bg: 'rgba(108, 92, 231, 0.15)',
                border: 'rgba(108, 92, 231, 0.3)',
                text: '#a29bfe'
            },
            'vague': {
                bg: 'rgba(253, 203, 110, 0.15)',
                border: 'rgba(253, 203, 110, 0.3)',
                text: '#fdcb6e'
            },
            'needs_thinking': {
                bg: 'rgba(231, 76, 60, 0.15)',
                border: 'rgba(231, 76, 60, 0.3)',
                text: '#e74c3c'
            },
            'cross-domain': {
                bg: 'rgba(0, 206, 201, 0.15)',
                border: 'rgba(0, 206, 201, 0.3)',
                text: '#00cec9'
            }
        };
        return colors[tag] || {
            bg: 'var(--color-bg-tertiary)',
            border: 'rgba(255, 255, 255, 0.1)',
            text: 'var(--color-text-secondary)'
        };
    },

    renderTag(tag, className = 'node-tag') {
        const color = this.getTagColor(tag);
        const name = this.getTagDisplayName(tag);
        return `<span class="${className}" style="
            background: ${color.bg};
            border: 1px solid ${color.border};
            color: ${color.text};
        ">${name}</span>`;
    },

    renderTagsInOrder(tags, className = 'node-tag') {
        return this.TAG_ORDER.map(tagType => {
            if (tags.includes(tagType)) {
                return this.renderTag(tagType, className);
            } else {
                return `<span class="${className} tag-placeholder" style="
                    visibility: hidden;
                    pointer-events: none;
                "></span>`;
            }
        }).join('');
    }
};

const searchProgress = {
    eventSource: null,
    currentStage: 'submitting',

    stages: [
        'submitting',
        'loading_themes',
        'llm_reranking',
        'processing_results',
        'complete'
    ],

    show() {
        const progressEl = document.getElementById('searchProgress');
        if (progressEl) {
            progressEl.style.display = 'block';
            progressEl.classList.remove('error');
        }
        this.reset();
    },

    hide() {
        const progressEl = document.getElementById('searchProgress');
        if (progressEl) {
            setTimeout(() => {
                progressEl.style.display = 'none';
            }, 800);
        }
    },

    reset() {
        this.currentStage = 'submitting';
        this.updateProgress(0, '准备搜索', '');
        this.updateSteps('submitting');
    },

    updateProgress(percent, message, detail) {
        const fillEl = document.getElementById('progressFill');
        const stageEl = document.getElementById('progressStage');
        const percentEl = document.getElementById('progressPercent');
        const detailEl = document.getElementById('progressDetail');

        if (fillEl) fillEl.style.width = `${percent}%`;
        if (stageEl) stageEl.textContent = message;
        if (percentEl) percentEl.textContent = `${percent}%`;
        if (detailEl) detailEl.textContent = detail || '';
    },

    updateSteps(activeStage) {
        const steps = document.querySelectorAll('.step');
        const lines = document.querySelectorAll('.step-line');

        let activeIndex = -1;

        steps.forEach((step, index) => {
            const stepName = step.dataset.step;
            if (stepName === activeStage) {
                activeIndex = index;
            }
        });

        steps.forEach((step, index) => {
            const stepName = step.dataset.step;
            step.classList.remove('active', 'completed');

            if (stepName === activeStage) {
                step.classList.add('active');
            } else if (index < activeIndex) {
                step.classList.add('completed');
            }
        });

        lines.forEach((line, index) => {
            line.classList.remove('active');
            if (index < activeIndex) {
                line.classList.add('active');
            }
        });
    },

    setError(message) {
        const progressEl = document.getElementById('searchProgress');
        if (progressEl) {
            progressEl.classList.add('error');
        }
        this.updateProgress(0, '搜索出错', message);
    },

    close() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
};

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderMarkdown(text) {
    if (!text) return '';

    let html = escapeHtml(text);

    html = html.replace(/^#{2}\s+(.+)$/gm, '<h3 class="md-h3">$1</h3>');
    html = html.replace(/^#{3}\s+(.+)$/gm, '<h4 class="md-h4">$1</h4>');
    html = html.replace(/`(.+?)`/g, '<code class="md-code">$1</code>');
    html = html.replace(/(^|[\s\(])\*\*(.+?)\*\*([\s\)\.,;:!?]|$)/g, '$1<strong>$2</strong>$3');
    html = html.replace(/(^|[\s\(])\*(?!\*)(.+?)(?<!\*)\*([\s\)\.,;:!?]|$)/g, '$1<em>$2</em>$3');
    html = html.replace(/^[-\*]\s+(.+)$/gm, '<li class="md-li">$1</li>');
    html = html.replace(/^\d+\.\s+(.+)$/gm, '<li class="md-li">$1</li>');
    html = html.replace(/^>\s+(.+)$/gm, '<blockquote class="md-blockquote">$1</blockquote>');

    const lines = html.split('\n');
    const result = [];
    let currentList = [];
    let currentParagraph = [];

    function flushParagraph() {
        if (currentParagraph.length > 0) {
            const content = currentParagraph.join('<br>');
            result.push('<p class="md-p">' + content + '</p>');
            currentParagraph = [];
        }
    }

    function flushList() {
        if (currentList.length > 0) {
            result.push('<ul class="md-ul">' + currentList.join('') + '</ul>');
            currentList = [];
        }
    }

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();

        if (!line) {
            flushParagraph();
            continue;
        }

        if (line.startsWith('<h3') || line.startsWith('<h4') || line.startsWith('<blockquote')) {
            flushParagraph();
            flushList();
            result.push(line);
            continue;
        }

        if (line.startsWith('<li class="md-li">')) {
            flushParagraph();
            currentList.push(line);
            continue;
        }

        if (currentList.length > 0) {
            flushList();
        }
        currentParagraph.push(line);
    }

    flushParagraph();
    flushList();

    return result.join('\n');
}
