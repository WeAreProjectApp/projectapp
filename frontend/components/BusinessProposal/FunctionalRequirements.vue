<template>
  <section ref="sectionRef" class="functional-requirements min-h-screen w-full bg-surface flex items-center">
    <div class="w-full px-6 md:px-12 lg:px-24 py-12 md:py-6">
      <div class="max-w-5xl mx-auto">
        <div data-animate="fade-up" class="flex items-baseline gap-4 mb-10">
          <span class="text-text-muted font-light tracking-[0.25em] text-xs md:text-sm">
            {{ data.index }}
          </span>
          <h2 class="text-text-brand font-light leading-tight text-4xl md:text-6xl">
            {{ data.title }}
          </h2>
        </div>

        <div data-animate="fade-up" class="requirements-intro mb-12">
          <p
            class="text-text-default/80 font-light leading-relaxed text-lg md:text-xl"
            v-html="linkify(data.intro)"
          />
        </div>

        <!-- Overview: clickable group cards that open detail modal -->
        <div v-if="allGroups.length" data-animate="fade-up-stagger" class="overview-grid grid md:grid-cols-2 gap-6">
          <div v-for="group in allGroups" :key="group.id || group.title"
               class="overview-card group p-6 rounded-2xl border-2 cursor-pointer transition-all"
               :class="isGroupDeselected(group)
                 ? 'bg-surface-muted border-border-default opacity-50'
                 : 'bg-esmerald/5 border-esmerald/10 hover:border-esmerald/30'"
               @click="openModal(group)">
            <div class="flex items-center gap-3 mb-3">
              <div class="w-10 h-10 rounded-xl flex items-center justify-center bg-primary-soft group-hover:scale-110 transition-transform">
                <span class="text-xl">{{ group.icon || '🧩' }}</span>
              </div>
              <h3 class="text-lg font-medium text-text-brand">{{ group.title }}</h3>
              <span v-if="isGroupDeselected(group)" class="ml-auto text-[10px] font-medium text-text-subtle bg-surface-raised border border-border-default px-2 py-0.5 rounded-full whitespace-nowrap">
                No incluido
              </span>
              <span v-else-if="group.items?.length" class="ml-auto badge-count text-xs font-bold text-white bg-esmerald/70 px-2.5 py-1 rounded-full group-hover:bg-primary group-hover:scale-110 transition-all" style="color: white">
                {{ group.items.length }}
              </span>
            </div>
            <p class="text-sm text-text-default/70 font-light leading-relaxed mb-3" v-html="linkify(group.description)" />
            <span class="inline-flex items-center gap-1 text-xs font-semibold text-green-light group-hover:text-text-brand transition-colors">
              {{ t.viewDetail }}
              <svg class="w-3.5 h-3.5 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
              </svg>
            </span>
          </div>
        </div>
      </div>
    </div>

    <FunctionalRequirementsModal
      :visible="modalVisible"
      :group="selectedGroup"
      :item-requirements-map="itemRequirementsMap"
      :language="language"
      @close="modalVisible = false"
    />
  </section>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useSectionAnimations } from '~/composables/useSectionAnimations';
import { linkify } from '~/composables/useLinkify';
import { trackRequirementClick } from '~/utils/trackRequirementClick';
import FunctionalRequirementsModal from './FunctionalRequirementsModal.vue';

const sectionRef = ref(null);
useSectionAnimations(sectionRef);

const props = defineProps({
  data: {
    type: Object,
    default: () => ({
      index: '7',
      title: 'Requerimientos funcionales',
      intro: 'A continuación se detallan los requerimientos funcionales del proyecto.',
      groups: [],
      additionalModules: [],
    })
  },
  language: {
    type: String,
    default: 'es',
  },
  selectedCalculatorModules: {
    type: Array,
    default: () => [],
  },
  currency: {
    type: String,
    default: 'COP',
  },
  proposalUuid: {
    type: String,
    default: '',
  },
  valueAddedModuleIds: {
    type: Array,
    default: () => [],
  },
  itemRequirementsMap: {
    type: Object,
    default: () => ({}),
  },
});

const i18n = {
  es: { viewDetail: 'Ver detalle' },
  en: { viewDetail: 'View details' },
};
const t = computed(() => i18n[props.language] || i18n.es);

const data = props.data;

const allGroups = computed(() => {
  const groups = data.groups || [];
  const additional = data.additionalModules || [];
  const all = [...groups, ...additional].filter(g => g && g.is_visible !== false && (g.title || g.items?.length));
  // Modules already showcased in the value_added_modules section are hidden here
  // to avoid visual duplication; their canonical data stays in groups[] as catalog.
  const hidden = new Set(props.valueAddedModuleIds);
  return all.filter(g => {
    if (hidden.has(g.id)) return false;
    // Calculator modules: hide entirely when deselected (existing behavior)
    if (g.is_calculator_module) {
      return props.selectedCalculatorModules.includes(`module-${g.id}`);
    }
    // Regular groups: always show (dimmed when deselected)
    return true;
  });
});

// Check if a regular group is deselected (dimmed display)
function isGroupDeselected(group) {
  if (group.is_calculator_module) return false;
  if (group.is_always_included !== false) return false;
  const groupId = `group-${group.id}`;
  return props.selectedCalculatorModules.length > 0 && !props.selectedCalculatorModules.includes(groupId);
}

const modalVisible = ref(false);
const selectedGroup = ref({});

function openModal(group) {
  selectedGroup.value = group;
  modalVisible.value = true;
  trackRequirementClick(props.proposalUuid, group);
}
</script>

<style scoped>
.overview-card {
  transition: all 0.3s ease;
}

.overview-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 24px rgba(16, 185, 129, 0.12);
}

.badge-count {
  animation: badge-pulse 2s ease-in-out 0.5s 2;
}

@keyframes badge-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.2); }
}
</style>
