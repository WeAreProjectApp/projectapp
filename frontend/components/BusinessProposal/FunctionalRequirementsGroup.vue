<template>
  <section ref="sectionRef" class="fr-group min-h-screen w-full bg-surface py-16">
    <div class="w-full px-6 md:px-12 lg:px-24">
      <div class="max-w-5xl mx-auto">
        <!-- Sub-section number + title -->
        <div data-animate="fade-up" class="flex items-baseline gap-4 mb-10">
          <span class="text-text-muted font-light tracking-[0.25em] text-xs md:text-sm">
            {{ subIndex }}
          </span>
          <div class="flex items-center gap-3">
            <div class="w-12 h-12 rounded-xl flex items-center justify-center bg-primary-soft">
              <span class="text-2xl">{{ group.icon || '🧩' }}</span>
            </div>
            <h2 class="text-text-brand font-light leading-tight text-3xl md:text-5xl">
              {{ group.title }}
            </h2>
          </div>
        </div>

        <!-- Description -->
        <div data-animate="fade-up" class="mb-10">
          <div
            class="text-text-default/80 font-light leading-relaxed text-lg md:text-xl"
            v-html="linkify(group.description, group.text_formats?.['/description'])"
          />
        </div>

        <!-- Items grid -->
        <div v-if="group.items && group.items.length" data-animate="fade-up-stagger"
             class="requirements-grid grid md:grid-cols-2 gap-4">
          <div v-for="(item, idx) in group.items" :key="idx"
               class="requirement-card bg-esmerald/5 p-5 rounded-xl hover:bg-primary-soft transition-colors border border-esmerald/10 hover:border-esmerald/20">
            <div class="flex items-start">
              <div class="w-9 h-9 rounded-lg bg-primary-soft border border-esmerald/10 flex items-center justify-center mr-3 flex-shrink-0">
                <span class="text-lg">{{ item.icon || '✅' }}</span>
              </div>
              <div>
                <h4 class="font-bold text-text-brand mb-1">{{ item.name }}</h4>
                <BaseRichTextContent class="text-sm text-text-default/70 font-light" :source="item.description" :format="item.text_formats?.['/description'] || 'plain'" />
              </div>
            </div>
          </div>
        </div>
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
  group: {
    type: Object,
    default: () => ({
      id: '',
      icon: '🧩',
      title: '',
      description: '',
      items: [],
    })
  },
  subIndex: {
    type: String,
    default: '7.1',
  },
});

</script>

<style scoped>
.requirement-card {
  transition: all 0.3s ease;
}

.requirement-card:hover {
  transform: translateX(4px);
}
</style>
