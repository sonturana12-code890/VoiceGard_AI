/**
 * ============================================================================
 * VOICEGUARD AI — 3D Animation System
 * World-Class Three.js + GSAP Animation Engine
 *
 * Capabilities:
 * 1. initAICore: 3D AI Neural Sphere with Orbital Rings & Energy Waves
 * 2. initAudioVisualizer: 3D Sound-Wave Tunnel & Dynamic Frequency Spectrum
 * 3. initShield: 3D Holographic Cybersecurity Shield with Reactive Threat States
 * 4. initThreatMonitoring: 3D Futuristic Cyber Radar with Elevation Stalks
 * 5. initAuthBackground: 3D Neural Particles & Holographic Space for Auth Pages
 * 6. GSAP Timelines, Card 3D Tilt, ScrollTrigger & Micro-Interactions
 * ============================================================================
 */

class VoiceGuardAnimations {
    constructor() {
        this.containers = new Map();
        this.animationLoops = new Map();
        this.isWebGLSupported = this.checkWebGLSupport();
        this.reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        this.mouseX = 0;
        this.mouseY = 0;

        window.addEventListener('pointermove', (e) => {
            this.mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
            this.mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
        }, { passive: true });
    }

    checkWebGLSupport() {
        try {
            const canvas = document.createElement('canvas');
            return !!(window.WebGLRenderingContext && 
                (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
        } catch {
            return false;
        }
    }

    // ========================================================================
    // 1. HOLOGRAPHIC AI NEURAL SPHERE
    // ========================================================================
    initAICore(containerId) {
        const container = typeof containerId === 'string' ? document.getElementById(containerId) : containerId;
        if (!container) return null;

        if (!this.isWebGLSupported || !window.THREE) {
            this.initAICoreFallback(container);
            return null;
        }

        const THREE = window.THREE;
        const width = Math.max(container.clientWidth, 280);
        const height = Math.max(container.clientHeight, 280);

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 50);
        camera.position.z = 4.2;

        const renderer = new THREE.WebGLRenderer({
            alpha: true,
            antialias: true,
            powerPreference: 'high-performance'
        });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
        renderer.setSize(width, height, false);
        renderer.setClearColor(0x000000, 0);
        container.appendChild(renderer.domElement);

        const group = new THREE.Group();
        scene.add(group);

        // Volumetric 3D Faceted Core
        const coreMat = new THREE.MeshStandardMaterial({
            color: 0x362464,
            emissive: 0x4f22a5,
            emissiveIntensity: 1.1,
            roughness: 0.28,
            metalness: 0.68,
            transparent: true,
            opacity: 0.88
        });
        const core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.82, 2), coreMat);
        group.add(core);

        // Glowing Wireframe
        const wireMat = new THREE.MeshBasicMaterial({ color: 0x00f5d4, wireframe: true, transparent: true, opacity: 0.32 });
        const wire = new THREE.Mesh(new THREE.IcosahedronGeometry(0.84, 2), wireMat);
        group.add(wire);

        // Inner Seed
        const innerSeed = new THREE.Mesh(
            new THREE.SphereGeometry(0.48, 16, 16),
            new THREE.MeshBasicMaterial({ color: 0x00e5ff, transparent: true, opacity: 0.65 })
        );
        group.add(innerSeed);

        // Dynamic Energy Shockwave
        const energyWave = new THREE.Mesh(
            new THREE.SphereGeometry(0.88, 24, 24),
            new THREE.MeshBasicMaterial({ color: 0x00f5d4, wireframe: true, transparent: true, opacity: 0.35 })
        );
        group.add(energyWave);

        // 5 Multi-axis Orbital Rings
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
                new THREE.MeshBasicMaterial({ color: spec.color, transparent: true, opacity: 0.7 })
            );
            ring.rotation.set(spec.rx, spec.ry, spec.rz);
            ring.userData = { speed: spec.speed, radius: spec.r };

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

        // 340 Glowing Neural Particles
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

            particleBase.push({ x, y: py, z });

            const color = new THREE.Color(
                i % 4 === 0 ? 0x00f5d4 : (i % 3 === 0 ? 0x00e5ff : (i % 2 === 0 ? 0x8b5cf6 : 0xd946ef))
            );
            colors[i * 3] = color.r;
            colors[i * 3 + 1] = color.g;
            colors[i * 3 + 2] = color.b;
        }

        const particleGeom = new THREE.BufferGeometry();
        particleGeom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        particleGeom.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        const particles = new THREE.Points(
            particleGeom,
            new THREE.PointsMaterial({
                size: 0.032,
                vertexColors: true,
                transparent: true,
                opacity: 0.92,
                sizeAttenuation: true
            })
        );
        group.add(particles);

        // Interconnected Neural Nodes
        const neuralPoints = [];
        const neuralNodeCount = 76;
        const nodePositions = [];

        for (let i = 0; i < neuralNodeCount; i++) {
            const y = 1 - (i / (neuralNodeCount - 1)) * 2;
            const radius = Math.sqrt(1 - y * y);
            const angle = Math.PI * (3 - Math.sqrt(5)) * i;
            neuralPoints.push(new THREE.Vector3(
                Math.cos(angle) * radius * 1.08,
                y * 1.08,
                Math.sin(angle) * radius * 1.08
            ));
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
            new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(nodePositions, 3)),
            new THREE.LineBasicMaterial({ color: 0x8294ff, transparent: true, opacity: 0.32 })
        );
        group.add(neuralConnections);

        const neuralNodes = new THREE.InstancedMesh(
            new THREE.SphereGeometry(0.02, 6, 6),
            new THREE.MeshBasicMaterial({ color: 0x9beaff, transparent: true, opacity: 0.95 }),
            neuralPoints.length
        );
        const transformObj = new THREE.Object3D();
        neuralPoints.forEach((point, index) => {
            transformObj.position.copy(point);
            transformObj.scale.setScalar(index % 6 === 0 ? 1.8 : 1);
            transformObj.updateMatrix();
            neuralNodes.setMatrixAt(index, transformObj.matrix);
        });
        neuralNodes.instanceMatrix.needsUpdate = true;
        group.add(neuralNodes);

        // Lighting
        scene.add(new THREE.AmbientLight(0x8ea0ff, 1.6));
        const cyanLight = new THREE.PointLight(0x00f5d4, 8, 10);
        cyanLight.position.set(-2.4, 1.8, 3.0);
        scene.add(cyanLight);
        const violetLight = new THREE.PointLight(0x8b5cf6, 9, 10);
        violetLight.position.set(2.4, -1.5, 2.4);
        scene.add(violetLight);

        let pLerpX = 0;
        let pLerpY = 0;
        let animId = null;

        const animate = (timestamp = 0) => {
            if (!container.isConnected || document.hidden) {
                animId = requestAnimationFrame(animate);
                return;
            }

            const time = timestamp * 0.001;
            pLerpX += (this.mouseX * 0.4 - pLerpX) * 0.06;
            pLerpY += (-this.mouseY * 0.4 - pLerpY) * 0.06;

            group.rotation.y = time * 0.14 + pLerpX;
            group.rotation.x = Math.sin(time * 0.22) * 0.08 + pLerpY;

            const corePulse = 1 + Math.sin(time * 2.4) * 0.035;
            core.scale.set(corePulse, corePulse, corePulse);
            core.rotation.y = time * 0.12;

            wire.rotation.y = -time * 0.15;
            wire.rotation.x = time * 0.08;

            const seedPulse = 0.95 + Math.sin(time * 3.2) * 0.08;
            innerSeed.scale.set(seedPulse, seedPulse, seedPulse);

            const wavePhase = (time * 0.6) % 1;
            const waveScale = 1.0 + wavePhase * 0.65;
            energyWave.scale.set(waveScale, waveScale, waveScale);
            energyWave.material.opacity = Math.max(0, (1 - wavePhase) * 0.45);

            orbitalRings.forEach(ring => {
                ring.rotation.z += ring.userData.speed * 0.015;
                if (ring.userData.satellite) {
                    const sAngle = time * ring.userData.speed * 4;
                    ring.userData.satellite.position.x = Math.cos(sAngle) * ring.userData.radius;
                    ring.userData.satellite.position.y = Math.sin(sAngle) * ring.userData.radius;
                }
            });

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

            if (neuralConnections) {
                neuralConnections.material.opacity = 0.25 + Math.sin(time * 3.5) * 0.18;
                neuralConnections.rotation.y = -time * 0.08;
            }
            if (neuralNodes) {
                neuralNodes.rotation.y = -time * 0.08;
            }

            cyanLight.position.x = Math.cos(time * 0.7) * 2.8;
            cyanLight.position.z = Math.sin(time * 0.7) * 2.8;

            violetLight.position.x = Math.sin(time * 0.5) * 2.6;
            violetLight.position.y = Math.cos(time * 0.5) * 2.0;

            camera.position.x = Math.sin(time * 0.35) * 0.12;
            camera.position.y = Math.cos(time * 0.28) * 0.09;
            camera.lookAt(0, 0, 0);

            renderer.render(scene, camera);
            animId = requestAnimationFrame(animate);
        };

        animId = requestAnimationFrame(animate);
        this.containers.set(containerId, { renderer, scene, camera, animId });

        const onResize = () => {
            const w = container.clientWidth;
            const h = container.clientHeight;
            if (!w || !h) return;
            camera.aspect = w / h;
            camera.updateProjectionMatrix();
            renderer.setSize(w, h, false);
        };
        window.addEventListener('resize', onResize);

        return { renderer, scene, camera, group };
    }

    initAICoreFallback(container) {
        container.innerHTML = `
            <div style="display:flex;align-items:center;justify-content:center;width:100%;height:100%;background:radial-gradient(circle,rgba(139,92,246,0.2) 0%,transparent 70%);">
                <div style="width:190px;height:190px;border-radius:50%;background:radial-gradient(circle at 35% 35%,rgba(0,245,212,0.4),rgba(139,92,246,0.6));box-shadow:0 0 50px rgba(139,92,246,0.6),0 0 90px rgba(0,229,255,0.3);animation:aiCorePulse 4s ease-in-out infinite;"></div>
            </div>
        `;
    }

    // ========================================================================
    // 2. 3D SOUND-WAVE TUNNEL & DYNAMIC FREQUENCY SPECTRUM
    // ========================================================================
    initAudioVisualizer(containerId) {
        const container = typeof containerId === 'string' ? document.getElementById(containerId) : containerId;
        if (!container) return;
        if (window.VoiceGuardScenes) {
            window.VoiceGuardScenes.activate('analysis');
        }
    }

    // ========================================================================
    // 3. 3D HOLOGRAPHIC CYBERSECURITY SHIELD
    // ========================================================================
    initShield(containerId) {
        const container = typeof containerId === 'string' ? document.getElementById(containerId) : containerId;
        if (!container) return;
        if (window.VoiceGuardScenes) {
            window.VoiceGuardScenes.activate('fraud-prevention');
        }
    }

    // ========================================================================
    // 4. 3D CYBER THREAT RADAR
    // ========================================================================
    initThreatMonitoring(containerId) {
        const container = typeof containerId === 'string' ? document.getElementById(containerId) : containerId;
        if (!container) return;
        if (window.VoiceGuardScenes) {
            window.VoiceGuardScenes.activate('live-monitoring');
        }
    }

    // ========================================================================
    // 5. 3D NEURAL BACKGROUND & HOLOGRAPHIC PARTICLES FOR AUTH (LOGIN / SIGNUP)
    // ========================================================================
    initAuthBackground(authScreenId = 'auth-screen') {
        const screen = document.getElementById(authScreenId);
        if (!screen || !this.isWebGLSupported || !window.THREE) return;
        if (screen.querySelector('.auth-3d-backdrop')) return;

        const THREE = window.THREE;
        const canvas = document.createElement('canvas');
        canvas.className = 'auth-3d-backdrop';
        canvas.style.position = 'absolute';
        canvas.style.inset = '0';
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        canvas.style.pointerEvents = 'none';
        canvas.style.zIndex = '1';
        screen.style.position = 'relative';
        screen.prepend(canvas);

        const width = screen.clientWidth || window.innerWidth;
        const height = screen.clientHeight || window.innerHeight;

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
        camera.position.z = 5;

        const renderer = new THREE.WebGLRenderer({
            canvas,
            alpha: true,
            antialias: true,
            powerPreference: 'low-power'
        });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
        renderer.setSize(width, height, false);
        renderer.setClearColor(0x000000, 0);

        // 1. Floating Holographic Cyber Glyph
        const glyphGroup = new THREE.Group();
        glyphGroup.position.set(-1.8, 0, 0); // Positioned subtly in the left aside area

        const glyphCore = new THREE.Mesh(
            new THREE.IcosahedronGeometry(0.72, 1),
            new THREE.MeshBasicMaterial({ color: 0x8b5cf6, wireframe: true, transparent: true, opacity: 0.45 })
        );
        glyphGroup.add(glyphCore);

        const glyphRing = new THREE.Mesh(
            new THREE.TorusGeometry(1.05, 0.007, 4, 64),
            new THREE.MeshBasicMaterial({ color: 0x00f5d4, transparent: true, opacity: 0.65 })
        );
        glyphRing.rotation.x = 1.1;
        glyphGroup.add(glyphRing);

        scene.add(glyphGroup);

        // 2. 220 Floating 3D Particles with Neural Synapses
        const pCount = 220;
        const pPositions = new Float32Array(pCount * 3);
        const pVelocities = [];

        for (let i = 0; i < pCount; i++) {
            pPositions[i * 3] = (Math.random() - 0.5) * 12;
            pPositions[i * 3 + 1] = (Math.random() - 0.5) * 8;
            pPositions[i * 3 + 2] = (Math.random() - 0.5) * 4;

            pVelocities.push({
                x: (Math.random() - 0.5) * 0.005,
                y: (Math.random() - 0.5) * 0.005,
                z: (Math.random() - 0.5) * 0.005
            });
        }

        const pGeom = new THREE.BufferGeometry();
        pGeom.setAttribute('position', new THREE.BufferAttribute(pPositions, 3));
        const pMat = new THREE.PointsMaterial({
            color: 0x00e5ff,
            size: 0.045,
            transparent: true,
            opacity: 0.75,
            sizeAttenuation: true
        });
        const particles = new THREE.Points(pGeom, pMat);
        scene.add(particles);

        let pX = 0;
        let pY = 0;

        const animate = (timestamp = 0) => {
            if (!screen.isConnected || screen.hidden || document.hidden) {
                requestAnimationFrame(animate);
                return;
            }

            const time = timestamp * 0.001;
            pX += (this.mouseX * 0.35 - pX) * 0.05;
            pY += (-this.mouseY * 0.35 - pY) * 0.05;

            glyphGroup.rotation.y = time * 0.2 + pX;
            glyphGroup.rotation.x = Math.sin(time * 0.3) * 0.15 + pY;
            glyphRing.rotation.z = time * 0.3;

            // Drift particles
            const arr = particles.geometry.attributes.position.array;
            for (let i = 0; i < pCount; i++) {
                arr[i * 3] += pVelocities[i].x;
                arr[i * 3 + 1] += pVelocities[i].y;
                arr[i * 3 + 2] += pVelocities[i].z;

                if (Math.abs(arr[i * 3]) > 6) pVelocities[i].x *= -1;
                if (Math.abs(arr[i * 3 + 1]) > 4) pVelocities[i].y *= -1;
                if (Math.abs(arr[i * 3 + 2]) > 2) pVelocities[i].z *= -1;
            }
            particles.geometry.attributes.position.needsUpdate = true;
            particles.rotation.y = time * 0.03;

            camera.position.x = pX * 0.5;
            camera.position.y = pY * 0.5;
            camera.lookAt(0, 0, 0);

            renderer.render(scene, camera);
            requestAnimationFrame(animate);
        };

        requestAnimationFrame(animate);

        window.addEventListener('resize', () => {
            const w = screen.clientWidth || window.innerWidth;
            const h = screen.clientHeight || window.innerHeight;
            if (!w || !h) return;
            camera.aspect = w / h;
            camera.updateProjectionMatrix();
            renderer.setSize(w, h, false);
        });
    }

    // ========================================================================
    // 6. GSAP SCROLL & CARD TILT ANIMATIONS
    // ========================================================================
    addCardTiltEffect() {
        if (this.reducedMotion) return;
        const cards = document.querySelectorAll('.card, .metric-card, .auth-card');

        cards.forEach(card => {
            card.style.transition = 'transform 0.18s ease-out, box-shadow 0.22s ease-out';
            card.addEventListener('pointermove', (e) => {
                const rect = card.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;

                const centerX = rect.width / 2;
                const centerY = rect.height / 2;

                const rotateX = ((y - centerY) / centerY) * -5;
                const rotateY = ((x - centerX) / centerX) * 5;

                card.style.transform = `perspective(900px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateY(-2px)`;
            });

            card.addEventListener('pointerleave', () => {
                card.style.transform = 'perspective(900px) rotateX(0deg) rotateY(0deg) translateY(0)';
            });
        });
    }

    initScrollAnimations() {
        if (typeof gsap === 'undefined' || this.reducedMotion) return;
        if (window.ScrollTrigger) gsap.registerPlugin(window.ScrollTrigger);

        const cards = document.querySelectorAll('.metric-card, .card');
        cards.forEach((card, idx) => {
            if (window.ScrollTrigger) {
                gsap.fromTo(
                    card,
                    { opacity: 0, y: 22 },
                    {
                        opacity: 1,
                        y: 0,
                        duration: 0.65,
                        ease: 'power2.out',
                        scrollTrigger: {
                            trigger: card,
                            start: 'top 88%',
                            once: true
                        },
                        delay: (idx % 4) * 0.06
                    }
                );
            }
        });
    }
}

window.VoiceGuardAnimations = VoiceGuardAnimations;
