/**
 * ============================================================================
 * VOICEGUARD AI — Cyber Acoustic Defense & Voice Biometrics
 * Client-side Controller (Vanilla JavaScript)
 *
 * Architecture:
 * 1. Global State & Sample Datasets
 * 2. Navigation & Single Page Routing
 * 3. Dashboard Overview & Chart Renderers
 * 4. Voice Forensics & Synthetic Audio Analysis (Web Audio Synth + Upload)
 * 5. Live Stream Monitoring & Oscilloscope Waveform Visualizer
 * 6. Zero-Trust Speaker Biometrics & Voiceprint Vault
 * 7. Threat Intelligence & Incident Table Search/Filter
 * 8. Reports, Compliance Audit & CSV Export Utilities
 * ============================================================================
 */

document.addEventListener('DOMContentLoaded', () => {
    'use strict';

    // ==========================================================================
    // 1. DATASETS & TELEMETRY (Clearly Labelled Sample UI Data)
    // ==========================================================================

    const SAMPLE_DATA = {
        // 24-Hour Telemetry Volume (for Overview Chart)
        hourlyTelemetry: [
            { hour: '00:00', total: 420, flagged: 18 },
            { hour: '03:00', total: 290, flagged: 12 },
            { hour: '06:00', total: 510, flagged: 22 },
            { hour: '09:00', total: 1150, flagged: 74 },
            { hour: '12:00', total: 1420, flagged: 96 },
            { hour: '15:00', total: 1380, flagged: 88 },
            { hour: '18:00', total: 980, flagged: 54 },
            { hour: '21:00', total: 640, flagged: 31 }
        ],

        // Threat Vector Distribution (for Analytics Donut Chart)
        riskDistribution: [
            { label: 'Diffusion Voice Cloning', count: 44, color: '#ef4444' },
            { label: 'Conversational TTS Agent', count: 28, color: '#f59e0b' },
            { label: 'Acoustic Replay Attack', count: 18, color: '#00e5ff' },
            { label: 'Pitch/Formant Perturbation', count: 10, color: '#8b5cf6' }
        ],

        // Weekly Channel Volume by Protocol (for Analytics Bar Chart)
        weeklyProtocolVolume: [
            { day: 'Mon', sip: 2100, webrtc: 920 },
            { day: 'Tue', sip: 2450, webrtc: 1050 },
            { day: 'Wed', sip: 2800, webrtc: 1200 },
            { day: 'Thu', sip: 2600, webrtc: 1140 },
            { day: 'Fri', sip: 2950, webrtc: 1380 },
            { day: 'Sat', sip: 1400, webrtc: 650 },
            { day: 'Sun', sip: 1100, webrtc: 520 }
        ],

        // Recent Intercepted Calls (Threat Intelligence Table)
        threatIncidents: [{
                id: 'VG-9082',
                timestamp: '2026-11-10 14:22:18 UTC',
                origin: '+1 (415) 890-3129 [Geo-Spoofed: Moscow, RU]',
                target: 'Chief Financial Officer (Line 01)',
                vector: 'ElevenLabs Latent Diffusion Clone',
                risk: 'Critical',
                confidence: '98.6%',
                action: 'Auto-Terminated & SIP Blacklisted',
                details: 'Attempted authorization of unauthorized $480,000 SWIFT wire transfer imitating executive timbre.'
            },
            {
                id: 'VG-9081',
                timestamp: '2026-11-10 13:58:04 UTC',
                origin: 'SIP/212.58.244.18 [Carrier Bypass: NL]',
                target: 'IT Helpdesk — Tier 2 Support',
                vector: 'Conversational TTS Social Engineering',
                risk: 'High',
                confidence: '91.2%',
                action: 'Quarantined / Operator Alerted',
                details: 'Automated interactive speech agent attempting master reset of corporate VPN MFA tokens.'
            },
            {
                id: 'VG-9080',
                timestamp: '2026-11-10 12:45:30 UTC',
                origin: '+44 20 7946 0912 [London Gateway 04]',
                target: 'Customer Accounts Escrow',
                vector: 'Acoustic Replay Attack (Stitched)',
                risk: 'Medium',
                confidence: '84.0%',
                action: 'MFA Step-Up Challenge Enforced',
                details: 'Pre-recorded fragments of authentic client voice spliced together with phase discontinuities.'
            },
            {
                id: 'VG-9079',
                timestamp: '2026-11-10 11:14:52 UTC',
                origin: '+1 (212) 555-0199 [VoIP Trunk East]',
                target: 'Mergers & Acquisitions Legal Desk',
                vector: 'Real-Time Neural Pitch Shifting',
                risk: 'High',
                confidence: '89.5%',
                action: 'Isolated to Sandbox Channel',
                details: 'Human voice modulated via real-time VST voice changer attempting impersonation of Managing Partner.'
            },
            {
                id: 'VG-9078',
                timestamp: '2026-11-10 09:31:16 UTC',
                origin: 'SIP/185.220.101.5 [Anonymous Tor Exit]',
                target: 'Treasury Operations Vault',
                vector: 'Zero-Shot Multi-Speaker Cloner',
                risk: 'Critical',
                confidence: '97.9%',
                action: 'Auto-Terminated & Gateway Blocked',
                details: 'Acoustic fingerprint matched known synthetic open-source Tortoise/XTTS model footprint.'
            },
            {
                id: 'VG-9077',
                timestamp: '2026-11-10 08:04:41 UTC',
                origin: '+81 3 5555 0143 [Tokyo Carrier Trunk]',
                target: 'HR Benefits & Payroll Portal',
                vector: 'Synthetic Vocoder Harmonic Glitch',
                risk: 'Medium',
                confidence: '78.5%',
                action: 'Logged for SOC Analyst Audit',
                details: 'Unnatural formant frequency ratio detected in phoneme transition /i:/ to /u:/.'
            },
            {
                id: 'VG-9076',
                timestamp: '2026-11-10 06:40:19 UTC',
                origin: '+49 30 901820 [Frankfurt Relay]',
                target: 'Cloud Engineering Operations',
                vector: 'ElevenLabs Professional Voice Clone',
                risk: 'Critical',
                confidence: '96.4%',
                action: 'Auto-Terminated & SOC Flagged',
                details: 'Attempted emergency escalation into AWS Production IAM permissions via phone bridge.'
            },
            {
                id: 'VG-9075',
                timestamp: '2026-11-10 04:12:05 UTC',
                origin: '+1 (312) 555-0144 [Chicago Gateway]',
                target: 'Executive Assistant Pool',
                vector: 'Acoustic Replay (Recorded Voicemail)',
                risk: 'Medium',
                confidence: '82.1%',
                action: 'Diverted to Interactive Verification',
                details: 'Background room reverberation signature did not match legitimate executive office acoustics.'
            }
        ],

        // Enrolled Biometric Voiceprints Vault
        enrolledSpeakers: [{
                id: 'EMP-4012',
                name: 'Sarah Jenkins',
                dept: 'Treasury & Finance',
                clearance: 'Level 5 (Top Secret)',
                hash: 'SHA256: 7f83...b19a',
                enrolledDate: '2026-03-14',
                verifiedCalls: 142,
                status: 'Sample'
            },
            {
                id: 'EMP-1004',
                name: 'Marcus Vance',
                dept: 'Executive Board (CEO)',
                clearance: 'Level 5 (Top Secret)',
                hash: 'SHA256: 3c94...e4d2',
                enrolledDate: '2026-01-09',
                verifiedCalls: 89,
                status: 'Sample'
            },
            {
                id: 'EMP-7890',
                name: 'Dr. Aris Thorne',
                dept: 'IT Infrastructure',
                clearance: 'Level 4 (Secret)',
                hash: 'SHA256: a118...8f02',
                enrolledDate: '2026-05-22',
                verifiedCalls: 63,
                status: 'Sample'
            },
            {
                id: 'EMP-5521',
                name: 'Elena Rostova',
                dept: 'Legal & Compliance',
                clearance: 'Level 4 (Secret)',
                hash: 'SHA256: 9b2d...517c',
                enrolledDate: '2026-08-11',
                verifiedCalls: 34,
                status: 'Sample'
            }
        ],

        // SOC Compliance & Audit Log
        complianceLog: [
            { id: 'AUD-8821', type: 'ENCRYPTED_CALL_BLOCKED', user: 'SYSTEM (Neural Shield)', resource: 'SIP Trunk 04', status: '200 OK', hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4' },
            { id: 'AUD-8820', type: 'VOICEPRINT_VAULT_QUERY', user: 'SecOps Unit 09', resource: 'Vault Record EMP-4012', status: '200 OK', hash: '88d4266fd4e6338d13b845fcf289579d209c8978' },
            { id: 'AUD-8819', type: 'MFA_CHALLENGE_ISSUED', user: 'VoiceGuard Gatekeeper', resource: 'Caller +44 20 7946 0912', status: '401 CHALLENGE', hash: 'ca978112ca1bbdcafac231b39a23dc4da786eff8' },
            { id: 'AUD-8818', type: 'ACOUSTIC_MODEL_HEURISTIC', user: 'Worker-Node-Alpha', resource: 'Vocoder Weight Check', status: '200 OK', hash: '3e23e8160039594a33894f6564e1b1348bbd7a00' },
            { id: 'AUD-8817', type: 'GEO_SPOOF_TELEMETRY', user: 'Telecom Firewall', resource: 'Inbound SIP Header 890-3129', status: '403 FORBIDDEN', hash: '2e7d2c03a9507ae265ecf5b5356885a53393a202' }
        ],

        // Preset Forensic Audio Profiles (for Voice Analysis testing)
        forensicProfiles: {
            deepfake: {
                title: 'Preset 1: AI Clone (High Risk)',
                fileName: 'sample_exec_deepfake_clone.wav',
                specs: 'WAV • 16-bit PCM • 44.1 kHz • Mono (Synthetic)',
                synthType: 'deepfake',
                verdict: 'HIGH-RISK SYNTHETIC CLONE',
                verdictClass: 'danger',
                probability: '97.4%',
                summary: 'Acoustic signature matches neural speech synthesis. Strong vocoder phase artifacts and abnormal pitch stability detected.',
                vocoder: { val: 'High (94%)', width: '94%', class: 'bg-danger' },
                pitch: { val: 'Unnatural (14%)', width: '14%', class: 'bg-warning' },
                spectral: { val: 'Discontinuous (38%)', width: '38%', class: 'bg-info' },
                breath: { val: 'Missing (08%)', width: '8%', class: 'bg-danger' },
                modelAttribution: 'ElevenLabs v2 / Diffusion Latent TTS',
                modelDetails: 'Matches statistical latent distribution of multi-speaker diffusion acoustic synthesizers trained on scraped web audio.',
                recommendation: 'Quarantine active voice channel immediately. Require step-up out-of-band biometric authentication (FIDO2 / Hardware token).'
            },
            genuine: {
                title: 'Preset 2: Biological Voice (Clean)',
                fileName: 'sample_authentic_human_speech.wav',
                specs: 'WAV • 24-bit PCM • 48.0 kHz • Stereo (Biological)',
                synthType: 'genuine',
                verdict: 'VERIFIED BIOLOGICAL SPEECH',
                verdictClass: 'success',
                probability: '2.1%',
                summary: 'Acoustic characteristics exhibit natural vocal tract resonance, micro-tremors, and organic glottal pulse timing.',
                vocoder: { val: 'Undetected (04%)', width: '4%', class: 'bg-success' },
                pitch: { val: 'Natural (92%)', width: '92%', class: 'bg-success' },
                spectral: { val: 'Continuous (96%)', width: '96%', class: 'bg-success' },
                breath: { val: 'Natural (91%)', width: '91%', class: 'bg-success' },
                modelAttribution: 'None (Human Vocal Tract Anatomy)',
                modelDetails: 'Harmonic spectral envelope matches natural biological articulatory dynamics without synthetic vocoder footprint.',
                recommendation: 'Voice verified genuine. Proceed with standard customer communications protocol.'
            },
            suspicious: {
                title: 'Preset 3: Voice Changer (Suspicious)',
                fileName: 'sample_pitch_shifted_vocoder.wav',
                specs: 'WAV • 16-bit PCM • 44.1 kHz • Transcoded (Modified)',
                synthType: 'suspicious',
                verdict: 'SUSPICIOUS ACOUSTIC ANOMALY',
                verdictClass: 'warning',
                probability: '68.5%',
                summary: 'Frequency domain anomalies detected. Evidence of real-time formant manipulation or DSP pitch alteration.',
                vocoder: { val: 'Moderate (64%)', width: '64%', class: 'bg-warning' },
                pitch: { val: 'Perturbed (45%)', width: '45%', class: 'bg-warning' },
                spectral: { val: 'Phase Shuffled (58%)', width: '58%', class: 'bg-info' },
                breath: { val: 'Present (62%)', width: '62%', class: 'bg-info' },
                modelAttribution: 'Real-Time DSP / VST Pitch Modifier',
                modelDetails: 'Non-linear phase shifts and digital grain artifacts consistent with real-time software voice changer plugin.',
                recommendation: 'Flag session for SOC analyst review. Request caller repeat an unpredictable phonetic passphrase.'
            }
        }
    };

    // ==========================================================================
    // 2. NAVIGATION & SINGLE PAGE ROUTING
    // ==========================================================================

    const reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    let coreAnimationId = null;
    let coreRotation = 0;
    let coreThreeRenderer = null;
    let coreThreeScene = null;
    let coreThreeCamera = null;
    let coreThreeObjects = null;
    let coreThreeLastFrame = 0;
    let corePointerX = 0;
    let corePointerY = 0;
    let corePointerTargetX = 0;
    let corePointerTargetY = 0;
    let fallbackCoreLastFrame = 0;
    let isCoreVisible = true;
    let revealObserver = null;
    const initializedReveals = new WeakSet();
    const observedRevealViews = new WeakSet();

    function initializeThreeCore() {
        const canvas = document.getElementById('ai-core-webgl');
        const sceneElement = document.getElementById('core-scene');
        if (!canvas || !sceneElement || coreThreeRenderer) return Boolean(coreThreeRenderer);
        if (!window.THREE || !window.THREE.WebGLRenderer) return false;

        try {
            const THREE = window.THREE;
            const scene = new THREE.Scene();
            const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 40);
            camera.position.z = 4.2;

            const renderer = new THREE.WebGLRenderer({
                canvas,
                alpha: true,
                antialias: true,
                powerPreference: 'high-performance'
            });
            renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
            renderer.setSize(Math.max(canvas.clientWidth, 1), Math.max(canvas.clientHeight, 1), false);
            renderer.setClearColor(0x000000, 0);

            const group = new THREE.Group();
            scene.add(group);

            // 1. Faceted Volumetric AI Core
            const core = new THREE.Mesh(
                new THREE.IcosahedronGeometry(0.82, 2),
                new THREE.MeshStandardMaterial({
                    color: 0x362464,
                    emissive: 0x4f22a5,
                    emissiveIntensity: 1.05,
                    roughness: 0.28,
                    metalness: 0.68,
                    transparent: true,
                    opacity: 0.88
                })
            );
            group.add(core);

            // Glowing Wireframe Shell
            const wire = new THREE.Mesh(
                new THREE.IcosahedronGeometry(0.84, 2),
                new THREE.MeshBasicMaterial({
                    color: 0x00f5d4,
                    wireframe: true,
                    transparent: true,
                    opacity: 0.32
                })
            );
            group.add(wire);

            // Inner Pulsating Core Seed
            const innerSeed = new THREE.Mesh(
                new THREE.SphereGeometry(0.48, 16, 16),
                new THREE.MeshBasicMaterial({
                    color: 0x00e5ff,
                    transparent: true,
                    opacity: 0.65
                })
            );
            group.add(innerSeed);

            // Dynamic Energy Wave Shockwave Shell
            const energyWave = new THREE.Mesh(
                new THREE.SphereGeometry(0.88, 24, 24),
                new THREE.MeshBasicMaterial({
                    color: 0x00f5d4,
                    wireframe: true,
                    transparent: true,
                    opacity: 0.35
                })
            );
            group.add(energyWave);

            // 2. Multiple 3D Orbital Rings with Tracking Satellites
            const ringSpecs = [
                { r: 1.15, tube: 0.008, color: 0x00f5d4, rx: 0.85, ry: 0.34, rz: 0.18, speed: 0.22 },
                { r: 1.30, tube: 0.007, color: 0x00cfff, rx: 1.23, ry: -0.5, rz: 0.65, speed: -0.19 },
                { r: 1.46, tube: 0.006, color: 0x8b5cf6, rx: 0.2, ry: 1.15, rz: -0.42, speed: 0.25 },
                { r: 1.04, tube: 0.006, color: 0xd946ef, rx: -0.65, ry: 0.45, rz: 0.9, speed: -0.28 },
                { r: 1.62, tube: 0.005, color: 0x00f5d4, rx: 0.08, ry: 0, rz: 0, speed: 0.14 }
            ];

            const orbitalRings = ringSpecs.map(spec => {
                const ring = new THREE.Mesh(
                    new THREE.TorusGeometry(spec.r, spec.tube, 4, 96),
                    new THREE.MeshBasicMaterial({ color: spec.color, transparent: true, opacity: 0.68 })
                );
                ring.rotation.set(spec.rx, spec.ry, spec.rz);
                ring.userData = { speed: spec.speed, rx: spec.rx, ry: spec.ry, rz: spec.rz, radius: spec.r };

                // Satellite bead running on the ring
                const sat = new THREE.Mesh(
                    new THREE.SphereGeometry(0.024, 8, 8),
                    new THREE.MeshBasicMaterial({ color: spec.color })
                );
                sat.position.set(spec.r, 0, 0);
                ring.add(sat);
                ring.userData.satellite = sat;

                group.add(ring);
                return ring;
            });

            // 3. Hundreds of Glowing Neural Particles
            const particleCount = 340;
            const positions = new Float32Array(particleCount * 3);
            const colors = new Float32Array(particleCount * 3);
            const particleBase = [];

            for (let i = 0; i < particleCount; i++) {
                const y = 1 - (i / (particleCount - 1)) * 2;
                const radius = Math.sqrt(1 - y * y);
                const angle = Math.PI * (3 - Math.sqrt(5)) * i;
                const spread = 1.32 + (i % 7) * 0.045;
                const x = Math.cos(angle) * radius * spread;
                const py = y * spread;
                const z = Math.sin(angle) * radius * spread;

                positions[i * 3] = x;
                positions[i * 3 + 1] = py;
                positions[i * 3 + 2] = z;

                particleBase.push({ x, y: py, z, speed: 0.4 + (i % 5) * 0.2 });

                const color = new THREE.Color(
                    i % 4 === 0 ? 0x00f5d4 : (i % 3 === 0 ? 0x00e5ff : (i % 2 === 0 ? 0x8b5cf6 : 0xd946ef))
                );
                colors[i * 3] = color.r;
                colors[i * 3 + 1] = color.g;
                colors[i * 3 + 2] = color.b;
            }

            const particleGeometry = new THREE.BufferGeometry();
            particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
            particleGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
            const particles = new THREE.Points(
                particleGeometry,
                new THREE.PointsMaterial({
                    size: 0.032,
                    vertexColors: true,
                    transparent: true,
                    opacity: 0.92,
                    sizeAttenuation: true
                })
            );
            group.add(particles);

            // 4. Interconnected Neural Nodes and Synaptic Connections
            const nodePositions = [];
            const neuralPoints = [];
            const neuralNodeCount = 76;

            for (let i = 0; i < neuralNodeCount; i++) {
                const y = 1 - (i / (neuralNodeCount - 1)) * 2;
                const radius = Math.sqrt(1 - y * y);
                const angle = Math.PI * (3 - Math.sqrt(5)) * i;
                const point = new THREE.Vector3(
                    Math.cos(angle) * radius * 1.08,
                    y * 1.08,
                    Math.sin(angle) * radius * 1.08
                );
                neuralPoints.push(point);
            }

            for (let i = 0; i < neuralPoints.length; i++) {
                for (let j = i + 1; j < neuralPoints.length; j++) {
                    if (neuralPoints[i].distanceToSquared(neuralPoints[j]) < 0.32) {
                        nodePositions.push(
                            neuralPoints[i].x, neuralPoints[i].y, neuralPoints[i].z,
                            neuralPoints[j].x, neuralPoints[j].y, neuralPoints[j].z
                        );
                    }
                }
            }

            const neuralConnections = new THREE.LineSegments(
                new THREE.BufferGeometry().setAttribute(
                    'position',
                    new THREE.Float32BufferAttribute(nodePositions, 3)
                ),
                new THREE.LineBasicMaterial({
                    color: 0x8294ff,
                    transparent: true,
                    opacity: 0.32
                })
            );
            group.add(neuralConnections);

            const neuralNodes = new THREE.InstancedMesh(
                new THREE.SphereGeometry(0.02, 6, 6),
                new THREE.MeshBasicMaterial({ color: 0x9beaff, transparent: true, opacity: 0.95 }),
                neuralPoints.length
            );
            const nodeTransform = new THREE.Object3D();
            neuralPoints.forEach((point, index) => {
                nodeTransform.position.copy(point);
                nodeTransform.scale.setScalar(index % 6 === 0 ? 1.8 : 1);
                nodeTransform.updateMatrix();
                neuralNodes.setMatrixAt(index, nodeTransform.matrix);
            });
            neuralNodes.instanceMatrix.needsUpdate = true;
            group.add(neuralNodes);

            // 5. Advanced Lighting System
            scene.add(new THREE.AmbientLight(0x8ea0ff, 1.6));
            
            const cyanLight = new THREE.PointLight(0x00f5d4, 8, 10);
            cyanLight.position.set(-2.4, 1.8, 3.0);
            scene.add(cyanLight);

            const violetLight = new THREE.PointLight(0x8b5cf6, 9, 10);
            violetLight.position.set(2.4, -1.5, 2.4);
            scene.add(violetLight);

            const blueLight = new THREE.PointLight(0x00cfff, 5, 8);
            blueLight.position.set(0, -2.2, 2.0);
            scene.add(blueLight);

            coreThreeRenderer = renderer;
            coreThreeScene = scene;
            coreThreeCamera = camera;
            coreThreeObjects = {
                group,
                core,
                wire,
                innerSeed,
                energyWave,
                orbitalRings,
                particles,
                particleBase,
                neuralConnections,
                neuralNodes,
                cyanLight,
                violetLight
            };

            const rect = canvas.getBoundingClientRect();
            resizeThreeCore(rect.width, rect.height);
            sceneElement.classList.add('has-webgl');
            return true;
        } catch (error) {
            console.warn('3D core unavailable; using the lightweight canvas fallback.', error);
            sceneElement.classList.remove('has-webgl');
            return false;
        }
    }

    function resizeThreeCore(width, height) {
        if (!coreThreeRenderer || !coreThreeCamera || !width || !height) return;
        coreThreeCamera.aspect = width / height;
        coreThreeCamera.updateProjectionMatrix();
        coreThreeRenderer.setSize(width, height, false);
    }

    function animateThreeCore(timestamp) {
        if (!coreThreeRenderer || !coreThreeScene || !coreThreeCamera || !coreThreeObjects) return;
        const overview = document.getElementById('view-overview');
        if (!overview || !overview.classList.contains('active') || document.hidden) {
            coreAnimationId = null;
            return;
        }
        if (timestamp - coreThreeLastFrame < 16) {
            coreAnimationId = requestAnimationFrame(animateThreeCore);
            return;
        }
        coreThreeLastFrame = timestamp;
        const {
            group, core, wire, innerSeed, energyWave,
            orbitalRings, particles, particleBase,
            neuralConnections, neuralNodes, cyanLight, violetLight
        } = coreThreeObjects;

        const time = timestamp * 0.001;

        // Smooth Mouse Parallax Damping
        corePointerX += (corePointerTargetX - corePointerX) * 0.06;
        corePointerY += (corePointerTargetY - corePointerY) * 0.06;

        // Group cinematic rotations & mouse tilt
        group.rotation.y = time * 0.14 + corePointerX;
        group.rotation.x = Math.sin(time * 0.22) * 0.08 + corePointerY;

        // Pulsating Core Breathing
        const corePulse = 1 + Math.sin(time * 2.4) * 0.035;
        core.scale.set(corePulse, corePulse, corePulse);
        core.rotation.y = time * 0.12;
        core.rotation.z = Math.sin(time * 0.2) * 0.04;

        wire.rotation.y = -time * 0.15;
        wire.rotation.x = time * 0.08;

        const seedPulse = 0.95 + Math.sin(time * 3.2) * 0.08;
        innerSeed.scale.set(seedPulse, seedPulse, seedPulse);

        // Dynamic Energy Wave Shockwave
        const wavePhase = (time * 0.6) % 1;
        const waveScale = 1.0 + wavePhase * 0.65;
        energyWave.scale.set(waveScale, waveScale, waveScale);
        energyWave.material.opacity = Math.max(0, (1 - wavePhase) * 0.45);
        energyWave.rotation.y = time * 0.2;

        // Animate Orbital Rings and Satellites
        orbitalRings.forEach(ring => {
            ring.rotation.z += ring.userData.speed * 0.015;
            if (ring.userData.satellite) {
                const sAngle = time * ring.userData.speed * 4;
                ring.userData.satellite.position.x = Math.cos(sAngle) * ring.userData.radius;
                ring.userData.satellite.position.y = Math.sin(sAngle) * ring.userData.radius;
            }
        });

        // Waving Particles with Brownian Turbulence
        if (particles && particleBase) {
            const pos = particles.geometry.attributes.position.array;
            for (let i = 0; i < particleBase.length; i++) {
                const b = particleBase[i];
                const wave = Math.sin(time * 2.2 + i * 0.1) * 0.03;
                pos[i * 3] = b.x * (1 + wave);
                pos[i * 3 + 1] = b.y * (1 + wave);
                pos[i * 3 + 2] = b.z * (1 + wave);
            }
            particles.geometry.attributes.position.needsUpdate = true;
            particles.rotation.y = -time * 0.06;
        }

        // Synaptic Signal Pulse
        if (neuralConnections) {
            neuralConnections.material.opacity = 0.25 + Math.sin(time * 3.5) * 0.18;
            neuralConnections.rotation.y = -time * 0.08;
        }
        if (neuralNodes) {
            neuralNodes.rotation.y = -time * 0.08;
        }

        // Orbiting Lights
        if (cyanLight) {
            cyanLight.position.x = Math.cos(time * 0.7) * 2.8;
            cyanLight.position.z = Math.sin(time * 0.7) * 2.8;
        }
        if (violetLight) {
            violetLight.position.x = Math.sin(time * 0.5) * 2.6;
            violetLight.position.y = Math.cos(time * 0.5) * 2.0;
        }

        // Cinematic Camera Breathing
        coreThreeCamera.position.x = Math.sin(time * 0.35) * 0.12;
        coreThreeCamera.position.y = Math.cos(time * 0.28) * 0.09;
        coreThreeCamera.lookAt(0, 0, 0);

        coreThreeRenderer.render(coreThreeScene, coreThreeCamera);

        if (!reducedMotionQuery.matches) {
            coreAnimationId = requestAnimationFrame(animateThreeCore);
        } else {
            coreAnimationId = null;
        }
    }

    function startCoreAnimation() {
        const overview = document.getElementById('view-overview');
        if (!overview || !overview.classList.contains('active') || document.hidden || !isCoreVisible) return;
        if (initializeThreeCore()) {
            if (coreAnimationId) cancelAnimationFrame(coreAnimationId);
            coreAnimationId = requestAnimationFrame(animateThreeCore);
        } else {
            drawAiCore();
        }
    }

    function stopCoreAnimation() {
        if (coreAnimationId) cancelAnimationFrame(coreAnimationId);
        coreAnimationId = null;
    }

    function animateVisibleCounter(element) {
        if (reducedMotionQuery.matches || element.dataset.counterAnimated) return;
        const original = element.textContent.trim();
        const match = original.match(/^([\d,]+)(\.\d+)?(.*)$/);
        if (!match) return;
        const target = Number(`${match[1].replace(/,/g, '')}${match[2] || ''}`);
        if (!Number.isFinite(target)) return;
        element.dataset.counterAnimated = 'true';
        const decimals = match[2] ? match[2].length - 1 : 0;
        const suffix = match[3];
        const start = performance.now();
        const duration = 850;
        const update = now => {
            const progress = Math.min((now - start) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const value = target * eased;
            const formatted = decimals ? value.toFixed(decimals) : Math.round(value).toLocaleString();
            element.textContent = `${formatted}${suffix}`;
            if (progress < 1) requestAnimationFrame(update);
            else element.textContent = original;
        };
        requestAnimationFrame(update);
    }

    function revealActiveView(view) {
        if (!view) return;
        view.classList.remove('view-entered');
        void view.offsetWidth;
        view.classList.add('view-entered');
        if (reducedMotionQuery.matches) {
            view.querySelectorAll('[data-motion-reveal]').forEach(element => element.classList.add('is-visible'));
            return;
        }

        const revealItems = view.querySelectorAll('.hero-copy, .core-scene, .identity-shield, .metric-card, .view-section .card');
        revealItems.forEach(element => {
            element.setAttribute('data-motion-reveal', '');
            if (initializedReveals.has(element)) return;
            initializedReveals.add(element);
            if (window.gsap && window.ScrollTrigger) {
                window.gsap.registerPlugin(window.ScrollTrigger);
                window.gsap.fromTo(element, { autoAlpha: 0, y: 22 }, {
                    autoAlpha: 1,
                    y: 0,
                    duration: 0.64,
                    ease: 'power2.out',
                    scrollTrigger: {
                        trigger: element,
                        start: 'top 94%',
                        once: true,
                        onEnter: () => element.classList.add('is-visible')
                    }
                });
            } else if (!revealObserver) {
                element.classList.add('is-visible');
            }
        });

        view.querySelectorAll('.metric-number').forEach(element => {
            if (element.getBoundingClientRect().top < window.innerHeight * 0.94) {
                animateVisibleCounter(element);
            }
        });
        if (!observedRevealViews.has(view)) {
            observedRevealViews.add(view);
            if (revealObserver && !(window.gsap && window.ScrollTrigger)) {
                view.querySelectorAll('[data-motion-reveal]').forEach(element => {
                    if (!element.classList.contains('is-visible')) revealObserver.observe(element);
                });
            }
        }
        if (window.gsap && window.ScrollTrigger) window.ScrollTrigger.refresh();
    }

    if ('IntersectionObserver' in window) {
        revealObserver = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                const element = entry.target;
                element.classList.add('is-visible');
                if (element.classList.contains('metric-card')) {
                    const counter = element.querySelector('.metric-number');
                    if (counter) animateVisibleCounter(counter);
                }
                revealObserver.unobserve(element);
            });
        }, { threshold: 0.12, rootMargin: '0px 0px -24px 0px' });
    }

    const coreViewportObserver = 'IntersectionObserver' in window
        ? new IntersectionObserver(entries => {
            const entry = entries[0];
            if (!entry) return;
            isCoreVisible = entry.isIntersecting;
            if (isCoreVisible) startCoreAnimation();
            else stopCoreAnimation();
        }, { threshold: 0.05 })
        : null;
    const observedCoreScene = document.getElementById('core-scene');
    if (coreViewportObserver && observedCoreScene) coreViewportObserver.observe(observedCoreScene);

    function drawAiCore() {
        const canvas = document.getElementById('ai-core-canvas');
        const scene = document.getElementById('core-scene');
        const overview = document.getElementById('view-overview');
        if (!canvas || !scene || !overview || !overview.classList.contains('active') || document.hidden || scene.classList.contains('has-webgl')) return;
        if (coreAnimationId) cancelAnimationFrame(coreAnimationId);
        const ctx = canvas.getContext('2d');
        if (!ctx) {
            scene.classList.add('core-static-fallback');
            return;
        }

        const rect = canvas.getBoundingClientRect();
        if (!rect.width || !rect.height) return;
        const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
        canvas.width = Math.round(rect.width * dpr);
        canvas.height = Math.round(rect.height * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        const render = timestamp => {
            if (!overview.classList.contains('active') || document.hidden) {
                coreAnimationId = null;
                return;
            }
            if (timestamp && timestamp - fallbackCoreLastFrame < 33) {
                coreAnimationId = requestAnimationFrame(render);
                return;
            }
            fallbackCoreLastFrame = timestamp || performance.now();
            const width = rect.width;
            const height = rect.height;
            const cx = width / 2;
            const cy = height / 2;
            ctx.clearRect(0, 0, width, height);

            const glow = ctx.createRadialGradient(cx, cy, 5, cx, cy, width * 0.48);
            glow.addColorStop(0, 'rgba(0, 245, 212, 0.22)');
            glow.addColorStop(0.52, 'rgba(139, 92, 246, 0.12)');
            glow.addColorStop(1, 'rgba(5, 5, 16, 0)');
            ctx.fillStyle = glow;
            ctx.fillRect(0, 0, width, height);

            for (let i = 0; i < 38; i++) {
                const seed = i * 2.39996;
                const orbit = width * (0.18 + (i % 7) * 0.026);
                const angle = seed + coreRotation * (i % 2 ? 0.35 : -0.22);
                const x = cx + Math.cos(angle) * orbit;
                const y = cy + Math.sin(angle) * orbit * 0.78;
                const alpha = 0.35 + ((Math.sin(seed + coreRotation) + 1) * 0.3);
                ctx.beginPath();
                ctx.fillStyle = i % 3 === 0 ? `rgba(0, 245, 212, ${alpha})` : `rgba(139, 92, 246, ${alpha})`;
                ctx.shadowColor = i % 3 === 0 ? '#00f5d4' : '#8b5cf6';
                ctx.shadowBlur = 8;
                ctx.arc(x, y, i % 6 === 0 ? 2 : 1.25, 0, Math.PI * 2);
                ctx.fill();
            }
            ctx.shadowBlur = 0;

            if (!reducedMotionQuery.matches) {
                coreRotation += 0.006;
                coreAnimationId = requestAnimationFrame(render);
            } else {
                coreAnimationId = null;
            }
        };
        render();
    }

    const coreScene = document.getElementById('core-scene');
    if (coreScene && window.matchMedia('(pointer: fine)').matches && !reducedMotionQuery.matches) {
        coreScene.addEventListener('pointermove', event => {
            const bounds = coreScene.getBoundingClientRect();
            const x = (event.clientX - bounds.left) / bounds.width - 0.5;
            const y = (event.clientY - bounds.top) / bounds.height - 0.5;
            corePointerTargetX = x * 0.32;
            corePointerTargetY = y * -0.22;
            coreScene.style.setProperty('--pointer-x', `${x * 12}deg`);
            coreScene.style.setProperty('--pointer-y', `${y * -12}deg`);
        });
        coreScene.addEventListener('pointerleave', () => {
            corePointerTargetX = 0;
            corePointerTargetY = 0;
            coreScene.style.setProperty('--pointer-x', '0deg');
            coreScene.style.setProperty('--pointer-y', '0deg');
        });
    }

    if (window.matchMedia('(pointer: fine)').matches && !reducedMotionQuery.matches) {
        document.querySelectorAll('.metric-card').forEach(card => {
            card.addEventListener('pointermove', event => {
                const bounds = card.getBoundingClientRect();
                const x = (event.clientX - bounds.left) / bounds.width - 0.5;
                const y = (event.clientY - bounds.top) / bounds.height - 0.5;
                card.style.setProperty('--tilt-x', `${y * -4}deg`);
                card.style.setProperty('--tilt-y', `${x * 4}deg`);
            });
            card.addEventListener('pointerleave', () => {
                card.style.setProperty('--tilt-x', '0deg');
                card.style.setProperty('--tilt-y', '0deg');
            });
        });

        document.querySelectorAll('.card:not(.metric-card)').forEach(card => {
            card.classList.add('motion-tilt');
            card.addEventListener('pointermove', event => {
                const bounds = card.getBoundingClientRect();
                const x = (event.clientX - bounds.left) / bounds.width - 0.5;
                const y = (event.clientY - bounds.top) / bounds.height - 0.5;
                card.style.setProperty('--card-tilt-x', `${y * -2.2}deg`);
                card.style.setProperty('--card-tilt-y', `${x * 2.2}deg`);
            });
            card.addEventListener('pointerleave', () => {
                card.style.setProperty('--card-tilt-x', '0deg');
                card.style.setProperty('--card-tilt-y', '0deg');
            });
        });

        document.querySelectorAll('.btn:not(:disabled), .nav-link').forEach(element => {
            element.classList.add('motion-magnetic');
            element.addEventListener('pointermove', event => {
                const bounds = element.getBoundingClientRect();
                const x = (event.clientX - bounds.left) / bounds.width - 0.5;
                const y = (event.clientY - bounds.top) / bounds.height - 0.5;
                element.style.setProperty('--magnetic-x', `${x * 3}px`);
                element.style.setProperty('--magnetic-y', `${y * 2}px`);
            });
            element.addEventListener('pointerleave', () => {
                element.style.setProperty('--magnetic-x', '0px');
                element.style.setProperty('--magnetic-y', '0px');
            });
        });
    }

    const navLinks = document.querySelectorAll('.sidebar-nav .nav-link');
    const viewSections = document.querySelectorAll('.view-section');
    const currentViewTitle = document.getElementById('current-view-title');

    const VIEW_TITLES = {
        'overview': 'Dashboard Overview',
        'analysis': 'Voice Forensics & Analysis',
        'live-monitoring': 'Live Voice Stream Monitoring',
        'verification': 'Speaker Verification & Biometrics',
        'threat-intel': 'Threat Intelligence & Incidents',
        'fraud-prevention': 'Fraud Prevention Workflows',
        'history': 'Forensic Detection History',
        'reports': 'Forensic Reports & Audit',
        'analytics': 'Reports & Security Analytics',
        'profile': 'Your Profile',
        'settings': 'Account & Security Settings'
    };
    function switchView(viewId) {
        if (!VIEW_TITLES[viewId]) return;
        if (viewId !== 'analysis') stopMicrophoneRecording();
        stopCoreAnimation();

        // Update active nav link
        navLinks.forEach(link => {
            if (link.getAttribute('data-view') === viewId) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });

        // Update visible view section
        viewSections.forEach(section => {
            if (section.id === `view-${viewId}`) {
                section.classList.add('active');
            } else {
                section.classList.remove('active');
            }
        });
        const activeView = document.getElementById(`view-${viewId}`);
        if (activeView) revealActiveView(activeView);
        window.VoiceGuardScenes?.activate(viewId);

        // Update header breadcrumb
        if (currentViewTitle) {
            currentViewTitle.textContent = VIEW_TITLES[viewId];
        }

        // Trigger view transition animation
        if (typeof window.VoiceGuardAnimationAPI !== 'undefined') {
            window.VoiceGuardAnimationAPI.animateViewTransition(viewId);
        }

        // Refresh charts if entering overview or analytics
        if (viewId === 'overview') {
            setTimeout(renderOverviewTrendChart, 50);
            startCoreAnimation();
        } else if (viewId === 'analytics') {
            setTimeout(() => {
                renderRiskDonutChart();
                renderWeeklyVolumeChart();
            }, 50);
        }
    }

    // Nav link click event listeners
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const viewId = link.getAttribute('data-view');
            window.location.hash = viewId;
            switchView(viewId);
        });
    });

    // Cross-view button triggers
    const viewAllThreatsBtn = document.getElementById('view-all-threats-btn');
    if (viewAllThreatsBtn) {
        viewAllThreatsBtn.addEventListener('click', () => {
            window.location.hash = 'threat-intel';
            switchView('threat-intel');
        });
    }

    const startVoiceAnalysisBtn = document.getElementById('start-voice-analysis');
    if (startVoiceAnalysisBtn) {
        startVoiceAnalysisBtn.addEventListener('click', () => {
            window.location.hash = 'analysis';
            switchView('analysis');
        });
    }

    // Handle URL hash changes
    window.addEventListener('hashchange', () => {
        const rawHash = window.location.hash.replace('#', '');
        if (rawHash && VIEW_TITLES[rawHash]) {
            switchView(rawHash);
        }
    });

    // System UTC Clock
    const systemClockEl = document.getElementById('system-clock');

    function updateClock() {
        if (!systemClockEl) return;
        const now = new Date();
        const hours = String(now.getUTCHours()).padStart(2, '0');
        const minutes = String(now.getUTCMinutes()).padStart(2, '0');
        const seconds = String(now.getUTCSeconds()).padStart(2, '0');
        systemClockEl.textContent = `${hours}:${minutes}:${seconds} UTC`;
    }
    setInterval(updateClock, 1000);
    updateClock();

    // Toast Notification System
    const toastContainer = document.getElementById('toast-container');

    function showToast(message, type = 'info') {
        if (window.VoiceGuardDemoNotifications === false) return;
        if (!toastContainer) return;
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        const content = document.createElement('div');
        content.className = 'toast-content';
        const text = document.createElement('span');
        text.textContent = message;
        content.appendChild(text);
        toast.appendChild(content);
        toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    }

    // ==========================================================================
    // 3. DASHBOARD OVERVIEW & CHART RENDERERS
    // ==========================================================================

    // Populate Overview Recent Activity Table
    function populateOverviewTable() {
        const tableBody = document.getElementById('overview-recent-table');
        if (!tableBody) return;
        tableBody.innerHTML = '';

        // Show the first 4 threat incidents
        SAMPLE_DATA.threatIncidents.slice(0, 4).forEach(item => {
            const tr = document.createElement('tr');
            const badgeClass = item.risk === 'Critical' ? 'badge-danger' : (item.risk === 'High' ? 'badge-warning' : 'badge-info');
            tr.innerHTML = `
        <td class="mono-cell"><strong>${item.id}</strong></td>
        <td class="mono-cell">${item.timestamp.split(' ')[1]}</td>
        <td>${item.origin.split(' ')[0]}</td>
        <td>${item.target}</td>
        <td><span class="text-secondary">${item.vector}</span></td>
        <td><span class="badge ${badgeClass}">${item.risk}</span></td>
        <td><strong class="text-primary">${item.action}</strong></td>
      `;
            tableBody.appendChild(tr);
        });
    }

    // Canvas 1: 24-Hour Call Inspection Volume Chart
    function renderOverviewTrendChart() {
        const canvas = document.getElementById('overview-trend-canvas');
        if (!canvas) return;

        // Handle high DPI crispness
        const rect = canvas.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;

        const ctx = canvas.getContext('2d');
        ctx.scale(dpr, dpr);
        const width = rect.width;
        const height = rect.height;

        ctx.clearRect(0, 0, width, height);

        const padding = { top: 20, right: 20, bottom: 30, left: 45 };
        const chartW = width - padding.left - padding.right;
        const chartH = height - padding.top - padding.bottom;

        const data = SAMPLE_DATA.hourlyTelemetry;
        const maxVal = 1600;

        // Draw horizontal grid lines
        ctx.strokeStyle = '#1e2f54';
        ctx.lineWidth = 1;
        ctx.fillStyle = '#64748b';
        ctx.font = '10px JetBrains Mono, monospace';
        ctx.textAlign = 'right';

        const yTicks = 4;
        for (let i = 0; i <= yTicks; i++) {
            const yVal = Math.round((maxVal / yTicks) * i);
            const yPos = padding.top + chartH - (i / yTicks) * chartH;
            ctx.beginPath();
            ctx.moveTo(padding.left, yPos);
            ctx.lineTo(padding.left + chartW, yPos);
            ctx.stroke();
            ctx.fillText(yVal, padding.left - 8, yPos + 3);
        }

        // Calculate (x, y) coordinates
        const pointsClean = [];
        const pointsFlagged = [];
        const stepX = chartW / (data.length - 1);

        data.forEach((d, i) => {
            const x = padding.left + i * stepX;
            const yClean = padding.top + chartH - (d.total / maxVal) * chartH;
            const yFlagged = padding.top + chartH - ((d.flagged * 12) / maxVal) * chartH; // Scale flagged calls for visual contrast
            pointsClean.push({ x, y: yClean });
            pointsFlagged.push({ x, y: yFlagged });

            // Draw X axis label
            ctx.fillStyle = '#64748b';
            ctx.textAlign = 'center';
            ctx.fillText(d.hour, x, height - 10);
        });

        // Helper: Draw smooth line with fill
        function drawAreaAndLine(points, strokeColor, fillColor) {
            if (points.length < 2) return;

            // Fill area under curve
            ctx.beginPath();
            ctx.moveTo(points[0].x, padding.top + chartH);
            ctx.lineTo(points[0].x, points[0].y);
            for (let i = 1; i < points.length; i++) {
                ctx.lineTo(points[i].x, points[i].y);
            }
            ctx.lineTo(points[points.length - 1].x, padding.top + chartH);
            ctx.closePath();
            ctx.fillStyle = fillColor;
            ctx.fill();

            // Stroke line
            ctx.beginPath();
            ctx.moveTo(points[0].x, points[0].y);
            for (let i = 1; i < points.length; i++) {
                ctx.lineTo(points[i].x, points[i].y);
            }
            ctx.strokeStyle = strokeColor;
            ctx.lineWidth = 2.5;
            ctx.stroke();

            // Draw dots
            points.forEach(p => {
                ctx.beginPath();
                ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2);
                ctx.fillStyle = strokeColor;
                ctx.fill();
                ctx.strokeStyle = '#070b14';
                ctx.lineWidth = 1.5;
                ctx.stroke();
            });
        }

        // Draw Clean Calls Area (Electric Blue)
        const blueGradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartH);
        blueGradient.addColorStop(0, 'rgba(0, 229, 255, 0.25)');
        blueGradient.addColorStop(1, 'rgba(0, 229, 255, 0.01)');
        drawAreaAndLine(pointsClean, '#00e5ff', blueGradient);

        // Draw Flagged Calls Area (Cyber Purple)
        const purpleGradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartH);
        purpleGradient.addColorStop(0, 'rgba(139, 92, 246, 0.35)');
        purpleGradient.addColorStop(1, 'rgba(139, 92, 246, 0.01)');
        drawAreaAndLine(pointsFlagged, '#8b5cf6', purpleGradient);
    }

    // ==========================================================================
    // 4. VOICE ANALYSIS & SYNTHETIC AUDIO DEMO (Web Audio API Synth)
    // ==========================================================================

    let currentLoadedProfile = null;
    const audioDropzone = document.getElementById('audio-dropzone');
    const audioFileInput = document.getElementById('audio-file-input');
    const btnBrowseFile = document.getElementById('btn-browse-file');
    const loadedAudioCard = document.getElementById('loaded-audio-card');
    const audioPlayer = document.getElementById('audio-player');
    const audioFilename = document.getElementById('audio-filename');
    const audioSpecs = document.getElementById('audio-specs');
    const audioStatusBadge = document.getElementById('audio-status-badge');
    const btnRunAnalysis = document.getElementById('btn-run-analysis');
    const presetButtons = document.querySelectorAll('.preset-btn');

    const analysisIdleState = document.getElementById('analysis-idle-state');
    const analysisScanningState = document.getElementById('analysis-scanning-state');
    const analysisResultContent = document.getElementById('analysis-result-content');
    const analysisErrorState = document.getElementById('analysis-error-state');
    const analysisErrorMessage = document.getElementById('analysis-error-message');
    const resultStatusTag = document.getElementById('result-status-tag');
    const scanningStatusTitle = document.getElementById('scanning-status-title');
    const scanningStatusStep = document.getElementById('scanning-status-step');
    const scanningProgressFill = document.getElementById('scanning-progress-fill');

    // AudioContext powers the local playback visualizer; it never classifies audio.
    let audioContext = null;
    let audioAnalyser = null;
    let audioSourceNode = null;
    let audioObjectUrl = null;
    let audioVisualizerFrame = null;
    let lastAudioVisualizerFrame = 0;
    let audioFrequencyData = null;
    let audioWaveformData = null;
    const audioVisualizerCanvas = document.getElementById('audio-visualizer-canvas');
    const audioVisualizerStatus = document.getElementById('audio-visualizer-status');
    const audioVisualizerCtx = audioVisualizerCanvas ? audioVisualizerCanvas.getContext('2d') : null;

    function setAnalysisUnavailable(message) {
        if (analysisIdleState) analysisIdleState.style.display = 'none';
        if (analysisScanningState) analysisScanningState.style.display = 'none';
        if (analysisResultContent) analysisResultContent.style.display = 'none';
        if (analysisErrorState) analysisErrorState.hidden = false;
        if (analysisErrorMessage) analysisErrorMessage.textContent = message;
        if (resultStatusTag) {
            resultStatusTag.textContent = 'Backend unavailable';
            resultStatusTag.className = 'badge badge-warning';
        }
    }

    function showAnalysisIdle() {
        if (analysisIdleState) analysisIdleState.style.display = '';
        if (analysisScanningState) analysisScanningState.style.display = 'none';
        if (analysisResultContent) analysisResultContent.style.display = 'none';
        if (analysisErrorState) analysisErrorState.hidden = true;
    }

    function drawAudioVisualizer() {
        if (!audioVisualizerCtx || !audioVisualizerCanvas) return;
        const { width, height } = audioVisualizerCanvas;
        const ctx = audioVisualizerCtx;
        const bars = 56;
        const gap = 3;
        const barWidth = (width - gap * (bars - 1)) / bars;
        if (audioAnalyser && !audioFrequencyData) {
            audioFrequencyData = new Uint8Array(audioAnalyser.frequencyBinCount);
            audioWaveformData = new Uint8Array(audioAnalyser.fftSize);
        }
        if (audioAnalyser && audioFrequencyData) audioAnalyser.getByteFrequencyData(audioFrequencyData);
        window.VoiceGuardScenes?.setAudioData(
            audioFrequencyData,
            Boolean(audioPlayer && !audioPlayer.paused && !audioPlayer.ended)
        );

        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = '#070916';
        ctx.fillRect(0, 0, width, height);
        for (let i = 0; i < bars; i++) {
            const decorative = 7 + (Math.sin(i * 0.62) + 1) * 13 + (Math.cos(i * 0.21) + 1) * 6;
            const audioBin = audioFrequencyData ? audioFrequencyData[Math.floor(i * audioFrequencyData.length / bars)] / 255 * (height * 0.78) : 0;
            const barHeight = Math.max(4, audioAnalyser ? audioBin : decorative);
            const x = i * (barWidth + gap);
            const y = (height - barHeight) / 2;
            const gradient = ctx.createLinearGradient(0, y, 0, y + barHeight);
            gradient.addColorStop(0, '#00f5d4');
            gradient.addColorStop(1, '#8b5cf6');
            ctx.fillStyle = gradient;
            ctx.globalAlpha = audioAnalyser ? 0.9 : 0.48;
            ctx.fillRect(x, y, barWidth, barHeight);
        }
        if (audioAnalyser && audioWaveformData) {
            audioAnalyser.getByteTimeDomainData(audioWaveformData);
            ctx.beginPath();
            ctx.lineWidth = 1.6;
            ctx.strokeStyle = '#d7caff';
            ctx.shadowColor = '#00f5d4';
            ctx.shadowBlur = 7;
            for (let i = 0; i < audioWaveformData.length; i++) {
                const x = (i / (audioWaveformData.length - 1)) * width;
                const y = (audioWaveformData[i] / 255) * height;
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();
            ctx.shadowBlur = 0;
        }
        ctx.globalAlpha = 1;
    }

    function startAudioVisualizer() {
        if (!audioPlayer || !audioVisualizerCanvas) return;
        if (!audioContext || !audioAnalyser) {
            const AudioContextConstructor = window.AudioContext || window.webkitAudioContext;
            if (!AudioContextConstructor) {
                if (audioVisualizerStatus) audioVisualizerStatus.textContent = 'Playback visualization unavailable';
                return;
            }
            try {
                audioContext = new AudioContextConstructor();
                audioAnalyser = audioContext.createAnalyser();
                audioAnalyser.fftSize = 128;
                audioSourceNode = audioContext.createMediaElementSource(audioPlayer);
                audioSourceNode.connect(audioAnalyser);
                audioAnalyser.connect(audioContext.destination);
            } catch (error) {
                console.error('Unable to initialize the audio playback visualizer:', error);
                if (audioVisualizerStatus) audioVisualizerStatus.textContent = 'Playback visualization unavailable';
                return;
            }
        }

        if (audioContext.state === 'suspended') {
            audioContext.resume().catch(error => {
                console.error('Unable to resume the audio playback visualizer:', error);
                if (audioVisualizerStatus) audioVisualizerStatus.textContent = 'Playback visualization unavailable';
            });
        }

        if (audioVisualizerStatus) audioVisualizerStatus.textContent = 'Audio playback signal · not detection output';
        const render = timestamp => {
            if (timestamp && timestamp - lastAudioVisualizerFrame < 33) {
                audioVisualizerFrame = requestAnimationFrame(render);
                return;
            }
            lastAudioVisualizerFrame = timestamp || performance.now();
            drawAudioVisualizer();
            if (audioPlayer && !audioPlayer.paused && !audioPlayer.ended) {
                audioVisualizerFrame = requestAnimationFrame(render);
            }
        };
        if (audioVisualizerFrame) cancelAnimationFrame(audioVisualizerFrame);
        render();
    }

    if (audioPlayer) {
        audioPlayer.addEventListener('play', startAudioVisualizer);
        audioPlayer.addEventListener('pause', () => {
            if (audioVisualizerFrame) cancelAnimationFrame(audioVisualizerFrame);
            audioVisualizerFrame = null;
            window.VoiceGuardScenes?.setAudioData(null, false);
            drawAudioVisualizer();
            if (audioVisualizerStatus && audioAnalyser) audioVisualizerStatus.textContent = 'Paused · local audio only';
        });
        audioPlayer.addEventListener('ended', () => {
            if (audioVisualizerFrame) cancelAnimationFrame(audioVisualizerFrame);
            audioVisualizerFrame = null;
            window.VoiceGuardScenes?.setAudioData(null, false);
            drawAudioVisualizer();
            if (audioVisualizerStatus && audioAnalyser) audioVisualizerStatus.textContent = 'Playback complete';
        });
    }

    if (audioVisualizerCanvas) drawAudioVisualizer();

    function generateSyntheticWavDataUri(type) {
        // Generate a short 3-second audible test buffer using Web Audio offline rendering
        // and convert to a playable WAV data URI
        const sampleRate = 44100;
        const duration = 3.0;
        const numSamples = sampleRate * duration;
        const buffer = new Float32Array(numSamples);

        for (let i = 0; i < numSamples; i++) {
            const t = i / sampleRate;
            if (type === 'deepfake') {
                // Unnatural robotic / vocoder buzz: multiple sharp saw-like harmonics without natural jitter
                const fundamental = 160;
                const harm1 = Math.sin(2 * Math.PI * fundamental * t);
                const harm2 = Math.sin(2 * Math.PI * (fundamental * 2) * t) * 0.5;
                const harm3 = Math.sin(2 * Math.PI * (fundamental * 3) * t) * 0.25;
                const buzz = (t % 0.05 > 0.025 ? 0.08 : -0.08); // Digital vocoder step artifact
                buffer[i] = (harm1 + harm2 + harm3 + buzz) * 0.3;
            } else if (type === 'genuine') {
                // Natural human-like speech harmonic with gentle modulation & micro-tremor
                const f0 = 125 + Math.sin(2 * Math.PI * 4 * t) * 3; // Natural subtle vibrato
                const wave = Math.sin(2 * Math.PI * f0 * t) * 0.6 + Math.sin(2 * Math.PI * (f0 * 2) * t) * 0.3;
                const breath = (Math.random() * 2 - 1) * 0.03; // Biological breath air
                buffer[i] = (wave + breath) * 0.35;
            } else {
                // Voice changer: pitch shifting grain & ring mod
                const carrier = Math.sin(2 * Math.PI * 220 * t);
                const mod = Math.sin(2 * Math.PI * 35 * t);
                buffer[i] = carrier * mod * 0.35;
            }
        }

        // Convert Float32Array to 16-bit PCM WAV blob
        return encodeWav(buffer, sampleRate);
    }

    function encodeWav(samples, sampleRate) {
        const buffer = new ArrayBuffer(44 + samples.length * 2);
        const view = new DataView(buffer);

        function writeString(view, offset, string) {
            for (let i = 0; i < string.length; i++) {
                view.setUint8(offset + i, string.charCodeAt(i));
            }
        }

        /* RIFF identifier */
        writeString(view, 0, 'RIFF');
        /* RIFF chunk length */
        view.setUint32(4, 36 + samples.length * 2, true);
        /* RIFF type */
        writeString(view, 8, 'WAVE');
        /* format chunk identifier */
        writeString(view, 12, 'fmt ');
        /* format chunk length */
        view.setUint32(16, 16, true);
        /* sample format (raw) */
        view.setUint16(20, 1, true);
        /* channel count */
        view.setUint16(22, 1, true);
        /* sample rate */
        view.setUint32(24, sampleRate, true);
        /* byte rate (sample rate * block align) */
        view.setUint32(28, sampleRate * 2, true);
        /* block align (channel count * bytes per sample) */
        view.setUint16(32, 2, true);
        /* bits per sample */
        view.setUint16(34, 16, true);
        /* data chunk identifier */
        writeString(view, 36, 'data');
        /* data chunk length */
        view.setUint32(40, samples.length * 2, true);

        // Write the PCM samples
        let offset = 44;
        for (let i = 0; i < samples.length; i++, offset += 2) {
            const s = Math.max(-1, Math.min(1, samples[i]));
            view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        }

        const blob = new Blob([view], { type: 'audio/wav' });
        return URL.createObjectURL(blob);
    }

    function loadAudioProfile(profile) {
        if (audioObjectUrl) URL.revokeObjectURL(audioObjectUrl);
        currentLoadedProfile = profile;
        audioObjectUrl = generateSyntheticWavDataUri(profile.synthType);

        const profileState = profile.verdictClass === 'danger' ? 'high-risk' : (profile.verdictClass === 'success' ? 'safe' : 'suspicious');
        window.VoiceGuardScenes?.setSecurityState(profileState);

        audioPlayer.src = audioObjectUrl;

        audioFilename.textContent = profile.fileName;
        audioSpecs.textContent = profile.specs;
        audioStatusBadge.textContent = 'Preset Demo';
        audioStatusBadge.className = 'badge badge-purple';
        loadedAudioCard.style.display = 'block';

        btnRunAnalysis.disabled = false;
        if (analysisErrorState) analysisErrorState.hidden = true;
        if (analysisResultContent) analysisResultContent.style.display = 'none';
        if (analysisIdleState) analysisIdleState.style.display = 'block';
        resultStatusTag.textContent = 'Preset demo ready';
        resultStatusTag.className = 'badge badge-purple';

        showToast(`Loaded demo preset: ${profile.fileName}. Results are illustrative only.`, 'info');
    }

    // Handle Preset Click
    presetButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const presetKey = btn.getAttribute('data-preset');
            const profile = SAMPLE_DATA.forensicProfiles[presetKey];
            if (profile) {
                loadAudioProfile(profile);
            }
        });
    });

    // Handle Local File Upload
    if (btnBrowseFile) {
        btnBrowseFile.addEventListener('click', () => audioFileInput.click());
    }

    if (audioDropzone) {
        audioDropzone.addEventListener('click', (e) => {
            if (e.target !== btnBrowseFile) {
                audioFileInput.click();
            }
        });

        audioDropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            audioDropzone.classList.add('drag-over');
        });

        audioDropzone.addEventListener('dragleave', () => {
            audioDropzone.classList.remove('drag-over');
        });

        audioDropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            audioDropzone.classList.remove('drag-over');
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                handleUploadedFile(e.dataTransfer.files[0]);
            }
        });
    }

    if (audioFileInput) {
        audioFileInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleUploadedFile(e.target.files[0]);
            }
        });
    }

    const startRecordingButton = document.getElementById('btn-start-recording');
    const stopRecordingButton = document.getElementById('btn-stop-recording');
    const microphoneStatus = document.getElementById('microphone-status');
    let activeRecorder = null;
    let activeMicrophoneStream = null;
    let recordingChunks = [];
    let recordingTimeout = null;
    let discardRecording = false;
    let microphoneRequestId = 0;

    async function startMicrophoneRecording() {
        if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
            if (microphoneStatus) microphoneStatus.textContent = 'Microphone recording is not supported in this browser. Use HTTPS or localhost.';
            return;
        }
        if (startRecordingButton) startRecordingButton.disabled = true;
        const requestId = ++microphoneRequestId;
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            if (requestId !== microphoneRequestId || !document.getElementById('view-analysis')?.classList.contains('active')) {
                stream.getTracks().forEach(track => track.stop());
                return;
            }
            activeMicrophoneStream = stream;
            const preferredMime = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus']
                .find(type => MediaRecorder.isTypeSupported(type));
            activeRecorder = new MediaRecorder(activeMicrophoneStream, preferredMime ? { mimeType: preferredMime } : undefined);
            recordingChunks = [];
            activeRecorder.addEventListener('dataavailable', event => {
                if (event.data.size) recordingChunks.push(event.data);
            });
            activeRecorder.addEventListener('error', event => {
                console.error('Microphone recording failed:', event.error);
                if (microphoneStatus) microphoneStatus.textContent = 'Recording failed. Check microphone permissions and try again.';
                stopMicrophoneRecording(false);
            });
            activeRecorder.addEventListener('stop', () => {
                const blob = new Blob(recordingChunks, { type: activeRecorder.mimeType || 'audio/webm' });
                recordingChunks = [];
                activeMicrophoneStream?.getTracks().forEach(track => track.stop());
                activeMicrophoneStream = null;
                activeRecorder = null;
                if (!discardRecording && blob.size) {
                    const extension = blob.type.includes('ogg') ? 'ogg' : 'webm';
                    handleUploadedFile(new File([blob], `voice-recording.${extension}`, { type: blob.type }));
                    if (microphoneStatus) microphoneStatus.textContent = 'Recording saved locally for playback. Detection is unavailable without an inference backend.';
                }
                discardRecording = false;
                if (startRecordingButton) startRecordingButton.disabled = false;
                if (stopRecordingButton) stopRecordingButton.disabled = true;
            }, { once: true });
            activeRecorder.start();
            if (startRecordingButton) startRecordingButton.disabled = true;
            if (stopRecordingButton) stopRecordingButton.disabled = false;
            if (microphoneStatus) microphoneStatus.textContent = 'Recording locally… maximum duration 60 seconds.';
            recordingTimeout = setTimeout(() => stopMicrophoneRecording(), 60_000);
        } catch (error) {
            console.error('Unable to access the microphone:', error);
            activeMicrophoneStream?.getTracks().forEach(track => track.stop());
            activeMicrophoneStream = null;
            if (startRecordingButton) startRecordingButton.disabled = false;
            if (microphoneStatus) microphoneStatus.textContent = 'Microphone permission was denied or unavailable. You can upload an audio file instead.';
            showToast('Microphone access was not granted. No audio was recorded.', 'warning');
        }
    }

    function stopMicrophoneRecording(finalize = true) {
        microphoneRequestId++;
        if (recordingTimeout) clearTimeout(recordingTimeout);
        recordingTimeout = null;
        if (activeRecorder && activeRecorder.state !== 'inactive') {
            discardRecording = !finalize;
            activeRecorder.stop();
            if (!finalize) recordingChunks = [];
        } else {
            activeMicrophoneStream?.getTracks().forEach(track => track.stop());
            activeMicrophoneStream = null;
            if (startRecordingButton) startRecordingButton.disabled = false;
            if (stopRecordingButton) stopRecordingButton.disabled = true;
        }
    }

    startRecordingButton?.addEventListener('click', startMicrophoneRecording);
    stopRecordingButton?.addEventListener('click', () => stopMicrophoneRecording());
    window.addEventListener('pagehide', () => stopMicrophoneRecording(false));

    function rejectUploadedAudio(message) {
        currentLoadedProfile = null;
        if (audioObjectUrl) {
            URL.revokeObjectURL(audioObjectUrl);
            audioObjectUrl = null;
        }
        if (audioPlayer) {
            audioPlayer.pause();
            audioPlayer.removeAttribute('src');
            audioPlayer.load();
        }
        if (loadedAudioCard) loadedAudioCard.style.display = 'none';
        if (audioFileInput) audioFileInput.value = '';
        if (btnRunAnalysis) btnRunAnalysis.disabled = true;
        setAnalysisUnavailable(message);
        showToast(message, 'warning');
    }

    function handleUploadedFile(file) {
        const supportedAudioExtension = /\.(wav|mp3|flac|ogg|m4a|aac|webm|opus|mpeg|mpg)$/i.test(file.name);
        if (!file.type.startsWith('audio/') && !file.type.includes('mpeg') && !supportedAudioExtension) {
            rejectUploadedAudio('Choose a supported audio file (.wav, .mp3, .mpeg, .mpg, .flac, .ogg, .m4a, .aac, or .webm).');
            return;
        }

        if (file.size > 25 * 1024 * 1024) {
            rejectUploadedAudio('Audio files must be 25 MB or smaller.');
            return;
        }

        if (audioObjectUrl) URL.revokeObjectURL(audioObjectUrl);
        audioObjectUrl = URL.createObjectURL(file);
        audioPlayer.src = audioObjectUrl;
        currentLoadedProfile = null;

        audioFilename.textContent = file.name;
        audioSpecs.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB • ${file.type || 'audio file'} • Local playback`;
        audioStatusBadge.textContent = 'Local Only';
        audioStatusBadge.className = 'badge badge-warning';
        loadedAudioCard.style.display = 'block';
        btnRunAnalysis.disabled = false;
        showAnalysisIdle();
        setAnalysisUnavailable('This audio is available for local playback only. No AI inference backend is configured, so VoiceGuard cannot provide a genuine detection score.');
        if (audioVisualizerStatus) audioVisualizerStatus.textContent = 'Ready · visualization follows local playback only';
        showToast('Audio loaded locally. Detection is unavailable without an inference backend.', 'warning');
    }

    // Run Deep Voice Analysis Workflow
    if (btnRunAnalysis) {
        btnRunAnalysis.addEventListener('click', () => {
            if (!currentLoadedProfile) {
                setAnalysisUnavailable('No AI inference backend is connected. This upload can be played locally, but it cannot be classified here.');
                return;
            }

            btnRunAnalysis.disabled = true;
            analysisIdleState.style.display = 'none';
            if (analysisErrorState) analysisErrorState.hidden = true;
            analysisResultContent.style.display = 'none';
            analysisScanningState.style.display = 'block';

            resultStatusTag.textContent = 'Running preset demo...';
            resultStatusTag.className = 'badge badge-warning';

            const steps = [
                { pct: 25, title: 'Loading sample profile...', step: 'Preset demonstration · no audio inference' },
                { pct: 55, title: 'Rendering illustrative signal metrics...', step: 'Values are fixed sample data' },
                { pct: 85, title: 'Preparing demonstration summary...', step: 'No backend or risk engine is connected' },
                { pct: 100, title: 'Preset demonstration complete', step: 'Not an AI classification' }
            ];

            let stepIndex = 0;
            const interval = setInterval(() => {
                if (stepIndex < steps.length) {
                    const current = steps[stepIndex];
                    scanningProgressFill.style.width = `${current.pct}%`;
                    scanningStatusTitle.textContent = current.title;
                    scanningStatusStep.textContent = current.step;
                    stepIndex++;
                } else {
                    clearInterval(interval);
                    setTimeout(displayAnalysisResults, 300);
                }
            }, 400);
        });
    }

    function displayAnalysisResults() {
        analysisScanningState.style.display = 'none';
        analysisResultContent.style.display = 'block';
        btnRunAnalysis.disabled = false;

        const p = currentLoadedProfile;
        resultStatusTag.textContent = p.verdictClass === 'danger' ? 'Demo: High Risk' : (p.verdictClass === 'success' ? 'Demo: Verified Safe' : 'Demo: Suspicious');
        resultStatusTag.className = `badge badge-${p.verdictClass}`;

        const securityState = p.verdictClass === 'danger' ? 'high-risk' : (p.verdictClass === 'success' ? 'safe' : 'suspicious');
        window.VoiceGuardScenes?.setSecurityState(securityState);

        // Verdict Banner
        const verdictBanner = document.getElementById('verdict-banner');
        const verdictHeading = document.getElementById('verdict-heading');
        const verdictSummary = document.getElementById('verdict-summary');
        const verdictScoreVal = document.getElementById('verdict-score-val');
        const verdictIcon = document.getElementById('verdict-icon');

        verdictBanner.className = `verdict-banner ${p.verdictClass}`;
        verdictHeading.textContent = p.verdict;
        verdictSummary.textContent = p.summary;
        verdictScoreVal.textContent = p.probability;

        if (p.verdictClass === 'danger') {
            verdictIcon.innerHTML = `
        <svg viewBox="0 0 24 24" width="36" height="36" stroke="#ef4444" stroke-width="2" fill="none">
          <polygon points="12 2 2 22 22 22 12 2"></polygon>
          <line x1="12" y1="9" x2="12" y2="13"></line>
          <line x1="12" y1="17" x2="12.01" y2="17"></line>
        </svg>
      `;
        } else if (p.verdictClass === 'success') {
            verdictIcon.innerHTML = `
        <svg viewBox="0 0 24 24" width="36" height="36" stroke="#10b981" stroke-width="2" fill="none">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
          <polyline points="9 12 11 14 15 10"></polyline>
        </svg>
      `;
        } else {
            verdictIcon.innerHTML = `
        <svg viewBox="0 0 24 24" width="36" height="36" stroke="#f59e0b" stroke-width="2" fill="none">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
      `;
        }

        // Acoustic Metrics
        document.getElementById('metric-vocoder-val').textContent = p.vocoder.val;
        const meterVocoder = document.getElementById('meter-vocoder');
        meterVocoder.style.width = p.vocoder.width;
        meterVocoder.className = `meter-bar ${p.vocoder.class}`;

        document.getElementById('metric-pitch-val').textContent = p.pitch.val;
        const meterPitch = document.getElementById('meter-pitch');
        meterPitch.style.width = p.pitch.width;
        meterPitch.className = `meter-bar ${p.pitch.class}`;

        document.getElementById('metric-spectral-val').textContent = p.spectral.val;
        const meterSpectral = document.getElementById('meter-spectral');
        meterSpectral.style.width = p.spectral.width;
        meterSpectral.className = `meter-bar ${p.spectral.class}`;

        document.getElementById('metric-breath-val').textContent = p.breath.val;
        const meterBreath = document.getElementById('meter-breath');
        meterBreath.style.width = p.breath.width;
        meterBreath.className = `meter-bar ${p.breath.class}`;

        // Attributed Architecture & Action Protocol
        document.getElementById('sig-model-name').textContent = p.modelAttribution;
        document.getElementById('sig-details').textContent = p.modelDetails;
        document.getElementById('rec-text').textContent = p.recommendation;

        showToast(`Analysis complete: ${p.verdict}`, p.verdictClass === 'danger' ? 'danger' : 'success');
    }

    // ==========================================================================
    // 5. LIVE AUDIO MONITORING IS INITIALIZED BY app-controller.js
    // ==========================================================================

    document.querySelectorAll('.fraud-simulation-action').forEach(button => {
        button.addEventListener('click', () => {
            showToast(`${button.getAttribute('data-action')} is a simulation only; no transaction or identity service is connected.`, 'warning');
        });
    });

    // ==========================================================================
    // 6. ZERO-TRUST SPEAKER BIOMETRICS & VOICEPRINT VAULT
    // ==========================================================================

    const speakerRegisterForm = document.getElementById('speaker-register-form');
    const regVoiceUploadBox = document.getElementById('reg-voice-upload-box');
    const regVoiceInput = document.getElementById('reg-voice-input');
    const regFileLabel = document.getElementById('reg-file-label');
    const verifyTargetSpeaker = document.getElementById('verify-target-speaker');
    const enrolledSpeakersTable = document.getElementById('enrolled-speakers-table');
    const enrolledCountBadge = document.getElementById('enrolled-count-badge');

    const verifyVoiceUploadBox = document.getElementById('verify-voice-upload-box');
    const verifyVoiceInput = document.getElementById('verify-voice-input');
    const verifyFileLabel = document.getElementById('verify-file-label');
    const btnRunVerification = document.getElementById('btn-run-verification');
    const btnTestMatch = document.getElementById('btn-test-match');
    const btnTestSpoof = document.getElementById('btn-test-spoof');
    const verificationResultBox = document.getElementById('verification-result-box');

    // Populate Target Speaker Dropdown
    function refreshTargetSpeakerDropdown() {
        if (!verifyTargetSpeaker) return;
        verifyTargetSpeaker.innerHTML = '';
        SAMPLE_DATA.enrolledSpeakers.forEach(s => {
            const option = document.createElement('option');
            option.value = s.id;
            option.textContent = `${s.id} — ${s.name} (${s.dept})`;
            verifyTargetSpeaker.appendChild(option);
        });
    }

    // Populate Enrolled Speakers Table
    function populateEnrolledSpeakersTable() {
        if (!enrolledSpeakersTable) return;
        enrolledSpeakersTable.innerHTML = '';

        SAMPLE_DATA.enrolledSpeakers.forEach(spk => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
        <td class="mono-cell"><strong>${spk.id}</strong></td>
        <td><strong>${spk.name}</strong></td>
        <td>${spk.dept}</td>
        <td><span class="badge badge-purple">${spk.clearance}</span></td>
        <td class="mono-cell">${spk.hash}</td>
        <td class="mono-cell">${spk.enrolledDate}</td>
        <td class="mono-cell">${spk.verifiedCalls}</td>
        <td><span class="badge ${spk.status === 'Sample' ? 'badge-info' : 'badge-purple'}">${spk.status}</span></td>
      `;
            enrolledSpeakersTable.appendChild(tr);
        });

        if (enrolledCountBadge) {
            enrolledCountBadge.textContent = `${SAMPLE_DATA.enrolledSpeakers.length} Sample Profiles`;
        }
    }

    // Handle Voice Registration File Upload Trigger
    if (regVoiceUploadBox && regVoiceInput) {
        regVoiceUploadBox.addEventListener('click', () => regVoiceInput.click());
        regVoiceInput.addEventListener('change', () => {
            if (regVoiceInput.files && regVoiceInput.files.length > 0) {
                regFileLabel.textContent = `Attached: ${regVoiceInput.files[0].name}`;
            }
        });
    }

    // Enroll New Speaker Voiceprint
    if (speakerRegisterForm) {
        speakerRegisterForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const name = document.getElementById('reg-name').value.trim();
            const id = document.getElementById('reg-id').value.trim();
            const dept = document.getElementById('reg-dept').value;
            const clearance = document.getElementById('reg-clearance').value;

            if (!name || !id) {
                showToast('Please fill out all required fields.', 'warning');
                return;
            }

            // Check for duplicate ID
            if (SAMPLE_DATA.enrolledSpeakers.some(s => s.id.toLowerCase() === id.toLowerCase())) {
                showToast(`Speaker with ID ${id} already exists in the vault.`, 'warning');
                return;
            }

            const now = new Date().toISOString().split('T')[0];

            const newSpeaker = {
                id: id,
                name: name,
                dept: dept,
                clearance: clearance,
                hash: 'DEMO ONLY · NO EMBEDDING',
                enrolledDate: now,
                verifiedCalls: 0,
                status: 'Demo only'
            };

            SAMPLE_DATA.enrolledSpeakers.unshift(newSpeaker);
            populateEnrolledSpeakersTable();
            refreshTargetSpeakerDropdown();
            speakerRegisterForm.reset();
            regFileLabel.textContent = 'Choose sample audio (.wav / .mp3)';

            showToast(`Added ${name} (${id}) to this browser's demo list. No biometric voiceprint was created.`, 'info');
        });
    }

    // Verification File Selection
    if (verifyVoiceUploadBox && verifyVoiceInput) {
        verifyVoiceUploadBox.addEventListener('click', () => verifyVoiceInput.click());
        verifyVoiceInput.addEventListener('change', () => {
            if (verifyVoiceInput.files && verifyVoiceInput.files.length > 0) {
                verifyFileLabel.textContent = `Attached: ${verifyVoiceInput.files[0].name}`;
                simulatedVerifyType = null;
                showVerificationUnavailable('This file cannot be verified because no biometric identity backend is connected. Use a labeled sandbox scenario to preview the interface.');
            }
        });
    }

    // Quick Preset Test Buttons
    let simulatedVerifyType = null;
    if (btnTestMatch) {
        btnTestMatch.addEventListener('click', () => {
            simulatedVerifyType = 'match';
            verifyFileLabel.textContent = 'Loaded: genuine_exec_verification.wav';
            executeVerification(true);
        });
    }

    if (btnTestSpoof) {
        btnTestSpoof.addEventListener('click', () => {
            simulatedVerifyType = 'spoof';
            verifyFileLabel.textContent = 'Loaded: zero_shot_clone_attempt.wav';
            executeVerification(true);
        });
    }

    const speakerVerifyForm = document.getElementById('speaker-verify-form');
    if (speakerVerifyForm) {
        speakerVerifyForm.addEventListener('submit', (e) => {
            e.preventDefault();
            if (btnRunVerification) btnRunVerification.click();
        });
    }

    if (btnRunVerification) {
        btnRunVerification.addEventListener('click', () => {
            showVerificationUnavailable(verifyVoiceInput && verifyVoiceInput.files.length
                ? 'This file cannot be verified because no biometric identity backend is connected.'
                : 'No verification service is connected. Uploads are not compared to the sample vault; use a labeled sandbox scenario to preview the interface.');
        });
    }

    function showVerificationUnavailable(message) {
        const verifyStatusBadge = document.getElementById('verify-status-badge');
        const verifySimilarityVal = document.getElementById('verify-similarity-val');
        const verifyLivenessVal = document.getElementById('verify-liveness-val');
        const verifyDecisionVal = document.getElementById('verify-decision-val');
        const verifyNarrative = document.getElementById('verify-narrative');
        const verifyTime = document.getElementById('verify-time');
        if (verifyStatusBadge) {
            verifyStatusBadge.textContent = 'BACKEND UNAVAILABLE';
            verifyStatusBadge.className = 'badge badge-warning';
        }
        if (verifySimilarityVal) verifySimilarityVal.textContent = '—';
        if (verifyLivenessVal) verifyLivenessVal.textContent = '—';
        if (verifyDecisionVal) verifyDecisionVal.textContent = 'NOT VERIFIED';
        if (verifyNarrative) verifyNarrative.textContent = message;
        if (verifyTime) verifyTime.textContent = 'No real verification performed';
        if (verificationResultBox) verificationResultBox.style.display = 'block';
    }

    function executeVerification(isDemo = false) {
        if (!isDemo || !simulatedVerifyType) {
            showVerificationUnavailable('No verification service is connected. Uploaded audio is not compared to the sample vault.');
            return;
        }
        const selectedId = verifyTargetSpeaker ? verifyTargetSpeaker.value : 'EMP-4012';
        const speaker = SAMPLE_DATA.enrolledSpeakers.find(s => s.id === selectedId) || SAMPLE_DATA.enrolledSpeakers[0];

        const verifyStatusBadge = document.getElementById('verify-status-badge');
        const verifySimilarityVal = document.getElementById('verify-similarity-val');
        const verifyLivenessVal = document.getElementById('verify-liveness-val');
        const verifyDecisionVal = document.getElementById('verify-decision-val');
        const verifyNarrative = document.getElementById('verify-narrative');
        const verifyTime = document.getElementById('verify-time');

        if (verifyTime) {
            verifyTime.textContent = new Date().toLocaleTimeString();
        }

        if (simulatedVerifyType === 'match') {
            const shield = document.querySelector('.identity-shield');
            if (shield) {
                shield.classList.remove('shield-threat');
                shield.classList.add('shield-safe');
            }
            verifyStatusBadge.textContent = 'DEMO MATCH (SIMULATED)';
            verifyStatusBadge.className = 'badge badge-purple';
            verifySimilarityVal.textContent = '98.4%';
            verifySimilarityVal.className = 'v-val text-success';
            verifyLivenessVal.textContent = 'PASSED (96%)';
            verifyLivenessVal.className = 'v-val text-success';
            verifyDecisionVal.textContent = 'DEMO ONLY';
            verifyDecisionVal.className = 'v-val text-info';
            verifyNarrative.textContent = `Illustrative match scenario for ${speaker.id} (${speaker.name}). No biometric comparison or authentication occurred.`;
            showToast('Sandbox match scenario only. No speaker was authenticated.', 'info');
        } else {
            const shield = document.querySelector('.identity-shield');
            if (shield) {
                shield.classList.remove('shield-safe');
                shield.classList.add('shield-threat');
            }
            verifyStatusBadge.textContent = 'DEMO SPOOF (SIMULATED)';
            verifyStatusBadge.className = 'badge badge-warning';
            verifySimilarityVal.textContent = '41.2%';
            verifySimilarityVal.className = 'v-val text-danger';
            verifyLivenessVal.textContent = 'FAILED (12%)';
            verifyLivenessVal.className = 'v-val text-danger';
            verifyDecisionVal.textContent = 'DEMO ONLY';
            verifyDecisionVal.className = 'v-val text-warning';
            verifyNarrative.textContent = `Illustrative spoof scenario for ${speaker.id} (${speaker.name}). No biometric comparison or access decision occurred.`;
            showToast('Sandbox spoof scenario only. No impersonation was detected.', 'info');
        }

        verificationResultBox.style.display = 'block';
    }

    // ==========================================================================
    // 7. THREAT INTELLIGENCE & INCIDENT TABLE SEARCH/FILTER
    // ==========================================================================

    const threatTable = document.getElementById('threat-intelligence-table');
    const threatSearchInput = document.getElementById('threat-search-input');
    const threatFilterPills = document.querySelectorAll('#threat-filter-pills .filter-pill');
    const threatCountBadge = document.getElementById('threat-count-badge');
    const threatTableSubtitle = document.getElementById('threat-table-subtitle');

    let currentRiskFilter = 'all';
    let currentSearchQuery = '';

    function renderThreatTable() {
        if (!threatTable) return;
        threatTable.innerHTML = '';

        const filtered = SAMPLE_DATA.threatIncidents.filter(item => {
            // Risk filter
            const matchesRisk = (currentRiskFilter === 'all') || (item.risk.toLowerCase() === currentRiskFilter.toLowerCase());
            // Search query
            const matchesSearch = !currentSearchQuery ||
                item.id.toLowerCase().includes(currentSearchQuery) ||
                item.origin.toLowerCase().includes(currentSearchQuery) ||
                item.target.toLowerCase().includes(currentSearchQuery) ||
                item.vector.toLowerCase().includes(currentSearchQuery);

            return matchesRisk && matchesSearch;
        });

        if (filtered.length === 0) {
            threatTable.innerHTML = `
        <tr>
          <td colspan="9" style="text-align: center; padding: 2.5rem; color: var(--text-muted);">
            No threat incidents match the selected filter criteria.
          </td>
        </tr>
      `;
            if (threatCountBadge) threatCountBadge.textContent = '0 Incidents';
            return;
        }

        filtered.forEach(item => {
            const tr = document.createElement('tr');
            const badgeClass = item.risk === 'Critical' ? 'badge-danger' : (item.risk === 'High' ? 'badge-warning' : 'badge-info');

            tr.innerHTML = `
        <td class="mono-cell"><strong>${item.id}</strong></td>
        <td class="mono-cell">${item.timestamp}</td>
        <td>${item.origin}</td>
        <td><strong>${item.target}</strong></td>
        <td><span class="text-secondary">${item.vector}</span></td>
        <td><span class="badge ${badgeClass}">${item.risk}</span></td>
        <td class="mono-cell"><strong class="text-primary">${item.confidence}</strong></td>
        <td><span class="text-secondary">${item.action}</span></td>
        <td>
          <button class="btn btn-outline btn-sm btn-forensic-inspect" data-id="${item.id}">Inspect</button>
        </td>
      `;
            threatTable.appendChild(tr);
        });

        if (threatCountBadge) {
            threatCountBadge.textContent = `${filtered.length} Incidents Logged`;
        }

        // Attach inspect modal click handlers
        threatTable.querySelectorAll('.btn-forensic-inspect').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.getAttribute('data-id');
                openForensicModal(id);
            });
        });
    }

    // Search input handler
    if (threatSearchInput) {
        threatSearchInput.addEventListener('input', (e) => {
            currentSearchQuery = e.target.value.toLowerCase().trim();
            renderThreatTable();
        });
    }

    // Filter pills handler
    threatFilterPills.forEach(pill => {
        pill.addEventListener('click', () => {
            threatFilterPills.forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            currentRiskFilter = pill.getAttribute('data-filter');
            renderThreatTable();
        });
    });

    // Modal inspection dialog
    const forensicModal = document.getElementById('forensic-modal');
    const modalIncidentId = document.getElementById('modal-incident-id');
    const modalRiskBadge = document.getElementById('modal-risk-badge');
    const modalBodyContent = document.getElementById('modal-body-content');
    const modalCloseBtn = document.getElementById('modal-close-btn');
    const modalBtnDismiss = document.getElementById('modal-btn-dismiss');
    const modalBtnDownload = document.getElementById('modal-btn-download');

    function openForensicModal(incidentId) {
        const item = SAMPLE_DATA.threatIncidents.find(t => t.id === incidentId);
        if (!item) return;

        modalIncidentId.textContent = `INCIDENT #${item.id}`;
        modalRiskBadge.textContent = `${item.risk.toUpperCase()} THREAT`;
        modalRiskBadge.className = `badge ${item.risk === 'Critical' ? 'badge-danger' : (item.risk === 'High' ? 'badge-warning' : 'badge-info')}`;

        modalBodyContent.innerHTML = `
      <div class="incident-detail-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.25rem;">
        <div>
          <span class="form-label">SAMPLE TIMESTAMP</span>
          <p class="mono-cell text-primary">${item.timestamp}</p>
        </div>
        <div>
          <span class="form-label">INBOUND TRUNK / GEO-CLAIM</span>
          <p class="mono-cell text-primary">${item.origin}</p>
        </div>
        <div>
          <span class="form-label">TARGETED ENTERPRISE LINE</span>
          <p class="text-primary"><strong>${item.target}</strong></p>
        </div>
        <div>
          <span class="form-label">SAMPLE CONFIDENCE</span>
            <p class="mono-cell text-danger"><strong>${item.confidence} · illustrative value</strong></p>
        </div>
      </div>

      <div style="margin-bottom: 1rem; padding: 1rem; background-color: var(--bg-surface); border: 1px solid var(--border-default); border-radius: var(--radius-sm);">
        <span class="form-label">ATTACK VECTOR CLASSIFICATION</span>
        <h4 style="color: var(--blue-primary); margin: 0.25rem 0;">${item.vector}</h4>
        <p style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.4;">${item.details}</p>
      </div>

      <div style="padding: 1rem; background-color: var(--color-danger-bg); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: var(--radius-sm);">
        <span class="form-label" style="color: var(--color-danger);">SAMPLE RESPONSE</span>
        <p style="color: var(--text-primary); font-weight: 600;">${item.action}</p>
        <p style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem;">Illustrative incident detail only. No enforcement action, recording, or SIEM event exists.</p>
      </div>
    `;

        forensicModal.style.display = 'flex';
    }

    function closeForensicModal() {
        forensicModal.style.display = 'none';
    }

    if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeForensicModal);
    if (modalBtnDismiss) modalBtnDismiss.addEventListener('click', closeForensicModal);
    if (modalBtnDownload) {
        modalBtnDownload.addEventListener('click', () => {
            showToast('No PCAP is available; this is an illustrative sample incident.', 'warning');
        });
    }

    // ==========================================================================
    // 8. REPORTS, COMPLIANCE AUDIT & CSV EXPORT
    // ==========================================================================

    // Canvas 2: Threat Vector Distribution Donut Chart
    function renderRiskDonutChart() {
        const canvas = document.getElementById('risk-donut-canvas');
        if (!canvas) return;

        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        if (rect.width <= 20 || rect.height <= 20) return;
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;

        const ctx = canvas.getContext('2d');
        ctx.scale(dpr, dpr);
        const width = rect.width;
        const height = rect.height;

        ctx.clearRect(0, 0, width, height);

        const centerX = width / 2;
        const centerY = height / 2;
        const outerRadius = Math.min(centerX, centerY) - 10;
        const innerRadius = outerRadius * 0.65;

        const data = SAMPLE_DATA.riskDistribution;
        const total = data.reduce((acc, cur) => acc + cur.count, 0);

        let startAngle = -Math.PI / 2;

        data.forEach(slice => {
            const sliceAngle = (slice.count / total) * (Math.PI * 2);
            ctx.beginPath();
            ctx.arc(centerX, centerY, outerRadius, startAngle, startAngle + sliceAngle);
            ctx.arc(centerX, centerY, innerRadius, startAngle + sliceAngle, startAngle, true);
            ctx.closePath();
            ctx.fillStyle = slice.color;
            ctx.fill();
            ctx.strokeStyle = '#070b14';
            ctx.lineWidth = 2;
            ctx.stroke();

            startAngle += sliceAngle;
        });

        // Center text in Donut
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = '#f1f5f9';
        ctx.font = 'bold 20px JetBrains Mono, monospace';
        ctx.fillText('100%', centerX, centerY - 6);
        ctx.fillStyle = '#64748b';
        ctx.font = '10px Inter, sans-serif';
        ctx.fillText('EXPLOITS', centerX, centerY + 12);

        // Populate Legend
        const legendEl = document.getElementById('donut-legend');
        if (legendEl) {
            legendEl.innerHTML = '';
            data.forEach(item => {
                const row = document.createElement('div');
                row.className = 'donut-legend-item';
                row.innerHTML = `
          <div class="donut-color-box" style="background-color: ${item.color};"></div>
          <span class="donut-lbl">${item.label}</span>
          <span class="donut-pct">${item.count}%</span>
        `;
                legendEl.appendChild(row);
            });
        }
    }

    // Canvas 3: Weekly Protocol Volume Bar Chart
    function renderWeeklyVolumeChart() {
        const canvas = document.getElementById('weekly-volume-canvas');
        if (!canvas) return;

        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;

        const ctx = canvas.getContext('2d');
        ctx.scale(dpr, dpr);
        const width = rect.width;
        const height = rect.height;

        ctx.clearRect(0, 0, width, height);

        const padding = { top: 20, right: 20, bottom: 30, left: 45 };
        const chartW = width - padding.left - padding.right;
        const chartH = height - padding.top - padding.bottom;

        const data = SAMPLE_DATA.weeklyProtocolVolume;
        const maxVal = 3500;

        // Draw horizontal grid lines
        ctx.strokeStyle = '#1e2f54';
        ctx.lineWidth = 1;
        ctx.fillStyle = '#64748b';
        ctx.font = '10px JetBrains Mono, monospace';
        ctx.textAlign = 'right';

        for (let i = 0; i <= 4; i++) {
            const yVal = Math.round((maxVal / 4) * i);
            const yPos = padding.top + chartH - (i / 4) * chartH;
            ctx.beginPath();
            ctx.moveTo(padding.left, yPos);
            ctx.lineTo(padding.left + chartW, yPos);
            ctx.stroke();
            ctx.fillText(yVal, padding.left - 8, yPos + 3);
        }

        // Draw Bars
        const groupWidth = chartW / data.length;
        const barWidth = 14;

        data.forEach((d, i) => {
            const groupX = padding.left + i * groupWidth + (groupWidth - barWidth * 2 - 4) / 2;

            // Bar 1: SIP (Electric Blue)
            const h1 = (d.sip / maxVal) * chartH;
            const y1 = padding.top + chartH - h1;
            ctx.fillStyle = '#00e5ff';
            ctx.fillRect(groupX, y1, barWidth, h1);

            // Bar 2: WebRTC (Purple)
            const h2 = (d.webrtc / maxVal) * chartH;
            const y2 = padding.top + chartH - h2;
            ctx.fillStyle = '#8b5cf6';
            ctx.fillRect(groupX + barWidth + 4, y2, barWidth, h2);

            // Label Day
            ctx.fillStyle = '#94a3b8';
            ctx.textAlign = 'center';
            ctx.fillText(d.day, groupX + barWidth + 2, height - 10);
        });
    }

    // Populate Compliance Audit Log Table
    function populateComplianceLogTable() {
        const table = document.getElementById('compliance-log-table');
        if (!table) return;
        table.innerHTML = '';

        SAMPLE_DATA.complianceLog.forEach(log => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
        <td class="mono-cell"><strong>${log.id}</strong></td>
        <td><span class="badge badge-purple">${log.type}</span></td>
        <td>${log.user}</td>
        <td>${log.resource}</td>
        <td><strong class="text-success">${log.status}</strong></td>
        <td class="mono-cell">${log.hash.substring(0, 16)}...</td>
      `;
            table.appendChild(tr);
        });
    }

    async function exportAccountReportCSV(triggerButton) {
        if (triggerButton) triggerButton.disabled = true;
        try {
            const csv = await window.VoiceGuardAPI.exportReportsCsv();
            if (typeof csv !== 'string') throw new Error('The report service returned an invalid response.');

            const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
            const link = document.createElement('a');
            link.href = url;
            link.download = 'voiceguard-forensic-report.csv';
            document.body.append(link);
            link.click();
            link.remove();
            window.setTimeout(() => URL.revokeObjectURL(url), 1000);
            showToast('Downloaded your account forensic report.', 'success');
        } catch (error) {
            console.error('[VoiceGuardApp] Unable to export account report:', error);
            showToast(error.message || 'The account report could not be exported.', 'error');
        } finally {
            if (triggerButton) triggerButton.disabled = false;
        }
    }

    const btnExportThreats = document.getElementById('btn-export-threats');
    if (btnExportThreats) btnExportThreats.addEventListener('click', () => exportAccountReportCSV(btnExportThreats));

    const btnExportQuick = document.getElementById('btn-export-quick');
    if (btnExportQuick) btnExportQuick.addEventListener('click', () => exportAccountReportCSV(btnExportQuick));

    const btnGenerateReport = document.getElementById('btn-generate-report');
    if (btnGenerateReport) {
        btnGenerateReport.addEventListener('click', () => exportAccountReportCSV(btnGenerateReport));
    }

    // ==========================================================================
    // 9. INITIALIZATION
    // ==========================================================================

    function initApp() {
        document.body.classList.add('motion-ready');
        // 1. Check initial URL hash or default to overview
        const initialHash = window.location.hash.replace('#', '');
        if (initialHash && VIEW_TITLES[initialHash]) {
            switchView(initialHash);
        } else {
            switchView('overview');
        }

        // 2. Populate static data tables
        populateOverviewTable();
        populateEnrolledSpeakersTable();
        refreshTargetSpeakerDropdown();
        renderThreatTable();
        populateComplianceLogTable();

        // 3. Render initial Overview chart
        renderOverviewTrendChart();

        // 5. Handle window resize for canvas responsiveness
        window.addEventListener('resize', () => {
            renderOverviewTrendChart();
            renderRiskDonutChart();
            renderWeeklyVolumeChart();
            if (coreThreeRenderer) {
                const canvas = document.getElementById('ai-core-webgl');
                const rect = canvas.getBoundingClientRect();
                resizeThreeCore(rect.width, rect.height);
            } else {
                drawAiCore();
            }
            drawAudioVisualizer();
        });

        window.addEventListener('pagehide', () => {
            if (audioVisualizerFrame) cancelAnimationFrame(audioVisualizerFrame);
            if (audioObjectUrl) URL.revokeObjectURL(audioObjectUrl);
            if (audioContext && audioContext.state !== 'closed') {
                audioContext.close().catch(error => console.error('Unable to close audio visualization context:', error));
            }
        });

        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                startCoreAnimation();
            }
        });

        reducedMotionQuery.addEventListener?.('change', () => {
            if (reducedMotionQuery.matches) {
                stopCoreAnimation();
                document.querySelectorAll('.view-section [data-motion-reveal]').forEach(element => element.classList.add('is-visible'));
            } else {
                startCoreAnimation();
            }
        });

        console.log('%cVOICEGUARD AI %cDashboard ready — live AI inference is not connected', 'color: #00e5ff; font-weight: bold;', 'color: #8b5cf6;');
    }

    initApp();
});