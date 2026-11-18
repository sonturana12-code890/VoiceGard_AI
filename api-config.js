/**
 * VOICEGUARD AI — Central API Configuration
 * SIH26104 Autonomous Cyber Acoustic Defense
 * Single Source of Truth for Backend API URL and Endpoints
 */
'use strict';

(function(global) {
    function getApiBaseUrl() {
        // 1. Explicit global override (can be configured in HTML window object)
        if (typeof global.VOICEGUARD_API_URL === 'string' && global.VOICEGUARD_API_URL.trim()) {
            return global.VOICEGUARD_API_URL.trim().replace(/\/+$/, '');
        }

        // 2. Meta tag override (<meta name="voiceguard-api-url" content="...">)
        if (typeof document !== 'undefined') {
            const metaTag = document.querySelector('meta[name="voiceguard-api-url"]');
            if (metaTag && metaTag.content && metaTag.content.trim()) {
                return metaTag.content.trim().replace(/\/+$/, '');
            }
        }

        // 3. LocalStorage override
        try {
            const stored = global.localStorage?.getItem('voiceguard_api_url') || global.localStorage?.getItem('vg_api_url');
            if (stored && stored.trim()) {
                return stored.trim().replace(/\/+$/, '');
            }
        } catch (e) {}

        if (typeof window !== 'undefined' && window.location) {
            // 4. Direct file:// protocol access -> target local FastAPI backend
            if (window.location.protocol === 'file:' || !window.location.host) {
                return 'http://127.0.0.1:8000';
            }
            // 5. Frontend dev servers (e.g. Vite :5173, Node :3000, Live Server :5500)
            const port = window.location.port;
            const hostname = window.location.hostname || '127.0.0.1';
            if (port && port !== '8000') {
                return `${window.location.protocol}//${hostname}:8000`;
            }
        }
        // 6. Same-origin fallback (when served directly by FastAPI on port 8000)
        return '';
    }

    const API_BASE_URL = getApiBaseUrl();

    const VoiceGuardConfig = {
        API_BASE_URL: API_BASE_URL,
        BACKEND_ORIGIN: API_BASE_URL || (typeof window !== 'undefined' && window.location ? window.location.origin : 'http://127.0.0.1:8000'),
        ENDPOINTS: {
            HEALTH: '/health',
            API_HEALTH: '/api/health',
            AUTH_REGISTER: '/api/auth/register',
            AUTH_SIGNUP: '/api/auth/register',
            AUTH_LOGIN: '/api/auth/login',
            AUTH_LOGOUT: '/api/auth/logout',
            AUTH_ME: '/api/auth/me',
            AUTH_STATUS: '/api/auth/status',
            AUDIO_ANALYZE: '/api/audio/analyze',
            AUDIO_HISTORY: '/api/audio/history',
            DASHBOARD: '/api/dashboard',
            SPEAKERS: '/api/speakers',
            SPEAKERS_REGISTER: '/api/speakers/register',
            SPEAKERS_VERIFY: '/api/speakers/verify',
            THREATS: '/api/threats',
            SECURITY_EVENTS: '/api/security-events',
            REPORTS: '/api/reports'
        },
        resolveUrl(endpoint) {
            if (!endpoint) return this.API_BASE_URL;
            if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
                return endpoint;
            }
            const clean = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
            return `${this.API_BASE_URL}${clean}`;
        }
    };

    global.VOICEGUARD_CONFIG = VoiceGuardConfig;
    global.API_BASE_URL = VoiceGuardConfig.API_BASE_URL;
})(typeof window !== 'undefined' ? window : this);

