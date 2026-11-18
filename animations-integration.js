/**
 * ============================================================================
 * VOICEGUARD AI — Animation Integration System
 * Bridges existing functionality with 3D WebGL & GSAP animations
 * ============================================================================
 */

let animationEngine = null;
let reducedMotionEnabled = false;

// Initialize animation system after DOM is ready
function initializeAnimationSystem() {
    reducedMotionEnabled = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reducedMotionEnabled) {
        console.log('VoiceGuard Animations: Reduced motion preference detected');
        return;
    }

    if (typeof VoiceGuardAnimations !== 'undefined' && !animationEngine) {
        animationEngine = new VoiceGuardAnimations();
    }

    // Initialize Hero & Entrance Timelines
    initializeHeroAnimations();

    // Initialize GSAP ScrollTrigger Animations
    initializeScrollAnimations();

    // Initialize Dashboard-wide 3D Tilt & Interactivity
    initializeDashboardAnimations();

    // Initialize Interactive Micro-interaction Glows
    addInteractiveGlows();

    // Check for Auth Screen (Login / Signup)
    initializeAuthAnimations();
}

/**
 * Initialize Hero Section Animations
 */
function initializeHeroAnimations() {
    const coreContainer = document.getElementById('core-scene');

    // Only init core if page doesn't have internal webgl handler
    if (animationEngine && coreContainer && !document.getElementById('ai-core-webgl')) {
        try {
            animationEngine.initAICore('core-scene');
        } catch (error) {
            console.warn('WebGL initialization failed, using CSS fallback:', error);
        }
    }
    animateHeroText();
}

/**
 * Animate hero text with staggered reveal
 */
function animateHeroText() {
    if (typeof gsap === 'undefined' || reducedMotionEnabled) return;

    const timeline = gsap.timeline({ defaults: { ease: 'power3.out' } });

    timeline
        .from('.hero-eyebrow', { duration: 0.7, opacity: 0, x: -24 }, 0.1)
        .from('#hero-title', { duration: 0.85, opacity: 0, y: 22, stagger: 0.05 }, 0.25)
        .from('.hero-copy > p', { duration: 0.7, opacity: 0, y: 16 }, 0.4)
        .from('.hero-actions', { duration: 0.7, opacity: 0, y: 16 }, 0.5)
        .from('.hero-footnote', { duration: 0.6, opacity: 0, y: 12 }, 0.62);
}

/**
 * Initialize Scroll-Triggered Animations with GSAP
 */
function initializeScrollAnimations() {
    if (typeof gsap === 'undefined' || reducedMotionEnabled) return;

    const scrollTrigger = window.ScrollTrigger;
    if (scrollTrigger) {
        gsap.registerPlugin(scrollTrigger);
    }

    // Metric cards entrance
    const metricCards = document.querySelectorAll('.metric-card');
    metricCards.forEach((card, index) => {
        if (scrollTrigger) {
            gsap.fromTo(
                card,
                { opacity: 0, y: 25 },
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
                    delay: (index % 4) * 0.07
                }
            );
        }
    });

    // Content cards entrance
    const cards = document.querySelectorAll('.card:not(.metric-card)');
    cards.forEach((card, index) => {
        if (scrollTrigger) {
            gsap.fromTo(
                card,
                { opacity: 0, y: 28 },
                {
                    opacity: 1,
                    y: 0,
                    duration: 0.7,
                    ease: 'power2.out',
                    scrollTrigger: {
                        trigger: card,
                        start: 'top 85%',
                        once: true
                    },
                    delay: (index % 3) * 0.08
                }
            );
        }
    });

    // Data table row stagger
    document.querySelectorAll('.table-container').forEach(tbl => {
        if (scrollTrigger) {
            gsap.fromTo(
                tbl.querySelectorAll('tbody tr'),
                { opacity: 0, x: -12 },
                {
                    opacity: 1,
                    x: 0,
                    duration: 0.4,
                    stagger: 0.04,
                    ease: 'power2.out',
                    scrollTrigger: {
                        trigger: tbl,
                        start: 'top 85%',
                        once: true
                    }
                }
            );
        }
    });
}

/**
 * Initialize Dashboard-Specific Animations
 */
function initializeDashboardAnimations() {
    if (animationEngine) {
        // Add 3D tilt effect to cards
        animationEngine.addCardTiltEffect();
    }
}

/**
 * Initialize Authentication Page 3D Animations (Login & Signup)
 */
function initializeAuthAnimations() {
    const authScreen = document.getElementById('auth-screen');
    if (!authScreen) return;

    // Attach 3D neural backdrop if not hidden
    const checkAndInit = () => {
        if (!authScreen.hidden && animationEngine) {
            animationEngine.initAuthBackground('auth-screen');

            // Staggered GSAP reveal for auth card
            if (typeof gsap !== 'undefined' && !reducedMotionEnabled) {
                gsap.fromTo(
                    '.auth-card',
                    { opacity: 0, y: 28, scale: 0.98 },
                    { opacity: 1, y: 0, scale: 1, duration: 0.75, ease: 'power3.out' }
                );
            }
        }
    };

    checkAndInit();

    // Listen for attribute changes (e.g. unhidden by auth-client.js)
    const observer = new MutationObserver(checkAndInit);
    observer.observe(authScreen, { attributes: true, attributeFilter: ['hidden', 'class'] });
}

/**
 * Animate view transitions
 */
function animateViewTransition(viewName) {
    if (typeof gsap === 'undefined' || reducedMotionEnabled) return;

    const viewElement = document.getElementById(`view-${viewName}`);
    if (!viewElement) return;

    // Smooth entrance timeline
    gsap.fromTo(
        viewElement,
        { opacity: 0, y: 16 },
        { opacity: 1, y: 0, duration: 0.42, ease: 'power2.out' }
    );

    // Stagger child cards
    const contentElements = viewElement.querySelectorAll('.card, .section-header, .metric-card');
    if (contentElements.length) {
        gsap.fromTo(
            contentElements,
            { opacity: 0, y: 16 },
            {
                opacity: 1,
                y: 0,
                duration: 0.45,
                ease: 'power2.out',
                stagger: 0.04
            }
        );
    }
}

/**
 * Add glowing effect to active interactive elements
 */
function addInteractiveGlows() {
    if (reducedMotionEnabled) return;

    const interactiveElements = document.querySelectorAll('.btn-primary, .btn-outline, .preset-btn');
    interactiveElements.forEach(element => {
        element.addEventListener('pointerenter', function() {
            if (typeof gsap !== 'undefined') {
                gsap.to(this, {
                    duration: 0.25,
                    boxShadow: '0 0 18px rgba(0, 229, 255, 0.42)',
                    ease: 'power2.out'
                });
            }
        });

        element.addEventListener('pointerleave', function() {
            if (typeof gsap !== 'undefined') {
                gsap.to(this, {
                    duration: 0.3,
                    boxShadow: '0 0 0 rgba(0, 229, 255, 0)',
                    ease: 'power2.out'
                });
            }
        });
    });
}

/**
 * Animate threat alerts with pulsing effect
 */
function animateThreatAlert(elementId) {
    if (typeof gsap === 'undefined' || reducedMotionEnabled) return;

    const element = document.getElementById(elementId);
    if (!element) return;

    gsap.to(element, {
        boxShadow: [
            '0 0 0 rgba(239, 68, 68, 0)',
            '0 0 24px rgba(239, 68, 68, 0.85)',
            '0 0 0 rgba(239, 68, 68, 0)'
        ],
        duration: 1.4,
        repeat: -1,
        ease: 'sine.inOut'
    });
}

/**
 * Animate data table rows on render
 */
function animateTableRows(tableId) {
    if (typeof gsap === 'undefined' || reducedMotionEnabled) return;

    const table = document.getElementById(tableId);
    if (!table) return;

    const rows = table.querySelectorAll('tbody tr');
    gsap.fromTo(
        rows,
        { opacity: 0, x: -16 },
        {
            opacity: 1,
            x: 0,
            duration: 0.35,
            ease: 'power2.out',
            stagger: 0.03
        }
    );
}

/**
 * Export all animation functions for external use
 */
window.VoiceGuardAnimationAPI = {
    initializeAnimationSystem,
    initializeHeroAnimations,
    initializeScrollAnimations,
    initializeDashboardAnimations,
    initializeAuthAnimations,
    animateViewTransition,
    addInteractiveGlows,
    animateThreatAlert,
    animateTableRows,
    getAnimationEngine: () => animationEngine
};

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAnimationSystem);
} else {
    initializeAnimationSystem();
}
