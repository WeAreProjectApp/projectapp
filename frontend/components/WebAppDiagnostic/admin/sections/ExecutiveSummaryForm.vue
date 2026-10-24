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
      <label class="block text-xs font-medium text-text-muted mb-1">Intro</label>
      <BaseRichTextEditor v-model="form.intro" rows="2" class="w-full px-3 py-2 border border-border-default rounded-lg text-sm bg-surface text-text-default" :format="form.text_formats?.['/intro'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/intro': $event }" />
    </div>

    <div>
      <div class="text-xs font-medium text-text-muted mb-1">Conteo por nivel</div>
      <div class="grid sm:grid-cols-4 gap-2">
        <label class="text-xs text-rose-600">
          Crítico
          <input v-model.number="form.severityCounts.critico" type="number" min="0" class="w-full mt-1 px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
        </label>
        <label class="text-xs text-amber-600">
          Alto
          <input v-model.number="form.severityCounts.alto" type="number" min="0" class="w-full mt-1 px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
        </label>
        <label class="text-xs text-blue-600">
          Medio
          <input v-model.number="form.severityCounts.medio" type="number" min="0" class="w-full mt-1 px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
        </label>
        <label class="text-xs text-text-brand">
          Bajo
          <input v-model.number="form.severityCounts.bajo" type="number" min="0" class="w-full mt-1 px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
        </label>
      </div>
    </div>

    <div>
      <label class="block text-xs font-medium text-text-muted mb-1">Narrativa</label>
      <BaseRichTextEditor v-model="form.narrative" rows="4" class="w-full px-3 py-2 border border-border-default rounded-lg text-sm bg-surface text-text-default" :format="form.text_formats?.['/narrative'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/narrative': $event }" />
    </div>

    <div>
      <label class="block text-xs font-medium text-text-muted mb-1">Highlights (uno por línea)</label>
      <BaseRichTextListEditor v-model="form.highlightsText" rows="3" class="w-full px-3 py-2 border border-border-default rounded-lg text-sm font-mono bg-surface text-text-default" format-path="/highlights" :formats="form.text_formats || {}" @update:formats="form.text_formats = $event" />
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue';

const props = defineProps({ modelValue: { type: Object, required: true } });
const emit = defineEmits(['update:modelValue']);

const form = reactive({
  ...props.modelValue,
  severityCounts: { ...(props.modelValue.severityCounts || { critico: 0, alto: 0, medio: 0, bajo: 0 }) },
});

watch(() => props.modelValue, (next) => {
  Object.assign(form, next);
  form.severityCounts = { ...(next.severityCounts || { critico: 0, alto: 0, medio: 0, bajo: 0 }) };
}, { deep: true });

watch(form, (next) => emit('update:modelValue', {
  ...next,
  severityCounts: { ...next.severityCounts },
}), { deep: true });
</script>
