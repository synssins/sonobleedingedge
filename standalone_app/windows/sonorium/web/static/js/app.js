/**
 * Sonorium Web UI Application
 *
 * Main application logic for the sidebar-based web interface.
 * Function names and element IDs match index.html exactly.
 */

// Application State
const state = {
    speakers: [],
    themes: [],
    channels: [],
    sessions: [],
    settings: {},
    status: {},
    currentView: 'channels',
    editingChannelId: null,
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

    // Set up volume slider listener
    const volumeSlider = document.getElementById('channel-volume');
    if (volumeSlider) {
        volumeSlider.addEventListener('input', function() {
            document.getElementById('channel-volume-display').textContent = this.value + '%';
        });
    }

    // Load initial data
    await Promise.all([
        loadSpeakers(),
        loadThemes(),
        loadChannels(),
        loadSessions(),
        loadStatus(),
        loadSettings(),
    ]);

    // Show initial view
    showView('channels');

    // Start refresh interval (every 5 seconds)
    state.refreshInterval = setInterval(refreshData, 5000);

    console.log('Sonorium UI ready');
}

async function refreshData() {
    await Promise.all([
        loadSpeakers(),
        loadChannels(),
        loadSessions(),
        loadStatus(),
    ]);
}

// ─────────────────────────────────────────────────────────────────────────
// Navigation
// ─────────────────────────────────────────────────────────────────────────

function showView(viewId) {
    state.currentView = viewId;

    // Hide all views
    document.querySelectorAll('.view').forEach(v => {
        v.classList.remove('active');
    });

    // Show target view
    const targetView = document.getElementById(`view-${viewId}`);
    if (targetView) {
        targetView.classList.add('active');
    }

    // Update nav items
    document.querySelectorAll('.nav-item, .nav-sub-item').forEach(item => {
        item.classList.remove('active');
    });

    // Find and activate matching nav item
    const navItems = document.querySelectorAll('.nav-item, .nav-sub-item');
    navItems.forEach(item => {
        const onclick = item.getAttribute('onclick') || '';
        if (onclick.includes(`showView('${viewId}')`)) {
            item.classList.add('active');
        }
    });

    // Update header title
    const titles = {
        'channels': 'Channels',
        'themes': 'Themes',
        'settings-speakers': 'Speakers',
        'settings-audio': 'Audio Settings',
        'status': 'Status',
    };
    document.getElementById('view-title').textContent = titles[viewId] || viewId;

    // Update header actions based on view
    updateViewActions(viewId);

    // Close sidebar on mobile
    closeSidebar();
}

function updateViewActions(viewId) {
    const container = document.getElementById('view-actions');

    switch (viewId) {
        case 'channels':
            container.innerHTML = `
                <button class="btn btn-primary" onclick="openNewChannelModal()">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="12" y1="5" x2="12" y2="19"/>
                        <line x1="5" y1="12" x2="19" y2="12"/>
                    </svg>
                    New Channel
                </button>
            `;
            break;
        case 'themes':
            container.innerHTML = `
                <button class="btn btn-secondary" onclick="refreshThemes()">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M23 4v6h-6"/>
                        <path d="M1 20v-6h6"/>
                        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                    </svg>
                    Refresh
                </button>
            `;
            break;
        default:
            container.innerHTML = '';
    }
}

function toggleNavSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.classList.toggle('expanded');
    }
}

function toggleSidebar() {
    document.body.classList.toggle('sidebar-open');
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
        sidebar.classList.toggle('open');
    }
}

function closeSidebar() {
    document.body.classList.remove('sidebar-open');
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
        sidebar.classList.remove('open');
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Speakers
// ─────────────────────────────────────────────────────────────────────────

async function loadSpeakers() {
    try {
        const speakers = await api.getSpeakers();
        state.speakers = Array.isArray(speakers) ? speakers : [];
        renderSpeakers();
        updateChannelModalSpeakers();
    } catch (error) {
        console.error('Failed to load speakers:', error);
    }
}

function renderSpeakers() {
    const container = document.getElementById('speakers-list');
    if (!container) return;

    if (state.speakers.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No speakers discovered</p>
                <button class="btn btn-secondary btn-sm" onclick="discoverSpeakers()">
                    Discover Speakers
                </button>
            </div>
        `;
        return;
    }

    container.innerHTML = state.speakers.map(speaker => `
        <div class="speaker-item ${speaker.enabled ? '' : 'disabled'}" data-speaker-id="${speaker.id}">
            <div class="speaker-info">
                <svg class="speaker-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="4" y="2" width="16" height="20" rx="2" ry="2"/>
                    <circle cx="12" cy="14" r="4"/>
                    <line x1="12" y1="6" x2="12" y2="6"/>
                </svg>
                <div class="speaker-details">
                    <span class="speaker-name">${escapeHtml(speaker.name)}</span>
                    <span class="speaker-meta">${speaker.host} • ${speaker.protocol}</span>
                </div>
            </div>
            <label class="toggle-switch">
                <input type="checkbox" ${speaker.enabled ? 'checked' : ''}
                       onchange="toggleSpeaker('${speaker.id}', this.checked)">
                <span class="toggle-slider"></span>
            </label>
        </div>
    `).join('');
}

async function toggleSpeaker(speakerId, enabled) {
    try {
        if (enabled) {
            await api.enableSpeaker(speakerId);
        } else {
            await api.disableSpeaker(speakerId);
        }
        await loadSpeakers();
        await loadStatus();
    } catch (error) {
        console.error('Failed to toggle speaker:', error);
        showToast('Failed to toggle speaker', 'error');
        await loadSpeakers();
    }
}

async function discoverSpeakers() {
    try {
        showToast('Discovering speakers...', 'info');
        await api.discoverSpeakers();
        setTimeout(async () => {
            await loadSpeakers();
            await loadStatus();
            showToast('Speaker discovery complete', 'success');
        }, 3000);
    } catch (error) {
        console.error('Failed to discover speakers:', error);
        showToast('Failed to discover speakers', 'error');
    }
}

async function enableAllSpeakers() {
    try {
        await api.enableAllSpeakers();
        await loadSpeakers();
        await loadStatus();
        showToast('All speakers enabled', 'success');
    } catch (error) {
        console.error('Failed to enable speakers:', error);
        showToast('Failed to enable speakers', 'error');
    }
}

async function disableAllSpeakers() {
    try {
        await api.disableAllSpeakers();
        await loadSpeakers();
        await loadSessions();
        await loadStatus();
        showToast('All speakers disabled', 'success');
    } catch (error) {
        console.error('Failed to disable speakers:', error);
        showToast('Failed to disable speakers', 'error');
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
        updateChannelModalThemes();
    } catch (error) {
        console.error('Failed to load themes:', error);
    }
}

function renderThemes() {
    const container = document.getElementById('themes-browser');
    if (!container) return;

    if (state.themes.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h3>No themes found</h3>
                <p>Click "Refresh" to scan for available soundscapes</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="theme-grid">
            ${state.themes.map(theme => `
                <div class="theme-card" data-theme-id="${theme.id}">
                    <div class="theme-icon">${getThemeIcon(theme)}</div>
                    <div class="theme-info">
                        <h4 class="theme-name">${escapeHtml(theme.name)}</h4>
                        <p class="theme-description">${escapeHtml(theme.description || 'No description')}</p>
                        <div class="theme-meta">
                            <span>${theme.track_count || 0} tracks</span>
                            ${theme.tags?.length ? `<span>${theme.tags.join(', ')}</span>` : ''}
                        </div>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

function getThemeIcon(theme) {
    const tagIcons = {
        'nature': '🌲',
        'rain': '🌧️',
        'ocean': '🌊',
        'forest': '🌳',
        'city': '🏙️',
        'space': '🚀',
        'ambient': '🎵',
        'relaxing': '😌',
        'focus': '🎯',
        'sleep': '😴',
    };

    if (theme.tags) {
        for (const tag of theme.tags) {
            if (tagIcons[tag.toLowerCase()]) {
                return tagIcons[tag.toLowerCase()];
            }
        }
    }
    return '🎵';
}

async function refreshThemes() {
    try {
        showToast('Scanning for themes...', 'info');
        await api.scanThemes();
        setTimeout(async () => {
            await loadThemes();
            await loadStatus();
            showToast('Theme scan complete', 'success');
        }, 2000);
    } catch (error) {
        console.error('Failed to scan themes:', error);
        showToast('Failed to scan themes', 'error');
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Channels
// ─────────────────────────────────────────────────────────────────────────

async function loadChannels() {
    try {
        const channels = await api.getChannels();
        state.channels = Array.isArray(channels) ? channels : [];
    } catch (error) {
        console.error('Failed to load channels:', error);
        state.channels = [];
    }
    renderChannels();
    updatePlayingBadge();
}

function renderChannels() {
    const container = document.getElementById('channels-container');
    if (!container) return;

    if (state.channels.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h3>No channels yet</h3>
                <p>Create a channel to start playing soundscapes on your speakers</p>
                <button class="btn btn-primary" onclick="openNewChannelModal()">
                    Create Your First Channel
                </button>
            </div>
        `;
        return;
    }

    container.innerHTML = state.channels.map(channel => {
        const theme = state.themes.find(t => t.id === channel.theme_id);
        const themeName = theme ? theme.name : 'No theme';
        const speakerNames = channel.speaker_ids
            .map(id => state.speakers.find(s => s.id === id)?.name || id)
            .slice(0, 3)
            .join(', ');
        const extraSpeakers = channel.speaker_ids.length > 3
            ? ` +${channel.speaker_ids.length - 3} more` : '';

        return `
            <div class="channel-card ${channel.is_playing ? 'playing' : ''}" data-channel-id="${channel.id}">
                <div class="channel-header">
                    <div class="channel-title">
                        <span class="channel-icon">${getThemeIcon(theme || {})}</span>
                        <h3 class="channel-name">${escapeHtml(channel.name)}</h3>
                    </div>
                    <span class="channel-status ${channel.is_playing ? 'playing' : 'stopped'}">
                        ${channel.is_playing ? '● Playing' : '○ Stopped'}
                    </span>
                </div>

                <div class="channel-body">
                    <div class="channel-field">
                        <label>Theme</label>
                        <span class="field-value">${escapeHtml(themeName)}</span>
                    </div>
                    <div class="channel-field">
                        <label>Speakers</label>
                        <span class="field-value">${speakerNames}${extraSpeakers || ''}</span>
                    </div>

                    <div class="volume-control">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                            <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/>
                        </svg>
                        <input type="range" class="volume-slider" min="0" max="100"
                               value="${Math.round((channel.volume || 1) * 100)}"
                               oninput="this.nextElementSibling.textContent = this.value + '%'"
                               onchange="setChannelVolume('${channel.id}', this.value / 100)">
                        <span class="volume-value">${Math.round((channel.volume || 1) * 100)}%</span>
                    </div>
                </div>

                <div class="channel-actions">
                    <button class="btn ${channel.is_playing ? 'btn-danger' : 'btn-primary'} btn-play"
                            onclick="toggleChannel('${channel.id}', ${!channel.is_playing})"
                            ${!channel.theme_id && !channel.is_playing ? 'disabled title="Select a theme first"' : ''}>
                        ${channel.is_playing ? '⏹ Stop' : '▶ Play'}
                    </button>
                    <button class="btn btn-secondary" onclick="editChannel('${channel.id}')">
                        Edit
                    </button>
                    <button class="btn btn-ghost btn-danger-text" onclick="deleteChannel('${channel.id}')">
                        Delete
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

function updatePlayingBadge() {
    const badge = document.getElementById('playing-badge');
    if (!badge) return;

    const playingCount = state.channels.filter(c => c.is_playing).length;
    if (playingCount > 0) {
        badge.textContent = playingCount;
        badge.style.display = '';
    } else {
        badge.style.display = 'none';
    }
}

async function toggleChannel(channelId, play) {
    try {
        const channel = state.channels.find(c => c.id === channelId);
        if (!channel) return;

        if (play) {
            if (!channel.theme_id) {
                showToast('Please select a theme first', 'error');
                return;
            }
            await api.playChannel(channelId, channel.theme_id);
            showToast(`Playing ${channel.name}`, 'success');
        } else {
            await api.stopChannel(channelId);
            showToast(`Stopped ${channel.name}`, 'success');
        }
        await loadChannels();
        await loadSessions();
        await loadStatus();
    } catch (error) {
        console.error('Failed to toggle channel:', error);
        showToast('Failed: ' + error.message, 'error');
    }
}

async function setChannelVolume(channelId, volume) {
    try {
        await api.setChannelVolume(channelId, volume);
    } catch (error) {
        console.error('Failed to set channel volume:', error);
    }
}

async function deleteChannel(channelId) {
    const channel = state.channels.find(c => c.id === channelId);
    if (!channel) return;

    if (!confirm(`Delete channel "${channel.name}"?`)) return;

    try {
        await api.deleteChannel(channelId);
        await loadChannels();
        showToast('Channel deleted', 'success');
    } catch (error) {
        console.error('Failed to delete channel:', error);
        showToast('Failed to delete channel', 'error');
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Channel Modal
// ─────────────────────────────────────────────────────────────────────────

function openNewChannelModal() {
    state.editingChannelId = null;
    document.getElementById('modal-title').textContent = 'New Channel';
    document.getElementById('save-btn-text').textContent = 'Create Channel';
    document.getElementById('edit-channel-id').value = '';
    document.getElementById('channel-name').value = '';
    document.getElementById('channel-theme').value = '';
    document.getElementById('channel-volume').value = 60;
    document.getElementById('channel-volume-display').textContent = '60%';

    // Clear speaker checkboxes
    updateChannelModalSpeakers([]);

    document.getElementById('channel-modal').classList.add('active');
}

function editChannel(channelId) {
    const channel = state.channels.find(c => c.id === channelId);
    if (!channel) return;

    state.editingChannelId = channelId;
    document.getElementById('modal-title').textContent = 'Edit Channel';
    document.getElementById('save-btn-text').textContent = 'Save Changes';
    document.getElementById('edit-channel-id').value = channelId;
    document.getElementById('channel-name').value = channel.name;
    document.getElementById('channel-theme').value = channel.theme_id || '';
    document.getElementById('channel-volume').value = Math.round((channel.volume || 1) * 100);
    document.getElementById('channel-volume-display').textContent =
        Math.round((channel.volume || 1) * 100) + '%';

    // Set speaker checkboxes
    updateChannelModalSpeakers(channel.speaker_ids);

    document.getElementById('channel-modal').classList.add('active');
}

function updateChannelModalSpeakers(selectedIds = []) {
    const container = document.getElementById('channel-speakers');
    if (!container) return;

    // Only show enabled speakers
    const enabledSpeakers = state.speakers.filter(s => s.enabled);

    if (enabledSpeakers.length === 0) {
        container.innerHTML = `
            <p class="empty-hint">No enabled speakers available.
            <a href="#" onclick="showView('settings-speakers'); closeChannelModal(); return false;">Enable speakers</a> first.</p>
        `;
        return;
    }

    container.innerHTML = enabledSpeakers.map(speaker => `
        <label class="checkbox-item">
            <input type="checkbox" name="channel-speaker" value="${speaker.id}"
                   ${selectedIds.includes(speaker.id) ? 'checked' : ''}>
            <span class="checkbox-label">
                <span class="checkbox-name">${escapeHtml(speaker.name)}</span>
                <span class="checkbox-meta">${speaker.host}</span>
            </span>
        </label>
    `).join('');
}

function updateChannelModalThemes() {
    const select = document.getElementById('channel-theme');
    if (!select) return;

    const currentValue = select.value;
    select.innerHTML = '<option value="">-- Select a theme --</option>' +
        state.themes.map(t =>
            `<option value="${t.id}">${escapeHtml(t.name)}</option>`
        ).join('');

    if (currentValue) {
        select.value = currentValue;
    }
}

async function saveChannel() {
    const name = document.getElementById('channel-name').value.trim();
    if (!name) {
        showToast('Please enter a channel name', 'error');
        return;
    }

    const themeId = document.getElementById('channel-theme').value || null;
    const volume = parseInt(document.getElementById('channel-volume').value) / 100;
    const speakerIds = Array.from(
        document.querySelectorAll('input[name="channel-speaker"]:checked')
    ).map(cb => cb.value);

    try {
        if (state.editingChannelId) {
            // Update existing channel
            const channel = state.channels.find(c => c.id === state.editingChannelId);
            const updates = { name, volume };

            if (themeId !== channel.theme_id) {
                updates.theme_id = themeId;
            }

            // Calculate speaker changes
            const currentSpeakers = channel.speaker_ids || [];
            const addSpeakers = speakerIds.filter(id => !currentSpeakers.includes(id));
            const removeSpeakers = currentSpeakers.filter(id => !speakerIds.includes(id));

            if (addSpeakers.length > 0) updates.add_speakers = addSpeakers;
            if (removeSpeakers.length > 0) updates.remove_speakers = removeSpeakers;

            await api.updateChannel(state.editingChannelId, updates);
            showToast('Channel updated', 'success');
        } else {
            // Create new channel
            const newChannel = await api.createChannel(name, speakerIds);

            // If theme selected, update the channel with theme
            if (themeId) {
                await api.updateChannel(newChannel.id, { theme_id: themeId, volume });
            }
            showToast('Channel created', 'success');
        }

        closeChannelModal();
        await loadChannels();
    } catch (error) {
        console.error('Failed to save channel:', error);
        showToast('Failed to save: ' + error.message, 'error');
    }
}

function closeChannelModal() {
    document.getElementById('channel-modal').classList.remove('active');
    state.editingChannelId = null;
}

function closeModalOnBackdrop(event) {
    if (event.target.classList.contains('modal-backdrop')) {
        closeChannelModal();
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Sessions
// ─────────────────────────────────────────────────────────────────────────

async function loadSessions() {
    try {
        const sessions = await api.getSessions();
        state.sessions = Array.isArray(sessions) ? sessions : [];
    } catch (error) {
        console.error('Failed to load sessions:', error);
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Status
// ─────────────────────────────────────────────────────────────────────────

async function loadStatus() {
    try {
        const status = await api.getStatus();
        state.status = status || {};
        renderStatus();
    } catch (error) {
        console.error('Failed to load status:', error);
    }
}

function renderStatus() {
    // Status cards
    document.getElementById('status-active-sessions').textContent =
        state.status.active_session_count || 0;
    document.getElementById('status-total-speakers').textContent =
        state.status.speaker_count || 0;
    document.getElementById('status-enabled-speakers').textContent =
        state.status.enabled_speaker_count || 0;
    document.getElementById('status-theme-count').textContent =
        state.status.theme_count || 0;

    // About section
    document.getElementById('about-version').textContent =
        state.status.version || 'Unknown';
    document.getElementById('about-state').textContent =
        state.status.state || 'Unknown';

    // Sidebar version
    document.getElementById('version-text').textContent =
        'v' + (state.status.version || '...');
}

// ─────────────────────────────────────────────────────────────────────────
// Settings
// ─────────────────────────────────────────────────────────────────────────

async function loadSettings() {
    try {
        const settings = await api.getSettings();
        state.settings = settings || {};
        renderSettings();
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

function renderSettings() {
    const masterVolume = Math.round((state.settings.master_volume || 0.8) * 100);
    const slider = document.getElementById('settings-master-volume');
    const display = document.getElementById('settings-master-volume-value');

    if (slider) slider.value = masterVolume;
    if (display) display.textContent = masterVolume + '%';
}

function updateMasterVolumeDisplay(value) {
    const display = document.getElementById('settings-master-volume-value');
    if (display) {
        display.textContent = value + '%';
    }
}

async function saveAudioSettings() {
    try {
        const masterVolume = parseInt(
            document.getElementById('settings-master-volume').value
        ) / 100;

        await api.updateSettings({ master_volume: masterVolume });
        state.settings.master_volume = masterVolume;
        showToast('Settings saved', 'success');
    } catch (error) {
        console.error('Failed to save settings:', error);
        showToast('Failed to save settings', 'error');
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Toast Notifications
// ─────────────────────────────────────────────────────────────────────────

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = {
        success: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
        error: '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>',
        info: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
    };

    toast.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            ${icons[type] || icons.info}
        </svg>
        <span>${escapeHtml(message)}</span>
    `;

    container.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });

    // Auto-remove after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
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
