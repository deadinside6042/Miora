const CACHE="miora-shell-v1";
const ASSETS=["/","/manifest.webmanifest"];
self.addEventListener("install",event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS))));
self.addEventListener("activate",event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key))))));
self.addEventListener("fetch",event=>{const url=new URL(event.request.url);if(url.origin===location.origin&&event.request.method==="GET"&&url.pathname!=="/"){event.respondWith(fetch(event.request).catch(()=>caches.match(event.request)))}});