/**
 * VOICEGUARD AI — Landing Page Controller & Visualizer
 * Manages 3D Hero Visualizer, Real-Time Audio Canvas, Navigation & Auth Modal.
 */

'use strict';

document.addEventListener('DOMContentLoaded', () => {
    // ========================================================================
    // 1. 3D HERO VISUALIZER (THREE.JS)
    // ========================================================================
    const canvas3d = document.getElementById('hero-3d-canvas');
    if (canvas3d && window.THREE) {
        initHero3dScene(canvas3d);
    }

    function initHero3dScene(canvas) {
        const THREE = window.THREE;
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(45, canvas.clientWidth / canvas.clientHeight, 0.1, 100);
        camera.position.z = 4.5;

        const renderer = new THREE.WebGLRenderer({
            canvas,
            alpha: true,
            antialias: true,
            powerPreference: 'high-performance'
        });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.setSize(canvas.clientWidth, canvas.clientHeight, false);

        // Core Group
        const rootGroup = new THREE.Group();
        scene.add(rootGroup);

        // 1. Glowing Icosahedron Core
        const coreGeo = new THREE.IcosahedronGeometry(0.85, 2);
        const coreMat = new THREE.MeshStandardMaterial({
            color: 0x00f2fe,
            emissive: 0x004488,
            emissiveIntensity: 0.8,
            roughness: 0.25,
            metalness: 0.8,
            wireframe: false
        });
        const coreMesh = new THREE.Mesh(coreGeo, coreMat);
        rootGroup.add(coreMesh);

        // 2. Cyber Wireframe Cage
        const wireGeo = new THREE.IcosahedronGeometry(0.87, 2);
        const wireMat = new THREE.MeshBasicMaterial({
            color: 0x38bdf8,
            wireframe: true,
            transparent: true,
            opacity: 0.35
        });
        const wireMesh = new THREE.Mesh(wireGeo, wireMat);
        rootGroup.add(wireMesh);

        // 3. Orbital Shield Rings
        const ringConfigs = [
            { radius: 1.25, tube: 0.012, color: 0x00f2fe, rot: [0.7, 0.4, 0] },
            { radius: 1.45, tube: 0.010, color: 0x8b5cf6, rot: [1.2, -0.6, 0.4] },
            { radius: 1.65, tube: 0.008, color: 0x38bdf8, rot: [0.2, 1.1, -0.5] }
        ];

        const rings = ringConfigs.map(cfg => {
            const geo = new THREE.TorusGeometry(cfg.radius, cfg.tube, 16, 100);
            const mat = new THREE.MeshBasicMaterial({
                color: cfg.color,
                transparent: true,
                opacity: 0.75
            });
            const mesh = new THREE.Mesh(geo, mat);
            mesh.rotation.set(...cfg.rot);
            rootGroup.add(mesh);
            return mesh;
        });

        // 4. Floating Neural Particles
        const particleCount = 180;
        const particleGeo = new THREE.BufferGeometry();
        const posArray = new Float32Array(particleCount * 3);
        const colorArray = new Float32Array(particleCount * 3);

        for (let i = 0; i < particleCount; i++) {
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos((Math.random() * 2) - 1);
            const radius = 1.3 + Math.random() * 0.8;

            posArray[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
            posArray[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
            posArray[i * 3 + 2] = radius * Math.cos(phi);

            // Alternate Cyan and Violet particles
            const isCyan = i % 2 === 0;
            colorArray[i * 3] = isCyan ? 0.0 : 0.54;
            colorArray[i * 3 + 1] = isCyan ? 0.95 : 0.36;
            colorArray[i * 3 + 2] = isCyan ? 0.99 : 0.96;
        }

        particleGeo.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
        particleGeo.setAttribute('color', new THREE.BufferAttribute(colorArray, 3));

        const particleMat = new THREE.PointsMaterial({
            size: 0.035,
            vertexColors: true,
            transparent: true,
            opacity: 0.85
        });
        const particles = new THREE.Points(particleGeo, particleMat);
        rootGroup.add(particles);

        // Lighting
        const ambLight = new THREE.AmbientLight(0xffffff, 0.8);
        scene.add(ambLight);

        const pointLight1 = new THREE.PointLight(0x00f2fe, 3, 10);
        pointLight1.position.set(3, 3, 3);
        scene.add(pointLight1);

        const pointLight2 = new THREE.PointLight(0x8b5cf6, 3, 10);
        pointLight2.position.set(-3, -2, 2);
        scene.add(pointLight2);

        // Mouse Parallax
        let targetRotX = 0;
        let targetRotY = 0;

        window.addEventListener('mousemove', e => {
            const normX = (e.clientX / window.innerWidth) * 2 - 1;
            const normY = -(e.clientY / window.innerHeight) * 2 + 1;
            targetRotY = normX * 0.4;
            targetRotX = -normY * 0.3;
        });

        // Resize Listener
        window.addEventListener('resize', () => {
            if (!canvas.parentElement) return;
            const w = canvas.parentElement.clientWidth;
            const h = canvas.parentElement.clientHeight;
            camera.aspect = w / h;
            camera.updateProjectionMatrix();
            renderer.setSize(w, h, false);
        });

        // Animation Loop
        let clock = new THREE.Clock();
        function animate() {
            requestAnimationFrame(animate);
            const delta = clock.getDelta();
            const elapsed = clock.getElapsedTime();

            // Smooth mouse follow
            rootGroup.rotation.y += (targetRotY - rootGroup.rotation.y) * 0.05;
            rootGroup.rotation.x += (targetRotX - rootGroup.rotation.x) * 0.05;

            // Idle rotation
            coreMesh.rotation.y += delta * 0.4;
            wireMesh.rotation.y -= delta * 0.2;
            particles.rotation.y += delta * 0.15;

            // Ring orbits
            rings[0].rotation.z += delta * 0.3;
            rings[1].rotation.x += delta * 0.25;
            rings[2].rotation.y += delta * 0.2;

            // Core breathing pulse
            const scale = 1 + Math.sin(elapsed * 2.5) * 0.04;
            coreMesh.scale.set(scale, scale, scale);

            renderer.render(scene, camera);
        }
        animate();
    }

    // ========================================================================
    // 2. DYNAMIC VOICE WAVEFORM CANVAS
    // ========================================================================
    const waveCanvas = document.getElementById('hero-waveform-canvas');
    if (waveCanvas) {
        initWaveformVisualizer(waveCanvas);
    }

    function initWaveformVisualizer(canvas) {
        const ctx = canvas.getContext('2d');
        let dpr = window.devicePixelRatio || 1;

        function resize() {
            const rect = canvas.getBoundingClientRect();
            canvas.width = rect.width * dpr;
            canvas.height = rect.height * dpr;
            ctx.scale(dpr, dpr);
        }
        resize();
        window.addEventListener('resize', resize);

        let phase = 0;
        function drawWave() {
            requestAnimationFrame(drawWave);
            const w = canvas.width / dpr;
            const h = canvas.height / dpr;
            ctx.clearRect(0, 0, w, h);

            phase += 0.035;
            ctx.lineWidth = 2;

            // Draw primary cyan wave
            ctx.strokeStyle = '#00f2fe';
            ctx.beginPath();
            for (let x = 0; x < w; x++) {
                const normX = x / w;
                const envelope = Math.sin(normX * Math.PI); // tapering edges
                const y = h / 2 + Math.sin(normX * 18 + phase) * 16 * envelope 
                                + Math.cos(normX * 8 - phase * 0.7) * 8 * envelope;
                if (x === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();

            // Draw secondary purple harmonic wave
            ctx.strokeStyle = 'rgba(139, 92, 246, 0.6)';
            ctx.beginPath();
            for (let x = 0; x < w; x++) {
                const normX = x / w;
                const envelope = Math.sin(normX * Math.PI);
                const y = h / 2 + Math.sin(normX * 14 - phase * 1.2) * 12 * envelope;
                if (x === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();
        }
        drawWave();
    }

    // ========================================================================
    // 3. AUTH MODAL (SIGN IN / SIGN UP)
    // ========================================================================
    const modal = document.getElementById('cyber-auth-modal');
    const openBtns = document.querySelectorAll('[data-open-auth]');
    const closeBtn = document.getElementById('modal-close-btn');
    const tabSignin = document.getElementById('tab-signin-btn');
    const tabSignup = document.getElementById('tab-signup-btn');
    const signinForm = document.getElementById('modal-signin-form');
    const signupForm = document.getElementById('modal-signup-form');
    const feedbackBanner = document.getElementById('auth-modal-feedback');

    function showAuthModal(defaultTab = 'signin') {
        if (!modal) return;
        modal.classList.add('active');
        switchAuthTab(defaultTab);
        clearFeedback();
    }

    function hideAuthModal() {
        if (!modal) return;
        modal.classList.remove('active');
        clearFeedback();
    }

    function switchAuthTab(tab) {
        if (tab === 'signup') {
            tabSignup?.classList.add('active');
            tabSignin?.classList.remove('active');
            signinForm.style.display = 'none';
            signupForm.style.display = 'block';
        } else {
            tabSignin?.classList.add('active');
            tabSignup?.classList.remove('active');
            signinForm.style.display = 'block';
            signupForm.style.display = 'none';
        }
        clearFeedback();
    }

    function showFeedback(msg, type = 'error') {
        if (!feedbackBanner) return;
        feedbackBanner.textContent = msg;
        feedbackBanner.className = `auth-feedback-banner ${type}`;
        feedbackBanner.style.display = 'block';
    }

    function clearFeedback() {
        if (!feedbackBanner) return;
        feedbackBanner.style.display = 'none';
        feedbackBanner.textContent = '';
    }

    [signinForm, signupForm].forEach(form => {
        if (!form) return;
        const button = form.querySelector('button[type="submit"]');
        button.dataset.originalLabel = button.textContent.trim();
    });

    function setSubmitting(form, submitting, label) {
        const button = form.querySelector('button[type="submit"]');
        button.disabled = submitting;
        button.setAttribute('aria-busy', String(submitting));
        button.textContent = submitting ? label : button.dataset.originalLabel;
    }

    function getAppUrl() {
        return window.VOICEGUARD_CONFIG
            ? window.VOICEGUARD_CONFIG.resolveUrl('/app')
            : '/app';
    }

    function showAuthError(error, fallback) {
        const message = String(error.message || '');
        if ((error.status === 400 || error.status === 409) && /already exists|duplicate/i.test(message)) {
            showFeedback('An account with this email already exists. Sign in or use a different email.');
        } else if (error.status === 401) {
            showFeedback('The email or password is incorrect.');
        } else if (error.isNetworkError || /failed to fetch|cannot connect|network/i.test(message)) {
            showFeedback('Unable to connect to the VoiceGuard backend. Please verify that the backend server is running at http://127.0.0.1:8000 (run start_voiceguard.ps1 or start_voiceguard.bat) and open http://127.0.0.1:8000 in your browser.');
        } else {
            showFeedback(message || fallback);
        }
    }

    openBtns.forEach(btn => {
        btn.addEventListener('click', e => {
            e.preventDefault();
            const tab = btn.getAttribute('data-open-auth') || 'signin';
            showAuthModal(tab);
        });
    });

    closeBtn?.addEventListener('click', hideAuthModal);
    modal?.addEventListener('click', e => {
        if (e.target === modal) hideAuthModal();
    });

    tabSignin?.addEventListener('click', () => switchAuthTab('signin'));
    tabSignup?.addEventListener('click', () => switchAuthTab('signup'));

    // Quick demo credentials auto-fill
    const demoFillBtn = document.getElementById('btn-fill-demo');
    if (demoFillBtn) {
        demoFillBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const emailInput = document.getElementById('signin-email');
            const pwdInput = document.getElementById('signin-password');
            if (emailInput) emailInput.value = 'analyst@voiceguard.ai';
            if (pwdInput) pwdInput.value = 'VoiceGuard@2026!';
            showFeedback('Demo credentials filled. Click "Sign In to Workspace".', 'success');
        });
    }

    // Handle Sign In submission
    signinForm?.addEventListener('submit', async e => {
        e.preventDefault();

        const formData = new FormData(signinForm);
        const email = String(formData.get('email') || document.getElementById('signin-email')?.value || '').trim();
        const password = String(formData.get('password') || document.getElementById('signin-password')?.value || '');
        const remember = formData.get('remember') === 'on' || document.getElementById('signin-remember')?.checked === true;
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 255) {
            showFeedback('Enter a valid email address.');
            return;
        }
        if (!password || password.length > 128) {
            showFeedback('Enter your password (up to 128 characters).');
            return;
        }

        setSubmitting(signinForm, true, 'Verifying credentials...');
        clearFeedback();

        try {
            if (window.VoiceGuardAPI) {
                await window.VoiceGuardAPI.login(email, password, remember);
                showFeedback('Authentication successful. Redirecting...', 'success');
                setTimeout(() => {
                    window.location.assign(getAppUrl());
                }, 800);
            } else {
                throw new Error('API client unavailable.');
            }
        } catch (err) {
            showAuthError(err, 'Sign in could not be completed. Please try again.');
            setSubmitting(signinForm, false);
        }
    });

    // Handle Sign Up submission
    signupForm?.addEventListener('submit', async e => {
        e.preventDefault();
        const formData = new FormData(signupForm);
        const fullName = String(formData.get('fullName') || '').trim();
        const email = String(formData.get('email') || '').trim().toLowerCase();
        const password = String(formData.get('password') || '');
        const terms = formData.get('terms') === 'on' || formData.get('terms') === 'true';
        if (fullName.length < 2 || fullName.length > 100) {
            showFeedback('Enter a full name between 2 and 100 characters.');
            return;
        }
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 255) {
            showFeedback('Please enter a valid email address.');
            return;
        }
        if (password.length < 12 || password.length > 128 ||
            !/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/[0-9]/.test(password)) {
            showFeedback('Use 12–128 characters with at least one uppercase letter, lowercase letter, and number.');
            return;
        }
        if (!terms) {
            showFeedback('You must accept the terms of service.');
            return;
        }

        setSubmitting(signupForm, true, 'Creating account...');
        clearFeedback();

        try {
            if (window.VoiceGuardAPI) {
                await window.VoiceGuardAPI.signup(fullName, email, password, true);
                showFeedback('Account created successfully! Launching workspace...', 'success');
                setTimeout(() => {
                    window.location.assign(getAppUrl());
                }, 900);
            } else {
                throw new Error('API client unavailable.');
            }
        } catch (err) {
            showAuthError(err, 'Registration failed. Please try again.');
            setSubmitting(signupForm, false);
        }
    });

    // Automatically open Sign In or Sign Up modal if accessed via /login or /signup
    const currentPath = window.location.pathname;
    const urlParams = new URLSearchParams(window.location.search);
    if (currentPath === '/login' || urlParams.get('auth') === 'login' || urlParams.get('view') === 'login') {
        showAuthModal('signin');
    } else if (currentPath === '/signup' || urlParams.get('auth') === 'signup' || urlParams.get('view') === 'signup') {
        showAuthModal('signup');
    }

    // Auto-detect and redirect when opened via file:// protocol
    if (window.location.protocol === 'file:') {
        fetch('http://127.0.0.1:8000/health', { mode: 'cors' })
            .then(res => res.json())
            .then(data => {
                if (data && data.status === 'healthy') {
                    console.info('[VoiceGuard AI] Backend detected at http://127.0.0.1:8000. Redirecting from file:// to full web application...');
                    window.location.href = 'http://127.0.0.1:8000/' + window.location.search + window.location.hash;
                }
            })
            .catch(() => {
                console.warn('[VoiceGuard AI] Running from local file. Backend is not yet reachable on http://127.0.0.1:8000.');
            });
    }

    // Auto-check existing session on landing page
    if (window.VoiceGuardAPI) {
        window.VoiceGuardAPI.getStatus().then(async status => {
            if (status.authenticated) {
                await window.VoiceGuardAPI.getMe();
                const launchBtns = document.querySelectorAll('.btn-launch-console');
                launchBtns.forEach(btn => {
                    btn.textContent = 'Enter Console →';
                    btn.href = getAppUrl();
                });
            }
        }).catch(error => {
            console.warn('[VoiceGuardAuth] Unable to restore the current session:', error.message);
        });
    }
});

