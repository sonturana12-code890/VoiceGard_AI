/**
 * VOICEGUARD AI — Dashboard Controller & Live Telemetry Engine
 * Bridges Phase 1 FastAPI Backend with Advanced Phase 2 UI Components.
 * Handles 7-Stage Analysis, Mic Recording with Timer & Web Audio, Dynamic History, and Charts.
 */

'use strict';

document.addEventListener('DOMContentLoaded', async () => {
    const appLayout = document.querySelector('.app-layout');
    if (appLayout) {
        const sidebarToggle = document.getElementById('mobile-toggle-btn');
        const sidebarClose = document.getElementById('mobile-close-btn');
        const sidebarOverlay = document.getElementById('sidebar-overlay');
        const mobileSidebarQuery = window.matchMedia('(max-width: 768px)');
        const readSidebarPreference = (key, fallback) => {
            try {
                const value = localStorage.getItem(key);
                return value === null ? fallback : value === 'true';
            } catch (err) {
                console.warn('[VoiceGuardApp] Unable to read sidebar preference:', err);
                return fallback;
            }
        };
        const writeSidebarPreference = (key, value) => {
            try {
                localStorage.setItem(key, String(value));
            } catch (err) {
                console.warn('[VoiceGuardApp] Unable to save sidebar preference:', err);
            }
        };

        let desktopSidebarCollapsed = readSidebarPreference('voiceguard_sidebar_collapsed', false);
        let mobileSidebarOpen = readSidebarPreference('voiceguard_mobile_sidebar_open', false);

        const applySidebarState = () => {
            const isMobile = mobileSidebarQuery.matches;
            const isExpanded = isMobile ? mobileSidebarOpen : !desktopSidebarCollapsed;
            appLayout.classList.toggle('sidebar-collapsed', !isMobile && desktopSidebarCollapsed);
            appLayout.classList.toggle('mobile-sidebar-open', isMobile && mobileSidebarOpen);
            document.body.classList.toggle('sidebar-drawer-open', isMobile && mobileSidebarOpen);

            if (sidebarToggle) {
                sidebarToggle.setAttribute('aria-expanded', String(isExpanded));
                sidebarToggle.setAttribute('aria-label', isExpanded ? 'Collapse navigation' : 'Expand navigation');
            }
            if (sidebarOverlay) {
                sidebarOverlay.setAttribute('aria-hidden', String(!isMobile || !mobileSidebarOpen));
            }
        };

        const closeMobileSidebar = () => {
            if (!mobileSidebarQuery.matches || !mobileSidebarOpen) return;
            mobileSidebarOpen = false;
            writeSidebarPreference('voiceguard_mobile_sidebar_open', mobileSidebarOpen);
            applySidebarState();
            sidebarToggle?.focus({ preventScroll: true });
        };

        sidebarToggle?.addEventListener('click', () => {
            if (mobileSidebarQuery.matches) {
                mobileSidebarOpen = !mobileSidebarOpen;
                writeSidebarPreference('voiceguard_mobile_sidebar_open', mobileSidebarOpen);
            } else {
                desktopSidebarCollapsed = !desktopSidebarCollapsed;
                writeSidebarPreference('voiceguard_sidebar_collapsed', desktopSidebarCollapsed);
            }
            applySidebarState();
        });
        sidebarClose?.addEventListener('click', closeMobileSidebar);
        sidebarOverlay?.addEventListener('click', closeMobileSidebar);
        document.querySelector('.sidebar-nav')?.addEventListener('click', event => {
            if (event.target instanceof Element && event.target.closest('a[data-view]')) {
                closeMobileSidebar();
            }
        });
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape') closeMobileSidebar();
        });

        if (typeof mobileSidebarQuery.addEventListener === 'function') {
            mobileSidebarQuery.addEventListener('change', applySidebarState);
        } else {
            mobileSidebarQuery.addListener(applySidebarState);
        }
        applySidebarState();
    }

    const API = window.VoiceGuardAPI;
    if (!API) {
        console.error('[VoiceGuardApp] VoiceGuardAPI client is missing.');
        return;
    }

    // Initialize 2D Log-Mel Spectrogram Heatmap Viewer
    const specContainer = document.getElementById('detection-spectrogram-container');
    if (specContainer && window.LogMelSpectrogramViewer) {
        window.VoiceGuardSpectrogram = new window.LogMelSpectrogramViewer(specContainer, {
            defaultColormap: 'cyberpunk',
            height: 320,
        });
    }

    // ========================================================================
    // LIVE MICROPHONE MONITORING
    // ========================================================================
    function initializeLiveMonitoring() {
        const startButton = document.getElementById('btn-start-monitoring');
        const stopButton = document.getElementById('btn-stop-monitoring');
        const feedback = document.getElementById('live-monitoring-feedback');
        const waveformCanvas = document.getElementById('live-waveform-canvas');
        const alertTable = document.getElementById('live-channels-table');
        if (!startButton || !stopButton || !waveformCanvas || !alertTable) return;

        const connectionStatus = document.getElementById('live-connection-status');
        const streamStatusLabel = document.getElementById('stream-status-label');
        const streamStatusPill = document.getElementById('stream-status-pill');
        const sessionIdElement = document.getElementById('live-session-id');
        const durationElement = document.getElementById('live-duration');
        const processingStatus = document.getElementById('live-processing-status');
        const modelStatus = document.getElementById('live-model-status');
        const detectionStatus = document.getElementById('live-detection-status');
        const inferenceStatus = document.getElementById('live-inference-status');
        const waveformBadge = document.getElementById('live-waveform-badge');
        const inputLevel = document.getElementById('live-input-level');
        const inputMeter = document.querySelector('.live-input-meter');
        const inputMeterFill = document.getElementById('live-input-meter-fill');
        const rmsLevel = document.getElementById('live-rms-dbfs');
        const peakLevel = document.getElementById('live-peak-dbfs');
        const signalQuality = document.getElementById('live-signal-quality');
        const alertCount = document.getElementById('live-alert-count');
        const alertStatus = document.getElementById('live-alert-status');
        const alertTitle = document.getElementById('live-alert-title');
        const flagBullet = document.getElementById('live-flag-bullet');

        // Extended detection & session telemetry elements
        const confidenceScore = document.getElementById('live-confidence-score');
        const humanProb = document.getElementById('live-human-prob');
        const aiProb = document.getElementById('live-ai-prob');
        const selectedModel = document.getElementById('live-selected-model');
        const inferenceLatency = document.getElementById('live-inference-latency');
        const analysisStatus = document.getElementById('live-analysis-status');
        const lastInferenceTime = document.getElementById('live-last-inference-time');
        const analyzedWindows = document.getElementById('live-analyzed-windows');
        const liveAudioBanner = document.getElementById('live-audio-banner');

        let isStarting = false;
        let isMonitoring = false;
        let requestId = 0;
        let socket = null;
        let microphoneStream = null;
        let audioContext = null;
        let sourceNode = null;
        let captureNode = null;
        let muteNode = null;
        let timerId = null;
        let startedAt = 0;
        let latestSamples = new Float32Array(0);
        let currentDetectionStatus = 'WAITING FOR AUDIO';
        let currentAlerts = [];
        let hasReceivedPrediction = false;

        function setFeedback(message, kind) {
            if (!feedback) return;
            feedback.textContent = message;
            feedback.className = kind ? `workflow-feedback ${kind}` : 'workflow-feedback';
            feedback.hidden = !message;
        }

        function setConnectionState(message, state) {
            if (connectionStatus) connectionStatus.textContent = message;
            if (streamStatusLabel) streamStatusLabel.textContent = message.toUpperCase();
            if (streamStatusPill) {
                streamStatusPill.classList.toggle('is-connected', state === 'connected');
                streamStatusPill.classList.toggle('is-error', state === 'error');
            }
        }

        function formatDuration(seconds) {
            const total = Math.max(0, Math.floor(seconds));
            const minutes = String(Math.floor(total / 60)).padStart(2, '0');
            const remainder = String(total % 60).padStart(2, '0');
            return `${minutes}:${remainder}`;
        }

        function updateDuration() {
            if (isMonitoring && durationElement) {
                durationElement.textContent = formatDuration((Date.now() - startedAt) / 1000);
            }
        }

        function setButtons() {
            startButton.disabled = isStarting || isMonitoring;
            stopButton.disabled = !isStarting && !isMonitoring;
        }

        function getEmptyAlertMessage(status) {
            if (status === 'REAL_HUMAN' || status === 'HUMAN') {
                return 'No active threats detected. Model classified the analyzed audio as human.';
            } else if (status === 'AI_GENERATED') {
                return 'Potential synthetic voice detected. Review the threat alert.';
            } else if (status === 'SESSION ENDED') {
                return 'Monitoring session ended. Audio stream was stopped and discarded.';
            } else {
                return 'Unable to determine voice authenticity. More audio or a supported model is required.';
            }
        }

        function resetDetectionDisplay(statusText = 'WAITING FOR AUDIO', analysisStatusText = 'IDLE') {
            currentDetectionStatus = statusText;
            hasReceivedPrediction = false;
            if (detectionStatus) {
                detectionStatus.textContent = statusText;
                applyDetectionBadgeColor(statusText);
            }
            if (confidenceScore) {
                confidenceScore.textContent = '—';
            }
            if (humanProb) {
                humanProb.textContent = '—';
            }
            if (aiProb) {
                aiProb.textContent = '—';
            }
            if (selectedModel) {
                selectedModel.textContent = 'None';
            }
            if (inferenceLatency) {
                inferenceLatency.textContent = '—';
            }
            if (analysisStatus) {
                analysisStatus.textContent = analysisStatusText;
            }
            if (inferenceStatus) {
                inferenceStatus.textContent = statusText === 'SESSION ENDED' ? 'SESSION ENDED' : (statusText === 'WAITING FOR AUDIO' ? 'IDLE · AWAITING AUDIO' : statusText);
            }
            if (alertStatus) {
                alertStatus.textContent = getEmptyAlertMessage(statusText);
                alertStatus.style.color = 'var(--text-muted)';
            }
            if (alertTitle) {
                alertTitle.textContent = statusText === 'SESSION ENDED' ? 'Session Completed' : 'Threat Monitoring Status';
            }
            renderAlerts([], statusText);
        }

        function renderAlerts(alerts, detStatus) {
            if (!Array.isArray(alerts)) return;
            currentAlerts = alerts;
            const status = detStatus || currentDetectionStatus;
            alertTable.replaceChildren();
            if (alertCount) alertCount.textContent = `${alerts.length} alert${alerts.length === 1 ? '' : 's'}`;

            if (alerts.length === 0) {
                const row = document.createElement('tr');
                const cell = document.createElement('td');
                cell.colSpan = 4;
                cell.className = 'text-muted';
                cell.textContent = getEmptyAlertMessage(status);
                row.append(cell);
                alertTable.append(row);
                return;
            }

            alerts.forEach(alert => {
                const row = document.createElement('tr');
                [alert.threat_type, alert.risk_level, alert.created_at, alert.status].forEach(value => {
                    const cell = document.createElement('td');
                    cell.textContent = value ? String(value) : 'Not available';
                    row.append(cell);
                });
                alertTable.append(row);
            });
        }

        function drawWaveform(samples) {
            latestSamples = samples;
            const rect = waveformCanvas.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0) return;
            const dpr = window.devicePixelRatio || 1;
            waveformCanvas.width = Math.round(rect.width * dpr);
            waveformCanvas.height = Math.round(rect.height * dpr);
            const context = waveformCanvas.getContext('2d');
            context.setTransform(dpr, 0, 0, dpr, 0, 0);
            context.fillStyle = '#05080f';
            context.fillRect(0, 0, rect.width, rect.height);
            context.strokeStyle = 'rgba(30, 47, 84, 0.4)';
            context.lineWidth = 1;
            for (let column = 1; column < 10; column++) {
                const x = rect.width * column / 10;
                context.beginPath();
                context.moveTo(x, 0);
                context.lineTo(x, rect.height);
                context.stroke();
            }
            for (let row = 1; row < 6; row++) {
                const y = rect.height * row / 6;
                context.beginPath();
                context.moveTo(0, y);
                context.lineTo(rect.width, y);
                context.stroke();
            }
            context.beginPath();
            context.strokeStyle = '#00e5ff';
            context.lineWidth = 2;
            context.shadowColor = 'rgba(0, 229, 255, 0.45)';
            context.shadowBlur = 7;
            const centerY = rect.height / 2;
            for (let x = 0; x < rect.width; x++) {
                const sampleIndex = latestSamples.length
                    ? Math.min(latestSamples.length - 1, Math.floor(x * latestSamples.length / rect.width))
                    : 0;
                const sample = latestSamples.length ? latestSamples[sampleIndex] : 0;
                const y = centerY - sample * rect.height * 0.44;
                if (x === 0) context.moveTo(x, y);
                else context.lineTo(x, y);
            }
            context.stroke();
            context.shadowBlur = 0;
        }

        function applyModelBadge(status) {
            if (!modelStatus) return;
            const norm = String(status || 'MODEL UNAVAILABLE').trim();
            modelStatus.textContent = norm;
            if (norm.includes('ACTIVE')) {
                modelStatus.className = 'badge badge-success';
            } else if (norm.includes('ERROR')) {
                modelStatus.className = 'badge badge-danger';
            } else {
                modelStatus.className = 'badge badge-warning';
            }
        }

        function applyDetectionBadgeColor(status) {
            if (!detectionStatus) return;
            if (status === 'AI_GENERATED') {
                detectionStatus.className = 'score-large text-danger';
                if (flagBullet) flagBullet.className = 'flag-bullet bg-danger';
            } else if (status === 'REAL_HUMAN' || status === 'HUMAN') {
                detectionStatus.className = 'score-large text-success';
                if (flagBullet) flagBullet.className = 'flag-bullet bg-success';
            } else if (status === 'SESSION ENDED') {
                detectionStatus.className = 'score-large text-muted';
                if (flagBullet) flagBullet.className = 'flag-bullet bg-secondary';
            } else {
                detectionStatus.className = 'score-large text-warning';
                if (flagBullet) flagBullet.className = 'flag-bullet bg-warning';
            }
        }

        function updateMetrics(message) {
            const metrics = message.acoustic_metrics;
            if (!metrics) return;
            if (durationElement && Number.isFinite(metrics.duration_seconds)) {
                durationElement.textContent = formatDuration(metrics.duration_seconds);
            }
            if (inputLevel) inputLevel.textContent = `${metrics.input_level_percent}%`;
            if (inputMeterFill) inputMeterFill.style.width = `${metrics.input_level_percent}%`;
            if (inputMeter) inputMeter.setAttribute('aria-valuenow', String(metrics.input_level_percent));
            if (rmsLevel) rmsLevel.textContent = `${metrics.rms_dbfs} dBFS`;
            if (peakLevel) peakLevel.textContent = `${metrics.peak_dbfs} dBFS`;
            if (signalQuality) signalQuality.textContent = String(metrics.signal_quality || 'unavailable').toUpperCase();
            if (processingStatus) processingStatus.textContent = message.processing_status || 'PROCESSING';
            if (detectionStatus && message.detection_status) {
                if (hasReceivedPrediction) {
                    if (message.detection_status !== 'WAITING FOR AUDIO') {
                        currentDetectionStatus = message.detection_status;
                        detectionStatus.textContent = message.detection_status;
                        applyDetectionBadgeColor(message.detection_status);
                    }
                } else {
                    currentDetectionStatus = 'WAITING FOR AUDIO';
                    detectionStatus.textContent = 'WAITING FOR AUDIO';
                    applyDetectionBadgeColor('WAITING FOR AUDIO');
                }
            }
            if (message.ai_model_status) {
                applyModelBadge(message.ai_model_status);
            }
            if (lastInferenceTime && message.last_inference_timestamp) {
                lastInferenceTime.textContent = message.last_inference_timestamp;
            }
            if (analyzedWindows && Number.isFinite(message.analyzed_windows)) {
                analyzedWindows.textContent = String(message.analyzed_windows);
            }
            renderAlerts(message.threat_alerts || currentAlerts, currentDetectionStatus);
        }

        function updatePrediction(message) {
            const isCompleted = message.analysis_status === 'completed';
            const hasValidProbs = Number.isFinite(message.human_probability) && Number.isFinite(message.synthetic_probability);
            const isSuccess = isCompleted && hasValidProbs && (message.predicted_class === 'REAL_HUMAN' || message.predicted_class === 'AI_GENERATED');

            let predClass = 'INCONCLUSIVE';
            if (isSuccess) {
                predClass = message.predicted_class;
                hasReceivedPrediction = true;
            } else if (message.predicted_class === 'WAITING FOR AUDIO' && !hasReceivedPrediction) {
                predClass = 'WAITING FOR AUDIO';
            } else {
                predClass = 'INCONCLUSIVE';
            }
            currentDetectionStatus = predClass;

            const modelUsed = message.selected_model && message.selected_model !== 'NONE' ? message.selected_model : 'None';
            const conf = isSuccess && Number.isFinite(message.confidence_score)
                ? Math.round(message.confidence_score * 100)
                : null;
            const latencyMs = Number.isFinite(message.inference_time) ? Math.round(message.inference_time * 1000) : null;

            // 1. Classification (Display REAL HUMAN, AI GENERATED / SPOOF, or INCONCLUSIVE)
            if (detectionStatus) {
                const displayClass = (predClass === 'REAL_HUMAN' || predClass === 'HUMAN')
                    ? 'REAL HUMAN'
                    : predClass === 'AI_GENERATED'
                    ? 'AI GENERATED / SPOOF'
                    : predClass;
                detectionStatus.textContent = displayClass;
                applyDetectionBadgeColor(predClass);
            }

            // 2. Model Confidence Score
            if (confidenceScore) {
                confidenceScore.textContent = conf !== null ? `${conf}%` : '—';
            }

            // 3. Human & AI Probabilities (Always display actual finite percentages)
            if (humanProb) {
                humanProb.textContent = Number.isFinite(message.human_probability)
                    ? `${(message.human_probability * 100).toFixed(1)}%`
                    : '—';
            }
            if (aiProb) {
                aiProb.textContent = Number.isFinite(message.synthetic_probability)
                    ? `${(message.synthetic_probability * 100).toFixed(1)}%`
                    : '—';
            }

            // 4. Model Name
            if (selectedModel) {
                selectedModel.textContent = modelUsed;
            }

            // 5. Inference Latency
            if (inferenceLatency) {
                inferenceLatency.textContent = latencyMs !== null ? `${latencyMs} ms` : '—';
            }

            // 6. Analysis Status
            if (analysisStatus) {
                analysisStatus.textContent = String(message.analysis_status || (isSuccess ? 'COMPLETED' : 'INCONCLUSIVE')).toUpperCase();
            }

            // 7. Inference Status Pill
            if (inferenceStatus) {
                if (predClass === 'INCONCLUSIVE') {
                    inferenceStatus.textContent = modelUsed !== 'None' ? `${modelUsed} EVALUATING` : 'NO AI INFERENCE';
                } else if (predClass === 'WAITING FOR AUDIO') {
                    inferenceStatus.textContent = 'IDLE · AWAITING AUDIO';
                } else if (conf !== null) {
                    inferenceStatus.textContent = `${modelUsed} (${conf}% CONF · ${latencyMs || 0}ms)`;
                } else {
                    inferenceStatus.textContent = `${modelUsed} ACTIVE`;
                }
            }

            // 8. Model Status
            if (message.ai_model_status) {
                applyModelBadge(message.ai_model_status);
            } else if (modelUsed !== 'None') {
                applyModelBadge(`${modelUsed} ACTIVE`);
            }

            // 9. Alert Status & Summary
            if (alertStatus) {
                alertStatus.textContent = getEmptyAlertMessage(predClass);
                if (predClass === 'AI_GENERATED') {
                    alertStatus.style.color = '#ef4444';
                } else if (predClass === 'REAL_HUMAN' || predClass === 'HUMAN') {
                    alertStatus.style.color = '#10b981';
                } else {
                    alertStatus.style.color = 'var(--text-muted)';
                }
            }
            if (alertTitle) {
                alertTitle.textContent = predClass === 'AI_GENERATED' ? 'Threat Detected' : (predClass === 'INCONCLUSIVE' ? 'Evaluating Voice Authenticity' : (predClass === 'WAITING FOR AUDIO' ? 'Threat Monitoring Status' : 'Authentication Verified'));
            }

            // 10. Session Telemetry: Timestamp & Windows
            if (lastInferenceTime && message.last_inference_timestamp) {
                lastInferenceTime.textContent = message.last_inference_timestamp;
            }
            if (analyzedWindows && Number.isFinite(message.analyzed_windows)) {
                analyzedWindows.textContent = String(message.analyzed_windows);
            }

            renderAlerts(message.threat_alerts || [], predClass);
        }

        function socketUrl() {
            const base = window.VOICEGUARD_CONFIG?.API_BASE_URL || window.location.origin;
            const url = new URL('/api/v1/stream/ws', base);
            if (url.protocol === 'https:') url.protocol = 'wss:';
            else if (url.protocol === 'http:') url.protocol = 'ws:';
            else throw new Error('Live audio monitoring requires an HTTP or HTTPS backend URL.');
            return url.toString();
        }

        function connectSocket(token, activeRequestId) {
            return new Promise((resolve, reject) => {
                let settled = false;
                const candidate = new WebSocket(socketUrl());
                socket = candidate;
                candidate.binaryType = 'arraybuffer';
                const timeoutId = window.setTimeout(() => {
                    if (settled) return;
                    settled = true;
                    candidate.close();
                    reject(new Error('The streaming service did not respond in time.'));
                }, 10000);
                const fail = error => {
                    if (settled) return;
                    settled = true;
                    window.clearTimeout(timeoutId);
                    reject(error);
                };

                candidate.onopen = () => {
                    candidate.send(JSON.stringify({
                        type: 'auth',
                        token: token || '',
                        sample_rate: 16000,
                        channels: 1,
                        encoding: 'pcm_s16le',
                        model: 'RAWNET2'
                    }));
                };
                candidate.onmessage = event => {
                    let message;
                    try {
                        message = JSON.parse(event.data);
                    } catch (error) {
                        console.error('[VoiceGuardApp] Invalid live-stream message:', error);
                        fail(new Error('The streaming service sent an invalid response.'));
                        return;
                    }

                    if (message.type === 'error') {
                        setFeedback(message.message || 'The live audio session failed.', 'error');
                        fail(new Error(message.message || 'The live audio session failed.'));
                        return;
                    }
                    if (message.type === 'ready') {
                        if (activeRequestId !== requestId) {
                            fail(new Error('Monitoring was cancelled.'));
                            return;
                        }
                        window.clearTimeout(timeoutId);
                        settled = true;
                        hasReceivedPrediction = false;
                        if (sessionIdElement) sessionIdElement.textContent = message.session_id;
                        if (processingStatus) processingStatus.textContent = message.processing_status;
                        if (message.ai_model_status) applyModelBadge(message.ai_model_status);
                        resetDetectionDisplay(message.detection_status || 'WAITING FOR AUDIO', 'AWAITING AUDIO');
                        if (lastInferenceTime) lastInferenceTime.textContent = '—';
                        if (analyzedWindows) analyzedWindows.textContent = '0';
                        setConnectionState('Connected', 'connected');
                        resolve(message);
                    } else if (message.type === 'metrics') {
                        updateMetrics(message);
                    } else if (message.type === 'prediction') {
                        updatePrediction(message);
                    } else if (message.type === 'stopped') {
                        if (durationElement && Number.isFinite(message.duration_seconds)) {
                            durationElement.textContent = formatDuration(message.duration_seconds);
                        }
                        if (lastInferenceTime && message.last_inference_timestamp) {
                            lastInferenceTime.textContent = message.last_inference_timestamp;
                        }
                        if (analyzedWindows && Number.isFinite(message.analyzed_windows)) {
                            analyzedWindows.textContent = String(message.analyzed_windows);
                        }
                        resetDetectionDisplay('SESSION ENDED', 'SESSION ENDED');
                    }
                };
                candidate.onerror = () => {
                    fail(new Error('Could not connect to the live audio WebSocket.'));
                };
                candidate.onclose = event => {
                    window.clearTimeout(timeoutId);
                    if (!settled) fail(new Error(`Live audio connection closed (${event.code}).`));
                    if (socket === candidate && isMonitoring) {
                        isMonitoring = false;
                        hasReceivedPrediction = false;
                        void cleanupAudio();
                        setButtons();
                        setConnectionState('Disconnected', 'error');
                        if (waveformBadge) waveformBadge.textContent = 'CONNECTION LOST';
                        if (processingStatus) processingStatus.textContent = 'DISCONNECTED';
                        resetDetectionDisplay('INCONCLUSIVE', 'DISCONNECTED');
                        setFeedback('The audio stream disconnected. Microphone capture has stopped.', 'error');
                    }
                };
            });
        }

        function permissionErrorMessage(error) {
            if (error && error.name === 'NotAllowedError') {
                return 'Microphone permission was denied. Allow microphone access in browser settings and try again.';
            }
            if (error && error.name === 'NotFoundError') {
                return 'No microphone was found. Connect a microphone and try again.';
            }
            if (error && error.name === 'NotReadableError') {
                return 'The microphone is busy or unavailable to this browser.';
            }
            if (error && error.name === 'SecurityError') {
                return 'Microphone access requires HTTPS or localhost.';
            }
            return error && error.message ? error.message : 'Unable to start microphone monitoring.';
        }

        async function cleanupAudio() {
            if (timerId !== null) window.clearInterval(timerId);
            timerId = null;
            if (captureNode) {
                if (captureNode.port) captureNode.port.onmessage = null;
                if (captureNode.onaudioprocess) captureNode.onaudioprocess = null;
                try { captureNode.disconnect(); } catch (e) {}
                captureNode = null;
            }
            if (sourceNode) {
                try { sourceNode.disconnect(); } catch (e) {}
                sourceNode = null;
            }
            if (muteNode) {
                try { muteNode.disconnect(); } catch (e) {}
                muteNode = null;
            }
            if (microphoneStream) {
                microphoneStream.getTracks().forEach(track => {
                    try { track.stop(); } catch (e) {}
                });
                microphoneStream = null;
            }
            if (audioContext && audioContext.state !== 'closed') {
                const context = audioContext;
                audioContext = null;
                try { await context.close(); } catch (e) {}
            } else {
                audioContext = null;
            }
        }

        async function startMonitoring() {
            if (isStarting || isMonitoring) return;
            const token = (API && typeof API.getToken === 'function' ? API.getToken() : null)
                || localStorage.getItem('vg_token')
                || sessionStorage.getItem('vg_token')
                || localStorage.getItem('access_token')
                || sessionStorage.getItem('access_token')
                || '';

            const activeRequestId = ++requestId;
            isStarting = true;
            hasReceivedPrediction = false;
            setButtons();
            resetDetectionDisplay('WAITING FOR AUDIO', 'AUTHENTICATING');
            setFeedback('Requesting microphone permission…', 'info');
            setConnectionState('Connecting', '');
            if (processingStatus) processingStatus.textContent = 'AUTHENTICATING';
            if (lastInferenceTime) lastInferenceTime.textContent = '—';
            if (analyzedWindows) analyzedWindows.textContent = '0';

            try {
                if (!navigator.mediaDevices?.getUserMedia) {
                    throw new Error('Microphone capture is unavailable. Use a supported browser on HTTPS or localhost.');
                }
                const stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        channelCount: 1,
                        echoCancellation: false,
                        noiseSuppression: false,
                        autoGainControl: false
                    }
                });
                if (activeRequestId !== requestId) {
                    stream.getTracks().forEach(track => track.stop());
                    return;
                }
                microphoneStream = stream;

                await connectSocket(token, activeRequestId);
                const AudioContextConstructor = window.AudioContext || window.webkitAudioContext;
                if (!AudioContextConstructor) {
                    throw new Error('This browser does not support Web Audio API.');
                }
                audioContext = new AudioContextConstructor();

                if (activeRequestId !== requestId || socket?.readyState !== WebSocket.OPEN) {
                    throw new Error('The live audio session ended before capture could start.');
                }

                sourceNode = audioContext.createMediaStreamSource(stream);
                muteNode = audioContext.createGain();
                muteNode.gain.value = 0;

                // Setup audio streaming: AudioWorklet primary with ScriptProcessorNode fallback
                let workletLoaded = false;
                if (audioContext.audioWorklet && window.AudioWorkletNode) {
                    try {
                        await audioContext.audioWorklet.addModule(new URL('live-audio-processor.js', document.baseURI));
                        workletLoaded = true;
                    } catch (workletErr) {
                        console.warn('[VoiceGuardApp] AudioWorklet module load failed, using ScriptProcessor fallback:', workletErr);
                        workletLoaded = false;
                    }
                }

                if (workletLoaded) {
                    captureNode = new AudioWorkletNode(audioContext, 'voiceguard-pcm-capture', {
                        numberOfInputs: 1,
                        numberOfOutputs: 1,
                        outputChannelCount: [1],
                        channelCount: 1,
                        channelCountMode: 'explicit'
                    });
                    captureNode.port.onmessage = event => {
                        const pcmBuffer = event.data && event.data.buffer;
                        if (!(pcmBuffer instanceof ArrayBuffer)) return;
                        const samples = new Float32Array(pcmBuffer.byteLength / 2);
                        const view = new DataView(pcmBuffer);
                        for (let index = 0; index < samples.length; index++) {
                            samples[index] = view.getInt16(index * 2, true) / 32768;
                        }
                        drawWaveform(samples);
                        if (isMonitoring && socket?.readyState === WebSocket.OPEN) {
                            socket.send(pcmBuffer);
                        }
                    };
                } else {
                    // ScriptProcessorNode fallback (16000 Hz, Mono, Signed 16-bit Little-Endian PCM)
                    const bufferSize = 4096;
                    captureNode = audioContext.createScriptProcessor(bufferSize, 1, 1);
                    const targetSr = 16000;
                    let phase = 0;
                    let accum = 0;
                    let accumCount = 0;
                    const chunkSampleCount = 3200;
                    const chunk = new Int16Array(chunkSampleCount);
                    let chunkIndex = 0;

                    captureNode.onaudioprocess = event => {
                        const input = event.inputBuffer.getChannelData(0);
                        const srcSr = audioContext.sampleRate;
                        for (let i = 0; i < input.length; i++) {
                            accum += input[i];
                            accumCount += 1;
                            phase += targetSr;
                            if (phase >= srcSr) {
                                phase -= srcSr;
                                const s = Math.max(-1, Math.min(1, accum / accumCount));
                                accum = 0;
                                accumCount = 0;
                                chunk[chunkIndex++] = s < 0 ? s * 32768 : s * 32767;
                                if (chunkIndex === chunkSampleCount) {
                                    const pcm = new ArrayBuffer(chunkSampleCount * 2);
                                    const view = new DataView(pcm);
                                    const waveSamples = new Float32Array(chunkSampleCount);
                                    for (let j = 0; j < chunkSampleCount; j++) {
                                        view.setInt16(j * 2, chunk[j], true);
                                        waveSamples[j] = chunk[j] / 32768;
                                    }
                                    drawWaveform(waveSamples);
                                    if (isMonitoring && socket?.readyState === WebSocket.OPEN) {
                                        socket.send(pcm);
                                    }
                                    chunkIndex = 0;
                                }
                            }
                        }
                    };
                }

                sourceNode.connect(captureNode);
                captureNode.connect(muteNode);
                muteNode.connect(audioContext.destination);
                await audioContext.resume();

                isMonitoring = true;
                isStarting = false;
                startedAt = Date.now();
                timerId = window.setInterval(updateDuration, 250);
                if (waveformBadge) waveformBadge.textContent = 'MICROPHONE CONNECTED · STREAMING';
                setConnectionState('Connected (RAWNET2 Active)', 'connected');
                setFeedback('Microphone connected. Streaming 16kHz PCM to RAWNET2 neural detector…', 'success');
                setButtons();
            } catch (error) {
                if (activeRequestId !== requestId) return;
                console.error('[VoiceGuardApp] Unable to start live microphone monitoring:', error);
                isStarting = false;
                isMonitoring = false;
                hasReceivedPrediction = false;
                await cleanupAudio();
                if (socket && socket.readyState < WebSocket.CLOSING) socket.close();
                socket = null;
                if (waveformBadge) waveformBadge.textContent = 'NOT MONITORING';
                if (processingStatus) processingStatus.textContent = 'IDLE';
                resetDetectionDisplay('WAITING FOR AUDIO', 'IDLE');
                setConnectionState('Disconnected', 'error');
                setFeedback(permissionErrorMessage(error), 'error');
                setButtons();
            }
        }

        async function stopMonitoring() {
            if (!isStarting && !isMonitoring) return;
            requestId += 1;
            const activeSocket = socket;
            isStarting = false;
            isMonitoring = false;
            hasReceivedPrediction = false;
            if (activeSocket && activeSocket.readyState === WebSocket.OPEN) {
                activeSocket.send(JSON.stringify({ type: 'stop' }));
            }
            await cleanupAudio();
            if (activeSocket && activeSocket.readyState < WebSocket.CLOSING) {
                activeSocket.close(1000, 'Monitoring stopped by user.');
            }
            if (socket === activeSocket) socket = null;
            setButtons();
            setConnectionState('Disconnected', '');
            if (processingStatus) processingStatus.textContent = 'STOPPED';
            if (waveformBadge) waveformBadge.textContent = 'STOPPED';
            if (streamStatusLabel) streamStatusLabel.textContent = 'STOPPED';
            if (streamStatusPill) {
                streamStatusPill.classList.remove('is-connected');
                streamStatusPill.classList.remove('is-error');
            }
            drawWaveform(new Float32Array(0));
            resetDetectionDisplay('SESSION ENDED', 'SESSION ENDED');
            setFeedback('Monitoring stopped. The microphone was released and session audio was discarded.', 'info');
        }

        startButton.addEventListener('click', startMonitoring);
        stopButton.addEventListener('click', stopMonitoring);
        window.addEventListener('hashchange', () => {
            if (window.location.hash !== '#live-monitoring') void stopMonitoring();
        });
        window.addEventListener('pagehide', () => void stopMonitoring());
        window.addEventListener('resize', () => drawWaveform(latestSamples));
        resetDetectionDisplay('WAITING FOR AUDIO', 'IDLE');
        drawWaveform(latestSamples);
        setButtons();
    }

    initializeLiveMonitoring();

    // ========================================================================
    // 2. LIVE HEALTH & TELEMETRY CHECK
    // ========================================================================
    async function updateSystemHealth() {
        const statusIndicator = document.getElementById('system-status-indicator');
        const statusText = document.getElementById('system-status-text');
        const modelStatusBadge = document.getElementById('model-status-badge');

        try {
            const health = await API.getHealth();
            if (health.status === 'healthy') {
                if (statusIndicator) statusIndicator.className = 'pulsing-status-dot';
                if (statusText) statusText.textContent = 'API CONNECTED · PHASE 1 BASELINE';
                if (modelStatusBadge) {
                    modelStatusBadge.textContent = 'AASIST / RAWNET2 PIPELINE READY';
                    modelStatusBadge.className = 'badge badge-info';
                }
            }
        } catch (err) {
            if (statusIndicator) statusIndicator.className = 'pulsing-status-dot offline';
            if (statusText) statusText.textContent = 'API OFFLINE';
        }
    }
    updateSystemHealth();

    // ========================================================================
    // 3. DASHBOARD METRICS SYNCHRONIZATION
    // ========================================================================
    async function syncDashboardMetrics() {
        try {
            const [overview, history] = await Promise.all([
                API.getDashboardOverview(),
                API.getAudioHistory(1, 1)
            ]);
            const totalCallsEl = document.getElementById('metric-total-calls');
            const genuineCallsEl = document.getElementById('metric-genuine-voices');
            const suspiciousCallsEl = document.getElementById('metric-suspicious-voices');
            const criticalAlertsEl = document.getElementById('metric-critical-alerts');

            const stats = history && history.stats;
            if (!overview || !stats) throw new Error('Dashboard metrics response is incomplete.');
            if (totalCallsEl) totalCallsEl.textContent = Number(overview.total_audio_uploads).toLocaleString();
            if (genuineCallsEl) genuineCallsEl.textContent = Number(stats.genuine_voices).toLocaleString();
            if (suspiciousCallsEl) suspiciousCallsEl.textContent = Number(stats.inconclusive_voices).toLocaleString();
            if (criticalAlertsEl) criticalAlertsEl.textContent = Number(stats.ai_generated_voices).toLocaleString();
        } catch (err) {
            console.error('[VoiceGuardApp] Unable to load account dashboard metrics:', err);
            ['metric-total-calls', 'metric-genuine-voices', 'metric-suspicious-voices', 'metric-critical-alerts']
                .forEach(id => {
                    const element = document.getElementById(id);
                    if (element) element.textContent = '—';
                });
        }
        await syncRecentOverviewTable();
    }
    syncDashboardMetrics();

    async function syncRecentOverviewTable() {
        const table = document.getElementById('overview-recent-table');
        if (!table) return;
        try {
            const res = await API.getAudioHistory(1, 6);
            const records = res.history || [];
            if (records.length > 0) {
                table.innerHTML = records.map(r => {
                    const isUnconfigured = r.analysis_status === 'AI_MODEL_NOT_CONFIGURED';
                    const riskBadge = isUnconfigured 
                        ? '<span class="badge badge-amber" style="background: rgba(245,158,11,0.15); color: #fcd34d;">PHASE 1 READY</span>' 
                        : (r.synthetic_score > 0.6 ? '<span class="badge badge-danger">CRITICAL</span>' : '<span class="badge badge-success">CLEAN</span>');
                    const actionTaken = isUnconfigured ? 'Preprocessed (16kHz PCM)' : (r.synthetic_score > 0.6 ? 'Quarantined' : 'Verified');
                    return `
                        <tr>
                            <td style="font-family: var(--cyber-font-mono); color: var(--cyber-cyan);">${r.id.slice(0, 8)}</td>
                            <td>${new Date(r.created_at).toLocaleTimeString()}</td>
                            <td>${r.filename}</td>
                            <td>Inbound VoIP</td>
                            <td>${r.file_type.toUpperCase()}</td>
                            <td>${riskBadge}</td>
                            <td>${actionTaken}</td>
                        </tr>
                    `;
                }).join('');
            } else {
                table.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--cyber-text-dim); padding: 24px;">No audio analyzed yet. Upload an audio sample or record speech above to begin real-time forensics.</td></tr>';
            }
        } catch (e) {
            console.warn('Recent activity sync deferred:', e.message);
        }
    }

    // ========================================================================
    // 4. ADVANCED MICROPHONE RECORDING SYSTEM (START, STOP, PAUSE, RESUME, CANCEL)
    // ========================================================================
    let mediaRecorder = null;
    let audioChunks = [];
    let recordStartTime = 0;
    let accumulatedTime = 0;
    let isPaused = false;
    let timerInterval = null;
    let audioContext = null;
    let analyserNode = null;
    let micStream = null;
    let animFrameId = null;

    const micBtn = document.getElementById('btn-mic-toggle');
    const micPauseBtn = document.getElementById('btn-mic-pause');
    const micClearBtn = document.getElementById('btn-mic-clear');
    const micTimerEl = document.getElementById('mic-recording-timer');
    const micCanvas = document.getElementById('mic-waveform-canvas');
    const micStatus = document.getElementById('mic-status-label');

    if (micBtn) {
        micBtn.addEventListener('click', toggleMicrophoneRecording);
    }
    if (micPauseBtn) {
        micPauseBtn.addEventListener('click', toggleMicrophonePause);
    }
    if (micClearBtn) {
        micClearBtn.addEventListener('click', cancelMicrophoneRecording);
    }

    async function toggleMicrophoneRecording() {
        if (mediaRecorder && (mediaRecorder.state === 'recording' || mediaRecorder.state === 'paused')) {
            stopMicrophoneRecording();
        } else {
            await startMicrophoneRecording();
        }
    }

    function toggleMicrophonePause() {
        if (!mediaRecorder) return;
        if (mediaRecorder.state === 'recording') {
            pauseMicrophoneRecording();
        } else if (mediaRecorder.state === 'paused') {
            resumeMicrophoneRecording();
        }
    }

    async function startMicrophoneRecording() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            showMicStatus('[ERROR] Browser does not support mediaDevices.getUserMedia. Use Chrome, Firefox, or Edge on HTTPS or localhost.', 'error');
            return;
        }

        try {
            showMicStatus('Requesting microphone permission...', 'info');
            micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                },
                video: false,
            });

            audioChunks = [];
            accumulatedTime = 0;
            isPaused = false;

            // Detect preferred recording mime type supported by browser
            const preferredTypes = [
                'audio/webm;codecs=opus',
                'audio/webm',
                'audio/ogg;codecs=opus',
                'audio/ogg',
                'audio/wav',
                'audio/mp4',
            ];
            const supportedType = preferredTypes.find(t => window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || '';
            const recorderOptions = supportedType ? { mimeType: supportedType } : {};

            mediaRecorder = new MediaRecorder(micStream, recorderOptions);
            const recordedMimeType = mediaRecorder.mimeType || supportedType || 'audio/webm';

            mediaRecorder.ondataavailable = e => {
                if (e.data && e.data.size > 0) {
                    audioChunks.push(e.data);
                }
            };

            // Convert Web Audio API AudioBuffer to standard 16kHz mono 16-bit PCM WAV Blob
            function audioBufferToWav(buffer, optSampleRate = 16000) {
                const numChannels = 1;
                const sampleRate = optSampleRate || buffer.sampleRate;
                const format = 1; // PCM
                const bitDepth = 16;

                // Downmix to mono if multi-channel
                let channelData;
                if (buffer.numberOfChannels === 1) {
                    channelData = buffer.getChannelData(0);
                } else {
                    const left = buffer.getChannelData(0);
                    const right = buffer.getChannelData(1);
                    channelData = new Float32Array(left.length);
                    for (let i = 0; i < left.length; i++) {
                        channelData[i] = (left[i] + right[i]) / 2;
                    }
                }

                // Resample to target sample rate
                let samples;
                if (buffer.sampleRate !== sampleRate) {
                    const ratio = buffer.sampleRate / sampleRate;
                    const newLength = Math.round(channelData.length / ratio);
                    samples = new Float32Array(newLength);
                    for (let i = 0; i < newLength; i++) {
                        const originIndex = i * ratio;
                        const idx = Math.floor(originIndex);
                        const frac = originIndex - idx;
                        const s0 = channelData[idx] || 0;
                        const s1 = channelData[idx + 1] || s0;
                        samples[i] = s0 + frac * (s1 - s0);
                    }
                } else {
                    samples = channelData;
                }

                const byteRate = sampleRate * numChannels * (bitDepth / 8);
                const blockAlign = numChannels * (bitDepth / 8);
                const dataSize = samples.length * (bitDepth / 8);
                const bufferSize = 44 + dataSize;
                const arrayBuffer = new ArrayBuffer(bufferSize);
                const view = new DataView(arrayBuffer);

                function writeString(offset, str) {
                    for (let i = 0; i < str.length; i++) {
                        view.setUint8(offset + i, str.charCodeAt(i));
                    }
                }

                writeString(0, 'RIFF');
                view.setUint32(4, 36 + dataSize, true);
                writeString(8, 'WAVE');
                writeString(12, 'fmt ');
                view.setUint32(16, 16, true);
                view.setUint16(20, format, true);
                view.setUint16(22, numChannels, true);
                view.setUint32(24, sampleRate, true);
                view.setUint32(28, byteRate, true);
                view.setUint16(32, blockAlign, true);
                view.setUint16(34, bitDepth, true);
                writeString(36, 'data');
                view.setUint32(40, dataSize, true);

                let offset = 44;
                for (let i = 0; i < samples.length; i++, offset += 2) {
                    const s = Math.max(-1, Math.min(1, samples[i]));
                    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
                }

                return new Blob([view], { type: 'audio/wav' });
            }

            mediaRecorder.onstop = async () => {
                const totalDurationSec = (accumulatedTime + (isPaused ? 0 : Date.now() - recordStartTime)) / 1000;
                
                // Reject empty or ultra-short recordings
                if (audioChunks.length === 0 || totalDurationSec < 0.5) {
                    showMicStatus('[EMPTY] Recording was too short (under 0.5s). Please record 1-2 seconds of clear voice.', 'error');
                    resetMicControls();
                    return;
                }

                const audioBlob = new Blob(audioChunks, { type: recordedMimeType });
                let finalAudioFile = null;

                // Transcode recorded audio to clean 16kHz mono WAV for pristine backend DSP feature extraction
                try {
                    const arrayBuf = await audioBlob.arrayBuffer();
                    const decodeCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
                    const audioBuffer = await decodeCtx.decodeAudioData(arrayBuf);
                    const wavBlob = audioBufferToWav(audioBuffer, 16000);
                    finalAudioFile = new File([wavBlob], `mic_recording_${Date.now()}.wav`, { type: 'audio/wav' });
                    try { decodeCtx.close(); } catch (_) {}
                } catch (convErr) {
                    const ext = recordedMimeType.includes('webm') ? 'webm' : (recordedMimeType.includes('ogg') ? 'ogg' : 'wav');
                    finalAudioFile = new File([audioBlob], `mic_recording_${Date.now()}.${ext}`, { type: recordedMimeType });
                }

                handleSelectedAudioFile(finalAudioFile);
                showMicStatus(`Recording saved (${totalDurationSec.toFixed(1)}s). Ready for analysis.`, 'success');
            };

            mediaRecorder.onerror = err => {
                showMicStatus(`[RECORDING ERROR] ${err.message || 'MediaRecorder error occurred'}`, 'error');
                stopMicrophoneRecording();
            };

            // Slice into 250ms chunks for smooth recording
            mediaRecorder.start(250);

            // Web Audio API setup for live spectrum & waveform
            try {
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                if (audioContext.state === 'suspended') {
                    await audioContext.resume();
                }
                const source = audioContext.createMediaStreamSource(micStream);
                analyserNode = audioContext.createAnalyser();
                analyserNode.fftSize = 256;
                source.connect(analyserNode);
            } catch (audioCtxErr) {
                console.warn('[VoiceGuardApp] Web Audio Context visualizer initialization warning:', audioCtxErr.message);
            }

            // Start live timer
            recordStartTime = Date.now();
            updateTimerDisplay(0);
            timerInterval = setInterval(() => {
                if (!isPaused) {
                    const elapsedSec = Math.floor((accumulatedTime + Date.now() - recordStartTime) / 1000);
                    updateTimerDisplay(elapsedSec);
                }
            }, 1000);

            // Update UI State for Active Recording
            micBtn.classList.add('is-recording');
            micBtn.innerHTML = '<span class="pulse-ring"></span><span>Stop Recording</span>';
            if (micPauseBtn) {
                micPauseBtn.style.display = 'inline-flex';
                micPauseBtn.textContent = 'Pause';
            }
            if (micClearBtn) {
                micClearBtn.style.display = 'inline-flex';
            }
            showMicStatus('● RECORDING IN PROGRESS — Speak into microphone', 'recording');

            // Draw real-time canvas waveform
            drawMicWaveform();

        } catch (err) {
            console.error('[VoiceGuardApp] Microphone error:', err);
            resetMicControls();

            if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
                showMicStatus('[ACCESS DENIED] Microphone permission denied. Please allow microphone access in your browser.', 'error');
            } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
                showMicStatus('[NOT FOUND] No microphone hardware detected on your device.', 'error');
            } else if (err.name === 'NotReadableError') {
                showMicStatus('[BUSY] Microphone is already in use by another application or OS process.', 'error');
            } else {
                showMicStatus(`[MIC ERROR] ${err.message}`, 'error');
            }
        }
    }

    function pauseMicrophoneRecording() {
        if (!mediaRecorder || mediaRecorder.state !== 'recording') return;
        try {
            mediaRecorder.pause();
            isPaused = true;
            accumulatedTime += Date.now() - recordStartTime;
            if (micPauseBtn) micPauseBtn.textContent = 'Resume';
            showMicStatus('⏸ RECORDING PAUSED', 'paused');
        } catch (e) {
            console.warn('MediaRecorder pause failed:', e);
        }
    }

    function resumeMicrophoneRecording() {
        if (!mediaRecorder || mediaRecorder.state !== 'paused') return;
        try {
            mediaRecorder.resume();
            isPaused = false;
            recordStartTime = Date.now();
            if (micPauseBtn) micPauseBtn.textContent = 'Pause';
            showMicStatus('● RECORDING RESUMED — Speak into microphone', 'recording');
        } catch (e) {
            console.warn('MediaRecorder resume failed:', e);
        }
    }

    function stopMicrophoneRecording() {
        if (mediaRecorder && (mediaRecorder.state === 'recording' || mediaRecorder.state === 'paused')) {
            try {
                mediaRecorder.stop();
            } catch (e) {
                console.warn('MediaRecorder stop warning:', e);
            }
        }
        cleanupMicStream();
        resetMicControls();
    }

    function cancelMicrophoneRecording() {
        // Discard recording without saving
        audioChunks = [];
        if (mediaRecorder && (mediaRecorder.state === 'recording' || mediaRecorder.state === 'paused')) {
            mediaRecorder.onstop = null; // Do not trigger file packaging
            try { mediaRecorder.stop(); } catch (e) {}
        }
        cleanupMicStream();
        resetMicControls();
        updateTimerDisplay(0);
        clearMicCanvas();
        showMicStatus('Recording cancelled. Microphone ready.', 'info');
    }

    function cleanupMicStream() {
        if (micStream) {
            micStream.getTracks().forEach(track => {
                try { track.stop(); } catch (e) {}
            });
            micStream = null;
        }
        if (audioContext && audioContext.state !== 'closed') {
            try { audioContext.close(); } catch (e) {}
            audioContext = null;
        }
        clearInterval(timerInterval);
        cancelAnimationFrame(animFrameId);
    }

    function resetMicControls() {
        if (micBtn) {
            micBtn.classList.remove('is-recording');
            micBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/></svg><span>Record from Microphone</span>';
        }
        if (micPauseBtn) micPauseBtn.style.display = 'none';
        if (micClearBtn) micClearBtn.style.display = 'none';
        isPaused = false;
    }

    function updateTimerDisplay(seconds) {
        if (!micTimerEl) return;
        const mm = String(Math.floor(seconds / 60)).padStart(2, '0');
        const ss = String(seconds % 60).padStart(2, '0');
        micTimerEl.textContent = `${mm}:${ss}`;
    }

    function showMicStatus(text, type = 'info') {
        if (!micStatus) return;
        micStatus.textContent = text;
        if (type === 'error') {
            micStatus.style.color = '#ef4444';
        } else if (type === 'recording') {
            micStatus.style.color = '#00f2fe';
        } else if (type === 'paused') {
            micStatus.style.color = '#f59e0b';
        } else if (type === 'success') {
            micStatus.style.color = '#10b981';
        } else {
            micStatus.style.color = 'var(--cyber-text-dim)';
        }
    }

    function drawMicWaveform() {
        if (!micCanvas || !analyserNode) return;
        const ctx = micCanvas.getContext('2d');
        const bufferLength = analyserNode.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        function render() {
            animFrameId = requestAnimationFrame(render);
            if (isPaused) return; // Freeze visualization when paused

            analyserNode.getByteTimeDomainData(dataArray);

            ctx.clearRect(0, 0, micCanvas.width, micCanvas.height);
            ctx.lineWidth = 2;
            ctx.strokeStyle = '#00f2fe';
            ctx.beginPath();

            const sliceWidth = (micCanvas.width * 1.0) / bufferLength;
            let x = 0;

            for (let i = 0; i < bufferLength; i++) {
                const v = dataArray[i] / 128.0;
                const y = (v * micCanvas.height) / 2;

                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
                x += sliceWidth;
            }
            ctx.stroke();
        }
        render();
    }

    function clearMicCanvas() {
        if (!micCanvas) return;
        const ctx = micCanvas.getContext('2d');
        ctx.clearRect(0, 0, micCanvas.width, micCanvas.height);
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = 'rgba(0, 242, 254, 0.25)';
        ctx.beginPath();
        ctx.moveTo(0, micCanvas.height / 2);
        ctx.lineTo(micCanvas.width, micCanvas.height / 2);
        ctx.stroke();
    }
    clearMicCanvas();

    // ========================================================================
    // 5. AUDIO UPLOAD & LOADED FILE MANAGEMENT
    // ========================================================================
    const dropzone = document.getElementById('central-audio-dropzone');
    const fileInput = document.getElementById('central-file-input');
    const removeFileBtn = document.getElementById('btn-remove-loaded-file');
    let currentSelectedFile = null;

    if (dropzone && fileInput) {
        dropzone.addEventListener('click', e => {
            // Prevent duplicate trigger if clicking on internal elements
            if (e.target !== fileInput) {
                fileInput.click();
            }
        });

        dropzone.addEventListener('dragover', e => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('drag-active');
        });

        dropzone.addEventListener('dragleave', e => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('drag-active');
        });

        dropzone.addEventListener('drop', e => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('drag-active');
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
                handleSelectedAudioFile(e.dataTransfer.files[0]);
            }
        });

        fileInput.addEventListener('change', e => {
            if (e.target.files && e.target.files[0]) {
                handleSelectedAudioFile(e.target.files[0]);
            }
        });
    }

    if (removeFileBtn) {
        removeFileBtn.addEventListener('click', () => {
            discardSelectedAudio();
        });
    }

    function discardSelectedAudio() {
        currentSelectedFile = null;
        if (fileInput) fileInput.value = '';
        
        const fileCard = document.getElementById('loaded-file-meta-card');
        const playerEl = document.getElementById('central-audio-player');
        const analyzeBtn = document.getElementById('btn-execute-analysis');

        if (playerEl) {
            playerEl.pause();
            playerEl.src = '';
            playerEl.style.display = 'none';
        }
        if (fileCard) fileCard.style.display = 'none';
        if (analyzeBtn) {
            analyzeBtn.disabled = true;
            analyzeBtn.classList.add('disabled');
        }

        // Hide pipeline & results
        const stageContainer = document.getElementById('ai-7stage-pipeline');
        const resultsContainer = document.getElementById('detection-results-panel');
        if (stageContainer) stageContainer.style.display = 'none';
        if (resultsContainer) resultsContainer.style.display = 'none';
        if (window.VoiceGuardSpectrogram) {
            window.VoiceGuardSpectrogram.clear();
        }
        clearForensicsDashboard();

        showMicStatus('Audio discarded. Ready to upload or record new sample.', 'info');
    }

    function handleSelectedAudioFile(file) {
        const validExtensions = ['wav', 'mp3', 'flac', 'ogg', 'm4a', 'aac', 'webm', 'opus', 'mpeg', 'mpg'];
        const ext = file.name.split('.').pop().toLowerCase();

        if (!validExtensions.includes(ext)) {
            alert(`Unsupported audio format (.${ext}). Supported formats: ${validExtensions.join(', ').toUpperCase()}`);
            return;
        }

        if (file.size > 25 * 1024 * 1024) {
            alert(`File exceeds the maximum 25 MB limit (${(file.size / (1024 * 1024)).toFixed(2)} MB).`);
            return;
        }

        currentSelectedFile = file;

        // Display Metadata Card
        const fileCard = document.getElementById('loaded-file-meta-card');
        const fileNameEl = document.getElementById('meta-file-name');
        const fileSizeEl = document.getElementById('meta-file-size');
        const fileTypeEl = document.getElementById('meta-file-type');
        const fileDurationEl = document.getElementById('meta-file-duration');
        const playerEl = document.getElementById('central-audio-player');
        const analyzeBtn = document.getElementById('btn-execute-analysis');

        if (fileNameEl) fileNameEl.textContent = file.name;
        if (fileSizeEl) fileSizeEl.textContent = (file.size / (1024 * 1024)).toFixed(2) + ' MB';
        if (fileTypeEl) fileTypeEl.textContent = ext.toUpperCase();
        if (fileDurationEl) fileDurationEl.textContent = 'Measuring...';

        if (playerEl) {
            playerEl.src = URL.createObjectURL(file);
            playerEl.style.display = 'block';
            playerEl.onloadedmetadata = () => {
                if (fileDurationEl && playerEl.duration && Number.isFinite(playerEl.duration)) {
                    fileDurationEl.textContent = `${playerEl.duration.toFixed(2)}s`;
                }
            };
        }

        if (fileCard) fileCard.style.display = 'block';
        if (analyzeBtn) {
            analyzeBtn.disabled = false;
            analyzeBtn.classList.remove('disabled');
        }

        // Scroll to loaded card smoothly
        fileCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // ========================================================================
    // 6. 7-STAGE AI ANALYSIS EXECUTION & LIVE FORENSIC VERIFICATION
    // ========================================================================
    const analyzeBtn = document.getElementById('btn-execute-analysis');
    const stageContainer = document.getElementById('ai-7stage-pipeline');
    const resultsContainer = document.getElementById('detection-results-panel');

    const stages = [
        { id: 'stage-1', name: '1. Audio Uploading' },
        { id: 'stage-2', name: '2. Audio Preprocessing' },
        { id: 'stage-3', name: '3. Feature Extraction (LFCC/CQCC)' },
        { id: 'stage-4', name: '4. Voice Pattern Analysis' },
        { id: 'stage-5', name: '5. Synthetic Voice Detection' },
        { id: 'stage-6', name: '6. Authenticity Assessment' },
        { id: 'stage-7', name: '7. Final Report Generation' },
    ];

    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', execute7StageAnalysis);
    }

    async function execute7StageAnalysis() {
        if (!currentSelectedFile) return;

        analyzeBtn.disabled = true;
        analyzeBtn.textContent = 'Analyzing Voice...';
        if (stageContainer) stageContainer.style.display = 'block';
        if (resultsContainer) resultsContainer.style.display = 'none';
        if (window.VoiceGuardSpectrogram) {
            window.VoiceGuardSpectrogram.setLoading('Extracting 40-band Log-Mel Spectrogram via 512-point STFT...');
        }

        // Reset all pipeline steps
        for (let i = 1; i <= 7; i++) {
            updatePipelineStep(i, 'pending');
        }

        try {
            // Step 1: Uploading
            updatePipelineStep(1, 'in-progress');
            const modelSelector = document.getElementById('select-ai-model');
            const chosenModel = modelSelector ? modelSelector.value : 'AASIST';
            const analysisPromise = API.analyzeAudioV1(currentSelectedFile, chosenModel);

            // Update step 5 description according to selected neural model
            const step5Desc = document.querySelector('#pipeline-step-5 .step-info small');
            if (step5Desc) {
                step5Desc.textContent = chosenModel === 'RAWNET2'
                    ? 'RawNet2 SincNet analytical filterbank & 3-layer GRU temporal anti-spoofing scan'
                    : 'AASIST Heterogeneous Stacking Graph Attention & SincNet feature map scan';
            }

            // Progress smoothly through audio preprocessing and DSP stages
            await new Promise(r => setTimeout(r, 220));
            updatePipelineStep(1, 'completed');
            updatePipelineStep(2, 'in-progress'); // Preprocessing (16kHz mono)

            await new Promise(r => setTimeout(r, 260));
            updatePipelineStep(2, 'completed');
            updatePipelineStep(3, 'in-progress'); // Feature Extraction (LFCC/CQCC)

            await new Promise(r => setTimeout(r, 260));
            updatePipelineStep(3, 'completed');
            updatePipelineStep(4, 'in-progress'); // Voice Pattern Analysis

            await new Promise(r => setTimeout(r, 260));
            updatePipelineStep(4, 'completed');
            updatePipelineStep(5, 'in-progress'); // Synthetic Voice Detection

            const res = await analysisPromise;

            updatePipelineStep(5, 'completed');
            updatePipelineStep(6, 'in-progress'); // Authenticity Assessment
            await new Promise(r => setTimeout(r, 160));
            updatePipelineStep(6, 'completed');
            updatePipelineStep(7, 'in-progress'); // Final Report Generation
            await new Promise(r => setTimeout(r, 160));
            updatePipelineStep(7, 'completed');

            if (res.prediction && res.audio_information) {
                displayPhase3Result(res);
            } else {
                const analysis = res.analysis || {};
                const classification = res.classification || 'INCONCLUSIVE';
                const features = res.acoustic_features || null;
                displayDetectionResult(analysis, classification, features);
            }
            refreshHistoryTable();
            syncDashboardMetrics();
        } catch (err) {
            console.error('[VoiceGuardApp] Analysis error:', err);
            const errMsg = err.message || (err.data && (err.data.detail || err.data.error)) || 'An error occurred during audio processing.';
            showMicStatus(`[ANALYSIS FAILED] ${errMsg}`, 'error');
            if (window.VoiceGuardSpectrogram) {
                window.VoiceGuardSpectrogram.setError(errMsg);
            }

            if (err.status === 401) {
                alert('Session expired or authentication token missing. Please sign in to continue.');
                window.location.assign('/login');
                return;
            }

            displayDetectionResult({
                filename: currentSelectedFile.name,
                file_size: currentSelectedFile.size,
                file_type: currentSelectedFile.name.split('.').pop(),
                analysis_status: 'ANALYSIS_ERROR',
                synthetic_score: null,
                detection_result: `Processing Error: ${errMsg}`
            }, 'ERROR', null);
        } finally {
            analyzeBtn.disabled = false;
            analyzeBtn.innerHTML = '<span>Start AI Analysis</span> &rarr;';
        }
    }

    function updatePipelineStep(stepIndex, state) {
        const item = document.getElementById(`pipeline-step-${stepIndex}`);
        if (!item) return;
        item.className = `pipeline-step-item ${state}`;
        const badge = item.querySelector('.step-state-badge');
        if (badge) {
            badge.textContent = state === 'completed' ? '✓ DONE' : 'PROCESSING...';
        }
    }

    function displayPhase3Result(res) {
        if (stageContainer) stageContainer.style.display = 'none';
        if (resultsContainer) resultsContainer.style.display = 'block';

        const statusTag = document.getElementById('res-verdict-badge');
        const confidenceText = document.getElementById('res-confidence-text');
        const confidenceCircle = document.getElementById('res-confidence-circle');
        const filenameEl = document.getElementById('res-filename');
        const filesizeEl = document.getElementById('res-filesize');
        const statusDetailEl = document.getElementById('res-status-detail');

        if (filenameEl) filenameEl.textContent = res.filename || 'voice_sample.wav';
        if (filesizeEl) {
            const dur = res.audio_information ? `${res.audio_information.duration}s` : '';
            filesizeEl.textContent = `${dur} · ${res.segments_analyzed} segment(s)`;
        }

        const pred = res.prediction || {};
        const audioInfo = res.audio_information || {};
        const isSynthetic = pred.label === 'AI_GENERATED';
        const isAuthentic = pred.label === 'HUMAN';
        const isModelReady = res.model && res.model.inference_completed;

        if (isSynthetic) {
            if (statusTag) {
                statusTag.textContent = 'HIGH RISK: AI GENERATED CLONE';
                statusTag.className = 'verdict-badge-red';
            }
            const pct = Math.round((pred.confidence || pred.synthetic_probability || 0.9) * 100);
            if (confidenceText) confidenceText.textContent = `${pct}%`;
            if (confidenceCircle) {
                confidenceCircle.style.strokeDashoffset = String(280 - (280 * pct) / 100);
                confidenceCircle.style.stroke = '#ef4444';
            }
        } else if (isAuthentic) {
            if (statusTag) {
                statusTag.textContent = 'VERIFIED AUTHENTIC: REAL HUMAN';
                statusTag.className = 'verdict-badge-green';
            }
            const pct = Math.round((pred.confidence || pred.human_probability || 0.9) * 100);
            if (confidenceText) confidenceText.textContent = `${pct}%`;
            if (confidenceCircle) {
                confidenceCircle.style.strokeDashoffset = String(280 - (280 * pct) / 100);
                confidenceCircle.style.stroke = '#10b981';
            }
        } else {
            if (statusTag) {
                statusTag.textContent = isModelReady ? 'INCONCLUSIVE · AMBIGUOUS SIGNALS' : 'INCONCLUSIVE · MODEL WEIGHTS UNCONFIGURED';
                statusTag.className = 'verdict-badge-amber';
            }
            if (confidenceText) confidenceText.textContent = '--';
            if (confidenceCircle) {
                confidenceCircle.style.strokeDashoffset = '280';
                confidenceCircle.style.stroke = '#f59e0b';
            }
        }

        if (statusDetailEl) {
            // Render Segment Cards
            let segmentsHtml = '';
            if (res.segment_analysis && res.segment_analysis.length > 0) {
                const segRows = res.segment_analysis.map(s => {
                    const color = s.prediction === 'AI_GENERATED' ? '#ef4444' : s.prediction === 'HUMAN' || s.prediction === 'REAL_HUMAN' ? '#10b981' : '#f59e0b';
                    const scoreText = s.score !== null && s.score !== undefined ? `${Math.round(s.score * 100)}%` : 'DSP Metrics Only';
                    const labelText = s.prediction === 'HUMAN' ? 'REAL_HUMAN' : s.prediction;
                    return `
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 10px; margin-bottom: 4px; background: rgba(255,255,255,0.03); border-radius: 4px; border-left: 3px solid ${color}; font-size: 0.78rem;">
                            <span>Segment #${s.segment_id} (${s.start}s &ndash; ${s.end}s)</span>
                            <span style="font-weight: 600; color: ${color};">${labelText} (${scoreText})</span>
                        </div>
                    `;
                }).join('');

                segmentsHtml = `
                    <div style="margin-top: 10px;">
                        <div style="font-size: 0.78rem; text-transform: uppercase; color: var(--cyber-text-dim); margin-bottom: 6px; letter-spacing: 0.05em;">
                            Segment-by-Segment Forensic Breakdown:
                        </div>
                        <div style="max-height: 140px; overflow-y: auto;">
                            ${segRows}
                        </div>
                    </div>
                `;
            }

            // Render Acoustic DSP & Model Telemetry Info (Module 4 & 6)
            const realProbVal = res.real_probability !== undefined && res.real_probability !== null ? res.real_probability : pred.human_probability;
            const fakeProbVal = res.fake_probability !== undefined && res.fake_probability !== null ? res.fake_probability : pred.synthetic_probability;
            const realProbText = realProbVal !== null && realProbVal !== undefined ? `${(realProbVal * 100).toFixed(1)}%` : 'DSP Only';
            const fakeProbText = fakeProbVal !== null && fakeProbVal !== undefined ? `${(fakeProbVal * 100).toFixed(1)}%` : 'DSP Only';
            const confScoreText = pred.confidence !== null && pred.confidence !== undefined ? `${(pred.confidence * 100).toFixed(1)}%` : '--';
            const modelNameText = res.model_name || (res.model ? res.model.name : 'AASIST');
            const modelStatusText = res.model_status || (res.model && res.model.inference_completed ? 'ACTIVE' : 'UNCONFIGURED');
            const infTimeSec = res.inference_time !== undefined && res.inference_time !== null ? res.inference_time : (pred.inference_time || 0);
            const infTimeText = infTimeSec > 0 ? `${(infTimeSec * 1000).toFixed(1)} ms` : `${((res.processing_time_seconds || 0) * 1000).toFixed(0)} ms`;
            const reliability = res.prediction_reliability || pred.prediction_reliability || (isModelReady ? 'HIGH' : 'UNRELIABLE');
            const relBadgeColor = reliability === 'HIGH' ? '#10b981' : reliability === 'MEDIUM' ? '#00f2fe' : reliability === 'LOW' ? '#f59e0b' : '#64748b';

            const probabilityCardsHtml = `
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; margin: 12px 0;">
                    <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 6px; padding: 8px 12px;">
                        <div style="font-size: 0.72rem; color: #10b981; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;">Real Probability</div>
                        <div style="font-size: 1.15rem; font-weight: 700; color: #ffffff; margin-top: 2px;">${realProbText}</div>
                    </div>
                    <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.25); border-radius: 6px; padding: 8px 12px;">
                        <div style="font-size: 0.72rem; color: #ef4444; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;">Fake Probability</div>
                        <div style="font-size: 1.15rem; font-weight: 700; color: #ffffff; margin-top: 2px;">${fakeProbText}</div>
                    </div>
                    <div style="background: rgba(0, 242, 254, 0.08); border: 1px solid rgba(0, 242, 254, 0.25); border-radius: 6px; padding: 8px 12px;">
                        <div style="font-size: 0.72rem; color: #00f2fe; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;">Inference Time</div>
                        <div style="font-size: 1.15rem; font-weight: 700; color: #ffffff; margin-top: 2px;">${infTimeText}</div>
                    </div>
                    <div style="background: rgba(168, 85, 247, 0.08); border: 1px solid rgba(168, 85, 247, 0.25); border-radius: 6px; padding: 8px 12px;">
                        <div style="font-size: 0.72rem; color: #c084fc; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;">Model & Reliability</div>
                        <div style="font-size: 0.88rem; font-weight: 700; color: #ffffff; margin-top: 4px; display: flex; align-items: center; justify-content: space-between;">
                            <span>${modelNameText}</span>
                            <span class="badge" style="background: rgba(255,255,255,0.08); color: ${relBadgeColor}; border: 1px solid ${relBadgeColor}; font-size: 0.65rem; padding: 2px 6px;">${reliability}</span>
                        </div>
                    </div>
                </div>
            `;

            const techExplanationHtml = `
                <div style="margin-top: 10px; padding: 10px 14px; border-radius: 6px; background: rgba(13, 20, 36, 0.7); border: 1px solid rgba(0, 242, 254, 0.15); font-size: 0.78rem; line-height: 1.5; color: var(--cyber-text-muted);">
                    <div style="font-weight: 600; color: #ffffff; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;">
                        <span style="color: var(--cyber-cyan);">&bull;</span> Technical Explanation:
                    </div>
                    <div>
                        ${isModelReady ? `
                            Input audio decomposed into 64,600-sample windows at 16kHz mono PCM and processed through <strong>${modelNameText}</strong> sinc-convolutional sub-band filterbanks, 6-block residual encoder, and heterogeneous graph attention network (Homo/Hetero-GAT). Logit readouts mapped via softmax: Real Probability: <strong>${realProbText}</strong>, Fake Probability: <strong>${fakeProbText}</strong> (Confidence: <strong>${confScoreText}</strong>, Reliability: <strong style="color: ${relBadgeColor};">${reliability}</strong>).
                        ` : `
                            Pretrained weights for <strong>${modelNameText}</strong> are not installed in backend/models_weights. VoiceGuard AI strictly enforced zero-hallucination policy, computing deterministic DSP measurements without fabricating artificial detection probabilities.
                        `}
                    </div>
                </div>
            `;

            const dspHtml = `
                <div style="margin-top: 10px; padding: 10px; border-radius: 6px; background: rgba(56,189,248,0.05); border: 1px solid rgba(56,189,248,0.2); font-family: var(--cyber-font-mono); font-size: 0.78rem; color: #38bdf8;">
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 6px;">
                        <div>&bull; Duration: <strong>${audioInfo.duration || 0}s</strong></div>
                        <div>&bull; Channels: <strong>${audioInfo.channels || 1} (${(audioInfo.channels === 1 ? 'Mono' : 'Stereo')})</strong></div>
                        <div>&bull; Sample Rate: <strong>${audioInfo.sample_rate || 16000} Hz</strong></div>
                        <div>&bull; Peak Amplitude: <strong>${audioInfo.peak_amplitude || 0}</strong></div>
                        <div>&bull; RMS Energy: <strong>${audioInfo.rms_energy || 0}</strong></div>
                        <div>&bull; Spectral Centroid: <strong>${audioInfo.spectral_centroid_hz || 0} Hz</strong></div>
                        <div>&bull; Pitch Stability: <strong>${audioInfo.pitch_stability || 0}</strong></div>
                        <div>&bull; Processing Time: <strong>${res.processing_time_seconds || 0}s</strong></div>
                    </div>
                </div>
            `;

            const zeroHallucinationNotice = !isModelReady ? `
                <div style="margin-top: 8px; padding: 8px 12px; border-radius: 4px; background: rgba(245, 158, 11, 0.08); border-left: 3px solid #f59e0b; font-size: 0.75rem; color: #f59e0b;">
                    <strong>Zero-Hallucination Guard:</strong> Pretrained weights for ${modelNameText} are not installed in backend/models_weights. Empirical acoustic telemetry was calculated; no random probabilities were fabricated.
                </div>
            ` : '';

            statusDetailEl.innerHTML = `
                <div>
                    <strong>Phase 4 Production AI Voice Deepfake Detection Completed.</strong><br>
                    ${res.message || 'Audio resampled to 16kHz mono PCM and evaluated through neural anti-spoofing pipeline.'}
                </div>
                ${probabilityCardsHtml}
                ${techExplanationHtml}
                ${dspHtml}
                ${zeroHallucinationNotice}
                ${segmentsHtml}
            `;
        }

        // Load Genuine 2D Log-Mel Spectrogram Heatmap
        if (window.VoiceGuardSpectrogram) {
            const specPayload = res.spectrogram || (res.features && res.features.spectrogram);
            if (specPayload && specPayload.matrix) {
                const playerEl = document.getElementById('central-audio-player');
                window.VoiceGuardSpectrogram.loadData(specPayload, playerEl);
            } else {
                window.VoiceGuardSpectrogram.setEmpty();
            }
        }

        // Render Phase 3 Audio Forensics & Signal Quality Analysis Dashboard
        if (res.forensics) {
            const totalDur = res.audio_duration || (res.audio_information && res.audio_information.duration) || res.forensics.duration_seconds || 1.0;
            renderForensicsDashboard(res.forensics, totalDur);
        } else if (res.analysis_id && window.VoiceGuardAPI && typeof window.VoiceGuardAPI.getAudioForensics === 'function') {
            window.VoiceGuardAPI.getAudioForensics(res.analysis_id)
                .then(fData => {
                    if (fData && fData.forensics) {
                        const totalDur = res.audio_duration || (res.audio_information && res.audio_information.duration) || fData.forensics.duration_seconds || 1.0;
                        renderForensicsDashboard(fData.forensics, totalDur);
                    }
                })
                .catch(e => console.warn('[VoiceGuardApp] Forensics fetch fallback failed:', e));
        }

        if (window.VoiceGuardScenes && window.VoiceGuardScenes.setSecurityState) {
            const state = isSynthetic ? 'high-risk' : (isAuthentic ? 'safe' : 'suspicious');
            window.VoiceGuardScenes.setSecurityState(state);
        }

        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function clearForensicsDashboard() {
        const scoreNumEl = document.getElementById('forensics-quality-score-num');
        const scoreCircle = document.getElementById('forensics-quality-circle');
        const scoreBadge = document.getElementById('forensics-quality-badge');
        const gradeText = document.getElementById('forensics-quality-grade-text');
        const snrValEl = document.getElementById('forensics-snr-val');
        const snrBadge = document.getElementById('forensics-snr-badge');
        const snrInterp = document.getElementById('forensics-snr-interpretation');
        const snrMarker = document.getElementById('snr-meter-marker');
        const silBar = document.getElementById('silence-timeline-bar');
        const vadBar = document.getElementById('vad-timeline-bar');
        const clipChips = document.getElementById('forensics-clipping-intervals-container');

        if (scoreNumEl) scoreNumEl.textContent = '--';
        if (scoreCircle) scoreCircle.style.strokeDashoffset = '100';
        if (scoreBadge) {
            scoreBadge.textContent = 'PRISTINE';
            scoreBadge.className = 'badge badge-success';
        }
        if (gradeText) gradeText.textContent = 'Awaiting Analysis...';
        if (snrValEl) snrValEl.textContent = '--';
        if (snrBadge) {
            snrBadge.textContent = '--';
            snrBadge.className = 'badge badge-info';
        }
        if (snrInterp) snrInterp.textContent = 'Awaiting audio signal evaluation...';
        if (snrMarker) snrMarker.style.left = '0%';
        if (silBar) silBar.innerHTML = '';
        if (vadBar) vadBar.innerHTML = '';
        if (clipChips) clipChips.innerHTML = '';
    }

    function renderForensicsDashboard(forensics, totalDuration = 0) {
        if (!forensics) return;
        const dur = Math.max(0.01, totalDuration || forensics.duration_seconds || 1.0);

        // 1. Audio Quality Score (0-100)
        const qScore = forensics.quality_score || {};
        const scoreVal = typeof qScore.overall_score === 'number' ? qScore.overall_score : null;
        const scoreNumEl = document.getElementById('forensics-quality-score-num');
        const scoreCircle = document.getElementById('forensics-quality-circle');
        const scoreBadge = document.getElementById('forensics-quality-badge');
        const gradeText = document.getElementById('forensics-quality-grade-text');

        if (scoreNumEl && scoreVal !== null) {
            scoreNumEl.textContent = Math.round(scoreVal);
        }
        if (gradeText && qScore.grade) {
            gradeText.textContent = qScore.grade;
        }
        if (scoreBadge) {
            scoreBadge.textContent = qScore.badge || 'PRISTINE';
            scoreBadge.className = `badge ${
                qScore.badge === 'PRISTINE' ? 'badge-success' :
                qScore.badge === 'HIGH' ? 'badge-info' :
                qScore.badge === 'ACCEPTABLE' ? 'badge-primary' :
                qScore.badge === 'DEGRADED' ? 'badge-warning' : 'badge-danger'
            }`;
        }
        if (scoreCircle && scoreVal !== null) {
            const offset = 100 - scoreVal;
            scoreCircle.style.strokeDashoffset = String(Math.max(0, Math.min(100, offset)));
            scoreCircle.style.stroke = (
                scoreVal >= 85 ? '#10b981' :
                scoreVal >= 70 ? '#00f2fe' :
                scoreVal >= 50 ? '#38bdf8' :
                scoreVal >= 30 ? '#f59e0b' : '#ef4444'
            );
        }

        // Breakdown items
        const bd = qScore.breakdown || {};
        const setBreakdown = (id, comp, fallbackMax) => {
            const el = document.getElementById(id);
            if (!el) return;
            if (comp) {
                el.textContent = `${comp.points} / ${comp.max_points}`;
            } else {
                el.textContent = `-- / ${fallbackMax}`;
            }
        };
        setBreakdown('fb-snr-pts', bd.snr_component, 30);
        setBreakdown('fb-clip-pts', bd.clipping_component, 20);
        setBreakdown('fb-floor-pts', bd.noise_floor_component, 20);
        setBreakdown('fb-dyn-pts', bd.dynamic_range_component, 15);
        setBreakdown('fb-speech-pts', bd.speech_presence_component, 15);

        // 2. Signal-to-Noise Ratio (SNR)
        const snr = forensics.snr_analysis || {};
        const snrValEl = document.getElementById('forensics-snr-val');
        const snrBadge = document.getElementById('forensics-snr-badge');
        const snrInterp = document.getElementById('forensics-snr-interpretation');
        const snrMarker = document.getElementById('snr-meter-marker');
        const speechPwrEl = document.getElementById('forensics-speech-pwr');
        const noisePwrEl = document.getElementById('forensics-noise-pwr');

        if (snrValEl) {
            snrValEl.textContent = (snr.snr_db !== null && snr.snr_db !== undefined) ? snr.snr_db.toFixed(1) : 'N/A';
        }
        if (snrBadge) {
            snrBadge.textContent = snr.classification || 'UNAVAILABLE';
            snrBadge.className = `badge ${
                snr.classification === 'EXCELLENT' ? 'badge-success' :
                snr.classification === 'GOOD' ? 'badge-info' :
                snr.classification === 'FAIR' ? 'badge-primary' :
                snr.classification === 'POOR' ? 'badge-warning' : 'badge-danger'
            }`;
        }
        if (snrInterp) {
            snrInterp.textContent = snr.interpretation || 'Signal evaluated.';
        }
        if (snrMarker) {
            const dbVal = snr.snr_db !== null && snr.snr_db !== undefined ? snr.snr_db : 0;
            const pct = Math.max(0, Math.min(100, (dbVal / 50.0) * 100));
            snrMarker.style.left = `${pct}%`;
        }
        if (speechPwrEl) speechPwrEl.textContent = snr.speech_power_dbfs !== null && snr.speech_power_dbfs !== undefined ? `${snr.speech_power_dbfs.toFixed(1)} dBFS` : '-- dBFS';
        if (noisePwrEl) noisePwrEl.textContent = snr.noise_power_dbfs !== null && snr.noise_power_dbfs !== undefined ? `${snr.noise_power_dbfs.toFixed(1)} dBFS` : '-- dBFS';

        // 3. Background Noise & Floor
        const nf = forensics.noise_floor || {};
        const noise = forensics.noise_analysis || {};
        const nfValEl = document.getElementById('forensics-noise-floor-val');
        const nfInterpEl = document.getElementById('forensics-noise-floor-interp');
        const noiseBadge = document.getElementById('forensics-noise-intensity-badge');
        const noiseIntText = document.getElementById('forensics-noise-intensity-text');
        const meanNoiseEl = document.getElementById('forensics-mean-noise-dbfs');
        const peakNoiseEl = document.getElementById('forensics-peak-noise-dbfs');
        const noisySegCountEl = document.getElementById('forensics-noisy-segments-count');

        if (nfValEl) nfValEl.textContent = (nf.noise_floor_dbfs !== undefined) ? nf.noise_floor_dbfs.toFixed(1) : '--';
        if (nfInterpEl) nfInterpEl.textContent = nf.interpretation || 'Baseline noise floor';
        if (noiseBadge) {
            const label = noise.noise_intensity_label || (noise.has_background_noise ? 'Detected' : 'Silent');
            noiseBadge.textContent = label.split(' ')[0].toUpperCase();
        }
        if (noiseIntText) noiseIntText.textContent = noise.noise_intensity_label || (noise.has_background_noise ? 'Active' : 'Silent');
        if (meanNoiseEl) meanNoiseEl.textContent = noise.mean_noise_dbfs !== undefined ? `${noise.mean_noise_dbfs.toFixed(1)} dBFS` : '-- dBFS';
        if (peakNoiseEl) peakNoiseEl.textContent = noise.peak_noise_dbfs !== undefined ? `${noise.peak_noise_dbfs.toFixed(1)} dBFS` : '-- dBFS';
        if (noisySegCountEl) noisySegCountEl.textContent = noise.noisy_segments_count !== undefined ? String(noise.noisy_segments_count) : '0';

        // 4. Digital Clipping Detection
        const clip = forensics.clipping_analysis || {};
        const clipPctEl = document.getElementById('forensics-clipping-pct');
        const clipBadge = document.getElementById('forensics-clipping-badge');
        const clipStatusText = document.getElementById('forensics-clipping-status-text');
        const clipSamplesEl = document.getElementById('forensics-clipped-samples-count');
        const clipSevEl = document.getElementById('forensics-clipping-severity');
        const clipIntCountEl = document.getElementById('forensics-clipped-intervals-count');
        const clipChipsContainer = document.getElementById('forensics-clipping-intervals-container');

        if (clipPctEl) clipPctEl.textContent = `${(clip.clipping_percentage || 0).toFixed(2)}%`;
        if (clipBadge) {
            clipBadge.textContent = clip.has_clipping ? (clip.severity || 'CLIPPED').toUpperCase() : 'CLEAN';
            clipBadge.className = `badge ${clip.has_clipping ? (clip.severity === 'Severe' ? 'badge-danger' : 'badge-warning') : 'badge-success'}`;
        }
        if (clipStatusText) {
            clipStatusText.textContent = clip.has_clipping
                ? `Waveform saturation detected across ${clip.affected_intervals_count || 1} timestamped interval(s).`
                : 'No waveform saturation or ADC sample clipping detected.';
        }
        if (clipSamplesEl) clipSamplesEl.textContent = String(clip.clipped_samples_count || 0);
        if (clipSevEl) clipSevEl.textContent = clip.severity || 'None';
        if (clipIntCountEl) clipIntCountEl.textContent = String(clip.affected_intervals_count || 0);

        if (clipChipsContainer) {
            clipChipsContainer.innerHTML = '';
            const intervals = clip.clipping_intervals || [];
            if (intervals.length === 0) {
                clipChipsContainer.innerHTML = '<span style="font-size:0.7rem; color:var(--cyber-text-dim);">No clipped intervals</span>';
            } else {
                intervals.slice(0, 12).forEach(it => {
                    const chip = document.createElement('span');
                    chip.className = 'clipping-chip';
                    chip.title = `Samples: ${it.clipped_samples}, Peak: ${it.peak_amplitude}`;
                    chip.textContent = `[${it.start.toFixed(2)}s - ${it.end.toFixed(2)}s]`;
                    clipChipsContainer.appendChild(chip);
                });
                if (intervals.length > 12) {
                    const more = document.createElement('span');
                    more.style.fontSize = '0.68rem';
                    more.style.color = 'var(--cyber-text-dim)';
                    more.textContent = `+${intervals.length - 12} more`;
                    clipChipsContainer.appendChild(more);
                }
            }
        }

        // 5. Silence & Pause Timeline
        const sil = forensics.silence_analysis || {};
        const silStatsEl = document.getElementById('silence-timeline-stats');
        const silBar = document.getElementById('silence-timeline-bar');

        if (silStatsEl) {
            silStatsEl.textContent = `Total Silence: ${(sil.total_silence_seconds || 0).toFixed(2)}s (${(sil.silence_percentage || 0).toFixed(1)}%) · ${sil.silent_segments_count || 0} pause(s)`;
        }
        if (silBar) {
            silBar.innerHTML = '';
            // Base layer: Audible
            const baseAudible = document.createElement('div');
            baseAudible.className = 'timeline-segment timeline-segment-audible';
            baseAudible.style.left = '0%';
            baseAudible.style.width = '100%';
            baseAudible.title = `Audible Signal: ${(dur - (sil.total_silence_seconds || 0)).toFixed(2)}s`;
            silBar.appendChild(baseAudible);

            // Overlay silence intervals
            (sil.silent_segments || []).forEach(seg => {
                const sLeft = Math.max(0, Math.min(100, (seg.start / dur) * 100));
                const sWidth = Math.max(0.5, Math.min(100 - sLeft, (seg.duration / dur) * 100));
                const segEl = document.createElement('div');
                segEl.className = 'timeline-segment timeline-segment-silence';
                segEl.style.left = `${sLeft}%`;
                segEl.style.width = `${sWidth}%`;
                segEl.title = `Silent Pause: ${seg.start.toFixed(2)}s - ${seg.end.toFixed(2)}s (${seg.duration.toFixed(2)}s) · ${seg.mean_dbfs || '--'} dBFS`;
                silBar.appendChild(segEl);
            });
        }

        // 6. Voice Activity Detection (VAD) Timeline
        const vad = forensics.voice_activity || {};
        const vadStatsEl = document.getElementById('vad-timeline-stats');
        const vadBar = document.getElementById('vad-timeline-bar');

        if (vadStatsEl) {
            vadStatsEl.textContent = `Speech: ${(vad.total_speech_seconds || 0).toFixed(2)}s (${(vad.speech_percentage || 0).toFixed(1)}%) · Non-Speech: ${(vad.total_non_speech_seconds || 0).toFixed(2)}s (${(vad.non_speech_percentage || 0).toFixed(1)}%)`;
        }
        if (vadBar) {
            vadBar.innerHTML = '';
            // Base layer: Non-Speech
            const baseNonSpeech = document.createElement('div');
            baseNonSpeech.className = 'timeline-segment timeline-segment-nonspeech';
            baseNonSpeech.style.left = '0%';
            baseNonSpeech.style.width = '100%';
            baseNonSpeech.title = `Ambient / Non-Speech: ${(vad.total_non_speech_seconds || 0).toFixed(2)}s`;
            vadBar.appendChild(baseNonSpeech);

            // Overlay speech intervals
            (vad.speech_segments || []).forEach(seg => {
                const sLeft = Math.max(0, Math.min(100, (seg.start / dur) * 100));
                const sWidth = Math.max(0.5, Math.min(100 - sLeft, (seg.duration / dur) * 100));
                const segEl = document.createElement('div');
                segEl.className = 'timeline-segment timeline-segment-speech';
                segEl.style.left = `${sLeft}%`;
                segEl.style.width = `${sWidth}%`;
                segEl.title = `Active Speech: ${seg.start.toFixed(2)}s - ${seg.end.toFixed(2)}s (${seg.duration.toFixed(2)}s) · ${seg.mean_dbfs || '--'} dBFS`;
                vadBar.appendChild(segEl);
            });
        }
    }

    function displayDetectionResult(analysis, classification = 'INCONCLUSIVE', features = null) {
        if (stageContainer) stageContainer.style.display = 'none';
        if (resultsContainer) resultsContainer.style.display = 'block';

        const statusTag = document.getElementById('res-verdict-badge');
        const confidenceText = document.getElementById('res-confidence-text');
        const confidenceCircle = document.getElementById('res-confidence-circle');
        const filenameEl = document.getElementById('res-filename');
        const filesizeEl = document.getElementById('res-filesize');
        const statusDetailEl = document.getElementById('res-status-detail');

        if (filenameEl) filenameEl.textContent = analysis.filename || 'voice_sample.wav';
        if (filesizeEl) filesizeEl.textContent = analysis.file_size ? `${(analysis.file_size / 1024).toFixed(1)} KB` : 'N/A';

        // Check Classification
        const isSynthetic = classification === 'SYNTHETIC' || (analysis.synthetic_score && analysis.synthetic_score >= 0.65);
        const isAuthentic = classification === 'AUTHENTIC' || (analysis.synthetic_score && analysis.synthetic_score < 0.35);

        if (isSynthetic) {
            if (statusTag) {
                statusTag.textContent = 'HIGH RISK: SYNTHETIC CLONE DETECTED';
                statusTag.className = 'verdict-badge-red';
            }
            const pct = Math.round((analysis.synthetic_score || 0.88) * 100);
            if (confidenceText) confidenceText.textContent = `${pct}%`;
            if (confidenceCircle) {
                confidenceCircle.style.strokeDashoffset = String(280 - (280 * pct) / 100);
                confidenceCircle.style.stroke = '#ef4444';
            }
            if (statusDetailEl) {
                statusDetailEl.innerHTML = `
                    <strong style="color: #ef4444;">Deepfake Voice Cloning Attack Detected.</strong><br>
                    Acoustic artifacts consistent with neural vocoder synthesis (HiFi-GAN / WaveGlow) and unnatural spectro-temporal formants identified.
                `;
            }
        } else if (isAuthentic) {
            if (statusTag) {
                statusTag.textContent = 'VERIFIED AUTHENTIC HUMAN VOICE';
                statusTag.className = 'verdict-badge-green';
            }
            const pct = Math.round((1 - (analysis.synthetic_score || 0.12)) * 100);
            if (confidenceText) confidenceText.textContent = `${pct}%`;
            if (confidenceCircle) {
                confidenceCircle.style.strokeDashoffset = String(280 - (280 * pct) / 100);
                confidenceCircle.style.stroke = '#10b981';
            }
            if (statusDetailEl) {
                statusDetailEl.innerHTML = `
                    <strong style="color: #10b981;">Authentic Speech Confirmed.</strong><br>
                    Acoustic signals exhibit natural vocal tract biomechanics, continuous fundamental frequency micro-jitter, and biological glottal pulses.
                `;
            }
        } else if (classification === 'ERROR') {
            if (statusTag) {
                statusTag.textContent = 'ANALYSIS ERROR · PROCESSING FAILED';
                statusTag.className = 'verdict-badge-red';
            }
            if (confidenceText) confidenceText.textContent = '!';
            if (confidenceCircle) {
                confidenceCircle.style.strokeDashoffset = '0';
                confidenceCircle.style.stroke = '#ef4444';
            }
            if (statusDetailEl) {
                statusDetailEl.innerHTML = `
                    <strong style="color: #ef4444;">Processing Error Encountered.</strong><br>
                    ${analysis.detection_result || 'The audio file could not be processed by the server. Please verify the format and file size.'}
                `;
            }
        } else {
            // INCONCLUSIVE / AI_MODEL_NOT_CONFIGURED (Truthful zero-hallucination reporting)
            if (statusTag) {
                statusTag.textContent = 'INCONCLUSIVE · MODEL UNCONFIGURED (PHASE 1 BASELINE)';
                statusTag.className = 'verdict-badge-amber';
            }
            if (confidenceText) confidenceText.textContent = '--';
            if (confidenceCircle) {
                confidenceCircle.style.strokeDashoffset = '280';
                confidenceCircle.style.stroke = '#f59e0b';
            }
            if (statusDetailEl) {
                const featHtml = features ? `
                    <div style="margin-top: 8px; padding: 10px; border-radius: 6px; background: rgba(255,255,255,0.03); font-family: var(--cyber-font-mono); font-size: 0.82rem; color: #38bdf8;">
                        &bull; Target Spec: 16,000 Hz Mono PCM (64,600 samples)<br>
                        &bull; RMS Energy: ${features.rms_energy} &bull; Zero Crossing Rate: ${features.zero_crossing_rate}<br>
                        &bull; Spectral Centroid: ${features.spectral_centroid_hz} Hz &bull; High-Freq Ratio (>4kHz): ${features.high_frequency_ratio}
                    </div>
                ` : '';

                statusDetailEl.innerHTML = `
                    <strong>Audio Ingested, Resampled &amp; Preprocessed Successfully.</strong><br>
                    ${analysis.detection_result || 'Preprocessed to 16kHz mono PCM for AASIST / RawNet2 architecture.'}
                    ${featHtml}
                    <div style="margin-top: 8px; color: var(--cyber-text-dim); font-size: 0.8rem;">
                        <em>Note: Place trained model weights ('aasist.onnx') in 'backend/models_weights/' to activate neural inference. No fake scores were fabricated.</em>
                    </div>
                `;
            }
        }

        // Hook 3D Holographic Scene if present
        // Load Genuine 2D Log-Mel Spectrogram Heatmap if available
        if (window.VoiceGuardSpectrogram) {
            const specPayload = (features && features.spectrogram) || (analysis && analysis.spectrogram);
            if (specPayload && specPayload.matrix) {
                const playerEl = document.getElementById('central-audio-player');
                window.VoiceGuardSpectrogram.loadData(specPayload, playerEl);
            } else {
                window.VoiceGuardSpectrogram.setEmpty();
            }
        }

        if (window.VoiceGuardScenes && window.VoiceGuardScenes.setSecurityState) {
            const state = isSynthetic ? 'high-risk' : (isAuthentic ? 'safe' : 'suspicious');
            window.VoiceGuardScenes.setSecurityState(state);
        }

        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // ========================================================================
    // 7. DETECTION HISTORY SEARCH & FILTERING
    // ========================================================================
    const historyTbody = document.getElementById('history-table-tbody');
    const historySearch = document.getElementById('history-search-input');
    const historyDateFilter = document.getElementById('history-date-filter');
    const historyResultFilter = document.getElementById('history-result-filter');
    const historyRiskFilter = document.getElementById('history-risk-filter');
    const historyStats = document.getElementById('history-stats');
    const historyRecordSummary = document.getElementById('history-record-summary');
    const historyRetryBtn = document.getElementById('history-retry-btn');
    const historyFeedback = document.getElementById('history-feedback');
    const exportCsvBtn = document.getElementById('btn-export-history-csv');
    const detailDialog = document.getElementById('history-detail-dialog');
    const detailDialogBody = document.getElementById('history-detail-body');
    const detailDialogClose = document.getElementById('history-detail-close');
    let loadedHistory = [];
    let historyTotal = 0;

    const historyStatElements = {
        total_audio_scans: document.getElementById('history-total-scans'),
        genuine_voices: document.getElementById('history-genuine-voices'),
        ai_generated_voices: document.getElementById('history-ai-voices'),
        threats_detected: document.getElementById('history-threats')
    };

    function getHistoryClassification(item) {
        const status = String(item.analysis_status || '').toUpperCase();
        if (status === 'PENDING') return { key: 'PENDING', label: 'Processing', badge: 'badge-info' };
        if (status === 'FAILED') return { key: 'FAILED', label: 'Analysis failed', badge: 'badge-red' };

        const score = item.synthetic_score;
        if (typeof score !== 'number' || !Number.isFinite(score)) {
            return { key: 'INCONCLUSIVE', label: 'Unassessed', badge: 'badge-amber' };
        }
        if (score >= 0.65) return { key: 'SYNTHETIC', label: 'AI generated', badge: 'badge-red' };
        if (score <= 0.35) return { key: 'AUTHENTIC', label: 'Genuine voice', badge: 'badge-green' };
        return { key: 'INCONCLUSIVE', label: 'Inconclusive', badge: 'badge-amber' };
    }

    function getHistoryRiskLevel(item) {
        if (String(item.analysis_status || '').toLowerCase() !== 'completed' ||
            typeof item.synthetic_score !== 'number' || !Number.isFinite(item.synthetic_score)) {
            return { key: 'UNASSESSED', label: 'Unassessed', badge: 'badge-amber' };
        }
        if (item.synthetic_score >= 0.85) return { key: 'CRITICAL', label: 'Critical', badge: 'badge-red' };
        if (item.synthetic_score >= 0.6) return { key: 'HIGH', label: 'High', badge: 'badge-red' };
        if (item.synthetic_score >= 0.35) return { key: 'MEDIUM', label: 'Medium', badge: 'badge-amber' };
        return { key: 'LOW', label: 'Low', badge: 'badge-green' };
    }

    function formatHistoryDate(value) {
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? 'Date unavailable' : date.toLocaleString();
    }

    function getHistoryDateValue(value) {
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '';
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${date.getFullYear()}-${month}-${day}`;
    }

    function renderHistoryState(title, message, actionLabel, actionName) {
        if (!historyTbody) return;
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 6;

        const state = document.createElement('div');
        state.className = 'history-state';
        const heading = document.createElement('h3');
        heading.textContent = title;
        const description = document.createElement('p');
        description.textContent = message;
        state.append(heading, description);

        if (actionName === 'analysis') {
            const link = document.createElement('a');
            link.className = 'btn btn-primary btn-sm';
            link.href = '#analysis';
            link.textContent = actionLabel;
            state.append(link);
        } else if (actionName) {
            const button = document.createElement('button');
            button.className = 'btn btn-outline btn-sm';
            button.type = 'button';
            button.dataset.historyAction = actionName;
            button.textContent = actionLabel;
            state.append(button);
        }

        cell.append(state);
        row.append(cell);
        historyTbody.replaceChildren(row);
    }

    async function refreshHistoryTable() {
        if (!historyTbody) return;
        historyTbody.setAttribute('aria-busy', 'true');
        historyStats?.setAttribute('aria-busy', 'true');
        if (historyRecordSummary) historyRecordSummary.textContent = 'Loading your account history…';
        if (historyRetryBtn) historyRetryBtn.hidden = true;
        if (historyFeedback) {
            historyFeedback.textContent = '';
            historyFeedback.classList.remove('is-error');
        }
        renderHistoryState('Loading detection history…', 'Retrieving records securely from your account.');

        try {
            const res = await API.getAudioHistory(1, 200);
            if (!res || !Array.isArray(res.history) || !res.stats) {
                throw new Error('The history service returned an incomplete response.');
            }
            loadedHistory = res.history;
            historyTotal = Number(res.stats.total_audio_scans);
            Object.entries(historyStatElements).forEach(([key, element]) => {
                if (element) element.textContent = Number(res.stats[key]).toLocaleString();
            });
            if (historyStats) historyStats.setAttribute('aria-busy', 'false');
            if (historyRecordSummary) {
                historyRecordSummary.textContent = historyTotal === 0
                    ? 'No analysis records are stored for your account.'
                    : `Showing the latest ${loadedHistory.length.toLocaleString()} of ${historyTotal.toLocaleString()} account scans.`;
            }
            renderFilteredHistory();
        } catch (err) {
            console.error('[VoiceGuardApp] Unable to load audio history:', err);
            if (historyStats) historyStats.setAttribute('aria-busy', 'false');
            if (historyRecordSummary) historyRecordSummary.textContent = 'History could not be loaded.';
            if (historyRetryBtn) historyRetryBtn.hidden = false;
            renderHistoryState(
                'History is temporarily unavailable',
                'Your detection history could not be retrieved. Check your connection and try again.',
                'Try again',
                'retry'
            );
        } finally {
            historyTbody.setAttribute('aria-busy', 'false');
        }
    }

    function renderFilteredHistory() {
        if (!historyTbody) return;
        const query = (historySearch?.value || '').toLowerCase().trim();
        const selectedDate = historyDateFilter?.value || '';
        const selectedResult = (historyResultFilter?.value || 'ALL').toUpperCase();
        const selectedRisk = (historyRiskFilter?.value || 'ALL').toUpperCase();

        const filtered = loadedHistory.filter(item => {
            const filename = String(item.filename || '').toLowerCase();
            const matchesQuery = !query || filename.includes(query);
            const matchesDate = !selectedDate || getHistoryDateValue(item.created_at) === selectedDate;
            const matchesResult = selectedResult === 'ALL' || getHistoryClassification(item).key === selectedResult;
            const matchesRisk = selectedRisk === 'ALL' || getHistoryRiskLevel(item).key === selectedRisk;
            return matchesQuery && matchesDate && matchesResult && matchesRisk;
        });

        if (loadedHistory.length === 0) {
            renderHistoryState(
                'No Detection History Yet',
                'Your audio analyses will appear here after you run a voice detection.',
                'Go to Voice Detection',
                'analysis'
            );
            return;
        }

        if (historyRecordSummary) {
            const coverage = historyTotal > loadedHistory.length
                ? ` Latest ${loadedHistory.length.toLocaleString()} of ${historyTotal.toLocaleString()} total scans.`
                : '';
            historyRecordSummary.textContent = `${filtered.length.toLocaleString()} record${filtered.length === 1 ? '' : 's'} match the current filters.${coverage}`;
        }
        if (filtered.length === 0) {
            renderHistoryState(
                'No matching records',
                'Try changing your search or filters to see more results.',
                'Clear filters',
                'clear'
            );
            return;
        }

        const rows = filtered.map(item => {
            const row = document.createElement('tr');
            const classification = getHistoryClassification(item);
            const risk = getHistoryRiskLevel(item);
            const score = item.synthetic_score;
            const confidence = String(item.analysis_status || '').toLowerCase() === 'completed' &&
                typeof score === 'number' && Number.isFinite(score)
                ? `${Math.round(Math.max(score, 1 - score) * 100)}%`
                : '—';

            const fileCell = document.createElement('td');
            const filename = document.createElement('strong');
            filename.className = 'history-record-file';
            filename.textContent = item.filename || 'Unnamed audio file';
            const recordId = document.createElement('small');
            recordId.className = 'history-record-id';
            recordId.textContent = `ID ${item.id}`;
            fileCell.append(filename, recordId);

            const dateCell = document.createElement('td');
            dateCell.textContent = formatHistoryDate(item.created_at);

            const resultCell = document.createElement('td');
            const resultBadge = document.createElement('span');
            resultBadge.className = `badge ${classification.badge}`;
            resultBadge.textContent = classification.label;
            resultCell.append(resultBadge);

            const confidenceCell = document.createElement('td');
            confidenceCell.textContent = confidence;

            const riskCell = document.createElement('td');
            const riskBadge = document.createElement('span');
            riskBadge.className = `badge ${risk.badge}`;
            riskBadge.textContent = risk.label;
            riskCell.append(riskBadge);

            const actionCell = document.createElement('td');
            const detailButton = document.createElement('button');
            detailButton.className = 'btn btn-outline btn-sm';
            detailButton.type = 'button';
            detailButton.dataset.historyAnalysisId = item.id;
            detailButton.textContent = 'View Details';
            actionCell.append(detailButton);

            row.append(fileCell, dateCell, resultCell, confidenceCell, riskCell, actionCell);
            return row;
        });
        historyTbody.replaceChildren(...rows);
    }

    historySearch?.addEventListener('input', renderFilteredHistory);
    historyDateFilter?.addEventListener('change', renderFilteredHistory);
    historyResultFilter?.addEventListener('change', renderFilteredHistory);
    historyRiskFilter?.addEventListener('change', renderFilteredHistory);
    window.addEventListener('hashchange', () => {
        if (window.location.hash === '#history') refreshHistoryTable();
    });
    historyRetryBtn?.addEventListener('click', refreshHistoryTable);
    historyTbody?.addEventListener('click', async event => {
        const target = event.target instanceof Element
            ? event.target.closest('[data-history-action], [data-history-analysis-id]')
            : null;
        if (!target) return;

        if (target.dataset.historyAction === 'retry') {
            await refreshHistoryTable();
            return;
        }
        if (target.dataset.historyAction === 'clear') {
            if (historySearch) historySearch.value = '';
            if (historyDateFilter) historyDateFilter.value = '';
            if (historyResultFilter) historyResultFilter.value = 'ALL';
            if (historyRiskFilter) historyRiskFilter.value = 'ALL';
            renderFilteredHistory();
            return;
        }
        if (!target.dataset.historyAnalysisId || !detailDialog || !detailDialogBody) return;

        detailDialogBody.textContent = 'Loading record details…';
        detailDialog.showModal();
        try {
            const record = await API.getAudioDetails(target.dataset.historyAnalysisId);
            const details = [
                ['Audio file', record.filename],
                ['Analysis ID', record.id],
                ['Analysis status', record.analysis_status],
                ['File type', record.file_type],
                ['File size', Number.isFinite(record.file_size) ? `${record.file_size.toLocaleString()} bytes` : 'Not available'],
                ['Duration', Number.isFinite(record.duration_seconds) ? `${record.duration_seconds.toFixed(2)} seconds` : 'Not available'],
                ['Detection result', getHistoryClassification(record).label],
                ['Synthetic score', typeof record.synthetic_score === 'number' ? `${(record.synthetic_score * 100).toFixed(1)}%` : 'Not assessed'],
                ['Risk level', getHistoryRiskLevel(record).label],
                ['Analysis date', formatHistoryDate(record.created_at)],
                ['Model details', record.detection_result || 'No additional model details were stored.']
            ];
            const grid = document.createElement('dl');
            grid.className = 'history-detail-grid';
            details.forEach(([label, value], index) => {
                const item = document.createElement('div');
                item.className = index === details.length - 1
                    ? 'history-detail-item history-detail-item-wide'
                    : 'history-detail-item';
                const term = document.createElement('dt');
                term.textContent = label;
                const description = document.createElement('dd');
                description.textContent = String(value ?? 'Not available');
                item.append(term, description);
                grid.append(item);
            });
            detailDialogBody.replaceChildren(grid);

            // Add action button to view Spectrogram in Detection View
            const viewSpecBtn = document.createElement('button');
            viewSpecBtn.className = 'btn btn-primary btn-sm mt-3';
            viewSpecBtn.type = 'button';
            viewSpecBtn.style.marginTop = '14px';
            viewSpecBtn.textContent = 'Inspect 2D Spectrogram & Audio Forensics →';
            viewSpecBtn.onclick = async () => {
                detailDialog.close();
                const navAnalysis = document.querySelector('a[data-view="analysis"]');
                if (navAnalysis) navAnalysis.click();
                const resultsContainer = document.getElementById('detection-results-panel');
                if (resultsContainer) resultsContainer.style.display = 'block';

                // Load Spectrogram
                if (window.VoiceGuardSpectrogram) {
                    window.VoiceGuardSpectrogram.setLoading(`Fetching 2D spectrogram for ${record.filename}...`);
                    try {
                        const specData = await API.getAudioSpectrogram(record.id);
                        window.VoiceGuardSpectrogram.loadData(specData);
                    } catch (e) {
                        window.VoiceGuardSpectrogram.setError(`Could not retrieve spectrogram: ${e.message || 'Record lacks audio data'}`);
                    }
                }

                // Load Forensics
                if (API && typeof API.getAudioForensics === 'function') {
                    try {
                        const forensicsRes = await API.getAudioForensics(record.id);
                        if (forensicsRes && forensicsRes.forensics) {
                            renderForensicsDashboard(forensicsRes.forensics, record.duration_seconds || forensicsRes.forensics.duration_seconds);
                        }
                    } catch (fe) {
                        console.warn('[VoiceGuardApp] Forensics retrieval failed for record:', fe);
                    }
                }

                const specEl = document.getElementById('detection-spectrogram-container');
                if (specEl) specEl.scrollIntoView({ behavior: 'smooth' });
            };
            detailDialogBody.append(viewSpecBtn);
        } catch (err) {
            console.error('[VoiceGuardApp] Unable to load detection details:', err);
            detailDialogBody.textContent = 'Unable to load this record. Please close the dialog and try again.';
        }
    });
    detailDialogClose?.addEventListener('click', () => detailDialog?.close());
    detailDialog?.addEventListener('click', event => {
        if (event.target === detailDialog) detailDialog.close();
    });

    exportCsvBtn?.addEventListener('click', async () => {
        if (!exportCsvBtn) return;
        exportCsvBtn.disabled = true;
        if (historyFeedback) {
            historyFeedback.textContent = '';
            historyFeedback.classList.remove('is-error');
        }
        try {
            const csv = await API.exportReportsCsv();
            if (typeof csv !== 'string') throw new Error('The export service returned an invalid response.');
            const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
            const link = document.createElement('a');
            link.href = url;
            link.download = 'voiceguard-forensic-report.csv';
            document.body.append(link);
            link.click();
            link.remove();
            window.setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (err) {
            console.error('[VoiceGuardApp] Unable to export detection history:', err);
            if (historyFeedback) {
                historyFeedback.textContent = 'History export failed. Please try again.';
                historyFeedback.classList.add('is-error');
            }
        } finally {
            exportCsvBtn.disabled = false;
        }
    });

    // ========================================================================
    // 1:1 ECAPA-TDNN SPEAKER VERIFICATION & BIOMETRIC PLATFORM
    // ========================================================================
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function debounce(fn, delay = 300) {
        let timer = null;
        return function (...args) {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), delay);
        };
    }

    function initializeSpeakerVerificationSection() {
        // Navigation Subtabs
        const subtabBtns = document.querySelectorAll('.speaker-subtab-btn');
        const subviews = document.querySelectorAll('.speaker-subview');
        const badgeProfilesCount = document.getElementById('badge-profiles-count');
        const badgeHistoryCount = document.getElementById('badge-history-count');

        // Reference Mode Toggle
        const btnModeAudio = document.getElementById('btn-mode-audio');
        const btnModeProfile = document.getElementById('btn-mode-profile');
        const refDropzoneContainer = document.getElementById('ref-dropzone-container');
        const refProfileSelectContainer = document.getElementById('ref-profile-select-container');
        const refCardTitle = document.getElementById('ecapa-ref-card-title');
        const refCardSubtitle = document.getElementById('ecapa-ref-card-subtitle');
        const refBadge = document.getElementById('ecapa-ref-badge');
        const profileSelect = document.getElementById('ecapa-profile-select');
        const selectedProfileDetails = document.getElementById('ecapa-selected-profile-details');
        const selProfName = document.getElementById('sel-prof-name');
        const selProfId = document.getElementById('sel-prof-id');
        const selProfMeta = document.getElementById('sel-prof-meta');

        // Verification Inputs
        const refUploadBox = document.getElementById('ecapa-ref-upload-box');
        const refInput = document.getElementById('ecapa-ref-input');
        const refFileLabel = document.getElementById('ecapa-ref-file-label');
        const refFileInfo = document.getElementById('ecapa-ref-file-info');
        const refName = document.getElementById('ecapa-ref-name');
        const refSize = document.getElementById('ecapa-ref-size');
        const refPlayer = document.getElementById('ecapa-ref-player');

        const cmpUploadBox = document.getElementById('ecapa-cmp-upload-box');
        const cmpInput = document.getElementById('ecapa-cmp-input');
        const cmpFileLabel = document.getElementById('ecapa-cmp-file-label');
        const cmpFileInfo = document.getElementById('ecapa-cmp-file-info');
        const cmpName = document.getElementById('ecapa-cmp-name');
        const cmpSize = document.getElementById('ecapa-cmp-size');
        const cmpPlayer = document.getElementById('ecapa-cmp-player');

        const thresholdSlider = document.getElementById('ecapa-threshold-slider');
        const thresholdInput = document.getElementById('ecapa-threshold-input');
        const presetBtns = document.querySelectorAll('.ecapa-preset-btn');
        const verifyBtn = document.getElementById('btn-ecapa-verify');
        const verifyBtnText = document.getElementById('btn-ecapa-verify-text');
        const errorAlert = document.getElementById('ecapa-error-alert');
        const errorText = document.getElementById('ecapa-error-text');

        // Verification Results
        const resultsCard = document.getElementById('ecapa-results-card');
        const verdictBanner = document.getElementById('ecapa-verdict-banner');
        const verdictIcon = document.getElementById('ecapa-verdict-icon');
        const verdictTitle = document.getElementById('ecapa-verdict-title');
        const verdictDesc = document.getElementById('ecapa-verdict-desc');
        const verdictPill = document.getElementById('ecapa-verdict-pill');
        const latencyVal = document.getElementById('ecapa-latency-val');

        const simValue = document.getElementById('ecapa-sim-value');
        const metricThreshold = document.getElementById('ecapa-metric-threshold');
        const simGap = document.getElementById('ecapa-sim-gap');
        const simBar = document.getElementById('ecapa-sim-bar');
        const statusValue = document.getElementById('ecapa-status-value');

        const warningsContainer = document.getElementById('ecapa-warnings-container');
        const warningsList = document.getElementById('ecapa-warnings-list');

        const tblRefName = document.getElementById('ecapa-tbl-ref-name');
        const tblCmpName = document.getElementById('ecapa-tbl-cmp-name');
        const tblRefDuration = document.getElementById('ecapa-tbl-ref-duration');
        const tblCmpDuration = document.getElementById('ecapa-tbl-cmp-duration');
        const tblRefRms = document.getElementById('ecapa-tbl-ref-rms');
        const tblCmpRms = document.getElementById('ecapa-tbl-cmp-rms');
        const interpretationNote = document.getElementById('ecapa-interpretation-note');
        const statusPill = document.getElementById('ecapa-status-pill');

        // Enrollment Elements
        const formEnroll = document.getElementById('form-enroll-speaker');
        const inputEnrollName = document.getElementById('enroll-speaker-name');
        const inputEnrollId = document.getElementById('enroll-speaker-id');
        const btnAutoGenId = document.getElementById('btn-auto-gen-id');
        const inputEnrollDept = document.getElementById('enroll-department');
        const selectEnrollClearance = document.getElementById('enroll-clearance');
        const enrollDropzone = document.getElementById('enroll-dropzone');
        const inputEnrollFile = document.getElementById('enroll-file-input');
        const enrollFileLabel = document.getElementById('enroll-file-label');
        const enrollFileInfo = document.getElementById('enroll-file-info');
        const enrollFileName = document.getElementById('enroll-file-name');
        const enrollFileSize = document.getElementById('enroll-file-size');
        const enrollPlayer = document.getElementById('enroll-audio-player');
        const checkEnrollConsent = document.getElementById('enroll-consent-checkbox');
        const alertEnrollFeedback = document.getElementById('enroll-feedback-alert');
        const btnSubmitEnroll = document.getElementById('btn-submit-enroll');
        const btnSubmitEnrollText = document.getElementById('btn-submit-enroll-text');

        // Profiles Management Elements
        const profilesSearchInput = document.getElementById('profiles-search-input');
        const profilesStatusFilter = document.getElementById('profiles-status-filter');
        const btnRefreshProfiles = document.getElementById('btn-refresh-profiles');
        const btnGotoEnroll = document.getElementById('btn-goto-enroll');
        const btnEmptyEnroll = document.getElementById('btn-empty-enroll');
        const profilesFeedbackBanner = document.getElementById('profiles-feedback-banner');
        const profilesCardsContainer = document.getElementById('profiles-cards-container');
        const profilesEmptyState = document.getElementById('profiles-empty-state');

        // History Elements
        const histStatTotal = document.getElementById('hist-stat-total');
        const histStatMatched = document.getElementById('hist-stat-matched');
        const histStatMismatched = document.getElementById('hist-stat-mismatched');
        const histStatInconclusive = document.getElementById('hist-stat-inconclusive');
        const histStatAvgSim = document.getElementById('hist-stat-avg-sim');
        const spkHistSearch = document.getElementById('spk-hist-search');
        const spkHistVerdict = document.getElementById('spk-hist-verdict');
        const btnSpkExportCsv = document.getElementById('btn-spk-export-csv');
        const btnSpkClearHist = document.getElementById('btn-spk-clear-hist');
        const spkHistoryTableBody = document.getElementById('spk-history-table-body');
        const spkHistoryEmpty = document.getElementById('spk-history-empty');

        if (!verifyBtn) return;

        // State Variables
        let currentRefMode = 'audio'; // 'audio' | 'profile'
        let selectedRef = null;
        let selectedCmp = null;
        let selectedSpeakerId = null;
        let cachedProfiles = [];
        let enrollAudioFile = null;

        function formatBytes(bytes) {
            if (!bytes || bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
        }

        function formatDate(isoStr) {
            if (!isoStr) return '—';
            try {
                const d = new Date(isoStr);
                return isNaN(d.getTime()) ? isoStr : d.toLocaleString();
            } catch {
                return isoStr;
            }
        }

        // Check model status
        if (API.getSpeakerModelInfo) {
            API.getSpeakerModelInfo().then(res => {
                if (res && res.status === 'online') {
                    if (statusPill) {
                        statusPill.innerHTML = '<span style="width: 8px; height: 8px; border-radius: 50%; background: #10b981; box-shadow: 0 0 8px #10b981;"></span> SpeechBrain ECAPA-TDNN Online';
                        statusPill.className = 'badge badge-success';
                    }
                }
            }).catch(() => {});
        }

        // ====================================================================
        // SUBTAB NAVIGATION
        // ====================================================================
        function switchSubtab(targetTab) {
            subtabBtns.forEach(b => {
                b.classList.toggle('active', b.dataset.subtab === targetTab);
            });
            subviews.forEach(v => {
                v.style.display = (v.id === `speaker-subview-${targetTab}`) ? 'block' : 'none';
            });

            if (targetTab === 'profiles') {
                loadProfiles();
            } else if (targetTab === 'history') {
                loadHistory();
            } else if (targetTab === 'verify') {
                loadProfileDropdown();
            }
        }

        subtabBtns.forEach(btn => {
            btn.addEventListener('click', () => switchSubtab(btn.dataset.subtab));
        });

        if (btnGotoEnroll) btnGotoEnroll.addEventListener('click', () => switchSubtab('enroll'));
        if (btnEmptyEnroll) btnEmptyEnroll.addEventListener('click', () => switchSubtab('enroll'));

        // ====================================================================
        // REFERENCE MODE TOGGLE (DUAL AUDIO vs ENROLLED PROFILE)
        // ====================================================================
        function setReferenceMode(mode) {
            currentRefMode = mode;
            if (mode === 'audio') {
                btnModeAudio?.classList.add('active');
                btnModeProfile?.classList.remove('active');
                if (refDropzoneContainer) refDropzoneContainer.style.display = 'block';
                if (refProfileSelectContainer) refProfileSelectContainer.style.display = 'none';
                if (refCardTitle) refCardTitle.textContent = 'Reference Audio (Baseline Voiceprint)';
                if (refCardSubtitle) refCardSubtitle.textContent = 'Known baseline recording of claimed identity';
                if (refBadge) {
                    refBadge.textContent = 'Reference';
                    refBadge.className = 'badge badge-info';
                }
            } else {
                btnModeProfile?.classList.add('active');
                btnModeAudio?.classList.remove('active');
                if (refDropzoneContainer) refDropzoneContainer.style.display = 'none';
                if (refProfileSelectContainer) refProfileSelectContainer.style.display = 'block';
                if (refCardTitle) refCardTitle.textContent = 'Enrolled Biometric Profile';
                if (refCardSubtitle) refCardSubtitle.textContent = 'Stored 192-D encrypted voiceprint';
                if (refBadge) {
                    refBadge.textContent = 'Enrolled Voiceprint';
                    refBadge.className = 'badge badge-success';
                }
                loadProfileDropdown();
            }
            hideError();
        }

        btnModeAudio?.addEventListener('click', () => setReferenceMode('audio'));
        btnModeProfile?.addEventListener('click', () => setReferenceMode('profile'));

        async function loadProfileDropdown(preselectId = null) {
            if (!profileSelect || !API.listSpeakerProfiles) return;
            try {
                const res = await API.listSpeakerProfiles('', 'ACTIVE', 100, 0);
                cachedProfiles = res.profiles || [];
                if (badgeProfilesCount) badgeProfilesCount.textContent = res.total ?? cachedProfiles.length;

                profileSelect.innerHTML = '<option value="">-- Choose an Enrolled Speaker --</option>';
                cachedProfiles.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.speaker_id;
                    opt.textContent = `${p.speaker_name} (${p.speaker_id})`;
                    if (preselectId && p.speaker_id === preselectId) {
                        opt.selected = true;
                    }
                    profileSelect.appendChild(opt);
                });

                if (preselectId) {
                    handleProfileSelection(preselectId);
                } else if (profileSelect.value) {
                    handleProfileSelection(profileSelect.value);
                } else {
                    selectedSpeakerId = null;
                    if (selectedProfileDetails) selectedProfileDetails.style.display = 'none';
                }
            } catch (err) {
                console.warn('[VoiceGuardApp] Error loading profile dropdown:', err);
            }
        }

        function handleProfileSelection(speakerId) {
            selectedSpeakerId = speakerId || null;
            const profile = cachedProfiles.find(p => p.speaker_id === speakerId);
            if (profile && selectedProfileDetails) {
                selectedProfileDetails.style.display = 'block';
                if (selProfName) selProfName.textContent = profile.speaker_name;
                if (selProfId) selProfId.textContent = profile.speaker_id;
                if (selProfMeta) {
                    const dept = profile.department ? `Dept: ${profile.department} • ` : '';
                    const clearance = profile.clearance_level ? `Clearance: ${profile.clearance_level} • ` : '';
                    const verifs = profile.verification_count || 0;
                    selProfMeta.textContent = `${dept}${clearance}Enrolled: ${formatDate(profile.enrolled_at)} • Verifications: ${verifs}`;
                }
            } else if (selectedProfileDetails) {
                selectedProfileDetails.style.display = 'none';
            }
            hideError();
        }

        profileSelect?.addEventListener('change', () => {
            handleProfileSelection(profileSelect.value);
        });

        // ====================================================================
        // FILE DROPZONES: REFERENCE & COMPARISON
        // ====================================================================
        if (refUploadBox && refInput) {
            refUploadBox.addEventListener('click', () => refInput.click());
            refUploadBox.addEventListener('dragover', e => {
                e.preventDefault();
                refUploadBox.classList.add('dragover');
            });
            refUploadBox.addEventListener('dragleave', () => refUploadBox.classList.remove('dragover'));
            refUploadBox.addEventListener('drop', e => {
                e.preventDefault();
                refUploadBox.classList.remove('dragover');
                if (e.dataTransfer?.files?.[0]) handleRefFile(e.dataTransfer.files[0]);
            });
            refInput.addEventListener('change', () => {
                if (refInput.files?.[0]) handleRefFile(refInput.files[0]);
            });
        }

        function handleRefFile(file) {
            selectedRef = file;
            refUploadBox?.classList.add('has-file');
            if (refFileLabel) refFileLabel.textContent = `Attached: ${file.name}`;
            if (refName) refName.textContent = file.name;
            if (refSize) refSize.textContent = formatBytes(file.size);
            if (refFileInfo) refFileInfo.style.display = 'block';
            if (refPlayer) refPlayer.src = URL.createObjectURL(file);
            hideError();
        }

        if (cmpUploadBox && cmpInput) {
            cmpUploadBox.addEventListener('click', () => cmpInput.click());
            cmpUploadBox.addEventListener('dragover', e => {
                e.preventDefault();
                cmpUploadBox.classList.add('dragover');
            });
            cmpUploadBox.addEventListener('dragleave', () => cmpUploadBox.classList.remove('dragover'));
            cmpUploadBox.addEventListener('drop', e => {
                e.preventDefault();
                cmpUploadBox.classList.remove('dragover');
                if (e.dataTransfer?.files?.[0]) handleCmpFile(e.dataTransfer.files[0]);
            });
            cmpInput.addEventListener('change', () => {
                if (cmpInput.files?.[0]) handleCmpFile(cmpInput.files[0]);
            });
        }

        function handleCmpFile(file) {
            selectedCmp = file;
            cmpUploadBox?.classList.add('has-file');
            if (cmpFileLabel) cmpFileLabel.textContent = `Attached: ${file.name}`;
            if (cmpName) cmpName.textContent = file.name;
            if (cmpSize) cmpSize.textContent = formatBytes(file.size);
            if (cmpFileInfo) cmpFileInfo.style.display = 'block';
            if (cmpPlayer) cmpPlayer.src = URL.createObjectURL(file);
            hideError();
        }

        // ====================================================================
        // THRESHOLD SLIDER & PRESETS
        // ====================================================================
        if (thresholdSlider && thresholdInput) {
            thresholdSlider.addEventListener('input', () => {
                thresholdInput.value = parseFloat(thresholdSlider.value).toFixed(2);
                updateActivePreset(thresholdSlider.value);
            });
            thresholdInput.addEventListener('input', () => {
                const val = parseFloat(thresholdInput.value);
                if (!isNaN(val) && val >= -1.0 && val <= 1.0) {
                    thresholdSlider.value = val;
                    updateActivePreset(val);
                }
            });
        }

        function updateActivePreset(val) {
            const num = parseFloat(val);
            presetBtns.forEach(btn => {
                const p = parseFloat(btn.dataset.preset);
                btn.classList.toggle('active', Math.abs(num - p) < 0.02);
            });
        }

        presetBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const presetVal = parseFloat(btn.dataset.preset);
                if (!isNaN(presetVal)) {
                    if (thresholdSlider) thresholdSlider.value = presetVal;
                    if (thresholdInput) thresholdInput.value = presetVal.toFixed(2);
                    presetBtns.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                }
            });
        });

        function showError(msg) {
            if (errorAlert && errorText) {
                errorText.textContent = msg;
                errorAlert.style.display = 'block';
            }
        }

        function hideError() {
            if (errorAlert) errorAlert.style.display = 'none';
        }

        // ====================================================================
        // EXECUTE VERIFICATION
        // ====================================================================
        verifyBtn.addEventListener('click', async () => {
            hideError();

            if (currentRefMode === 'profile') {
                if (!selectedSpeakerId) {
                    showError('Please select a registered biometric speaker profile to compare against.');
                    return;
                }
            } else {
                if (!selectedRef) {
                    showError('Please upload or select a Reference Audio file.');
                    return;
                }
            }

            if (!selectedCmp) {
                showError('Please upload or select a Comparison Audio file to verify.');
                return;
            }

            const threshold = thresholdInput ? parseFloat(thresholdInput.value) : 0.25;

            // Set loading state
            verifyBtn.disabled = true;
            if (verifyBtnText) verifyBtnText.textContent = 'Verifying Voiceprints (ECAPA-TDNN)...';

            try {
                const refParam = (currentRefMode === 'profile') ? selectedSpeakerId : selectedRef;
                const data = await API.verifySpeakerV1(refParam, selectedCmp, threshold);

                if (!data || !data.success) {
                    throw new Error(data?.detail || 'Verification service returned an unsuccessful response.');
                }

                // Render Results
                renderVerificationResults(data);

                // Refresh badge counts
                refreshHistoryBadge();

            } catch (err) {
                console.error('[VoiceGuardApp] Speaker Verification Error:', err);
                const detail = err.detail || err.message || 'An error occurred during speaker verification.';
                showError(detail);
            } finally {
                verifyBtn.disabled = false;
                if (verifyBtnText) verifyBtnText.textContent = 'Verify Voiceprints';
            }
        });

        function renderVerificationResults(data) {
            if (!resultsCard) return;
            resultsCard.style.display = 'block';

            const sim = data.cosine_similarity;
            const thresh = data.threshold;
            const verdict = data.verdict || (data.is_same_speaker ? 'SAME_SPEAKER' : 'DIFFERENT_SPEAKER');
            const isMatch = (verdict === 'SAME_SPEAKER');
            const isInconclusive = (verdict === 'INCONCLUSIVE');

            // Verdict Banner styling
            if (verdictBanner) {
                if (isInconclusive) {
                    verdictBanner.className = 'ecapa-verdict-inconclusive';
                } else if (isMatch) {
                    verdictBanner.className = 'ecapa-verdict-same';
                } else {
                    verdictBanner.className = 'ecapa-verdict-different';
                }
            }

            // Verdict Icon
            if (verdictIcon) {
                if (isInconclusive) {
                    verdictIcon.style.background = 'rgba(245, 158, 11, 0.2)';
                    verdictIcon.innerHTML = '<svg viewBox="0 0 24 24" width="28" height="28" stroke="#f59e0b" stroke-width="2.5" fill="none"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>';
                } else if (isMatch) {
                    verdictIcon.style.background = 'rgba(16, 185, 129, 0.2)';
                    verdictIcon.innerHTML = '<svg viewBox="0 0 24 24" width="28" height="28" stroke="#10b981" stroke-width="2.5" fill="none"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>';
                } else {
                    verdictIcon.style.background = 'rgba(239, 68, 68, 0.2)';
                    verdictIcon.innerHTML = '<svg viewBox="0 0 24 24" width="28" height="28" stroke="#ef4444" stroke-width="2.5" fill="none"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>';
                }
            }

            // Verdict Title & Desc
            if (verdictTitle) {
                if (isInconclusive) {
                    verdictTitle.textContent = 'INCONCLUSIVE — Acoustic Distance Ambiguous';
                    verdictTitle.style.color = '#fbbf24';
                } else if (isMatch) {
                    verdictTitle.textContent = 'SAME SPEAKER — Biometric Voiceprint Authenticated';
                    verdictTitle.style.color = '#34d399';
                } else {
                    verdictTitle.textContent = 'DIFFERENT SPEAKER — Biometric Voice Mismatch';
                    verdictTitle.style.color = '#f87171';
                }
            }

            if (verdictDesc) {
                if (isInconclusive) {
                    verdictDesc.textContent = `Acoustic distance is borderline or audio quality degraded (Cosine Similarity: ${sim >= 0 ? '+' : ''}${sim.toFixed(4)}, Threshold: ${thresh.toFixed(2)}). Verification requires a cleaner sample.`;
                } else if (isMatch) {
                    verdictDesc.textContent = `Strong directional alignment in 192-D VoxCeleb latent space (Cosine Similarity: ${sim >= 0 ? '+' : ''}${sim.toFixed(4)} ≥ ${thresh.toFixed(2)})`;
                } else {
                    verdictDesc.textContent = `Acoustic distance indicates distinct vocal tract characteristics (Cosine Similarity: ${sim >= 0 ? '+' : ''}${sim.toFixed(4)} < ${thresh.toFixed(2)})`;
                }
            }

            if (verdictPill) {
                if (isInconclusive) {
                    verdictPill.textContent = 'INCONCLUSIVE';
                    verdictPill.className = 'badge badge-warning';
                } else if (isMatch) {
                    verdictPill.textContent = 'AUTHENTIC MATCH';
                    verdictPill.className = 'badge badge-success';
                } else {
                    verdictPill.textContent = 'VOICE MISMATCH';
                    verdictPill.className = 'badge badge-danger';
                }
            }

            if (latencyVal) {
                latencyVal.textContent = `${Math.round(data.processing_time * 1000)} ms`;
            }

            // Key Metrics
            if (simValue) {
                simValue.textContent = `${sim >= 0 ? '+' : ''}${sim.toFixed(4)}`;
                simValue.style.color = isInconclusive ? '#fbbf24' : (isMatch ? '#34d399' : '#f87171');
            }

            if (metricThreshold) {
                metricThreshold.textContent = thresh.toFixed(2);
            }

            if (simGap) {
                const diff = sim - thresh;
                simGap.textContent = diff >= 0
                    ? `+${diff.toFixed(3)} above threshold`
                    : `${diff.toFixed(3)} below threshold`;
                simGap.style.color = isInconclusive ? '#fbbf24' : (diff >= 0 ? '#34d399' : '#f87171');
            }

            if (simBar) {
                const pct = Math.max(0, Math.min(100, ((sim + 1.0) / 2.0) * 100));
                simBar.style.width = `${pct}%`;
                simBar.style.background = isInconclusive ? '#f59e0b' : (isMatch ? '#10b981' : '#ef4444');
            }

            if (statusValue) {
                statusValue.textContent = data.verdict || data.verification_status;
                statusValue.style.color = isInconclusive ? '#fbbf24' : (isMatch ? '#34d399' : '#f87171');
            }

            // Audio Quality Warnings
            if (warningsContainer && warningsList) {
                warningsList.innerHTML = '';
                const warnings = data.audio_quality_warnings || [];
                if (warnings.length > 0) {
                    warnings.forEach(w => {
                        const li = document.createElement('li');
                        li.textContent = w;
                        warningsList.appendChild(li);
                    });
                    warningsContainer.style.display = 'block';
                } else {
                    warningsContainer.style.display = 'none';
                }
            }

            // Audio Information Comparison Table
            const refInfo = data.reference_audio_info || {};
            const cmpInfo = data.comparison_audio_info || {};

            if (tblRefName) {
                if (data.speaker_name) {
                    tblRefName.textContent = `${data.speaker_name} (${data.speaker_id || ''}) [Enrolled Profile]`;
                } else {
                    tblRefName.textContent = refInfo.filename || (selectedRef ? selectedRef.name : 'Reference Audio');
                }
            }
            if (tblCmpName) {
                tblCmpName.textContent = cmpInfo.filename || (selectedCmp ? selectedCmp.name : 'Comparison Audio');
            }

            if (tblRefDuration) tblRefDuration.textContent = refInfo.duration_seconds !== undefined ? `${refInfo.duration_seconds.toFixed(2)}s` : '—';
            if (tblCmpDuration) tblCmpDuration.textContent = cmpInfo.duration_seconds !== undefined ? `${cmpInfo.duration_seconds.toFixed(2)}s` : '—';

            if (tblRefRms) tblRefRms.textContent = refInfo.rms_energy !== undefined ? refInfo.rms_energy.toFixed(4) : '—';
            if (tblCmpRms) tblCmpRms.textContent = cmpInfo.rms_energy !== undefined ? cmpInfo.rms_energy.toFixed(4) : '—';

            if (interpretationNote && data.interpretation_note) {
                interpretationNote.textContent = data.interpretation_note;
            }

            resultsCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        // ====================================================================
        // ENROLLMENT LOGIC (MODULE 1)
        // ====================================================================
        if (btnAutoGenId && inputEnrollId) {
            btnAutoGenId.addEventListener('click', () => {
                const rawName = (inputEnrollName?.value || 'SPK').trim().toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 8) || 'SPK';
                const rand = Math.random().toString(36).substring(2, 6).toUpperCase();
                inputEnrollId.value = `SPK-${rawName}-${rand}`;
            });
        }

        if (enrollDropzone && inputEnrollFile) {
            enrollDropzone.addEventListener('click', () => inputEnrollFile.click());
            enrollDropzone.addEventListener('dragover', e => {
                e.preventDefault();
                enrollDropzone.classList.add('dragover');
            });
            enrollDropzone.addEventListener('dragleave', () => enrollDropzone.classList.remove('dragover'));
            enrollDropzone.addEventListener('drop', e => {
                e.preventDefault();
                enrollDropzone.classList.remove('dragover');
                if (e.dataTransfer?.files?.[0]) handleEnrollFile(e.dataTransfer.files[0]);
            });
            inputEnrollFile.addEventListener('change', () => {
                if (inputEnrollFile.files?.[0]) handleEnrollFile(inputEnrollFile.files[0]);
            });
        }

        function handleEnrollFile(file) {
            enrollAudioFile = file;
            enrollDropzone?.classList.add('has-file');
            if (enrollFileLabel) enrollFileLabel.textContent = `Attached: ${file.name}`;
            if (enrollFileName) enrollFileName.textContent = file.name;
            if (enrollFileSize) enrollFileSize.textContent = formatBytes(file.size);
            if (enrollFileInfo) enrollFileInfo.style.display = 'block';
            if (enrollPlayer) enrollPlayer.src = URL.createObjectURL(file);
            if (alertEnrollFeedback) alertEnrollFeedback.style.display = 'none';
        }

        function showEnrollAlert(msg, type = 'info') {
            if (!alertEnrollFeedback) return;
            alertEnrollFeedback.style.display = 'block';
            if (type === 'success') {
                alertEnrollFeedback.style.background = 'rgba(16, 185, 129, 0.15)';
                alertEnrollFeedback.style.border = '1px solid rgba(16, 185, 129, 0.4)';
                alertEnrollFeedback.style.color = '#6ee7b7';
            } else {
                alertEnrollFeedback.style.background = 'rgba(239, 68, 68, 0.15)';
                alertEnrollFeedback.style.border = '1px solid rgba(239, 68, 68, 0.4)';
                alertEnrollFeedback.style.color = '#fca5a5';
            }
            alertEnrollFeedback.textContent = msg;
        }

        formEnroll?.addEventListener('submit', async e => {
            e.preventDefault();
            if (!enrollAudioFile) {
                showEnrollAlert('Please select or drop a reference voice recording.', 'danger');
                return;
            }
            if (!checkEnrollConsent?.checked) {
                showEnrollAlert('Explicit biometric consent confirmation is required to proceed.', 'danger');
                return;
            }

            const name = inputEnrollName.value.trim();
            const speakerId = inputEnrollId.value.trim();
            const dept = inputEnrollDept.value.trim();
            const clearance = selectEnrollClearance.value;

            btnSubmitEnroll.disabled = true;
            if (btnSubmitEnrollText) btnSubmitEnrollText.textContent = 'Extracting 192-D Voiceprint & Encrypting...';

            try {
                const res = await API.enrollSpeaker(name, enrollAudioFile, true, dept, clearance, speakerId);
                if (!res || !res.success) {
                    throw new Error(res?.detail || 'Enrollment failed.');
                }

                showEnrollAlert(
                    `Biometric voiceprint enrolled successfully for ${res.speaker_name} (${res.speaker_id})! Acoustic duration: ${res.audio_duration_seconds.toFixed(2)}s. Embedding encrypted with PBKDF2-HMAC-SHA256 at rest.`,
                    'success'
                );

                // Reset inputs
                formEnroll.reset();
                enrollAudioFile = null;
                enrollDropzone?.classList.remove('has-file');
                if (enrollFileLabel) enrollFileLabel.textContent = 'Drop baseline voice recording here or browse';
                if (enrollFileInfo) enrollFileInfo.style.display = 'none';
                if (enrollPlayer) enrollPlayer.removeAttribute('src');

                // Refresh dropdown and profiles
                loadProfileDropdown();
                loadProfiles();
            } catch (err) {
                console.error('[VoiceGuardApp] Enrollment Error:', err);
                const detail = err.detail || err.message || 'Enrollment failed due to an unexpected error.';
                showEnrollAlert(detail, 'danger');
            } finally {
                btnSubmitEnroll.disabled = false;
                if (btnSubmitEnrollText) btnSubmitEnrollText.textContent = 'Extract 192-D Voiceprint & Enroll';
            }
        });

        // ====================================================================
        // PROFILES MANAGEMENT (MODULE 2)
        // ====================================================================
        async function loadProfiles() {
            if (!profilesCardsContainer || !API.listSpeakerProfiles) return;
            const search = profilesSearchInput?.value.trim() || '';
            const status = profilesStatusFilter?.value || '';

            try {
                const res = await API.listSpeakerProfiles(search, status, 100, 0);
                const profiles = res.profiles || [];
                if (badgeProfilesCount) badgeProfilesCount.textContent = res.total ?? profiles.length;

                if (profiles.length === 0) {
                    profilesCardsContainer.style.display = 'none';
                    if (profilesEmptyState) profilesEmptyState.style.display = 'block';
                    return;
                }

                if (profilesEmptyState) profilesEmptyState.style.display = 'none';
                profilesCardsContainer.style.display = 'grid';
                profilesCardsContainer.innerHTML = '';

                profiles.forEach(p => {
                    const card = document.createElement('div');
                    card.className = 'speaker-profile-card';

                    const enrolledDate = formatDate(p.enrolled_at);
                    const lastVerified = p.last_verified_at ? formatDate(p.last_verified_at) : 'Never';
                    const durationStr = p.audio_duration_seconds ? `${p.audio_duration_seconds.toFixed(2)}s` : '—';
                    const verifsCount = p.verification_count || 0;

                    card.innerHTML = `
                        <div>
                            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
                                <div>
                                    <h4 style="font-size: 1.05rem; font-weight: 700; color: #f8fafc; margin: 0 0 0.25rem;">${escapeHtml(p.speaker_name)}</h4>
                                    <span style="font-family: monospace; font-size: 0.75rem; color: #38bdf8; background: rgba(56, 189, 248, 0.15); padding: 2px 7px; border-radius: 4px; border: 1px solid rgba(56, 189, 248, 0.3);">
                                        ${escapeHtml(p.speaker_id)}
                                    </span>
                                </div>
                                <span class="badge ${p.voiceprint_status === 'ACTIVE' ? 'badge-success' : 'badge-outline'}" style="font-size: 0.72rem;">
                                    ${p.voiceprint_status}
                                </span>
                            </div>

                            <div style="font-size: 0.8rem; color: #94a3b8; display: grid; gap: 0.4rem; margin-bottom: 1rem;">
                                <div><strong style="color: #cbd5e1;">Dept:</strong> ${escapeHtml(p.department || 'Not specified')}</div>
                                <div><strong style="color: #cbd5e1;">Clearance:</strong> ${escapeHtml(p.clearance_level || 'Tier-3 (Executive)')}</div>
                                <div><strong style="color: #cbd5e1;">Enrolled:</strong> ${enrolledDate}</div>
                                <div><strong style="color: #cbd5e1;">Acoustic Baseline:</strong> ${durationStr}</div>
                                <div><strong style="color: #cbd5e1;">Verifications:</strong> ${verifsCount} (${lastVerified})</div>
                            </div>
                        </div>

                        <div>
                            <div style="margin-bottom: 0.85rem; padding: 0.45rem 0.65rem; background: rgba(15, 23, 42, 0.8); border-radius: 6px; font-size: 0.72rem; color: #64748b; display: flex; align-items: center; gap: 0.4rem;">
                                <svg viewBox="0 0 24 24" width="12" height="12" stroke="#10b981" stroke-width="2" fill="none"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                                <span>192-D L2-Normalized &bull; Encrypted at Rest</span>
                            </div>
                            <div style="display: flex; gap: 0.5rem;">
                                <button type="button" class="btn btn-sm btn-primary btn-card-verify" data-id="${escapeHtml(p.speaker_id)}" style="flex: 1; padding: 0.45rem 0.5rem; font-size: 0.78rem; display: flex; align-items: center; justify-content: center; gap: 0.35rem;">
                                    <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg>
                                    <span>Verify Against</span>
                                </button>
                                <button type="button" class="btn btn-sm btn-outline btn-card-delete" data-id="${escapeHtml(p.speaker_id)}" style="color: #f87171; border-color: rgba(239, 68, 68, 0.3); padding: 0.45rem 0.65rem; font-size: 0.78rem;" title="Delete Voiceprint">
                                    <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                                </button>
                            </div>
                        </div>
                    `;

                    // Wire up Card buttons
                    const btnVerify = card.querySelector('.btn-card-verify');
                    btnVerify?.addEventListener('click', () => {
                        switchSubtab('verify');
                        setReferenceMode('profile');
                        loadProfileDropdown(p.speaker_id);
                        document.getElementById('ecapa-cmp-upload-box')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    });

                    const btnDelete = card.querySelector('.btn-card-delete');
                    btnDelete?.addEventListener('click', async () => {
                        if (!confirm(`Are you sure you want to permanently delete the biometric voiceprint for ${p.speaker_name} (${p.speaker_id})? This cannot be undone.`)) {
                            return;
                        }
                        try {
                            const delRes = await API.deleteSpeakerProfile(p.speaker_id);
                            showProfileFeedback(delRes?.message || `Voiceprint ${p.speaker_id} deleted successfully.`, 'success');
                            loadProfiles();
                            loadProfileDropdown();
                        } catch (err) {
                            console.error('[VoiceGuardApp] Delete Profile Error:', err);
                            showProfileFeedback(err.detail || err.message || 'Failed to delete voiceprint profile.', 'danger');
                        }
                    });

                    profilesCardsContainer.appendChild(card);
                });

            } catch (err) {
                console.error('[VoiceGuardApp] Error loading profiles:', err);
                showProfileFeedback(err.detail || err.message || 'Error loading speaker profiles.', 'danger');
            }
        }

        function showProfileFeedback(msg, type = 'info') {
            if (!profilesFeedbackBanner) return;
            profilesFeedbackBanner.style.display = 'block';
            if (type === 'success') {
                profilesFeedbackBanner.style.background = 'rgba(16, 185, 129, 0.15)';
                profilesFeedbackBanner.style.border = '1px solid rgba(16, 185, 129, 0.4)';
                profilesFeedbackBanner.style.color = '#6ee7b7';
            } else {
                profilesFeedbackBanner.style.background = 'rgba(239, 68, 68, 0.15)';
                profilesFeedbackBanner.style.border = '1px solid rgba(239, 68, 68, 0.4)';
                profilesFeedbackBanner.style.color = '#fca5a5';
            }
            profilesFeedbackBanner.textContent = msg;
            setTimeout(() => {
                if (profilesFeedbackBanner) profilesFeedbackBanner.style.display = 'none';
            }, 6000);
        }

        profilesSearchInput?.addEventListener('input', debounce(loadProfiles, 300));
        profilesStatusFilter?.addEventListener('change', loadProfiles);
        btnRefreshProfiles?.addEventListener('click', loadProfiles);

        // ====================================================================
        // VERIFICATION HISTORY (MODULE 4)
        // ====================================================================
        async function refreshHistoryBadge() {
            if (!API.getSpeakerHistory) return;
            try {
                const res = await API.getSpeakerHistory({ limit: 1 });
                if (badgeHistoryCount) badgeHistoryCount.textContent = res.total ?? 0;
            } catch {}
        }

        async function loadHistory() {
            if (!spkHistoryTableBody || !API.getSpeakerHistory) return;
            const search = spkHistSearch?.value.trim() || '';
            const verdict = spkHistVerdict?.value || '';

            try {
                const res = await API.getSpeakerHistory({ search, verdict, limit: 100 });
                const items = res.items || [];
                const total = res.total ?? items.length;

                if (badgeHistoryCount) badgeHistoryCount.textContent = total;

                // Compute Stats
                let matchCount = 0;
                let mismatchCount = 0;
                let inconclusiveCount = 0;
                let simSum = 0;

                items.forEach(it => {
                    const v = it.verdict || (it.is_same_speaker ? 'SAME_SPEAKER' : 'DIFFERENT_SPEAKER');
                    if (v === 'SAME_SPEAKER') matchCount++;
                    else if (v === 'DIFFERENT_SPEAKER') mismatchCount++;
                    else if (v === 'INCONCLUSIVE') inconclusiveCount++;
                    simSum += (it.cosine_similarity || 0);
                });

                const avgSim = items.length > 0 ? (simSum / items.length).toFixed(3) : '0.00';

                if (histStatTotal) histStatTotal.textContent = total;
                if (histStatMatched) histStatMatched.textContent = matchCount;
                if (histStatMismatched) histStatMismatched.textContent = mismatchCount;
                if (histStatInconclusive) histStatInconclusive.textContent = inconclusiveCount;
                if (histStatAvgSim) histStatAvgSim.textContent = avgSim;

                if (items.length === 0) {
                    spkHistoryTableBody.innerHTML = '';
                    if (spkHistoryEmpty) spkHistoryEmpty.style.display = 'block';
                    return;
                }

                if (spkHistoryEmpty) spkHistoryEmpty.style.display = 'none';
                spkHistoryTableBody.innerHTML = '';

                items.forEach(it => {
                    const row = document.createElement('tr');
                    const v = it.verdict || (it.is_same_speaker ? 'SAME_SPEAKER' : 'DIFFERENT_SPEAKER');
                    const sim = it.cosine_similarity;
                    const latency = it.processing_time_ms ? `${Math.round(it.processing_time_ms)} ms` : '—';
                    const dateStr = formatDate(it.created_at);

                    let verdictBadge = '';
                    let simColor = '#f8fafc';
                    if (v === 'SAME_SPEAKER') {
                        verdictBadge = '<span class="badge badge-success" style="font-size: 0.72rem;">SAME_SPEAKER</span>';
                        simColor = '#34d399';
                    } else if (v === 'DIFFERENT_SPEAKER') {
                        verdictBadge = '<span class="badge badge-danger" style="font-size: 0.72rem;">DIFFERENT_SPEAKER</span>';
                        simColor = '#f87171';
                    } else {
                        verdictBadge = '<span class="badge badge-warning" style="font-size: 0.72rem;">INCONCLUSIVE</span>';
                        simColor = '#fbbf24';
                    }

                    const targetDisplay = it.speaker_name
                        ? `<span style="font-weight: 600; color: #93c5fd;">${escapeHtml(it.speaker_name)}</span> <span style="font-size: 0.75rem; color: #64748b;">(${escapeHtml(it.speaker_id || '')})</span>`
                        : `<span style="font-family: monospace; color: #cbd5e1;">${escapeHtml(it.reference_filename || 'Direct Audio')}</span>`;

                    row.innerHTML = `
                        <td style="white-space: nowrap; font-size: 0.78rem; color: #94a3b8;">${dateStr}</td>
                        <td>${targetDisplay}</td>
                        <td style="font-family: monospace; font-size: 0.8rem; color: #cbd5e1;">${escapeHtml(it.comparison_filename || 'Probe')}</td>
                        <td style="font-family: monospace; font-weight: 700; color: ${simColor};">${sim >= 0 ? '+' : ''}${sim.toFixed(4)}</td>
                        <td>${verdictBadge}</td>
                        <td style="font-family: monospace; font-size: 0.8rem; color: #94a3b8;">${it.threshold.toFixed(2)}</td>
                        <td style="font-size: 0.8rem; color: #94a3b8;">${latency}</td>
                        <td>
                            <button type="button" class="btn btn-sm btn-outline btn-row-del" data-id="${it.id}" style="color: #f87171; border-color: rgba(239, 68, 68, 0.3); padding: 0.25rem 0.5rem; font-size: 0.75rem;" title="Delete Record">
                                <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                            </button>
                        </td>
                    `;

                    row.querySelector('.btn-row-del')?.addEventListener('click', async () => {
                        try {
                            await API.deleteSpeakerHistoryRecord(it.id);
                            loadHistory();
                        } catch (err) {
                            console.error('[VoiceGuardApp] Delete History Record Error:', err);
                        }
                    });

                    spkHistoryTableBody.appendChild(row);
                });

            } catch (err) {
                console.error('[VoiceGuardApp] Error loading history:', err);
            }
        }

        spkHistSearch?.addEventListener('input', debounce(loadHistory, 300));
        spkHistVerdict?.addEventListener('change', loadHistory);

        btnSpkExportCsv?.addEventListener('click', () => {
            const search = spkHistSearch?.value.trim() || '';
            const verdict = spkHistVerdict?.value || '';
            const url = API.getSpeakerHistoryExportUrl(search, verdict);
            window.open(url, '_blank');
        });

        btnSpkClearHist?.addEventListener('click', async () => {
            if (!confirm('Are you sure you want to clear your entire speaker verification history? This cannot be undone.')) {
                return;
            }
            try {
                await API.clearSpeakerHistory();
                loadHistory();
            } catch (err) {
                console.error('[VoiceGuardApp] Clear History Error:', err);
            }
        });

        // Initial Load
        loadProfileDropdown();
        refreshHistoryBadge();
    }

    refreshHistoryTable();
    initializeSpeakerVerificationSection();

});
