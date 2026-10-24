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
    <p class="text-xs text-text-subtle italic">
      La duración se toma del campo «Duración» del tab de Pricing.
    </p>
    <div>
      <label class="block text-xs font-medium text-text-muted mb-1">Título de la distribución</label>
      <input v-model="form.distributionTitle" type="text" class="w-full px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
    </div>
    <div>
      <div class="flex items-center justify-between mb-1">
        <span class="text-xs font-medium text-text-muted">Distribución día a día</span>
        <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand hover:underline" @click="addItem"><BaseActionIcon action="create" /> Agregar</button>
      </div>
      <div class="space-y-2">
        <div
          v-for="(d, idx) in form.distribution"
          :key="idx"
          class="grid sm:grid-cols-[1fr,3fr,auto] gap-2 items-start"
        >
          <input v-model="d.dayRange" type="text" placeholder="Día X" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
          <BaseRichTextEditor v-model="d.description" rows="2" placeholder="Descripción" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" :format="d.text_formats?.['/description'] || 'plain'" @update:format="d.text_formats = { ...d.text_formats, '/description': $event }" />
        <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar fase" size="sm" @click="form.distribution.splice(idx,1)" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue';

const props = defineProps({ modelValue: { type: Object, required: true } });
const emit = defineEmits(['update:modelValue']);

const form = reactive({ ...props.modelValue, distribution: [...(props.modelValue.distribution || [])] });

watch(() => props.modelValue, (next) => {
  Object.assign(form, next);
  form.distribution = [...(next.distribution || [])];
}, { deep: true });

watch(form, (next) => emit('update:modelValue', { ...next, distribution: [...next.distribution] }), { deep: true });

function addItem() { form.distribution.push({ dayRange: '', description: '' }); }
</script>
