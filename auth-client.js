'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    const requestedView = params.get('view');
    const isSignup = window.location.pathname === '/signup' || requestedView === 'signup';
    const isLogin = window.location.pathname === '/login' || requestedView === 'login';
    const authScreen = document.getElementById('auth-screen');
    const message = document.getElementById('auth-message');
    const loginForm = document.getElementById('login-form');
    const signupForm = document.getElementById('signup-form');
    if (!authScreen || !loginForm || !signupForm) return;

    const showAuth = isSignup || isLogin;
    if (showAuth) {
        authScreen.hidden = false;
        document.body.classList.add('auth-mode');
        document.getElementById('auth-title').textContent = isSignup ? 'Create your account.' : 'Welcome back.';
        document.getElementById('auth-subtitle').textContent = isSignup
            ? 'Create a private account for your VoiceGuard workspace.'
            : 'Sign in to continue to your VoiceGuard workspace.';
        document.getElementById('auth-mode-label').textContent = isSignup ? 'CREATE SECURE ACCESS' : 'SECURE ACCESS';
        loginForm.hidden = isSignup;
        signupForm.hidden = !isSignup;
        document.getElementById('auth-switch-login').hidden = isSignup;
        document.getElementById('auth-switch-signup').hidden = !isSignup;
    }

    const toast = document.getElementById('public-toast');
    let toastTimer;
    function showToast(text) {
        toast.textContent = text;
        toast.classList.add('visible');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toast.classList.remove('visible'), 4500);
    }

    function showMessage(text, kind = 'error') {
        message.textContent = text;
        message.className = `auth-message ${kind}`;
        message.hidden = false;
    }

    function setBusy(form, busy) {
        const button = form.querySelector('button[type="submit"]');
        button.disabled = busy;
        button.classList.toggle('is-loading', busy);
        button.setAttribute('aria-busy', String(busy));
    }

    async function submitAuth(form, endpoint, data) {
        setBusy(form, true);
        message.hidden = true;
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify(data)
            });
            const result = await response.json();
            if (!response.ok) {
                const errorMsg = result.detail || result.error || 'Authentication could not be completed.';
                throw new Error(errorMsg);
            }
            if (result.access_token) {
                localStorage.setItem('vg_token', result.access_token);
                if (window.VoiceGuardAPI) {
                    window.VoiceGuardAPI.setToken(result.access_token);
                }
            }
            window.location.assign('/app');
        } catch (error) {
            showMessage(error.message || 'The server could not be reached. Start the VoiceGuard server and try again.');
            setBusy(form, false);
        }
    }

    loginForm.addEventListener('submit', event => {
        event.preventDefault();
        const formData = new FormData(loginForm);
        submitAuth(loginForm, '/api/auth/login', {
            email: formData.get('email'),
            password: formData.get('password'),
            remember: formData.get('remember') === 'on'
        });
    });

    signupForm.addEventListener('submit', event => {
        event.preventDefault();
        const formData = new FormData(signupForm);
        if (formData.get('password') !== formData.get('confirmPassword')) {
            showMessage('The password and confirmation do not match.');
            return;
        }
        submitAuth(signupForm, '/api/auth/register', {
            fullName: formData.get('fullName'),
            email: formData.get('email'),
            password: formData.get('password'),
            termsAccepted: formData.get('terms') === 'on',
            remember: false
        });
    });

    document.querySelectorAll('[data-password-toggle]').forEach(button => {
        button.addEventListener('click', () => {
            const input = document.getElementById(button.dataset.passwordToggle);
            const reveal = input.type === 'password';
            input.type = reveal ? 'text' : 'password';
            button.textContent = reveal ? 'Hide' : 'Show';
            button.setAttribute('aria-label', `${reveal ? 'Hide' : 'Show'} password`);
        });
    });

    document.getElementById('forgot-password')?.addEventListener('click', () => {
        showMessage('Password-reset email is not configured. Contact the workspace administrator to reset your account.', 'info');
    });

    const menuToggle = document.getElementById('public-menu-toggle');
    menuToggle?.addEventListener('click', () => {
        const open = document.body.classList.toggle('public-menu-open');
        menuToggle.setAttribute('aria-expanded', String(open));
        menuToggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    });

    const dialog = document.getElementById('demo-dialog');
    document.getElementById('watch-demo')?.addEventListener('click', () => dialog.showModal());
    document.getElementById('close-demo')?.addEventListener('click', () => dialog.close());
    dialog?.addEventListener('click', event => {
        if (event.target === dialog) dialog.close();
    });
    const termsDialog = document.getElementById('terms-dialog');
    document.getElementById('show-terms')?.addEventListener('click', () => termsDialog.showModal());
    document.getElementById('close-terms')?.addEventListener('click', () => termsDialog.close());
    document.getElementById('acknowledge-terms')?.addEventListener('click', () => termsDialog.close());

    if (!showAuth) {
        fetch('/api/auth/status', { credentials: 'same-origin' })
            .then(response => response.json())
            .then(result => {
                if (result.authenticated) window.location.replace('/app');
            })
            .catch(error => console.error('Unable to check the current sign-in session:', error));
    }
});
