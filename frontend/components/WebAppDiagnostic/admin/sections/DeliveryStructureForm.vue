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

    <div class="flex items-center justify-between pt-2">
      <span class="text-xs font-medium text-text-muted">Bloques (lo que se encontró bien / hallazgos / recomendaciones)</span>
      <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand hover:underline" @click="addBlock"><BaseActionIcon action="create" /> Agregar</button>
    </div>
    <div class="space-y-2">
      <div
        v-for="(b, idx) in form.blocks"
        :key="idx"
        class="p-3 border border-border-default rounded-xl space-y-2"
      >
        <div class="flex items-center justify-between">
          <input v-model="b.title" type="text" placeholder="Título del bloque" class="flex-1 px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
          <BaseButton variant="danger-ghost" size="sm" class="ml-2" @click="form.blocks.splice(idx, 1)">Quitar</BaseButton>
        </div>
        <BaseRichTextListEditor v-model="b.paragraphsText" rows="3" placeholder="Párrafos (uno por línea)" class="w-full px-3 py-2 border border-border-default rounded-lg text-sm font-mono bg-surface text-text-default" format-path="/paragraphs" :formats="b.text_formats || {}" @update:formats="b.text_formats = $event" />
        <input v-model="b.example" type="text" placeholder="Ejemplo" class="w-full px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue';

const props = defineProps({ modelValue: { type: Object, required: true } });
const emit = defineEmits(['update:modelValue']);

const form = reactive({ ...props.modelValue, blocks: [...(props.modelValue.blocks || [])] });

watch(() => props.modelValue, (next) => {
  Object.assign(form, next);
  form.blocks = [...(next.blocks || [])];
}, { deep: true });

watch(form, (next) => emit('update:modelValue', { ...next, blocks: [...next.blocks] }), { deep: true });

function addBlock() { form.blocks.push({ title: '', paragraphsText: '', example: '' }); }
</script>
