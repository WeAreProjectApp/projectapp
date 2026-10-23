<template>
  <section ref="sectionRef" class="roi-projection min-h-screen py-16 md:py-24 bg-surface">
    <div class="container mx-auto px-6 md:px-12 lg:px-24 max-w-5xl">
      <div class="section-header mb-12">
        <div data-animate="fade-up" class="flex items-baseline gap-4 mb-10">
          <span class="text-text-muted font-light tracking-[0.25em] text-xs md:text-sm">
            {{ content.index }}
          </span>
          <h2 class="text-text-brand font-light leading-tight text-4xl md:text-6xl">
            {{ content.title }}
          </h2>
        </div>
        <div
          v-if="content.subtitle"
          data-animate="fade-up"
          class="text-text-default/70 font-light text-lg md:text-xl leading-relaxed"
          v-html="linkify(content.subtitle, content.text_formats?.['/subtitle'])"
        />
      </div>

      <!-- KPI cards -->
      <div
        v-if="kpis.length"
        data-animate="fade-up"
        class="grid sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-16"
      >
        <div
          v-for="(kpi, idx) in kpis"
          :key="idx"
          class="roi-kpi-card bg-primary-soft border border-border-default rounded-2xl p-6 hover:border-text-brand/30 transition-all"
        >
          <div v-if="kpi.icon" class="text-3xl mb-3">{{ kpi.icon }}</div>
          <p class="text-2xl md:text-3xl font-bold text-text-brand mb-1 tabular-nums">{{ kpi.value }}</p>
          <p class="text-sm font-semibold text-text-brand mb-2">{{ kpi.label }}</p>
          <p v-if="kpi.sublabel" class="text-xs text-text-default/70 leading-relaxed mb-1">
            {{ kpi.sublabel }}
          </p>
          <p v-if="kpi.source" class="text-xs italic text-text-default/50 leading-relaxed">
            {{ kpi.source }}
          </p>
        </div>
      </div>

      <!-- Methodology — how the projections were built -->
      <div
        v-if="content.methodology"
        data-animate="fade-up"
        class="bg-primary-soft border border-border-default rounded-2xl p-5 md:p-6 mb-8 flex gap-3"
      >
        <span class="text-xl md:text-2xl shrink-0 leading-none mt-0.5">🧮</span>
        <div
          class="text-sm md:text-base text-text-default/80 font-light leading-relaxed"
          v-html="linkify(content.methodology, content.text_formats?.['/methodology'])"
        />
      </div>

      <!-- Scenarios -->
      <div v-if="scenarios.length" data-animate="fade-up" class="mb-12">
        <h3
          v-if="content.scenariosTitle"
          class="text-text-brand font-light text-2xl md:text-3xl mb-6"
        >
          {{ content.scenariosTitle }}
        </h3>
        <div class="grid md:grid-cols-3 gap-5">
          <div
            v-for="(scenario, idx) in scenarios"
            :key="idx"
            class="scenario-card bg-surface border border-border-default rounded-2xl p-6"
          >
            <div class="flex items-center gap-2 mb-4 pb-3 border-b border-border-default">
              <span v-if="scenario.icon" class="text-xl">{{ scenario.icon }}</span>
              <h4 class="font-bold text-text-brand text-lg">{{ scenario.label || scenario.name }}</h4>
            </div>
            <ul
              v-if="(scenario.assumptions || []).length"
              class="space-y-1 mb-4"
            >
              <li
                v-for="(assumption, aIdx) in scenario.assumptions"
                :key="'a-' + aIdx"
                class="text-xs text-text-default/70 leading-snug flex gap-1.5"
              >
                <span class="text-text-brand/60 shrink-0">·</span>
                <span>{{ assumption }}</span>
              </li>
            </ul>
            <ul class="space-y-2">
              <li
                v-for="(metric, mIdx) in (scenario.metrics || [])"
                :key="mIdx"
                :class="metric.emphasis ? 'pt-2 border-t border-border-default mt-2' : ''"
              >
                <div class="flex items-baseline justify-between gap-3">
                  <span
                    class="text-xs text-text-default/70 leading-tight"
                    :class="metric.emphasis ? 'font-semibold text-text-brand' : ''"
                  >
                    {{ metric.label }}
                  </span>
                  <span
                    class="text-sm font-bold text-text-brand tabular-nums whitespace-nowrap"
                    :class="metric.emphasis ? 'text-base' : ''"
                  >
                    {{ metric.value }}
                  </span>
                </div>
                <p
                  v-if="metric.basis"
                  class="text-[11px] italic text-text-default/50 leading-tight mt-0.5"
                >
                  {{ metric.basis }}
                </p>
              </li>
            </ul>
          </div>
        </div>
      </div>

      <!-- CTA note -->
      <div
        v-if="content.ctaNote"
        data-animate="fade-up"
        class="bg-primary p-6 md:p-8 rounded-2xl"
      >
        <div
          class="text-on-primary font-light leading-relaxed text-base md:text-lg"
          v-html="linkify(content.ctaNote, content.text_formats?.['/ctaNote'])"
        />
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useSectionAnimations } from '~/composables/useSectionAnimations';
import { linkify } from '~/composables/useLinkify';

const sectionRef = ref(null);
useSectionAnimations(sectionRef);

const props = defineProps({
  text_formats: { type: Object, default: () => ({}) },
  content: { type: Object, default: () => ({}) },
});

const kpis = computed(() => Array.isArray(props.content?.kpis) ? props.content.kpis : []);
const scenarios = computed(() => Array.isArray(props.content?.scenarios) ? props.content.scenarios : []);
</script>

<style scoped>
.roi-kpi-card {
  transition: all 0.3s ease;
}
.roi-kpi-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
}
</style>
