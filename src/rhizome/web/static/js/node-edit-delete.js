/**
 * Rhizome Thinking - Node Edit & Delete
 */

let currentEditingNodeId = null;
let currentDeletingNodeId = null;

async function openEditModal(nodeId) {
    try {
        const response = await api.getNode(nodeId);
        const node = response.node;
        currentEditingNodeId = nodeId;

        document.getElementById('editProposition').value = node.processed.proposition;
        document.getElementById('editRawInput').value = node.raw_input;
        document.getElementById('editSourceTitle').value = node.source.title || '';
        document.getElementById('editSourceLocation').value = node.source.location || '';
        document.getElementById('editOpenQuestions').value = (node.processed.open_questions || []).join('\n');

        // Set tags
        document.querySelectorAll('#editTags input[type="checkbox"]').forEach(cb => {
            cb.checked = node.tags.includes(cb.value);
        });

        document.getElementById('nodeEditModal').style.display = 'flex';
    } catch (error) {
        ui.showToast(`加载节点失败: ${error.message}`, 'error');
    }
}

function closeEditModal() {
    document.getElementById('nodeEditModal').style.display = 'none';
    currentEditingNodeId = null;
}

async function saveNodeEdit() {
    if (!currentEditingNodeId) return;

    const tags = Array.from(document.querySelectorAll('#editTags input[type="checkbox"]:checked')).map(cb => cb.value);
    const openQuestions = document.getElementById('editOpenQuestions').value.split('\n').filter(q => q.trim());

    const data = {
        proposition: document.getElementById('editProposition').value.trim(),
        raw_input: document.getElementById('editRawInput').value.trim(),
        tags: tags,
        open_questions: openQuestions,
        source_title: document.getElementById('editSourceTitle').value.trim() || null,
        source_location: document.getElementById('editSourceLocation').value.trim() || null
    };

    try {
        const response = await api.updateNode(currentEditingNodeId, data);
        ui.showToast('节点已更新');
        closeEditModal();

        // Refresh display if the node is currently shown
        refreshNodeDisplay(currentEditingNodeId, response.node);
    } catch (error) {
        ui.showToast(`更新失败: ${error.message}`, 'error');
    }
}

function refreshNodeDisplay(nodeId, node) {
    // Update in search results if present
    const card = document.querySelector(`[data-node-id="${nodeId}"]`);
    if (card) {
        const propEl = card.querySelector('.node-proposition');
        if (propEl) propEl.textContent = node.processed.proposition;
    }

    // Update in modal if open
    if (windowManager.windows.some(w => w.nodeId === nodeId)) {
        const windowObj = windowManager.windows.find(w => w.nodeId === nodeId);
        if (windowObj) {
            windowManager.loadWindowContent(windowObj);
        }
    }
}

async function openDeleteModal(nodeId) {
    try {
        const response = await api.getNode(nodeId);
        const node = response.node;
        currentDeletingNodeId = nodeId;

        document.getElementById('deleteNodeTitle').textContent = node.processed.proposition;
        document.getElementById('deleteConfirmModal').style.display = 'flex';
    } catch (error) {
        ui.showToast(`加载节点失败: ${error.message}`, 'error');
    }
}

function closeDeleteModal() {
    document.getElementById('deleteConfirmModal').style.display = 'none';
    currentDeletingNodeId = null;
}

async function confirmDeleteNode() {
    if (!currentDeletingNodeId) return;

    try {
        await api.deleteNode(currentDeletingNodeId);
        ui.showToast('节点已删除');
        closeDeleteModal();

        // Remove from display
        const card = document.querySelector(`[data-node-id="${currentDeletingNodeId}"]`);
        if (card) card.remove();

        // Close modal if open
        if (windowManager.windows.some(w => w.nodeId === currentDeletingNodeId)) {
            const windowObj = windowManager.windows.find(w => w.nodeId === currentDeletingNodeId);
            if (windowObj) {
                windowManager.closeWindow(windowObj.id);
            }
        }
    } catch (error) {
        ui.showToast(`删除失败: ${error.message}`, 'error');
    }
}
