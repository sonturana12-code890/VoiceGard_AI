'use strict';

window.VoiceGuardAuth = {
    user: null,
    ready: null,
    async request(path, options = {}) {
        return window.VoiceGuardAPI.request(path, options);
    },
    async logout() {
        await window.VoiceGuardAPI.logout();
        const homeUrl = window.VOICEGUARD_CONFIG
            ? window.VOICEGUARD_CONFIG.resolveUrl('/')
            : '/';
        window.location.replace(homeUrl);
    }
};

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Sidebar logout button binding
    const logoutBtn = document.getElementById('sidebar-logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            logoutBtn.disabled = true;
            window.VoiceGuardAuth.logout().catch(error => {
                console.error('Unable to complete sign out:', error);
                logoutBtn.disabled = false;
            });
        });
    }

    // 2. Validate current session and populate profile fields
    try {
        window.VoiceGuardAuth.ready = window.VoiceGuardAuth.request('/api/auth/me');
        const result = await window.VoiceGuardAuth.ready;
        const rawUser = result.user || result;
        const user = {
            ...rawUser,
            fullName: rawUser.fullName || rawUser.full_name || 'Security Analyst',
            role: rawUser.role || 'SECURITY ANALYST'
        };
        window.VoiceGuardAuth.user = user;

        const name = document.getElementById('sidebar-user-name');
        const avatar = document.getElementById('sidebar-user-avatar');
        const role = document.getElementById('sidebar-user-role');
        const profileInitials = document.getElementById('profile-initials');
        const profileCardName = document.getElementById('profile-card-name');
        const profileEmailDisplay = document.getElementById('profile-email-display');
        const profileFullNameInput = document.getElementById('profile-full-name');
        const profileEmailInput = document.getElementById('profile-email');

        const initials = (user.fullName || user.email || 'VG')
            .trim()
            .split(/\s+/)
            .slice(0, 2)
            .map(part => part[0])
            .join('')
            .toUpperCase() || 'VG';

        if (name) name.textContent = user.fullName || 'Security Analyst';
        if (avatar) avatar.textContent = initials;
        if (role) role.textContent = user.role || 'SECURITY ANALYST';
        if (profileInitials) profileInitials.textContent = initials;
        if (profileCardName) profileCardName.textContent = user.fullName || 'Security Analyst';
        if (profileEmailDisplay) profileEmailDisplay.textContent = user.email || '—';
        if (profileFullNameInput && !profileFullNameInput.value) profileFullNameInput.value = user.fullName || '';
        if (profileEmailInput) profileEmailInput.value = user.email || '';

        document.body.classList.remove('auth-pending');
    } catch (error) {
        console.error('Unable to validate the application session:', error);
        const loginUrl = window.VOICEGUARD_CONFIG
            ? window.VOICEGUARD_CONFIG.resolveUrl('/login?auth=login')
            : '/login?auth=login';
        window.location.replace(loginUrl);
    }
});
