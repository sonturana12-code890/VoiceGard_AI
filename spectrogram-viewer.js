/**
 * VOICEGUARD AI — Advanced 2D Log-Mel Spectrogram Heatmap Visualizer
 * Professional-grade HTML5 Canvas-based forensic acoustic spectrum analyzer.
 * 
 * Features:
 * - 40 Mel frequency filterbank bands (0 Hz to 8,000 Hz, 16 kHz sample rate)
 * - 512-point FFT, 160-sample hop length (10ms temporal resolution)
 * - Calibrated dB dynamic range (-80 dB to 0 dB normalized)
 * - 4 scientific/cyber color palettes: Cyberpunk (default), Viridis, Plasma, Grayscale
 * - Dual-layer rendering: Offscreen heatmap buffer + sharp High-DPI overlay canvas
 * - Interactive hover inspection: Neon crosshairs + real-time floating Cyber HUD tooltip
 * - Zoom & Pan navigation (1x to 8x time-domain magnification with drag-to-pan)
 * - Bi-directional audio player synchronization (live playhead scrubber + click-to-seek)
 * - Full responsive reflow via ResizeObserver
 * - Robust Empty, Loading (cyber shimmer), and Error states
 * 
 * Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.
 */

(function (window, document) {
    'use strict';

    // =========================================================================
    // COLORMAP GENERATORS (256-ENTRY RGB LOOKUP TABLES)
    // =========================================================================

    function interpolateRgb(c1, c2, factor) {
        return [
            Math.round(c1[0] + (c2[0] - c1[0]) * factor),
            Math.round(c1[1] + (c2[1] - c1[1]) * factor),
            Math.round(c1[2] + (c2[2] - c1[2]) * factor),
        ];
    }

    function buildLut(stops) {
        const lut = new Uint8ClampedArray(256 * 3);
        const numSegments = stops.length - 1;
        for (let i = 0; i < 256; i++) {
            const norm = i / 255.0;
            const segment = Math.min(Math.floor(norm * numSegments), numSegments - 1);
            const segStart = segment / numSegments;
            const segEnd = (segment + 1) / numSegments;
            const factor = (norm - segStart) / (segEnd - segStart);
            const rgb = interpolateRgb(stops[segment], stops[segment + 1], Math.max(0, Math.min(1, factor)));
            lut[i * 3 + 0] = rgb[0];
            lut[i * 3 + 1] = rgb[1];
            lut[i * 3 + 2] = rgb[2];
        }
        return lut;
    }

    const COLORMAPS = {
        // VoiceGuard Cyberpunk (Default): Deep SOC Navy -> Dark Violet -> Magenta -> Neon Orange -> Cyber Cyan
        cyberpunk: buildLut([
            [6, 11, 23],     // -80 dB: Deep SOC navy black
            [22, 16, 56],    // -65 dB: Dark indigo
            [65, 18, 92],    // -50 dB: Rich violet
            [140, 24, 108],  // -35 dB: Hot magenta
            [225, 68, 62],   // -20 dB: Intense crimson/orange
            [248, 160, 42],  // -10 dB: Radiant gold
            [0, 242, 254],   //   0 dB: White-hot cyan
        ]),

        // Viridis (Scientific Standard): Perceptually uniform for rigorous publication
        viridis: buildLut([
            [68, 1, 84],     // Deep purple
            [59, 82, 139],   // Blue
            [33, 145, 140],  // Teal
            [94, 201, 98],   // Green
            [253, 231, 37],  // Bright yellow
        ]),

        // Plasma: High vibrancy thermal progression
        plasma: buildLut([
            [13, 8, 135],    // Dark blue
            [106, 0, 168],   // Violet
            [177, 42, 144],  // Pink
            [225, 100, 98],  // Orange
            [240, 249, 33],  // Hot yellow
        ]),

        // Grayscale: High-contrast monochromatic forensic view
        grayscale: buildLut([
            [8, 10, 15],     // Pure near-black
            [50, 55, 65],    // Dark charcoal
            [110, 118, 130], // Mid gray
            [190, 198, 205], // Light slate
            [255, 255, 255], // Pure white
        ]),
    };

    // =========================================================================
    // SPECTROGRAM VIEWER CLASS
    // =========================================================================

    class LogMelSpectrogramViewer {
        /**
         * @param {string|HTMLElement} container - DOM element or selector for the viewer
         * @param {Object} options - Configuration options
         */
        constructor(container, options = {}) {
            this.container = typeof container === 'string' ? document.querySelector(container) : container;
            if (!this.container) {
                console.warn('[SpectrogramViewer] Container not found:', container);
                return;
            }

            this.options = Object.assign({
                defaultColormap: 'cyberpunk',
                minDb: -80.0,
                maxDb: 0.0,
                height: 320,
                gutterLeft: 64,   // Space for frequency axis labels
                gutterRight: 64,  // Space for dB colorbar legend
                gutterBottom: 32, // Space for time axis labels
                gutterTop: 18,    // Top margin padding
            }, options);

            this.colormapName = this.options.defaultColormap;
            this.data = null;             // Backend spectrogram matrix payload
            this.audioElement = null;     // Synchronized HTML5 Audio element
            this.state = 'empty';         // 'empty' | 'loading' | 'ready' | 'error'
            this.errorMessage = '';

            // Zoom & Pan Viewport State
            this.zoomLevel = 1.0;
            this.viewStartSec = 0.0;
            this.viewEndSec = 0.0;
            this.isDragging = false;
            this.dragStartX = 0;
            this.dragStartViewStart = 0;

            // Hover & Inspection State
            this.hoverPos = null;         // { x, y } in CSS pixels relative to canvas
            this.isHovering = false;
            this.currentPlayheadSec = 0.0;
            this.animFrameId = null;

            // Offscreen Buffer for cached matrix heatmap
            this.offscreenCanvas = document.createElement('canvas');
            this.offscreenCtx = this.offscreenCanvas.getContext('2d');

            // Build DOM structure and bind events
            this._buildDOM();
            this._bindEvents();
            this._observeResize();
            this.setEmpty();
        }

        // =====================================================================
        // DOM CONSTRUCTION & STYLING
        // =====================================================================

        _buildDOM() {
            this.container.innerHTML = `
                <div class="vg-spec-card">
                    <!-- Top Control Toolbar -->
                    <div class="vg-spec-toolbar">
                        <div class="vg-spec-title-group">
                            <span class="vg-spec-indicator"></span>
                            <strong class="vg-spec-title">2D LOG-MEL SPECTROGRAM HEATMAP</strong>
                            <span class="vg-spec-badge">40 MEL BANDS &bull; 16 kHz</span>
                            <span class="vg-spec-subbadge" id="vg-spec-frame-count">0 frames</span>
                        </div>
                        <div class="vg-spec-controls-group">
                            <label class="vg-spec-control-label" for="vg-spec-colormap-select">Palette:</label>
                            <select class="vg-spec-select" id="vg-spec-colormap-select" title="Switch spectrogram color palette">
                                <option value="cyberpunk" selected>Cyberpunk (Default)</option>
                                <option value="viridis">Viridis (Scientific)</option>
                                <option value="plasma">Plasma (Thermal)</option>
                                <option value="grayscale">Grayscale (High Contrast)</option>
                            </select>
                            <div class="vg-spec-btn-group">
                                <button type="button" class="vg-spec-btn" id="vg-spec-btn-zoom-out" title="Zoom out time axis (-)" aria-label="Zoom out">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
                                </button>
                                <span class="vg-spec-zoom-display" id="vg-spec-zoom-indicator" title="Current Zoom (1.0x - 8.0x)">1.0x</span>
                                <button type="button" class="vg-spec-btn" id="vg-spec-btn-zoom-in" title="Zoom in time axis (+)" aria-label="Zoom in">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
                                </button>
                            </div>
                            <button type="button" class="vg-spec-reset-btn" id="vg-spec-btn-zoom-reset" title="Reset Zoom to 1.0x (full audio timeline)">
                                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
                                <span>Reset Zoom</span>
                            </button>
                        </div>
                    </div>

                    <!-- Canvas Visualization Container -->
                    <div class="vg-spec-canvas-wrapper" id="vg-spec-canvas-wrapper">
                        <canvas class="vg-spec-canvas" id="vg-spec-canvas"></canvas>
                        
                        <!-- Floating Cyber HUD Tooltip -->
                        <div class="vg-spec-hud-tooltip" id="vg-spec-hud-tooltip" style="display: none;">
                            <div class="vg-spec-hud-header">ACOUSTIC RETICLE INSPECTION</div>
                            <div class="vg-spec-hud-grid">
                                <div><span class="vg-spec-hud-lbl">TIME:</span> <strong id="hud-time">0.00s</strong></div>
                                <div><span class="vg-spec-hud-lbl">FREQ:</span> <strong id="hud-freq">0 Hz</strong></div>
                                <div><span class="vg-spec-hud-lbl">BAND:</span> <strong id="hud-band">#0 / 40</strong></div>
                                <div><span class="vg-spec-hud-lbl">POWER:</span> <strong id="hud-db">0.0 dB</strong></div>
                            </div>
                        </div>

                        <!-- Empty State Overlay -->
                        <div class="vg-spec-overlay vg-spec-overlay-empty" id="vg-spec-empty-overlay">
                            <div class="vg-spec-empty-icon">
                                <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                                    <path d="M2 10v3M6 6v11M10 3v18M14 8v7M18 5v13M22 10v4"/>
                                </svg>
                            </div>
                            <h4>Awaiting Audio Analysis</h4>
                            <p>Upload a file or record audio to compute the 2D Log-Mel Spectrogram matrix.</p>
                        </div>

                        <!-- Loading State Overlay -->
                        <div class="vg-spec-overlay vg-spec-overlay-loading" id="vg-spec-loading-overlay" style="display: none;">
                            <div class="vg-spec-spinner"></div>
                            <h4>Extracting Acoustic Spectrogram</h4>
                            <p id="vg-spec-loading-message">Computing 512-point STFT and 40-band Mel filterbanks...</p>
                        </div>

                        <!-- Error State Overlay -->
                        <div class="vg-spec-overlay vg-spec-overlay-error" id="vg-spec-error-overlay" style="display: none;">
                            <div class="vg-spec-error-icon">&times;</div>
                            <h4>Spectrogram Extraction Failed</h4>
                            <p id="vg-spec-error-message">Unable to render spectrogram matrix.</p>
                        </div>
                    </div>

                    <!-- Bottom Status Bar -->
                    <div class="vg-spec-footer">
                        <div class="vg-spec-footer-left">
                            <span class="vg-spec-footer-tag">FFT: 512</span>
                            <span class="vg-spec-footer-tag">HOP: 160 (10ms)</span>
                            <span class="vg-spec-footer-tag">MEL RANGE: 0 - 8000 Hz</span>
                            <span class="vg-spec-footer-tag">DYNAMIC RANGE: 80 dB</span>
                        </div>
                        <div class="vg-spec-footer-right">
                            <span id="vg-spec-scrubber-hint">Click spectrogram to seek audio playback &bull; Drag horizontally to pan</span>
                        </div>
                    </div>
                </div>
            `;

            // Cache element references
            this.canvas = this.container.querySelector('#vg-spec-canvas');
            this.ctx = this.canvas.getContext('2d');
            this.wrapper = this.container.querySelector('#vg-spec-canvas-wrapper');
            this.hudTooltip = this.container.querySelector('#vg-spec-hud-tooltip');
            this.emptyOverlay = this.container.querySelector('#vg-spec-empty-overlay');
            this.loadingOverlay = this.container.querySelector('#vg-spec-loading-overlay');
            this.errorOverlay = this.container.querySelector('#vg-spec-error-overlay');
            this.loadingMessageEl = this.container.querySelector('#vg-spec-loading-message');
            this.errorMessageEl = this.container.querySelector('#vg-spec-error-message');
            this.frameCountEl = this.container.querySelector('#vg-spec-frame-count');
            this.zoomIndicatorEl = this.container.querySelector('#vg-spec-zoom-indicator');

            // HUD fields
            this.hudTime = this.container.querySelector('#hud-time');
            this.hudFreq = this.container.querySelector('#hud-freq');
            this.hudBand = this.container.querySelector('#hud-band');
            this.hudDb = this.container.querySelector('#hud-db');

            // Controls
            this.colormapSelect = this.container.querySelector('#vg-spec-colormap-select');
            this.btnZoomIn = this.container.querySelector('#vg-spec-btn-zoom-in');
            this.btnZoomOut = this.container.querySelector('#vg-spec-btn-zoom-out');
            this.btnZoomReset = this.container.querySelector('#vg-spec-btn-zoom-reset');
        }

        // =====================================================================
        // EVENT BINDINGS
        // =====================================================================

        _bindEvents() {
            // Colormap change
            if (this.colormapSelect) {
                this.colormapSelect.addEventListener('change', (e) => {
                    this.setColormap(e.target.value);
                });
            }

            // Zoom controls
            if (this.btnZoomIn) {
                this.btnZoomIn.addEventListener('click', () => this.zoomIn());
            }
            if (this.btnZoomOut) {
                this.btnZoomOut.addEventListener('click', () => this.zoomOut());
            }
            if (this.btnZoomReset) {
                this.btnZoomReset.addEventListener('click', () => this.resetZoom());
            }

            // Canvas Mouse Interactions
            this.canvas.addEventListener('mousemove', (e) => this._onMouseMove(e));
            this.canvas.addEventListener('mouseleave', () => this._onMouseLeave());
            this.canvas.addEventListener('mousedown', (e) => this._onMouseDown(e));
            window.addEventListener('mouseup', () => this._onMouseUp());
            this.canvas.addEventListener('click', (e) => this._onClick(e));
            this.canvas.addEventListener('wheel', (e) => this._onWheel(e), { passive: false });

            // Touch support
            this.canvas.addEventListener('touchstart', (e) => this._onTouchStart(e), { passive: true });
            this.canvas.addEventListener('touchmove', (e) => this._onTouchMove(e), { passive: true });
            this.canvas.addEventListener('touchend', () => this._onMouseUp());
        }

        _observeResize() {
            if (window.ResizeObserver && this.wrapper) {
                this.resizeObserver = new ResizeObserver(() => {
                    if (this.state === 'ready') {
                        this.render();
                    }
                });
                this.resizeObserver.observe(this.wrapper);
            }
        }

        // =====================================================================
        // PUBLIC API
        // =====================================================================

        /**
         * Loads backend spectrogram payload and binds audio player.
         * @param {Object} specData - Structured spectrogram matrix from backend
         * @param {HTMLAudioElement} [audioEl] - Audio player element to synchronize with
         */
        loadData(specData, audioEl = null) {
            if (!specData || !Array.isArray(specData.matrix) || specData.matrix.length === 0) {
                this.setError('Spectrogram matrix payload is empty or invalid.');
                return;
            }

            this.data = specData;
            this.state = 'ready';
            this.errorMessage = '';

            // Setup viewport boundaries — strictly 1.0x full audio view at initial load
            const duration = Math.max(0.1, Number(specData.duration_seconds) || 1.0);
            this.viewStartSec = 0.0;
            this.viewEndSec = duration;
            this.zoomLevel = 1.0;
            if (this.zoomIndicatorEl) this.zoomIndicatorEl.textContent = '1.0x';
            this._updateZoomButtonStates();

            // Update UI count
            if (this.frameCountEl) {
                const totalFrames = specData.num_frames || specData.matrix.length;
                this.frameCountEl.textContent = `${totalFrames} frames &bull; ${duration.toFixed(2)}s`;
            }

            // Bind audio element
            this.bindAudioElement(audioEl);

            // Pre-render the full offscreen matrix image buffer
            this._renderOffscreenMatrix();

            // Hide overlays and draw
            this._showOverlay(null);
            this.render();
        }

        /**
         * Binds an HTML5 audio element for synchronized playhead scrubber & seek.
         */
        bindAudioElement(audioEl) {
            if (this.audioElement) {
                this._unbindAudioEvents();
            }
            this.audioElement = audioEl;
            if (this.audioElement) {
                this._bindAudioEvents();
            }
        }

        _bindAudioEvents() {
            if (!this.audioElement) return;

            this._onTimeUpdate = () => {
                if (this.state === 'ready') {
                    this.currentPlayheadSec = this.audioElement.currentTime;
                    this.renderOverlayOnly();
                }
            };

            this._onPlayPause = () => {
                if (this.state === 'ready') {
                    this.currentPlayheadSec = this.audioElement.currentTime;
                    this.renderOverlayOnly();
                }
            };

            this.audioElement.addEventListener('timeupdate', this._onTimeUpdate);
            this.audioElement.addEventListener('seeking', this._onTimeUpdate);
            this.audioElement.addEventListener('seeked', this._onTimeUpdate);
            this.audioElement.addEventListener('play', this._onPlayPause);
            this.audioElement.addEventListener('pause', this._onPlayPause);
            this.audioElement.addEventListener('ended', this._onPlayPause);
        }

        _unbindAudioEvents() {
            if (!this.audioElement) return;
            if (this._onTimeUpdate) {
                this.audioElement.removeEventListener('timeupdate', this._onTimeUpdate);
                this.audioElement.removeEventListener('seeking', this._onTimeUpdate);
                this.audioElement.removeEventListener('seeked', this._onTimeUpdate);
            }
            if (this._onPlayPause) {
                this.audioElement.removeEventListener('play', this._onPlayPause);
                this.audioElement.removeEventListener('pause', this._onPlayPause);
                this.audioElement.removeEventListener('ended', this._onPlayPause);
            }
            this.audioElement = null;
        }

        setColormap(name) {
            if (COLORMAPS[name]) {
                this.colormapName = name;
                if (this.state === 'ready') {
                    this._renderOffscreenMatrix();
                    this.render();
                }
            }
        }

        /**
         * Sets zoom level strictly bounded between 1.0x (full view) and 8.0x (max zoom).
         * @param {number} targetZoom - Desired zoom magnification
         * @param {number} centerRatio - Viewport pivot anchor (0.0 to 1.0, default 0.5 center)
         */
        setZoom(targetZoom, centerRatio = 0.5) {
            if (this.state !== 'ready' || !this.data) return;
            const totalDuration = Math.max(0.1, Number(this.data.duration_seconds) || 1.0);

            // Strict clamping: Minimum 1.0x, Maximum 8.0x
            const clampedZoom = Math.max(1.0, Math.min(8.0, targetZoom));
            this.zoomLevel = Math.round(clampedZoom * 10) / 10;

            if (this.zoomLevel <= 1.001) {
                // Exact 1.0x: Entire audio duration is visible
                this.zoomLevel = 1.0;
                this.viewStartSec = 0.0;
                this.viewEndSec = totalDuration;
            } else {
                const newSpan = totalDuration / this.zoomLevel;
                const currentSpan = this.viewEndSec - this.viewStartSec;
                const centerTime = this.viewStartSec + currentSpan * centerRatio;

                let newStart = centerTime - newSpan * centerRatio;
                let newEnd = newStart + newSpan;

                if (newStart < 0) {
                    newStart = 0;
                    newEnd = Math.min(totalDuration, newSpan);
                }
                if (newEnd > totalDuration) {
                    newEnd = totalDuration;
                    newStart = Math.max(0, totalDuration - newSpan);
                }

                this.viewStartSec = Math.max(0, newStart);
                this.viewEndSec = Math.min(totalDuration, newEnd);
            }

            if (this.zoomIndicatorEl) {
                this.zoomIndicatorEl.textContent = `${this.zoomLevel.toFixed(1)}x`;
            }

            this._updateZoomButtonStates();
            this.render();
        }

        zoomIn(factor = 1.3) {
            if (this.state !== 'ready' || !this.data) return;
            this.setZoom(this.zoomLevel * factor);
        }

        zoomOut(factor = 1.3) {
            if (this.state !== 'ready' || !this.data) return;
            this.setZoom(this.zoomLevel / factor);
        }

        resetZoom() {
            if (this.state !== 'ready' || !this.data) return;
            this.setZoom(1.0);
        }

        _updateZoomButtonStates() {
            if (this.btnZoomOut) {
                const isMin = this.zoomLevel <= 1.001;
                this.btnZoomOut.disabled = isMin;
                this.btnZoomOut.style.opacity = isMin ? '0.35' : '1';
                this.btnZoomOut.style.cursor = isMin ? 'not-allowed' : 'pointer';
            }
            if (this.btnZoomIn) {
                const isMax = this.zoomLevel >= 7.999;
                this.btnZoomIn.disabled = isMax;
                this.btnZoomIn.style.opacity = isMax ? '0.35' : '1';
                this.btnZoomIn.style.cursor = isMax ? 'not-allowed' : 'pointer';
            }
            if (this.btnZoomReset) {
                const isZoomed = this.zoomLevel > 1.001;
                this.btnZoomReset.style.opacity = isZoomed ? '1' : '0.65';
                this.btnZoomReset.style.boxShadow = isZoomed ? '0 0 10px rgba(0, 242, 254, 0.35)' : 'none';
            }
        }

        setLoading(message = 'Extracting 40-band Log-Mel Spectrogram via 512-point STFT...') {
            this.state = 'loading';
            if (this.loadingMessageEl) this.loadingMessageEl.textContent = message;
            this._showOverlay('loading');
        }

        setError(message = 'Failed to extract or render spectrogram matrix.') {
            this.state = 'error';
            this.errorMessage = message;
            if (this.errorMessageEl) this.errorMessageEl.textContent = message;
            this._showOverlay('error');
        }

        setEmpty() {
            this.state = 'empty';
            this.data = null;
            this._showOverlay('empty');
            this._clearCanvas();
        }

        clear() {
            this.setEmpty();
        }

        _showOverlay(which) {
            if (this.emptyOverlay) this.emptyOverlay.style.display = which === 'empty' ? 'flex' : 'none';
            if (this.loadingOverlay) this.loadingOverlay.style.display = which === 'loading' ? 'flex' : 'none';
            if (this.errorOverlay) this.errorOverlay.style.display = which === 'error' ? 'flex' : 'none';
            if (this.hudTooltip) this.hudTooltip.style.display = 'none';
        }

        _clearCanvas() {
            if (!this.canvas || !this.ctx) return;
            const dpr = window.devicePixelRatio || 1;
            const w = this.canvas.width / dpr;
            const h = this.canvas.height / dpr;
            this.ctx.clearRect(0, 0, w, h);
        }

        // =====================================================================
        // OFFSCREEN MATRIX HEATMAP GENERATOR
        // =====================================================================

        _renderOffscreenMatrix() {
            if (!this.data || !Array.isArray(this.data.matrix)) return;
            const matrix = this.data.matrix;
            const numFrames = matrix.length;
            const numMels = this.data.num_mels || (matrix[0] ? matrix[0].length : 40);

            if (numFrames === 0 || numMels === 0) return;

            // Set offscreen canvas dimension to matrix resolution [numFrames x numMels]
            this.offscreenCanvas.width = numFrames;
            this.offscreenCanvas.height = numMels;

            const imgData = this.offscreenCtx.createImageData(numFrames, numMels);
            const pixels = imgData.data;
            const lut = COLORMAPS[this.colormapName] || COLORMAPS.cyberpunk;

            const minDb = this.options.minDb;
            const maxDb = this.options.maxDb;
            const dbRange = (maxDb - minDb) || 80.0;

            // Notice: Mel band 0 is lowest frequency (bottom).
            // Image coordinates (0, 0) are top-left, so we flip the Y-axis so band 0 is at bottom!
            for (let f = 0; f < numFrames; f++) {
                const frameBands = matrix[f];
                for (let m = 0; m < numMels; m++) {
                    const db = frameBands ? frameBands[m] : minDb;
                    // Normalized intensity: 0.0 (minDb) to 1.0 (maxDb)
                    const norm = Math.max(0.0, Math.min(1.0, (db - minDb) / dbRange));
                    const lutIdx = Math.floor(norm * 255.0);

                    // Flip Y: top pixel is highest band (numMels - 1 - m), bottom pixel is band 0
                    const y = (numMels - 1) - m;
                    const pixelIdx = (y * numFrames + f) * 4;

                    pixels[pixelIdx + 0] = lut[lutIdx * 3 + 0];
                    pixels[pixelIdx + 1] = lut[lutIdx * 3 + 1];
                    pixels[pixelIdx + 2] = lut[lutIdx * 3 + 2];
                    pixels[pixelIdx + 3] = 255;
                }
            }

            this.offscreenCtx.putImageData(imgData, 0, 0);
        }

        // =====================================================================
        // CORE RENDERING ENGINE (SHARP HIGH-DPI CANVAS)
        // =====================================================================

        _getPlotDimensions() {
            const rect = this.wrapper.getBoundingClientRect();
            const width = Math.max(300, rect.width || this.wrapper.clientWidth || 700);
            const height = this.options.height;
            const dpr = window.devicePixelRatio || 1;

            const gl = this.options.gutterLeft;
            const gr = this.options.gutterRight;
            const gt = this.options.gutterTop;
            const gb = this.options.gutterBottom;

            const plotX = gl;
            const plotY = gt;
            const plotW = Math.max(100, width - gl - gr);
            const plotH = Math.max(80, height - gt - gb);

            return { width, height, dpr, plotX, plotY, plotW, plotH, gl, gr, gt, gb };
        }

        render() {
            if (this.state !== 'ready' || !this.data) return;

            // Viewport boundary validation
            const totalDuration = Math.max(0.1, Number(this.data.duration_seconds) || 1.0);
            if (this.zoomLevel <= 1.001) {
                this.zoomLevel = 1.0;
                this.viewStartSec = 0.0;
                this.viewEndSec = totalDuration;
            } else {
                const span = this.viewEndSec - this.viewStartSec;
                if (this.viewStartSec < 0) {
                    this.viewStartSec = 0.0;
                    this.viewEndSec = Math.min(totalDuration, span);
                }
                if (this.viewEndSec > totalDuration) {
                    this.viewEndSec = totalDuration;
                    this.viewStartSec = Math.max(0.0, totalDuration - span);
                }
            }

            const dims = this._getPlotDimensions();
            const { width, height, dpr, plotX, plotY, plotW, plotH } = dims;

            // Set physical canvas pixels with DPR scaling
            this.canvas.width = Math.round(width * dpr);
            this.canvas.height = Math.round(height * dpr);
            this.canvas.style.width = `${width}px`;
            this.canvas.style.height = `${height}px`;

            this.ctx.save();
            this.ctx.scale(dpr, dpr);

            // 1. Draw Background
            this.ctx.fillStyle = '#060b17';
            this.ctx.fillRect(0, 0, width, height);

            // 2. Draw Heatmap Matrix from Offscreen Buffer
            this._drawHeatmap(dims);

            // 3. Draw Axes, Grid Lines & Ticks
            this._drawAxes(dims);

            // 4. Draw Decibel Colorbar Legend
            this._drawColorbar(dims);

            // 5. Draw Overlays: Playhead, Crosshair, and Tooltip
            this._drawDynamicOverlays(dims);

            this.ctx.restore();
        }

        renderOverlayOnly() {
            // For smooth 60 FPS playhead & crosshair updates without re-generating full matrix
            this.render();
        }

        _drawHeatmap(dims) {
            const { plotX, plotY, plotW, plotH } = dims;
            const totalDuration = this.data.duration_seconds || 1.0;
            const numFrames = this.offscreenCanvas.width;
            const numMels = this.offscreenCanvas.height;

            if (numFrames === 0 || numMels === 0) return;

            // Calculate source slice based on viewStartSec & viewEndSec
            const startFrac = Math.max(0, this.viewStartSec / totalDuration);
            const endFrac = Math.min(1, this.viewEndSec / totalDuration);

            const sx = Math.floor(startFrac * numFrames);
            const sw = Math.max(1, Math.ceil((endFrac - startFrac) * numFrames));
            const sy = 0;
            const sh = numMels;

            // Configure smoothing: imageSmoothingEnabled = false gives authentic pixel precision
            this.ctx.imageSmoothingEnabled = true;
            this.ctx.imageSmoothingQuality = 'high';

            // Draw slice
            this.ctx.drawImage(
                this.offscreenCanvas,
                sx, sy, sw, sh,
                plotX, plotY, plotW, plotH
            );

            // Plot boundary border
            this.ctx.strokeStyle = 'rgba(0, 242, 254, 0.35)';
            this.ctx.lineWidth = 1;
            this.ctx.strokeRect(plotX, plotY, plotW, plotH);
        }

        _drawAxes(dims) {
            const { plotX, plotY, plotW, plotH, gl, gt, gb } = dims;

            this.ctx.font = '10px "JetBrains Mono", Consolas, monospace';
            this.ctx.fillStyle = '#94a3b8';
            this.ctx.textAlign = 'right';
            this.ctx.textBaseline = 'middle';

            // -----------------------------------------------------------------
            // Y-Axis: Frequency Labels (Hz) along Mel Scale
            // -----------------------------------------------------------------
            const targetFreqs = [0, 500, 1000, 2000, 4000, 8000];
            const fMax = this.data.f_max || 8000;
            const maxMel = 2595.0 * Math.log10(1.0 + fMax / 700.0);

            targetFreqs.forEach((freq) => {
                const mel = 2595.0 * Math.log10(1.0 + freq / 700.0);
                const normMel = mel / maxMel;
                // Invert Y: 0 Hz is bottom (plotY + plotH), 8000 Hz is top (plotY)
                const y = plotY + (1.0 - normMel) * plotH;

                // Subtle grid line
                this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
                this.ctx.lineWidth = 1;
                this.ctx.setLineDash([2, 4]);
                this.ctx.beginPath();
                this.ctx.moveTo(plotX, y);
                this.ctx.lineTo(plotX + plotW, y);
                this.ctx.stroke();
                this.ctx.setLineDash([]);

                // Frequency label
                const label = freq >= 1000 ? `${freq / 1000}k` : `${freq}`;
                this.ctx.fillStyle = '#64748b';
                this.ctx.fillText(`${label} Hz`, plotX - 8, y);
            });

            // Y-Axis Title (Rotated vertical)
            this.ctx.save();
            this.ctx.translate(14, plotY + plotH / 2);
            this.ctx.rotate(-Math.PI / 2);
            this.ctx.textAlign = 'center';
            this.ctx.font = '10px "JetBrains Mono", Consolas, monospace';
            this.ctx.fillStyle = '#00f2fe';
            this.ctx.fillText('FREQUENCY (Hz) &bull; MEL SCALE', 0, 0);
            this.ctx.restore();

            // -----------------------------------------------------------------
            // X-Axis: Time Labels (Seconds)
            // -----------------------------------------------------------------
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'top';

            const span = this.viewEndSec - this.viewStartSec;
            const numTimeTicks = Math.max(3, Math.min(10, Math.floor(plotW / 90)));
            const stepSec = span / (numTimeTicks - 1);

            for (let i = 0; i < numTimeTicks; i++) {
                const t = this.viewStartSec + i * stepSec;
                const normX = i / (numTimeTicks - 1);
                const x = plotX + normX * plotW;

                // Vertical grid line
                this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
                this.ctx.lineWidth = 1;
                this.ctx.setLineDash([2, 4]);
                this.ctx.beginPath();
                this.ctx.moveTo(x, plotY);
                this.ctx.lineTo(x, plotY + plotH);
                this.ctx.stroke();
                this.ctx.setLineDash([]);

                // Tick mark
                this.ctx.strokeStyle = '#00f2fe';
                this.ctx.beginPath();
                this.ctx.moveTo(x, plotY + plotH);
                this.ctx.lineTo(x, plotY + plotH + 4);
                this.ctx.stroke();

                // Label
                this.ctx.fillStyle = '#94a3b8';
                this.ctx.fillText(`${t.toFixed(2)}s`, x, plotY + plotH + 8);
            }

            // X-Axis Title
            this.ctx.textAlign = 'center';
            this.ctx.fillStyle = '#00f2fe';
            this.ctx.fillText('TIME (SECONDS)', plotX + plotW / 2, plotY + plotH + 20);
        }

        _drawColorbar(dims) {
            const { plotX, plotY, plotW, plotH, width } = dims;
            const barW = 12;
            const barX = plotX + plotW + 14;
            const barY = plotY;
            const barH = plotH;

            // Draw colorbar gradient using active colormap LUT
            const lut = COLORMAPS[this.colormapName] || COLORMAPS.cyberpunk;
            for (let y = 0; y < barH; y++) {
                // Top (y=0) is 0 dB (loudest), bottom (y=barH) is -80 dB (quietest)
                const norm = 1.0 - (y / barH);
                const lutIdx = Math.floor(norm * 255.0);
                this.ctx.fillStyle = `rgb(${lut[lutIdx * 3 + 0]}, ${lut[lutIdx * 3 + 1]}, ${lut[lutIdx * 3 + 2]})`;
                this.ctx.fillRect(barX, barY + y, barW, 1);
            }

            // Colorbar border
            this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
            this.ctx.strokeRect(barX, barY, barW, barH);

            // Decibel Ticks
            const dbTicks = [0, -20, -40, -60, -80];
            this.ctx.font = '9px "JetBrains Mono", Consolas, monospace';
            this.ctx.textAlign = 'left';
            this.ctx.textBaseline = 'middle';

            dbTicks.forEach((db) => {
                const norm = (db - this.options.minDb) / (this.options.maxDb - this.options.minDb);
                const y = barY + (1.0 - norm) * barH;

                this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
                this.ctx.beginPath();
                this.ctx.moveTo(barX + barW, y);
                this.ctx.lineTo(barX + barW + 3, y);
                this.ctx.stroke();

                this.ctx.fillStyle = '#94a3b8';
                this.ctx.fillText(`${db} dB`, barX + barW + 6, y);
            });
        }

        _drawDynamicOverlays(dims) {
            const { plotX, plotY, plotW, plotH } = dims;

            // -----------------------------------------------------------------
            // A. Audio Playhead Line (Synced to <audio> playback)
            // -----------------------------------------------------------------
            if (this.currentPlayheadSec >= this.viewStartSec && this.currentPlayheadSec <= this.viewEndSec) {
                const playFrac = (this.currentPlayheadSec - this.viewStartSec) / (this.viewEndSec - this.viewStartSec);
                const playX = plotX + playFrac * plotW;

                // Glowing Playhead Line
                this.ctx.save();
                this.ctx.shadowColor = '#00f2fe';
                this.ctx.shadowBlur = 8;
                this.ctx.strokeStyle = '#00f2fe';
                this.ctx.lineWidth = 2;
                this.ctx.beginPath();
                this.ctx.moveTo(playX, plotY);
                this.ctx.lineTo(playX, plotY + plotH);
                this.ctx.stroke();

                // Playhead Top Pointer Tag
                this.ctx.fillStyle = '#00f2fe';
                this.ctx.beginPath();
                this.ctx.moveTo(playX - 4, plotY);
                this.ctx.lineTo(playX + 4, plotY);
                this.ctx.lineTo(playX, plotY + 6);
                this.ctx.closePath();
                this.ctx.fill();
                this.ctx.restore();
            }

            // -----------------------------------------------------------------
            // B. Interactive Hover Crosshairs
            // -----------------------------------------------------------------
            if (this.isHovering && this.hoverPos) {
                const hx = this.hoverPos.x;
                const hy = this.hoverPos.y;

                if (hx >= plotX && hx <= plotX + plotW && hy >= plotY && hy <= plotY + plotH) {
                    this.ctx.save();
                    this.ctx.strokeStyle = 'rgba(0, 242, 254, 0.65)';
                    this.ctx.lineWidth = 1;
                    this.ctx.setLineDash([3, 3]);

                    // Vertical reticle line
                    this.ctx.beginPath();
                    this.ctx.moveTo(hx, plotY);
                    this.ctx.lineTo(hx, plotY + plotH);
                    this.ctx.stroke();

                    // Horizontal reticle line
                    this.ctx.beginPath();
                    this.ctx.moveTo(plotX, hy);
                    this.ctx.lineTo(plotX + plotW, hy);
                    this.ctx.stroke();
                    this.ctx.restore();

                    // Center crosshair ring
                    this.ctx.strokeStyle = '#00f2fe';
                    this.ctx.beginPath();
                    this.ctx.arc(hx, hy, 4, 0, Math.PI * 2);
                    this.ctx.stroke();
                }
            }
        }

        // =====================================================================
        // INTERACTIVE MOUSE / TOUCH INSPECTION & SCRUBBER
        // =====================================================================

        _getCanvasCoords(e) {
            const rect = this.canvas.getBoundingClientRect();
            return {
                x: e.clientX - rect.left,
                y: e.clientY - rect.top,
            };
        }

        _onMouseMove(e) {
            if (this.state !== 'ready' || !this.data) return;

            const coords = this._getCanvasCoords(e);
            this.hoverPos = coords;
            this.isHovering = true;

            const dims = this._getPlotDimensions();
            const { plotX, plotY, plotW, plotH } = dims;

            // Handle Drag Pan
            if (this.isDragging) {
                if (this.zoomLevel <= 1.001) {
                    return; // No panning at 1.0x (full view)
                }
                const dx = coords.x - this.dragStartX;
                const totalDuration = Math.max(0.1, Number(this.data.duration_seconds) || 1.0);
                const span = this.viewEndSec - this.viewStartSec;
                const timeShift = -(dx / plotW) * span;

                let newStart = this.dragStartViewStart + timeShift;
                let newEnd = newStart + span;

                if (newStart < 0) {
                    newStart = 0;
                    newEnd = span;
                }
                if (newEnd > totalDuration) {
                    newEnd = totalDuration;
                    newStart = Math.max(0, totalDuration - span);
                }

                this.viewStartSec = Math.max(0, newStart);
                this.viewEndSec = Math.min(totalDuration, newEnd);
                this.render();
                return;
            }

            // Inside Heatmap: Update Cyber HUD Tooltip & Dynamic Cursor
            if (coords.x >= plotX && coords.x <= plotX + plotW && coords.y >= plotY && coords.y <= plotY + plotH) {
                this.canvas.style.cursor = this.zoomLevel > 1.001 ? 'grab' : 'crosshair';
                this._updateHudTooltip(coords, dims);
                this.renderOverlayOnly();
            } else {
                this.canvas.style.cursor = 'default';
                this._hideHudTooltip();
                this.renderOverlayOnly();
            }
        }

        _onMouseLeave() {
            this.isHovering = false;
            this.isDragging = false;
            this.canvas.style.cursor = 'default';
            this._hideHudTooltip();
            if (this.state === 'ready') {
                this.renderOverlayOnly();
            }
        }

        _onMouseDown(e) {
            if (this.state !== 'ready' || !this.data) return;
            const coords = this._getCanvasCoords(e);
            const dims = this._getPlotDimensions();

            if (coords.x >= dims.plotX && coords.x <= dims.plotX + dims.plotW &&
                coords.y >= dims.plotY && coords.y <= dims.plotY + dims.plotH) {
                if (this.zoomLevel > 1.001) {
                    this.isDragging = true;
                    this.dragStartX = coords.x;
                    this.dragStartViewStart = this.viewStartSec;
                    this.canvas.style.cursor = 'grabbing';
                }
            }
        }

        _onMouseUp() {
            if (this.isDragging) {
                this.isDragging = false;
                this.canvas.style.cursor = this.zoomLevel > 1.001 ? 'grab' : 'crosshair';
            }
        }

        _onClick(e) {
            if (this.state !== 'ready' || !this.data) return;
            const coords = this._getCanvasCoords(e);
            const dims = this._getPlotDimensions();
            const { plotX, plotY, plotW, plotH } = dims;

            // Click within heatmap seeks audio playback
            if (coords.x >= plotX && coords.x <= plotX + plotW && coords.y >= plotY && coords.y <= plotY + plotH) {
                const normX = (coords.x - plotX) / plotW;
                const targetSec = this.viewStartSec + normX * (this.viewEndSec - this.viewStartSec);

                if (this.audioElement) {
                    this.audioElement.currentTime = targetSec;
                    this.currentPlayheadSec = targetSec;
                    this.renderOverlayOnly();
                }
            }
        }

        _onWheel(e) {
            if (this.state !== 'ready' || !this.data) return;
            const coords = this._getCanvasCoords(e);
            const dims = this._getPlotDimensions();

            if (coords.x >= dims.plotX && coords.x <= dims.plotX + dims.plotW &&
                coords.y >= dims.plotY && coords.y <= dims.plotY + dims.plotH) {
                e.preventDefault();
                const centerRatio = (coords.x - dims.plotX) / dims.plotW;
                // Gentle delta: 0.25x zoom increment per wheel tick, strictly clamped
                const zoomDelta = -Math.sign(e.deltaY) * 0.25;
                this.setZoom(this.zoomLevel + zoomDelta, centerRatio);
            }
        }

        _onTouchStart(e) {
            if (e.touches && e.touches[0]) {
                const touch = e.touches[0];
                this._onMouseDown({ clientX: touch.clientX, clientY: touch.clientY });
            }
        }

        _onTouchMove(e) {
            if (e.touches && e.touches[0]) {
                const touch = e.touches[0];
                this._onMouseMove({ clientX: touch.clientX, clientY: touch.clientY });
            }
        }

        _updateHudTooltip(coords, dims) {
            if (!this.hudTooltip || !this.data) return;

            const { plotX, plotY, plotW, plotH } = dims;
            const normX = (coords.x - plotX) / plotW;
            const normY = 1.0 - ((coords.y - plotY) / plotH); // 0 at bottom, 1 at top

            const currentSec = this.viewStartSec + normX * (this.viewEndSec - this.viewStartSec);
            const totalDuration = this.data.duration_seconds || 1.0;
            const matrix = this.data.matrix;
            const numFrames = matrix.length;
            const numMels = this.data.num_mels || 40;

            // Find closest frame and Mel band
            const frameIndex = Math.max(0, Math.min(numFrames - 1, Math.floor((currentSec / totalDuration) * numFrames)));
            const melBandIndex = Math.max(0, Math.min(numMels - 1, Math.floor(normY * numMels)));

            // Frequency lookup
            const melFreqs = this.data.mel_frequencies || [];
            const freqHz = melFreqs[melBandIndex] !== undefined ? melFreqs[melBandIndex] : Math.round(normY * 8000);

            // Intensity dB
            const frame = matrix[frameIndex];
            const dbVal = frame && frame[melBandIndex] !== undefined ? frame[melBandIndex] : -80.0;

            // Update DOM text
            if (this.hudTime) this.hudTime.textContent = `${currentSec.toFixed(2)}s`;
            if (this.hudFreq) this.hudFreq.textContent = `${Math.round(freqHz)} Hz`;
            if (this.hudBand) this.hudBand.textContent = `#${melBandIndex + 1} / ${numMels}`;
            if (this.hudDb) {
                this.hudDb.textContent = `${dbVal.toFixed(1)} dB`;
                this.hudDb.style.color = dbVal >= -20 ? '#00f2fe' : (dbVal >= -50 ? '#f59e0b' : '#94a3b8');
            }

            // Position Tooltip with boundary clamping
            const tooltipW = 210;
            const tooltipH = 75;
            let left = coords.x + 18;
            let top = coords.y - tooltipH / 2;

            if (left + tooltipW > dims.width - 20) {
                left = coords.x - tooltipW - 18;
            }
            if (top < 10) top = 10;
            if (top + tooltipH > dims.height - 10) top = dims.height - tooltipH - 10;

            this.hudTooltip.style.left = `${left}px`;
            this.hudTooltip.style.top = `${top}px`;
            this.hudTooltip.style.display = 'block';
        }

        _hideHudTooltip() {
            if (this.hudTooltip) {
                this.hudTooltip.style.display = 'none';
            }
        }

        destroy() {
            this._unbindAudioEvents();
            if (this.resizeObserver) {
                this.resizeObserver.disconnect();
            }
            if (this.container) {
                this.container.innerHTML = '';
            }
        }
    }

    // Export to global namespace
    window.LogMelSpectrogramViewer = LogMelSpectrogramViewer;

})(window, document);
