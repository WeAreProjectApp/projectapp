<template>
  <div ref="rootElement" class="min-w-0" data-testid="secure-link-title-editor">
    <div v-if="!editing" class="flex min-w-0 items-start gap-1">
      <h3 class="min-w-0 text-lg font-bold text-text-default [overflow-wrap:anywhere]">{{ title }}</h3>
      <BaseActionButton
        action="rename"
        class="-my-1.5 shrink-0"
        :label="t('secureLinks.panel.renameTitle')"
        :disabled="disabled"
        :disabled-reason="t('secureLinks.panel.saving')"
        data-testid="secure-link-title-edit"
        @click="start"
      />
    </div>
    <form v-else class="space-y-2" novalidate data-testid="secure-link-title-form" @submit.prevent="submit">
      <BaseInput
        v-model="draft"
        maxlength="160"
        :aria-label="t('secureLinks.panel.title')"
        :error="Boolean(errorMessage)"
        :aria-describedby="errorMessage ? errorId : undefined"
        :disabled="saving"
        :disabled-reason="t('secureLinks.panel.saving')"
        data-testid="secure-link-title-input"
        @keydown.esc.stop.prevent="cancel"
      />
      <p v-if="errorMessage" :id="errorId" class="text-xs text-danger-strong" role="alert" data-testid="secure-link-title-error">
        {{ errorMessage }}
      </p>
      <div class="flex justify-end gap-2">
        <BaseButton
          type="button"
          variant="ghost"
          size="sm"
          :disabled="saving"
          :disabled-reason="t('secureLinks.panel.saving')"
          data-testid="secure-link-title-cancel"
          @click="cancel"
        >
          {{ t('secureLinks.panel.cancel') }}
        </BaseButton>
        <BaseButton type="submit" variant="primary" size="sm" :loading="saving" data-testid="secure-link-title-save">
          {{ t('secureLinks.panel.saveTitle') }}
        </BaseButton>
      </div>
    </form>
  </div>
</template>

<script setup>
import { nextTick, ref, useId } from 'vue';
import BaseActionButton from '~/components/base/BaseActionButton.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseInput from '~/components/base/BaseInput.vue';

/**
 * Renames a secure link in place, without opening the content editor.
 *
 * Esc cancels and stops there: the detail modal closes on any Escape that
 * reaches `window`. The owner runs the request and returns the store result,
 * so field errors stay next to the input with the draft intact.
 */
const props = defineProps({
  title: { type: String, default: '' },
  /** Another detail action is running. */
  disabled: { type: Boolean, default: false },
  /** async (title) => { success, error?, stale? } */
  save: { type: Function, required: true },
});

const { t } = useI18n();
const rootElement = ref(null);
const editing = ref(false);
const saving = ref(false);
const draft = ref('');
const errorMessage = ref('');
const errorId = useId();

async function start() {
  if (props.disabled) return;
  draft.value = props.title;
  errorMessage.value = '';
  editing.value = true;
  await nextTick();
  rootElement.value?.querySelector('input')?.focus();
}

function cancel() {
  if (saving.value) return;
  editing.value = false;
  errorMessage.value = '';
}

function validationError(title) {
  if (!title) return t('secureLinks.panel.titleRequired');
  if ([...title].length > 160) return t('secureLinks.validation.maxLength', { max: 160 });
  return '';
}

function serverError(error) {
  const value = error?.fieldErrors?.title;
  const message = Array.isArray(value) ? value[0] : value;
  return (typeof message === 'string' && message) || error?.message || t('secureLinks.genericError');
}

async function submit() {
  if (saving.value) return;
  const next = draft.value.trim();
  errorMessage.value = validationError(next);
  if (errorMessage.value) return;
  if (next === props.title) {
    editing.value = false;
    return;
  }
  saving.value = true;
  const result = await props.save(next);
  saving.value = false;
  if (result?.success) editing.value = false;
  else if (!result?.stale) errorMessage.value = serverError(result?.error);
}
</script>
