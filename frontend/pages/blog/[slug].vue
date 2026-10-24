<template>
  <div class="min-h-screen bg-primary-soft" itemscope itemtype="https://schema.org/BlogPosting">
    <!-- Reading progress bar + time remaining -->
    <ReadingProgressBar v-if="post" :read-time-minutes="post.read_time_minutes || 0" :lang="blogLang" />

    <!-- Back Button -->
    <div class="pt-24 sm:pt-28 pb-6 sm:pb-8 px-4 sm:px-6">
      <div class="max-w-4xl mx-auto">
        <NuxtLink
          :to="localePath('/blog')"
          class="inline-flex items-center gap-2 text-sm font-regular text-green-light hover:text-text-brand transition-colors"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          {{ isEnglish ? 'Back to blog' : 'Volver al blog' }}
        </NuxtLink>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="blogStore.isLoading" class="flex items-center justify-center py-32">
      <div class="w-8 h-8 border-2 border-esmerald/30 border-t-esmerald rounded-full animate-spin" />
    </div>

    <!-- Not found -->
    <div v-else-if="blogStore.error === 'not_found'" class="min-h-screen flex items-center justify-center px-6">
      <div class="text-center">
        <h1 class="text-4xl font-light text-text-brand mb-4">
          {{ isEnglish ? 'Article not found' : 'Artículo no encontrado' }}
        </h1>
        <NuxtLink
          :to="localePath('/blog')"
          class="inline-flex items-center gap-2 px-8 py-4 rounded-full transition-all hover:scale-105 bg-primary text-white"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          {{ isEnglish ? 'Back to blog' : 'Volver al blog' }}
        </NuxtLink>
      </div>
    </div>

    <!-- Article -->
    <template v-else-if="post">
      <article>
        <!-- Article Header -->
        <header ref="articleHeader" class="px-4 sm:px-6 pb-8 sm:pb-12">
          <div class="max-w-4xl mx-auto">
            <div class="flex flex-wrap items-center gap-3 sm:gap-4 mb-6 sm:mb-8">
              <span v-if="post.category" class="px-3 sm:px-4 py-1.5 sm:py-2 rounded-full text-xs sm:text-sm bg-primary-soft text-text-brand font-medium capitalize">
                {{ formatCategory(post.category) }}
              </span>
              <div class="flex items-center gap-3 sm:gap-4 text-xs sm:text-sm text-green-light">
                <div v-if="post.published_at" class="flex items-center gap-1.5 sm:gap-2">
                  <svg class="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                  <time :datetime="post.published_at" itemprop="datePublished">{{ formatDate(post.published_at) }}</time>
                </div>
                <div v-if="post.read_time_minutes" class="flex items-center gap-1.5 sm:gap-2">
                  <svg class="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                  <span>{{ post.read_time_minutes }} min {{ isEnglish ? 'read' : 'de lectura' }}</span>
                </div>
              </div>
            </div>

            <h1 data-enter class="text-3xl sm:text-5xl md:text-6xl lg:text-7xl font-light mb-6 sm:mb-8 tracking-tight leading-[1.05] text-text-brand" itemprop="headline">
              {{ post.title }}
            </h1>

            <BaseRichTextContent class="text-lg sm:text-xl md:text-2xl mb-8 sm:mb-10 text-green-light leading-relaxed font-regular" itemprop="description" :source="post.excerpt" :format="post.text_formats?.['/excerpt_' + (locale === 'en-us' ? 'en' : 'es')] || 'plain'" />

            <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 pb-8 sm:pb-10 border-b border-border-default/60">
              <div class="flex items-center gap-4">
                <img
                  :src="authorProfile.image"
                  :alt="authorProfile.name"
                  class="w-11 h-11 sm:w-14 sm:h-14 rounded-full object-cover"
                />
                <div>
                  <p class="text-sm sm:text-base font-medium text-text-brand mb-0.5 sm:mb-1" itemprop="author">{{ authorProfile.name }}</p>
                  <p class="text-xs sm:text-sm text-green-light font-regular">{{ isEnglish ? authorProfile.role_en : authorProfile.role_es }}</p>
                </div>
              </div>

              <button
                class="px-5 sm:px-6 py-2.5 sm:py-3 rounded-full flex items-center gap-2 transition-all hover:scale-105 border-2 border-border-default text-text-brand"
                @click="handleShare"
              >
                <svg class="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" /></svg>
                <span class="text-sm font-regular">{{ isEnglish ? 'Share' : 'Compartir' }}</span>
              </button>
            </div>
          </div>
        </header>

        <!-- Featured Image -->
        <div v-if="post.cover_image" ref="coverImageWrap" class="px-4 sm:px-6 mb-10 sm:mb-16">
          <figure class="max-w-6xl mx-auto">
            <div class="relative aspect-[16/9] sm:aspect-[21/9] rounded-2xl sm:rounded-3xl overflow-hidden shadow-2xl">
              <img
                :src="post.cover_image"
                :alt="post.title"
                class="w-full h-full object-cover"
                loading="eager"
                itemprop="image"
              />
            </div>
            <figcaption v-if="post.cover_image_credit" class="mt-3 text-center text-sm text-green-light/60 font-regular">
              <a
                v-if="post.cover_image_credit_url"
                :href="post.cover_image_credit_url"
                target="_blank"
                rel="noopener noreferrer"
                class="hover:text-text-brand transition-colors"
              >
                {{ post.cover_image_credit }}
              </a>
              <span v-else>{{ post.cover_image_credit }}</span>
            </figcaption>
          </figure>
        </div>

        <!-- Article Content -->
        <div class="px-4 sm:px-6 pb-14 sm:pb-20">
          <div class="max-w-3xl mx-auto">
            <BlogContentRenderer
              :content-json="resolveEditorialContent(post.content_json, post.text_formats, '/content_json_' + (locale === 'en-us' ? 'en' : 'es'))"
              :html-content="post.content"
              :content-format="post.text_formats?.['/content_' + (locale === 'en-us' ? 'en' : 'es')] || 'plain'"
            />

            <!-- CTA inline -->
            <div class="bg-surface rounded-2xl p-6 sm:p-10 shadow-sm border border-border-default/60 text-center mt-12">
              <h3 class="text-2xl sm:text-3xl font-light mb-3 sm:mb-4 text-text-brand">
                {{ isEnglish ? 'Did This Article Inspire You?' : '¿Te Inspiró Este Artículo?' }}
              </h3>
              <p class="text-base sm:text-lg mb-6 sm:mb-8 text-green-light leading-relaxed font-regular">
                {{ isEnglish
                  ? 'Let\'s talk about your project. Schedule a free consultation.'
                  : 'Hablemos de tu proyecto. Agenda una consultoría gratuita.'
                }}
              </p>
              <NuxtLink
                :to="localePath('/contact')"
                class="px-8 sm:px-10 py-4 sm:py-5 rounded-full inline-flex items-center justify-center gap-3 transition-all hover:scale-105 bg-primary text-white"
              >
                <span class="text-base sm:text-lg font-medium">{{ isEnglish ? 'Contact Us' : 'Contáctanos' }}</span>
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" /></svg>
              </NuxtLink>
            </div>

            <!-- Sources -->
            <section v-if="post.sources && post.sources.length > 0" class="mt-16 pt-8 border-t border-border-default/50">
              <h3 class="text-sm font-regular text-green-light uppercase tracking-wider mb-5">
                {{ isEnglish ? 'Sources consulted' : 'Fuentes consultadas' }}
              </h3>
              <ul class="space-y-3">
                <li v-for="(source, idx) in post.sources" :key="idx">
                  <a
                    :href="source.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="inline-flex items-center gap-2 text-text-brand hover:text-esmerald/70 transition-colors text-sm font-regular"
                  >
                    <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                    {{ source.name }}
                  </a>
                </li>
              </ul>
            </section>

            <!-- Previous / Next Article Navigation -->
            <nav v-if="prevPost || nextPost" class="mt-16 pt-8 border-t border-border-default/50">
              <div class="grid grid-cols-1 gap-4" :class="prevPost && nextPost ? 'sm:grid-cols-2' : ''">
                <NuxtLink
                  v-if="prevPost"
                  :to="localePath(`/blog/${prevPost.slug}`)"
                  class="group flex items-center gap-3 p-4 rounded-2xl bg-surface border border-border-default/60 hover:shadow-md transition-all overflow-hidden"
                >
                  <svg class="w-5 h-5 text-green-light group-hover:text-text-brand transition-colors flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
                  <div class="min-w-0 flex-1">
                    <p class="text-xs text-green-light mb-1">{{ isEnglish ? 'Previous' : 'Anterior' }}</p>
                    <p class="text-sm font-medium text-text-brand leading-tight line-clamp-2">{{ prevPost.title }}</p>
                  </div>
                </NuxtLink>
                <NuxtLink
                  v-if="nextPost"
                  :to="localePath(`/blog/${nextPost.slug}`)"
                  class="group flex items-center justify-end gap-3 p-4 rounded-2xl bg-surface border border-border-default/60 hover:shadow-md transition-all text-right overflow-hidden"
                >
                  <div class="min-w-0 flex-1">
                    <p class="text-xs text-green-light mb-1">{{ isEnglish ? 'Next' : 'Siguiente' }}</p>
                    <p class="text-sm font-medium text-text-brand leading-tight line-clamp-2">{{ nextPost.title }}</p>
                  </div>
                  <svg class="w-5 h-5 text-green-light group-hover:text-text-brand transition-colors flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
                </NuxtLink>
              </div>
            </nav>
          </div>
        </div>
      </article>

      <!-- Related Posts -->
      <section v-if="relatedPosts.length > 0" class="py-14 sm:py-20 px-4 sm:px-6 bg-primary-soft">
        <div class="max-w-7xl mx-auto">
          <h2 class="text-3xl sm:text-4xl font-light mb-8 sm:mb-12 text-center text-text-brand">
            {{ isEnglish ? 'Related Articles' : 'Artículos Relacionados' }}
          </h2>

          <div class="grid sm:grid-cols-2 md:grid-cols-3 gap-6 sm:gap-8">
            <article
              v-for="relPost in relatedPosts"
              :key="relPost.id"
              class="group bg-surface rounded-2xl overflow-hidden shadow-sm hover:shadow-xl transition-all duration-500 cursor-pointer"
              @click="navigateTo(localePath(`/blog/${relPost.slug}`))"
            >
              <div class="relative aspect-[16/10] overflow-hidden">
                <img
                  v-if="relPost.cover_image"
                  :src="relPost.cover_image"
                  :alt="relPost.title"
                  class="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700"
                  loading="lazy"
                />
                <div v-else class="w-full h-full bg-gradient-to-br from-esmerald-light to-gray-100 flex items-center justify-center">
                  <svg class="w-10 h-10 text-esmerald/15" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" /></svg>
                </div>
                <div v-if="relPost.category" class="absolute top-4 left-4">
                  <span class="px-3 py-1.5 rounded-full text-xs backdrop-blur-md bg-surface/90 text-text-brand font-medium capitalize">
                    {{ formatCategory(relPost.category) }}
                  </span>
                </div>
              </div>

              <div class="p-6">
                <h3 class="text-xl font-light mb-4 group-hover:text-green-light transition-colors leading-tight text-text-brand">
                  <NuxtLink :to="localePath(`/blog/${relPost.slug}`)" @click.stop>{{ relPost.title }}</NuxtLink>
                </h3>
                <div v-if="relPost.read_time_minutes" class="flex items-center gap-2 text-sm text-green-light">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                  <span class="font-regular">{{ relPost.read_time_minutes }} min</span>
                </div>
              </div>
            </article>
          </div>
        </div>
      </section>
    </template>

    <!-- Contact + Footer -->
    <ContactSection />
    <FooterSection />
  </div>
</template>

<script setup>
import { resolveEditorialContent } from '~/utils/editorialMetadata';
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import ContactSection from '~/components/sections/ContactSection.vue';
import FooterSection from '~/components/sections/FooterSection.vue';
import BlogContentRenderer from '~/components/blog/BlogContentRenderer.vue';
import ReadingProgressBar from '~/components/blog/ReadingProgressBar.vue';
import { useBlogStore } from '~/stores/blog';
import { fadeUp } from '~/animations';
import { usePageEntrance } from '~/composables/usePageEntrance';
import { useBlogPostJsonLd } from '~/composables/useSeoJsonLd';
import { formatDate as formatDateBase } from '~/utils/formatDate';

usePageEntrance();

const AUTHOR_PROFILES = {
  'projectapp-team': {
    name: 'Project App',
    role_es: 'Equipo de Ingeniería',
    role_en: 'Engineering Team',
    image: '/img/authors/projectapp-team.webp',
  },
  'gustavo-perez': {
    name: 'Gustavo Pérez',
    role_es: 'CEO — Project App',
    role_en: 'CEO — Project App',
    image: '/img/authors/gustavo-perez.webp',
  },
  'carlos-blanco': {
    name: 'Carlos Blanco',
    role_es: 'CFO — Project App',
    role_en: 'CFO — Project App',
    image: '/img/authors/carlos-blanco.webp',
  },
};

const route = useRoute();
const { locale } = useI18n();
const localePath = useLocalePath();
const blogStore = useBlogStore();
const post = computed(() => blogStore.currentPost);
const isEnglish = computed(() => locale.value.startsWith('en'));
const blogLang = computed(() => isEnglish.value ? 'en' : 'es');

// Fetch the post during SSR/prerender so the generated HTML carries the full
// article + metas (crawlers and link previews never run onMounted). On the
// server, relative /api URLs have no origin, so we hit Django directly.
const runtimeConfig = useRuntimeConfig();
const { data: ssrPost, error: ssrError } = await useAsyncData(
  `blog-post-${route.params.slug}-${locale.value}`,
  () => {
    const base = import.meta.server ? runtimeConfig.apiInternalOrigin : '';
    return $fetch(`${base}/api/blog/${route.params.slug}/?lang=${isEnglish.value ? 'en' : 'es'}`);
  },
);

if (ssrPost.value) {
  blogStore.currentPost = ssrPost.value;
  blogStore.error = null;
} else if (ssrError.value) {
  blogStore.error = ssrError.value.statusCode === 404 ? 'not_found' : 'fetch_failed';
  if (import.meta.server) {
    setResponseStatus(useRequestEvent(), ssrError.value.statusCode === 404 ? 404 : 500);
  }
}

const authorProfile = computed(() => {
  const slug = post.value?.author || 'projectapp-team';
  return AUTHOR_PROFILES[slug] || AUTHOR_PROFILES['projectapp-team'];
});

const relatedPosts = computed(() => {
  if (!post.value || !blogStore.posts.length) return [];
  return blogStore.posts
    .filter((p) => p.id !== post.value.id)
    .slice(0, 3);
});

const currentIndex = computed(() => {
  if (!post.value || !blogStore.posts.length) return -1;
  return blogStore.posts.findIndex((p) => p.id === post.value.id);
});

const prevPost = computed(() => {
  const idx = currentIndex.value;
  if (idx <= 0) return null;
  return blogStore.posts[idx - 1];
});

const nextPost = computed(() => {
  const idx = currentIndex.value;
  if (idx < 0 || idx >= blogStore.posts.length - 1) return null;
  return blogStore.posts[idx + 1];
});

const baseUrl = 'https://projectapp.co';
const i18nHead = useLocaleHead({ addSeoAttributes: true });

const articleTitle = computed(() => {
  if (!post.value) return 'Blog — Project App.';
  return post.value.meta_title || `${post.value.title} — Project App.`;
});
const articleDescription = computed(() => post.value?.meta_description || post.value?.excerpt_plain || post.value?.excerpt || '');

useHead({
  title: articleTitle,
  meta: [
    { name: 'description', content: articleDescription },
    { name: 'keywords', content: computed(() => post.value?.meta_keywords || '') },
    { property: 'og:title', content: articleTitle },
    { property: 'og:description', content: articleDescription },
    { property: 'og:image', content: computed(() => post.value?.cover_image || `${baseUrl}/img/og-image.webp`) },
    { property: 'og:type', content: 'article' },
    { property: 'og:url', content: computed(() => `${baseUrl}${route.fullPath}`) },
    { property: 'og:site_name', content: 'Project App.' },
    { property: 'og:locale', content: computed(() => locale.value === 'es-co' ? 'es_CO' : 'en_US') },
    { property: 'article:published_time', content: computed(() => post.value?.published_at || '') },
    { property: 'article:author', content: 'Project App.' },
    { name: 'twitter:card', content: 'summary_large_image' },
    { name: 'twitter:site', content: '@projectappco' },
    { name: 'twitter:title', content: articleTitle },
    { name: 'twitter:description', content: articleDescription },
    { name: 'twitter:image', content: computed(() => post.value?.cover_image || `${baseUrl}/img/og-image.webp`) },
  ],
  htmlAttrs: {
    lang: i18nHead.value.htmlAttrs?.lang,
  },
  link: [
    { rel: 'canonical', href: computed(() => `${baseUrl}${route.fullPath}`) },
    ...(i18nHead.value.link || []),
  ],
});

watch(post, (newPost) => {
  if (newPost) {
    useBlogPostJsonLd(newPost, locale.value);
  }
}, { immediate: true });

const CATEGORY_LABELS = {
  technology: { es: 'Tecnología', en: 'Technology' },
  design: { es: 'Diseño', en: 'Design' },
  guides: { es: 'Guías', en: 'Guides' },
  business: { es: 'Negocios', en: 'Business' },
  'case-study': { es: 'Casos de Éxito', en: 'Case Studies' },
  ai: { es: 'IA', en: 'AI' },
  development: { es: 'Desarrollo', en: 'Development' },
  marketing: { es: 'Marketing Digital', en: 'Digital Marketing' },
  startup: { es: 'Startups', en: 'Startups' },
  productivity: { es: 'Productividad', en: 'Productivity' },
  security: { es: 'Ciberseguridad', en: 'Cybersecurity' },
  cloud: { es: 'Cloud & DevOps', en: 'Cloud & DevOps' },
  data: { es: 'Datos & Analytics', en: 'Data & Analytics' },
  'no-code': { es: 'No-Code / Low-Code', en: 'No-Code / Low-Code' },
  trends: { es: 'Tendencias', en: 'Trends' },
  'e-commerce': { es: 'E-Commerce', en: 'E-Commerce' },
  'ux-ui': { es: 'UX / UI', en: 'UX / UI' },
};

function formatCategory(cat) {
  const labels = CATEGORY_LABELS[cat];
  if (labels) return isEnglish.value ? labels.en : labels.es;
  return cat;
}

const articleHeader = ref(null);
const coverImageWrap = ref(null);

function runArticleAnimations() {
  nextTick(() => {
    if (articleHeader.value) {
      const children = articleHeader.value.querySelectorAll('h1, p, .flex');
      children.forEach((el, i) => fadeUp(el, { delay: 0.1 + i * 0.12 }));
    }
    if (coverImageWrap.value) fadeUp(coverImageWrap.value, { delay: 0.3 });
  });
}

onMounted(async () => {
  // The post itself is hydrated from the SSR payload; only refetch if missing.
  if (!post.value) {
    await blogStore.fetchPost(route.params.slug, blogLang.value);
  }
  if (!blogStore.error && !blogStore.posts.length) {
    blogStore.fetchPosts(blogLang.value);
  }
  runArticleAnimations();
});

watch(() => route.params.slug, (newSlug) => {
  if (newSlug) {
    blogStore.fetchPost(newSlug, blogLang.value);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
});

function formatDate(dateStr) {
  return formatDateBase(dateStr, { locale: isEnglish.value ? 'en' : 'es', fallback: '' });
}

function handleShare() {
  if (navigator.share) {
    navigator.share({
      title: post.value?.title || '',
      text: post.value?.excerpt || '',
      url: window.location.href,
    });
  } else {
    navigator.clipboard.writeText(window.location.href);
  }
}
</script>
