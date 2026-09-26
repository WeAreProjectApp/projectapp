/**
 * Public-only analytics/marketing loader.
 *
 * GTM, Microsoft Clarity, Google Ads (gtag.js) and the Facebook Pixel are
 * injected here — lazily and ONLY while the user is on a public marketing
 * route. Private areas (panel, platform, proposal, diagnostic) never load any
 * of these tags, so they are never reported to Analytics/Ads/Clarity/Meta.
 *
 * The tags previously lived in nuxt.config.ts `head`, which loaded them on
 * every route. They were moved here so the route can gate them.
 *
 * Note: Cal.com (the booking widget) is NOT analytics and stays global in
 * nuxt.config.ts. The Google Ads conversion helpers in useGtagConversions.js
 * keep working because `window.gtag` is defined here before any conversion can
 * fire (conversions only happen on public pages).
 */

// Same private-route set used by app.vue (showNavbar/showWhatsApp). `includes`
// is robust to optional locale prefixes (e.g. /en-us/... never matches these).
const PRIVATE_SEGMENTS = [
  '/panel',
  '/platform',
  '/proposal',
  '/diagnostic',
  '/additional-modules/share',
  '/secure-link',
]

const isPublicRoute = (path) =>
  !PRIVATE_SEGMENTS.some((segment) => path.includes(segment))

// Egress shield: hosts/paths used PURELY for analytics/marketing ingestion.
// Matched against outbound request URLs so that, while on a private route, any
// straggler hit (e.g. a GA4/GTM history-change pageview that fires after the
// tags were loaded on a public page) is dropped. Deliberately narrow — it
// never matches first-party `/api`, app assets, or anything else.
const ANALYTICS_HOSTS = [
  'google-analytics.com',
  'analytics.google.com',
  'googletagmanager.com',
  'googleadservices.com',
  'clarity.ms',
  'connect.facebook.net',
  'facebook.com/tr',
]

const isAnalyticsUrl = (url) => {
  if (!url) return false
  const u = String(url)
  return ANALYTICS_HOSTS.some((h) => u.includes(h))
}

const loadGoogleTagManager = () => {
  /* eslint-disable */
  ;(function (w, d, s, l, i) {
    w[l] = w[l] || []
    w[l].push({ 'gtm.start': new Date().getTime(), event: 'gtm.js' })
    const f = d.getElementsByTagName(s)[0]
    const j = d.createElement(s)
    const dl = l != 'dataLayer' ? '&l=' + l : ''
    j.async = true
    j.src = 'https://www.googletagmanager.com/gtm.js?id=' + i + dl
    f.parentNode.insertBefore(j, f)
  })(window, document, 'script', 'dataLayer', 'GTM-564CMQCG')
  /* eslint-enable */
}

const loadClarity = () => {
  /* eslint-disable */
  ;(function (c, l, a, r, i, t, y) {
    c[a] = c[a] || function () {
      ;(c[a].q = c[a].q || []).push(arguments)
    }
    t = l.createElement(r)
    t.async = 1
    t.src = 'https://www.clarity.ms/tag/' + i
    y = l.getElementsByTagName(r)[0]
    y.parentNode.insertBefore(t, y)
  })(window, document, 'clarity', 'script', 'vm01q8i9wc')
  /* eslint-enable */
}

const loadGoogleAds = () => {
  window.dataLayer = window.dataLayer || []
  // Keep the canonical gtag signature so useGtagConversions.js can call it.
  function gtag() {
    window.dataLayer.push(arguments)
  }
  window.gtag = window.gtag || gtag

  const s = document.createElement('script')
  s.async = true
  s.src = 'https://www.googletagmanager.com/gtag/js?id=AW-16942315762'
  document.head.appendChild(s)

  window.gtag('js', new Date())
  window.gtag('config', 'AW-16942315762')
}

const loadFacebookPixel = () => {
  /* eslint-disable */
  ;(function (f, b, e, v, n, t, s) {
    if (f.fbq) return
    n = f.fbq = function () {
      n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments)
    }
    if (!f._fbq) f._fbq = n
    n.push = n
    n.loaded = !0
    n.version = '2.0'
    n.queue = []
    t = b.createElement(e)
    t.async = !0
    t.src = v
    s = b.getElementsByTagName(e)[0]
    s.parentNode.insertBefore(t, s)
  })(window, document, 'script', 'https://connect.facebook.net/en_US/fbevents.js')
  /* eslint-enable */
  window.fbq('init', '1870177640258815')
  window.fbq('track', 'PageView')
}

// Install the egress shield once. While `onPrivate` is true, analytics-only
// requests are silently dropped; every other request passes through untouched.
let onPrivate = false
let shieldInstalled = false

const installEgressShield = () => {
  if (shieldInstalled || typeof window === 'undefined') return
  shieldInstalled = true

  // navigator.sendBeacon — GA4/Clarity's primary transport.
  if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
    const originalBeacon = navigator.sendBeacon.bind(navigator)
    navigator.sendBeacon = (url, data) => {
      if (onPrivate && isAnalyticsUrl(url)) return true // pretend success, send nothing
      return originalBeacon(url, data)
    }
  }

  // window.fetch — GA4 keepalive fallback. Pass everything else (incl. /api).
  if (typeof window.fetch === 'function') {
    const originalFetch = window.fetch.bind(window)
    window.fetch = (input, init) => {
      const url = typeof input === 'string' ? input : input?.url
      if (onPrivate && isAnalyticsUrl(url)) {
        return Promise.resolve(new Response(null, { status: 204, statusText: 'No Content' }))
      }
      return originalFetch(input, init)
    }
  }
}

export default defineNuxtPlugin(() => {
  const router = useRouter()
  let loaded = false

  const loadAll = () => {
    if (loaded) return
    loaded = true
    loadGoogleTagManager()
    loadClarity()
    loadGoogleAds()
    loadFacebookPixel()
  }

  installEgressShield()

  const applyRoute = (path) => {
    onPrivate = !isPublicRoute(path)
    if (!onPrivate) loadAll()
  }

  // Initial route: set the shield state and load tags if public...
  applyRoute(router.currentRoute.value.path)

  // ...and keep both in sync on every navigation. Tags load the first time a
  // public route is seen (guarded against duplicates); the shield blocks
  // analytics egress whenever the current route is private.
  router.afterEach((to) => {
    applyRoute(to.path)
  })
})
