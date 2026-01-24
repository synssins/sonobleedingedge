/**
 * Sonorium API Client
 *
 * Handles all communication with the Sonorium backend.
 */

class SonoriumAPI {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
    }

    async request(method, endpoint, data = null) {
        const url = `${this.baseUrl}/api${endpoint}`;
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

            // Handle empty responses
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

    async getSpeakers() {
        return this.request('GET', '/speakers');
    }

    async getEnabledSpeakers() {
        return this.request('GET', '/speakers/enabled');
    }

    async enableSpeaker(speakerId) {
        return this.request('POST', `/speakers/${speakerId}/enable`);
    }

    async disableSpeaker(speakerId) {
        return this.request('POST', `/speakers/${speakerId}/disable`);
    }

    async enableAllSpeakers() {
        return this.request('POST', '/speakers/enable-all');
    }

    async disableAllSpeakers() {
        return this.request('POST', '/speakers/disable-all');
    }

    async setSpeakerVolume(speakerId, volume) {
        return this.request('POST', `/speakers/${speakerId}/volume`, { volume });
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
        return this.request('GET', `/themes/${themeId}`);
    }

    async playTheme(themeId, speakerIds = null, volume = 1.0) {
        return this.request('POST', `/themes/${themeId}/play`, {
            speaker_ids: speakerIds,
            volume,
        });
    }

    async scanThemes() {
        return this.request('POST', '/themes/scan');
    }

    async setThemeFavorite(themeId, isFavorite) {
        return this.request('PATCH', `/themes/${themeId}`, {
            is_favorite: isFavorite,
        });
    }

    async applyPreset(themeId, presetId) {
        return this.request('POST', `/themes/${themeId}/presets/${presetId}/apply`);
    }

    // ─────────────────────────────────────────────────────────────────────
    // Sessions
    // ─────────────────────────────────────────────────────────────────────

    async getSessions() {
        return this.request('GET', '/sessions');
    }

    async getSession(sessionId) {
        return this.request('GET', `/sessions/${sessionId}`);
    }

    async createSession(themeId, speakerIds, volume = 1.0) {
        return this.request('POST', '/sessions', {
            theme_id: themeId,
            speaker_ids: speakerIds,
            volume,
        });
    }

    async stopSession(sessionId) {
        return this.request('DELETE', `/sessions/${sessionId}`);
    }

    async updateSession(sessionId, updates) {
        return this.request('PATCH', `/sessions/${sessionId}`, updates);
    }

    async setSessionVolume(sessionId, volume) {
        return this.updateSession(sessionId, { volume });
    }

    async muteSession(sessionId, muted = true) {
        return this.updateSession(sessionId, { muted });
    }

    async stopAllSessions() {
        return this.request('POST', '/sessions/stop-all');
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

    async getMasterVolume() {
        return this.request('GET', '/settings/master-volume');
    }

    async setMasterVolume(volume) {
        return this.request('POST', '/settings/master-volume', { volume });
    }

    // ─────────────────────────────────────────────────────────────────────
    // Status
    // ─────────────────────────────────────────────────────────────────────

    async getStatus() {
        return this.request('GET', '/status');
    }
}

// Global API instance
const api = new SonoriumAPI();
