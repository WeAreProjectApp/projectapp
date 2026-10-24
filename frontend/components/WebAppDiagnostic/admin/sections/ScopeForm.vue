<template>
  <div class="space-y-3">
    <div class="grid sm:grid-cols-6 gap-3">
      <div class="sm:col-span-1">
        <label class="block text-xs font-medium text-text-muted mb-1">Índice</label>
        <input v-model="form.index" type="text" class="w-full px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
      </div>
      <div class="sm:col-span-5">
        <label class="block text-xs font-medium text-text-muted mb-1">Título</label>
        <input v-model="form.title" type="text" class="w-full px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
      </div>
    </div>
    <div>
      <label class="block text-xs font-medium text-text-muted mb-1">Consideraciones (una por línea)</label>
      <BaseRichTextListEditor v-model="form.considerationsText" rows="6" class="w-full px-3 py-2 border border-border-default rounded-lg text-sm font-mono bg-surface text-text-default" format-path="/considerations" :formats="form.text_formats || {}" @update:formats="form.text_formats = $event" />
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue';

const props = defineProps({ modelValue: { type: Object, required: true } });
const emit = defineEmits(['update:modelValue']);

const form = reactive({ ...props.modelValue });

watch(() => props.modelValue, (next) => Object.assign(form, next), { deep: true });
watch(form, (next) => emit('update:modelValue', { ...next }), { deep: true });
</script>
