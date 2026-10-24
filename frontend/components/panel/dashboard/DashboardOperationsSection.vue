<template>
  <section
    v-if="operations"
    aria-labelledby="dashboard-operations-title"
    data-testid="dashboard-operations-section"
  >
    <h2
      id="dashboard-operations-title"
      class="mb-3 text-xs font-semibold uppercase tracking-widest text-text-muted"
    >
      Operación
    </h2>

    <BaseEmptyState
      v-if="isAllZero"
      title="Sin actividad operativa aún"
      description="Cuando existan tareas, documentos, emails o diagnósticos verás sus indicadores aquí."
    />
    <div v-else class="grid grid-cols-1 gap-4 panel-portrait:grid-cols-2 panel-desktop:grid-cols-5">
      <DashboardStatTile
        label="Tareas abiertas"
        :value="tasks.open"
        format="number"
        :tone="tasksTone"
        :sub="tasksSub"
        :to="localePath('/panel/tasks')"
        data-testid="dashboard-tasks-tile"
      />
      <DashboardStatTile
        label="Por cobrar"
        :value="Number(collection.outstanding_total)"
        format="currency"
        :tone="collection.overdue_issued > 0 ? 'danger' : 'default'"
        :sub="collectionSub"
        :to="localePath('/panel/documents')"
      />
      <DashboardStatTile
        label="Éxito email 30d"
        :value="emails.success_rate"
        format="percent"
        :tone="emailTone"
        :sub="emailSub"
        :sparkline="emailSparkline"
        sparkline-label="Emails enviados por día, últimos 14 días"
        :to="localePath('/panel/emails')"
      />
      <DashboardStatTile
        label="Diagnósticos activos"
        :value="diagnostics.active_pipeline"
        format="number"
        :sub="diagnosticsSub"
        :to="localePath('/panel/diagnostics')"
      />
      <DashboardStatTile
        label="Paquetes de requerimientos"
        :value="hourPackages.active_count"
        format="number"
        sub="activos en catálogo"
        :to="localePath('/panel/hour-packages')"
      />
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import DashboardStatTile from '~/components/panel/dashboard/DashboardStatTile.vue';
import { formatMoney } from '~/utils/formatMoney';

/** Operations tiles: tasks, receivables, email health, diagnostics, hour packages. */
const props = defineProps({
  operations: { type: Object, default: null },
});

const localePath = useLocalePath();

const tasks = computed(() => props.operations?.tasks || {});
const collection = computed(
  () => props.operations?.documents?.collection_accounts || {},
);
const emails = computed(() => props.operations?.emails || {});
const diagnostics = computed(() => props.operations?.diagnostics || {});
const hourPackages = computed(() => props.operations?.hour_packages || {});

const isAllZero = computed(() =>
  !tasks.value.open
  && !collection.value.issued_count
  && !emails.value.total_30d
  && !diagnostics.value.active_pipeline
  && !hourPackages.value.active_count,
);

const tasksTone = computed(() => {
  if (tasks.value.overdue_high > 0) return 'danger';
  if (tasks.value.overdue > 0) return 'warning';
  return 'default';
});

const tasksSub = computed(() => {
  const parts = [];
  if (tasks.value.overdue > 0) parts.push(`${tasks.value.overdue} vencidas`);
  if (tasks.value.blocked > 0) parts.push(`${tasks.value.blocked} bloqueadas`);
  return parts.join(' · ') || 'sin vencidas';
});

const collectionSub = computed(() => {
  const issued = collection.value.issued_count || 0;
  const overdue = collection.value.overdue_issued || 0;
  if (!issued) return 'sin cuentas emitidas';
  const base = `${issued} emitida${issued === 1 ? '' : 's'}`;
  return overdue > 0 ? `${base} · ${overdue} vencida${overdue === 1 ? '' : 's'}` : base;
});

const emailTone = computed(() => {
  if (emails.value.success_rate === null || emails.value.success_rate === undefined) {
    return 'default';
  }
  if (emails.value.success_rate < 90) return 'danger';
  if (emails.value.failed_count > 0) return 'warning';
  return 'success';
});

const emailSub = computed(() => {
  if (!emails.value.total_30d) return 'sin envíos recientes';
  return `${emails.value.failed_count} fallidos de ${emails.value.total_30d}`;
});

const emailSparkline = computed(() =>
  (emails.value.daily_trend || []).map((row) => row.total),
);

const diagnosticsSub = computed(() => {
  const accepted = Number(diagnostics.value.accepted_value) || 0;
  return accepted > 0 ? `${formatMoney(accepted)} aceptado` : 'en pipeline';
});
</script>
