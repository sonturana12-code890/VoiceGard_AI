'use strict';

/**
 * ============================================================================
 * VOICEGUARD AI — Advanced 3D Workspace Scene Engine
 * World-Class Three.js WebGL Interactive Visualizations
 *
 * Scenes:
 * 1. waveform: Advanced 3D Sound-Wave Tunnel & Dynamic Audio Spectrum (Web Audio reactive)
 * 2. radar: Futuristic 3D Cyber Threat Radar with Scanning Beam & Elevation Stalks
 * 3. shield: Holographic Cybersecurity Shield with Multi-Ring Scanners & Threat States
 * 4. analytics: Holographic 3D Data Towers & Telemetry Metropolis
 * 5. identity: 3D Biometric Voiceprint Lattice & Identity Vault
 * 6. controls: 3D Cyber Defense Gyroscope & Hex Security Core
 * ============================================================================
 */

(() => {
    const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');

    let renderer = null;
    let scene = null;
    let camera = null;
    let content = null;
    let activeMount = null;
    let resizeObserver = null;
    let intersectionObserver = null;
    let isInViewport = false;
    let lastFrame = 0;
    let pointerX = 0;
    let pointerY = 0;
    let targetPointerX = 0;
    let targetPointerY = 0;
    let audioData = null;
    let audioIsPlaying = false;
    let securityState = 'neutral';

    function setFallback() {
        document.querySelectorAll('.workspace-scene[data-scene]').forEach(mount => mount.classList.add('scene-fallback'));
    }

    function createRenderer() {
        if (!window.THREE?.WebGLRenderer) {
            setFallback();
            return false;
        }

        try {
            const THREE = window.THREE;
            renderer = new THREE.WebGLRenderer({
                alpha: true,
                antialias: true,
                powerPreference: 'high-performance'
            });
            renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
            renderer.setClearColor(0x000000, 0);
            renderer.domElement.setAttribute('aria-hidden', 'true');
            renderer.domElement.className = 'workspace-scene-canvas';
            
            scene = new THREE.Scene();
            camera = new THREE.PerspectiveCamera(40, 1, 0.1, 50);
            camera.position.set(0, 0, 3.8);
            
            content = new THREE.Group();
            scene.add(content);

            // Studio Lighting System
            const ambient = new THREE.AmbientLight(0x7e8eff, 1.4);
            scene.add(ambient);

            const cyanLight = new THREE.PointLight(0x00f5d4, 4.5, 12);
            cyanLight.position.set(-2.2, 1.6, 3.2);
            scene.add(cyanLight);

            const violetLight = new THREE.PointLight(0x8b5cf6, 5.0, 12);
            violetLight.position.set(2.2, -1.2, 2.8);
            scene.add(violetLight);

            const blueAccent = new THREE.PointLight(0x00d2ff, 3.0, 10);
            blueAccent.position.set(0, 2.5, -1.0);
            scene.add(blueAccent);

            resizeObserver = new ResizeObserver(entries => {
                for (const entry of entries) {
                    if (entry.target === activeMount) {
                        const { width, height } = entry.contentRect;
                        resize(width, height);
                    }
                }
            });

            intersectionObserver = new IntersectionObserver(entries => {
                const entry = entries.find(item => item.target === activeMount);
                if (!entry) return;
                isInViewport = entry.isIntersecting;
                updateLoop();
            }, { threshold: 0.05 });

            window.addEventListener('pointermove', updatePointer, { passive: true });
            document.addEventListener('visibilitychange', updateLoop);
            motionPreference.addEventListener?.('change', updateLoop);
            return true;
        } catch (error) {
            console.warn('Workspace 3D scene unavailable; using the lightweight visual fallback.', error);
            renderer?.dispose();
            renderer = null;
            setFallback();
            return false;
        }
    }

    function updatePointer(event) {
        if (!activeMount || !window.matchMedia('(pointer: fine)').matches) return;
        const bounds = activeMount.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right ||
            event.clientY < bounds.top || event.clientY > bounds.bottom) {
            targetPointerX = 0;
            targetPointerY = 0;
            return;
        }
        targetPointerX = ((event.clientX - bounds.left) / bounds.width - 0.5) * 0.6;
        targetPointerY = ((event.clientY - bounds.top) / bounds.height - 0.5) * 0.45;
    }

    function disposeContent() {
        if (!content) return;
        while (content.children.length) {
            const object = content.children[content.children.length - 1];
            object.traverse?.(child => {
                child.geometry?.dispose();
                if (Array.isArray(child.material)) child.material.forEach(m => m.dispose());
                else child.material?.dispose();
            });
            content.remove(object);
        }
    }

    // ========================================================================
    // SCENE 1: ADVANCED 3D VOICE SOUND-WAVE TUNNEL & FREQUENCY SPECTRUM
    // ========================================================================
    function addWaveform() {
        const THREE = window.THREE;
        const waveGroup = new THREE.Group();

        // 1. 3D Sound-Wave Tunnel Rings extending into the depth (-Z)
        const tunnelRings = [];
        const ringCount = 14;
        const tunnelDepth = 2.4;

        for (let i = 0; i < ringCount; i++) {
            const zNorm = i / (ringCount - 1);
            const zPos = 0.5 - zNorm * tunnelDepth;
            const radius = 0.85 - zNorm * 0.35; // Tapering cylindrical tunnel
            
            // Polygonal hex/circle ring
            const segments = 48;
            const ringGeom = new THREE.BufferGeometry();
            const positions = new Float32Array((segments + 1) * 3);
            
            for (let j = 0; j <= segments; j++) {
                const angle = (j / segments) * Math.PI * 2;
                positions[j * 3] = Math.cos(angle) * radius;
                positions[j * 3 + 1] = Math.sin(angle) * radius;
                positions[j * 3 + 2] = 0;
            }
            ringGeom.setAttribute('position', new THREE.BufferAttribute(positions, 3));

            const hue = i % 2 === 0 ? 0x00f5d4 : (i % 3 === 0 ? 0x8b5cf6 : 0x00e5ff);
            const ringMat = new THREE.LineBasicMaterial({
                color: hue,
                transparent: true,
                opacity: 0.35 + (1 - zNorm) * 0.45,
                linewidth: 1.5
            });

            const ringMesh = new THREE.Line(ringGeom, ringMat);
            ringMesh.position.z = zPos;
            ringMesh.userData = {
                baseRadius: radius,
                zPos,
                index: i,
                isTunnelRing: true
            };
            waveGroup.add(ringMesh);
            tunnelRings.push(ringMesh);
        }

        // 2. 3D Frequency Spectrum Bars in an amphitheater arc
        const barCount = 36;
        const spectrumBars = [];
        const barGeom = new THREE.BoxGeometry(0.038, 1, 0.038);

        for (let i = 0; i < barCount; i++) {
            const angle = Math.PI * 1.15 + (i / (barCount - 1)) * (Math.PI * 0.7); // Arc along bottom
            const arcRadius = 1.05;
            const x = Math.cos(angle) * arcRadius;
            const y = Math.sin(angle) * 0.7 - 0.2;
            const z = 0.1 + Math.sin(i * 0.18) * 0.15;

            // Gradient colors from cyan at edges to purple at center
            const centerDist = Math.abs(i - barCount / 2) / (barCount / 2);
            const color = new THREE.Color().lerpColors(
                new THREE.Color(0x8b5cf6),
                new THREE.Color(0x00f5d4),
                centerDist
            );

            const barMat = new THREE.MeshStandardMaterial({
                color,
                emissive: color,
                emissiveIntensity: 0.6,
                metalness: 0.3,
                roughness: 0.4
            });

            const bar = new THREE.Mesh(barGeom, barMat);
            bar.position.set(x, y, z);
            bar.rotation.z = angle - Math.PI / 2;
            const baseH = 0.12 + Math.sin(i * 0.4) * 0.08;
            bar.scale.set(1, baseH, 1);
            bar.userData = {
                spectrumBar: true,
                index: i,
                baseHeight: baseH,
                angle,
                phase: i * 0.35
            };
            waveGroup.add(bar);
            spectrumBars.push(bar);
        }

        // 3. Rotating Audio Waveform Rings around core
        const orbitRings = [
            { r: 1.18, color: 0x00f5d4, rx: 1.2, ry: 0.2, speed: 0.2 },
            { r: 1.34, color: 0x8b5cf6, rx: 0.4, ry: 1.1, speed: -0.15 },
            { r: 0.95, color: 0x00cfff, rx: 0.8, ry: -0.5, speed: 0.28 }
        ];
        const audioOrbits = orbitRings.map(spec => {
            const torus = new THREE.Mesh(
                new THREE.TorusGeometry(spec.r, 0.007, 4, 80),
                new THREE.MeshBasicMaterial({ color: spec.color, transparent: true, opacity: 0.65 })
            );
            torus.rotation.set(spec.rx, spec.ry, 0);
            torus.userData = { orbitSpeed: spec.speed, isAudioOrbit: true, baseR: spec.r };
            waveGroup.add(torus);
            return torus;
        });

        // 4. Floating Audio Particle Cloud
        const particleCount = 140;
        const partPositions = new Float32Array(particleCount * 3);
        const partColors = new Float32Array(particleCount * 3);
        const partBasePos = [];

        for (let i = 0; i < particleCount; i++) {
            const angle = Math.random() * Math.PI * 2;
            const dist = 0.5 + Math.random() * 0.9;
            const z = (Math.random() - 0.5) * 2.2;
            const x = Math.cos(angle) * dist;
            const y = Math.sin(angle) * dist * 0.85;

            partPositions[i * 3] = x;
            partPositions[i * 3 + 1] = y;
            partPositions[i * 3 + 2] = z;

            partBasePos.push({ x, y, z, angle, dist, speed: 0.3 + Math.random() * 0.7 });

            const pColor = new THREE.Color(i % 3 === 0 ? 0x00f5d4 : (i % 2 === 0 ? 0x00e5ff : 0x8b5cf6));
            partColors[i * 3] = pColor.r;
            partColors[i * 3 + 1] = pColor.g;
            partColors[i * 3 + 2] = pColor.b;
        }

        const particleGeom = new THREE.BufferGeometry();
        particleGeom.setAttribute('position', new THREE.BufferAttribute(partPositions, 3));
        particleGeom.setAttribute('color', new THREE.BufferAttribute(partColors, 3));

        const audioParticles = new THREE.Points(
            particleGeom,
            new THREE.PointsMaterial({
                size: 0.038,
                vertexColors: true,
                transparent: true,
                opacity: 0.85,
                sizeAttenuation: true
            })
        );
        waveGroup.add(audioParticles);

        content.add(waveGroup);
        content.userData.waveformVisual = {
            tunnelRings,
            spectrumBars,
            audioOrbits,
            audioParticles,
            partBasePos,
            waveGroup
        };
    }

    // ========================================================================
    // SCENE 2: FUTURISTIC 3D CYBER THREAT RADAR
    // ========================================================================
    function addRadar() {
        const THREE = window.THREE;
        const radarGroup = new THREE.Group();

        // Tilt radar plane for dramatic 3D perspective
        radarGroup.rotation.x = 0.82;
        radarGroup.position.y = -0.15;

        // 1. Concentric Holographic Range Rings
        const radii = [0.38, 0.74, 1.10, 1.45];
        radii.forEach((r, idx) => {
            const ring = new THREE.Mesh(
                new THREE.TorusGeometry(r, 0.007, 4, 96),
                new THREE.MeshBasicMaterial({
                    color: idx === 2 ? 0x8b5cf6 : 0x00f5d4,
                    transparent: true,
                    opacity: idx === 3 ? 0.75 : 0.45
                })
            );
            radarGroup.add(ring);
        });

        // 2. Radial Crosshair Spokes & Compass Divisions (12 lines)
        const spokeGeom = new THREE.BufferGeometry();
        const spokePositions = [];
        for (let i = 0; i < 12; i++) {
            const angle = (i / 12) * Math.PI * 2;
            const rInner = i % 3 === 0 ? 0.15 : 0.38;
            const rOuter = 1.45;
            spokePositions.push(
                Math.cos(angle) * rInner, Math.sin(angle) * rInner, 0,
                Math.cos(angle) * rOuter, Math.sin(angle) * rOuter, 0
            );
        }
        spokeGeom.setAttribute('position', new THREE.Float32BufferAttribute(spokePositions, 3));
        const spokeMesh = new THREE.LineSegments(
            spokeGeom,
            new THREE.LineBasicMaterial({ color: 0x3d5488, transparent: true, opacity: 0.55 })
        );
        radarGroup.add(spokeMesh);

        // 3. Rotating Radar Scanning Beam with Fading Sector Trail
        const sectorSegments = 32;
        const sectorAngle = Math.PI * 0.45; // ~80 degrees wedge
        const sweepGeom = new THREE.BufferGeometry();
        const sweepPositions = [0, 0, 0.01];
        const sweepColors = [0, 0.96, 0.83, 0.8]; // Vertex RGBA

        for (let i = 0; i <= sectorSegments; i++) {
            const a = (i / sectorSegments) * sectorAngle;
            const alpha = Math.pow(i / sectorSegments, 2.5); // Fading tail
            sweepPositions.push(Math.cos(a) * 1.45, Math.sin(a) * 1.45, 0.01);
            sweepColors.push(0, 0.96, 0.83, alpha * 0.45);
        }

        // Build triangle fan for sweep
        const indices = [];
        for (let i = 1; i < sectorSegments + 1; i++) {
            indices.push(0, i, i + 1);
        }
        sweepGeom.setIndex(indices);
        sweepGeom.setAttribute('position', new THREE.Float32BufferAttribute(sweepPositions, 3));

        const sweepMat = new THREE.MeshBasicMaterial({
            color: 0x00f5d4,
            transparent: true,
            opacity: 0.22,
            side: THREE.DoubleSide,
            depthWrite: false
        });
        const sweepMesh = new THREE.Mesh(sweepGeom, sweepMat);

        // Leading laser edge line
        const leadLine = new THREE.Line(
            new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(0, 0, 0.02),
                new THREE.Vector3(Math.cos(sectorAngle) * 1.45, Math.sin(sectorAngle) * 1.45, 0.02)
            ]),
            new THREE.LineBasicMaterial({ color: 0x00f5d4, transparent: true, opacity: 0.95, linewidth: 2 })
        );
        sweepMesh.add(leadLine);
        radarGroup.add(sweepMesh);

        // 4. Animated Threat Signals with Vertical Elevation Laser Stalks
        const threats = [
            { angle: 0.45, r: 0.88, z: 0.24, risk: 'high', label: 'VG-9082' },
            { angle: 1.82, r: 1.15, z: 0.18, risk: 'critical', label: 'SIP-Bypass' },
            { angle: 3.25, r: 0.58, z: 0.14, risk: 'medium', label: 'Replay' },
            { angle: 4.10, r: 1.28, z: 0.28, risk: 'critical', label: 'Neural-Pitch' },
            { angle: 5.15, r: 0.92, z: 0.19, risk: 'medium', label: 'IVR-Probe' },
            { angle: 2.70, r: 0.42, z: 0.12, risk: 'low', label: 'Verified' },
            { angle: 5.90, r: 0.72, z: 0.16, risk: 'high', label: 'Synth-TTS' }
        ];

        const threatMeshes = [];
        const stalkPositions = [];
        const stalkColors = [];

        threats.forEach(t => {
            const x = Math.cos(t.angle) * t.r;
            const y = Math.sin(t.angle) * t.r;
            const color = t.risk === 'critical' ? 0xef4444 : (t.risk === 'high' ? 0xf59e0b : (t.risk === 'medium' ? 0x00e5ff : 0x10b981));

            // Floating 3D blip sphere
            const blip = new THREE.Mesh(
                new THREE.SphereGeometry(0.042, 10, 10),
                new THREE.MeshStandardMaterial({
                    color,
                    emissive: color,
                    emissiveIntensity: 0.9,
                    metalness: 0.5,
                    roughness: 0.2
                })
            );
            blip.position.set(x, y, t.z);
            radarGroup.add(blip);

            // Ground target ring
            const groundRing = new THREE.Mesh(
                new THREE.TorusGeometry(0.05, 0.005, 4, 24),
                new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.6 })
            );
            groundRing.position.set(x, y, 0.005);
            radarGroup.add(groundRing);

            // Shockwave ping ring
            const pingRing = new THREE.Mesh(
                new THREE.TorusGeometry(0.06, 0.004, 4, 32),
                new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.8 })
            );
            pingRing.position.set(x, y, t.z);
            radarGroup.add(pingRing);

            // Vertical stalk connecting to ground plane
            stalkPositions.push(x, y, 0, x, y, t.z);
            const cObj = new THREE.Color(color);
            stalkColors.push(cObj.r, cObj.g, cObj.b, cObj.r, cObj.g, cObj.b);

            threatMeshes.push({
                blip,
                pingRing,
                groundRing,
                target: t,
                x, y, z: t.z,
                baseColor: cObj
            });
        });

        const stalkGeom = new THREE.BufferGeometry();
        stalkGeom.setAttribute('position', new THREE.Float32BufferAttribute(stalkPositions, 3));
        stalkGeom.setAttribute('color', new THREE.Float32BufferAttribute(stalkColors, 3));
        const stalkLines = new THREE.LineSegments(
            stalkGeom,
            new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.55 })
        );
        radarGroup.add(stalkLines);

        // Center beacon core
        const centerCore = new THREE.Mesh(
            new THREE.CylinderGeometry(0.04, 0.08, 0.12, 16),
            new THREE.MeshStandardMaterial({
                color: 0x00f5d4,
                emissive: 0x00f5d4,
                emissiveIntensity: 0.8
            })
        );
        centerCore.rotation.x = Math.PI / 2;
        radarGroup.add(centerCore);

        content.add(radarGroup);
        content.userData.radarVisual = {
            radarGroup,
            sweepMesh,
            threatMeshes,
            sweepAngle: 0
        };
    }

    // ========================================================================
    // SCENE 3: PREMIUM 3D HOLOGRAPHIC CYBERSECURITY SHIELD
    // ========================================================================
    function addShield() {
        const THREE = window.THREE;
        const shieldGroup = new THREE.Group();

        // 1. Sculpted 3D Cyber Shield Geometry
        const shape = new THREE.Shape();
        shape.moveTo(0, 0.92);
        shape.lineTo(0.68, 0.62);
        shape.lineTo(0.60, -0.06);
        shape.quadraticCurveTo(0.46, -0.65, 0, -0.95);
        shape.quadraticCurveTo(-0.46, -0.65, -0.60, -0.06);
        shape.lineTo(-0.68, 0.62);
        shape.closePath();

        const extrudeSettings = {
            depth: 0.14,
            bevelEnabled: true,
            bevelSegments: 4,
            steps: 1,
            bevelSize: 0.05,
            bevelThickness: 0.05
        };

        const shieldMat = new THREE.MeshStandardMaterial({
            color: 0x18143d,
            emissive: 0x3d2780,
            emissiveIntensity: 0.85,
            metalness: 0.72,
            roughness: 0.28,
            transparent: true,
            opacity: 0.88
        });

        const shieldMesh = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, extrudeSettings), shieldMat);
        shieldMesh.position.z = -0.07;
        shieldGroup.add(shieldMesh);

        // 2. Wireframe Crest Overlay
        const wireMat = new THREE.LineBasicMaterial({ color: 0x00f5d4, transparent: true, opacity: 0.85, linewidth: 2 });
        const outlinePoints = shape.getPoints(54).map(p => new THREE.Vector3(p.x, p.y, 0.12));
        const wireMesh = new THREE.Line(new THREE.BufferGeometry().setFromPoints(outlinePoints), wireMat);
        shieldGroup.add(wireMesh);

        // 3. Central Holographic Security Keyhole / Core Crest
        const keyholeShape = new THREE.Shape();
        keyholeShape.absarc(0, 0.08, 0.12, 0, Math.PI * 2);
        const innerCore = new THREE.Mesh(
            new THREE.IcosahedronGeometry(0.18, 2),
            new THREE.MeshStandardMaterial({
                color: 0x00f5d4,
                emissive: 0x00f5d4,
                emissiveIntensity: 1.1,
                roughness: 0.2,
                metalness: 0.8
            })
        );
        innerCore.position.z = 0.14;
        shieldGroup.add(innerCore);

        // 4. Concentric Defense Scanning Rings
        const scanRings = [
            { r: 1.15, rx: 1.25, ry: 0.2, speed: 0.25, color: 0x00e5ff },
            { r: 1.32, rx: -0.4, ry: 1.15, speed: -0.18, color: 0x8b5cf6 },
            { r: 1.02, rx: 0.8, ry: -0.65, speed: 0.32, color: 0x00f5d4 }
        ];

        const ringMeshes = scanRings.map(s => {
            const ring = new THREE.Mesh(
                new THREE.TorusGeometry(s.r, 0.009, 4, 84),
                new THREE.MeshBasicMaterial({ color: s.color, transparent: true, opacity: 0.72 })
            );
            ring.rotation.set(s.rx, s.ry, 0);
            ring.userData = { speed: s.speed, rx: s.rx, ry: s.ry };
            shieldGroup.add(ring);
            return ring;
        });

        // 5. Hexagonal Energy Forcefield Grid & Radiating Protection Rays
        const rayGeom = new THREE.BufferGeometry();
        const rayPositions = [];
        const rayCount = 12;
        for (let i = 0; i < rayCount; i++) {
            const angle = (i / rayCount) * Math.PI * 2;
            rayPositions.push(
                Math.cos(angle) * 0.45, Math.sin(angle) * 0.45, 0.05,
                Math.cos(angle) * 1.35, Math.sin(angle) * 1.35, 0.05
            );
        }
        rayGeom.setAttribute('position', new THREE.Float32BufferAttribute(rayPositions, 3));
        const rayMesh = new THREE.LineSegments(
            rayGeom,
            new THREE.LineBasicMaterial({ color: 0x00f5d4, transparent: true, opacity: 0.4 })
        );
        shieldGroup.add(rayMesh);

        // 6. Floating Digital Security Bits
        const bitCount = 72;
        const bitPositions = new Float32Array(bitCount * 3);
        const bitColors = new Float32Array(bitCount * 3);
        for (let i = 0; i < bitCount; i++) {
            const angle = Math.random() * Math.PI * 2;
            const dist = 0.85 + Math.random() * 0.6;
            bitPositions[i * 3] = Math.cos(angle) * dist;
            bitPositions[i * 3 + 1] = Math.sin(angle) * dist * 1.1;
            bitPositions[i * 3 + 2] = (Math.random() - 0.5) * 0.6;

            const c = new THREE.Color(i % 3 === 0 ? 0x00f5d4 : (i % 2 === 0 ? 0x00e5ff : 0x8b5cf6));
            bitColors[i * 3] = c.r;
            bitColors[i * 3 + 1] = c.g;
            bitColors[i * 3 + 2] = c.b;
        }
        const bitGeom = new THREE.BufferGeometry();
        bitGeom.setAttribute('position', new THREE.BufferAttribute(bitPositions, 3));
        bitGeom.setAttribute('color', new THREE.BufferAttribute(bitColors, 3));
        const bitParticles = new THREE.Points(
            bitGeom,
            new THREE.PointsMaterial({ size: 0.035, vertexColors: true, transparent: true, opacity: 0.85 })
        );
        shieldGroup.add(bitParticles);

        content.add(shieldGroup);

        // Security State Visual Targets
        content.userData.shieldVisual = {
            shieldMesh,
            shieldMat,
            wireMat,
            innerCore,
            rayMesh,
            ringMeshes,
            bitParticles,
            targets: {
                neutral: {
                    base: new THREE.Color(0x18143d),
                    emissive: new THREE.Color(0x3d2780),
                    wire: new THREE.Color(0x00f5d4),
                    core: new THREE.Color(0x00f5d4),
                    intensity: 0.85
                },
                safe: {
                    base: new THREE.Color(0x073527),
                    emissive: new THREE.Color(0x10b981),
                    wire: new THREE.Color(0x00f5d4),
                    core: new THREE.Color(0x10b981),
                    intensity: 1.05
                },
                suspicious: {
                    base: new THREE.Color(0x422606),
                    emissive: new THREE.Color(0xd97706),
                    wire: new THREE.Color(0xf59e0b),
                    core: new THREE.Color(0xfbbf24),
                    intensity: 1.2
                },
                'high-risk': {
                    base: new THREE.Color(0x4a0a14),
                    emissive: new THREE.Color(0xef4444),
                    wire: new THREE.Color(0xff365b),
                    core: new THREE.Color(0xff2244),
                    intensity: 1.55
                }
            }
        };
    }

    // ========================================================================
    // SCENE 4: HOLOGRAPHIC 3D ANALYTICS METROPOLIS
    // ========================================================================
    function addAnalytics() {
        const THREE = window.THREE;
        const analyticsGroup = new THREE.Group();
        analyticsGroup.rotation.x = 0.55;

        // 12 dynamic cyber towers
        const barHeights = [0.4, 0.72, 0.55, 0.95, 0.82, 1.2, 0.65, 1.05, 0.88, 1.35, 0.78, 1.1];
        const towerMeshes = [];
        const geom = new THREE.BoxGeometry(0.12, 1, 0.12);

        barHeights.forEach((h, i) => {
            const x = (i - 5.5) * 0.22;
            const z = ((i % 3) - 1) * 0.25;
            const color = i % 3 === 0 ? 0x00f5d4 : (i % 2 === 0 ? 0x8b5cf6 : 0x00cfff);

            const mat = new THREE.MeshStandardMaterial({
                color,
                emissive: color,
                emissiveIntensity: 0.55,
                metalness: 0.4,
                roughness: 0.3,
                transparent: true,
                opacity: 0.88
            });

            const mesh = new THREE.Mesh(geom, mat);
            mesh.position.set(x, -0.6 + h / 2, z);
            mesh.scale.set(1, h, 1);
            mesh.userData = { baseH: h, phase: i * 0.45, chartBar: true };
            analyticsGroup.add(mesh);
            towerMeshes.push(mesh);
        });

        // Orbiting Telemetry Rings
        const ring = new THREE.Mesh(
            new THREE.TorusGeometry(1.4, 0.008, 4, 80),
            new THREE.MeshBasicMaterial({ color: 0x8b5cf6, transparent: true, opacity: 0.5 })
        );
        ring.rotation.x = Math.PI / 2;
        ring.userData = { orbitSpeed: 0.15 };
        analyticsGroup.add(ring);

        content.add(analyticsGroup);
        content.userData.analyticsVisual = { analyticsGroup, towerMeshes };
    }

    // ========================================================================
    // SCENE 5: 3D BIOMETRIC VOICEPRINT LATTICE & IDENTITY VAULT
    // ========================================================================
    function addIdentityNetwork() {
        const THREE = window.THREE;
        const identityGroup = new THREE.Group();

        // Biometric Double-Helix Lattice
        const strandCount = 48;
        const positions = [];
        const rungPositions = [];

        for (let i = 0; i < strandCount; i++) {
            const t = (i / strandCount) * Math.PI * 4;
            const y = (i / strandCount - 0.5) * 1.9;
            const r = 0.55;

            const x1 = Math.cos(t) * r;
            const z1 = Math.sin(t) * r;
            const x2 = Math.cos(t + Math.PI) * r;
            const z2 = Math.sin(t + Math.PI) * r;

            positions.push(x1, y, z1, x2, y, z2);

            if (i % 3 === 0) {
                rungPositions.push(x1, y, z1, x2, y, z2);
            }
        }

        // Connecting rungs
        const rungs = new THREE.LineSegments(
            new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(rungPositions, 3)),
            new THREE.LineBasicMaterial({ color: 0x00f5d4, transparent: true, opacity: 0.7, linewidth: 2 })
        );
        identityGroup.add(rungs);

        // Verification Nodes
        const nodeGeom = new THREE.SphereGeometry(0.032, 8, 8);
        const nodeMat = new THREE.MeshStandardMaterial({
            color: 0x00e5ff,
            emissive: 0x00e5ff,
            emissiveIntensity: 0.8
        });

        for (let i = 0; i < positions.length; i += 6) {
            const sphere1 = new THREE.Mesh(nodeGeom, nodeMat);
            sphere1.position.set(positions[i], positions[i + 1], positions[i + 2]);
            identityGroup.add(sphere1);

            const sphere2 = new THREE.Mesh(nodeGeom, nodeMat);
            sphere2.position.set(positions[i + 3], positions[i + 4], positions[i + 5]);
            identityGroup.add(sphere2);
        }

        // Orbiting Identity Hex Rings
        const orbit = new THREE.Mesh(
            new THREE.TorusGeometry(0.95, 0.008, 4, 6),
            new THREE.MeshBasicMaterial({ color: 0x8b5cf6, transparent: true, opacity: 0.75 })
        );
        orbit.rotation.x = 1.1;
        orbit.userData = { orbitSpeed: 0.22 };
        identityGroup.add(orbit);

        content.add(identityGroup);
        content.userData.identityVisual = { identityGroup };
    }

    // ========================================================================
    // SCENE 6: 3D CYBER DEFENSE GYROSCOPE (Settings & Controls)
    // ========================================================================
    function addControls() {
        const THREE = window.THREE;
        const gyroGroup = new THREE.Group();

        // Core icosahedron
        const core = new THREE.Mesh(
            new THREE.IcosahedronGeometry(0.38, 2),
            new THREE.MeshStandardMaterial({
                color: 0x221650,
                emissive: 0x8b5cf6,
                emissiveIntensity: 0.9,
                wireframe: true
            })
        );
        gyroGroup.add(core);

        // 3 concentric gimbal rings
        const gimbals = [
            { r: 0.65, rx: 0, ry: 0, speed: 0.35, color: 0x00f5d4 },
            { r: 0.88, rx: 1.1, ry: 0.4, speed: -0.28, color: 0x00e5ff },
            { r: 1.12, rx: -0.6, ry: 1.2, speed: 0.2, color: 0x8b5cf6 }
        ];

        gimbals.forEach(g => {
            const ring = new THREE.Mesh(
                new THREE.TorusGeometry(g.r, 0.012, 5, 64),
                new THREE.MeshBasicMaterial({ color: g.color, transparent: true, opacity: 0.75 })
            );
            ring.rotation.set(g.rx, g.ry, 0);
            ring.userData = { orbitSpeed: g.speed };
            gyroGroup.add(ring);
        });

        content.add(gyroGroup);
        content.userData.controlsVisual = { gyroGroup, core };
    }

    // ========================================================================
    // SCENE ROUTING & BUILDER
    // ========================================================================
    function buildScene(kind) {
        if (!content) return;
        disposeContent();

        switch (kind) {
            case 'waveform':
                addWaveform();
                break;
            case 'radar':
                addRadar();
                break;
            case 'shield':
                addShield();
                break;
            case 'analytics':
                addAnalytics();
                break;
            case 'identity':
                addIdentityNetwork();
                break;
            case 'controls':
                addControls();
                break;
            default:
                addShield();
                break;
        }

        content.userData.kind = kind;
        content.rotation.set(0.05, 0, 0);
        const bounds = activeMount.getBoundingClientRect();
        resize(bounds.width, bounds.height);
    }

    function resize(width, height) {
        if (!renderer || !camera || !activeMount) return;
        const bounds = activeMount.getBoundingClientRect();
        const sceneWidth = Math.floor(width || bounds.width);
        const sceneHeight = Math.floor(height || bounds.height);
        if (!sceneWidth || !sceneHeight) return;
        camera.aspect = sceneWidth / sceneHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(sceneWidth, sceneHeight, false);
        render(performance.now());
    }

    // ========================================================================
    // ANIMATION & RENDER LOOP
    // ========================================================================
    function render(timestamp = 0) {
        if (!renderer || !scene || !camera || !activeMount?.isConnected) return;
        if (!motionPreference.matches && timestamp - lastFrame < 16) return; // 60 FPS cap
        lastFrame = timestamp;
        const time = timestamp * 0.001;

        // Mouse Parallax Lerping
        pointerX += (targetPointerX - pointerX) * 0.06;
        pointerY += (targetPointerY - pointerY) * 0.06;

        content.rotation.y = time * 0.12 + pointerX;
        content.rotation.x = Math.sin(time * 0.35) * 0.045 - pointerY;

        // Animate General Children with orbitSpeed
        content.traverse(child => {
            if (child.userData.orbitSpeed) {
                child.rotation.z += child.userData.orbitSpeed * 0.015;
            }
        });

        // 1. WAVEFORM ANIMATION (Real Audio Reactive + Idle Waves)
        const wf = content.userData.waveformVisual;
        if (wf) {
            // Spectrum bars reactivity
            wf.spectrumBars.forEach((bar, idx) => {
                let barLevel = 0;
                if (audioIsPlaying && audioData?.length) {
                    const bin = Math.min(
                        audioData.length - 1,
                        Math.floor((idx / wf.spectrumBars.length) * (audioData.length * 0.75))
                    );
                    barLevel = audioData[bin] / 255;
                }

                const idleH = bar.userData.baseHeight * (0.85 + Math.sin(time * 2.8 + bar.userData.phase) * 0.35);
                const activeH = bar.userData.baseHeight + barLevel * 1.7;
                const finalH = audioIsPlaying ? activeH : idleH;

                bar.scale.y = THREE.MathUtils.lerp(bar.scale.y, finalH, 0.22);
                if (bar.material.emissiveIntensity) {
                    bar.material.emissiveIntensity = audioIsPlaying ? 0.6 + barLevel * 1.2 : 0.6;
                }
            });

            // Tunnel Rings wave pulse
            wf.tunnelRings.forEach((ring, idx) => {
                const waveOffset = Math.sin(time * 3.5 - idx * 0.45);
                let audioPulse = 0;
                if (audioIsPlaying && audioData?.length) {
                    const bin = (idx * 4) % audioData.length;
                    audioPulse = (audioData[bin] / 255) * 0.45;
                }
                const scale = 1 + waveOffset * 0.06 + audioPulse;
                ring.scale.set(scale, scale, 1);
                ring.rotation.z = time * 0.1 + idx * 0.08;
            });

            // Floating Audio Particles
            if (wf.audioParticles) {
                const pos = wf.audioParticles.geometry.attributes.position.array;
                let audioVol = 0;
                if (audioIsPlaying && audioData?.length) {
                    audioVol = (audioData[4] || 0) / 255;
                }
                wf.partBasePos.forEach((b, i) => {
                    const pAngle = b.angle + time * 0.15 * b.speed;
                    const r = b.dist * (1 + (audioIsPlaying ? audioVol * 0.4 : Math.sin(time + i) * 0.08));
                    pos[i * 3] = Math.cos(pAngle) * r;
                    pos[i * 3 + 1] = Math.sin(pAngle) * r * 0.85;
                    pos[i * 3 + 2] = b.z + Math.sin(time * 2 + i) * 0.05;
                });
                wf.audioParticles.geometry.attributes.position.needsUpdate = true;
            }
        }

        // 2. RADAR ANIMATION (Scanning Beam & Threat Detection)
        const rd = content.userData.radarVisual;
        if (rd) {
            rd.sweepAngle += 0.024;
            rd.sweepMesh.rotation.z = rd.sweepAngle;

            // Animate Threat Signals when swept
            rd.threatMeshes.forEach(tMesh => {
                const tAngle = tMesh.target.angle;
                const diff = (rd.sweepAngle - tAngle) % (Math.PI * 2);
                const isSwept = diff >= 0 && diff < 0.6;

                // Ping pulse expanding
                const pingScale = 1 + (diff % 1.5) * 1.8;
                tMesh.pingRing.scale.set(pingScale, pingScale, 1);
                tMesh.pingRing.material.opacity = Math.max(0, 0.9 - (diff % 1.5) * 0.6);

                // Blip flare up
                const emissiveTarget = isSwept ? 2.2 : 0.8;
                tMesh.blip.material.emissiveIntensity = THREE.MathUtils.lerp(
                    tMesh.blip.material.emissiveIntensity,
                    emissiveTarget,
                    0.15
                );
            });
        }

        // 3. SHIELD ANIMATION & DYNAMIC THREAT STATE
        const sh = content.userData.shieldVisual;
        if (sh) {
            sh.shieldMesh.rotation.y = Math.sin(time * 0.6) * 0.08;
            sh.innerCore.rotation.x = time * 0.4;
            sh.innerCore.rotation.y = time * 0.6;

            // Pulsing scale for breathing effect
            const breath = 1 + Math.sin(time * 2.2) * 0.025;
            sh.shieldMesh.scale.set(breath, breath, breath);

            // Interpolate toward Security State
            const stateTarget = sh.targets[securityState] || sh.targets.neutral;
            const blend = motionPreference.matches ? 1 : 0.07;
            
            sh.shieldMat.color.lerp(stateTarget.base, blend);
            sh.shieldMat.emissive.lerp(stateTarget.emissive, blend);
            sh.wireMat.color.lerp(stateTarget.wire, blend);
            sh.innerCore.material.emissive.lerp(stateTarget.core, blend);
            sh.shieldMat.emissiveIntensity = THREE.MathUtils.lerp(
                sh.shieldMat.emissiveIntensity,
                stateTarget.intensity,
                blend
            );
        }

        // 4. ANALYTICS METROPOLIS ANIMATION
        const an = content.userData.analyticsVisual;
        if (an) {
            an.towerMeshes.forEach(tower => {
                const pulse = Math.sin(time * 2.0 + tower.userData.phase) * 0.18;
                const h = Math.max(0.1, tower.userData.baseH + pulse);
                tower.scale.y = h;
                tower.position.y = -0.6 + h / 2;
            });
        }

        // 5. IDENTITY LATTICE ROTATION
        const idV = content.userData.identityVisual;
        if (idV) {
            idV.identityGroup.rotation.y = time * 0.35;
        }

        // 6. CONTROLS GYROSCOPE
        const ctrl = content.userData.controlsVisual;
        if (ctrl) {
            ctrl.core.rotation.x = time * 0.4;
            ctrl.core.rotation.y = time * 0.55;
        }

        renderer.render(scene, camera);
    }

    function updateLoop() {
        if (!renderer) return;
        const shouldAnimate = activeMount && isInViewport && !document.hidden && !motionPreference.matches;
        if (shouldAnimate) {
            renderer.setAnimationLoop(render);
        } else {
            renderer.setAnimationLoop(null);
            render(performance.now());
        }
    }

    function activate(viewId) {
        const view = document.getElementById(`view-${viewId}`);
        const explicitMount = view?.querySelector('.workspace-scene[data-scene]');
        const nextMount = viewId === 'overview' ? null : (explicitMount || view);
        
        if (!nextMount) {
            if (activeMount) {
                intersectionObserver?.unobserve(activeMount);
                resizeObserver?.unobserve(activeMount);
                activeMount.classList.remove('webgl-ready');
                activeMount.classList.remove('workspace-scene-host');
            }
            renderer?.setAnimationLoop(null);
            renderer?.domElement.remove();
            activeMount = null;
            return;
        }

        if (!explicitMount) nextMount.classList.add('workspace-scene-host');
        const previousMount = activeMount;
        if (previousMount && previousMount !== nextMount) {
            intersectionObserver?.unobserve(previousMount);
            resizeObserver?.unobserve(previousMount);
            previousMount.classList.remove('webgl-ready');
            previousMount.classList.remove('workspace-scene-host');
        }

        activeMount = nextMount;
        if (!renderer && !createRenderer()) {
            activeMount.classList.add('scene-fallback');
            return;
        }

        document.querySelectorAll('.workspace-scene[data-scene]').forEach(mount => mount.classList.remove('webgl-ready'));
        activeMount.classList.remove('scene-fallback');
        renderer.domElement.classList.toggle('workspace-scene-backdrop', !explicitMount);
        activeMount.classList.add('webgl-ready');
        activeMount.appendChild(renderer.domElement);
        
        resizeObserver.observe(activeMount);
        intersectionObserver.disconnect();
        intersectionObserver.observe(activeMount);

        const bounds = activeMount.getBoundingClientRect();
        isInViewport = bounds.bottom > 0 && bounds.top < window.innerHeight;

        const kind = explicitMount?.dataset.scene || ({
            analysis: 'waveform',
            'live-monitoring': 'radar',
            verification: 'shield',
            'threat-intel': 'radar',
            'fraud-prevention': 'shield',
            analytics: 'analytics',
            profile: 'identity',
            settings: 'controls'
        }[viewId] || 'waveform');

        buildScene(kind);
        updateLoop();
    }

    document.addEventListener('DOMContentLoaded', () => {
        const initialView = window.location.hash.slice(1) || 'overview';
        activate(initialView);
    }, { once: true });

    window.VoiceGuardScenes = {
        activate,
        setAudioData(data, playing) {
            audioData = data;
            audioIsPlaying = Boolean(playing && data?.length);
        },
        setSecurityState(state) {
            if (['neutral', 'safe', 'suspicious', 'high-risk'].includes(state)) {
                securityState = state;
                if (renderer && content?.userData.shieldVisual) {
                    lastFrame = 0;
                    render(performance.now());
                }
            }
        },
        getSecurityState() {
            return securityState;
        }
    };
})();
