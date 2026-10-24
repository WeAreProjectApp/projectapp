<template>
  <div class="min-h-screen bg-primary-soft" itemscope itemtype="https://schema.org/Blog">
    <!-- Hero Section -->
    <section ref="heroSection" class="relative pt-32 sm:pt-40 pb-16 sm:pb-20 px-4 sm:px-6 overflow-hidden" aria-labelledby="blog-title">
      <!-- Subtle decorative circles -->
      <div class="absolute top-20 -left-32 w-96 h-96 bg-esmerald/5 rounded-full blur-3xl" />
      <div class="absolute top-40 -right-32 w-80 h-80 bg-accent/10 rounded-full blur-3xl" />
      <div class="max-w-7xl mx-auto relative">
        <div class="text-center mb-16">
          <h1
            id="blog-title"
            data-enter
            class="text-5xl sm:text-6xl md:text-7xl lg:text-8xl font-light mb-6 tracking-tight leading-[1.05] text-text-brand"
          >
            Blog
          </h1>
          <p data-enter class="text-xl md:text-2xl max-w-3xl mx-auto text-green-light leading-relaxed font-regular">
            {{ isEnglish
              ? 'Insights and trends in AI, software development, and digital transformation.'
              : 'Novedades y tendencias en IA, desarrollo de software y transformación digital.'
            }}
          </p>
        </div>

        <!-- Search & Category Filters -->
        <div class="mb-16">
          <div class="max-w-2xl mx-auto mb-8">
            <div class="relative">
              <svg class="absolute left-6 top-1/2 -translate-y-1/2 w-5 h-5 text-green-light" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                v-model="searchQuery"
                type="text"
                :placeholder="isEnglish ? 'Search articles...' : 'Buscar artículos...'"
                class="w-full pl-14 pr-6 py-5 rounded-2xl border-2 border-border-default focus:outline-none focus:border-primary transition-all text-lg bg-surface font-regular"
              />
            </div>
          </div>

          <div ref="filtersRow" class="flex items-center gap-2 sm:gap-3 overflow-x-auto pb-2 sm:pb-0 sm:flex-wrap sm:justify-center sm:overflow-visible scrollbar-hide">
            <button
              :class="[
                'flex-shrink-0 px-4 sm:px-6 py-2.5 sm:py-3 rounded-full transition-all hover:scale-105 border-2 text-sm sm:text-base whitespace-nowrap',
                selectedCategory === ''
                  ? 'bg-primary text-white border-primary font-medium'
                  : 'bg-surface text-green-light border-border-default font-regular hover:border-esmerald/40'
              ]"
              @click="selectedCategory = ''"
            >
              {{ isEnglish ? 'All' : 'Todos' }}
            </button>
            <button
              v-for="cat in availableCategories"
              :key="cat"
              :class="[
                'flex-shrink-0 px-4 sm:px-6 py-2.5 sm:py-3 rounded-full transition-all hover:scale-105 border-2 text-sm sm:text-base capitalize whitespace-nowrap',
                selectedCategory === cat
                  ? 'bg-primary text-white border-primary font-medium'
                  : 'bg-surface text-green-light border-border-default font-regular hover:border-esmerald/40'
              ]"
              @click="selectedCategory = cat"
            >
              {{ formatCategory(cat) }}
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- Loading -->
    <div v-if="blogStore.isLoading" class="flex items-center justify-center py-32">
      <div class="w-8 h-8 border-2 border-esmerald/30 border-t-esmerald rounded-full animate-spin" />
    </div>

    <!-- Content -->
    <main v-else class="px-4 sm:px-6">
      <div class="max-w-7xl mx-auto">

        <!-- Empty state -->
        <div v-if="posts.length === 0" class="text-center py-32">
          <p class="text-green-light text-lg font-regular">
            {{ isEnglish ? 'No articles published yet.' : 'No hay artículos publicados aún.' }}
          </p>
        </div>

        <template v-else>
          <!-- Featured Post (full-width hero with gradient overlay) -->
          <article
            v-if="featured && selectedCategory === '' && !searchQuery"
            ref="featuredCard"
            class="mb-20 group cursor-pointer"
            @click="navigateTo(localePath(`/blog/${featured.slug}`))"
            itemscope
            itemtype="https://schema.org/BlogPosting"
          >
            <div class="relative aspect-[16/9] sm:aspect-[21/9] rounded-2xl sm:rounded-3xl overflow-hidden bg-surface shadow-lg hover:shadow-2xl transition-all duration-500">
              <img
                v-if="featured.cover_image"
                :src="featured.cover_image"
                :alt="featured.title"
                class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
                loading="eager"
                itemprop="image"
              />
              <div
                v-else
                class="w-full h-full bg-gradient-to-br from-esmerald to-esmerald-dark"
              />
              <div class="absolute inset-0 bg-gradient-to-t from-esmerald-dark/80 via-esmerald-dark/30 to-transparent" />

              <div class="absolute inset-0 flex flex-col justify-end p-5 sm:p-8 md:p-12 lg:p-16">
                <div class="flex flex-wrap items-center gap-2 sm:gap-4 mb-4 sm:mb-6">
                  <span class="px-3 sm:px-4 py-1.5 sm:py-2 rounded-full text-xs sm:text-sm bg-accent text-text-brand font-medium">
                    {{ isEnglish ? '⭐ Featured' : '⭐ Destacado' }}
                  </span>
                  <span v-if="featured.category" class="px-3 sm:px-4 py-1.5 sm:py-2 rounded-full text-xs sm:text-sm bg-surface/20 text-white font-regular capitalize">
                    {{ formatCategory(featured.category) }}
                  </span>
                </div>

                <h2 class="text-2xl sm:text-4xl md:text-5xl lg:text-6xl font-light mb-4 sm:mb-6 max-w-4xl text-white leading-[1.1]" itemprop="headline">
                  <NuxtLink :to="localePath(`/blog/${featured.slug}`)" @click.stop>{{ featured.title }}</NuxtLink>
                </h2>

                <p class="text-sm sm:text-lg md:text-xl mb-4 sm:mb-8 max-w-3xl text-white/80 leading-relaxed hidden sm:block font-regular" itemprop="description">
                  {{ featured.excerpt }}
                </p>

                <div class="hidden sm:flex items-center gap-6 text-sm text-white/70">
                  <div v-if="featured.published_at" class="flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                    <time :datetime="featured.published_at" itemprop="datePublished">{{ formatDate(featured.published_at) }}</time>
                  </div>
                  <div v-if="featured.read_time_minutes" class="flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    <span>{{ featured.read_time_minutes }} min {{ isEnglish ? 'read' : 'de lectura' }}</span>
                  </div>
                  <div class="flex items-center gap-2 ml-auto group-hover:gap-4 transition-all">
                    <span class="font-medium text-white">{{ isEnglish ? 'Read article' : 'Leer artículo' }}</span>
                    <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" /></svg>
                  </div>
                </div>
              </div>
            </div>
          </article>

          <!-- Mobile cards (compact horizontal) -->
          <div class="sm:hidden space-y-3 pb-16">
            <article
              v-for="post in filteredPosts"
              :key="post.id"
              class="group bg-surface rounded-2xl overflow-hidden shadow-sm active:scale-[0.98] transition-transform border border-border-default/60 cursor-pointer"
              @click="navigateTo(localePath(`/blog/${post.slug}`))"
              itemscope
              itemtype="https://schema.org/BlogPosting"
            >
              <div class="flex gap-3 p-3">
                <div class="relative w-24 h-24 rounded-xl overflow-hidden flex-shrink-0">
                  <img
                    v-if="post.cover_image"
                    :src="post.cover_image"
                    :alt="post.title"
                    class="w-full h-full object-cover"
                    loading="lazy"
                    itemprop="image"
                  />
                  <div v-else class="w-full h-full bg-primary-soft flex items-center justify-center">
                    <svg class="w-8 h-8 text-esmerald/15" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" /></svg>
                  </div>
                  <div v-if="post.category" class="absolute top-1.5 left-1.5">
                    <span class="px-2 py-0.5 rounded-full text-[10px] backdrop-blur-md bg-surface/90 text-text-brand font-medium capitalize">
                      {{ formatCategory(post.category) }}
                    </span>
                  </div>
                </div>
                <div class="flex-1 min-w-0 py-0.5 flex flex-col">
                  <h3 class="text-sm font-medium text-text-brand mb-1 leading-tight line-clamp-2" itemprop="headline">
                    <NuxtLink :to="localePath(`/blog/${post.slug}`)" @click.stop>{{ post.title }}</NuxtLink>
                  </h3>
                  <BaseRichTextContent class="text-xs text-green-light line-clamp-2 mb-1.5 flex-1 font-regular" itemprop="description" :source="post.excerpt" :format="post.text_formats?.['/excerpt_' + (locale === 'en-us' ? 'en' : 'es')] || 'plain'" />
                  <div class="flex items-center gap-3 text-[10px] text-green-light">
                    <span v-if="post.published_at" class="flex items-center gap-1">
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                      <time :datetime="post.published_at" itemprop="datePublished">{{ formatDateShort(post.published_at) }}</time>
                    </span>
                    <span v-if="post.read_time_minutes" class="flex items-center gap-1">
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      {{ post.read_time_minutes }} min
                    </span>
                  </div>
                </div>
              </div>
            </article>
          </div>

          <!-- Desktop grid -->
          <div ref="postsGrid" class="hidden sm:grid sm:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8 pb-20">
            <article
              v-for="post in filteredPosts"
              :key="post.id"
              class="group bg-surface rounded-2xl overflow-hidden shadow-sm hover:shadow-xl transition-all duration-500 h-full flex flex-col cursor-pointer border border-border-default/40"
              @click="navigateTo(localePath(`/blog/${post.slug}`))"
              itemscope
              itemtype="https://schema.org/BlogPosting"
            >
              <div class="relative aspect-[16/10] overflow-hidden">
                <img
                  v-if="post.cover_image"
                  :src="post.cover_image"
                  :alt="post.title"
                  class="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700"
                  loading="lazy"
                  itemprop="image"
                />
                <div v-else class="w-full h-full bg-gradient-to-br from-esmerald-light to-gray-100 flex items-center justify-center">
                  <svg class="w-10 h-10 text-esmerald/15" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" /></svg>
                </div>
                <div v-if="post.category" class="absolute top-4 left-4">
                  <span class="px-3 py-1.5 rounded-full text-xs backdrop-blur-md bg-surface/90 text-text-brand font-medium capitalize">
                    {{ formatCategory(post.category) }}
                  </span>
                </div>
              </div>

              <div class="p-6 flex-1 flex flex-col">
                <div class="flex items-center gap-4 mb-4 text-xs text-green-light">
                  <div v-if="post.published_at" class="flex items-center gap-1.5">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                    <time :datetime="post.published_at" itemprop="datePublished">{{ formatDate(post.published_at) }}</time>
                  </div>
                  <div v-if="post.read_time_minutes" class="flex items-center gap-1.5">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    <span>{{ post.read_time_minutes }} min</span>
                  </div>
                </div>

                <h3 class="text-xl font-light mb-3 group-hover:text-green-light transition-colors leading-tight text-text-brand" itemprop="headline">
                  <NuxtLink :to="localePath(`/blog/${post.slug}`)" @click.stop>{{ post.title }}</NuxtLink>
                </h3>

                <BaseRichTextContent class="text-base mb-6 flex-1 text-green-light leading-relaxed font-regular" itemprop="description" :source="post.excerpt" :format="post.text_formats?.['/excerpt_' + (locale === 'en-us' ? 'en' : 'es')] || 'plain'" />

                <div class="flex items-center gap-2 text-sm text-text-brand font-medium group-hover:gap-4 transition-all">
                  <span>{{ isEnglish ? 'Read more' : 'Leer más' }}</span>
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" /></svg>
                </div>
              </div>
            </article>
          </div>

          <!-- No Results -->
          <div v-if="filteredPosts.length === 0 && (searchQuery || selectedCategory)" class="text-center py-20">
            <p class="text-2xl mb-4 text-green-light font-regular">
              {{ isEnglish ? 'No articles match your criteria' : 'No encontramos artículos con esos criterios' }}
            </p>
            <button
              class="text-sm font-medium text-text-brand hover:opacity-60 transition-opacity"
              @click="searchQuery = ''; selectedCategory = ''"
            >
              {{ isEnglish ? 'Clear filters' : 'Limpiar filtros' }}
            </button>
          </div>

          <!-- Pagination -->
          <div v-if="totalPages > 1 && !searchQuery && !selectedCategory" class="flex items-center justify-center gap-2 pb-20 pt-4">
            <BaseButton
              unstyled
              icon-only
              :disabled="currentPage <= 1"
              :aria-label="isEnglish ? 'Previous page' : 'Página anterior'"
              class="px-4 py-2.5 rounded-full border-2 text-sm transition-all hover:scale-105 disabled:opacity-30 disabled:hover:scale-100"
              :class="currentPage <= 1 ? 'border-border-default text-text-subtle' : 'border-border-default text-text-brand hover:border-esmerald/40'"
              @click="goToPage(currentPage - 1)"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
            </BaseButton>
            <button
              v-for="p in paginationRange"
              :key="p"
              class="w-10 h-10 rounded-full text-sm font-medium transition-all hover:scale-105 border-2"
              :class="p === currentPage
                ? 'bg-primary text-white border-primary'
                : 'bg-surface text-green-light border-border-default hover:border-esmerald/40'"
              @click="goToPage(p)"
            >
              {{ p }}
            </button>
            <BaseButton
              unstyled
              icon-only
              :disabled="currentPage >= totalPages"
              :aria-label="isEnglish ? 'Next page' : 'Página siguiente'"
              class="px-4 py-2.5 rounded-full border-2 text-sm transition-all hover:scale-105 disabled:opacity-30 disabled:hover:scale-100"
              :class="currentPage >= totalPages ? 'border-border-default text-text-subtle' : 'border-border-default text-text-brand hover:border-esmerald/40'"
              @click="goToPage(currentPage + 1)"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
            </BaseButton>
          </div>
        </template>
      </div>
    </main>

    <!-- CTA Section -->
    <section class="py-14 sm:py-20 px-4 sm:px-6 bg-primary">
      <div class="max-w-4xl mx-auto text-center">
        <h2 class="text-3xl sm:text-4xl md:text-5xl font-light mb-6 tracking-tight text-white">
          {{ isEnglish ? 'Have a Project in Mind?' : '¿Tienes un Proyecto en Mente?' }}
        </h2>
        <p class="text-xl mb-10 text-white/70 leading-relaxed font-regular">
          {{ isEnglish
            ? 'Schedule a free consultation and discover how we can transform your digital presence.'
            : 'Agenda una consultoría gratuita y descubre cómo podemos transformar tu presencia digital.'
          }}
        </p>
        <div class="flex flex-col sm:flex-row gap-4 justify-center">
          <NuxtLink
            :to="localePath('/contact')"
            class="px-8 sm:px-10 py-4 sm:py-5 rounded-full flex items-center justify-center gap-3 transition-all hover:scale-105 bg-accent text-text-brand"
          >
            <span class="text-base sm:text-lg font-medium">{{ isEnglish ? 'Contact Us' : 'Contáctanos' }}</span>
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" /></svg>
          </NuxtLink>
        </div>
      </div>
    </section>

    <!-- Contact + Footer -->
    <ContactSection />
    <FooterSection />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import ContactSection from '~/components/sections/ContactSection.vue';
import FooterSection from '~/components/sections/FooterSection.vue';
import { useBlogStore } from '~/stores/blog';
import { fadeUp, staggerFadeUp } from '~/animations';
import { usePageEntrance } from '~/composables/usePageEntrance';
import { useBlogListJsonLd } from '~/composables/useSeoJsonLd';
import { formatDate as formatDateBase, formatDayMonth } from '~/utils/formatDate';

usePageEntrance();

const { locale } = useI18n();
const i18nHead = useLocaleHead({ addSeoAttributes: true });
const route = useRoute();
const localePath = useLocalePath();
const blogStore = useBlogStore();
const posts = computed(() => blogStore.posts);
const featured = computed(() => blogStore.featuredPost);
const isEnglish = computed(() => locale.value.startsWith('en'));
const blogLang = computed(() => isEnglish.value ? 'en' : 'es');
const baseUrl = 'https://projectapp.co';

const blogTitle = 'Blog — Project App.';
const blogDescription = computed(() => isEnglish.value
  ? 'Insights and trends in AI, software development, and digital transformation.'
  : 'Novedades y tendencias en IA, desarrollo de software y transformación digital.'
);

// Fetch the first page during SSR/prerender so the generated index carries the
// post list (real internal links for crawlers, not an empty client-side shell).
const runtimeConfig = useRuntimeConfig();
const { data: ssrPosts } = await useAsyncData(
  `blog-posts-${locale.value}`,
  () => {
    const base = import.meta.server ? runtimeConfig.apiInternalOrigin : '';
    return $fetch(`${base}/api/blog/?lang=${isEnglish.value ? 'en' : 'es'}&page=1&page_size=6`);
  },
);

if (ssrPosts.value && !blogStore.posts.length) {
  blogStore.posts = ssrPosts.value.results || ssrPosts.value;
  blogStore.pagination = {
    count: ssrPosts.value.count || blogStore.posts.length,
    page: ssrPosts.value.page || 1,
    pageSize: ssrPosts.value.page_size || 6,
    totalPages: ssrPosts.value.total_pages || 1,
  };
}

useHead({
  title: blogTitle,
  meta: [
    { name: 'description', content: blogDescription },
    { name: 'keywords', content: computed(() => isEnglish.value
      ? 'Project App. blog, software development, AI, digital transformation, web design, mobile apps, tech insights'
      : 'Project App. blog, desarrollo de software, IA, transformación digital, diseño web, apps móviles, tecnología'
    )},
    { property: 'og:title', content: blogTitle },
    { property: 'og:description', content: blogDescription },
    { property: 'og:type', content: 'website' },
    { property: 'og:url', content: computed(() => `${baseUrl}${route.fullPath}`) },
    { property: 'og:image', content: `${baseUrl}/img/og-image.webp` },
    { property: 'og:site_name', content: 'Project App.' },
    { property: 'og:locale', content: computed(() => locale.value === 'es-co' ? 'es_CO' : 'en_US') },
    { name: 'twitter:card', content: 'summary_large_image' },
    { name: 'twitter:site', content: '@projectappco' },
    { name: 'twitter:title', content: blogTitle },
    { name: 'twitter:description', content: blogDescription },
    { name: 'twitter:image', content: `${baseUrl}/img/og-image.webp` },
  ],
  htmlAttrs: {
    lang: i18nHead.value.htmlAttrs?.lang,
  },
  link: [
    { rel: 'canonical', href: computed(() => `${baseUrl}${route.fullPath}`) },
    ...(i18nHead.value.link || []),
  ],
});

watch(posts, (newPosts) => {
  if (newPosts && newPosts.length > 0) {
    useBlogListJsonLd(newPosts, locale.value);
  }
}, { immediate: true });

const searchQuery = ref('');
const selectedCategory = ref('');

const availableCategories = computed(() => blogStore.categories);

const filteredPosts = computed(() => {
  const others = blogStore.otherPosts;
  return others.filter((post) => {
    const matchesCategory = !selectedCategory.value || post.category === selectedCategory.value;
    const q = searchQuery.value.toLowerCase();
    const matchesSearch = !q
      || (post.title || '').toLowerCase().includes(q)
      || (post.excerpt || '').toLowerCase().includes(q);
    return matchesCategory && matchesSearch;
  });
});

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

const currentPage = computed(() => blogStore.pagination.page);
const totalPages = computed(() => blogStore.pagination.totalPages);

const paginationRange = computed(() => {
  const total = totalPages.value;
  const current = currentPage.value;
  const pages = [];
  const start = Math.max(1, current - 2);
  const end = Math.min(total, current + 2);
  for (let i = start; i <= end; i++) pages.push(i);
  return pages;
});

function goToPage(page) {
  if (page < 1 || page > totalPages.value) return;
  blogStore.fetchPosts(blogLang.value, page, 6);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

const heroSection = ref(null);
const filtersRow = ref(null);
const featuredCard = ref(null);
const postsGrid = ref(null);

function runHeroAnimations() {
  if (heroSection.value) {
    const title = heroSection.value.querySelector('#blog-title');
    const subtitle = heroSection.value.querySelector('p');
    if (title) fadeUp(title, { delay: 0.1 });
    if (subtitle) fadeUp(subtitle, { delay: 0.25 });
  }
  if (filtersRow.value) fadeUp(filtersRow.value, { delay: 0.4 });
}

function runPostAnimations() {
  nextTick(() => {
    if (featuredCard.value) fadeUp(featuredCard.value, { delay: 0.1 });
    if (postsGrid.value) {
      const cards = postsGrid.value.querySelectorAll('article');
      if (cards.length) staggerFadeUp(Array.from(cards), { delay: 0.15 });
    }
  });
}

onMounted(() => {
  // The SSR payload covers first paint and crawlers; refetch unconditionally
  // so visitors see posts published after the last prerender snapshot.
  blogStore.fetchPosts(blogLang.value);
  runHeroAnimations();
});

watch(posts, () => { runPostAnimations(); });

function formatDate(dateStr) {
  return formatDateBase(dateStr, { locale: isEnglish.value ? 'en' : 'es', fallback: '' });
}

function formatDateShort(dateStr) {
  return formatDayMonth(dateStr, { locale: isEnglish.value ? 'en' : 'es' });
}
</script>

<style scoped>
.scrollbar-hide::-webkit-scrollbar { display: none; }
.scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
</style>
