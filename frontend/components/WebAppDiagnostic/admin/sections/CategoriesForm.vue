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
      <span class="text-xs font-medium text-text-muted">Categorías evaluadas ({{ form.categories.length }})</span>
      <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand hover:underline" @click="addCategory"><BaseActionIcon action="create" /> Nueva categoría</button>
    </div>

    <div class="space-y-3">
      <details
        v-for="(cat, idx) in form.categories"
        :key="idx"
        class="border border-border-default rounded-xl"
      >
        <summary class="px-3 py-2 cursor-pointer select-none text-sm font-medium text-text-default flex items-center justify-between">
          <span class="truncate">{{ idx + 1 }}. {{ cat.title || '(sin título)' }}</span>
          <BaseButton variant="danger-ghost" size="sm" class="ml-2" @click.prevent="removeCategory(idx)">Quitar</BaseButton>
        </summary>
        <div class="p-3 space-y-3 border-t border-border-muted">
          <div class="grid sm:grid-cols-2 gap-2">
            <div>
              <label class="block text-xs font-medium text-text-muted mb-1">Clave</label>
              <input v-model="cat.key" type="text" class="w-full px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
            </div>
            <div>
              <label class="block text-xs font-medium text-text-muted mb-1">Título</label>
              <input v-model="cat.title" type="text" class="w-full px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
            </div>
          </div>
          <div>
            <label class="block text-xs font-medium text-text-muted mb-1">Descripción</label>
            <BaseRichTextEditor v-model="cat.description" rows="3" class="w-full px-3 py-2 border border-border-default rounded-lg text-sm bg-surface text-text-default" :format="cat.text_formats?.['/description'] || 'plain'" @update:format="cat.text_formats = { ...cat.text_formats, '/description': $event }" />
          </div>
          <div>
            <label class="block text-xs font-medium text-text-muted mb-1">Lo bueno (una línea por ítem)</label>
            <BaseRichTextListEditor v-model="cat.strengthsText" rows="3" class="w-full px-3 py-2 border border-border-default rounded-lg text-sm font-mono bg-surface text-text-default" format-path="/strengths" :formats="cat.text_formats || {}" @update:formats="cat.text_formats = $event" />
          </div>

          <div class="pt-2 border-t border-border-muted">
            <div class="flex items-center justify-between mb-1">
              <span class="text-xs font-medium text-text-muted">Hallazgos</span>
              <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand hover:underline" @click="addFinding(cat)"><BaseActionIcon action="create" /> Agregar</button>
            </div>
            <div class="space-y-2">
              <div
                v-for="(f, fi) in cat.findings"
                :key="fi"
                class="grid sm:grid-cols-[1fr,2fr,3fr,auto] gap-2 items-start"
              >
                <select v-model="f.level" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default">
                  <option value="">Nivel…</option>
                  <option v-for="lvl in SEVERITY_LEVELS" :key="lvl" :value="lvl">{{ lvl }}</option>
                </select>
                <input v-model="f.title" type="text" placeholder="Título" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
                <BaseRichTextEditor v-model="f.detail" rows="2" placeholder="Detalle" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" :format="f.text_formats?.['/detail'] || 'plain'" @update:format="f.text_formats = { ...f.text_formats, '/detail': $event }" />
          <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar hallazgo" size="sm" @click="cat.findings.splice(fi,1)" />
              </div>
            </div>
          </div>

          <div class="pt-2 border-t border-border-muted">
            <div class="flex items-center justify-between mb-1">
              <span class="text-xs font-medium text-text-muted">Recomendaciones</span>
              <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand hover:underline" @click="addRec(cat)"><BaseActionIcon action="create" /> Agregar</button>
            </div>
            <div class="space-y-2">
              <div
                v-for="(r, ri) in cat.recommendations"
                :key="ri"
                class="grid sm:grid-cols-[1fr,2fr,3fr,auto] gap-2 items-start"
              >
                <select v-model="r.level" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default">
                  <option value="">Nivel…</option>
                  <option v-for="lvl in SEVERITY_LEVELS" :key="lvl" :value="lvl">{{ lvl }}</option>
                </select>
                <input v-model="r.title" type="text" placeholder="Sugerencia" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
                <BaseRichTextEditor v-model="r.detail" rows="2" placeholder="Relación/Detalle" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" :format="r.text_formats?.['/detail'] || 'plain'" @update:format="r.text_formats = { ...r.text_formats, '/detail': $event }" />
          <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar recomendación" size="sm" @click="r.recommendations?.splice(ri,1); cat.recommendations.splice(ri,1)" />
              </div>
            </div>
          </div>
        </div>
      </details>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue';
import { SEVERITY_LEVELS } from '~/stores/diagnostics_constants';

const props = defineProps({ modelValue: { type: Object, required: true } });
const emit = defineEmits(['update:modelValue']);

function cloneCategories(list) {
  return (list || []).map((c) => ({
    key: c.key || '',
    ...(c.text_formats ? { text_formats: { ...c.text_formats } } : {}),
    title: c.title || '',
    description: c.description || '',
    strengthsText: c.strengthsText || '',
    findings: [...(c.findings || [])].map((f) => ({ ...f })),
    recommendations: [...(c.recommendations || [])].map((r) => ({ ...r })),
  }));
}

const form = reactive({
  ...props.modelValue,
  categories: cloneCategories(props.modelValue.categories),
});

watch(() => props.modelValue, (next) => {
  Object.assign(form, next);
  form.categories = cloneCategories(next.categories);
}, { deep: true });

watch(form, (next) => emit('update:modelValue', {
  ...next,
  categories: cloneCategories(next.categories),
}), { deep: true });

function addCategory() {
  form.categories.push({
    key: '',
    title: '',
    description: '',
    strengthsText: '',
    findings: [],
    recommendations: [],
  });
}
function removeCategory(i) { form.categories.splice(i, 1); }
function addFinding(cat) { cat.findings.push({ level: '', title: '', detail: '' }); }
function addRec(cat) { cat.recommendations.push({ level: '', title: '', detail: '' }); }
</script>
