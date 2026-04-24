/**
 * Service Worker for Rhizome Thinking PWA
 * Enhanced offline support and caching strategies
 */

const CACHE_VERSION = 'v3';
const CACHE_NAME = `rhizome-thinking-${CACHE_VERSION}`;
const STATIC_CACHE = `rhizome-static-${CACHE_VERSION}`;
const API_CACHE = `rhizome-api-${CACHE_VERSION}`;
const IMAGE_CACHE = `rhizome-images-${CACHE_VERSION}`;

// Static assets to cache on install
const STATIC_ASSETS = [
    '/',
    '/static/css/style.css',
    '/static/js/app.js',
    '/static/js/views.js',
    '/static/manifest.json',
    '/static/images/icon.svg'
];

// External CDN resources to cache
const CDN_ASSETS = [
    'https://unpkg.com/cytoscape@3.26.0/dist/cytoscape.min.js',
    'https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&display=swap'
];

// Icon sizes to cache
const ICON_SIZES = [72, 96, 128, 144, 152, 192, 384, 512];
const ICON_ASSETS = ICON_SIZES.map(size => `/static/images/icon-${size}.png`);

// Install event - cache static assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        Promise.all([
            // Cache static assets
            caches.open(STATIC_CACHE).then(cache => {
                console.log('[SW] Caching static assets');
                return cache.addAll([...STATIC_ASSETS, ...ICON_ASSETS]);
            }),
            // Cache CDN resources
            caches.open(CACHE_NAME).then(async cache => {
                console.log('[SW] Caching CDN assets');
                for (const url of CDN_ASSETS) {
                    try {
                        const response = await fetch(url, { mode: 'no-cors' });
                        await cache.put(url, response);
                    } catch (err) {
                        console.warn(`[SW] Failed to cache CDN: ${url}`, err);
                    }
                }
            })
        ])
    );
    self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames
                    .filter(name => {
                        return name.startsWith('rhizome-') && 
                               !name.includes(CACHE_VERSION);
                    })
                    .map(name => {
                        console.log('[SW] Deleting old cache:', name);
                        return caches.delete(name);
                    })
            );
        })
    );
    self.clients.claim();
});

// Fetch event - serve from cache or network
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }

    // Skip chrome-extension requests
    if (url.protocol === 'chrome-extension:') {
        return;
    }

    // Handle API requests
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(handleAPIRequest(request));
        return;
    }

    // Handle image requests
    if (request.destination === 'image') {
        event.respondWith(handleImageRequest(request));
        return;
    }

    // Handle CDN resources
    if (CDN_ASSETS.includes(url.href)) {
        event.respondWith(handleCDNRequest(request));
        return;
    }

    // Handle static assets and navigation
    event.respondWith(handleStaticRequest(request));
});

// API request handler - network first with timeout, fallback to cache
async function handleAPIRequest(request) {
    const url = new URL(request.url);
    
    // Don't cache streaming search endpoints - they should always be fresh
    if (url.pathname.includes('/stream/')) {
        console.log('[SW] Bypassing cache for streaming endpoint:', request.url);
        try {
            return await fetch(request);
        } catch (error) {
            return new Response(
                JSON.stringify({
                    error: '网络错误',
                    message: '无法连接到服务器',
                    offline: true
                }),
                {
                    status: 503,
                    headers: { 'Content-Type': 'application/json' }
                }
            );
        }
    }
    
    const cache = await caches.open(API_CACHE);
    
    try {
        // Try network with timeout
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10000);
        
        const networkResponse = await fetch(request, { signal: controller.signal });
        clearTimeout(timeout);
        
        if (networkResponse.ok) {
            // Clone and cache successful responses
            const cloned = networkResponse.clone();
            cache.put(request, cloned);
            return networkResponse;
        }
        throw new Error('Network response not OK');
    } catch (error) {
        // Try to return cached response
        const cached = await cache.match(request);
        
        if (cached) {
            console.log('[SW] Serving API from cache:', request.url);
            return cached;
        }
        
        // Return offline JSON response
        return new Response(
            JSON.stringify({
                error: '离线模式',
                message: '当前处于离线状态，该功能暂不可用',
                offline: true
            }),
            {
                status: 503,
                headers: { 'Content-Type': 'application/json' }
            }
        );
    }
}

// Image request handler - cache first with network fallback
async function handleImageRequest(request) {
    const cache = await caches.open(IMAGE_CACHE);
    const cached = await cache.match(request);
    
    if (cached) {
        // Update cache in background
        fetch(request).then(response => {
            if (response.ok) {
                cache.put(request, response);
            }
        }).catch(() => {});
        return cached;
    }
    
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        // Return placeholder or offline indicator
        return new Response('Image unavailable', { status: 503 });
    }
}

// CDN request handler - cache first
async function handleCDNRequest(request) {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(request);
    
    if (cached) {
        return cached;
    }
    
    try {
        const networkResponse = await fetch(request, { mode: 'no-cors' });
        if (networkResponse.ok || networkResponse.type === 'opaque') {
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        return new Response('CDN resource unavailable', { status: 503 });
    }
}

// Static asset handler - stale-while-revalidate
async function handleStaticRequest(request) {
    const cache = await caches.open(STATIC_CACHE);
    const cached = await cache.match(request);
    
    // Update cache in background
    const fetchPromise = fetch(request).then(networkResponse => {
        if (networkResponse.ok) {
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    }).catch(() => cached);
    
    // Return cached immediately if available, otherwise wait for network
    return cached || fetchPromise;
}

// Background sync for offline form submissions
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-nodes') {
        event.waitUntil(syncPendingNodes());
    }
});

// Handle background sync for pending node submissions
async function syncPendingNodes() {
    // This will be called when connectivity is restored
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
        client.postMessage({
            type: 'SYNC_COMPLETED',
            message: '网络已恢复，可以同步离线数据'
        });
    });
}

// Handle push notifications (for future use)
self.addEventListener('push', (event) => {
    const data = event.data?.json() || {};
    const options = {
        body: data.body || '新通知',
        icon: '/static/images/icon-192.png',
        badge: '/static/images/icon-72.png',
        tag: data.tag || 'default',
        requireInteraction: false
    };
    
    event.waitUntil(
        self.registration.showNotification(data.title || 'Rhizome Thinking', options)
    );
});

// Handle notification click
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    event.waitUntil(
        self.clients.openWindow('/')
    );
});

// Message handler from main thread
self.addEventListener('message', (event) => {
    if (event.data === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    
    if (event.data.type === 'CACHE_URLS') {
        event.waitUntil(
            caches.open(CACHE_NAME).then(cache => {
                return cache.addAll(event.data.urls);
            })
        );
    }
});
