<template>
  <div>
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-8">
      <div>
        <h2 class="text-lg font-medium text-text-default">{{ t('panelUsability.emailStatus') }}</h2>
        <p class="text-sm text-text-muted mt-1">
          Monitoreo de emails enviados en los últimos 30 días.
        </p>
      </div>

    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="text-center py-16 text-text-subtle text-sm">
      Cargando estadísticas de email...
    </div>

    <template v-else-if="stats">
      <!-- KPI Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div class="bg-surface rounded-xl border border-border-muted p-5 shadow-card">
          <div class="text-xs font-medium text-text-muted uppercase tracking-wider mb-1">Total Enviados</div>
          <div class="text-3xl font-bold text-text-default tabular-nums">{{ stats.total_emails_30d }}</div>
          <div class="text-xs text-text-subtle mt-1">últimos 30 días</div>
        </div>
        <div class="bg-surface rounded-xl border border-border-muted p-5 shadow-card">
          <div class="text-xs font-medium text-text-muted uppercase tracking-wider mb-1">Tasa de Éxito</div>
          <div class="text-3xl font-bold tabular-nums" :class="stats.success_rate >= 95 ? 'text-text-brand' : stats.success_rate >= 80 ? 'text-warning-strong' : 'text-danger-strong'">
            {{ stats.success_rate }}%
          </div>
          <div class="text-xs text-text-subtle mt-1">enviados correctamente</div>
        </div>
        <div class="bg-surface rounded-xl border border-border-muted p-5 shadow-card">
          <div class="text-xs font-medium text-text-brand uppercase tracking-wider mb-1">Exitosos</div>
          <div class="text-3xl font-bold text-text-brand tabular-nums">{{ stats.sent_count }}</div>
        </div>
        <div class="bg-surface rounded-xl border border-border-muted p-5 shadow-card">
          <div class="text-xs font-medium text-danger-strong uppercase tracking-wider mb-1">Fallidos</div>
          <div class="text-3xl font-bold tabular-nums" :class="stats.failed_count > 0 ? 'text-danger-strong' : 'text-text-subtle'">
            {{ stats.failed_count }}
          </div>
        </div>
      </div>

      <!-- Per-template breakdown -->
      <div class="bg-surface rounded-xl border border-border-muted shadow-card mb-8 overflow-hidden">
        <div class="px-6 py-4 border-b border-border-muted">
          <h2 class="text-sm font-semibold text-text-default">Por Plantilla</h2>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full min-w-[36rem] table-fixed text-sm">
            <thead class="bg-surface-muted">
              <tr>
                <th class="w-2/5 text-left px-6 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Plantilla</th>
                <th class="text-center px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Total</th>
                <th class="text-center px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Exitosos</th>
                <th class="text-center px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Fallidos</th>
                <th class="text-center px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Tasa</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border-muted">
              <tr v-for="tpl in stats.by_template" :key="tpl.template_key" class="hover:bg-surface-muted transition-colors">
                <td class="px-6 py-3 font-medium text-text-default">
                  <code
                    class="inline-block min-w-0 max-w-full whitespace-normal rounded bg-surface-raised px-2 py-0.5 text-xs [overflow-wrap:anywhere]"
                    :title="tpl.template_key"
                  >{{ tpl.template_key }}</code>
                </td>
                <td class="px-4 py-3 text-center text-text-muted tabular-nums">{{ tpl.total }}</td>
                <td class="px-4 py-3 text-center text-text-brand tabular-nums">{{ tpl.sent }}</td>
                <td class="px-4 py-3 text-center tabular-nums" :class="tpl.failed > 0 ? 'text-danger-strong font-medium' : 'text-text-subtle'">{{ tpl.failed }}</td>
                <td class="px-4 py-3 text-center">
                  <span class="inline-block px-2 py-0.5 rounded-full text-xs font-medium"
                    :class="tpl.success_rate >= 95 ? 'bg-primary-soft text-text-brand' : tpl.success_rate >= 80 ? 'bg-warning-soft text-warning-strong' : 'bg-danger-soft text-danger-strong'">
                    {{ tpl.success_rate }}%
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!stats.by_template.length" class="px-6 py-8 text-center text-text-subtle text-sm">
          No hay datos de email en los últimos 30 días.
        </div>
      </div>

      <!-- Daily trend (simple bar chart) -->
      <div v-if="stats.daily_trend.length" class="bg-surface rounded-xl border border-border-muted shadow-card mb-8 overflow-hidden">
        <div class="px-6 py-4 border-b border-border-muted">
          <h2 class="text-sm font-semibold text-text-default">Tendencia Diaria</h2>
        </div>
        <div class="px-6 py-4">
          <div class="flex items-end gap-1 h-32">
            <div
              v-for="day in stats.daily_trend"
              :key="day.date"
              class="flex-1 flex flex-col items-center justify-end h-full group relative"
            >
              <div
                class="w-full rounded-t transition-all"
                :class="day.failed > 0 ? 'bg-danger-strong' : 'bg-success-strong'"
                :style="{ height: `${Math.max(4, (day.total / maxDailyTotal) * 100)}%` }"
              />
              <div class="absolute bottom-full mb-1 hidden group-hover:block bg-primary-strong text-white shadow-raised text-[10px] px-2 py-1 rounded whitespace-nowrap z-10">
                {{ day.date }}: {{ day.total }} emails
                <span v-if="day.failed > 0" class="text-danger-soft">({{ day.failed }} fallidos)</span>
              </div>
            </div>
          </div>
          <div class="flex justify-between mt-2 text-[10px] text-text-subtle">
            <span>{{ stats.daily_trend[0]?.date }}</span>
            <span>{{ stats.daily_trend[stats.daily_trend.length - 1]?.date }}</span>
          </div>
        </div>
      </div>

      <!-- Recent failures -->
      <div v-if="stats.recent_failures.length" class="bg-surface rounded-xl border border-danger-strong/30 shadow-card overflow-hidden">
        <div class="px-6 py-4 border-b border-danger-strong/30 bg-danger-soft">
          <h2 class="text-sm font-semibold text-danger-strong">Fallos Recientes ({{ stats.recent_failures.length }})</h2>
        </div>
        <div class="divide-y divide-border-muted">
          <div v-for="(failure, idx) in stats.recent_failures" :key="idx" class="px-6 py-3 text-sm">
            <div class="flex flex-wrap items-center gap-2 mb-1">
              <code class="text-xs bg-surface-raised px-2 py-0.5 rounded">{{ failure.template_key }}</code>
              <span class="text-text-subtle">→</span>
              <span class="text-text-default font-medium">{{ failure.recipient }}</span>
              <span class="text-xs px-1.5 py-0.5 rounded-full font-medium"
                :class="failure.status === 'bounced' ? 'bg-warning-soft text-warning-strong' : 'bg-danger-soft text-danger-strong'">
                {{ failure.status }}
              </span>
              <span class="text-xs text-text-subtle ml-auto">{{ formatDate(failure.sent_at) }}</span>
            </div>
            <p
              v-if="failure.error_message"
              class="max-w-full truncate text-xs text-danger-strong"
              :title="failure.error_message"
            >
              {{ failure.error_message }}
            </p>
          </div>
        </div>
      </div>
    </template>

    <!-- Empty state -->
    <div v-else class="text-center py-16">
      <div class="text-4xl mb-3">📭</div>
      <p class="text-text-muted text-sm">No se pudieron cargar las estadísticas de email.</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { formatDateTime } from '~/utils/formatDate';
import { useProposalStore } from '~/stores/proposals';

const { t } = useI18n();

const proposalStore = useProposalStore();
defineExpose({ refresh: loadStats });

const stats = ref(null);
const isLoading = ref(false);

const maxDailyTotal = computed(() => {
  if (!stats.value?.daily_trend?.length) return 1;
  return Math.max(1, ...stats.value.daily_trend.map(d => d.total));
});

function formatDate(isoStr) {
  return formatDateTime(isoStr, { fallback: '' });
}

async function loadStats() {
  if (isLoading.value) return;
  isLoading.value = true;
  try {
    const result = await proposalStore.fetchEmailDeliverability();
    stats.value = result.success ? result.data : null;
  } finally {
    isLoading.value = false;
  }
}

onMounted(() => {
  loadStats();
});


</script>
