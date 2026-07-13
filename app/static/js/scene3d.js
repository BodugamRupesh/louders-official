/**
 * LOUD Platform - Redesigned Cinematic 3D WebGL Background Engine
 * Incorporates:
 * - Volumetric light beams & rotating light shafts
 * - Emissive canvas holographic text mapping on the central license key
 * - Frosted glass cubes, triangular prisms, crystal icosahedrons, and shards
 * - Ambient fog, sweeping point lights, particles, and idle camera orbits.
 */

const LOUDScene3D = (() => {
    let scene, camera, renderer;
    let mainGroup;       // Holds the holographic card
    let backgroundGroup; // Holds orbiting glass geometry
    let lightBeamGroup;  // Holds volumetric cylinders representing light rays
    let licenseCard, particleSystem;
    
    // Position targets for active views
    let targetGroupX = 2.0;
    let targetGroupY = 0;
    let targetGroupScale = 1.0;
    let targetCardOpacity = 1.0;
    
    let currentGroupX = 2.0;
    let currentGroupY = 0;
    let currentGroupScale = 1.0;
    let currentCardOpacity = 1.0;

    let backgroundObjects = [];
    let lightBeams = [];
    
    // Parallax mouse variables
    let mouseX = 0, mouseY = 0;
    let targetCameraX = 0, targetCameraY = 0;
    let currentCameraX = 0, currentCameraY = 0;
    
    let animationFrameId = null;
    let isInitialized = false;

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function init() {
        if (isInitialized) return;
        
        const canvas = document.getElementById('hero-3d-canvas');
        if (!canvas) return;

        const width = window.innerWidth;
        const height = window.innerHeight;

        // 1. Scene & Atmosphere Fog
        scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x050816, 0.08);

        // 2. Camera Setup
        camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
        camera.position.set(0, 0, 9.5);

        // 3. WebGL Renderer
        renderer = new THREE.WebGLRenderer({
            canvas: canvas,
            antialias: true,
            alpha: true,
            powerPreference: "high-performance"
        });
        renderer.setSize(width, height, false);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        // 4. Lighting Rig (Cyan, Violet, Blue colors)
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.2);
        scene.add(ambientLight);

        // Blue Point Light
        const blueLight = new THREE.PointLight(0x3b82f6, 6, 25);
        blueLight.position.set(-6, 5, 4);
        scene.add(blueLight);

        // Cyan Point Light
        const cyanLight = new THREE.PointLight(0x22d3ee, 6, 25);
        cyanLight.position.set(6, -5, 4);
        scene.add(cyanLight);

        // Violet Ambient Glow Point Light
        const violetLight = new THREE.PointLight(0x8b5cf6, 8, 30);
        violetLight.position.set(0, 0, 5);
        scene.add(violetLight);

        // Soft Directional Light for glass specular highlights
        const dirLight = new THREE.DirectionalLight(0xffffff, 1.5);
        dirLight.position.set(2, 8, 6);
        scene.add(dirLight);

        // 5. Container Groups
        backgroundGroup = new THREE.Group();
        scene.add(backgroundGroup);

        mainGroup = new THREE.Group();
        scene.add(mainGroup);

        lightBeamGroup = new THREE.Group();
        scene.add(lightBeamGroup);

        // 6. Build Scene Assets
        createLicenseCard();
        createAbstractGlassGeometry();
        createVolumetricLightBeams();
        createFloatingParticles();

        // 7. Event Listeners
        window.addEventListener('resize', onWindowResize);
        if (!prefersReducedMotion) {
            window.addEventListener('mousemove', onMouseMove);
        }

        isInitialized = true;
        
        // 8. Start Loop
        animate(0);
    }

    function setView(viewName) {
        if (!isInitialized) init();
        
        if (viewName === 'landing') {
            targetGroupX = 1.9;
            targetGroupY = 0;
            targetGroupScale = 1.0;
            targetCardOpacity = 1.0;
        } else if (viewName === 'login') {
            targetGroupX = 0;
            targetGroupY = 0.55;
            targetGroupScale = 0.95;
            targetCardOpacity = 0.65;
        } else if (viewName === 'dashboard') {
            targetGroupX = 0;
            targetGroupY = -12; // Animate out of view
            targetGroupScale = 0.1;
            targetCardOpacity = 0;
        }
    }

    function createLicenseCard() {
        licenseCard = new THREE.Group();

        // Main glass body
        const geometry = new THREE.BoxGeometry(3.1, 1.95, 0.08);

        // Physically based glass material
        const glassMaterial = new THREE.MeshPhysicalMaterial({
            color: 0xffffff,
            transparent: true,
            opacity: 0.24,
            roughness: 0.05,
            metalness: 0.05,
            transmission: 0.95, // High refraction transmission
            ior: 1.55,          // Refractive index
            thickness: 0.6,
            specularIntensity: 1.2,
            clearcoat: 1.0,
            clearcoatRoughness: 0.05
        });

        const cardBody = new THREE.Mesh(geometry, glassMaterial);
        licenseCard.add(cardBody);

        // Holographic Canvas Texture Layer (emissive print text)
        const textCanvas = document.createElement('canvas');
        textCanvas.width = 512;
        textCanvas.height = 256;
        const ctx = textCanvas.getContext('2d');
        ctx.fillStyle = 'rgba(0,0,0,0)';
        ctx.fillRect(0, 0, 512, 256);
        
        // Draw cyber design details
        ctx.font = 'bold 32px Sora, sans-serif';
        ctx.fillStyle = '#22d3ee';
        ctx.fillText('LOUD PROTOCOL', 60, 90);
        ctx.font = '18px JetBrains Mono, monospace';
        ctx.fillStyle = '#8b5cf6';
        ctx.fillText('LIC: lp_05aF...8a', 60, 135);
        ctx.fillStyle = '#94a3b8';
        ctx.fillText('STATUS: ACTIVE SECURE', 60, 175);

        const textTex = new THREE.CanvasTexture(textCanvas);
        const textMat = new THREE.MeshBasicMaterial({
            map: textTex,
            transparent: true,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });
        const textPlane = new THREE.Mesh(new THREE.PlaneGeometry(2.6, 1.3), textMat);
        textPlane.position.z = 0.05;
        licenseCard.add(textPlane);

        // Wireframe border highlight lines
        const wireframeGeom = new THREE.BoxGeometry(3.06, 1.91, 0.07);
        const wireframeMat = new THREE.MeshBasicMaterial({
            color: 0x22d3ee,
            wireframe: true,
            transparent: true,
            opacity: 0.22
        });
        const cardWire = new THREE.Mesh(wireframeGeom, wireframeMat);
        licenseCard.add(cardWire);

        // Glowing horizontal lasers
        const laserGeom = new THREE.BoxGeometry(2.9, 0.025, 0.09);
        const laserMat = new THREE.MeshBasicMaterial({
            color: 0x8b5cf6,
            transparent: true,
            opacity: 0.65
        });
        const laserTop = new THREE.Mesh(laserGeom, laserMat);
        laserTop.position.y = 0.82;
        const laserBottom = new THREE.Mesh(laserGeom, laserMat.clone());
        laserBottom.material.color.setHex(0x22d3ee);
        laserBottom.position.y = -0.82;

        licenseCard.add(laserTop);
        licenseCard.add(laserBottom);

        mainGroup.add(licenseCard);
    }

    function createAbstractGlassGeometry() {
        const glassColors = [0x3b82f6, 0x22d3ee, 0x8b5cf6, 0xffffff];

        function createGlassMaterial(colorHex) {
            return new THREE.MeshPhysicalMaterial({
                color: colorHex,
                transparent: true,
                opacity: 0.16,
                roughness: 0.08,
                metalness: 0.05,
                transmission: 0.92,
                ior: 1.52,
                thickness: 0.6,
                specularIntensity: 1.0,
                clearcoat: 1.0,
                clearcoatRoughness: 0.08
            });
        }

        // Glass Cubes
        const cubeGeom = new THREE.BoxGeometry(0.55, 0.55, 0.55);
        for (let i = 0; i < 4; i++) {
            const mat = createGlassMaterial(glassColors[i % glassColors.length]);
            const mesh = new THREE.Mesh(cubeGeom, mat);
            resetObject(mesh);
            backgroundGroup.add(mesh);
            backgroundObjects.push(mesh);
        }

        // Crystal Prisms (3-sided Cylinder)
        const prismGeom = new THREE.CylinderGeometry(0.28, 0.28, 0.8, 3);
        for (let i = 0; i < 3; i++) {
            const mat = createGlassMaterial(glassColors[(i + 1) % glassColors.length]);
            const mesh = new THREE.Mesh(prismGeom, mat);
            resetObject(mesh);
            backgroundGroup.add(mesh);
            backgroundObjects.push(mesh);
        }

        // Icosahedrons
        const crystalGeom = new THREE.IcosahedronGeometry(0.42, 0);
        for (let i = 0; i < 3; i++) {
            const mat = createGlassMaterial(glassColors[(i + 2) % glassColors.length]);
            const mesh = new THREE.Mesh(crystalGeom, mat);
            resetObject(mesh);
            backgroundGroup.add(mesh);
            backgroundObjects.push(mesh);
        }

        // Torus Rings
        const torusGeom = new THREE.TorusGeometry(0.32, 0.07, 8, 24);
        for (let i = 0; i < 3; i++) {
            const mat = createGlassMaterial(glassColors[(i + 3) % glassColors.length]);
            const mesh = new THREE.Mesh(torusGeom, mat);
            resetObject(mesh);
            backgroundGroup.add(mesh);
            backgroundObjects.push(mesh);
        }
    }

    function createVolumetricLightBeams() {
        const beamCount = prefersReducedMotion ? 2 : 5;
        // Cylinder representing light shafts
        const beamGeom = new THREE.CylinderGeometry(0.01, 1.8, 12, 16, 1, true);

        for (let i = 0; i < beamCount; i++) {
            const beamMat = new THREE.MeshBasicMaterial({
                color: i % 2 === 0 ? 0x22d3ee : 0x8b5cf6,
                transparent: true,
                opacity: 0.05,
                blending: THREE.AdditiveBlending,
                side: THREE.DoubleSide,
                depthWrite: false
            });
            const beam = new THREE.Mesh(beamGeom, beamMat);
            
            beam.position.set(
                (Math.random() - 0.5) * 14,
                (Math.random() - 0.5) * 8,
                -3 - Math.random() * 2
            );
            
            beam.rotation.z = (Math.random() - 0.5) * 0.5;
            beam.rotation.x = (Math.random() - 0.5) * 0.3;

            beam.userData = {
                angleSpeed: 0.005 + Math.random() * 0.005,
                angle: Math.random() * Math.PI,
                initialX: beam.position.x
            };

            lightBeamGroup.add(beam);
            lightBeams.push(beam);
        }
    }

    function resetObject(mesh) {
        mesh.position.x = (Math.random() - 0.5) * 12;
        mesh.position.y = (Math.random() - 0.5) * 8;
        mesh.position.z = (Math.random() - 0.7) * 4;

        mesh.userData = {
            rotSpeedX: (Math.random() - 0.5) * 0.012,
            rotSpeedY: (Math.random() - 0.5) * 0.012,
            rotSpeedZ: (Math.random() - 0.5) * 0.008,
            floatSpeed: 0.003 + Math.random() * 0.004,
            floatRange: 0.12 + Math.random() * 0.15,
            initialY: mesh.position.y,
            seed: Math.random() * 100
        };
    }

    function createFloatingParticles() {
        const count = prefersReducedMotion ? 25 : 100;
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(count * 3);

        for (let i = 0; i < count * 3; i += 3) {
            positions[i] = (Math.random() - 0.5) * 14;
            positions[i + 1] = (Math.random() - 0.5) * 10;
            positions[i + 2] = (Math.random() - 0.6) * 5;
        }

        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

        const canvas = document.createElement('canvas');
        canvas.width = 16;
        canvas.height = 16;
        const ctx = canvas.getContext('2d');
        const gradient = ctx.createRadialGradient(8, 8, 0, 8, 8, 8);
        gradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
        gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, 16, 16);

        const texture = new THREE.CanvasTexture(canvas);

        const material = new THREE.PointsMaterial({
            color: 0x3b82f6,
            size: 0.11,
            map: texture,
            transparent: true,
            opacity: 0.28,
            depthWrite: false,
            blending: THREE.AdditiveBlending
        });

        particleSystem = new THREE.Points(geometry, material);
        scene.add(particleSystem);
    }

    function onMouseMove(event) {
        mouseX = (event.clientX / window.innerWidth) - 0.5;
        mouseY = (event.clientY / window.innerHeight) - 0.5;

        targetCameraX = mouseX * 2.2;
        targetCameraY = -mouseY * 2.2;
    }

    function onWindowResize() {
        const canvas = document.getElementById('hero-3d-canvas');
        if (!canvas) return;

        const width = window.innerWidth;
        const height = window.innerHeight;

        camera.aspect = width / height;
        camera.updateProjectionMatrix();

        renderer.setSize(width, height, false);
    }

    function animate(time) {
        animationFrameId = requestAnimationFrame(animate);

        const timeSec = time * 0.001;

        // 1. Group positions lerping across route navigation
        currentGroupX += (targetGroupX - currentGroupX) * 0.08;
        currentGroupY += (targetGroupY - currentGroupY) * 0.08;
        currentGroupScale += (targetGroupScale - currentGroupScale) * 0.08;
        currentCardOpacity += (targetCardOpacity - currentCardOpacity) * 0.08;

        if (mainGroup) {
            mainGroup.position.x = currentGroupX;
            mainGroup.position.y = currentGroupY;
            mainGroup.scale.set(currentGroupScale, currentGroupScale, currentGroupScale);

            // Apply card opacity smoothly
            mainGroup.traverse(child => {
                if (child.material) {
                    child.material.opacity = child.userData.initialOpacity ? 
                        child.userData.initialOpacity * currentCardOpacity : 
                        currentCardOpacity;
                }
            });
        }

        // Cache initial opacity values once
        if (mainGroup && currentCardOpacity === 1.0) {
            mainGroup.traverse(child => {
                if (child.material && !child.userData.initialOpacity) {
                    child.userData.initialOpacity = child.material.opacity;
                }
            });
        }

        // 2. Camera Parallax and Continuous Idle Orbit
        const idleOrbitX = Math.sin(timeSec * 0.2) * 0.4;
        const idleOrbitY = Math.cos(timeSec * 0.15) * 0.2;

        if (!prefersReducedMotion) {
            currentCameraX += (targetCameraX - currentCameraX) * 0.04;
            currentCameraY += (targetCameraY - currentCameraY) * 0.04;
            
            camera.position.x = currentCameraX + idleOrbitX;
            camera.position.y = currentCameraY + idleOrbitY;
        } else {
            camera.position.x = idleOrbitX * 0.1;
            camera.position.y = idleOrbitY * 0.1;
        }
        camera.lookAt(0, 0, 0);

        // 3. Central card rotation and hover offsets
        if (licenseCard && currentCardOpacity > 0.01) {
            licenseCard.position.y = Math.sin(timeSec * 0.8) * 0.14;
            licenseCard.rotation.x = Math.sin(timeSec * 0.4) * 0.05;
            licenseCard.rotation.y = timeSec * 0.1;
            licenseCard.rotation.z = Math.cos(timeSec * 0.3) * 0.03;
        }

        // 4. Update floating abstract geometries
        backgroundObjects.forEach(obj => {
            const data = obj.userData;
            obj.rotation.x += data.rotSpeedX;
            obj.rotation.y += data.rotSpeedY;
            obj.rotation.z += data.rotSpeedZ;

            obj.position.y = data.initialY + Math.sin(timeSec * data.floatSpeed * 100 + data.seed) * data.floatRange;
            
            obj.position.x += 0.0025;
            if (obj.position.x > 6.5) {
                obj.position.x = -6.5;
            }
        });

        // 5. Update volumetric light beams (rays oscillation)
        lightBeams.forEach(beam => {
            const data = beam.userData;
            data.angle += data.angleSpeed;
            if (prefersReducedMotion) data.angle += 0.001;

            // Oscillate Y translation and Z rotation angle
            beam.position.x = data.initialX + Math.sin(data.angle) * 0.8;
            beam.rotation.z += Math.cos(data.angle) * 0.0003;
        });

        // 6. Update Particle systems
        if (particleSystem) {
            const positions = particleSystem.geometry.attributes.position.array;
            const length = positions.length;
            const flow = prefersReducedMotion ? 0.0003 : 0.0035;

            for (let i = 1; i < length; i += 3) {
                positions[i] -= flow;
                if (positions[i] < -5) {
                    positions[i] = 5;
                }
            }
            particleSystem.geometry.attributes.position.needsUpdate = true;
            particleSystem.rotation.y = timeSec * 0.015;
        }

        renderer.render(scene, camera);
    }

    function destroy() {
        isInitialized = false;
        if (animationFrameId) {
            cancelAnimationFrame(animationFrameId);
            animationFrameId = null;
        }
        window.removeEventListener('resize', onWindowResize);
        window.removeEventListener('mousemove', onMouseMove);
        backgroundObjects = [];
        lightBeams = [];
    }

    return {
        init,
        setView,
        destroy
    };
})();
