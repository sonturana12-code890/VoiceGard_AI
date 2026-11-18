'use strict';

document.addEventListener('DOMContentLoaded', async () => {
    const auth = window.VoiceGuardAuth;
    if (!auth) return;

    const feedback = (id, message, kind = 'info') => {
        const element = document.getElementById(id);
        if (!element) return;
        element.textContent = message;
        element.className = `workflow-feedback ${kind}`;
        element.hidden = false;
    };

    try {
        const result = auth.user
            ? { user: auth.user }
            : await (auth.ready || auth.request('/api/auth/me'));
        const rawUser = result.user || result;
        const user = {
            ...rawUser,
            fullName: rawUser.fullName || rawUser.full_name || 'Security Analyst'
        };
        auth.user = user;
        const fullName = document.getElementById('profile-full-name');
        const email = document.getElementById('profile-email');
        const cardName = document.getElementById('profile-card-name');
        const cardEmail = document.getElementById('profile-card-email');
        const initials = document.getElementById('profile-initials');
        if (fullName) fullName.value = user.fullName;
        if (email) email.value = user.email;
        if (cardName) cardName.textContent = user.fullName;
        if (cardEmail) cardEmail.textContent = user.email;
        if (initials) initials.textContent = String(user.fullName || 'Security Analyst').trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();

        const preferenceKey = `voiceguard.preferences.${user.id}`;
        const preferenceToggle = document.getElementById('pref-motion');
        try {
            const preferences = JSON.parse(localStorage.getItem(preferenceKey) || '{}');
            window.VoiceGuardDemoNotifications = preferences.demoNotifications !== false;
            const demoNotifications = document.getElementById('pref-demo-notices');
            if (demoNotifications) demoNotifications.checked = window.VoiceGuardDemoNotifications;
            if (preferenceToggle) {
                preferenceToggle.checked = preferences.reducedMotion === true;
                document.documentElement.classList.toggle('account-reduced-motion', preferenceToggle.checked);
            }
        } catch (error) {
            console.error('Unable to load local display preferences:', error);
        }

        document.getElementById('profile-form')?.addEventListener('submit', async event => {
            event.preventDefault();
            const button = event.currentTarget.querySelector('button[type="submit"]');
            button.disabled = true;
            try {
                const updated = await auth.request('/api/auth/profile', {
                    method: 'PATCH',
                    body: JSON.stringify({ fullName: fullName.value })
                });
                auth.user = updated.user;
                document.getElementById('sidebar-user-name').textContent = updated.user.fullName;
                document.getElementById('sidebar-user-avatar').textContent = updated.user.fullName.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();
                cardName.textContent = updated.user.fullName;
                initials.textContent = document.getElementById('sidebar-user-avatar').textContent;
                feedback('profile-feedback', 'Profile updated.', 'success');
            } catch (error) {
                feedback('profile-feedback', error.message, 'error');
            } finally {
                button.disabled = false;
            }
        });

        document.getElementById('password-form')?.addEventListener('submit', async event => {
            event.preventDefault();
            const form = event.currentTarget;
            const button = form.querySelector('button[type="submit"]');
            if (form.elements.newPassword.value !== form.elements.confirmNewPassword.value) {
                feedback('password-feedback', 'The new password and confirmation do not match.', 'error');
                return;
            }
            button.disabled = true;
            try {
                const updated = await auth.request('/api/auth/password', {
                    method: 'PATCH',
                    body: JSON.stringify({
                        currentPassword: form.elements.currentPassword.value,
                        newPassword: form.elements.newPassword.value
                    })
                });
                form.reset();
                feedback('password-feedback', updated.message, 'success');
            } catch (error) {
                feedback('password-feedback', error.message, 'error');
            } finally {
                button.disabled = false;
            }
        });

        document.getElementById('btn-save-preferences')?.addEventListener('click', () => {
            try {
                localStorage.setItem(preferenceKey, JSON.stringify({
                    reducedMotion: Boolean(preferenceToggle?.checked),
                    demoNotifications: Boolean(document.getElementById('pref-demo-notices')?.checked)
                }));
                window.VoiceGuardDemoNotifications = Boolean(document.getElementById('pref-demo-notices')?.checked);
                document.documentElement.classList.toggle('account-reduced-motion', Boolean(preferenceToggle?.checked));
                feedback('preferences-feedback', 'Display preferences saved in this browser.', 'success');
            } catch (error) {
                console.error('Unable to save local display preferences:', error);
                feedback('preferences-feedback', 'Preferences could not be saved in this browser.', 'error');
            }
        });
    } catch (error) {
        console.error('Unable to load the authenticated account profile:', error);
    }

    document.getElementById('btn-logout')?.addEventListener('click', async event => {
        event.currentTarget.disabled = true;
        try {
            await auth.logout();
        } catch (error) {
            console.error('Unable to end the VoiceGuard session:', error);
            event.currentTarget.disabled = false;
            feedback('preferences-feedback', 'Sign out failed. Please try again.', 'error');
        }
    });

    document.getElementById('btn-callback-preview')?.addEventListener('click', () => {
        feedback('callback-feedback', 'Checklist: pause the request, locate a trusted directory number, call independently, and document human confirmation. No call was placed.', 'info');
    });
    document.getElementById('btn-mfa-preview')?.addEventListener('click', () => {
        feedback('mfa-feedback', 'Use a passkey or hardware key through your organization’s verified identity provider. No challenge was sent or validated.', 'info');
    });
    document.getElementById('btn-hold-preview')?.addEventListener('click', event => {
        event.currentTarget.textContent = 'Local hold plan prepared';
        feedback('hold-feedback', 'Preview only: pause authorization, verify through an independent channel, and escalate to an authorized reviewer. No transaction was held.', 'warning');
    });
});
