<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="visible" class="fixed inset-0 z-[9999] flex items-center justify-center p-4 sm:p-6" :data-theme="isDark ? 'dark' : 'light'">
        <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="$emit('close')" />
        <div class="relative bg-surface rounded-2xl shadow-overlay border border-border-default w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-5 border-b border-border-muted">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-xl flex items-center justify-center bg-primary-soft">
                <span class="text-xl">{{ group.icon || '🧩' }}</span>
              </div>
              <h3 class="text-xl font-medium text-text-brand">{{ group.title }}</h3>
            </div>
            <BaseButton
              unstyled
              icon-only
              class="w-8 h-8 rounded-lg flex items-center justify-center text-text-subtle hover:text-text-default hover:bg-surface-raised transition-colors"
              :aria-label="language === 'en' ? 'Close requirements group' : 'Cerrar grupo de requerimientos'"
              @click="$emit('close')"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </BaseButton>
          </div>

          <!-- Body -->
          <div class="overflow-y-auto px-6 py-6 flex-1">
            <div
              v-if="group.description"
              class="text-text-default/80 font-light leading-relaxed text-base mb-8"
              v-html="linkify(group.description, group.text_formats?.['/description'])"
            />

            <div v-if="group.items && group.items.length" class="grid md:grid-cols-2 gap-4">
              <div v-for="(item, idx) in group.items" :key="idx"
                   class="requirement-card bg-surface-raised p-5 rounded-xl border border-border-default">
                <div class="flex items-start">
                  <div class="w-9 h-9 rounded-lg bg-primary-soft flex items-center justify-center mr-3 flex-shrink-0">
                    <span class="text-lg">{{ item.icon || '✅' }}</span>
                  </div>
                  <div>
                    <h4 class="font-bold text-text-brand mb-1">{{ item.name }}</h4>
                    <div class="text-sm text-text-default/70 font-light" v-html="linkify(item.description, item.text_formats?.['/description'])" />
                    <button
                      v-if="linkedRequirements(item).length"
                      type="button"
                      class="linked-req-link mt-2 inline-flex items-center gap-1 text-sm font-medium text-text-brand hover:underline"
                      data-testid="view-requirements-link"
                      @click="openRequirements(item)"
                    >
                      {{ viewRequirementsLabel(item) }}
                      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>

  <LinkedRequirementsModal
    :visible="!!activeItem"
    :item="activeItem || {}"
    :requirements="activeItem ? linkedRequirements(activeItem) : []"
    :language="language"
    @close="activeItem = null"
  />
</template>

<script setup>
import { ref, watch } from 'vue';
import { useProposalDarkMode } from '~/composables/useProposalDarkMode';
import { linkify } from '~/composables/useLinkify';
import LinkedRequirementsModal from '~/components/BusinessProposal/LinkedRequirementsModal.vue';

const { isDark } = useProposalDarkMode();

const props = defineProps({
  text_formats: { type: Object, default: () => ({}) },
  visible: {
    type: Boolean,
    default: false,
  },
  group: {
    type: Object,
    default: () => ({
      icon: '🧩',
      title: '',
      description: '',
      items: [],
    }),
  },
  itemRequirementsMap: {
    type: Object,
    default: () => ({}),
  },
  language: {
    type: String,
    default: 'es',
  },
});

defineEmits(['close']);

const activeItem = ref(null);

watch(() => props.visible, (open) => {
  if (!open) activeItem.value = null;
});

function linkedRequirements(item) {
  const itemId = typeof item?.id === 'string' ? item.id.trim() : '';
  if (!itemId) return [];
  return props.itemRequirementsMap?.[itemId] || [];
}

function viewRequirementsLabel(item) {
  const count = linkedRequirements(item).length;
  return props.language === 'en'
    ? `View requirements (${count})`
    : `Ver requerimientos (${count})`;
}

function openRequirements(item) {
  activeItem.value = item;
}
</script>

<style scoped>
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.25s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.requirement-card {
  transition: all 0.2s ease;
}

.requirement-card:hover {
  border-color: rgb(var(--color-focus-ring-rgb) / 0.4);
  transform: translateX(4px);
}

</style>
