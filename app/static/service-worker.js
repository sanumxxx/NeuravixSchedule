// service-worker.js

// Имя кэша - меняйте при обновлении приложения
const CACHE_NAME = 'melgu-schedule-v1';

// Список ресурсов для кэширования
const urlsToCache = [
    '/',
    '/static/manifest.json',
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
    // Стили и скрипты
    '/static/css/style.css',
    '/static/js/main.js',
    // Добавьте другие важные ресурсы
];

// Установка Service Worker
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('Кэш открыт');
                return cache.addAll(urlsToCache);
            })
            .then(() => self.skipWaiting()) // Активируем SW сразу
    );
});

// Активация Service Worker
self.addEventListener('activate', (event) => {
    event.waitUntil(
        // Удаляем старые версии кэша
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});

// Перехват запросов
self.addEventListener('fetch', (event) => {
    event.respondWith(
        caches.match(event.request)
            .then((response) => {
                // Возвращаем кэшированный ответ если есть
                if (response) {
                    return response;
                }

                // Иначе делаем запрос к сети
                return fetch(event.request).then(
                    (response) => {
                        // Проверяем корректность ответа
                        if (!response || response.status !== 200 || response.type !== 'basic') {
                            return response;
                        }

                        // Кэшируем ответ
                        let responseToCache = response.clone();
                        caches.open(CACHE_NAME)
                            .then((cache) => {
                                cache.put(event.request, responseToCache);
                            });

                        return response;
                    }
                ).catch(() => {
                    // Если нет соединения, возвращаем заглушку
                    if (event.request.mode === 'navigate') {
                        return new Response(
                            `
                            <!DOCTYPE html>
                            <html lang="ru">
                            <head>
                                <meta charset="UTF-8">
                                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                                <title>Офлайн - Расписание МелГУ</title>
                                <style>
                                    body {
                                        font-family: system-ui;
                                        display: flex;
                                        align-items: center;
                                        justify-content: center;
                                        height: 100vh;
                                        margin: 0;
                                        background: #1d232a;
                                        color: white;
                                    }
                                    .offline-message {
                                        text-align: center;
                                        padding: 20px;
                                    }
                                </style>
                            </head>
                            <body>
                                <div class="offline-message">
                                    <h1>Нет подключения к интернету</h1>
                                    <p>Проверьте подключение и попробуйте снова</p>
                                </div>
                            </body>
                            </html>
                            `,
                            {
                                headers: {
                                    'Content-Type': 'text/html; charset=utf-8'
                                }
                            }
                        );
                    }
                });
            })
    );
});