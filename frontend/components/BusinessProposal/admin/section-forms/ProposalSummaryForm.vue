<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <FieldInput v-model="form.index" label="Índice" placeholder="10" />
    <FieldInput v-model="form.title" label="Título" />
  </div>
  <FieldTextarea v-model="form.subtitle" :format="form.text_formats?.['/subtitle'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/subtitle': $event }" label="Subtítulo" :rows="2" :isSingle="true" />
  <div>
    <label class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-2">KPIs personalizados</label>
    <p class="text-[10px] text-text-subtle mb-2">Métricas clave que aparecerán como tarjetas destacadas al inicio del resumen. Incluye fuentes verificables.</p>
    <div v-for="(kpi, idx) in (form.kpis || [])" :key="'kpi-' + idx" class="mb-2 bg-primary-soft rounded-xl p-3 border border-emerald-100">
      <div class="flex items-center justify-between mb-1">
        <span class="text-xs text-text-brand font-medium">KPI {{ idx + 1 }}</span>
        <BaseButton variant="danger-ghost" size="sm" @click="form.kpis.splice(idx, 1)">Eliminar</BaseButton>
      </div>
      <div class="grid grid-cols-[120px_1fr] gap-2 mb-1">
        <FieldInput v-model="kpi.value" label="Valor" placeholder="+40%" />
        <FieldInput v-model="kpi.label" label="Etiqueta" placeholder="Incremento en conversión web" />
      </div>
      <FieldInput v-model="kpi.source" label="Fuente" placeholder="HubSpot 2024" />
    </div>
    <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand font-medium" @click="if (!form.kpis) form.kpis = []; form.kpis.push({ value: '', label: '', source: '' })"><BaseActionIcon action="create" /> Agregar KPI</button>
  </div>
  <div>
    <label class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Tarjetas de resumen</label>
    <draggable v-model="form.cards" item-key="_idx" handle=".drag-handle" ghost-class="opacity-30">
      <template #item="{ element: card, index: idx }">
        <div class="mb-3 bg-surface-raised rounded-xl p-3 border border-border-muted">
          <div class="flex items-center justify-between mb-1">
            <div class="flex items-center gap-2">
              <span class="drag-handle cursor-grab text-text-subtle hover:text-text-muted">⠿</span>
              <span class="text-xs text-text-subtle">Tarjeta {{ idx + 1 }}</span>
            </div>
            <BaseButton variant="danger-ghost" size="sm" @click="form.cards.splice(idx, 1)">Eliminar</BaseButton>
          </div>
          <div class="grid grid-cols-[100px_1fr] gap-2 mb-1">
            <EmojiIconField v-model="card.icon" label="Icono" placeholder="💰" />
            <FieldInput v-model="card.title" label="Título" />
          </div>
          <FieldInput v-model="card.description" label="Descripción" />
          <div class="mt-1">
            <label class="block text-[10px] text-text-subtle mb-0.5">Fuente del valor</label>
            <select v-model="card.source" class="w-full px-2 py-1.5 border border-border-default dark:border-white/[0.08] rounded-lg text-xs bg-surface dark:text-white focus:ring-1 focus:ring-focus-ring/30 outline-none">
              <option value="static">Estático (solo texto)</option>
              <option value="total_investment">Inversión total (auto)</option>
              <option value="timeline_duration">Duración del cronograma (auto)</option>
              <option value="expires_at">Fecha de expiración (auto)</option>
              <option value="cta">Call-to-action</option>
            </select>
          </div>
        </div>
      </template>
    </draggable>
    <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand font-medium" @click="form.cards.push({ icon: '', title: '', description: '', source: 'static' })"><BaseActionIcon action="create" /> Agregar tarjeta</button>
  </div>
</template>

<script setup>
import { FieldInput, FieldTextarea } from './fields.js';
import EmojiIconField from '~/components/BusinessProposal/admin/EmojiIconField.vue';
import draggable from 'vuedraggable';

defineProps({
  form: { type: Object, required: true },
  proposalData: { type: Object, default: () => ({}) },
});
</script>
