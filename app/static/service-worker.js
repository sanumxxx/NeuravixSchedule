// service-worker.js

// Версия кэша - изменяйте при обновлении приложения
const CACHE_NAME = 'melgu-schedule-v1';

// Список URL для предварительного кэширования
const PRECACHE_URLS = [
    '/',
    '/static/manifest.json',
    '/static/offline.html',
    // Иконки Android
    '/static/android/android-launchericon-512-512.png',
    '/static/android/android-launchericon-192-192.png',
    '/static/android/android-launchericon-144-144.png',
    '/static/android/android-launchericon-96-96.png',
    '/static/android/android-launchericon-72-72.png',
    '/static/android/android-launchericon-48-48.png',
    // Иконки iOS
    '/static/ios/180.png',
    '/static/ios/1024.png',
    // Дополнительные ресурсы
    '/static/js/main.js',
    '/static/css/style.css'
];

// Установка Service Worker
self.addEventListener('install', (event) => {
    console.log('[ServiceWorker] Install');
    event.waitUntil(
        // Открываем кэш
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[ServiceWorker] Caching app shell');
                // Добавляем все URL в кэш
                return cache.addAll(PRECACHE_URLS);
            })
            .then(() => {
                // Принудительно активируем Service Worker
                console.log('[ServiceWorker] Skip waiting');
                return self.skipWaiting();
            })
    );
});

// Активация Service Worker
self.addEventListener('activate', (event) => {
    console.log('[ServiceWorker] Activate');
    event.waitUntil(
        Promise.all([
            // Удаляем старые версии кэша
            caches.keys().then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((cacheName) => {
                        if (cacheName !== CACHE_NAME) {
                            console.log('[ServiceWorker] Removing old cache', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            }),
            // Принимаем все клиенты под наш контроль
            self.clients.claim()
        ])
    );
});

// Функция для определения, является ли запрос навигационным
function isNavigationRequest(request) {
    return (request.mode === 'navigate' ||
           (request.method === 'GET' &&
            request.headers.get('accept').includes('text/html')));
}

// Функция для проверки, является ли URL API запросом
function isApiRequest(url) {
    return url.pathname.startsWith('/api/');
}

// Основная функция для обработки запросов
async function handleFetch(event) {
    const request = event.request;
    const url = new URL(request.url);

    try {
        // Для API запросов используем Network First стратегию
        if (isApiRequest(url)) {
            try {
                const networkResponse = await fetch(request);
                if (networkResponse.ok) {
                    const cache = await caches.open(CACHE_NAME);
                    await cache.put(request, networkResponse.clone());
                    return networkResponse;
                }
            } catch (error) {
                const cachedResponse = await caches.match(request);
                if (cachedResponse) {
                    return cachedResponse;
                }
                // Возвращаем JSON с ошибкой для API запросов
                return new Response(
                    JSON.stringify({ error: 'Нет подключения к сети' }),
                    {
                        status: 503,
                        headers: { 'Content-Type': 'application/json' }
                    }
                );
            }
        }

        // Для навигационных запросов
        if (isNavigationRequest(request)) {
            try {
                // Сначала пытаемся получить из сети
                const networkResponse = await fetch(request);
                if (networkResponse.ok) {
                    const cache = await caches.open(CACHE_NAME);
                    await cache.put(request, networkResponse.clone());
                    return networkResponse;
                }
            } catch (error) {
                // При ошибке проверяем кэш
                const cachedResponse = await caches.match(request);
                if (cachedResponse) {
                    return cachedResponse;
                }
                // Если нет в кэше, возвращаем офлайн страницу
                return caches.match('/static/offline.html');
            }
        }

        // Для остальных запросов используем Cache First стратегию
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }

        // Если нет в кэше, делаем запрос к сети
        try {
            const networkResponse = await fetch(request);
            if (networkResponse.ok) {
                const cache = await caches.open(CACHE_NAME);
                await cache.put(request, networkResponse.clone());
            }
            return networkResponse;
        } catch (error) {
            // Для картинок возвращаем плейсхолдер или fallback
            if (request.destination === 'image') {
                return caches.match('/static/offline-image.png');
            }
            throw error;
        }
    } catch (error) {
        console.error('[ServiceWorker] Fetch error:', error);
        // Возвращаем офлайн страницу для навигационных запросов
        if (isNavigationRequest(request)) {
            return caches.match('/static/offline.html');
        }
        // Для остальных запросов возвращаем ошибку
        return new Response('Нет подключения к сети', { status: 503 });
    }
}

// Перехватываем запросы
self.addEventListener('fetch', (event) => {
    event.respondWith(handleFetch(event));
});

// Периодическое обновление кэша
self.addEventListener('sync', (event) => {
    if (event.tag === 'update-cache') {
        event.waitUntil(
            caches.open(CACHE_NAME)
                .then((cache) => {
                    return cache.addAll(PRECACHE_URLS);
                })
        );
    }
});

// Обработка push-уведомлений
self.addEventListener('push', (event) => {
    if (event.data) {
        const options = {
            body: event.data.text(),
            icon: '/static/android/android-launchericon-192-192.png',
            badge: '/static/android/android-launchericon-72-72.png',
            vibrate: [100, 50, 100],
            data: {
                dateOfArrival: Date.now(),
                primaryKey: 1
            }
        };

        event.waitUntil(
            self.registration.showNotification('Расписание МелГУ', options)
        );
    }
});

// Обработка клика по уведомлению
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    event.waitUntil(
        clients.openWindow('/')
    );
});