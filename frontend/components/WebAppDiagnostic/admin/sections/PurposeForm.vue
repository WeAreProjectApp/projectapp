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
      <label class="block text-xs font-medium text-text-muted mb-1">Párrafos (uno por línea)</label>
      <BaseRichTextListEditor v-model="form.paragraphsText" rows="5" class="w-full px-3 py-2 border border-border-default rounded-lg text-sm font-mono bg-surface text-text-default" format-path="/paragraphs" :formats="form.text_formats || {}" @update:formats="form.text_formats = $event" />
    </div>
    <div>
      <label class="block text-xs font-medium text-text-muted mb-1">Nota de alcance</label>
      <BaseRichTextEditor v-model="form.scopeNote" rows="3" class="w-full px-3 py-2 border border-border-default rounded-lg text-sm bg-surface text-text-default" :format="form.text_formats?.['/scopeNote'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/scopeNote': $event }" />
    </div>

    <div class="pt-3 border-t border-border-muted space-y-2">
      <div class="grid sm:grid-cols-2 gap-3">
        <div>
          <label class="block text-xs font-medium text-text-muted mb-1">Título de Severidad</label>
          <input v-model="form.severityTitle" type="text" class="w-full px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
        </div>
        <div>
          <label class="block text-xs font-medium text-text-muted mb-1">Intro de Severidad</label>
          <input v-model="form.severityIntro" type="text" class="w-full px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
        </div>
      </div>
      <div>
        <div class="flex items-center justify-between mb-1">
          <span class="text-xs font-medium text-text-muted">Niveles de severidad</span>
          <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand hover:underline" @click="addLevel"><BaseActionIcon action="create" /> Agregar</button>
        </div>
        <div class="space-y-2">
          <div
            v-for="(lvl, idx) in form.severityLevels"
            :key="idx"
            class="grid sm:grid-cols-[1fr,3fr,auto] gap-2 items-start"
          >
            <input v-model="lvl.level" type="text" placeholder="Crítico / Alto / Medio / Bajo" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
            <BaseRichTextEditor v-model="lvl.meaning" rows="2" placeholder="Significado" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" :format="lvl.text_formats?.['/meaning'] || 'plain'" @update:format="lvl.text_formats = { ...lvl.text_formats, '/meaning': $event }" />
            <BaseButton variant="danger-ghost" size="sm" @click="removeLevel(idx)">Quitar</BaseButton>
          </div>
          <div v-if="!form.severityLevels.length" class="text-xs text-text-subtle italic">Sin niveles configurados.</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue';

const props = defineProps({ modelValue: { type: Object, required: true } });
const emit = defineEmits(['update:modelValue']);

const form = reactive({ ...props.modelValue, severityLevels: [...(props.modelValue.severityLevels || [])] });

watch(() => props.modelValue, (next) => {
  Object.assign(form, next);
  form.severityLevels = [...(next.severityLevels || [])];
}, { deep: true });

watch(form, (next) => emit('update:modelValue', { ...next, severityLevels: [...next.severityLevels] }), { deep: true });

function addLevel() { form.severityLevels.push({ level: '', meaning: '' }); }
function removeLevel(i) { form.severityLevels.splice(i, 1); }
</script>
