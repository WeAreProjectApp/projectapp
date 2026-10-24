<template>
  <div class="min-h-screen bg-primary-soft" itemscope itemtype="https://schema.org/CreativeWork">
    <!-- Loading -->
    <div v-if="portfolioStore.isLoading" class="flex items-center justify-center min-h-screen">
      <div class="w-8 h-8 border-2 border-esmerald/30 border-t-esmerald rounded-full animate-spin" />
    </div>

    <!-- Not found -->
    <div v-else-if="portfolioStore.error === 'not_found'" class="min-h-screen flex items-center justify-center px-6">
      <div class="text-center">
        <h1 class="text-4xl font-light text-text-brand mb-4">
          {{ isEnglish ? 'Project not found' : 'Proyecto no encontrado' }}
        </h1>
        <NuxtLink :to="localePath('/portfolio-works')" class="inline-flex items-center gap-2 px-8 py-4 rounded-full transition-all hover:scale-105 bg-primary text-white">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
          {{ isEnglish ? 'Back to portfolio' : 'Volver al portafolio' }}
        </NuxtLink>
      </div>
    </div>

    <!-- Work detail -->
    <template v-else-if="work">
      <article class="slide-up-enter">
        <!-- Back button -->
        <div class="pt-24 sm:pt-28 pb-6 sm:pb-8 px-4 sm:px-6">
          <div class="max-w-4xl mx-auto">
            <NuxtLink :to="localePath('/portfolio-works')" class="inline-flex items-center gap-2 text-sm font-regular text-green-light hover:text-text-brand transition-colors">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
              {{ isEnglish ? 'All projects' : 'Todos los proyectos' }}
            </NuxtLink>
          </div>
        </div>

        <!-- Title + Excerpt + Share (above the image) -->
        <header ref="titleSection" class="px-4 sm:px-6 pb-8 sm:pb-12">
          <div class="max-w-4xl mx-auto text-center">
            <h1 data-enter class="text-3xl sm:text-5xl md:text-6xl lg:text-7xl font-light mb-6 sm:mb-8 tracking-tight leading-[1.05] text-text-brand" itemprop="name">
              {{ work.title }}
            </h1>
            <p v-if="work.excerpt" data-enter class="text-lg sm:text-xl md:text-2xl max-w-3xl mx-auto text-green-light leading-relaxed font-regular mb-8 sm:mb-10" itemprop="description">
              {{ work.excerpt }}
            </p>
            <div data-enter class="flex items-center justify-center gap-3">
              <button class="px-5 sm:px-6 py-2.5 sm:py-3 rounded-full flex items-center gap-2 transition-all hover:scale-105 border-2 border-border-default text-text-brand" @click="handleShare">
                <svg class="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" /></svg>
                <span class="text-sm font-regular">{{ isEnglish ? 'Share' : 'Compartir' }}</span>
              </button>
              <a
                v-if="work.project_url"
                :href="work.project_url"
                target="_blank"
                rel="noopener noreferrer"
                class="px-5 sm:px-6 py-2.5 sm:py-3 rounded-full flex items-center gap-2 transition-all hover:scale-105 bg-primary text-white"
              >
                <svg class="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                <span class="text-sm font-medium">{{ isEnglish ? 'Visit Site' : 'Visitar Sitio' }}</span>
              </a>
            </div>
          </div>
        </header>

        <!-- Cover image (styled like blog post) -->
        <div v-if="work.cover_image" class="px-4 sm:px-6 mb-10 sm:mb-16">
          <figure class="max-w-6xl mx-auto">
            <div class="relative aspect-[16/9] sm:aspect-[21/9] rounded-2xl sm:rounded-3xl overflow-hidden shadow-2xl">
              <img :src="work.cover_image" :alt="work.title" class="w-full h-full object-cover" loading="eager" itemprop="image" />
            </div>
          </figure>
        </div>

        <!-- Content sections -->
        <div class="px-4 sm:px-6 pb-32">
          <div class="max-w-4xl mx-auto space-y-16 sm:space-y-24">
            <!-- Problem -->
            <section v-if="cJson?.problem" id="problem" class="scroll-mt-24">
              <div class="flex items-center gap-3 mb-6">
                <span class="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center text-red-600 flex-shrink-0">
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" /></svg>
                </span>
                <h2 class="text-3xl sm:text-4xl font-light text-text-brand">
                  {{ cJson.problem.title || (isEnglish ? 'The Challenge' : 'El Desafío') }}
                </h2>
              </div>
              <BaseRichTextContent class="text-lg text-green-light leading-relaxed font-regular mb-6" :source="cJson.problem.description" :format="cJson.problem.text_formats?.['/description'] || 'plain'" />
              <ul v-if="cJson.problem.highlights?.length" class="space-y-3">
                <li v-for="(item, idx) in cJson.problem.highlights" :key="idx" class="flex items-start gap-3">
                  <svg class="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4" /></svg>
                  <BaseRichTextContent class="text-base text-green-light font-regular" :source="item" :format="cJson.problem.text_formats?.['/highlights/' + idx] || 'plain'" />
                </li>
              </ul>
            </section>

            <!-- Solution -->
            <section v-if="cJson?.solution" id="solution" class="scroll-mt-24">
              <div class="flex items-center gap-3 mb-6">
                <span class="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 flex-shrink-0">
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
                </span>
                <h2 class="text-3xl sm:text-4xl font-light text-text-brand">
                  {{ cJson.solution.title || (isEnglish ? 'Our Solution' : 'Nuestra Solución') }}
                </h2>
              </div>
              <BaseRichTextContent class="text-lg text-green-light leading-relaxed font-regular mb-6" :source="cJson.solution.description" :format="cJson.solution.text_formats?.['/description'] || 'plain'" />
              <ul v-if="cJson.solution.highlights?.length" class="space-y-3">
                <li v-for="(item, idx) in cJson.solution.highlights" :key="idx" class="flex items-start gap-3">
                  <svg class="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4" /></svg>
                  <BaseRichTextContent class="text-base text-green-light font-regular" :source="item" :format="cJson.solution.text_formats?.['/highlights/' + idx] || 'plain'" />
                </li>
              </ul>
            </section>

            <!-- Results -->
            <section v-if="cJson?.results" id="results" class="scroll-mt-24">
              <div class="flex items-center gap-3 mb-6">
                <span class="w-10 h-10 rounded-full bg-primary-soft flex items-center justify-center text-text-brand flex-shrink-0">
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                </span>
                <h2 class="text-3xl sm:text-4xl font-light text-text-brand">
                  {{ cJson.results.title || (isEnglish ? 'The Results' : 'Los Resultados') }}
                </h2>
              </div>
              <BaseRichTextContent class="text-lg text-green-light leading-relaxed font-regular mb-6" :source="cJson.results.description" :format="cJson.results.text_formats?.['/description'] || 'plain'" />
              <ul v-if="cJson.results.highlights?.length" class="space-y-3 mb-8">
                <li v-for="(item, idx) in cJson.results.highlights" :key="idx" class="flex items-start gap-3">
                  <svg class="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4" /></svg>
                  <BaseRichTextContent class="text-base text-green-light font-regular" :source="item" :format="cJson.results.text_formats?.['/highlights/' + idx] || 'plain'" />
                </li>
              </ul>
              <!-- YouTube testimonial -->
              <div v-if="videoEmbedUrl" class="mt-8">
                <h3 class="text-xl font-light text-text-brand mb-4">{{ isEnglish ? 'Client Testimonial' : 'Testimonio del Cliente' }}</h3>
                <div class="relative aspect-video rounded-2xl overflow-hidden shadow-lg bg-black">
                  <iframe :src="videoEmbedUrl" class="absolute inset-0 w-full h-full" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen />
                </div>
              </div>
            </section>
          </div>
        </div>
      </article>

      <!-- CTA Section -->
      <section class="py-14 sm:py-20 px-4 sm:px-6 bg-primary">
        <div class="max-w-4xl mx-auto text-center">
          <h2 class="text-3xl sm:text-4xl md:text-5xl font-light mb-6 tracking-tight text-white">
            {{ isEnglish ? 'Ready to Build Something Like This?' : '¿Listo para Construir Algo Así?' }}
          </h2>
          <p class="text-xl mb-10 text-white/70 leading-relaxed font-regular">
            {{ isEnglish
              ? 'Schedule a free consultation and let\'s bring your project to life.'
              : 'Agenda una consultoría gratuita y hagamos realidad tu proyecto.'
            }}
          </p>
          <NuxtLink
            :to="localePath('/contact')"
            class="px-8 sm:px-10 py-4 sm:py-5 rounded-full inline-flex items-center justify-center gap-3 transition-all hover:scale-105 bg-accent text-text-brand"
          >
            <span class="text-base sm:text-lg font-medium">{{ isEnglish ? 'Get a Quote' : 'Cotizar tu Proyecto' }}</span>
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" /></svg>
          </NuxtLink>
        </div>
      </section>

      <!-- Footer -->
      <FooterSection />

      <!-- Sticky Awwwards bar — desktop only, hidden on mobile to not conflict with WhatsApp button -->
      <div class="hidden lg:block fixed bottom-6 left-1/2 -translate-x-1/2 z-40 w-auto">
        <div class="bg-primary-strong/95 backdrop-blur-md rounded-2xl shadow-2xl border border-white/10 px-3 sm:px-4 py-2.5 sm:py-3 flex items-center gap-2 sm:gap-3">
          <!-- Pr. logo circle -->
          <NuxtLink :to="localePath('/')" class="w-10 h-10 sm:w-11 sm:h-11 rounded-full bg-surface flex items-center justify-center flex-shrink-0 hover:scale-105 transition-transform">
            <span class="text-text-brand font-bold text-sm sm:text-base tracking-tight">Pr.</span>
          </NuxtLink>
          <!-- Nav buttons with border pills -->
          <button class="px-3 sm:px-4 py-1.5 sm:py-2 rounded-full border border-white/25 text-xs sm:text-sm font-medium text-white/90 hover:text-white hover:border-white/50 hover:bg-surface/10 transition-all" @click="scrollTo('problem')">
            {{ isEnglish ? 'Problem' : 'Problema' }}
          </button>
          <button class="px-3 sm:px-4 py-1.5 sm:py-2 rounded-full border border-white/25 text-xs sm:text-sm font-medium text-white/90 hover:text-white hover:border-white/50 hover:bg-surface/10 transition-all" @click="scrollTo('solution')">
            {{ isEnglish ? 'Solution' : 'Solución' }}
          </button>
          <button class="px-3 sm:px-4 py-1.5 sm:py-2 rounded-full border border-white/25 text-xs sm:text-sm font-medium text-white/90 hover:text-white hover:border-white/50 hover:bg-surface/10 transition-all" @click="scrollTo('results')">
            {{ isEnglish ? 'Result' : 'Resultado' }}
          </button>
          <!-- Visit Site lemon pill -->
          <a :href="work.project_url" target="_blank" rel="noopener noreferrer" class="px-4 sm:px-5 py-1.5 sm:py-2 rounded-full text-xs sm:text-sm font-medium bg-accent text-text-brand hover:bg-accent/90 transition-all">
            {{ isEnglish ? 'Visit Site' : 'Visitar Sitio' }}
          </a>
        </div>
      </div>

      <!-- JSON-LD -->
      <component :is="'script'" type="application/ld+json" v-html="jsonLdWork" />
      <component :is="'script'" v-if="jsonLdFaq" type="application/ld+json" v-html="jsonLdFaq" />
    </template>
  </div>
</template>

<script setup>
import { resolveEditorialContent } from '~/utils/editorialMetadata';
import BaseRichTextContent from '~/components/base/BaseRichTextContent.vue';
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import FooterSection from '~/components/sections/FooterSection.vue';
import { usePortfolioWorksStore } from '~/stores/portfolio_works';
import { fadeUp } from '~/animations';
import { usePageEntrance } from '~/composables/usePageEntrance';

usePageEntrance();

const route = useRoute();
const { locale } = useI18n();
const localePath = useLocalePath();
const portfolioStore = usePortfolioWorksStore();
const work = computed(() => portfolioStore.currentWork);
const isEnglish = computed(() => locale.value.startsWith('en'));
const portfolioLang = computed(() => isEnglish.value ? 'en' : 'es');
const cJson = computed(() => work.value?.content_json ? resolveEditorialContent(work.value.content_json, work.value.text_formats, '/content_json_' + (isEnglish.value ? 'en' : 'es')) : null);

const videoEmbedUrl = computed(() => {
  const url = cJson.value?.results?.testimonial_video_url;
  if (!url) return null;
  const yt = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]+)/);
  if (yt) return `https://www.youtube.com/embed/${yt[1]}`;
  if (url.includes('youtube.com/embed/')) return url;
  const vm = url.match(/vimeo\.com\/(\d+)/);
  if (vm) return `https://player.vimeo.com/video/${vm[1]}`;
  return url;
});

useHead({
  meta: [
    { name: 'description', content: computed(() => work.value?.meta_description || work.value?.excerpt || '') },
    { property: 'og:title', content: computed(() => work.value?.meta_title || work.value?.title || '') },
    { property: 'og:description', content: computed(() => work.value?.meta_description || work.value?.excerpt || '') },
    { property: 'og:image', content: computed(() => work.value?.cover_image || '') },
    { property: 'og:type', content: 'article' },
    { property: 'article:published_time', content: computed(() => work.value?.published_at || '') },
    { name: 'keywords', content: computed(() => work.value?.meta_keywords || '') },
  ],
  link: [
    { rel: 'canonical', href: computed(() => `https://projectapp.co/portfolio-works/${route.params.slug}`) },
  ],
});

const jsonLdWork = computed(() => {
  if (!work.value) return '';
  return JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'CreativeWork',
    name: work.value.title,
    description: work.value.excerpt || work.value.meta_description || '',
    image: work.value.cover_image || '',
    url: `https://projectapp.co/portfolio-works/${work.value.slug}`,
    datePublished: work.value.published_at || '',
    author: { '@type': 'Organization', name: 'Project App', url: 'https://projectapp.co' },
    creator: { '@type': 'Organization', name: 'Project App', url: 'https://projectapp.co' },
  });
});

const jsonLdFaq = computed(() => {
  if (!cJson.value?.problem || !cJson.value?.solution) return null;
  return JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
      {
        '@type': 'Question',
        name: cJson.value.problem.title || (isEnglish.value ? 'What was the challenge?' : '¿Cuál fue el desafío?'),
        acceptedAnswer: { '@type': 'Answer', text: cJson.value.problem.description || '' },
      },
      {
        '@type': 'Question',
        name: cJson.value.solution.title || (isEnglish.value ? 'What was the solution?' : '¿Cuál fue la solución?'),
        acceptedAnswer: { '@type': 'Answer', text: cJson.value.solution.description || '' },
      },
    ],
  });
});

const titleSection = ref(null);

function runAnimations() {
  nextTick(() => {
    if (titleSection.value) {
      const children = titleSection.value.querySelectorAll('h1, p, .flex');
      children.forEach((el, i) => fadeUp(el, { delay: 0.1 + i * 0.12 }));
    }
  });
}

function scrollTo(id) {
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function handleShare() {
  const url = window.location.href;
  if (navigator.share) {
    navigator.share({ title: work.value?.title || '', text: work.value?.excerpt || '', url });
  } else {
    navigator.clipboard.writeText(url);
  }
}

onMounted(async () => {
  await portfolioStore.fetchWork(route.params.slug, portfolioLang.value);
  runAnimations();
});

watch(() => route.params.slug, (newSlug) => {
  if (newSlug) {
    portfolioStore.fetchWork(newSlug, portfolioLang.value);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
});
</script>

<style scoped>
.slide-up-enter {
  animation: slideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
@keyframes slideUp {
  from { opacity: 0; transform: translateY(40px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
