/**
 * Node.js automated verification for 2D Log-Mel Spectrogram Zoom & Timeline
 * Tests with 95.472s audio duration.
 */

const fs = require('fs');
const path = require('path');

// Minimal mock DOM for node testing
class MockElement {
    constructor(id = '', tag = 'div') {
        this.id = id;
        this.tagName = tag;
        this.style = {};
        this.textContent = '';
        this.innerHTML = '';
        this.children = [];
        this.disabled = false;
        this.listeners = {};
    }

    querySelector(selector) {
        if (selector.startsWith('#')) {
            const targetId = selector.substring(1);
            return this.findElementById(targetId);
        }
        return new MockElement();
    }

    findElementById(id) {
        if (this.id === id) return this;
        for (const child of this.children) {
            if (child.id === id) return child;
            if (child.findElementById) {
                const found = child.findElementById(id);
                if (found) return found;
            }
        }
        // Return a mock child if not explicitly structured
        const mockChild = new MockElement(id);
        this.children.push(mockChild);
        return mockChild;
    }

    addEventListener(event, fn) {
        if (!this.listeners[event]) this.listeners[event] = [];
        this.listeners[event].push(fn);
    }

    removeEventListener(event, fn) {
        if (this.listeners[event]) {
            this.listeners[event] = this.listeners[event].filter(f => f !== fn);
        }
    }

    getBoundingClientRect() {
        return { left: 0, top: 0, width: 800, height: 320, right: 800, bottom: 320 };
    }

    getContext() {
        return {
            save: () => {},
            restore: () => {},
            scale: () => {},
            translate: () => {},
            rotate: () => {},
            clearRect: () => {},
            fillRect: () => {},
            strokeRect: () => {},
            beginPath: () => {},
            closePath: () => {},
            moveTo: () => {},
            lineTo: () => {},
            arc: () => {},
            stroke: () => {},
            fill: () => {},
            fillText: () => {},
            createImageData: (w, h) => ({ data: new Uint8ClampedArray(w * h * 4) }),
            putImageData: () => {},
            drawImage: () => {},
            setLineDash: () => {},
        };
    }
}

// Global browser shims
global.window = {
    devicePixelRatio: 1,
    addEventListener: () => {},
    removeEventListener: () => {},
};
global.document = {
    createElement: (tag) => new MockElement('', tag),
    querySelector: (sel) => new MockElement(sel.replace('#', '')),
};
global.ResizeObserver = class {
    constructor(cb) { this.cb = cb; }
    observe() {}
    disconnect() {}
};

// Load spectrogram-viewer.js
const viewerPath = path.join(__dirname, '..', 'spectrogram-viewer.js');
const viewerCode = fs.readFileSync(viewerPath, 'utf8');
eval(viewerCode);

const LogMelSpectrogramViewer = global.window.LogMelSpectrogramViewer;
console.log('✓ LogMelSpectrogramViewer loaded successfully');

// Initialize viewer
const mockContainer = new MockElement('spectrogram-container');
const viewer = new LogMelSpectrogramViewer(mockContainer, { height: 320 });

// Mock 95.472s audio spectrogram payload
const testDuration = 95.472;
const numFrames = 600;
const mockMatrix = [];
for (let i = 0; i < numFrames; i++) {
    const frame = [];
    for (let m = 0; m < 40; m++) frame.push(-40.0);
    mockMatrix.push(frame);
}

const mockPayload = {
    matrix: mockMatrix,
    num_frames: numFrames,
    num_mels: 40,
    mel_frequencies: Array.from({ length: 40 }, (_, i) => 100 + i * 180),
    duration_seconds: testDuration,
    time_step_seconds: 0.1591,
    min_db: -80.0,
    max_db: 0.0,
    mean_db: -40.0,
};

// Test 1: Initial load
viewer.loadData(mockPayload);
console.log(`[TEST 1] Initial Zoom Level: ${viewer.zoomLevel}x`);
console.log(`[TEST 1] View Start: ${viewer.viewStartSec}s, View End: ${viewer.viewEndSec}s (Span: ${viewer.viewEndSec - viewer.viewStartSec}s)`);

if (viewer.zoomLevel !== 1.0) throw new Error(`Expected initial zoom 1.0x, got ${viewer.zoomLevel}x`);
if (Math.abs(viewer.viewStartSec - 0.0) > 0.001) throw new Error('Expected viewStartSec to be 0.0');
if (Math.abs(viewer.viewEndSec - testDuration) > 0.001) throw new Error(`Expected viewEndSec to be ${testDuration}`);
console.log('✓ TEST 1 PASSED: Initial zoom is strictly 1.0x and entire 95.472s timeline is visible.');

// Test 2: Rapid zoom-in (simulating mouse wheel or zoom button spam)
for (let i = 0; i < 50; i++) {
    viewer.zoomIn(1.3);
}
console.log(`[TEST 2] Max Zoom Level reached after 50 zoom-in calls: ${viewer.zoomLevel}x`);
console.log(`[TEST 2] View Window at Max Zoom: ${viewer.viewStartSec.toFixed(2)}s to ${viewer.viewEndSec.toFixed(2)}s (Span: ${(viewer.viewEndSec - viewer.viewStartSec).toFixed(2)}s)`);

if (viewer.zoomLevel > 8.0) throw new Error(`Max zoom exceeded! Got ${viewer.zoomLevel}x (must be <= 8.0x)`);
if (viewer.zoomLevel !== 8.0) throw new Error(`Expected zoom level to cap at 8.0x, got ${viewer.zoomLevel}x`);
const minSpan = testDuration / 8.0;
if (Math.abs((viewer.viewEndSec - viewer.viewStartSec) - minSpan) > 0.05) {
    throw new Error(`Expected window span at 8.0x to be ${minSpan.toFixed(2)}s, got ${(viewer.viewEndSec - viewer.viewStartSec).toFixed(2)}s`);
}
console.log('✓ TEST 2 PASSED: Strict 8.0x maximum zoom enforced. Never reaches 763.8x.');

// Test 3: Rapid zoom-out
for (let i = 0; i < 50; i++) {
    viewer.zoomOut(1.3);
}
console.log(`[TEST 3] Min Zoom Level reached after 50 zoom-out calls: ${viewer.zoomLevel}x`);
console.log(`[TEST 3] View Window at Min Zoom: ${viewer.viewStartSec.toFixed(2)}s to ${viewer.viewEndSec.toFixed(2)}s (Span: ${(viewer.viewEndSec - viewer.viewStartSec).toFixed(2)}s)`);

if (viewer.zoomLevel < 1.0) throw new Error(`Min zoom violated! Got ${viewer.zoomLevel}x (must be >= 1.0x)`);
if (viewer.zoomLevel !== 1.0) throw new Error(`Expected zoom level to cap at 1.0x, got ${viewer.zoomLevel}x`);
if (Math.abs(viewer.viewStartSec - 0.0) > 0.001 || Math.abs(viewer.viewEndSec - testDuration) > 0.001) {
    throw new Error('At 1.0x zoom, window must cover exact [0.0, 95.472]');
}
console.log('✓ TEST 3 PASSED: Strict 1.0x minimum zoom enforced. Timeline covers 100% of audio.');

// Test 4: Reset Zoom
viewer.setZoom(5.5);
console.log(`[TEST 4] Zoomed to intermediate: ${viewer.zoomLevel}x`);
viewer.resetZoom();
console.log(`[TEST 4] After resetZoom(): ${viewer.zoomLevel}x, Start: ${viewer.viewStartSec}s, End: ${viewer.viewEndSec}s`);
if (viewer.zoomLevel !== 1.0) throw new Error('resetZoom() failed to restore 1.0x');
if (Math.abs(viewer.viewEndSec - testDuration) > 0.001) throw new Error('resetZoom() failed to restore full timeline');
console.log('✓ TEST 4 PASSED: Reset Zoom restores 1.0x full view instantly.');

// Test 5: Drag Panning within valid audio boundaries
viewer.setZoom(2.0); // 2.0x zoom -> span is 47.736s
const halfSpan = testDuration / 2.0;

// Shift start to negative (should clamp to 0)
viewer.viewStartSec = -10.0;
viewer.viewEndSec = -10.0 + halfSpan;
viewer.render();
if (viewer.viewStartSec < 0) throw new Error('Left boundary clamp failed');

// Shift end beyond totalDuration (should clamp to totalDuration)
viewer.viewStartSec = testDuration - 10.0;
viewer.viewEndSec = testDuration + 20.0;
viewer.render();
if (viewer.viewEndSec > testDuration) throw new Error('Right boundary clamp failed');
console.log('✓ TEST 5 PASSED: Panning strictly bounded within [0.0, 95.472s].');

console.log('\n======================================================');
console.log('ALL SPECTROGRAM ZOOM & TIMELINE TESTS PASSED (100%)');
console.log('======================================================\n');
