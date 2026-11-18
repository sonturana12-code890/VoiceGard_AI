/**
 * VOICEGUARD AI — Unified Frontend API Client
 * Enterprise-grade client connecting to Phase 1 FastAPI backend.
 * Problem Statement: SIH26104 – AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks.
 */

'use strict';

(function(global) {
    function resolveApiBase() {
        if (global.VOICEGUARD_CONFIG) {
            return global.VOICEGUARD_CONFIG.API_BASE_URL;
        }
        if (typeof window !== 'undefined' && window.location) {
            // 1. If opened directly via file:// protocol
            if (window.location.protocol === 'file:' || !window.location.host) {
                return 'http://127.0.0.1:8000';
            }
            const port = window.location.port;
            const hostname = window.location.hostname || '127.0.0.1';
            // 2. If running on a dev server (e.g. port 3000, 5500, 5173), direct to FastAPI backend on port 8000
            if (port && port !== '8000') {
                return `http://${hostname}:8000`;
            }
        }
        return '';
    }

    function authEndpoint(name, fallback) {
        return global.VOICEGUARD_CONFIG && global.VOICEGUARD_CONFIG.ENDPOINTS[name]
            ? global.VOICEGUARD_CONFIG.ENDPOINTS[name]
            : fallback;
    }

    class VoiceGuardAPIClient {
        constructor() {
            let savedToken = null;
            try {
                savedToken = localStorage.getItem('vg_token') || sessionStorage.getItem('vg_token');
            } catch (error) {
                savedToken = null;
            }
            this.token = savedToken || null;
            this.user = null;
        }

        getToken() {
            if (!this.token) {
                try {
                    this.token = localStorage.getItem('vg_token') || sessionStorage.getItem('vg_token');
                } catch (error) {
                    this.token = null;
                }
            }
            return this.token;
        }

        /**
         * Generic fetch wrapper handling JSON, errors, and auth credentials.
         */
        async request(endpoint, options = {}) {
            const url = global.VOICEGUARD_CONFIG
                ? global.VOICEGUARD_CONFIG.resolveUrl(endpoint)
                : (endpoint.startsWith('http') ? endpoint : `${resolveApiBase()}${endpoint}`);
            const headers = {
                ...(options.headers || {})
            };

            // Dynamically refresh and include JWT Bearer token if present
            const activeToken = this.getToken();
            if (activeToken && !headers['Authorization']) {
                headers['Authorization'] = `Bearer ${activeToken}`;
            }

            // Only set application/json if not sending FormData
            if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
                headers['Content-Type'] = 'application/json';
            }

            const isFile = typeof window !== 'undefined' && window.location && window.location.protocol === 'file:';
            const config = {
                ...options,
                headers,
                credentials: isFile ? 'omit' : 'include'
            };

            try {
                const response = await fetch(url, config);
                const contentType = response.headers.get('content-type') || '';
                
                let data = null;
                if (contentType.includes('application/json')) {
                    data = await response.json();
                } else if (contentType.includes('text/csv') || contentType.includes('text/plain')) {
                    data = await response.text();
                } else if (response.status === 204) {
                    data = {};
                }

                if (!response.ok) {
                    const detail = data && (data.error || data.detail);
                    const errorMessage = Array.isArray(detail)
                        ? detail.map(item => item.msg || item.message || String(item)).join(' ')
                        : detail || `HTTP ${response.status}: ${response.statusText}`;
                    const error = new Error(errorMessage);
                    error.status = response.status;
                    error.data = data;
                    throw error;
                }

                return data;
            } catch (err) {
                // If unauthorized and on protected dashboard page, handle session expiry
                if (err.status === 401 && /^\/app(?:\.html)?\/?$/.test(window.location.pathname)) {
                    this.user = null;
                    window.location.replace(global.VOICEGUARD_CONFIG
                        ? global.VOICEGUARD_CONFIG.resolveUrl('/login')
                        : '/login');
                }
                const isNetworkError = err.name === 'TypeError' && (
                    !err.status ||
                    err.message.toLowerCase().includes('failed to fetch') ||
                    err.message.toLowerCase().includes('network')
                );
                if (isNetworkError) {
                    const targetBase = global.VOICEGUARD_CONFIG?.API_BASE_URL || 'http://127.0.0.1:8000';
                    const netErr = new Error(`Cannot connect to VoiceGuard AI backend (${targetBase || 'http://127.0.0.1:8000'}). Please ensure the backend server is running and accessible.`);
                    netErr.status = 0;
                    netErr.isNetworkError = true;
                    throw netErr;
                }
                throw err;
            }
        }

        // ====================================================================
        // SYSTEM & HEALTH
        // ====================================================================
        async getHealth() {
            return await this.request('/api/health');
        }

        // ====================================================================
        // AUTHENTICATION
        // ====================================================================
        async signup(fullName, email, password, termsAccepted = true) {
            const payload = { fullName, email, password, termsAccepted, remember: false };
            const res = await this.request(authEndpoint('AUTH_REGISTER', '/api/auth/register'), {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            if (res && res.access_token) {
                this.setToken(res.access_token);
            }
            this.user = res.user || null;
            return res;
        }

        async login(email, password, remember = true) {
            const payload = { email, password, remember };
            const res = await this.request(authEndpoint('AUTH_LOGIN', '/api/auth/login'), {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            if (res && res.access_token) {
                this.setToken(res.access_token);
            }
            this.user = res.user || null;
            return res;
        }

        async getMe() {
            try {
                const res = await this.request(authEndpoint('AUTH_ME', '/api/auth/me'));
                this.user = res.user || null;
                return res;
            } catch (err) {
                this.user = null;
                throw err;
            }
        }

        async getStatus() {
            return await this.request(authEndpoint('AUTH_STATUS', '/api/auth/status'));
        }

        async logout() {
            try {
                await this.request(authEndpoint('AUTH_LOGOUT', '/api/auth/logout'), { method: 'POST' });
            } finally {
                this.clearToken();
                this.user = null;
            }
        }

        async updateProfile(fullName) {
            const res = await this.request('/api/auth/profile', {
                method: 'PATCH',
                body: JSON.stringify({ fullName })
            });
            if (res.user) this.user = res.user;
            return res;
        }

        async changePassword(currentPassword, newPassword) {
            return await this.request('/api/auth/password', {
                method: 'PATCH',
                body: JSON.stringify({ currentPassword, newPassword })
            });
        }

        async refreshToken() {
            const res = await this.request('/api/auth/refresh', { method: 'POST' });
            if (res.user) this.user = res.user;
            return { user: this.user };
        }

        setToken(token) {
            this.token = token || null;
            try {
                if (token) {
                    localStorage.setItem('vg_token', token);
                    sessionStorage.setItem('vg_token', token);
                } else {
                    localStorage.removeItem('vg_token');
                    sessionStorage.removeItem('vg_token');
                }
            } catch (e) {
                // Storage may be restricted
            }
        }

        clearToken() {
            this.token = null;
            try {
                localStorage.removeItem('vg_token');
                localStorage.removeItem('access_token');
                sessionStorage.removeItem('vg_token');
                sessionStorage.removeItem('access_token');
            } catch (e) {
                // Storage may be unavailable
            }
        }

        // ====================================================================
        // AUDIO INGESTION & FORENSICS
        // ====================================================================
        async uploadAudio(file) {
            const formData = new FormData();
            formData.append('file', file);
            return await this.request('/api/audio/upload', {
                method: 'POST',
                body: formData
            });
        }

        async analyzeAudio(fileOrId) {
            if (typeof File !== 'undefined' && (fileOrId instanceof File || fileOrId instanceof Blob)) {
                const formData = new FormData();
                formData.append('file', fileOrId);
                return await this.request('/api/audio/analyze', {
                    method: 'POST',
                    body: formData
                });
            } else {
                return await this.request(`/api/audio/${fileOrId}`);
            }
        }

        async getAudioHistory(page = 1, limit = 20) {
            return await this.request(`/api/audio/history?page=${page}&limit=${limit}`);
        }

        async getAudioDetails(analysisId) {
            return await this.request(`/api/audio/${analysisId}`);
        }

        // ====================================================================
        // PHASE 3: ADVANCED DETECTION & FORENSICS PIPELINE (/api/v1/audio)
        // ====================================================================
        async validateAudio(file) {
            const formData = new FormData();
            formData.append('file', file);
            return await this.request('/api/v1/audio/validate', {
                method: 'POST',
                body: formData
            });
        }

        async analyzeAudioV1(file, modelName = 'AASIST') {
            const formData = new FormData();
            formData.append('file', file);
            const endpoint = `/api/v1/audio/analyze?model_name=${encodeURIComponent(modelName)}`;
            return await this.request(endpoint, {
                method: 'POST',
                body: formData
            });
        }

        async getAnalysisDetailV1(analysisId) {
            return await this.request(`/api/v1/audio/analysis/${analysisId}`);
        }

        async getAudioPipelineHealth() {
            return await this.request('/api/v1/audio/health');
        }

        async getAudioSpectrogram(analysisId) {
            return await this.request(`/api/v1/audio/${encodeURIComponent(analysisId)}/spectrogram`);
        }

        async getAudioForensics(analysisId) {
            return await this.request(`/api/v1/audio/${encodeURIComponent(analysisId)}/forensics`);
        }

        async analyzeAudioForensics(file) {
            const formData = new FormData();
            formData.append('file', file);
            return await this.request('/api/v1/audio/forensics', {
                method: 'POST',
                body: formData
            });
        }

        // ====================================================================
        // SPEAKER VERIFICATION
        // ====================================================================
        async registerSpeaker(speakerName, audioFile, consentStatus = true, department = '', clearanceLevel = '') {
            const formData = new FormData();
            formData.append('speaker_name', speakerName);
            formData.append('file', audioFile);
            formData.append('consent_status', String(consentStatus));
            if (department) formData.append('department', department);
            if (clearanceLevel) formData.append('clearance_level', clearanceLevel);

            return await this.request('/api/speaker/register', {
                method: 'POST',
                body: formData
            });
        }

        async listSpeakers() {
            return await this.request('/api/speaker/list');
        }

        async verifySpeaker(speakerId, audioFile) {
            const formData = new FormData();
            formData.append('speaker_id', speakerId);
            formData.append('file', audioFile);

            return await this.request('/api/speaker/verify', {
                method: 'POST',
                body: formData
            });
        }

        async enrollSpeaker(speakerName, audioFile, consent = true, department = '', clearanceLevel = '', speakerId = '') {
            const formData = new FormData();
            formData.append('speaker_name', speakerName);
            formData.append('file', audioFile);
            formData.append('consent', String(consent));
            if (speakerId) formData.append('speaker_id', speakerId);
            if (department) formData.append('department', department);
            if (clearanceLevel) formData.append('clearance_level', clearanceLevel);

            return await this.request('/api/v1/speaker/enroll', {
                method: 'POST',
                body: formData
            });
        }

        async listSpeakerProfiles(search = '', status = '', limit = 50, offset = 0) {
            const params = new URLSearchParams();
            if (search) params.append('search', search);
            if (status) params.append('status', status);
            if (limit) params.append('limit', limit);
            if (offset) params.append('offset', offset);
            const query = params.toString() ? `?${params.toString()}` : '';
            return await this.request(`/api/v1/speaker/profiles${query}`);
        }

        async getSpeakerProfile(speakerId) {
            return await this.request(`/api/v1/speaker/profiles/${encodeURIComponent(speakerId)}`);
        }

        async deleteSpeakerProfile(speakerId) {
            return await this.request(`/api/v1/speaker/profiles/${encodeURIComponent(speakerId)}`, {
                method: 'DELETE'
            });
        }

        async verifySpeakerV1(referenceOrSpeakerId, comparisonFile, threshold = 0.25) {
            const formData = new FormData();
            if (typeof referenceOrSpeakerId === 'string') {
                formData.append('speaker_id', referenceOrSpeakerId);
            } else if (referenceOrSpeakerId instanceof File || referenceOrSpeakerId instanceof Blob) {
                formData.append('reference_audio', referenceOrSpeakerId);
            } else if (referenceOrSpeakerId && referenceOrSpeakerId.speaker_id) {
                formData.append('speaker_id', referenceOrSpeakerId.speaker_id);
            }
            formData.append('comparison_audio', comparisonFile);
            formData.append('threshold', String(threshold));

            const query = (threshold !== undefined && threshold !== null) ? `?threshold=${encodeURIComponent(threshold)}` : '';
            return await this.request(`/api/v1/speaker/verify${query}`, {
                method: 'POST',
                body: formData
            });
        }

        async getSpeakerHistory(options = {}) {
            const params = new URLSearchParams();
            if (options.search) params.append('search', options.search);
            if (options.verdict) params.append('verdict', options.verdict);
            if (options.speaker_id) params.append('speaker_id', options.speaker_id);
            if (options.start_date) params.append('start_date', options.start_date);
            if (options.end_date) params.append('end_date', options.end_date);
            if (options.limit) params.append('limit', options.limit);
            if (options.offset) params.append('offset', options.offset);
            const query = params.toString() ? `?${params.toString()}` : '';
            return await this.request(`/api/v1/speaker/history${query}`);
        }

        async deleteSpeakerHistoryRecord(id) {
            return await this.request(`/api/v1/speaker/history/${encodeURIComponent(id)}`, {
                method: 'DELETE'
            });
        }

        async clearSpeakerHistory() {
            return await this.request('/api/v1/speaker/history', {
                method: 'DELETE'
            });
        }

        getSpeakerHistoryExportUrl(search = '', verdict = '') {
            const params = new URLSearchParams();
            if (search) params.append('search', search);
            if (verdict) params.append('verdict', verdict);
            const query = params.toString() ? `?${params.toString()}` : '';
            return global.VOICEGUARD_CONFIG
                ? global.VOICEGUARD_CONFIG.resolveUrl(`/api/v1/speaker/history/export${query}`)
                : `/api/v1/speaker/history/export${query}`;
        }

        async getSpeakerModelInfo() {
            return await this.request('/api/v1/speaker/model-info');
        }

        // ====================================================================
        // DASHBOARD & TELEMETRY
        // ====================================================================
        async getDashboardOverview() {
            return await this.request('/api/dashboard/overview');
        }

        async getDashboardAnalytics() {
            return await this.request('/api/dashboard/analytics');
        }

        async getRecentActivity() {
            return await this.request('/api/dashboard/recent-activity');
        }

        // ====================================================================
        // THREATS & INCIDENTS
        // ====================================================================
        async getThreats() {
            return await this.request('/api/threats');
        }

        async getThreatDetails(threatId) {
            return await this.request(`/api/threats/${threatId}`);
        }

        // ====================================================================
        // REPORTS & EXPORT
        // ====================================================================
        async getReports() {
            return await this.request('/api/reports');
        }

        async exportReportsCsv() {
            return await this.request('/api/reports/export');
        }
    }

    // Export singleton to global window scope
    global.VoiceGuardAPI = new VoiceGuardAPIClient();
})(typeof window !== 'undefined' ? window : this);

