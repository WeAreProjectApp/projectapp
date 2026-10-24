<template>
  <section>
    <SectionHeader :index="content.index" :title="content.title" fallback="Radiografía" />
    <BaseRichTextContent v-if="content.intro" class="text-text-brand/80 dark:text-text-brand/80 leading-relaxed" :source="content.intro" :format="content.text_formats?.['/intro'] || 'plain'" />

    <div v-if="content.includes?.length" class="mt-6">
      <h3 class="text-lg font-semibold text-text-brand dark:text-text-brand mb-3">{{ content.includesTitle || '¿Qué incluye esta radiografía?' }}</h3>
      <ul class="space-y-2.5">
        <li v-for="(i, idx) in content.includes" :key="idx" class="flex gap-3">
          <span class="mt-1.5 flex-none w-1.5 h-1.5 rounded-full bg-primary dark:bg-accent-soft" />
          <div>
            <strong class="text-text-brand dark:text-text-brand">{{ i.title }}:</strong>
            <span class="text-text-brand/75 dark:text-text-brand/75"><BaseRichTextContent :source="i.description" :format="i.text_formats?.['/description'] || 'plain'" /></span>
          </div>
        </li>
      </ul>
    </div>

    <div v-if="content.classificationRows?.length" class="mt-8">
      <h3 class="text-lg font-semibold text-text-brand dark:text-text-brand mb-2">{{ content.classificationTitle || 'Clasificación por tamaño' }}</h3>
      <BaseRichTextContent v-if="content.classificationIntro" class="text-text-brand/75 dark:text-text-brand/75 mb-3" :source="content.classificationIntro" :format="content.text_formats?.['/classificationIntro'] || 'plain'" />
      <div class="overflow-x-auto">
        <table class="min-w-full text-sm border border-input-border dark:border-input-border rounded-xl overflow-hidden">
          <thead class="bg-primary/5 dark:bg-primary-soft">
            <tr>
              <th class="px-3 py-2 text-left font-semibold text-text-brand dark:text-text-brand">Dimensión</th>
              <th class="px-3 py-2 text-left font-semibold text-text-brand dark:text-text-brand">Pequeña</th>
              <th class="px-3 py-2 text-left font-semibold text-text-brand dark:text-text-brand">Mediana</th>
              <th class="px-3 py-2 text-left font-semibold text-text-brand dark:text-text-brand">Grande</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in content.classificationRows" :key="idx" class="border-t border-input-border dark:border-input-border">
              <td class="px-3 py-2 text-text-brand dark:text-text-brand">{{ row.dimension }}</td>
              <td class="px-3 py-2 text-text-brand/75 dark:text-text-brand/75">{{ row.small }}</td>
              <td class="px-3 py-2 text-text-brand/75 dark:text-text-brand/75">{{ row.medium }}</td>
              <td class="px-3 py-2 text-text-brand/75 dark:text-text-brand/75">{{ row.large }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <BaseRichTextContent v-if="content.classificationNote" class="text-xs text-text-brand/55 dark:text-text-brand/55 mt-2 italic" :source="content.classificationNote" :format="content.text_formats?.['/classificationNote'] || 'plain'" />
    </div>

    <div v-if="renderContext && hasStack" class="mt-8 bg-primary/5 dark:bg-primary-soft border border-input-border dark:border-input-border rounded-xl p-4 text-sm">
      <h3 class="text-sm font-semibold text-text-brand dark:text-text-brand mb-1">Lo que encontramos en tu aplicación</h3>
      <p class="text-xs text-text-brand/60 mb-3">Cada número explica una parte del tamaño y la complejidad de tu sistema.</p>
      <dl class="grid sm:grid-cols-2 gap-3">
        <div v-for="metric in stackMetrics" :key="metric.label" class="bg-surface/60 rounded-lg px-3 py-2 border border-input-border">
          <dt class="text-xs font-semibold text-text-brand">{{ metric.label }}</dt>
          <dd class="text-sm text-text-default mt-0.5">{{ metric.value }}</dd>
          <dd class="text-xs text-text-brand/60 mt-0.5">{{ metric.explain }}</dd>
        </div>
      </dl>
    </div>
  </section>
</template>

<script setup>
import BaseRichTextContent from '~/components/base/BaseRichTextContent.vue';
import { computed } from 'vue';
import SectionHeader from './SectionHeader.vue';
const props = defineProps({
  content: { type: Object, required: true },
  renderContext: { type: Object, default: () => ({}) },
});
const hasStack = computed(() => !!(props.renderContext?.stack_backend_name || props.renderContext?.stack_frontend_name));

const stackMetrics = computed(() => {
  const rc = props.renderContext || {};
  const metrics = [];
  if (rc.stack_backend_name) {
    metrics.push({
      label: 'Tecnología del servidor',
      value: rc.stack_backend_version ? `${rc.stack_backend_name} (${rc.stack_backend_version})` : rc.stack_backend_name,
      explain: 'El motor que procesa y guarda la información de tu negocio.',
    });
  }
  if (rc.stack_frontend_name) {
    metrics.push({
      label: 'Tecnología de la interfaz',
      value: rc.stack_frontend_version ? `${rc.stack_frontend_name} (${rc.stack_frontend_version})` : rc.stack_frontend_name,
      explain: 'Con lo que están construidas las pantallas que usan tus usuarios.',
    });
  }
  if (rc.entities_count) {
    metrics.push({
      label: 'Tipos de información',
      value: `${rc.entities_count} (${rc.entities_size})`,
      explain: 'Las piezas de datos que tu aplicación gestiona: clientes, pedidos, productos…',
    });
  }
  if (rc.routes_total) {
    metrics.push({
      label: 'Operaciones internas',
      value: `${rc.routes_total} (${rc.routes_size})`,
      explain: 'Las acciones que el sistema puede ejecutar detrás de escena.',
    });
  }
  if (rc.frontend_routes_count) {
    metrics.push({
      label: 'Pantallas',
      value: `${rc.frontend_routes_count} (${rc.frontend_routes_size})`,
      explain: 'Las vistas por las que navegan tus usuarios.',
    });
  }
  if (rc.components_count) {
    metrics.push({
      label: 'Piezas de interfaz',
      value: `${rc.components_count} (${rc.components_size})`,
      explain: 'Bloques reutilizables con los que se arma cada pantalla.',
    });
  }
  if (rc.external_integrations) {
    metrics.push({
      label: 'Conexiones externas',
      value: `${rc.external_integrations} (${rc.integrations_size})`,
      explain: 'Servicios de terceros con los que tu aplicación se comunica (pagos, correos…).',
    });
  }
  return metrics;
});
</script>
