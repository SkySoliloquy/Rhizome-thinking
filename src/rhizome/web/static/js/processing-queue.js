/**
 * Rhizome Thinking - Processing Queue
 */

const processingQueue = {
    maxConcurrent: 3,
    tasks: [],
    runningCount: 0,

    addTask(rawInput, data) {
        const taskId = Date.now() + Math.random();
        const task = {
            id: taskId,
            rawInput: rawInput.substring(0, 50) + (rawInput.length > 50 ? '...' : ''),
            status: 'pending', // pending, processing, completed, failed
            progress: 0,
            data: data,
            error: null
        };

        this.tasks.push(task);
        this.renderQueue();
        this.processQueue();

        return taskId;
    },

    async processQueue() {
        while (this.runningCount < this.maxConcurrent && this.tasks.some(t => t.status === 'pending')) {
            const task = this.tasks.find(t => t.status === 'pending');
            if (task) {
                this.runningCount++;
                task.status = 'processing';
                this.renderQueue();
                this.executeTask(task);
            }
        }
    },

    async executeTask(task) {
        try {
            // Simulate progress updates
            const progressInterval = setInterval(() => {
                if (task.progress < 90) {
                    task.progress += Math.random() * 15;
                    if (task.progress > 90) task.progress = 90;
                    this.renderQueue();
                }
            }, 500);

            const response = await api.createNode(task.data);
            clearInterval(progressInterval);
            task.progress = 100;
            task.status = 'completed';
            task.response = response;

            ui.showToast('节点创建成功！');

            // Show potential links if any
            if (response.potential_links && response.potential_links.length > 0) {
                showPotentialLinks(response.node, response.potential_links);
            }

        } catch (error) {
            task.status = 'failed';
            task.error = error.message;
            ui.showToast(`创建失败: ${error.message}`, 'error');
            console.error('Create node error:', error);
        } finally {
            this.runningCount--;
            this.renderQueue();
            this.processQueue();
            this.cleanupOldTasks();
        }
    },

    removeTask(taskId) {
        const task = this.tasks.find(t => t.id === taskId);
        if (task && task.status !== 'processing') {
            this.tasks = this.tasks.filter(t => t.id !== taskId);
            this.renderQueue();
        }
    },

    cleanupOldTasks() {
        // Remove completed tasks older than 5 minutes
        const fiveMinutesAgo = Date.now() - 5 * 60 * 1000;
        this.tasks = this.tasks.filter(t => {
            if (t.status === 'completed' && t.id < fiveMinutesAgo) {
                return false;
            }
            return true;
        });
        this.renderQueue();
    },

    renderQueue() {
        const container = document.getElementById('processingQueue');
        if (!container) return;

        if (this.tasks.length === 0) {
            container.innerHTML = '';
            return;
        }

        container.innerHTML = this.tasks.map(task => {
            let statusIcon = '';
            let progressBar = '';
            let removeBtnClass = '';
            let removeBtn = '';

            switch (task.status) {
                case 'pending':
                    statusIcon = '<svg class="clock" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>';
                    progressBar = `<div class="queue-progress"><div class="queue-progress-bar"><div class="queue-progress-bar-fill" style="width: 0%"></div></div><span class="queue-percent">等待中</span></div>`;
                    break;
                case 'processing':
                    statusIcon = '<div class="spinner"></div>';
                    progressBar = `<div class="queue-progress"><div class="queue-progress-bar"><div class="queue-progress-bar-fill" style="width: ${task.progress}%"></div></div><span class="queue-percent">${Math.round(task.progress)}%</span></div>`;
                    break;
                case 'completed':
                    statusIcon = '<svg class="checkmark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="20 6 9 17 4 12"></polyline></svg>';
                    progressBar = '<span class="queue-percent" style="color: var(--color-success)">已完成</span>';
                    removeBtnClass = ' completed';
                    removeBtn = '';
                    break;
                case 'failed':
                    statusIcon = '<svg class="cross" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
                    progressBar = `<span class="queue-percent" style="color: var(--color-danger)">失败</span>`;
                    break;
            }

            if (task.status !== 'completed') {
                removeBtn = `<button class="queue-remove${removeBtnClass}" onclick="processingQueue.removeTask(${task.id})">&times;</button>`;
            } else {
                removeBtn = `<button class="queue-remove${removeBtnClass}" disabled>&times;</button>`;
            }

            return `
                <div class="queue-item ${task.status}">
                    <div class="queue-status">${statusIcon}</div>
                    <div class="queue-content" title="${escapeHtml(task.rawInput)}">${escapeHtml(task.rawInput)}</div>
                    ${progressBar}
                    ${removeBtn}
                </div>
            `;
        }).join('');
    }
};
