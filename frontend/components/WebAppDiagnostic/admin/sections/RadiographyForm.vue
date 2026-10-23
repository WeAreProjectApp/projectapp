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
      <BaseRichTextEditor v-model="form.intro" rows="3" class="w-full px-3 py-2 border border-border-default rounded-lg text-sm bg-surface text-text-default" :format="form.text_formats?.['/intro'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/intro': $event }" />
    </div>

    <div class="pt-3 border-t border-border-muted space-y-2">
      <div>
        <label class="block text-xs font-medium text-text-muted mb-1">Título «¿Qué incluye?»</label>
        <input v-model="form.includesTitle" type="text" class="w-full px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
      </div>
      <div class="flex items-center justify-between">
        <span class="text-xs font-medium text-text-muted">Elementos de la radiografía</span>
        <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand hover:underline" @click="addInclude"><BaseActionIcon action="create" /> Agregar</button>
      </div>
      <div class="space-y-2">
        <div
          v-for="(it, idx) in form.includes"
          :key="idx"
          class="grid sm:grid-cols-[1fr,2fr,auto] gap-2 items-start"
        >
          <input v-model="it.title" type="text" placeholder="Título" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
          <BaseRichTextEditor v-model="it.description" rows="2" placeholder="Descripción" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" :format="it.text_formats?.['/description'] || 'plain'" @update:format="it.text_formats = { ...it.text_formats, '/description': $event }" />
          <BaseButton variant="danger-ghost" size="sm" @click="removeInclude(idx)">Quitar</BaseButton>
        </div>
      </div>
    </div>

    <div class="pt-3 border-t border-border-muted space-y-2">
      <div class="grid sm:grid-cols-2 gap-3">
        <div>
          <label class="block text-xs font-medium text-text-muted mb-1">Título de clasificación</label>
          <input v-model="form.classificationTitle" type="text" class="w-full px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
        </div>
        <div>
          <label class="block text-xs font-medium text-text-muted mb-1">Intro clasificación</label>
          <input v-model="form.classificationIntro" type="text" class="w-full px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
        </div>
      </div>

      <div class="flex items-center justify-between">
        <span class="text-xs font-medium text-text-muted">Filas de tamaño</span>
        <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand hover:underline" @click="addRow"><BaseActionIcon action="create" /> Agregar</button>
      </div>
      <div class="space-y-2">
        <div
          v-for="(r, idx) in form.classificationRows"
          :key="idx"
          class="grid sm:grid-cols-[2fr,1fr,1fr,1fr,auto] gap-2 items-center"
        >
          <input v-model="r.dimension" type="text" placeholder="Dimensión" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
          <input v-model="r.small" type="text" placeholder="Pequeña" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
          <input v-model="r.medium" type="text" placeholder="Mediana" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
          <input v-model="r.large" type="text" placeholder="Grande" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
          <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar tecnología" size="sm" @click="removeRow(idx)" />
        </div>
      </div>

      <div>
        <label class="block text-xs font-medium text-text-muted mb-1">Nota de clasificación</label>
        <BaseRichTextEditor v-model="form.classificationNote" rows="2" class="w-full px-3 py-2 border border-border-default rounded-lg text-sm bg-surface text-text-default" :format="form.text_formats?.['/classificationNote'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/classificationNote': $event }" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue';

const props = defineProps({ modelValue: { type: Object, required: true } });
const emit = defineEmits(['update:modelValue']);

const form = reactive({
  ...props.modelValue,
  includes: [...(props.modelValue.includes || [])],
  classificationRows: [...(props.modelValue.classificationRows || [])],
});

watch(() => props.modelValue, (next) => {
  Object.assign(form, next);
  form.includes = [...(next.includes || [])];
  form.classificationRows = [...(next.classificationRows || [])];
}, { deep: true });

watch(form, (next) => emit('update:modelValue', {
  ...next,
  includes: [...next.includes],
  classificationRows: [...next.classificationRows],
}), { deep: true });

function addInclude() { form.includes.push({ title: '', description: '' }); }
function removeInclude(i) { form.includes.splice(i, 1); }
function addRow() { form.classificationRows.push({ dimension: '', small: '', medium: '', large: '' }); }
function removeRow(i) { form.classificationRows.splice(i, 1); }
</script>
