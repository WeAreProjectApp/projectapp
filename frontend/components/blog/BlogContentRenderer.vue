<template>
  <div v-if="hasJsonContent" class="blog-json-content">
    <!-- Introduction -->
    <BaseRichTextContent class="text-xl mb-12 text-text-brand/80 dark:text-white/80 leading-relaxed font-regular" :source="contentJson.intro" :format="contentJson.text_formats?.['/intro'] || 'plain'" />

    <!-- Sections -->
    <div v-for="(section, index) in contentJson.sections" :key="index" class="mb-16">
      <h2 class="text-2xl md:text-3xl lg:text-4xl font-light mb-6 tracking-tight text-text-brand dark:text-white">
        {{ section.heading }}
      </h2>

      <BaseRichTextContent v-if="section.content" class="text-lg mb-6 text-green-light dark:text-green-light/80 leading-relaxed font-regular" :source="section.content" :format="section.text_formats?.['/content'] || 'plain'" />

      <!-- List with check icons -->
      <ul v-if="section.list && section.list.length" class="space-y-4 mb-6">
        <li v-for="(item, i) in section.list" :key="i" class="flex items-start gap-3">
          <svg class="w-6 h-6 flex-shrink-0 mt-1 text-text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
          <BaseRichTextContent class="text-lg text-green-light dark:text-green-light/80 leading-relaxed font-regular" :source="item" :format="section.text_formats?.['/list/' + i] || 'plain'" />
        </li>
      </ul>

      <!-- Subsections as cards -->
      <div v-if="section.subsections && section.subsections.length" class="space-y-4 sm:space-y-6">
        <div
          v-for="(sub, i) in section.subsections"
          :key="i"
          class="bg-primary-soft rounded-2xl p-5 sm:p-8 border border-border-default"
        >
          <h3 class="text-xl font-medium mb-3 text-text-brand dark:text-white">{{ sub.title }}</h3>
          <BaseRichTextContent class="text-base text-green-light dark:text-green-light/80 leading-relaxed font-regular" :source="sub.description" :format="sub.text_formats?.['/description'] || 'plain'" />
        </div>
      </div>

      <!-- Timeline with numbered steps -->
      <div v-if="section.timeline && section.timeline.length" class="space-y-4">
        <div v-for="(item, i) in section.timeline" :key="i" class="flex gap-6">
          <div class="flex flex-col items-center">
            <div class="w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0 bg-primary-soft">
              <span class="text-lg font-bold text-text-brand dark:text-white">{{ i + 1 }}</span>
            </div>
            <div v-if="i < section.timeline.length - 1" class="w-0.5 h-full mt-2 bg-border-muted" />
          </div>
          <div class="pb-8">
            <h4 class="text-lg font-medium mb-2 text-text-brand dark:text-white">{{ item.step }}</h4>
            <BaseRichTextContent class="text-base text-green-light dark:text-green-light/80 leading-relaxed font-regular" :source="item.description" :format="item.text_formats?.['/description'] || 'plain'" />
          </div>
        </div>
      </div>

      <!-- Examples as grid cards -->
      <div v-if="section.examples && section.examples.length" class="grid md:grid-cols-2 gap-4">
        <div
          v-for="(example, i) in section.examples"
          :key="i"
          class="bg-primary-soft rounded-xl p-6"
        >
          <BaseRichTextContent class="text-base font-regular text-text-brand dark:text-white/80 leading-relaxed" :source="example" :format="section.text_formats?.['/examples/' + i] || 'plain'" />
        </div>
      </div>

      <!-- Inline image with credit -->
      <figure v-if="section.image && section.image.url" class="my-8">
        <div class="rounded-2xl overflow-hidden shadow-lg">
          <img
            :src="section.image.url"
            :alt="section.image.alt || section.heading"
            class="w-full h-auto object-cover"
            loading="lazy"
          />
        </div>
        <figcaption v-if="section.image.credit" class="mt-3 text-center text-sm text-green-light/70 font-regular">
          <a
            v-if="section.image.credit_url"
            :href="section.image.credit_url"
            target="_blank"
            rel="noopener noreferrer"
            class="hover:text-text-brand transition-colors"
          >
            {{ section.image.credit }}
          </a>
          <span v-else>{{ section.image.credit }}</span>
        </figcaption>
      </figure>

      <!-- Quote -->
      <blockquote v-if="section.quote && section.quote.text" class="my-8 pl-6 border-l-4 border-lemon">
        <p class="text-xl italic text-text-brand dark:text-white/90 leading-relaxed font-regular mb-3">
          "{{ section.quote.text }}"
        </p>
        <cite v-if="section.quote.author" class="text-sm text-green-light font-regular not-italic">
          — {{ section.quote.author }}
        </cite>
      </blockquote>

      <!-- Callout (tip / warning / info / note) -->
      <div
        v-if="section.callout && section.callout.text"
        class="my-8 rounded-2xl p-5 sm:p-8 border"
        :class="calloutClasses(section.callout.type)"
      >
        <div class="flex items-start gap-3">
          <span class="text-xl flex-shrink-0 mt-0.5" aria-hidden="true">{{ calloutIcon(section.callout.type) }}</span>
          <div>
            <p v-if="section.callout.title" class="font-medium mb-2 text-text-brand dark:text-white text-lg">{{ section.callout.title }}</p>
            <BaseRichTextContent class="text-base text-green-light dark:text-green-light/80 leading-relaxed font-regular" :source="section.callout.text" :format="section.callout.text_formats?.['/text'] || 'plain'" />
          </div>
        </div>
      </div>

      <!-- Video (YouTube / Vimeo embed) -->
      <div v-if="section.video && section.video.url" class="my-8">
        <div class="relative aspect-video rounded-2xl overflow-hidden shadow-lg bg-primary-strong">
          <iframe
            :src="videoEmbedUrl(section.video.url)"
            :title="section.video.title || section.heading"
            class="absolute inset-0 w-full h-full"
            frameborder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowfullscreen
            loading="lazy"
          />
        </div>
      </div>

      <!-- Key Takeaways (summary box — AI engines love structured summaries) -->
      <div v-if="section.key_takeaways && section.key_takeaways.length" class="my-8 bg-lemon/10 dark:bg-lemon/5 border-2 border-lemon/30 dark:border-lemon/20 rounded-2xl p-5 sm:p-8">
        <div class="flex items-center gap-2 mb-5">
          <span class="text-xl" aria-hidden="true">💡</span>
          <h3 class="text-lg font-medium text-text-brand dark:text-white">{{ section.heading }}</h3>
        </div>
        <ul class="space-y-3">
          <li v-for="(takeaway, i) in section.key_takeaways" :key="i" class="flex items-start gap-3">
            <span class="w-6 h-6 rounded-full bg-primary text-white text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">{{ i + 1 }}</span>
            <BaseRichTextContent class="text-base text-green-light dark:text-green-light/80 leading-relaxed font-regular" :source="takeaway" :format="section.text_formats?.['/key_takeaways/' + i] || 'plain'" />
          </li>
        </ul>
      </div>

      <!-- FAQ (Q&A pairs — maps to Google FAQ Schema) -->
      <div
        v-if="section.faq && section.faq.length"
        class="my-8 space-y-4"
        itemscope
        itemtype="https://schema.org/FAQPage"
      >
        <div
          v-for="(item, i) in section.faq"
          :key="i"
          class="bg-surface rounded-2xl border border-border-default overflow-hidden"
          itemscope
          itemprop="mainEntity"
          itemtype="https://schema.org/Question"
        >
          <details class="group">
            <summary class="flex items-center justify-between gap-4 px-5 sm:px-8 py-5 cursor-pointer select-none hover:bg-primary-soft transition-colors">
              <span class="text-base sm:text-lg font-medium text-text-brand dark:text-white leading-snug" itemprop="name">{{ item.question }}</span>
              <svg class="w-5 h-5 text-green-light flex-shrink-0 transition-transform group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
            </summary>
            <div class="px-5 sm:px-8 pb-5 sm:pb-8" itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
              <BaseRichTextContent class="text-base text-green-light dark:text-green-light/80 leading-relaxed font-regular" itemprop="text" :source="item.answer" :format="item.text_formats?.['/answer'] || 'plain'" />
            </div>
          </details>
        </div>
      </div>
    </div>

    <!-- Conclusion -->
    <div v-if="contentJson.conclusion" class="bg-primary rounded-2xl p-6 sm:p-10 mb-10 sm:mb-12">
      <BaseRichTextContent class="text-lg sm:text-xl mb-4 sm:mb-6 text-white/90 leading-relaxed font-regular" :source="contentJson.conclusion" :format="contentJson.text_formats?.['/conclusion'] || 'plain'" />
      <BaseRichTextContent v-if="contentJson.cta" class="text-lg text-white/60 leading-relaxed font-light" :source="contentJson.cta" :format="contentJson.text_formats?.['/cta'] || 'plain'" />
    </div>
  </div>

  <!-- Fallback: HTML content via v-html -->
  <BaseRichTextContent v-else-if="htmlContent && contentFormat !== 'plain'" :source="htmlContent" :format="contentFormat" class="blog-html-content" />
  <div v-else-if="htmlContent" class="blog-html-content" v-html="safeLegacyHtml" />
</template>

<script setup>
import BaseRichTextContent from '~/components/base/BaseRichTextContent.vue';
import { computed, ref, onMounted } from 'vue';
import DOMPurify from 'dompurify';

const props = defineProps({
  contentFormat: { type: String, default: 'plain' },
  contentJson: {
    type: Object,
    default: () => ({}),
  },
  htmlContent: {
    type: String,
    default: '',
  },
});

const mounted = ref(false);
onMounted(() => { mounted.value = true; });
const safeLegacyHtml = computed(() => mounted.value ? DOMPurify.sanitize(props.htmlContent) : '');

const hasJsonContent = computed(() => {
  return props.contentJson
    && typeof props.contentJson === 'object'
    && props.contentJson.intro
    && Array.isArray(props.contentJson.sections);
});

function calloutClasses(type) {
  const map = {
    tip: 'bg-success-soft border-success-strong/30',
    warning: 'bg-warning-soft border-warning-strong/30',
    info: 'bg-info-soft border-info-strong/30',
    note: 'bg-surface-muted border-border-default',
  };
  return map[type] || map.note;
}

function calloutIcon(type) {
  const map = { tip: '💡', warning: '⚠️', info: 'ℹ️', note: '📌' };
  return map[type] || map.note;
}

function videoEmbedUrl(url) {
  if (!url) return '';
  // YouTube
  const ytMatch = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]+)/);
  if (ytMatch) return `https://www.youtube.com/embed/${ytMatch[1]}`;
  // Vimeo
  const vimeoMatch = url.match(/vimeo\.com\/(\d+)/);
  if (vimeoMatch) return `https://player.vimeo.com/video/${vimeoMatch[1]}`;
  return url;
}
</script>

<style scoped>
.blog-html-content :deep(h2) {
  font-family: 'Ubuntu-Light', sans-serif;
  font-size: 1.75rem;
  color: #002921;
  margin-top: 2.5rem;
  margin-bottom: 1rem;
}

.blog-html-content :deep(h3) {
  font-family: 'Ubuntu-Regular', sans-serif;
  font-size: 1.25rem;
  color: #002921;
  margin-top: 2rem;
  margin-bottom: 0.75rem;
}

.blog-html-content :deep(p) {
  font-family: 'Ubuntu-Regular', sans-serif;
  color: #809490;
  line-height: 1.75;
  margin-bottom: 1rem;
}

.blog-html-content :deep(a) {
  color: #002921;
  text-decoration: underline;
}

.blog-html-content :deep(strong) {
  color: #002921;
  font-family: 'Ubuntu-Medium', sans-serif;
}

.blog-html-content :deep(ul),
.blog-html-content :deep(ol) {
  color: #809490;
  padding-left: 1.5rem;
  margin-bottom: 1rem;
}

.blog-html-content :deep(li) {
  margin-bottom: 0.5rem;
  font-family: 'Ubuntu-Regular', sans-serif;
}

.blog-html-content :deep(blockquote) {
  border-left: 3px solid #F0FF3D;
  padding-left: 1rem;
  color: #002921;
  font-style: italic;
  font-family: 'Ubuntu-Regular', sans-serif;
  margin: 1.5rem 0;
}

/* Dark mode overrides for HTML fallback content */
:global(.dark) .blog-html-content :deep(h2) { color: #ffffff; }
:global(.dark) .blog-html-content :deep(h3) { color: #ffffff; }
:global(.dark) .blog-html-content :deep(p) { color: #a0b8b2; }
:global(.dark) .blog-html-content :deep(a) { color: #6ee7b7; }
:global(.dark) .blog-html-content :deep(strong) { color: #ffffff; }
:global(.dark) .blog-html-content :deep(ul),
:global(.dark) .blog-html-content :deep(ol) { color: #a0b8b2; }
:global(.dark) .blog-html-content :deep(blockquote) { color: #ffffff; }
</style>
