<script setup>
import { computed, nextTick } from 'vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import BaseModalActions from '~/components/base/BaseModalActions.vue';

/**
 * The menu behind an accounting row's three-dot button.
 *
 * A modal rather than a dropdown: the tables scroll inside an `overflow-x-auto`
 * wrapper, which clips an absolutely positioned menu on the last rows and on
 * narrow screens. The owner lists the entries it offers for the record and
 * reacts to `select`. Menus with entity-specific states (pocket, recurring,
 * incomes, hostings, collections) keep their dedicated components.
 */
const props = defineProps({
  open: { type: Boolean, default: false },
  record: { type: Object, default: null },
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  /** [{ id, action, label, danger?, disabled?, description?, testId? }] */
  actions: { type: Array, default: () => [] },
  /** Test ids: `${prefix}-actions-modal` and `${prefix}-action-${id}-${suffix}`. */
  testIdPrefix: { type: String, required: true },
  /** Suffix of the entry test ids; the record id when omitted. */
  testIdSuffix: { type: [String, Number], default: undefined },
  /** Off when the menu opens above a modal that already locks the page. */
  lockScroll: { type: Boolean, default: true },
});

const emit = defineEmits(['close', 'select']);

const titleId = computed(() => `${props.testIdPrefix}-actions-title`);

function entryTestId(action) {
  return action.testId
    || `${props.testIdPrefix}-action-${action.id}-${props.testIdSuffix ?? props.record?.id}`;
}

function descriptionId(action) {
  return `${props.testIdPrefix}-action-${action.id}-description`;
}

/**
 * Close first, act on the next tick. The owner opens the follow-up dialog
 * (history, note, form, confirmation) from `select`; opening it in the same
 * flush as this close made the two dialogs trade focus traps and scroll locks.
 * The record is captured because the owner clears it on close.
 */
async function choose(action) {
  const record = props.record;
  if (!record || action.disabled) return;
  emit('close');
  await nextTick();
  emit('select', action.id, record);
}
</script>

<template>
  <BaseModal
    :model-value="open"
    kind="confirm"
    :title-id="titleId"
    :lock-scroll="lockScroll"
    @close="emit('close')"
  >
    <div :data-testid="`${testIdPrefix}-actions-modal`">
      <header class="border-b border-border-muted px-6 pb-4 pt-6">
        <h3 :id="titleId" class="break-words text-base font-bold text-text-default">
          {{ title }}
        </h3>
        <p v-if="subtitle" class="mt-1 break-words text-sm text-text-muted">
          {{ subtitle }}
        </p>
      </header>

      <ul class="py-2">
        <li v-for="action in actions" :key="action.id">
          <!-- design-tokens: allow-raw-button -- menu row, not a standalone CTA -->
          <button
            type="button"
            class="flex min-h-11 w-full items-start gap-3 px-6 py-3 text-left text-sm transition-colors"
            :class="[
              action.danger
                ? 'text-danger-strong hover:bg-danger-soft'
                : 'text-text-default hover:bg-surface-raised',
              action.disabled ? 'cursor-not-allowed opacity-50' : '',
            ]"
            :disabled="action.disabled"
            :aria-describedby="action.description ? descriptionId(action) : undefined"
            :data-testid="entryTestId(action)"
            @click="choose(action)"
          >
            <BaseActionIcon :action="action.action" class="mt-0.5" />
            <span class="min-w-0">
              <span class="block">{{ action.label }}</span>
              <span
                v-if="action.description"
                :id="descriptionId(action)"
                class="mt-0.5 block text-xs text-text-subtle"
              >{{ action.description }}</span>
            </span>
          </button>
        </li>
      </ul>

      <BaseModalActions>
        <BaseButton variant="secondary" @click="emit('close')">Cerrar</BaseButton>
      </BaseModalActions>
    </div>
  </BaseModal>
</template>
