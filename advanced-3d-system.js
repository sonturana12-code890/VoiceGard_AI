/**
 * ============================================================================
 * VOICEGUARD AI — ADVANCED 3D ANIMATION SYSTEM
 * World-Class Three.js + WebGL + Web Audio API Integration
 * ============================================================================
 * 
 * A premium, production-grade 3D animation system that enhances existing
 * website without modifying original structure or functionality.
 * 
 * Features:
 * - Advanced neural particle system
 * - Real-time audio visualization
 * - Cybersecurity shield with threat states
 * - Cyber radar system
 * - Cinematic animations
 * - Performance-optimized rendering
 */

class AdvancedVoiceGuard3D {
    constructor() {
        this.scenes = new Map();
        this.renderers = new Map();
        this.animationFrames = new Map();
        this.audioContext = null;
        this.audioAnalyser = null;
        this.isWebGLSupported = this.checkWebGL();
        this.reduceMotion = this.checkReducedMotion();
        this.initialized = false;
    }

    checkWebGL() {
        try {
            const canvas = document.createElement('canvas');
            return !!(window.WebGLRenderingContext && 
                (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
        } catch (e) {
            return false;
        }
    }

    checkReducedMotion() {
        return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    // ========================================================================
    // ADVANCED NEURAL SPHERE SYSTEM
    // ========================================================================

    createAdvancedNeuralSphere(containerId) {
        const container = document.getElementById(containerId);
        if (!container || !this.isWebGLSupported) return;

        const width = container.clientWidth;
        const height = container.clientHeight;

        // Scene setup
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x050510);
        scene.fog = new THREE.Fog(0x050510, 100, 1000);

        const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
        camera.position.z = 8;

        const renderer = new THREE.WebGLRenderer({
            antialias: true,
            alpha: true,
            powerPreference: 'high-performance'
        });
        renderer.setSize(width, height);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFShadowShadowMap;
        container.appendChild(renderer.domElement);

        // Advanced Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
        scene.add(ambientLight);

        const primaryLight = new THREE.PointLight(0x8b5cf6, 3, 200);
        primaryLight.position.set(15, 10, 15);
        primaryLight.castShadow = true;
        primaryLight.shadow.mapSize.width = 4096;
        primaryLight.shadow.mapSize.height = 4096;
        scene.add(primaryLight);

        const secondaryLight = new THREE.PointLight(0x00e5ff, 2, 150);
        secondaryLight.position.set(-10, -5, 10);
        scene.add(secondaryLight);

        // Core Neural Sphere
        const coreGeometry = new THREE.IcosahedronGeometry(1.5, 7);
        const coreMaterial = new THREE.MeshPhongMaterial({
            color: 0x8b5cf6,
            emissive: 0x6a3fa0,
            emissiveIntensity: 0.6,
            shininess: 150,
            wireframe: false,
            side: THREE.FrontSide
        });
        const coreSphere = new THREE.Mesh(coreGeometry, coreMaterial);
        coreSphere.castShadow = true;
        coreSphere.receiveShadow = true;
        scene.add(coreSphere);

        // Outer Glowing Layer
        const glowGeometry = new THREE.IcosahedronGeometry(1.52, 7);
        const glowMaterial = new THREE.MeshBasicMaterial({
            color: 0x00f5d4,
            wireframe: true,
            transparent: true,
            opacity: 0.3
        });
        const glowMesh = new THREE.Mesh(glowGeometry, glowMaterial);
        scene.add(glowMesh);

        // Neural Nodes (interconnected points)
        this.createNeuralNodes(scene, coreGeometry);

        // Orbital Rings
        this.createAdvancedOrbitalRings(scene);

        // Particle System
        this.createNeuralParticleSystem(scene);

        // Energy Waves
        this.createEnergyWaves(scene);

        // Store scene data
        this.scenes.set(containerId, {
            scene, camera, renderer,
            coreSphere, glowMesh,
            animations: {
                coreRotation: { x: 0.001, y: 0.002, z: 0.0005 },
                glowRotation: { x: 0.003, y: -0.001, z: 0.002 }
            }
        });

        this.renderers.set(containerId, renderer);

        // Animation loop
        this.startNeuralSphereAnimation(containerId);

        // Responsive
        window.addEventListener('resize', () => this.onWindowResize(containerId));

        return { scene, camera, renderer };
    }

    createNeuralNodes(scene, geometry) {
        const positions = geometry.attributes.position.array;
        const nodeGeometry = new THREE.SphereGeometry(0.08, 8, 8);
        const nodeMaterial = new THREE.MeshPhongMaterial({
            color: 0x00f5d4,
            emissive: 0x00f5d4,
            emissiveIntensity: 0.8,
            shininess: 100
        });

        const nodeCount = Math.min(positions.length / 3, 60);
        
        for (let i = 0; i < nodeCount; i++) {
            const node = new THREE.Mesh(nodeGeometry, nodeMaterial.clone());
            const idx = Math.floor(Math.random() * (positions.length / 3)) * 3;
            node.position.set(
                positions[idx] * 1.0,
                positions[idx + 1] * 1.0,
                positions[idx + 2] * 1.0
            );
            node.scale.set(0.8, 0.8, 0.8);
            scene.add(node);
        }

        // Connection lines
        const lineGeometry = new THREE.BufferGeometry();
        const linePositions = [];

        for (let i = 0; i < nodeCount - 1; i++) {
            const idx1 = Math.floor(Math.random() * (positions.length / 3)) * 3;
            const idx2 = Math.floor(Math.random() * (positions.length / 3)) * 3;
            
            linePositions.push(
                positions[idx1], positions[idx1 + 1], positions[idx1 + 2],
                positions[idx2], positions[idx2 + 1], positions[idx2 + 2]
            );
        }

        lineGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(linePositions), 3));
        const lineMaterial = new THREE.LineBasicMaterial({
            color: 0x8b5cf6,
            transparent: true,
            opacity: 0.3,
            linewidth: 1
        });
        const lines = new THREE.LineSegments(lineGeometry, lineMaterial);
        scene.add(lines);
    }

    createAdvancedOrbitalRings(scene) {
        const ringConfigs = [
            { radius: 2.5, speed: 0.003, color: 0x8b5cf6, opacity: 0.6 },
            { radius: 3.5, speed: -0.002, color: 0x00e5ff, opacity: 0.4 },
            { radius: 4.5, speed: 0.0015, color: 0x00f5d4, opacity: 0.3 }
        ];

        ringConfigs.forEach((config, idx) => {
            const ringGeometry = new THREE.BufferGeometry();
            const points = [];

            for (let i = 0; i <= 256; i++) {
                const angle = (i / 256) * Math.PI * 2;
                points.push(
                    Math.cos(angle) * config.radius,
                    Math.sin(angle) * (0.1 + idx * 0.05),
                    Math.sin(angle) * config.radius
                );
            }

            ringGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(points), 3));

            const ringMaterial = new THREE.LineBasicMaterial({
                color: config.color,
                transparent: true,
                opacity: config.opacity,
                linewidth: 2
            });

            const ring = new THREE.Line(ringGeometry, ringMaterial);
            ring.userData = {
                speed: config.speed,
                originalRotation: { x: idx * 0.3, y: 0, z: idx * 0.2 }
            };
            scene.add(ring);
        });
    }

    createNeuralParticleSystem(scene) {
        const particleCount = 800;
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(particleCount * 3);
        const velocities = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);

        const colorPalette = [
            new THREE.Color(0x00f5d4),
            new THREE.Color(0x8b5cf6),
            new THREE.Color(0x00e5ff),
            new THREE.Color(0xd7caff)
        ];

        for (let i = 0; i < particleCount; i++) {
            // Positions in sphere
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.random() * Math.PI;
            const r = 3 + Math.random() * 3;

            positions[i * 3] = Math.sin(phi) * Math.cos(theta) * r;
            positions[i * 3 + 1] = Math.cos(phi) * r;
            positions[i * 3 + 2] = Math.sin(phi) * Math.sin(theta) * r;

            // Random velocities
            velocities[i * 3] = (Math.random() - 0.5) * 0.03;
            velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.03;
            velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.03;

            // Random colors
            const color = colorPalette[Math.floor(Math.random() * colorPalette.length)];
            colors[i * 3] = color.r;
            colors[i * 3 + 1] = color.g;
            colors[i * 3 + 2] = color.b;
        }

        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

        const material = new THREE.PointsMaterial({
            size: 0.12,
            sizeAttenuation: true,
            transparent: true,
            opacity: 0.8,
            vertexColors: true
        });

        const particles = new THREE.Points(geometry, material);
        scene.add(particles);

        particles.userData = {
            positions,
            velocities,
            geometry
        };

        return particles;
    }

    createEnergyWaves(scene) {
        const waveCount = 5;
        for (let w = 0; w < waveCount; w++) {
            const waveGeometry = new THREE.TorusGeometry(2 + w * 0.5, 0.15, 16, 128);
            const waveMaterial = new THREE.MeshPhongMaterial({
                color: new THREE.Color().setHSL((w / waveCount) * 0.3 + 0.6, 1, 0.5),
                emissive: new THREE.Color().setHSL((w / waveCount) * 0.3 + 0.6, 1, 0.3),
                emissiveIntensity: 0.5,
                transparent: true,
                opacity: 0.4 - (w * 0.08)
            });

            const wave = new THREE.Mesh(waveGeometry, waveMaterial);
            wave.rotation.x = Math.random() * Math.PI;
            wave.rotation.y = Math.random() * Math.PI;
            wave.userData = {
                rotationSpeed: (Math.random() - 0.5) * 0.01,
                scaleDirection: w % 2 === 0 ? 1 : -1
            };
            scene.add(wave);
        }
    }

    startNeuralSphereAnimation(containerId) {
        const data = this.scenes.get(containerId);
        if (!data) return;

        const animate = () => {
            const { scene, camera, renderer, coreSphere, glowMesh, animations } = data;

            // Rotate core sphere
            coreSphere.rotation.x += animations.coreRotation.x;
            coreSphere.rotation.y += animations.coreRotation.y;
            coreSphere.rotation.z += animations.coreRotation.z;

            // Rotate glow mesh
            glowMesh.rotation.x += animations.glowRotation.x;
            glowMesh.rotation.y += animations.glowRotation.y;
            glowMesh.rotation.z += animations.glowRotation.z;

            // Pulsating scale
            const pulse = 0.98 + Math.sin(Date.now() * 0.004) * 0.02;
            coreSphere.scale.set(pulse, pulse, pulse);

            // Update particle positions
            scene.children.forEach(obj => {
                if (obj instanceof THREE.Points && obj.userData.positions) {
                    const { positions, velocities, geometry } = obj.userData;
                    
                    for (let i = 0; i < positions.length; i += 3) {
                        positions[i] += velocities[i];
                        positions[i + 1] += velocities[i + 1];
                        positions[i + 2] += velocities[i + 2];

                        // Bounds checking
                        if (Math.abs(positions[i]) > 6) velocities[i] *= -1;
                        if (Math.abs(positions[i + 1]) > 6) velocities[i + 1] *= -1;
                        if (Math.abs(positions[i + 2]) > 6) velocities[i + 2] *= -1;
                    }
                    geometry.attributes.position.needsUpdate = true;
                }

                // Rotate orbital rings
                if (obj instanceof THREE.Line && obj.userData.speed) {
                    obj.rotation.z += obj.userData.speed;
                    obj.rotation.x = obj.userData.originalRotation.x + Math.sin(Date.now() * 0.001) * 0.1;
                }

                // Animate energy waves
                if (obj instanceof THREE.Mesh && obj.geometry instanceof THREE.TorusGeometry) {
                    obj.rotation.x += obj.userData.rotationSpeed;
                    obj.rotation.y += obj.userData.rotationSpeed * 0.7;
                    
                    const scale = 1 + Math.sin(Date.now() * 0.003 + obj.userData.rotationSpeed) * 0.08;
                    obj.scale.set(scale, scale, scale);
                }
            });

            renderer.render(scene, camera);
            this.animationFrames.set(containerId, requestAnimationFrame(animate));
        };

        animate();
    }

    onWindowResize(containerId) {
        const data = this.scenes.get(containerId);
        if (!data) return;

        const container = document.getElementById(containerId);
        const width = container.clientWidth;
        const height = container.clientHeight;

        data.camera.aspect = width / height;
        data.camera.updateProjectionMatrix();
        data.renderer.setSize(width, height);
    }

    // ========================================================================
    // ADVANCED 3D AUDIO VISUALIZATION
    // ========================================================================

    createAudio3DVisualization(containerId, audioElementId) {
        const container = document.getElementById(containerId);
        if (!container || !this.isWebGLSupported) return;

        const width = container.clientWidth;
        const height = container.clientHeight;

        // Setup audio context
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }

        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x050510);

        const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
        camera.position.z = 15;

        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(width, height);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
        container.appendChild(renderer.domElement);

        // Lighting
        const light = new THREE.PointLight(0x00e5ff, 2, 300);
        light.position.set(10, 10, 10);
        scene.add(light);

        scene.add(new THREE.AmbientLight(0xffffff, 0.3));

        // Frequency bars
        const barCount = 64;
        const barGeometry = new THREE.BoxGeometry(1, 1, 1);
        const bars = [];

        for (let i = 0; i < barCount; i++) {
            const barMaterial = new THREE.MeshPhongMaterial({
                color: new THREE.Color().setHSL(i / barCount, 1, 0.5),
                emissive: new THREE.Color().setHSL(i / barCount, 1, 0.3),
                emissiveIntensity: 0.6
            });

            const bar = new THREE.Mesh(barGeometry, barMaterial);
            const angle = (i / barCount) * Math.PI * 2;
            bar.position.x = Math.cos(angle) * 8;
            bar.position.z = Math.sin(angle) * 8;
            bar.scale.set(0.8, 1, 0.8);
            scene.add(bar);
            bars.push(bar);
        }

        // Waveform ring
        const waveformGeometry = new THREE.BufferGeometry();
        const waveformMaterial = new THREE.LineBasicMaterial({ color: 0x00f5d4, linewidth: 2 });
        const waveformLine = new THREE.Line(waveformGeometry, waveformMaterial);
        scene.add(waveformLine);

        // Connect to audio element
        const audioElement = document.getElementById(audioElementId);
        if (audioElement) {
            const source = this.audioContext.createMediaElementAudioSource(audioElement);
            this.audioAnalyser = this.audioContext.createAnalyser();
            this.audioAnalyser.fftSize = 256;
            source.connect(this.audioAnalyser);
            this.audioAnalyser.connect(this.audioContext.destination);
        }

        // Animation
        const animate = () => {
            if (this.audioAnalyser) {
                const dataArray = new Uint8Array(this.audioAnalyser.frequencyBinCount);
                this.audioAnalyser.getByteFrequencyData(dataArray);

                // Update bars
                bars.forEach((bar, idx) => {
                    const value = dataArray[idx] / 255;
                    bar.scale.y = 1 + value * 3;
                    bar.position.y = bar.scale.y / 2;

                    const color = new THREE.Color().setHSL(idx / barCount, 1, 0.3 + value * 0.4);
                    bar.material.color.copy(color);
                    bar.material.emissive.copy(color);
                    bar.material.emissiveIntensity = 0.3 + value * 0.7;
                });

                // Update waveform
                const waveformData = new Uint8Array(this.audioAnalyser.fftSize);
                this.audioAnalyser.getByteTimeDomainData(waveformData);
                
                const wavePoints = [];
                for (let i = 0; i < waveformData.length; i++) {
                    const angle = (i / waveformData.length) * Math.PI * 2;
                    const radius = 5 + (waveformData[i] / 255) * 2;
                    wavePoints.push(
                        Math.cos(angle) * radius,
                        (waveformData[i] / 128 - 1) * 3,
                        Math.sin(angle) * radius
                    );
                }
                
                waveformGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(wavePoints), 3));
            }

            renderer.render(scene, camera);
            requestAnimationFrame(animate);
        };

        animate();

        return { scene, camera, renderer };
    }

    // ========================================================================
    // CYBERSECURITY SHIELD SYSTEM
    // ========================================================================

    createCybersecurityShield(containerId, threatState = 'safe') {
        const container = document.getElementById(containerId);
        if (!container) return;

        const canvas = document.createElement('canvas');
        container.innerHTML = '';
        container.style.position = 'relative';
        container.appendChild(canvas);

        const width = container.clientWidth;
        const height = container.clientHeight;

        canvas.width = width;
        canvas.height = height;

        const ctx = canvas.getContext('2d');
        const centerX = width / 2;
        const centerY = height / 2;
        const maxRadius = Math.min(width, height) * 0.35;

        const shieldColors = {
            safe: { glow: '#00f5d4', outer: '#00e5ff', inner: '#8b5cf6', pulse: 'rgba(0, 245, 212, 0.6)' },
            suspicious: { glow: '#f59e0b', outer: '#fbbf24', inner: '#f97316', pulse: 'rgba(245, 158, 11, 0.6)' },
            danger: { glow: '#ef4444', outer: '#f87171', inner: '#dc2626', pulse: 'rgba(239, 68, 68, 0.6)' }
        };

        const colors = shieldColors[threatState] || shieldColors.safe;
        let rotation = 0;
        let pulse = 0;

        const animate = () => {
            rotation += 2;
            pulse = Math.sin(Date.now() * 0.003) * 0.5 + 0.5;

            ctx.clearRect(0, 0, width, height);

            // Outer glow
            const glowGradient = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, maxRadius * 1.8);
            glowGradient.addColorStop(0, 'rgba(0,0,0,0)');
            glowGradient.addColorStop(0.3, colors.glow.replace('1)', `${0.3 * pulse})`));
            glowGradient.addColorStop(1, 'rgba(0,0,0,0)');
            
            ctx.fillStyle = glowGradient;
            ctx.beginPath();
            ctx.arc(centerX, centerY, maxRadius * 1.8, 0, Math.PI * 2);
            ctx.fill();

            // Main shield layers
            ctx.save();
            ctx.translate(centerX, centerY);
            ctx.rotate((rotation * Math.PI) / 180);

            // Outer ring
            ctx.strokeStyle = colors.outer;
            ctx.lineWidth = 4;
            ctx.globalAlpha = 0.8;
            ctx.beginPath();
            ctx.arc(0, 0, maxRadius, 0, Math.PI * 2);
            ctx.stroke();

            // Inner ring
            ctx.strokeStyle = colors.inner;
            ctx.lineWidth = 3;
            ctx.globalAlpha = 0.6;
            ctx.beginPath();
            ctx.arc(0, 0, maxRadius * 0.7, 0, Math.PI * 2);
            ctx.stroke();

            // Protection rays
            ctx.globalAlpha = 0.4 + pulse * 0.3;
            ctx.strokeStyle = colors.glow;
            ctx.lineWidth = 2;

            for (let i = 0; i < 12; i++) {
                const angle = (i / 12) * Math.PI * 2;
                const x1 = Math.cos(angle) * maxRadius;
                const y1 = Math.sin(angle) * maxRadius;
                const x2 = Math.cos(angle) * maxRadius * 1.3;
                const y2 = Math.sin(angle) * maxRadius * 1.3;

                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x2, y2);
                ctx.stroke();
            }

            ctx.restore();
            ctx.globalAlpha = 1;

            requestAnimationFrame(animate);
        };

        animate();
    }

    // ========================================================================
    // CYBER RADAR SYSTEM
    // ========================================================================

    createCyberRadar(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const canvas = document.createElement('canvas');
        container.innerHTML = '';
        container.appendChild(canvas);

        const width = container.clientWidth;
        const height = container.clientHeight;
        
        canvas.width = width;
        canvas.height = height;

        const ctx = canvas.getContext('2d');
        const centerX = width / 2;
        const centerY = height / 2;
        const maxRadius = Math.min(width, height) * 0.35;

        let scanAngle = 0;
        let threats = [];

        // Generate initial threats
        for (let i = 0; i < 5; i++) {
            threats.push({
                angle: Math.random() * Math.PI * 2,
                radius: Math.random() * maxRadius * 0.8,
                speed: Math.random() * 0.01 - 0.005,
                size: Math.random() * 8 + 4,
                type: Math.random() > 0.7 ? 'critical' : 'warning'
            });
        }

        const animate = () => {
            scanAngle += 2;

            ctx.clearRect(0, 0, width, height);
            ctx.fillStyle = '#050510';
            ctx.fillRect(0, 0, width, height);

            ctx.save();
            ctx.translate(centerX, centerY);

            // Draw radar rings
            ctx.strokeStyle = 'rgba(0, 229, 255, 0.2)';
            ctx.lineWidth = 1;
            for (let i = 0; i < 5; i++) {
                ctx.beginPath();
                ctx.arc(0, 0, (maxRadius / 5) * (i + 1), 0, Math.PI * 2);
                ctx.stroke();
            }

            // Draw crosshairs
            ctx.strokeStyle = 'rgba(0, 229, 255, 0.15)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(-maxRadius, 0);
            ctx.lineTo(maxRadius, 0);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(0, -maxRadius);
            ctx.lineTo(0, maxRadius);
            ctx.stroke();

            // Draw scanning beam
            ctx.strokeStyle = 'rgba(0, 245, 212, 0.3)';
            ctx.lineWidth = 2;
            const scanStart = (scanAngle * Math.PI) / 180;
            const scanEnd = scanStart + (Math.PI / 6);
            ctx.beginPath();
            ctx.moveTo(0, 0);
            ctx.arc(0, 0, maxRadius, scanStart, scanEnd);
            ctx.lineTo(0, 0);
            ctx.stroke();

            // Update and draw threats
            threats.forEach((threat, idx) => {
                threat.angle += threat.speed;
                threat.angle = (threat.angle + Math.PI * 2) % (Math.PI * 2);

                const x = Math.cos(threat.angle) * threat.radius;
                const y = Math.sin(threat.angle) * threat.radius;

                const color = threat.type === 'critical' ? '#ef4444' : '#f59e0b';
                ctx.fillStyle = color;
                ctx.globalAlpha = 0.3;
                ctx.beginPath();
                ctx.arc(x, y, threat.size * 2, 0, Math.PI * 2);
                ctx.fill();

                ctx.globalAlpha = 1;
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(x, y, threat.size, 0, Math.PI * 2);
                ctx.fill();

                // Threat rings
                ctx.strokeStyle = color;
                ctx.globalAlpha = 0.5;
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.arc(x, y, threat.size * 2.5, 0, Math.PI * 2);
                ctx.stroke();
            });

            ctx.restore();
            ctx.globalAlpha = 1;

            requestAnimationFrame(animate);
        };

        animate();
    }

    // ========================================================================
    // INITIALIZATION & CLEANUP
    // ========================================================================

    initialize() {
        if (this.initialized) return;
        this.initialized = true;

        // Apply global animations via GSAP
        this.applyGlobalAnimations();

        console.log('✅ Advanced 3D System initialized');
    }

    applyGlobalAnimations() {
        if (typeof gsap === 'undefined') return;

        // Cinematic element reveals
        gsap.fromTo('.card, .metric-card', 
            { opacity: 0, y: 30, rotation: 2 },
            {
                opacity: 1, y: 0, rotation: 0,
                duration: 0.8,
                stagger: 0.1,
                ease: 'back.out',
                scrollTrigger: {
                    trigger: '.card',
                    start: 'top 85%'
                }
            }
        );
    }

    cleanup(containerId) {
        if (this.scenes.has(containerId)) {
            const data = this.scenes.get(containerId);
            if (data.renderer) {
                data.renderer.dispose();
            }
            this.scenes.delete(containerId);
        }

        if (this.renderers.has(containerId)) {
            this.renderers.delete(containerId);
        }

        if (this.animationFrames.has(containerId)) {
            cancelAnimationFrame(this.animationFrames.get(containerId));
            this.animationFrames.delete(containerId);
        }
    }

    destroy() {
        this.scenes.forEach((_, containerId) => {
            this.cleanup(containerId);
        });
        this.scenes.clear();
        this.renderers.clear();
        this.animationFrames.clear();
    }
}

// Export for global use
window.AdvancedVoiceGuard3D = AdvancedVoiceGuard3D;

console.log('✅ Advanced 3D System loaded');
