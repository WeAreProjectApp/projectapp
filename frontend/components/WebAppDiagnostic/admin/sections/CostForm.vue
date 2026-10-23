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
      <label class="block text-xs font-medium text-text-muted mb-1">Beneficios (uno por línea)</label>
      <BaseRichTextListEditor v-model="form.valueBulletsText" rows="4" placeholder="Ej: Claridad técnica accionable: ..." class="w-full px-3 py-2 border border-border-default rounded-lg text-sm bg-surface text-text-default" format-path="/valueBullets" :formats="form.text_formats || {}" @update:formats="form.text_formats = $event" />
    </div>
    <p class="text-xs text-text-subtle italic">
      El monto, la moneda y los porcentajes se toman del tab General.
    </p>
    <div>
      <div class="flex items-center justify-between mb-1">
        <span class="text-xs font-medium text-text-muted">Descripción de los pagos</span>
        <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand hover:underline" @click="addItem"><BaseActionIcon action="create" /> Agregar</button>
      </div>
      <div class="space-y-2">
        <div
          v-for="(p, idx) in form.paymentDescription"
          :key="idx"
          class="grid sm:grid-cols-[1fr,3fr,auto] gap-2 items-start"
        >
          <input v-model="p.label" type="text" placeholder="al inicio / al final" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" />
          <BaseRichTextEditor v-model="p.detail" rows="2" placeholder="Detalle" class="px-2 py-1.5 border border-border-default rounded-lg text-sm bg-surface text-text-default" :format="p.text_formats?.['/detail'] || 'plain'" @update:format="p.text_formats = { ...p.text_formats, '/detail': $event }" />
        <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar descripción" size="sm" @click="form.paymentDescription.splice(idx,1)" />
        </div>
      </div>
    </div>
    <div>
      <label class="block text-xs font-medium text-text-muted mb-1">Nota</label>
      <BaseRichTextEditor v-model="form.note" rows="2" class="w-full px-3 py-2 border border-border-default rounded-lg text-sm bg-surface text-text-default" :format="form.text_formats?.['/note'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/note': $event }" />
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue';

const props = defineProps({ modelValue: { type: Object, required: true } });
const emit = defineEmits(['update:modelValue']);

const form = reactive({
  ...props.modelValue,
  paymentDescription: [...(props.modelValue.paymentDescription || [])],
});

watch(() => props.modelValue, (next) => {
  Object.assign(form, next);
  form.paymentDescription = [...(next.paymentDescription || [])];
}, { deep: true });

watch(form, (next) => emit('update:modelValue', {
  ...next,
  paymentDescription: [...next.paymentDescription],
}), { deep: true });

function addItem() { form.paymentDescription.push({ label: '', detail: '' }); }
</script>
