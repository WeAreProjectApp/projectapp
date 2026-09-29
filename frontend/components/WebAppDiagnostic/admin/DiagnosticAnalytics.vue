<template>
  <div class="space-y-6">
    <!-- Loading -->
    <div v-if="loading" class="space-y-4" data-testid="analytics-loading" aria-busy="true">
      <BaseSkeleton variant="card" class="w-full" />
      <div class="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <BaseSkeleton v-for="n in 6" :key="n" variant="card" />
      </div>
    </div>

    <!-- Load error (distinct from "never viewed") -->
    <BaseEmptyState
      v-else-if="loadError"
      data-testid="analytics-error-state"
      title="No se pudo cargar la analítica"
      :description="loadError"
    >
      <template #actions>
        <BaseButton variant="secondary" size="md" @click="refresh">Reintentar</BaseButton>
      </template>
    </BaseEmptyState>

    <!-- No data yet -->
    <BaseEmptyState
      v-else-if="!analytics"
      title="Este diagnóstico aún no ha sido visto"
      description="Cuando el cliente abra el enlace público, aquí verás sus sesiones, recorrido y señales de interés."
    />

    <template v-else>
      <!-- ── Summary band: score + suggestions first ── -->
      <div class="grid lg:grid-cols-[minmax(0,20rem)_1fr] gap-4 items-stretch">
        <!-- Engagement score -->
        <div
          v-if="analytics.engagement_score != null"
          class="bg-surface rounded-xl border shadow-card p-5 flex items-center gap-5"
          :class="scoreTone.border"
        >
          <div
            class="w-16 h-16 rounded-2xl flex items-center justify-center text-2xl font-bold text-white shrink-0"
            :class="scoreTone.tile"
          >
            {{ animatedScore }}
          </div>
          <div>
            <div class="flex items-center gap-1.5">
              <h3 class="text-sm font-medium text-text-default">Engagement score</h3>
              <BaseTooltip position="right" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted motion-safe:transition-colors motion-safe:duration-fast" />
                </template>
                {{ tt.engagementScore }}
              </BaseTooltip>
            </div>
            <p class="text-xs text-text-muted mt-1">{{ scoreTone.text }}</p>
          </div>
        </div>

        <!-- Suggested actions — the reason this page exists -->
        <div
          v-if="suggestions.length"
          class="bg-warning-soft border border-warning-strong/30 rounded-xl shadow-card p-4"
          data-testid="analytics-suggestions"
        >
          <div class="flex items-center gap-1.5 mb-2">
            <h3 class="text-sm font-medium text-warning-strong">💡 Acciones sugeridas</h3>
            <BaseTooltip position="right" width="max-w-2xl">
              <template #trigger>
                <QuestionMarkCircleIcon class="w-4 h-4 text-warning-strong/60 hover:text-warning-strong motion-safe:transition-colors motion-safe:duration-fast" />
              </template>
              {{ tt.suggestedActions }}
            </BaseTooltip>
          </div>
          <ul class="space-y-2">
            <li
              v-for="(s, i) in suggestions"
              :key="i"
              class="flex items-start gap-2 text-sm text-warning-strong"
            >
              <span class="mt-0.5 flex-shrink-0" aria-hidden="true">{{ s.icon }}</span>
              <span>{{ s.text }}</span>
            </li>
          </ul>
        </div>
        <div
          v-else
          class="bg-surface rounded-xl border border-border-muted shadow-card p-4 flex items-center"
        >
          <p class="text-sm text-text-muted">Sin acciones pendientes — el recorrido del cliente no muestra señales que requieran follow-up inmediato.</p>
        </div>
      </div>

      <!-- Skipped sections -->
      <div
        v-if="analytics.skipped_sections?.length"
        class="bg-danger-soft border border-danger-strong/30 rounded-xl shadow-card p-4"
      >
        <div class="flex items-center gap-1.5 mb-2">
          <h3 class="text-sm font-medium text-danger-strong">⚠️ Secciones no visitadas</h3>
          <BaseTooltip position="right" width="max-w-2xl">
            <template #trigger>
              <QuestionMarkCircleIcon class="w-4 h-4 text-danger-strong/60 hover:text-danger-strong motion-safe:transition-colors motion-safe:duration-fast" />
            </template>
            {{ tt.skippedSections }}
          </BaseTooltip>
        </div>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="s in analytics.skipped_sections"
            :key="s.section_type"
            class="inline-flex items-center px-3 py-1.5 bg-surface border border-danger-strong/40 rounded-lg text-xs text-danger-strong font-medium"
          >
            {{ s.section_title }}
          </span>
        </div>
      </div>

      <!-- KPI cards -->
      <div class="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <div v-for="kpi in kpiCards" :key="kpi.label" class="bg-surface rounded-xl border border-border-muted shadow-card p-4">
          <div class="flex items-center gap-1">
            <p class="text-2xs text-text-muted uppercase tracking-wider">{{ kpi.label }}</p>
            <BaseTooltip position="bottom" width="max-w-2xl">
              <template #trigger>
                <QuestionMarkCircleIcon class="w-3.5 h-3.5 text-text-subtle hover:text-text-muted motion-safe:transition-colors motion-safe:duration-fast" />
              </template>
              {{ kpi.tooltip }}
            </BaseTooltip>
          </div>
          <p class="mt-1 font-light" :class="[kpi.small ? 'text-sm' : 'text-2xl', kpi.valueClass || 'text-text-default']">
            {{ kpi.value }}
          </p>
        </div>
      </div>

      <!-- ── Detail tabs ── -->
      <div class="flex items-center justify-between gap-3">
        <BaseTabs
          v-model="activeSection"
          :tabs="[
            { id: 'journey', label: 'Recorrido' },
            { id: 'sessions', label: 'Sesiones' },
            { id: 'activity', label: 'Actividad' },
            { id: 'comparison', label: 'Comparativa' },
          ]"
        />
        <BaseButton variant="secondary" size="md" class="shrink-0" :loading="csvDownload.loading.value" @click="downloadCSV">
          <BaseActionIcon action="export" />
          Exportar CSV
        </BaseButton>
      </div>

      <!-- Recorrido -->
      <div v-show="activeSection === 'journey'" class="space-y-6">
        <div v-if="analytics.funnel?.length" class="bg-surface rounded-xl border border-border-muted shadow-card">
          <div class="px-4 sm:px-6 py-4 border-b border-border-muted">
            <div class="flex items-center gap-1.5">
              <h3 class="text-sm font-medium text-text-default">Funnel de navegación</h3>
              <BaseTooltip position="right" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted motion-safe:transition-colors motion-safe:duration-fast" />
                </template>
                {{ tt.funnel }}
              </BaseTooltip>
            </div>
            <p class="text-xs text-text-subtle mt-0.5">Porcentaje de sesiones que alcanzaron cada sección</p>
          </div>
          <div class="px-2 sm:px-4 py-2">
            <ClientOnly>
              <LazyApexChart
                type="bar"
                :height="funnelChartHeight"
                :options="funnelChartOptions"
                :series="funnelChartSeries"
              />
              <template #fallback>
                <div class="h-48 m-4 rounded-xl bg-surface-raised motion-safe:animate-pulse" />
              </template>
            </ClientOnly>
          </div>
          <div class="px-4 sm:px-6 pb-4 space-y-1">
            <p
              v-for="step in analytics.funnel.filter((s) => s.drop_off_percent > 0)"
              :key="step.section_type"
              class="text-xs text-danger-strong"
            >
              {{ step.section_title }}: -{{ step.drop_off_percent }}% de abandono
            </p>
          </div>
        </div>

        <div v-if="sortedSections.length" class="bg-surface rounded-xl border border-border-muted shadow-card">
          <div class="px-4 sm:px-6 py-4 border-b border-border-muted">
            <div class="flex items-center gap-1.5">
              <h3 class="text-sm font-medium text-text-default">🔥 Heatmap de interés</h3>
              <BaseTooltip position="right" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted motion-safe:transition-colors motion-safe:duration-fast" />
                </template>
                {{ tt.heatmap }}
              </BaseTooltip>
            </div>
            <p class="text-xs text-text-subtle mt-0.5">Secciones ordenadas por tiempo total — las más calientes son las que más le importan al cliente</p>
          </div>
          <div class="px-4 sm:px-6 py-4 space-y-3">
            <div v-for="(section, idx) in sortedSections" :key="section.section_type" class="flex items-center gap-3">
              <span class="text-base w-5 flex-shrink-0" aria-hidden="true">{{ heatEmoji(idx, sortedSections.length) }}</span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between mb-1 gap-2">
                  <span class="text-sm font-medium text-text-default truncate">{{ section.section_title }}</span>
                  <span class="text-xs text-text-muted flex-shrink-0 tabular-nums">{{ formatTime(section.total_time_seconds) }}</span>
                </div>
                <div class="w-full bg-surface-raised rounded-full h-2.5">
                  <div
                    class="h-2.5 rounded-full motion-safe:transition-all motion-safe:duration-slow motion-safe:ease-out-soft"
                    :class="heatBarColor(idx, sortedSections.length)"
                    :style="{ width: heatBarWidth(section.total_time_seconds) + '%' }"
                  />
                </div>
              </div>
            </div>
          </div>
          <div v-if="sectionInsights.length" class="px-4 sm:px-6 pb-4 space-y-2">
            <div
              v-for="insight in sectionInsights"
              :key="insight.type"
              class="flex items-start gap-2 bg-primary-soft border border-border-muted rounded-xl px-4 py-3"
            >
              <span class="text-base flex-shrink-0" aria-hidden="true">{{ insight.icon }}</span>
              <div>
                <p class="text-xs font-semibold text-text-brand">{{ insight.label }}</p>
                <p class="text-xs text-text-brand mt-0.5">{{ insight.text }}</p>
              </div>
            </div>
          </div>
        </div>

        <div class="bg-surface rounded-xl border border-border-muted shadow-card">
          <div class="px-4 sm:px-6 py-4 border-b border-border-muted">
            <div class="flex items-center gap-1.5">
              <h3 class="text-sm font-medium text-text-default">Engagement por sección</h3>
              <BaseTooltip position="right" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted motion-safe:transition-colors motion-safe:duration-fast" />
                </template>
                {{ tt.sectionEngagement }}
              </BaseTooltip>
            </div>
            <p class="text-xs text-text-subtle mt-0.5">Tiempo que el cliente pasó en cada sección</p>
          </div>
          <div v-if="analytics.sections.length" class="overflow-x-auto rounded-b-xl overflow-hidden">
            <table class="w-full text-sm">
              <thead>
                <tr class="bg-surface-raised text-left text-xs text-text-muted uppercase tracking-wider">
                  <th class="px-4 sm:px-6 py-3">Sección</th>
                  <th class="px-4 py-3 text-center">Visitas</th>
                  <th class="px-4 py-3 text-right">Tiempo total</th>
                  <th class="px-4 py-3 text-right">Promedio</th>
                  <th class="px-4 sm:px-6 py-3">Engagement</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-border-muted">
                <tr v-for="section in analytics.sections" :key="section.section_type" class="hover:bg-surface-muted">
                  <td class="px-4 sm:px-6 py-3">
                    <span class="font-medium text-text-default">{{ section.section_title }}</span>
                  </td>
                  <td class="px-4 py-3 text-center text-text-muted">{{ section.visit_count }}</td>
                  <td class="px-4 py-3 text-right text-text-muted">{{ formatTime(section.total_time_seconds) }}</td>
                  <td class="px-4 py-3 text-right text-text-muted">{{ formatTime(section.avg_time_seconds) }}</td>
                  <td class="px-4 sm:px-6 py-3">
                    <div class="flex items-center gap-2">
                      <div class="flex-1 bg-surface-raised rounded-full h-2 max-w-[120px]">
                        <div
                          class="h-2 rounded-full motion-safe:transition-all motion-safe:duration-slow motion-safe:ease-out-soft"
                          :class="barColor(section.avg_time_seconds)"
                          :style="{ width: barWidth(section.avg_time_seconds) + '%' }"
                        />
                      </div>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="px-6 py-8 text-center text-text-subtle text-sm">
            Aún no hay datos de engagement por sección.
          </div>
        </div>
      </div>

      <!-- Sesiones -->
      <div v-show="activeSection === 'sessions'" class="space-y-6">
        <div v-if="hasDeviceData" class="bg-surface rounded-xl border border-border-muted shadow-card p-4">
          <div class="flex items-center gap-1.5 mb-3">
            <h3 class="text-sm font-medium text-text-default">Dispositivos</h3>
            <BaseTooltip position="right" width="max-w-2xl">
              <template #trigger>
                <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted motion-safe:transition-colors motion-safe:duration-fast" />
              </template>
              {{ tt.devices }}
            </BaseTooltip>
          </div>
          <div class="flex gap-6 text-sm">
            <div class="flex items-center gap-2">
              <span class="text-lg" aria-hidden="true">🖥️</span>
              <span class="text-text-muted">Desktop: <strong>{{ analytics.device_breakdown.desktop }}</strong></span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-lg" aria-hidden="true">📱</span>
              <span class="text-text-muted">Mobile: <strong>{{ analytics.device_breakdown.mobile }}</strong></span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-lg" aria-hidden="true">📋</span>
              <span class="text-text-muted">Tablet: <strong>{{ analytics.device_breakdown.tablet }}</strong></span>
            </div>
          </div>
        </div>

        <div class="bg-surface rounded-xl border border-border-muted shadow-card">
          <div class="px-4 sm:px-6 py-4 border-b border-border-muted">
            <div class="flex items-center gap-1.5">
              <h3 class="text-sm font-medium text-text-default">Historial de sesiones</h3>
              <BaseTooltip position="right" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted motion-safe:transition-colors motion-safe:duration-fast" />
                </template>
                {{ tt.sessionHistory }}
              </BaseTooltip>
            </div>
            <p class="text-xs text-text-subtle mt-0.5">Últimas 50 sesiones de navegación</p>
          </div>
          <div v-if="analytics.sessions.length" class="overflow-x-auto rounded-b-xl overflow-hidden">
            <table class="w-full text-sm">
              <thead>
                <tr class="bg-surface-raised text-left text-xs text-text-muted uppercase tracking-wider">
                  <th class="px-4 sm:px-6 py-3">Sesión</th>
                  <th class="px-4 py-3">Fecha</th>
                  <th class="px-4 py-3 text-center">Secciones vistas</th>
                  <th class="px-4 sm:px-6 py-3 text-right">Tiempo total</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-border-muted">
                <tr v-for="session in analytics.sessions" :key="session.session_id" class="hover:bg-surface-muted">
                  <td class="px-4 sm:px-6 py-3">
                    <span class="font-mono text-xs text-text-muted">{{ (session.session_id || '').slice(0, 12) }}...</span>
                    <span v-if="session.ip_address" class="text-xs text-text-subtle ml-2">{{ session.ip_address }}</span>
                  </td>
                  <td class="px-4 py-3 text-text-muted">{{ formatDate(session.viewed_at) }}</td>
                  <td class="px-4 py-3 text-center text-text-muted">{{ session.sections_viewed }}</td>
                  <td class="px-4 sm:px-6 py-3 text-right text-text-muted">{{ formatTime(session.total_time_seconds) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="px-6 py-8 text-center text-text-subtle text-sm">
            Aún no hay sesiones registradas.
          </div>
        </div>
      </div>

      <!-- Actividad -->
      <div v-show="activeSection === 'activity'" class="bg-surface rounded-xl border border-border-muted shadow-card">
        <div class="px-4 sm:px-6 py-4 border-b border-border-muted">
          <div class="flex items-center gap-1.5">
            <h3 class="text-sm font-medium text-text-default">Historial de actividad</h3>
            <BaseTooltip position="right" width="max-w-2xl">
              <template #trigger>
                <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted motion-safe:transition-colors motion-safe:duration-fast" />
              </template>
              {{ tt.activityTimeline }}
            </BaseTooltip>
          </div>
          <p class="text-xs text-text-subtle mt-0.5">Timeline cronológico de eventos del diagnóstico</p>
        </div>
        <div v-if="analytics.timeline?.length" class="px-4 sm:px-6 py-4">
          <div class="relative">
            <div class="absolute left-4 top-0 bottom-0 w-px bg-border-default"></div>
            <div v-for="(event, idx) in analytics.timeline" :key="idx" class="relative pl-10 pb-5 last:pb-0">
              <div class="absolute left-2.5 w-3 h-3 rounded-full border-2 border-surface" :class="timelineColor(event.change_type)"></div>
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-xs font-medium px-2 py-0.5 rounded-full" :class="timelineBadge(event.change_type)">
                  {{ timelineIcon(event.change_type) }} {{ timelineLabel(event.change_type) }}
                </span>
                <span class="text-2xs font-medium px-1.5 py-0.5 rounded-full" :class="actorBadgeClass(event.actor_type)">
                  {{ actorLabel(event.actor_type) }}
                </span>
                <span class="text-xs text-text-subtle">{{ formatDate(event.created_at) }}</span>
              </div>
              <!-- eslint-disable-next-line vue/no-v-html -->
              <div class="text-sm text-text-muted mt-1" v-html="formatTimelineDescription(event)"></div>
            </div>
          </div>
        </div>
        <div v-else class="px-6 py-8 text-center text-text-subtle text-sm">
          Aún no hay eventos registrados.
        </div>
      </div>

      <!-- Comparativa -->
      <div v-show="activeSection === 'comparison'">
        <div v-if="analytics.comparison" class="bg-surface rounded-xl border border-border-muted shadow-card">
          <div class="px-4 py-3 border-b border-border-muted">
            <div class="flex items-center gap-1.5">
              <h3 class="text-sm font-medium text-text-default">Comparación con promedio global</h3>
              <BaseTooltip position="right" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted motion-safe:transition-colors motion-safe:duration-fast" />
                </template>
                {{ tt.globalComparison }}
              </BaseTooltip>
            </div>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 p-4">
            <div class="flex items-center gap-3 p-3 rounded-lg" :class="comparisonClass('ttfv')">
              <div class="text-2xl" aria-hidden="true">{{ comparisonEmoji('ttfv') }}</div>
              <div>
                <p class="text-xs text-text-muted">Tiempo a 1ra vista</p>
                <p class="text-sm font-medium">
                  {{ analytics.time_to_first_view_hours != null ? analytics.time_to_first_view_hours + 'h' : '—' }}
                  <span v-if="analytics.comparison.avg_time_to_first_view_hours != null" class="text-xs text-text-subtle">
                    vs {{ analytics.comparison.avg_time_to_first_view_hours }}h avg
                  </span>
                </p>
              </div>
            </div>
            <div class="flex items-center gap-3 p-3 rounded-lg" :class="comparisonClass('ttr')">
              <div class="text-2xl" aria-hidden="true">{{ comparisonEmoji('ttr') }}</div>
              <div>
                <p class="text-xs text-text-muted">Tiempo a respuesta</p>
                <p class="text-sm font-medium">
                  {{ analytics.time_to_response_hours != null ? analytics.time_to_response_hours + 'h' : '—' }}
                  <span v-if="analytics.comparison.avg_time_to_response_hours != null" class="text-xs text-text-subtle">
                    vs {{ analytics.comparison.avg_time_to_response_hours }}h avg
                  </span>
                </p>
              </div>
            </div>
            <div class="flex items-center gap-3 p-3 rounded-lg" :class="comparisonClass('views')">
              <div class="text-2xl" aria-hidden="true">{{ comparisonEmoji('views') }}</div>
              <div>
                <p class="text-xs text-text-muted">Total vistas</p>
                <p class="text-sm font-medium">
                  {{ analytics.total_views }}
                  <span v-if="analytics.comparison.avg_views != null" class="text-xs text-text-subtle">
                    vs {{ analytics.comparison.avg_views }} avg
                  </span>
                </p>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="px-6 py-8 text-center text-text-subtle text-sm bg-surface rounded-xl border border-border-muted shadow-card">
          Aún no hay datos de otros diagnósticos para comparar.
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { QuestionMarkCircleIcon } from '@heroicons/vue/24/outline';
import { usePanelDownload } from '~/composables/usePanelDownload';
const csvDownload = usePanelDownload();
import BaseTabs from '~/components/base/BaseTabs.vue';
import BaseTooltip from '~/components/base/BaseTooltip.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import BaseSkeleton from '~/components/base/BaseSkeleton.vue';
import { useAnimatedNumber } from '~/composables/useAnimatedNumber';
import { useChartTheme } from '~/composables/useChartTheme';
import { DIAGNOSTIC_ANALYTICS_THRESHOLDS as T } from '~/stores/diagnostics_constants';
import { formatDateTime as formatDate } from '~/utils/formatDate';

const { analytics: tt } = useTooltipTexts();

const props = defineProps({
  diagnosticId: { type: [Number, String], required: true },
  loader: { type: Function, required: true },
  diagnostic: { type: Object, default: null },
});

const loading = ref(true);
const loadError = ref('');
const analytics = ref(null);
const activeSection = ref('journey');

const hasDeviceData = computed(() => {
  const d = analytics.value?.device_breakdown;
  return d && (d.desktop || d.mobile || d.tablet);
});

const lastVisitedAt = computed(() => {
  const data = analytics.value;
  if (!data) return null;
  return data.last_viewed_at || data.sessions?.[0]?.viewed_at || data.first_viewed_at || null;
});

const totalReadingTime = computed(() => {
  const sections = analytics.value?.sections;
  if (!sections?.length) return 0;
  return sections.reduce((sum, s) => sum + (s.total_time_seconds || 0), 0);
});

const sectionCoverage = computed(() => {
  const visited = analytics.value?.sections?.length || 0;
  const skipped = analytics.value?.skipped_sections?.length || 0;
  const total = visited + skipped;
  if (total === 0) return null;
  return Math.round((visited / total) * 100);
});

const sortedSections = computed(() => {
  if (!analytics.value?.sections?.length) return [];
  return [...analytics.value.sections].sort(
    (a, b) => (b.total_time_seconds || 0) - (a.total_time_seconds || 0),
  );
});

// ── Score presentation ──────────────────────────────────────────────────
const engagementScore = computed(() => analytics.value?.engagement_score ?? 0);
const { animated: animatedScore } = useAnimatedNumber(engagementScore);

const scoreTone = computed(() => {
  const score = engagementScore.value;
  if (score >= T.ENGAGEMENT.HIGH) {
    return {
      tile: 'bg-success-strong',
      border: 'border-success-strong/30',
      text: 'Alto engagement — prioridad de follow-up',
    };
  }
  if (score >= T.ENGAGEMENT.MEDIUM) {
    return {
      tile: 'bg-warning-strong',
      border: 'border-warning-strong/30',
      text: 'Engagement moderado',
    };
  }
  return {
    tile: 'bg-danger-strong',
    border: 'border-danger-strong/30',
    text: 'Bajo engagement — necesita atención',
  };
});

const kpiCards = computed(() => {
  const a = analytics.value;
  if (!a) return [];
  const coverage = sectionCoverage.value;
  return [
    { label: 'Vistas', tooltip: tt.views, value: a.total_views },
    { label: 'Sesiones', tooltip: tt.sessions, value: a.unique_sessions },
    { label: 'Primera vista', tooltip: tt.firstView, value: a.first_viewed_at ? formatDate(a.first_viewed_at) : '—', small: true },
    { label: 'Tiempo de lectura', tooltip: tt.readingTime, value: formatTime(totalReadingTime.value) },
    {
      label: 'Cobertura',
      tooltip: tt.coverage,
      value: coverage != null ? coverage + '%' : '—',
      valueClass: coverage == null
        ? 'text-text-default'
        : coverage >= T.COVERAGE.GOOD
          ? 'text-success-strong'
          : coverage >= T.COVERAGE.WARN
            ? 'text-warning-strong'
            : 'text-danger-strong',
    },
    { label: 'Última visita', tooltip: tt.lastVisit, value: lastVisitedAt.value ? formatDate(lastVisitedAt.value) : '—', small: true },
  ];
});

// ── Funnel chart (ApexCharts via the shared panel theme) ────────────────
const { palette, baseOptions } = useChartTheme();

const funnelChartSeries = computed(() => [{
  name: 'Sesiones que llegaron',
  data: (analytics.value?.funnel || []).map((step) => funnelBarWidth(step)),
}]);

const funnelChartHeight = computed(() =>
  Math.max(160, (analytics.value?.funnel?.length || 0) * 44 + 60),
);

const funnelChartOptions = computed(() => ({
  ...baseOptions.value,
  colors: [palette.value.measures?.[0] || palette.value.categorical?.[0]],
  plotOptions: {
    bar: { horizontal: true, borderRadius: 4, barHeight: '55%' },
  },
  dataLabels: {
    enabled: true,
    formatter: (val) => `${val}%`,
  },
  xaxis: {
    categories: (analytics.value?.funnel || []).map((s) => s.section_title),
    max: 100,
    labels: { formatter: (val) => `${val}%` },
    axisBorder: { show: false },
    axisTicks: { show: false },
  },
  tooltip: {
    ...baseOptions.value.tooltip,
    y: { formatter: (val, opts) => {
      const step = analytics.value?.funnel?.[opts.dataPointIndex];
      return step ? `${val}% (${step.reached_count} sesiones)` : `${val}%`;
    } },
  },
}));

const SECTION_INSIGHTS = {
  cost: {
    icon: '💰',
    label: 'Interés en el costo',
    text: 'Revisó en detalle la inversión del diagnóstico. Refuerza el ROI y opciones de pago en el seguimiento.',
  },
  scope: {
    icon: '📋',
    label: 'Duda sobre el alcance',
    text: 'Pasó tiempo en alcance y consideraciones. Clarifica los entregables y límites antes de la siguiente llamada.',
  },
  timeline: {
    icon: '⏱️',
    label: 'Preocupación por plazos',
    text: 'Invirtió tiempo en el cronograma. En el follow-up, enfócate en velocidad de ejecución y el primer entregable.',
  },
  purpose: {
    icon: '🎯',
    label: 'Entiende la severidad',
    text: 'Leyó con atención el propósito y la escala de severidad. Ya tienes su atención sobre el dolor a resolver.',
  },
  radiography: {
    icon: '🩻',
    label: 'Reconoció su radiografía',
    text: 'Pasó tiempo revisando la radiografía de su aplicación. Úsala como ancla en el próximo contacto.',
  },
  categories: {
    icon: '🗂️',
    label: 'Revisó categorías evaluadas',
    text: 'Examinó las categorías evaluadas. Prepárate para profundizar en las que más le interesaron.',
  },
  executive_summary: {
    icon: '📑',
    label: 'Leyó el resumen ejecutivo',
    text: 'Se detuvo en el resumen ejecutivo — probablemente lo compartirá con otros stakeholders. Prepara material de apoyo.',
  },
  delivery_structure: {
    icon: '🏗️',
    label: 'Evalúa la estructura de entrega',
    text: 'Pasó tiempo en la estructura de entrega. Ofrece una llamada para alinear ritmo y puntos de control.',
  },
};

const sectionInsights = computed(() => {
  if (!sortedSections.value.length) return [];
  const top = sortedSections.value.slice(0, 2);
  const insights = [];
  for (const sec of top) {
    const def = SECTION_INSIGHTS[sec.section_type];
    if (def && sec.total_time_seconds >= 10) {
      insights.push({ type: sec.section_type, ...def });
    }
  }
  return insights;
});

const suggestions = computed(() => {
  if (!analytics.value) return [];
  const list = [];
  const a = analytics.value;
  const status = props.diagnostic?.status;

  const skippedTypes = (a.skipped_sections || []).map((s) => s.section_type);

  if (skippedTypes.includes('cost')) {
    list.push({
      icon: '💰',
      text: 'El cliente no vio la sección de Costo y formas de pago — envía un resumen por email o menciónalo en el próximo contacto.',
    });
  }

  if (skippedTypes.includes('scope')) {
    list.push({
      icon: '📋',
      text: 'No revisó Alcance y consideraciones — confirma expectativas antes de avanzar para evitar malentendidos.',
    });
  }

  if (a.total_views >= 3 && !a.responded_at) {
    list.push({
      icon: '🔥',
      text: `El cliente revisó el diagnóstico ${a.total_views} veces sin responder — señal de interés, haz un follow-up en caliente.`,
    });
  }

  skippedTypes
    .filter((t) => !['cost', 'scope'].includes(t))
    .forEach((t) => {
      const section = (a.skipped_sections || []).find((s) => s.section_type === t);
      if (section) {
        list.push({
          icon: '👁️',
          text: `El cliente no vio «${section.section_title}» — menciónala en el próximo contacto.`,
        });
      }
    });

  if (a.time_to_first_view_hours != null && a.time_to_first_view_hours > 24) {
    list.push({
      icon: '📬',
      text: `El cliente tardó ${a.time_to_first_view_hours}h en abrir el diagnóstico — verifica que el email llegó o considera reenviarlo.`,
    });
  }

  if (status === 'rejected') {
    list.push({
      icon: '🔄',
      text: 'Diagnóstico rechazado — considera ajustar alcance o presupuesto para retomar la negociación.',
    });
  }

  if (a.unique_sessions === 1 && !a.responded_at && status === 'sent') {
    list.push({
      icon: '📞',
      text: 'El cliente abrió el diagnóstico una sola vez — un seguimiento por llamada o WhatsApp puede aumentar la probabilidad de respuesta.',
    });
  }

  return list;
});

async function refresh() {
  loading.value = true;
  loadError.value = '';
  try {
    const result = await props.loader();
    if (result?.success) {
      analytics.value = result.data;
    } else if (result && result.success === false) {
      analytics.value = null;
      loadError.value = result.message || result.error || 'Ocurrió un error al cargar la analítica.';
    } else {
      analytics.value = result?.data || null;
    }
  } catch (error) {
    analytics.value = null;
    loadError.value = 'Ocurrió un error al cargar la analítica.';
  } finally {
    loading.value = false;
  }
}

watch(() => props.diagnosticId, refresh);
onMounted(refresh);

defineExpose({ refresh });

function downloadCSV() {
  const url = `/api/diagnostics/${props.diagnosticId}/analytics/csv/`;
  csvDownload.download(url, 'diagnostics-analytics.csv', 'text/csv');
}

function formatTime(seconds) {
  if (!seconds || seconds < 1) return '< 1s';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}

function barWidth(avgSeconds) {
  return Math.min(100, (avgSeconds / T.SECTION_BAR_MAX_SECONDS) * 100);
}

function barColor(avgSeconds) {
  if (avgSeconds >= T.SECTION_AVG_SECONDS.HIGH) return 'bg-success-strong';
  if (avgSeconds >= T.SECTION_AVG_SECONDS.MID) return 'bg-info-strong';
  if (avgSeconds >= T.SECTION_AVG_SECONDS.LOW) return 'bg-warning-strong';
  return 'bg-border-default';
}

function heatBarWidth(totalSeconds) {
  if (!sortedSections.value.length) return 0;
  const max = sortedSections.value[0].total_time_seconds || 1;
  return Math.min(100, Math.round((totalSeconds / max) * 100));
}

function heatBarColor(idx, total) {
  const ratio = total <= 1 ? 1 : idx / (total - 1);
  const [hottest, hot, warm, mild] = T.HEAT_RATIOS;
  if (ratio <= hottest) return 'bg-danger-strong';
  if (ratio <= hot) return 'bg-warning-strong';
  if (ratio <= warm) return 'bg-warning-strong/70';
  if (ratio <= mild) return 'bg-warning-strong/40';
  return 'bg-border-default';
}

function heatEmoji(idx, total) {
  const ratio = total <= 1 ? 1 : idx / (total - 1);
  const [hottest, hot, warm] = T.HEAT_RATIOS;
  if (ratio <= hottest) return '🔴';
  if (ratio <= hot) return '🟠';
  if (ratio <= warm) return '🟡';
  return '⚪';
}

const TIMELINE_LABELS = {
  created: 'Creado',
  updated: 'Actualizado',
  section_updated: 'Sección actualizada',
  sent: 'Enviado',
  viewed: 'Visto',
  negotiating: 'Negociando',
  accepted: 'Aceptado',
  rejected: 'Rechazado',
  finished: 'Finalizado',
  email_sent: 'Email enviado',
  note: 'Nota',
  call: 'Llamada',
  meeting: 'Reunión',
  followup: 'Seguimiento',
  status_change: 'Cambio de estado',
};

const ACTOR_LABELS = { client: 'Cliente', seller: 'Ventas', system: 'Sistema', '': 'Sistema' };
const ACTOR_BADGE_CLASSES = {
  client: 'bg-info-soft text-info-strong border border-info-strong/30',
  seller: 'bg-primary-soft text-text-brand border border-border-muted',
  system: 'bg-surface-raised text-text-muted border border-border-default',
  '': 'bg-surface-raised text-text-muted border border-border-default',
};

const FIELD_LABELS = {
  title: 'Título',
  client_name: 'Nombre del cliente',
  client_email: 'Email del cliente',
  client_phone: 'Teléfono del cliente',
  client_company: 'Empresa del cliente',
  status: 'Estado',
  language: 'Idioma',
  default_currency: 'Moneda',
  default_investment_amount: 'Inversión',
};

function timelineLabel(type) { return TIMELINE_LABELS[type] || type; }

function actorLabel(actorType) { return ACTOR_LABELS[actorType || ''] || 'Sistema'; }

function actorBadgeClass(actorType) {
  return ACTOR_BADGE_CLASSES[actorType || ''] || ACTOR_BADGE_CLASSES[''];
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatTimelineDescription(event) {
  const desc = event.description || '';

  if (event.change_type === 'updated' && event.field_name) {
    const fieldLabel = FIELD_LABELS[event.field_name] || event.field_name;
    const oldDisplay = escapeHtml(event.old_value || '(vacío)');
    const newDisplay = `<strong>${escapeHtml(event.new_value || '(vacío)')}</strong>`;
    return `<strong>${escapeHtml(fieldLabel)}</strong>: ${oldDisplay} → ${newDisplay}`;
  }

  if (event.change_type === 'status_change' && event.old_value && event.new_value) {
    return `<strong>Estado</strong>: ${escapeHtml(event.old_value)} → <strong>${escapeHtml(event.new_value)}</strong>`;
  }

  return escapeHtml(desc);
}

function timelineIcon(type) {
  const icons = {
    created: '📝', updated: '✏️', section_updated: '🧩',
    sent: '📧', viewed: '👁️', negotiating: '🤝',
    accepted: '✅', rejected: '❌', finished: '🏁',
    email_sent: '📨', note: '📝', call: '📞',
    meeting: '🤝', followup: '📩', status_change: '🔄',
  };
  return icons[type] || '•';
}

function timelineColor(type) {
  const colors = {
    created: 'bg-info-strong', updated: 'bg-warning-strong', section_updated: 'bg-warning-strong',
    sent: 'bg-info-strong', viewed: 'bg-success-strong', negotiating: 'bg-info-strong',
    accepted: 'bg-success-strong', rejected: 'bg-danger-strong', finished: 'bg-success-strong',
    email_sent: 'bg-info-strong', note: 'bg-border-default', call: 'bg-info-strong/70',
    meeting: 'bg-info-strong', followup: 'bg-warning-strong', status_change: 'bg-info-strong',
  };
  return colors[type] || 'bg-border-default';
}

function timelineBadge(type) {
  const badges = {
    created: 'bg-info-soft text-info-strong',
    updated: 'bg-warning-soft text-warning-strong',
    section_updated: 'bg-warning-soft text-warning-strong',
    sent: 'bg-info-soft text-info-strong',
    viewed: 'bg-success-soft text-success-strong',
    negotiating: 'bg-info-soft text-info-strong',
    accepted: 'bg-success-soft text-success-strong',
    rejected: 'bg-danger-soft text-danger-strong',
    finished: 'bg-success-soft text-success-strong',
    email_sent: 'bg-info-soft text-info-strong',
    note: 'bg-surface-raised text-text-muted',
    call: 'bg-info-soft text-info-strong',
    meeting: 'bg-info-soft text-info-strong',
    followup: 'bg-warning-soft text-warning-strong',
    status_change: 'bg-info-soft text-info-strong',
  };
  return badges[type] || 'bg-surface-raised text-text-default';
}

function funnelBarWidth(step) {
  if (!analytics.value?.unique_sessions) return 0;
  return Math.round((step.reached_count / analytics.value.unique_sessions) * 100);
}

function comparisonClass(metric) {
  const c = analytics.value?.comparison;
  if (!c) return 'bg-surface-raised';
  if (metric === 'ttfv') {
    const val = analytics.value?.time_to_first_view_hours;
    const avg = c.avg_time_to_first_view_hours;
    if (val == null || avg == null) return 'bg-surface-raised';
    return val < avg ? 'bg-success-soft' : 'bg-warning-soft';
  }
  if (metric === 'ttr') {
    const val = analytics.value?.time_to_response_hours;
    const avg = c.avg_time_to_response_hours;
    if (val == null || avg == null) return 'bg-surface-raised';
    return val < avg ? 'bg-success-soft' : 'bg-warning-soft';
  }
  if (metric === 'views') {
    const val = analytics.value?.total_views;
    const avg = c.avg_views;
    if (val == null || avg == null) return 'bg-surface-raised';
    return val > avg ? 'bg-success-soft' : 'bg-warning-soft';
  }
  return 'bg-surface-raised';
}

function comparisonEmoji(metric) {
  const c = analytics.value?.comparison;
  if (!c) return '📊';
  if (metric === 'ttfv') {
    const val = analytics.value?.time_to_first_view_hours;
    const avg = c.avg_time_to_first_view_hours;
    if (val == null || avg == null) return '📊';
    return val < avg ? '🔥' : '🐢';
  }
  if (metric === 'ttr') {
    const val = analytics.value?.time_to_response_hours;
    const avg = c.avg_time_to_response_hours;
    if (val == null || avg == null) return '📊';
    return val < avg ? '⚡' : '⏳';
  }
  if (metric === 'views') {
    const val = analytics.value?.total_views;
    const avg = c.avg_views;
    if (val == null || avg == null) return '📊';
    return val > avg ? '👀' : '😴';
  }
  return '📊';
}
</script>
