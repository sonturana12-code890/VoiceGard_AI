'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('landing-core');
    const host = canvas?.parentElement;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (!canvas || !host) return;

    let renderer;
    let frameId = null;
    let lastFrame = 0;
    let scene;
    let camera;
    let core;
    let rings;
    let particles;
    const pointer = { x: 0, y: 0 };
    const targetPointer = { x: 0, y: 0 };

    try {
        if (!window.THREE) throw new Error('Three.js was not loaded.');
        const THREE = window.THREE;
        scene = new THREE.Scene();
        camera = new THREE.PerspectiveCamera(42, 1, 0.1, 30);
        camera.position.z = 4.3;
        renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false, powerPreference: 'low-power' });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.25));
        renderer.setClearColor(0x000000, 0);

        const group = new THREE.Group();
        scene.add(group);
        core = new THREE.Mesh(
            new THREE.IcosahedronGeometry(.83, 2),
            new THREE.MeshStandardMaterial({
                color: 0x332767,
                emissive: 0x28165f,
                emissiveIntensity: 1.1,
                roughness: .36,
                metalness: .58
            })
        );
        group.add(core);
        const wire = new THREE.Mesh(
            new THREE.IcosahedronGeometry(.845, 2),
            new THREE.MeshBasicMaterial({ color: 0x00f5d4, wireframe: true, transparent: true, opacity: .25 })
        );
        group.add(wire);

        rings = [
            new THREE.Mesh(new THREE.TorusGeometry(1.13, .008, 5, 96), new THREE.MeshBasicMaterial({ color: 0x9b7aff, transparent: true, opacity: .7 })),
            new THREE.Mesh(new THREE.TorusGeometry(1.28, .006, 5, 96), new THREE.MeshBasicMaterial({ color: 0x00cfff, transparent: true, opacity: .6 })),
            new THREE.Mesh(new THREE.TorusGeometry(.98, .005, 5, 96), new THREE.MeshBasicMaterial({ color: 0x00f5d4, transparent: true, opacity: .42 }))
        ];
        rings[0].rotation.set(.87, .31, .12);
        rings[1].rotation.set(1.25, -.45, .68);
        rings[2].rotation.set(.18, 1.1, -.4);
        group.add(...rings);

        const count = 88;
        const positions = new Float32Array(count * 3);
        const colors = new Float32Array(count * 3);
        for (let i = 0; i < count; i++) {
            const y = 1 - (i / (count - 1)) * 2;
            const radius = Math.sqrt(1 - y * y);
            const angle = Math.PI * (3 - Math.sqrt(5)) * i;
            const offset = i * 3;
            const spread = 1.34 + (i % 5) * .045;
            positions[offset] = Math.cos(angle) * radius * spread;
            positions[offset + 1] = y * spread;
            positions[offset + 2] = Math.sin(angle) * radius * spread;
            const color = new THREE.Color(i % 4 === 0 ? 0x00f5d4 : 0x9b72ff);
            colors[offset] = color.r;
            colors[offset + 1] = color.g;
            colors[offset + 2] = color.b;
        }
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        particles = new THREE.Points(geometry, new THREE.PointsMaterial({
            size: .025,
            vertexColors: true,
            transparent: true,
            opacity: .85,
            sizeAttenuation: true
        }));
        group.add(particles);
        scene.add(new THREE.AmbientLight(0x98a4ff, 1.5));
        const cyanLight = new THREE.PointLight(0x00f5d4, 7, 8);
        cyanLight.position.set(-2, 1.6, 3);
        scene.add(cyanLight);
        const violetLight = new THREE.PointLight(0x8b5cf6, 8, 8);
        violetLight.position.set(2, -1.2, 2);
        scene.add(violetLight);
        core.userData.group = group;

        const resize = () => {
            const rect = host.getBoundingClientRect();
            if (!rect.width || !rect.height) return;
            camera.aspect = rect.width / rect.height;
            camera.updateProjectionMatrix();
            renderer.setSize(rect.width, rect.height, false);
            if (reducedMotion.matches) renderer.render(scene, camera);
        };
        new ResizeObserver(resize).observe(host);
        resize();
    } catch (error) {
        console.warn('3D landing visual unavailable; using the CSS fallback.', error);
        canvas.hidden = true;
        return;
    }

    function render(timestamp = 0) {
        frameId = null;
        if (document.hidden || reducedMotion.matches || !renderer) return;
        if (timestamp - lastFrame < 33) {
            frameId = requestAnimationFrame(render);
            return;
        }
        lastFrame = timestamp;
        const time = timestamp * .001;
        const group = core.userData.group;
        pointer.x += (targetPointer.x - pointer.x) * .035;
        pointer.y += (targetPointer.y - pointer.y) * .035;
        group.rotation.y = time * .15 + pointer.x * .16;
        group.rotation.x = Math.sin(time * .22) * .08 - pointer.y * .1;
        core.rotation.y = -time * .14;
        rings[0].rotation.z = .12 + time * .18;
        rings[1].rotation.y = -.45 + time * .15;
        rings[2].rotation.x = .18 - time * .12;
        particles.rotation.y = -time * .07;
        renderer.render(scene, camera);
        frameId = requestAnimationFrame(render);
    }

    function start() {
        if (reducedMotion.matches) {
            if (frameId) cancelAnimationFrame(frameId);
            frameId = null;
            renderer.render(scene, camera);
            return;
        }
        if (!frameId && !document.hidden) frameId = requestAnimationFrame(render);
    }
    host.addEventListener('pointermove', event => {
        const rect = host.getBoundingClientRect();
        targetPointer.x = ((event.clientX - rect.left) / rect.width - .5) * 2;
        targetPointer.y = ((event.clientY - rect.top) / rect.height - .5) * 2;
    });
    host.addEventListener('pointerleave', () => {
        targetPointer.x = 0;
        targetPointer.y = 0;
    });
    document.addEventListener('visibilitychange', start);
    reducedMotion.addEventListener?.('change', start);
    start();
});
