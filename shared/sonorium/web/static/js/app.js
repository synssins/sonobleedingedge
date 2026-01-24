/**
 * Sonorium Web UI Application
 *
 * Main application logic for the web interface.
 */

// Application State
const state = {
    speakers: [],
    themes: [],
    sessions: [],
    settings: {},
    selectedTheme: null,
    refreshInterval: null,
};

// ─────────────────────────────────────────────────────────────────────────
// Initialization
// ─────────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    console.log('Sonorium UI initializing...');

    // Set up event listeners
    setupEventListeners();

    // Load initial data
    await Promise.all([
        loadSpeakers(),
        loadThemes(),
        loadSessions(),
        loadSettings(),
    ]);

    // Start refresh interval
    state.refreshInterval = setInterval(refreshData, 5000);

    console.log('Sonorium UI ready');
}

function setupEventListeners() {
    // Header controls
    document.getElementById('master-volume').addEventListener('input', onMasterVolumeChange);
    document.getElementById('btn-settings').addEventListener('click', openSettingsModal);

    // Speaker controls
    document.getElementById('btn-discover').addEventListener('click', onDiscoverSpeakers);
    document.getElementById('btn-enable-all').addEventListener('click', onEnableAllSpeakers);
    document.getElementById('btn-disable-all').addEventListener('click', onDisableAllSpeakers);

    // Theme controls
    document.getElementById('theme-search').addEventListener('input', filterThemes);
    document.getElementById('theme-category').addEventListener('change', filterThemes);

    // Session controls
    document.getElementById('btn-stop-all').addEventListener('click', onStopAllSessions);

    // Modal controls
    document.getElementById('btn-play-theme').addEventListener('click', onPlaySelectedTheme);
    document.getElementById('btn-save-settings').addEventListener('click', onSaveSettings);

    // Close modals on backdrop click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.add('hidden');
            }
        });
    });
}

async function refreshData() {
    await Promise.all([
        loadSpeakers(),
        loadSessions(),
    ]);
}

// ─────────────────────────────────────────────────────────────────────────
// Speakers
// ─────────────────────────────────────────────────────────────────────────

async function loadSpeakers() {
    try {
        const speakers = await api.getSpeakers();
        state.speakers = Array.isArray(speakers) ? speakers : [];
        renderSpeakers();
    } catch (error) {
        console.error('Failed to load speakers:', error);
    }
}

function renderSpeakers() {
    const container = document.getElementById('speakers-list');

    if (state.speakers.length === 0) {
        container.innerHTML = '<div class="empty-state">No speakers discovered</div>';
        return;
    }

    container.innerHTML = state.speakers.map(speaker => `
        <div class="speaker-item ${speaker.enabled ? '' : 'disabled'} ${speaker.state === 'playing' ? 'playing' : ''}"
             data-speaker-id="${speaker.id}">
            <div class="speaker-info">
                <div class="speaker-name">${escapeHtml(speaker.name)}</div>
                <div class="speaker-details">
                    ${speaker.protocol} | ${speaker.host}
                    ${speaker.model ? ` | ${speaker.model}` : ''}
                </div>
            </div>
            <div class="speaker-controls">
                <input type="range" class="speaker-volume" min="0" max="100"
                       value="${Math.round((speaker.volume || 0.8) * 100)}"
                       title="Volume"
                       onchange="onSpeakerVolumeChange('${speaker.id}', this.value)">
                <label class="toggle-switch">
                    <input type="checkbox" ${speaker.enabled ? 'checked' : ''}
                           onchange="onToggleSpeaker('${speaker.id}', this.checked)">
                    <span class="toggle-slider"></span>
                </label>
            </div>
        </div>
    `).join('');
}

async function onToggleSpeaker(speakerId, enabled) {
    try {
        if (enabled) {
            await api.enableSpeaker(speakerId);
        } else {
            await api.disableSpeaker(speakerId);
        }
        await loadSpeakers();
    } catch (error) {
        console.error('Failed to toggle speaker:', error);
        await loadSpeakers(); // Refresh to show actual state
    }
}

async function onSpeakerVolumeChange(speakerId, value) {
    try {
        await api.setSpeakerVolume(speakerId, value / 100);
    } catch (error) {
        console.error('Failed to set speaker volume:', error);
    }
}

async function onDiscoverSpeakers() {
    const btn = document.getElementById('btn-discover');
    btn.disabled = true;
    btn.textContent = 'Discovering...';

    try {
        await api.discoverSpeakers();
        await loadSpeakers();
    } catch (error) {
        console.error('Failed to discover speakers:', error);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Discover';
    }
}

async function onEnableAllSpeakers() {
    try {
        await api.enableAllSpeakers();
        await loadSpeakers();
    } catch (error) {
        console.error('Failed to enable all speakers:', error);
    }
}

async function onDisableAllSpeakers() {
    try {
        await api.disableAllSpeakers();
        await loadSpeakers();
        await loadSessions();
    } catch (error) {
        console.error('Failed to disable all speakers:', error);
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Themes
// ─────────────────────────────────────────────────────────────────────────

async function loadThemes() {
    try {
        const themes = await api.getThemes();
        state.themes = Array.isArray(themes) ? themes : [];
        renderThemes();
        updateCategoryFilter();
    } catch (error) {
        console.error('Failed to load themes:', error);
    }
}

function renderThemes() {
    const container = document.getElementById('themes-list');
    const searchQuery = document.getElementById('theme-search').value.toLowerCase();
    const categoryFilter = document.getElementById('theme-category').value;

    // Filter themes
    let filteredThemes = state.themes;

    if (searchQuery) {
        filteredThemes = filteredThemes.filter(t =>
            t.name.toLowerCase().includes(searchQuery) ||
            (t.description && t.description.toLowerCase().includes(searchQuery))
        );
    }

    if (categoryFilter) {
        filteredThemes = filteredThemes.filter(t =>
            t.categories && t.categories.includes(categoryFilter)
        );
    }

    if (filteredThemes.length === 0) {
        container.innerHTML = '<div class="empty-state">No themes found</div>';
        return;
    }

    // Check which themes are playing
    const playingThemeIds = new Set(state.sessions.map(s => s.theme_id));

    container.innerHTML = filteredThemes.map(theme => `
        <div class="theme-card ${playingThemeIds.has(theme.id) ? 'playing' : ''}"
             data-theme-id="${theme.id}"
             onclick="openThemeModal('${theme.id}')">
            <div class="theme-icon">${theme.icon || '🎵'}</div>
            <div class="theme-name">${escapeHtml(theme.name)}</div>
            <div class="theme-category">
                ${theme.categories ? theme.categories.join(', ') : 'Uncategorized'}
            </div>
            <div class="theme-actions" onclick="event.stopPropagation()">
                <button class="btn-primary" onclick="quickPlayTheme('${theme.id}')">
                    ${playingThemeIds.has(theme.id) ? 'Playing' : 'Play'}
                </button>
            </div>
        </div>
    `).join('');
}

function updateCategoryFilter() {
    const select = document.getElementById('theme-category');
    const categories = new Set();

    state.themes.forEach(theme => {
        if (theme.categories) {
            theme.categories.forEach(c => categories.add(c));
        }
    });

    const currentValue = select.value;
    select.innerHTML = '<option value="">All Categories</option>' +
        Array.from(categories).sort().map(c =>
            `<option value="${c}">${c}</option>`
        ).join('');

    select.value = currentValue;
}

function filterThemes() {
    renderThemes();
}

async function quickPlayTheme(themeId) {
    // Get enabled speakers
    const enabledSpeakers = state.speakers.filter(s => s.enabled).map(s => s.id);

    if (enabledSpeakers.length === 0) {
        alert('No speakers enabled. Please enable at least one speaker.');
        return;
    }

    try {
        await api.playTheme(themeId, enabledSpeakers);
        await loadSessions();
        renderThemes();
    } catch (error) {
        console.error('Failed to play theme:', error);
        alert('Failed to play theme: ' + error.message);
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Theme Modal
// ─────────────────────────────────────────────────────────────────────────

async function openThemeModal(themeId) {
    try {
        const theme = await api.getTheme(themeId);
        state.selectedTheme = theme;
        renderThemeModal(theme);
        document.getElementById('theme-modal').classList.remove('hidden');
    } catch (error) {
        console.error('Failed to load theme:', error);
    }
}

function closeThemeModal() {
    document.getElementById('theme-modal').classList.add('hidden');
    state.selectedTheme = null;
}

function renderThemeModal(theme) {
    document.getElementById('theme-modal-title').textContent = theme.name;

    // Render tracks
    const tracksContainer = document.getElementById('theme-tracks');
    const tracks = theme.tracks || [];

    tracksContainer.innerHTML = tracks.map(track => `
        <div class="track-item ${track.muted ? 'muted' : ''}" data-track-id="${track.id}">
            <div class="track-info">
                <div class="track-name">${escapeHtml(track.name || track.id)}</div>
                <div class="track-mode">${track.playback_mode || 'loop'} | presence: ${Math.round((track.presence || 1) * 100)}%</div>
            </div>
            <div class="track-controls">
                <input type="range" class="track-volume" min="0" max="100"
                       value="${Math.round((track.volume || 1) * 100)}"
                       title="Volume">
                <label class="toggle-switch">
                    <input type="checkbox" ${track.muted ? '' : 'checked'}
                           title="${track.muted ? 'Unmute' : 'Mute'}">
                    <span class="toggle-slider"></span>
                </label>
            </div>
        </div>
    `).join('') || '<div class="empty-state">No tracks</div>';

    // Render presets
    const presetsContainer = document.getElementById('presets-list');
    const presets = theme.presets || [];

    presetsContainer.innerHTML = presets.map(preset => `
        <button class="preset-btn ${preset.is_default ? 'active' : ''}"
                onclick="onApplyPreset('${theme.id}', '${preset.id}')">
            ${escapeHtml(preset.name)}
        </button>
    `).join('') || '<div class="empty-state">No presets</div>';
}

async function onApplyPreset(themeId, presetId) {
    try {
        await api.applyPreset(themeId, presetId);
        await openThemeModal(themeId); // Refresh modal
    } catch (error) {
        console.error('Failed to apply preset:', error);
    }
}

async function onPlaySelectedTheme() {
    if (!state.selectedTheme) return;
    await quickPlayTheme(state.selectedTheme.id);
    closeThemeModal();
}

// ─────────────────────────────────────────────────────────────────────────
// Sessions
// ─────────────────────────────────────────────────────────────────────────

async function loadSessions() {
    try {
        const sessions = await api.getSessions();
        state.sessions = Array.isArray(sessions) ? sessions : [];
        renderSessions();
    } catch (error) {
        console.error('Failed to load sessions:', error);
    }
}

function renderSessions() {
    const container = document.getElementById('sessions-list');

    if (state.sessions.length === 0) {
        container.innerHTML = '<div class="empty-state">Nothing playing</div>';
        return;
    }

    container.innerHTML = state.sessions.map(session => {
        const theme = state.themes.find(t => t.id === session.theme_id);
        const themeName = theme ? theme.name : session.theme_id;

        return `
            <div class="session-item" data-session-id="${session.id}">
                <div class="session-header">
                    <div class="session-theme">${escapeHtml(themeName)}</div>
                    <button class="btn-danger" onclick="onStopSession('${session.id}')">
                        Stop
                    </button>
                </div>
                <div class="session-controls">
                    <div class="session-volume">
                        <input type="range" min="0" max="100"
                               value="${Math.round((session.volume || 1) * 100)}"
                               onchange="onSessionVolumeChange('${session.id}', this.value)">
                        <span>${Math.round((session.volume || 1) * 100)}%</span>
                    </div>
                </div>
                <div class="session-speakers">
                    ${(session.speakers || []).map(speakerId => {
                        const speaker = state.speakers.find(s => s.id === speakerId);
                        const name = speaker ? speaker.name : speakerId;
                        return `<span class="speaker-tag">${escapeHtml(name)}</span>`;
                    }).join('')}
                </div>
            </div>
        `;
    }).join('');
}

async function onStopSession(sessionId) {
    try {
        await api.stopSession(sessionId);
        await loadSessions();
        renderThemes();
    } catch (error) {
        console.error('Failed to stop session:', error);
    }
}

async function onSessionVolumeChange(sessionId, value) {
    try {
        await api.setSessionVolume(sessionId, value / 100);
    } catch (error) {
        console.error('Failed to set session volume:', error);
    }
}

async function onStopAllSessions() {
    try {
        await api.stopAllSessions();
        await loadSessions();
        renderThemes();
    } catch (error) {
        console.error('Failed to stop all sessions:', error);
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Settings
// ─────────────────────────────────────────────────────────────────────────

async function loadSettings() {
    try {
        const settings = await api.getSettings();
        state.settings = settings || {};
        applySettings(settings);
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

function applySettings(settings) {
    // Master volume
    const masterVolume = settings.master_volume || 0.8;
    document.getElementById('master-volume').value = masterVolume * 100;
    document.getElementById('master-volume-value').textContent = Math.round(masterVolume * 100) + '%';

    // MQTT
    if (settings.mqtt) {
        document.getElementById('mqtt-enabled').checked = settings.mqtt.enabled;
        document.getElementById('mqtt-host').value = settings.mqtt.host || 'localhost';
        document.getElementById('mqtt-port').value = settings.mqtt.port || 1883;
    }

    // Discovery
    if (settings.discovery) {
        document.getElementById('discovery-interval').value = settings.discovery.interval_seconds || 300;
    }

    // Audio
    if (settings.audio) {
        document.getElementById('default-volume').value = (settings.audio.default_volume || 0.8) * 100;
    }
}

function openSettingsModal() {
    document.getElementById('settings-modal').classList.remove('hidden');
}

function closeSettingsModal() {
    document.getElementById('settings-modal').classList.add('hidden');
}

async function onSaveSettings() {
    const settings = {
        mqtt: {
            enabled: document.getElementById('mqtt-enabled').checked,
            host: document.getElementById('mqtt-host').value,
            port: parseInt(document.getElementById('mqtt-port').value),
        },
        discovery: {
            interval_seconds: parseInt(document.getElementById('discovery-interval').value),
        },
        audio: {
            default_volume: document.getElementById('default-volume').value / 100,
        },
    };

    try {
        await api.updateSettings(settings);
        closeSettingsModal();
        await loadSettings();
    } catch (error) {
        console.error('Failed to save settings:', error);
        alert('Failed to save settings: ' + error.message);
    }
}

async function onMasterVolumeChange(event) {
    const value = event.target.value;
    document.getElementById('master-volume-value').textContent = value + '%';

    try {
        await api.setMasterVolume(value / 100);
    } catch (error) {
        console.error('Failed to set master volume:', error);
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────────────────────────────────

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
