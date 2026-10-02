<script setup>
import BaseButton from '~/components/base/BaseButton.vue'
import { ref, watch } from 'vue'
const props = defineProps({ initial: { type: String, default: '' }, busy: Boolean, editing: Boolean })
const emit = defineEmits(['submit', 'cancel'])
const { t } = useI18n()
const text = ref(props.initial)
watch(() => props.initial, (value) => { text.value = value })
</script>

<template>
  <form class="space-y-3" @submit.prevent="emit('submit', text)">
    <label for="project-idea-text" class="block text-sm font-medium text-text-default">{{ t('projectIdeas.text') }}</label>
    <textarea id="project-idea-text" v-model="text" rows="4" maxlength="10000" required class="w-full rounded-xl border border-border-default bg-surface px-4 py-3 text-text-default" data-testid="project-idea-text" />
    <div class="flex flex-wrap gap-2">
      <BaseButton variant="primary" size="md" textPolicy="wrap" class="min-h-11" type="submit" :disabled="busy || !text.trim()" data-testid="project-idea-save">{{ busy ? t('projectIdeas.saving') : t(editing ? 'projectIdeas.edit' : 'projectIdeas.save') }}</BaseButton>
      <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" v-if="editing" type="button" @click="emit('cancel')">{{ t('projectIdeas.cancel') }}</BaseButton>
    </div>
  </form>
</template>
