// https://nuxt.com/docs/api/configuration/nuxt-config
// Django dev server target for the dev proxy; override with DJANGO_DEV_TARGET
// when port 8000 is taken (e.g. DJANGO_DEV_TARGET=http://127.0.0.1:8001)
const djangoDevTarget = process.env.DJANGO_DEV_TARGET || 'http://127.0.0.1:8000'

// API origin used for server-side fetches during SSR/prerender, where relative
// /api URLs have no origin to resolve against.
const apiInternalOrigin = process.env.PRERENDER_API_ORIGIN || djangoDevTarget

// Blog post routes to prerender, fetched from the Django API at build time.
// Gated by PRERENDER_BLOG=1 (set by update-django-template.js) so `nuxi dev`
// and CI builds without a backend are unaffected. PRERENDER_REQUIRE_BLOG=1
// (set by the production rebuild task) turns a missing API into a hard build
// failure — a deploy that silently drops 62 prerendered posts is a regression.
async function blogPrerenderRoutes(): Promise<string[]> {
  if (process.env.PRERENDER_BLOG !== '1') return []
  try {
    const res = await fetch(`${apiInternalOrigin}/api/blog/sitemap-data/`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const posts: Array<{ slug: string }> = await res.json()
    const routes = posts.flatMap((p) => [`/es-co/blog/${p.slug}`, `/en-us/blog/${p.slug}`])
    console.log(`[blog-prerender] ${routes.length} routes (${posts.length} posts) from ${apiInternalOrigin}`)
    return routes
  } catch (err) {
    const msg = `[blog-prerender] Could not fetch slugs from ${apiInternalOrigin}: ${err}`
    if (process.env.PRERENDER_REQUIRE_BLOG === '1') throw new Error(msg)
    console.warn(`${msg} — building WITHOUT blog post prerender`)
    return []
  }
}

export default defineNuxtConfig({
  devtools: { enabled: true },

  // Keep the existing Nuxt 3-era root layout while adopting Nuxt 4. Nuxt 4
  // otherwise defaults application sources to app/.
  srcDir: '.',
  buildDir: '.nuxt',
  dir: {
    app: 'app',
  },

  modules: [
    '@nuxtjs/tailwindcss',
    '@pinia/nuxt',
    '@nuxtjs/i18n',
  ],

  // Hybrid rendering: key pages SSR, rest SPA
  routeRules: {
    '/': { ssr: true },
    '/en-us': { ssr: true },
    '/es-co': { ssr: true },
    '/en-us/landing-web-design': { ssr: true },
    '/es-co/landing-web-design': { ssr: true },
    '/en-us/landing-software': { ssr: true },
    '/es-co/landing-software': { ssr: true },
    '/en-us/landing-apps': { ssr: true },
    '/es-co/landing-apps': { ssr: true },
    '/en-us/about-us': { ssr: true },
    '/es-co/about-us': { ssr: true },
    '/en-us/additional-modules': { ssr: true },
    '/es-co/additional-modules': { ssr: true },
    '/en-us/partnership-program': { ssr: true },
    '/es-co/partnership-program': { ssr: true },
    '/en-us/additional-modules/share/**': { ssr: false },
    '/es-co/additional-modules/share/**': { ssr: false },
    '/en-us/secure-link/**': { ssr: false },
    '/es-co/secure-link/**': { ssr: false },
    '/en-us/portfolio-works': { ssr: true },
    '/en-us/portfolio-works/**': { ssr: true },
    '/es-co/portfolio-works': { ssr: true },
    '/es-co/portfolio-works/**': { ssr: true },
    '/portfolio-works/**': { ssr: true },
    '/es-co/**': { ssr: false },
    '/en-us/**': { ssr: false },
    '/blog': { ssr: true },
    '/blog/**': { ssr: true },
    '/en-us/blog': { ssr: true },
    '/en-us/blog/**': { ssr: true },
    '/es-co/blog': { ssr: true },
    '/es-co/blog/**': { ssr: true },
    '/proposal/**': { ssr: false },
    '/platform': { ssr: false },
    '/platform/**': { ssr: false },
    '/panel/**': { ssr: false },
    '/**': { ssr: false },
  },

  // Proxy API calls to Django backend
  nitro: {
    devProxy: {
      '/api': {
        target: `${djangoDevTarget}/api`,
        changeOrigin: true,
      },
      '/admin': {
        // Preserve the root slash: Django redirects /admin back to /admin/.
        target: `${djangoDevTarget}/admin/`,
        changeOrigin: true,
      },
      '/static': {
        target: `${djangoDevTarget}/static`,
        changeOrigin: true,
      },
      '/media': {
        target: `${djangoDevTarget}/media`,
        changeOrigin: true,
      },
    },
    prerender: {
      fallback: true,
      crawlLinks: true,
      routes: [
        '/',
        '/en-us',
        '/en-us/about-us',
        '/en-us/portfolio-works',
        '/en-us/contact',
        '/en-us/contact-success',
        '/en-us/blog',
        '/es-co',
        '/es-co/about-us',
        '/es-co/portfolio-works',
        '/es-co/contact',
        '/es-co/contact-success',
        '/es-co/blog',
        '/en-us/additional-modules',
        '/es-co/additional-modules',
        '/en-us/partnership-program',
        '/es-co/partnership-program',
        ...(await blogPrerenderRoutes()),
      ],
    },
    hooks: {
      'prerender:generate'(route) {
        const privateRoute = /^\/(?:(?:en-us|es-co)\/)?(?:(?:panel|platform|proposal|auth|secure-link)(?:\/|$)|additional-modules\/share(?:\/|$))/
        if (privateRoute.test(route.route ?? '')) route.skip = true
      },
    },
  },

  // Alias @ to project root (like src/ was before)
  alias: {
    '@': '.',
  },

  // CSS
  css: [
    '~/assets/styles/main.css',
    '~/assets/styles/platform-cover.css',
  ],

  // Tailwind config
  tailwindcss: {
    configPath: '~/tailwind.config.js',
  },

  // i18n configuration
  i18n: {
    locales: [
      {
        code: 'es-co',
        language: 'es-CO',
        name: 'Español (Colombia)',
        file: 'es-co.ts',
      },
      {
        code: 'en-us',
        language: 'en-US',
        name: 'English (United States)',
        file: 'en-us.ts',
      },
    ],
    defaultLocale: 'en-us',
    strategy: 'prefix',
    // Django owns the locale decision for unprefixed requests using the
    // preferred_locale cookie and nginx's country header. Enabling the i18n
    // redirect here also rewrites Nitro's /200.html SPA fallback into a
    // self-referential locale redirect, breaking every deep SPA route.
    detectBrowserLanguage: false,
    // SEO
    baseUrl: 'https://projectapp.co',
  },

  // App head (Facebook Pixel, Cal.com, meta)
  app: {
    // In production, assets are served by Django at /static/frontend/
    cdnURL: process.env.NUXT_APP_CDN_URL || '',
    head: {
      charset: 'utf-8',
      viewport: 'width=device-width, initial-scale=1',
      title: 'Project App.',
      meta: [
        { name: 'google-site-verification', content: 'EtrTR8lVbb-7KkP0sPu0WA9_W8gV1wpTp1FCgUvGG6s' },
      ],
      link: [
        { rel: 'icon', href: '/img/icons/icon-logo-192x192.png' },
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        { rel: 'stylesheet', href: 'https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&display=swap' },
      ],
      script: [
        // Analytics & marketing tags (GTM, Clarity, Google Ads, Facebook Pixel)
        // are NOT injected here. They load lazily, public-routes-only, via
        // plugins/analytics.client.js so private areas (panel/platform/
        // proposal/diagnostic) are never reported. Cal.com below is a
        // functional booking widget (not analytics) and stays global.
        {
          children: `(function(C,A,L){let p=function(a,ar){a.q.push(ar)};let d=C.document;C.Cal=C.Cal||function(){let cal=C.Cal;let ar=arguments;if(!cal.loaded){cal.ns={};cal.q=cal.q||[];d.head.appendChild(d.createElement("script")).src=A;cal.loaded=true}if(ar[0]===L){const api=function(){p(api,arguments)};const namespace=ar[1];api.q=api.q||[];if(typeof namespace==="string"){cal.ns[namespace]=cal.ns[namespace]||api;p(cal.ns[namespace],ar);p(cal,["initNamespace",namespace])}else{p(cal,ar)}return}p(cal,ar)}})(window,"https://app.cal.com/embed/embed.js","init");Cal("init","discovery-call-projectapp",{origin:"https://app.cal.com"});Cal.ns["discovery-call-projectapp"]("ui",{theme:"dark",hideEventTypeDetails:false,layout:"week_view"});`,
        },
      ],
    },
  },

  runtimeConfig: {
    // Server-only: origin for SSR/prerender fetches against the Django API.
    apiInternalOrigin,
    public: {
      recaptchaSiteKey: process.env.NUXT_PUBLIC_RECAPTCHA_SITE_KEY || '',
      // Only local dev/test servers may explicitly opt out. Generated builds enforce CAPTCHA.
      recaptchaEnabled: process.env.NODE_ENV === 'production' || process.env.NUXT_PUBLIC_RECAPTCHA_ENABLED !== 'false',
    },
  },

  experimental: {
    appManifest: false,
    // Django serves the generated site below /static/frontend/. Extracted
    // payload URLs use app.cdnURL and can be prerendered as HTML routes by the
    // Nitro crawler, so keep payload data inline for this deployment topology.
    payloadExtraction: false,
  },

  vite: {
    optimizeDeps: {
      include: [
        'apexcharts/core',
        'apexcharts/line',
        'apexcharts/area',
        'apexcharts/bar',
        'apexcharts/donut',
        'apexcharts/radialBar',
        'apexcharts/features/legend',
        'apexcharts/features/annotations',
        'apexcharts/features/exports',
      ],
    },
    $client: {
      build: {
        rollupOptions: {
          output: {
            manualChunks(id) {
              const normalizedId = id.replaceAll('\\', '/')

              if (normalizedId.includes('/node_modules/apexcharts/dist/features/')) {
                return 'apexcharts-features'
              }
              if (
                /\/node_modules\/apexcharts\/dist\/(line|area|bar|donut|radialBar)\.esm\.js$/.test(
                  normalizedId,
                )
              ) {
                return 'apexcharts-chart-types'
              }
              if (normalizedId.includes('/node_modules/apexcharts/dist/core.esm.js')) {
                return 'apexcharts-core'
              }
              if (normalizedId.includes('/node_modules/gsap/')) {
                return 'gsap'
              }

              return undefined
            },
          },
        },
      },
    },
  },

  compatibilityDate: '2024-11-01',
})
