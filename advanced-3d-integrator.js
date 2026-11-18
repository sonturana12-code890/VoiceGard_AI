/**
 * ============================================================================
 * ADVANCED 3D SYSTEM INTEGRATOR
 * Seamlessly integrates advanced 3D animations into existing website
 * WITHOUT modifying original structure or functionality
 * ============================================================================
 */

class Advanced3DIntegrator {
    constructor() {
        this.system = null;
        this.integrations = new Map();
        this.audioVisualizerActive = false;
        this.initialized = false;
    }

    /**
     * Initialize the advanced 3D system and integrate with existing website
     */
    async init() {
        if (this.initialized) return;

        // Wait for Three.js and other dependencies
        await this.waitForDependencies();

        // Create the 3D system
        this.system = new AdvancedVoiceGuard3D();
        this.system.initialize();

        // Integrate with existing website
        this.integrateWithDashboard();
        this.integrateWithVoiceAnalysis();
        this.integrateWithShield();
        this.integrateWithRadar();

        this.initialized = true;
        console.log('✅ Advanced 3D Integrator initialized');
    }

    /**
     * Wait for dependencies to load
     */
    async waitForDependencies() {
        const maxWait = 10000;
        const startTime = Date.now();

        return new Promise((resolve) => {
            const checkDeps = () => {
                if (typeof THREE !== 'undefined' && typeof gsap !== 'undefined') {
                    resolve();
                } else if (Date.now() - startTime > maxWait) {
                    console.warn('⚠️ Dependencies took too long to load, continuing anyway');
                    resolve();
                } else {
                    setTimeout(checkDeps, 100);
                }
            };
            checkDeps();
        });
    }

    /**
     * Integrate Neural Sphere with Dashboard Overview
     * Adds 3D visualization to the overview section WITHOUT modifying existing layout
     */
    integrateWithDashboard() {
        // Find the hero panel or overview section
        const overview = document.getElementById('view-overview');
        if (!overview) {
            console.warn('⚠️ Overview section not found, skipping dashboard integration');
            return;
        }

        // Create a container for 3D animation INSIDE existing layout
        const container3D = document.createElement('div');
        container3D.id = 'advanced-neural-sphere';
        container3D.style.cssText = `
            width: 100%;
            height: 300px;
            margin: 2rem 0;
            border-radius: 12px;
            border: 1px solid rgba(0, 229, 255, 0.1);
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.05) 0%, rgba(0, 229, 255, 0.05) 100%);
            overflow: hidden;
            position: relative;
        `;

        // Insert after the section header but before metrics
        const sectionHeader = overview.querySelector('.section-header');
        if (sectionHeader && sectionHeader.nextElementSibling) {
            sectionHeader.nextElementSibling.parentNode.insertBefore(container3D, sectionHeader.nextElementSibling);
        } else {
            overview.insertBefore(container3D, overview.firstChild.nextSibling);
        }

        // Create the advanced neural sphere
        this.system.createAdvancedNeuralSphere('advanced-neural-sphere');
        this.integrations.set('dashboard', 'advanced-neural-sphere');

        console.log('✅ Dashboard integration complete - Neural Sphere added');
    }

    /**
     * Integrate 3D Audio Visualization with Voice Analysis
     */
    integrateWithVoiceAnalysis() {
        const analysisView = document.getElementById('view-analysis');
        if (!analysisView) {
            console.warn('⚠️ Analysis section not found, skipping audio visualization');
            return;
        }

        // Find or create audio visualizer container
        let audioVizContainer = document.getElementById('advanced-audio-viz');
        
        if (!audioVizContainer) {
            audioVizContainer = document.createElement('div');
            audioVizContainer.id = 'advanced-audio-viz';
            audioVizContainer.style.cssText = `
                width: 100%;
                height: 250px;
                margin: 1.5rem 0;
                border-radius: 12px;
                border: 1px solid rgba(0, 229, 255, 0.1);
                background: #050510;
                overflow: hidden;
            `;

            // Insert into analysis view
            const analysisContent = analysisView.querySelector('.card');
            if (analysisContent) {
                analysisContent.parentNode.insertBefore(audioVizContainer, analysisContent.nextElementSibling);
            } else {
                analysisView.appendChild(audioVizContainer);
            }
        }

        // Create audio visualizer
        const audioElement = document.getElementById('audio-player') || 
                            analysisView.querySelector('audio');

        if (audioElement) {
            this.system.createAudio3DVisualization('advanced-audio-viz', audioElement.id || 'audio-player');
            this.audioVisualizerActive = true;
            this.integrations.set('audioViz', 'advanced-audio-viz');
            console.log('✅ Audio visualization integrated');
        }
    }

    /**
     * Integrate Cybersecurity Shield with Speaker Verification
     */
    integrateWithShield() {
        const verificationView = document.getElementById('view-verification');
        if (!verificationView) {
            console.warn('⚠️ Verification section not found, skipping shield');
            return;
        }

        // Create shield container
        let shieldContainer = document.getElementById('advanced-security-shield');
        
        if (!shieldContainer) {
            shieldContainer = document.createElement('div');
            shieldContainer.id = 'advanced-security-shield';
            shieldContainer.style.cssText = `
                width: 100%;
                height: 300px;
                margin: 1.5rem 0;
                border-radius: 12px;
                border: 1px solid rgba(0, 229, 255, 0.1);
                background: linear-gradient(135deg, rgba(139, 92, 246, 0.05) 0%, rgba(0, 229, 255, 0.05) 100%);
                overflow: hidden;
                display: flex;
                align-items: center;
                justify-content: center;
            `;

            // Insert into verification view
            const verificationContent = verificationView.querySelector('.card');
            if (verificationContent) {
                verificationContent.parentNode.insertBefore(shieldContainer, verificationContent);
            } else {
                verificationView.insertBefore(shieldContainer, verificationView.firstChild);
            }
        }

        // Determine threat state based on existing data
        let threatState = 'safe';
        const riskIndicator = document.querySelector('[data-risk-level]');
        if (riskIndicator) {
            const riskLevel = riskIndicator.getAttribute('data-risk-level');
            if (riskLevel === 'critical' || riskLevel === 'high') {
                threatState = 'danger';
            } else if (riskLevel === 'medium') {
                threatState = 'suspicious';
            }
        }

        // Create the shield
        this.system.createCybersecurityShield('advanced-security-shield', threatState);
        this.integrations.set('shield', 'advanced-security-shield');

        console.log('✅ Security shield integrated with state:', threatState);
    }

    /**
     * Integrate Cyber Radar with Threat Intelligence
     */
    integrateWithRadar() {
        const threatView = document.getElementById('view-threat-intel');
        if (!threatView) {
            console.warn('⚠️ Threat intel section not found, skipping radar');
            return;
        }

        // Create radar container
        let radarContainer = document.getElementById('advanced-cyber-radar');
        
        if (!radarContainer) {
            radarContainer = document.createElement('div');
            radarContainer.id = 'advanced-cyber-radar';
            radarContainer.style.cssText = `
                width: 100%;
                height: 320px;
                margin: 1.5rem 0;
                border-radius: 12px;
                border: 1px solid rgba(0, 229, 255, 0.1);
                background: #050510;
                overflow: hidden;
            `;

            // Insert into threat view
            const threatContent = threatView.querySelector('.card');
            if (threatContent) {
                threatContent.parentNode.insertBefore(radarContainer, threatContent);
            } else {
                threatView.insertBefore(radarContainer, threatView.firstChild);
            }
        }

        // Create the radar
        this.system.createCyberRadar('advanced-cyber-radar');
        this.integrations.set('radar', 'advanced-cyber-radar');

        console.log('✅ Cyber radar integrated');
    }

    /**
     * Apply cinematic animations to existing elements
     */
    applyElementAnimations() {
        if (typeof gsap === 'undefined') return;

        // Animate existing cards on scroll
        gsap.utils.toArray('.card').forEach((card, i) => {
            gsap.fromTo(card,
                {
                    opacity: 0,
                    y: 40,
                    rotation: 1.5
                },
                {
                    opacity: 1,
                    y: 0,
                    rotation: 0,
                    duration: 0.8,
                    ease: 'back.out',
                    delay: i * 0.05,
                    scrollTrigger: {
                        trigger: card,
                        start: 'top 80%',
                        toggleActions: 'play none none reverse'
                    }
                }
            );
        });

        // Hover animations for buttons
        document.querySelectorAll('button').forEach(btn => {
            btn.addEventListener('mouseenter', () => {
                gsap.to(btn, {
                    duration: 0.3,
                    boxShadow: '0 0 20px rgba(0, 229, 255, 0.5)',
                    ease: 'power2.out'
                });
            });

            btn.addEventListener('mouseleave', () => {
                gsap.to(btn, {
                    duration: 0.3,
                    boxShadow: 'none',
                    ease: 'power2.out'
                });
            });
        });

        console.log('✅ Element animations applied');
    }

    /**
     * Update threat visualization based on actual results
     */
    updateThreatVisualization(threatLevel) {
        const shieldContainer = document.getElementById('advanced-security-shield');
        if (!shieldContainer) return;

        let threatState = 'safe';
        if (threatLevel === 'critical' || threatLevel === 'high') {
            threatState = 'danger';
        } else if (threatLevel === 'medium') {
            threatState = 'suspicious';
        }

        // Recreate shield with new threat state
        this.system.createCybersecurityShield('advanced-security-shield', threatState);
        console.log('✅ Threat visualization updated:', threatState);
    }

    /**
     * Cleanup and destroy all 3D systems
     */
    destroy() {
        if (this.system) {
            this.system.destroy();
        }
        this.integrations.clear();
        this.initialized = false;
        console.log('✅ Advanced 3D System destroyed');
    }
}

// Global instance
let Advanced3DIntegratorInstance = null;

/**
 * Initialize the integrator when DOM is ready
 */
function initializeAdvanced3D() {
    if (Advanced3DIntegratorInstance) return;

    Advanced3DIntegratorInstance = new Advanced3DIntegrator();
    Advanced3DIntegratorInstance.init().then(() => {
        Advanced3DIntegratorInstance.applyElementAnimations();
        console.log('✅ Advanced 3D animations ready');
    });
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAdvanced3D);
} else {
    initializeAdvanced3D();
}

// Export for external use
window.Advanced3DIntegrator = Advanced3DIntegrator;
window.initializeAdvanced3D = initializeAdvanced3D;
window.getAdvanced3DIntegrator = () => Advanced3DIntegratorInstance;

console.log('✅ Advanced 3D Integrator loaded');
