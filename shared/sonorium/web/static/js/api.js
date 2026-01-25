/**
 * Sonorium API Client
 *
 * Handles all communication with the Sonorium backend.
 * Supports both standalone and HA ingress deployment.
 */

class SonoriumAPI {
    constructor() {
        // Use base path from index.html (supports HA ingress)
        // Falls back to calculating from current path
        let base = window.SONORIUM_BASE !== undefined
            ? window.SONORIUM_BASE
            : (function() {
                const path = window.location.pathname;
                return path.replace(/\/?(index\.html)?$/, '');
            })();

        // Ensure baseUrl ends with / when not empty (for proper URL construction)
        this.baseUrl = base ? (base.endsWith('/') ? base : base + '/') : '';
    }

    async request(method, endpoint, data = null) {
        // Use relative URL for ingress compatibility
        const url = `${this.baseUrl}api${endpoint}`;
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };

        if (data && (method === 'POST' || method === 'PATCH' || method === 'PUT')) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, options);

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            // Handle empty responses (204 No Content)
            if (response.status === 204) return {};
            const text = await response.text();
            return text ? JSON.parse(text) : {};
        } catch (error) {
            console.error(`API Error (${method} ${endpoint}):`, error);
            throw error;
        }
    }

    // ─────────────────────────────────────────────────────────────────────
    // Speakers
    // ─────────────────────────────────────────────────────────────────────

    async getSpeakers(enabledOnly = false) {
        const query = enabledOnly ? '?enabled_only=true' : '';
        return this.request('GET', `/speakers${query}`);
    }

    async getEnabledSpeakers() {
        return this.request('GET', '/speakers/enabled');
    }

    async getSpeaker(speakerId) {
        return this.request('GET', `/speakers/${encodeURIComponent(speakerId)}`);
    }

    async enableSpeaker(speakerId) {
        return this.request('POST', `/speakers/${encodeURIComponent(speakerId)}/enable`);
    }

    async disableSpeaker(speakerId) {
        return this.request('POST', `/speakers/${encodeURIComponent(speakerId)}/disable`);
    }

    async enableAllSpeakers() {
        return this.request('POST', '/speakers/enable-all');
    }

    async disableAllSpeakers() {
        return this.request('POST', '/speakers/disable-all');
    }

    async setSpeakerVolume(speakerId, volume) {
        return this.request('POST', `/speakers/${encodeURIComponent(speakerId)}/volume`, { volume });
    }

    async discoverSpeakers() {
        return this.request('POST', '/speakers/discover');
    }

    // ─────────────────────────────────────────────────────────────────────
    // Themes
    // ─────────────────────────────────────────────────────────────────────

    async getThemes() {
        return this.request('GET', '/themes');
    }

    async getTheme(themeId) {
        return this.request('GET', `/themes/${encodeURIComponent(themeId)}`);
    }

    async playTheme(themeId, speakerIds) {
        const query = speakerIds.map(id => `speaker_ids=${encodeURIComponent(id)}`).join('&');
        return this.request('POST', `/themes/${encodeURIComponent(themeId)}/play?${query}`);
    }

    async scanThemes() {
        return this.request('POST', '/themes/scan');
    }

    // ─────────────────────────────────────────────────────────────────────
    // Sessions
    // ─────────────────────────────────────────────────────────────────────

    async getSessions(activeOnly = true) {
        const query = `?active_only=${activeOnly}`;
        return this.request('GET', `/sessions${query}`);
    }

    async getSession(sessionId) {
        return this.request('GET', `/sessions/${encodeURIComponent(sessionId)}`);
    }

    async createSession(themeId, speakerIds, channelId = null, volume = 1.0) {
        return this.request('POST', '/sessions', {
            theme_id: themeId,
            speaker_ids: speakerIds,
            channel_id: channelId,
            volume,
        });
    }

    async updateSession(sessionId, updates) {
        return this.request('PATCH', `/sessions/${encodeURIComponent(sessionId)}`, updates);
    }

    async stopSession(sessionId) {
        return this.request('DELETE', `/sessions/${encodeURIComponent(sessionId)}`);
    }

    async setSessionVolume(sessionId, volume) {
        return this.updateSession(sessionId, { volume });
    }

    async muteSession(sessionId, muted = true) {
        return this.updateSession(sessionId, { muted });
    }

    // ─────────────────────────────────────────────────────────────────────
    // Channels
    // ─────────────────────────────────────────────────────────────────────

    async getChannels() {
        return this.request('GET', '/channels');
    }

    async getChannel(channelId) {
        return this.request('GET', `/channels/${encodeURIComponent(channelId)}`);
    }

    async createChannel(name, speakerIds = []) {
        return this.request('POST', '/channels', {
            name,
            speaker_ids: speakerIds,
        });
    }

    async updateChannel(channelId, updates) {
        return this.request('PATCH', `/channels/${encodeURIComponent(channelId)}`, updates);
    }

    async deleteChannel(channelId) {
        return this.request('DELETE', `/channels/${encodeURIComponent(channelId)}`);
    }

    async playChannel(channelId, themeId) {
        return this.request('POST', `/channels/${encodeURIComponent(channelId)}/play?theme_id=${encodeURIComponent(themeId)}`);
    }

    async stopChannel(channelId) {
        return this.request('POST', `/channels/${encodeURIComponent(channelId)}/stop`);
    }

    async setChannelVolume(channelId, volume) {
        return this.updateChannel(channelId, { volume });
    }

    async addSpeakersToChannel(channelId, speakerIds) {
        return this.updateChannel(channelId, { add_speakers: speakerIds });
    }

    async removeSpeakersFromChannel(channelId, speakerIds) {
        return this.updateChannel(channelId, { remove_speakers: speakerIds });
    }

    // ─────────────────────────────────────────────────────────────────────
    // Status
    // ─────────────────────────────────────────────────────────────────────

    async getStatus() {
        return this.request('GET', '/status');
    }

    // ─────────────────────────────────────────────────────────────────────
    // Settings
    // ─────────────────────────────────────────────────────────────────────

    async getSettings() {
        return this.request('GET', '/settings');
    }

    async updateSettings(settings) {
        return this.request('PATCH', '/settings', settings);
    }

    async setMasterVolume(volume) {
        return this.updateSettings({ master_volume: volume });
    }

    // ─────────────────────────────────────────────────────────────────────
    // Logs
    // ─────────────────────────────────────────────────────────────────────

    async getLogs(limit = 100, level = 'info') {
        return this.request('GET', `/logs?limit=${limit}&level=${encodeURIComponent(level)}`);
    }

    // ─────────────────────────────────────────────────────────────────────
    // Commands
    // ─────────────────────────────────────────────────────────────────────

    async executeCommand(action, params = {}) {
        return this.request('POST', '/command', { action, params });
    }

    async stopAll() {
        return this.executeCommand('stop_all');
    }
}

// Global API instance
const api = new SonoriumAPI();
