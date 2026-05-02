/**
 * Rhizome Thinking - API Client
 */

class APIClient {
    constructor() {
        this.baseURL = window.location.origin;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        if (config.body && typeof config.body === 'object') {
            config.body = JSON.stringify(config.body);
        }

        const response = await fetch(url, config);

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: '请求失败' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return response.json();
    }

    async createNode(data) {
        return this.request('/api/v1/nodes', {
            method: 'POST',
            body: data
        });
    }

    async getNodes(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/api/v1/nodes?${query}`);
    }

    async getNode(id) {
        return this.request(`/api/v1/nodes/${id}`);
    }

    async deleteNode(id) {
        return this.request(`/api/v1/nodes/${id}`, { method: 'DELETE' });
    }

    async query(data) {
        return this.request('/api/v1/query', {
            method: 'POST',
            body: data
        });
    }

    async clusterQuery(data) {
        return this.request('/api/v1/query/cluster', {
            method: 'POST',
            body: data
        });
    }

    async themeQuery(data) {
        return this.request('/api/v1/query/themes', {
            method: 'POST',
            body: data
        });
    }

    async searchKeywords(q, limit = 10) {
        return this.request(`/api/v1/search?q=${encodeURIComponent(q)}&limit=${limit}`);
    }

    async createLink(data) {
        return this.request('/api/v1/links', {
            method: 'POST',
            body: data
        });
    }

    async confirmLink(nodeId, targetId) {
        return this.request(`/api/v1/nodes/${nodeId}/links/${targetId}/confirm`, {
            method: 'POST'
        });
    }

    async getStats() {
        return this.request('/api/v1/stats');
    }

    async getRecentActivity(days = 7) {
        return this.request(`/api/v1/stats/recent?days=${days}`);
    }

    async getTags() {
        return this.request('/api/v1/tags');
    }

    async getSources() {
        return this.request('/api/v1/sources');
    }

    async createSource(data) {
        return this.request('/api/v1/sources', {
            method: 'POST',
            body: data
        });
    }

    async updateSource(sourceId, data) {
        return this.request(`/api/v1/sources/${sourceId}`, {
            method: 'PUT',
            body: data
        });
    }

    async deleteSource(sourceId) {
        return this.request(`/api/v1/sources/${sourceId}`, {
            method: 'DELETE'
        });
    }

    async updateNode(id, data) {
        return this.request(`/api/v1/nodes/${id}`, {
            method: 'PUT',
            body: data
        });
    }

    async preciseQuery(data) {
        return this.request('/api/v1/query/precise', {
            method: 'POST',
            body: data
        });
    }

    async getBackups() {
        return this.request('/api/v1/backups');
    }

    async createBackup() {
        return this.request('/api/v1/backups', { method: 'POST' });
    }

    async restoreBackup(name, confirm = false) {
        return this.request(`/api/v1/backups/${encodeURIComponent(name)}/restore`, {
            method: 'POST',
            body: { confirm }
        });
    }

    async deleteBackup(name) {
        return this.request(`/api/v1/backups/${encodeURIComponent(name)}`, { method: 'DELETE' });
    }

    async uploadBackup(file) {
        const url = `${this.baseURL}/api/v1/backups/upload`;
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: '上传失败' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return response.json();
    }
}

const api = new APIClient();
