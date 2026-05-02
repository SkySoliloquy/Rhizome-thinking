/**
 * Rhizome Thinking - Settings & Update Management
 */

let selectedVersionHash = null;
let updatePollInterval = null;

function openSettingsModal() {
    const modal = document.getElementById('settingsModal');
    if (modal) {
        modal.style.display = 'flex';
        // Reset state
        selectedVersionHash = null;
        document.getElementById('confirmUpdateBtn').disabled = true;
        document.getElementById('versionList').style.display = 'none';
        document.getElementById('updateProgress').style.display = 'none';
        // Load current version
        loadCurrentVersion();
    }
}

function closeSettingsModal() {
    const modal = document.getElementById('settingsModal');
    if (modal) {
        modal.style.display = 'none';
    }
    // Stop polling if active
    if (updatePollInterval) {
        clearInterval(updatePollInterval);
        updatePollInterval = null;
    }
}

async function loadCurrentVersion() {
    try {
        const response = await fetch('/api/v1/update/current-version');
        if (response.ok) {
            const data = await response.json();
            const shortVer = data.current_version_short || data.current_version || '未知';
            document.getElementById('currentVersionDisplay').textContent = shortVer;
        }
    } catch (error) {
        console.error('Failed to load current version:', error);
        document.getElementById('currentVersionDisplay').textContent = '未知';
    }
}

async function checkForUpdates() {
    const btn = document.getElementById('checkUpdateBtn');
    const versionList = document.getElementById('versionList');

    ui.showLoading(btn, '检查中...');
    versionList.style.display = 'none';
    document.getElementById('confirmUpdateBtn').disabled = true;

    try {
        const response = await fetch('/api/v1/update/check');
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            const errMsg = errData.detail || errData.message || `HTTP ${response.status}`;
            throw new Error(errMsg);
        }

        const data = await response.json();
        const versions = data.available_versions || [];
        const currentVersion = data.current_version || '';

        if (versions.length === 0) {
            ui.showToast(data.message || '当前已是最新版本');
            return;
        }

        renderVersionList(versions, currentVersion);
        versionList.style.display = 'block';
        ui.showToast(`发现 ${versions.length} 个可用版本`);
    } catch (error) {
        ui.showToast(`检查更新失败: ${error.message}`, 'error');
    } finally {
        ui.hideLoading(btn);
    }
}

function renderVersionList(versions, currentVersion) {
    const container = document.getElementById('versionList');

    container.innerHTML = versions.map(v => {
        const hash = v.commit_hash || v.hash || '';
        const isCurrent = hash === currentVersion || currentVersion.startsWith(hash) || hash.startsWith(currentVersion);
        const currentClass = isCurrent ? 'current' : '';
        const currentBadge = isCurrent ? '<span class="version-current-badge">当前</span>' : '';
        const shortHash = hash ? hash.substring(0, 7) : '';
        const dateStr = v.date ? new Date(v.date).toLocaleString('zh-CN') : (v.date || '');

        return `
            <div class="version-item ${currentClass}" data-hash="${hash}" onclick="selectVersion('${hash}')">
                <div class="version-info">
                    <div class="version-name">${shortHash} ${currentBadge}</div>
                    <div class="version-meta">${escapeHtml(dateStr)} · ${escapeHtml(v.author || '')}</div>
                    <div class="version-message">${escapeHtml(v.message || '')}</div>
                </div>
            </div>
        `;
    }).join('');
}

function selectVersion(hash) {
    selectedVersionHash = hash;

    // Update UI
    document.querySelectorAll('.version-item').forEach(item => {
        item.classList.remove('selected');
        if (item.dataset.hash === hash) {
            item.classList.add('selected');
        }
    });

    // Enable confirm button
    document.getElementById('confirmUpdateBtn').disabled = false;
}

async function performUpdate() {
    if (!selectedVersionHash) return;

    const btn = document.getElementById('confirmUpdateBtn');
    ui.showLoading(btn, '更新中...');

    try {
        const response = await fetch('/api/v1/update/perform', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_version: selectedVersionHash })
        });

        if (!response.ok) throw new Error('启动更新失败');

        document.getElementById('updateProgress').style.display = 'block';
        ui.showToast('更新已启动');

        // Start polling
        pollUpdateStatus();
    } catch (error) {
        ui.showToast(`更新失败: ${error.message}`, 'error');
        ui.hideLoading(btn);
    }
}

function pollUpdateStatus() {
    if (updatePollInterval) {
        clearInterval(updatePollInterval);
    }

    updatePollInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/v1/update/status');
            if (!response.ok) return;

            const status = await response.json();
            renderUpdateProgress(status);

            if (status.status === 'completed' || status.status === 'restarting') {
                clearInterval(updatePollInterval);
                updatePollInterval = null;
                ui.showToast('更新完成，页面将刷新');
                setTimeout(() => window.location.reload(), 3000);
            } else if (status.status === 'failed' || status.status === 'rolled_back') {
                clearInterval(updatePollInterval);
                updatePollInterval = null;
                const msg = status.error ? `更新失败: ${status.error}` : '更新失败';
                ui.showToast(msg, 'error');
                ui.hideLoading(document.getElementById('confirmUpdateBtn'));
            }
        } catch (error) {
            console.error('Poll update status error:', error);
        }
    }, 2000);
}

function renderUpdateProgress(status) {
    const progressText = document.getElementById('updateProgressText');
    const progressPercent = document.getElementById('updateProgressPercent');
    const progressFill = document.getElementById('updateProgressFill');

    const percent = status.progress || 0;
    progressText.textContent = status.message || '更新中...';
    progressPercent.textContent = `${percent}%`;
    progressFill.style.width = `${percent}%`;
}
