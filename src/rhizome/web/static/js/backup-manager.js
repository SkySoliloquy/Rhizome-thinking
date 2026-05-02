/**
 * Rhizome Thinking - Backup Manager
 */

const backupManager = {
    pendingRestoreName: null,
    pendingDeleteName: null,

    async loadBackups() {
        try {
            const response = await api.getBackups();
            this.renderBackups(response.backups);
        } catch (error) {
            console.error('Failed to load backups:', error);
            document.getElementById('backupList').innerHTML = '<p style="color: var(--color-text-muted);">加载备份列表失败</p>';
        }
    },

    renderBackups(backups) {
        const container = document.getElementById('backupList');
        if (!backups || backups.length === 0) {
            container.innerHTML = '<p style="color: var(--color-text-muted);">暂无备份</p>';
            return;
        }

        // Store backups data for reference
        this.backupsData = backups;

        container.innerHTML = backups.map((backup, index) => {
            return `
            <div class="backup-item" style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px;
                background: var(--color-bg-tertiary);
                border-radius: 8px;
                margin-bottom: 8px;
            " data-backup-index="${index}">
                <div class="backup-info">
                    <div style="font-weight: 500;">${escapeHtml(backup.name)}</div>
                    <div style="font-size: 0.75rem; color: var(--color-text-muted);">
                        ${new Date(backup.created_at).toLocaleString('zh-CN')} · ${backup.node_count} 个节点 · ${backup.size_mb} MB
                    </div>
                </div>
                <div class="backup-actions" style="display: flex; gap: 8px;">
                    <button class="btn-secondary btn-sm backup-download-btn" data-backup-index="${index}">下载</button>
                    <button class="btn-secondary btn-sm backup-restore-btn" data-backup-index="${index}">恢复</button>
                    <button class="btn-danger btn-sm backup-delete-btn" data-backup-index="${index}">删除</button>
                </div>
            </div>
        `}).join('');

        // Attach event listeners after rendering
        this.attachBackupEventListeners();
    },

    attachBackupEventListeners() {
        const container = document.getElementById('backupList');

        // Download buttons
        container.querySelectorAll('.backup-download-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                // Use currentTarget to get the button element, not the clicked child
                const button = e.currentTarget;
                const index = parseInt(button.dataset.backupIndex);
                const backup = this.backupsData[index];
                if (backup) {
                    console.log('[Backup] Download:', backup.name, 'Index:', index);
                    this.downloadBackup(backup.name);
                } else {
                    console.error('[Backup] Download failed - no backup at index:', index);
                }
            });
        });

        // Restore buttons - open confirm modal
        container.querySelectorAll('.backup-restore-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const button = e.currentTarget;
                const index = parseInt(button.dataset.backupIndex);
                const backup = this.backupsData[index];
                if (backup) {
                    console.log('[Backup] Restore:', backup.name, 'Index:', index);
                    this.openRestoreModal(backup.name);
                } else {
                    console.error('[Backup] Restore failed - no backup at index:', index);
                }
            });
        });

        // Delete buttons - open confirm modal
        container.querySelectorAll('.backup-delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const button = e.currentTarget;
                const index = parseInt(button.dataset.backupIndex);
                const backup = this.backupsData[index];
                if (backup) {
                    console.log('[Backup] Delete:', backup.name, 'Index:', index);
                    this.openDeleteModal(backup.name);
                } else {
                    console.error('[Backup] Delete failed - no backup at index:', index);
                }
            });
        });
    },

    openRestoreModal(backupName) {
        this.pendingRestoreName = backupName;
        document.getElementById('restoreBackupName').textContent = backupName;
        document.getElementById('backupRestoreModal').style.display = 'flex';
    },

    closeRestoreModal() {
        document.getElementById('backupRestoreModal').style.display = 'none';
        this.pendingRestoreName = null;
    },

    async confirmRestoreBackup() {
        if (!this.pendingRestoreName) return;

        // Save the name before closing modal (which clears it)
        const backupName = this.pendingRestoreName;
        console.log('[Backup] Confirm restore:', backupName);

        try {
            ui.showToast('正在恢复备份...');
            this.closeRestoreModal();
            await api.restoreBackup(backupName, true);
            ui.showToast('备份恢复成功，页面将刷新');
            setTimeout(() => window.location.reload(), 1500);
        } catch (error) {
            ui.showToast(`恢复备份失败: ${error.message}`, 'error');
        }
    },

    openDeleteModal(backupName) {
        this.pendingDeleteName = backupName;
        document.getElementById('deleteBackupName').textContent = backupName;
        document.getElementById('backupDeleteModal').style.display = 'flex';
    },

    closeDeleteModal() {
        document.getElementById('backupDeleteModal').style.display = 'none';
        this.pendingDeleteName = null;
    },

    async confirmDeleteBackup() {
        if (!this.pendingDeleteName) return;

        // Save the name before closing modal (which clears it)
        const backupName = this.pendingDeleteName;
        console.log('[Backup] Confirm delete:', backupName);

        try {
            this.closeDeleteModal();
            await api.deleteBackup(backupName);
            ui.showToast('备份已删除');
            await this.loadBackups();
        } catch (error) {
            ui.showToast(`删除备份失败: ${error.message}`, 'error');
        }
    },

    async createBackup() {
        try {
            const btn = document.getElementById('createBackupBtn');
            ui.showLoading(btn, '创建中...');
            const response = await api.createBackup();
            ui.showToast('备份创建成功');
            await this.loadBackups();
        } catch (error) {
            ui.showToast(`创建备份失败: ${error.message}`, 'error');
        } finally {
            const btn = document.getElementById('createBackupBtn');
            ui.hideLoading(btn);
        }
    },

    downloadBackup(backupName) {
        window.open(`${api.baseURL}/api/v1/backups/${encodeURIComponent(backupName)}/download`);
    },

    async importBackup(file) {
        if (!file) {
            ui.showToast('请选择备份文件', 'error');
            return;
        }

        if (!file.name.endsWith('.zip')) {
            ui.showToast('请选择 .zip 格式的备份文件', 'error');
            return;
        }

        try {
            ui.showToast('正在上传备份文件...');
            await api.uploadBackup(file);
            ui.showToast('备份导入成功');
            await this.loadBackups();
        } catch (error) {
            ui.showToast(`导入备份失败: ${error.message}`, 'error');
        }
    }
};
