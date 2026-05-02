/**
 * Rhizome Thinking - Mobile, PWA & Network Utilities
 */

// ===== Network Status Monitoring =====
const networkStatus = {
    isOnline: navigator.onLine,
    wasOffline: false,
    
    init() {
        this.createStatusIndicator();
        this.bindEvents();
        this.updateStatus(navigator.onLine);
    },
    
    createStatusIndicator() {
        const indicator = document.createElement('div');
        indicator.id = 'networkStatus';
        indicator.className = 'network-status';
        indicator.innerHTML = `
            <span class="status-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                    <path d="M1 4h22M1 12h22M1 20h22"></path>
                </svg>
            </span>
            <span class="status-text">在线</span>
        `;
        indicator.style.cssText = `
            position: fixed;
            top: calc(var(--header-height) + 8px);
            left: 50%;
            transform: translateX(-50%) translateY(-40px);
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            background: rgba(0, 184, 148, 0.9);
            border-radius: 16px;
            color: white;
            font-size: 0.75rem;
            font-weight: 500;
            z-index: 99;
            opacity: 0;
            transition: all 0.3s ease;
            backdrop-filter: blur(4px);
        `;
        document.body.appendChild(indicator);
    },
    
    bindEvents() {
        window.addEventListener('online', () => {
            this.updateStatus(true);
            this.wasOffline = true;
            
            // Trigger background sync if available
            if ('serviceWorker' in navigator) {
                navigator.serviceWorker.ready.then(reg => {
                    if ('sync' in reg) {
                        reg.sync.register('sync-nodes');
                    }
                });
            }
        });
        
        window.addEventListener('offline', () => {
            this.updateStatus(false);
        });
    },
    
    updateStatus(online) {
        this.isOnline = online;
        const indicator = document.getElementById('networkStatus');
        const icon = indicator.querySelector('.status-icon');
        const text = indicator.querySelector('.status-text');
        
        if (online) {
            indicator.style.background = 'rgba(0, 184, 148, 0.9)';
            text.textContent = this.wasOffline ? '已恢复在线' : '在线';
            icon.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                    <path d="M5 12.55a11 11 0 0 1 14.08 0M1.42 9a16 16 0 0 1 21.16 0M8.53 16.11a6 6 0 0 1 6.95 0M12 20h.01"></path>
                </svg>
            `;
            
            // Auto hide after 3 seconds if coming back online
            if (this.wasOffline) {
                setTimeout(() => this.hideIndicator(), 3000);
            }
        } else {
            indicator.style.background = 'rgba(231, 76, 60, 0.9)';
            text.textContent = '离线模式';
            icon.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                    <line x1="1" y1="1" x2="23" y2="23"></line>
                    <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55M5 12.55a10.94 10.94 0 0 1 5.17-2.39M10.71 5.05A16 16 0 0 1 22.58 9M1.42 9a15.91 15.91 0 0 1 4.7-2.88M8.53 16.11a6 12 6 0 0 1 6.95 0M12 20h.01"></path>
                </svg>
            `;
            this.showIndicator();
            ui.showToast('进入离线模式，部分功能可能受限', 'warning');
        }
    },
    
    showIndicator() {
        const indicator = document.getElementById('networkStatus');
        indicator.style.opacity = '1';
        indicator.style.transform = 'translateX(-50%) translateY(0)';
    },
    
    hideIndicator() {
        const indicator = document.getElementById('networkStatus');
        indicator.style.opacity = '0';
        indicator.style.transform = 'translateX(-50%) translateY(-40px)';
    }
};

// Initialize network status monitoring
networkStatus.init();

// ===== Mobile Touch Optimizations =====
// Add touch feedback to buttons
function addTouchFeedback() {
    const style = document.createElement('style');
    style.textContent = `
        @media (hover: none) {
            button, .nav-item, .tag-filter, .node-card, .source-node-link {
                -webkit-tap-highlight-color: transparent;
            }
            
            button:active, .nav-item:active, .tag-filter:active, 
            .node-card:active, .source-node-link:active {
                transform: scale(0.97);
            }
            
            .search-btn:active {
                transform: translateY(-50%) scale(0.97);
            }
        }
        
        /* Prevent pull-to-refresh on mobile */
        body {
            overscroll-behavior-y: none;
        }
        
        /* Smooth scrolling for iOS */
        .control-panel, .content-area, .search-results {
            -webkit-overflow-scrolling: touch;
        }
    `;
    document.head.appendChild(style);
}

// Initialize touch feedback
addTouchFeedback();

// ===== Standalone Mode Detection =====
function isStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches ||
           window.navigator.standalone === true;
}

if (isStandalone()) {
    document.body.classList.add('standalone-mode');
    console.log('Running as installed PWA');
}

// ===== Splash Screen Management =====
function hideSplashScreen() {
    const splash = document.getElementById('splash-screen');
    if (splash) {
        splash.classList.add('hidden');
        setTimeout(() => {
            splash.remove();
        }, 500);
    }
}

// Hide splash screen when app is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(hideSplashScreen, 1500);
    });
} else {
    setTimeout(hideSplashScreen, 1500);
}

// ===== Mobile Gestures & Interactions =====
const mobileGestures = {
    touchStartX: 0,
    touchStartY: 0,
    touchEndX: 0,
    touchEndY: 0,
    minSwipeDistance: 50,
    
    init() {
        this.bindTouchEvents();
        // Pull to refresh has been disabled as requested
        this.setupSidebarSwipe();
    },
    
    bindTouchEvents() {
        // Prevent zoom on double tap
        let lastTouchEnd = 0;
        document.addEventListener('touchend', (e) => {
            const now = Date.now();
            if (now - lastTouchEnd <= 300) {
                e.preventDefault();
            }
            lastTouchEnd = now;
        }, { passive: false });
    },
    
    // Note: setupPullToRefresh has been removed as requested
    // The search results page no longer supports pull-to-refresh
    
    setupSidebarSwipe() {
        const controlPanel = document.getElementById('controlPanel');
        const menuToggle = document.getElementById('menuToggle');
        if (!controlPanel || !menuToggle) return;
        
        let startX = 0;
        let currentX = 0;
        let isDragging = false;
        
        // Swipe from left edge to open sidebar
        document.addEventListener('touchstart', (e) => {
            const touchX = e.touches[0].clientX;
            
            // Only trigger if touching near left edge (20px)
            if (touchX < 20 && !controlPanel.classList.contains('open')) {
                startX = touchX;
                isDragging = true;
            }
            
            // Or if sidebar is open, allow swiping to close
            if (controlPanel.classList.contains('open') && touchX > 250) {
                startX = touchX;
                isDragging = true;
            }
        }, { passive: true });
        
        document.addEventListener('touchmove', (e) => {
            if (!isDragging) return;
            
            currentX = e.touches[0].clientX;
            const diff = currentX - startX;
            
            if (!controlPanel.classList.contains('open') && diff > 0) {
                // Opening
                const translateX = Math.min(diff - 280, 0);
                controlPanel.style.transform = `translateX(${translateX}px)`;
            } else if (controlPanel.classList.contains('open') && diff < 0) {
                // Closing
                const translateX = Math.max(diff, -280);
                controlPanel.style.transform = `translateX(${translateX}px)`;
            }
        }, { passive: true });
        
        document.addEventListener('touchend', () => {
            if (!isDragging) return;
            
            const diff = currentX - startX;
            
            if (!controlPanel.classList.contains('open')) {
                // Opening
                if (diff > 100) {
                    controlPanel.classList.add('open');
                }
                controlPanel.style.transform = '';
            } else {
                // Closing
                if (diff < -100) {
                    controlPanel.classList.remove('open');
                }
                controlPanel.style.transform = '';
            }
            
            isDragging = false;
        });
    }
};

// Initialize mobile gestures on touch devices
if ('ontouchstart' in window || navigator.maxTouchPoints > 0) {
    mobileGestures.init();
}

// ===== Query Mode Switching =====
function initQueryModeSwitching() {
    const queryModeBtns = document.querySelectorAll('.query-mode-btn');
    const semanticOptions = document.getElementById('semanticSearchOptions');
    const preciseOptions = document.getElementById('preciseSearchOptions');
    const searchInput = document.getElementById('searchInput');
    const batchRefineControl = document.getElementById('batchRefineControl');

    queryModeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            queryModeBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const mode = btn.dataset.mode;
            if (mode === 'semantic') {
                semanticOptions.style.display = 'block';
                preciseOptions.style.display = 'none';
                searchInput.placeholder = '输入语义锚点...';
                if (batchRefineControl) batchRefineControl.style.display = 'none';
                // Exit batch mode if active
                if (state.batchRefineMode) toggleBatchRefineMode();
            } else {
                semanticOptions.style.display = 'none';
                preciseOptions.style.display = 'block';
                searchInput.placeholder = '输入搜索内容（可选）...';
                if (batchRefineControl) batchRefineControl.style.display = 'block';
            }
        });
    });
}

// ===== Viewport Height Fix for Mobile Browsers =====
function setViewportHeight() {
    const vh = window.innerHeight * 0.01;
    document.documentElement.style.setProperty('--vh', `${vh}px`);
}

setViewportHeight();
window.addEventListener('resize', setViewportHeight);
window.addEventListener('orientationchange', setViewportHeight);

// ===== Prevent iOS Rubber Band Effect =====
if (/iPad|iPhone|iPod/.test(navigator.userAgent)) {
    document.body.addEventListener('touchmove', (e) => {
        if (e.target === document.body) {
            e.preventDefault();
        }
    }, { passive: false });
}

// ===== Haptic Feedback (on supported devices) =====
function hapticFeedback(type = 'light') {
    if ('vibrate' in navigator) {
        const patterns = {
            light: [10],
            medium: [20],
            heavy: [30],
            success: [10, 50, 10],
            error: [50, 100, 50]
        };
        navigator.vibrate(patterns[type] || patterns.light);
    }
}

// Add haptic feedback to buttons
if ('ontouchstart' in window) {
    document.addEventListener('click', (e) => {
        if (e.target.closest('button, .nav-item, .node-card, .tag-filter')) {
            hapticFeedback('light');
        }
    });
}

// ===== Keyboard handling for mobile =====
if ('virtualKeyboard' in navigator) {
    navigator.virtualKeyboard.overlaysContent = true;
}

// Adjust layout when keyboard appears
window.addEventListener('resize', () => {
    const isKeyboardOpen = window.innerHeight < window.outerHeight * 0.8;
    document.body.classList.toggle('keyboard-open', isKeyboardOpen);
});

// ===== Service Worker Registration =====
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/js/sw.js')
            .then(registration => {
                console.log('SW registered:', registration);
                
                // Listen for Service Worker updates
                registration.addEventListener('updatefound', () => {
                    const newWorker = registration.installing;
                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            // New version available
                            showUpdateNotification(newWorker);
                        }
                    });
                });
            })
            .catch(error => {
                console.log('SW registration failed:', error);
            });
        
        // Listen for Service Worker messages
        navigator.serviceWorker.addEventListener('message', (event) => {
            if (event.data.type === 'SYNC_COMPLETED') {
                ui.showToast(event.data.message);
            }
        });
    });
}

// Show update notification
function showUpdateNotification(worker) {
    const toast = document.createElement('div');
    toast.className = 'toast update-toast';
    toast.innerHTML = `
        <span>新版本可用</span>
        <button class="btn-primary" style="padding: 4px 12px; font-size: 0.75rem;">刷新</button>
    `;
    toast.querySelector('button').addEventListener('click', () => {
        worker.postMessage('SKIP_WAITING');
        window.location.reload();
    });
    document.getElementById('toastContainer').appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 100);
}
