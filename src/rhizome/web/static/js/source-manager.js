/**
 * Rhizome Thinking - Source Manager
 */

const sourceManager = {
    sources: [],
    
    async init() {
        await this.loadSources();
        this.setupEventListeners();
    },
    
    async loadSources() {
        try {
            this.sources = await api.getSources();
            this.renderSourceSelect();
        } catch (error) {
            console.error('Failed to load sources:', error);
            // Fallback to default sources
            this.sources = [
                { id: 'original', name: '原创想法', description: '', is_builtin: true },
                { id: 'book', name: '书籍', description: '', is_builtin: true },
                { id: 'paper', name: '论文', description: '', is_builtin: true },
                { id: 'article', name: '文章', description: '', is_builtin: true }
            ];
            this.renderSourceSelect();
        }
    },
    
    renderSourceSelect() {
        const select = document.getElementById('sourceType');
        if (!select) return;
        
        select.innerHTML = this.sources.map(source => 
            `<option value="${source.id}">${source.name}</option>`
        ).join('');
    },
    
    renderSourceList() {
        const container = document.getElementById('sourceList');
        if (!container) return;
        
        container.innerHTML = this.sources.map(source => `
            <div class="source-item ${source.is_builtin ? 'builtin' : ''}" data-source-id="${source.id}">
                <div class="source-info">
                    <div class="source-name">
                        ${source.is_builtin ? '<span class="source-badge">内置</span>' : ''}
                        <span class="source-name-text">${escapeHtml(source.name)}</span>
                    </div>
                    ${source.description ? `<div class="source-desc">${escapeHtml(source.description)}</div>` : ''}
                </div>
                ${!source.is_builtin ? `
                    <div class="source-actions">
                        <button class="source-action-btn" onclick="sourceManager.startEditSource('${source.id}')">编辑</button>
                        <button class="source-action-btn delete" onclick="sourceManager.deleteSource('${source.id}')">删除</button>
                    </div>
                ` : ''}
            </div>
        `).join('');
    },
    
    startEditSource(sourceId) {
        const source = this.sources.find(s => s.id === sourceId);
        if (!source) return;
        
        const itemEl = document.querySelector(`.source-item[data-source-id="${sourceId}"]`);
        if (!itemEl) return;
        
        const nameEl = itemEl.querySelector('.source-name');
        const actionsEl = itemEl.querySelector('.source-actions');
        
        // Replace name with input field
        nameEl.innerHTML = `
            <input type="text" class="source-edit-input" value="${escapeHtml(source.name)}" id="edit-source-name-${sourceId}">
        `;
        
        // Replace actions with save/cancel buttons
        actionsEl.innerHTML = `
            <button class="source-action-btn save" onclick="sourceManager.saveEditSource('${sourceId}')">保存</button>
            <button class="source-action-btn cancel" onclick="sourceManager.cancelEditSource('${sourceId}')">取消</button>
        `;
        
        // Focus input
        const input = document.getElementById(`edit-source-name-${sourceId}`);
        if (input) {
            input.focus();
            input.select();
            // Enter to save, Escape to cancel
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.saveEditSource(sourceId);
            });
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') this.cancelEditSource(sourceId);
            });
        }
    },
    
    cancelEditSource(sourceId) {
        // Just re-render to restore original state
        this.renderSourceList();
    },
    
    async saveEditSource(sourceId) {
        const input = document.getElementById(`edit-source-name-${sourceId}`);
        if (!input) return;
        
        const newName = input.value.trim();
        const source = this.sources.find(s => s.id === sourceId);
        
        if (!newName) {
            ui.showToast('来源名称不能为空', 'error');
            return;
        }
        
        if (newName === source.name) {
            this.cancelEditSource(sourceId);
            return;
        }
        
        try {
            await api.updateSource(sourceId, { name: newName });
            await this.loadSources();
            this.renderSourceList();
            ui.showToast('来源类型更新成功');
        } catch (error) {
            ui.showToast(`更新失败: ${error.message}`, 'error');
        }
    },
    
    openModal() {
        this.renderSourceList();
        document.getElementById('sourceManagerModal').style.display = 'flex';
    },
    
    closeModal() {
        document.getElementById('sourceManagerModal').style.display = 'none';
        // Clear input fields
        document.getElementById('newSourceName').value = '';
        document.getElementById('newSourceDesc').value = '';
    },
    
    async addSource() {
        const nameInput = document.getElementById('newSourceName');
        const descInput = document.getElementById('newSourceDesc');
        
        const name = nameInput.value.trim();
        if (!name) {
            ui.showToast('请输入来源名称', 'error');
            return;
        }
        
        try {
            await api.createSource({
                name: name,
                description: descInput.value.trim() || null
            });
            
            await this.loadSources();
            this.renderSourceList();
            
            nameInput.value = '';
            descInput.value = '';
            
            ui.showToast('来源类型添加成功');
        } catch (error) {
            ui.showToast(`添加失败: ${error.message}`, 'error');
        }
    },
    
    async deleteSource(sourceId) {
        if (!window.confirm('确定要删除这个来源类型吗？')) return;
        
        try {
            await api.deleteSource(sourceId);
            await this.loadSources();
            this.renderSourceList();
            ui.showToast('来源类型删除成功');
        } catch (error) {
            ui.showToast(`删除失败: ${error.message}`, 'error');
        }
    },
    
    setupEventListeners() {
        // Manage sources button
        const manageBtn = document.getElementById('manageSourcesBtn');
        if (manageBtn) {
            manageBtn.addEventListener('click', () => this.openModal());
        }
        
        // Close modal button
        const closeBtn = document.getElementById('closeSourceManager');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.closeModal());
        }
        
        // Add source button
        const addBtn = document.getElementById('addSourceBtn');
        if (addBtn) {
            addBtn.addEventListener('click', () => this.addSource());
        }
        
        // Close on backdrop click
        const modal = document.getElementById('sourceManagerModal');
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) this.closeModal();
            });
        }
    }
};
