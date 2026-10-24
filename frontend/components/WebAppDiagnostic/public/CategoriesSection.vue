<template>
  <section>
    <SectionHeader :index="content.index" :title="content.title" fallback="Categorías evaluadas" />
    <BaseRichTextContent v-if="content.intro" class="text-text-brand/80 dark:text-text-brand/80 mb-6" :source="content.intro" :format="content.text_formats?.['/intro'] || 'plain'" />

    <div class="space-y-3">
      <details
        v-for="(cat, idx) in content.categories"
        :key="cat.key || idx"
        class="group border-2 border-input-border rounded-2xl bg-primary/5 dark:bg-primary-soft hover:border-input-border dark:hover:border-input-border transition-all"
      >
        <summary class="px-6 py-5 cursor-pointer select-none flex items-center justify-between">
          <span class="font-semibold text-text-brand dark:text-text-brand text-base">
            <span class="text-text-brand/50 dark:text-text-brand/50 mr-2 font-mono text-sm">{{ idx + 1 }}.</span>
            {{ cat.title }}
          </span>
          <span class="text-xs text-text-brand/60 dark:text-text-brand/60 flex gap-2 items-center">
            <span v-if="cat.findings?.length" class="font-bold text-white dark:text-text-brand bg-primary/70 dark:bg-accent-soft px-2.5 py-1 rounded-full">
              {{ cat.findings.length }} hallazgo(s)
            </span>
            <svg class="w-4 h-4 transition-transform group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </span>
        </summary>
        <div class="px-6 pb-6 border-t border-input-border bg-surface/50 dark:bg-primary-soft space-y-4 text-sm">
          <BaseRichTextContent v-if="cat.description" class="text-text-brand/70 dark:text-text-brand/70 leading-relaxed pt-3" :source="cat.description" :format="cat.text_formats?.['/description'] || 'plain'" />

          <div v-if="cat.strengths?.length">
            <h4 class="font-semibold text-text-brand dark:text-text-brand mb-1">Lo que se encontró bien</h4>
            <ul class="list-disc pl-5 space-y-1 text-text-brand/80 dark:text-text-brand/80">
              <li v-for="(s, si) in cat.strengths" :key="si"><BaseRichTextContent :source="s" :format="cat.text_formats?.['/strengths/' + si] || 'plain'" /></li>
            </ul>
          </div>

          <div v-if="cat.findings?.length">
            <h4 class="font-semibold text-rose-700 dark:text-rose-300 mb-1">Hallazgos</h4>
            <ul class="space-y-2">
              <li v-for="(f, fi) in cat.findings" :key="fi" class="flex gap-2 items-start">
                <span
                  class="shrink-0 px-2 py-0.5 text-[10px] font-semibold uppercase rounded-full"
                  :class="levelClass(f.level)"
                >{{ f.level }}</span>
                <div>
                  <div class="font-medium text-text-brand dark:text-text-brand">{{ f.title }}</div>
                  <BaseRichTextContent v-if="f.detail" class="text-text-brand/70 dark:text-text-brand/70" :source="f.detail" :format="f.text_formats?.['/detail'] || 'plain'" />
                </div>
              </li>
            </ul>
          </div>

          <div v-if="cat.recommendations?.length">
            <h4 class="font-semibold text-indigo-700 dark:text-indigo-300 mb-1">Recomendaciones</h4>
            <ul class="space-y-2">
              <li v-for="(r, ri) in cat.recommendations" :key="ri" class="flex gap-2 items-start">
                <span
                  class="shrink-0 px-2 py-0.5 text-[10px] font-semibold uppercase rounded-full"
                  :class="levelClass(r.level)"
                >{{ r.level }}</span>
                <div>
                  <div class="font-medium text-text-brand dark:text-text-brand">{{ r.title }}</div>
                  <BaseRichTextContent v-if="r.detail" class="text-text-brand/70 dark:text-text-brand/70" :source="r.detail" :format="r.text_formats?.['/detail'] || 'plain'" />
                </div>
              </li>
            </ul>
          </div>

          <p v-if="!cat.strengths?.length && !cat.findings?.length && !cat.recommendations?.length"
             class="text-text-brand/45 dark:text-text-brand/45 italic text-xs pt-2">
            Hallazgos y recomendaciones se completarán durante el diagnóstico.
          </p>
        </div>
      </details>
    </div>
  </section>
</template>

<script setup>
import BaseRichTextContent from '~/components/base/BaseRichTextContent.vue';
import SectionHeader from './SectionHeader.vue';
import { severityLevelClass as levelClass } from '~/stores/diagnostics_constants';

defineProps({ content: { type: Object, required: true } });
</script>
