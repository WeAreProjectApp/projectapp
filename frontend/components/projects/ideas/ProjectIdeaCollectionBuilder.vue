<script setup>
import BaseButton from '~/components/base/BaseButton.vue'
import { ref } from 'vue'
const props = defineProps({ selected: { type: Array, default: () => [] }, busy: Boolean })
const emit = defineEmits(['submit'])
const { t } = useI18n()
const title = ref('')
</script>

<template>
  <form class="space-y-3 rounded-xl border border-border-default p-4" @submit.prevent="emit('submit', title)">
    <p class="text-sm text-text-subtle">{{ t('projectIdeas.collectionNotice') }}</p>
    <p class="text-sm">{{ t('projectIdeas.selected') }}: {{ selected.length }}</p>
    <label for="project-idea-collection-title" class="block text-sm font-medium">{{ t('projectIdeas.collectionTitle') }}</label>
    <input id="project-idea-collection-title" v-model="title" required maxlength="255" class="w-full rounded-xl border border-border-default bg-surface px-4 py-3" data-testid="idea-collection-title" />
    <BaseButton variant="primary" size="md" textPolicy="wrap" class="min-h-11" type="submit" :disabled="busy || !title.trim() || !selected.length" data-testid="idea-collection-save">{{ t('projectIdeas.collect') }}</BaseButton>
  </form>
</template>
