<template>
  <div class="space-y-6">
    <!-- Loading: mirror the summary-cards + panel layout so the tab does not
         jump when the real content lands. -->
    <div v-if="loading" class="space-y-6" data-testid="analytics-skeleton">
      <span class="sr-only" role="status">Cargando analytics...</span>
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <BaseSkeleton v-for="n in 4" :key="n" variant="card" class="h-20" />
      </div>
      <BaseSkeleton variant="card" class="h-48" />
    </div>

    <!-- No data -->
    <div v-else-if="!analytics" class="text-center py-8 text-text-subtle text-sm">
      No hay datos de analytics disponibles.
    </div>

    <template v-else>
      <!-- CSV Export button -->
      <div class="flex justify-end">
        <BaseButton variant="secondary" size="md" :loading="csvDownload.loading.value" @click="downloadCSV">
        <BaseActionIcon action="export" />
          Exportar CSV
        </BaseButton>
      </div>

      <div
        v-if="firstViewNotification"
        data-testid="first-view-notification-status"
        class="rounded-xl border border-border-muted bg-surface p-4 shadow-sm"
      >
        <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p class="text-xs uppercase tracking-wider text-text-subtle">Alerta de primera vista</p>
            <div class="mt-1 flex flex-wrap items-center gap-2">
              <span
                class="rounded-full px-2 py-0.5 text-xs font-medium"
                :class="firstViewNotificationClass"
              >
                {{ firstViewNotificationLabel }}
              </span>
              <span class="text-xs text-text-muted">
                {{ firstViewNotification.attempts }} intento(s)
              </span>
            </div>
            <p v-if="firstViewNotification.sent_at" class="mt-2 text-xs text-text-muted">
              Correo confirmado: {{ formatDate(firstViewNotification.sent_at) }}
            </p>
            <p
              v-if="firstViewNotification.last_error"
              class="mt-2 text-xs text-danger-strong"
            >
              {{ firstViewNotification.last_error }}
            </p>
          </div>
          <BaseButton
            v-if="firstViewNotification.can_retry"
            variant="secondary"
            size="sm"
            :loading="retryingFirstView"
            data-testid="retry-first-view-notification"
            @click="retryFirstViewNotification"
          >
            Reintentar alerta
          </BaseButton>
        </div>
      </div>

      <!-- Engagement score -->
      <details
        v-if="analytics.engagement_score != null"
        open
        class="group bg-surface rounded-xl border shadow-sm"
        :class="analytics.engagement_score >= 70 ? 'border-emerald-200' : analytics.engagement_score >= 40 ? 'border-yellow-200' : 'border-red-200'"
      >
        <summary class="flex items-center justify-between gap-3 px-4 py-3 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden border-b border-border-default">
          <div class="flex items-center gap-1.5">
            <h3 class="text-sm font-medium text-text-default">Engagement Score</h3>
            <BaseTooltip position="right" width="max-w-2xl">
              <template #trigger>
                <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted transition-colors" />
              </template>
              {{ tt.engagementScore }}
            </BaseTooltip>
          </div>
          <BaseActionIcon action="expand" class="text-text-subtle transition-transform group-open:rotate-180" />
        </summary>
        <div class="p-5 flex items-center gap-5">
          <div class="w-16 h-16 rounded-2xl flex items-center justify-center text-2xl font-bold text-white"
            :class="analytics.engagement_score >= 70 ? 'bg-primary' : analytics.engagement_score >= 40 ? 'bg-yellow-500' : 'bg-red-400'">
            {{ analytics.engagement_score }}
          </div>
          <p class="text-xs text-text-muted">
            {{ analytics.engagement_score >= 70 ? 'Alto engagement — prioridad de follow-up' : analytics.engagement_score >= 40 ? 'Engagement moderado' : 'Bajo engagement — necesita atención' }}
          </p>
        </div>
      </details>

      <!-- Summary cards -->
      <details open class="group bg-surface rounded-xl border border-border-muted shadow-sm">
        <summary class="flex items-center justify-between gap-3 px-4 py-3 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden border-b border-border-muted">
          <div class="flex items-center gap-1.5">
            <h3 class="text-sm font-medium text-text-default">Resumen general</h3>
            <BaseTooltip position="right" width="max-w-2xl">
              <template #trigger>
                <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted transition-colors" />
              </template>
              {{ tt.summary }}
            </BaseTooltip>
          </div>
          <BaseActionIcon action="expand" class="text-text-subtle transition-transform group-open:rotate-180" />
        </summary>
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-3 gap-4 p-4">
          <div class="bg-surface rounded-xl border border-border-muted shadow-sm p-4">
            <div class="flex items-center gap-1">
              <p class="text-xs text-text-subtle uppercase tracking-wider">Vistas</p>
              <BaseTooltip position="bottom" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-3.5 h-3.5 text-text-subtle hover:text-text-muted transition-colors" />
                </template>
                {{ tt.views }}
              </BaseTooltip>
            </div>
            <p class="text-2xl font-light text-text-default mt-1">{{ analytics.total_views }}</p>
          </div>
          <div class="bg-surface rounded-xl border border-border-muted shadow-sm p-4">
            <div class="flex items-center gap-1">
              <p class="text-xs text-text-subtle uppercase tracking-wider">Sesiones</p>
              <BaseTooltip position="bottom" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-3.5 h-3.5 text-text-subtle hover:text-text-muted transition-colors" />
                </template>
                {{ tt.sessions }}
              </BaseTooltip>
            </div>
            <p class="text-2xl font-light text-text-default mt-1">{{ analytics.unique_sessions }}</p>
          </div>
          <div class="bg-surface rounded-xl border border-border-muted shadow-sm p-4">
            <div class="flex items-center gap-1">
              <p class="text-xs text-text-subtle uppercase tracking-wider">Primera vista</p>
              <BaseTooltip position="bottom" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-3.5 h-3.5 text-text-subtle hover:text-text-muted transition-colors" />
                </template>
                {{ tt.firstView }}
              </BaseTooltip>
            </div>
            <p class="text-sm font-light text-text-default mt-1">
              {{ analytics.first_viewed_at ? formatDate(analytics.first_viewed_at) : '—' }}
            </p>
          </div>
          <div class="bg-surface rounded-xl border border-border-muted shadow-sm p-4">
            <div class="flex items-center gap-1">
              <p class="text-xs text-text-subtle uppercase tracking-wider">Tiempo de lectura</p>
              <BaseTooltip position="bottom" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-3.5 h-3.5 text-text-subtle hover:text-text-muted transition-colors" />
                </template>
                {{ tt.readingTime }}
              </BaseTooltip>
            </div>
            <p class="text-2xl font-light text-text-default mt-1">{{ formatTime(totalReadingTime) }}</p>
          </div>
          <div class="bg-surface rounded-xl border border-border-muted shadow-sm p-4">
            <div class="flex items-center gap-1">
              <p class="text-xs text-text-subtle uppercase tracking-wider">Cobertura</p>
              <BaseTooltip position="bottom" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-3.5 h-3.5 text-text-subtle hover:text-text-muted transition-colors" />
                </template>
                {{ tt.coverage }}
              </BaseTooltip>
            </div>
            <p class="text-2xl font-light mt-1"
              :class="sectionCoverage == null ? 'text-text-default' : sectionCoverage >= 80 ? 'text-text-brand' : sectionCoverage >= 50 ? 'text-amber-500 dark:text-amber-400' : 'text-red-500 dark:text-red-400'">
              {{ sectionCoverage != null ? sectionCoverage + '%' : '—' }}
            </p>
          </div>
          <div class="bg-surface rounded-xl border border-border-muted shadow-sm p-4">
            <div class="flex items-center gap-1">
              <p class="text-xs text-text-subtle uppercase tracking-wider">Última visita</p>
              <BaseTooltip position="bottom" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-3.5 h-3.5 text-text-subtle hover:text-text-muted transition-colors" />
                </template>
                {{ tt.lastVisit }}
              </BaseTooltip>
            </div>
            <p class="text-sm font-light text-text-default mt-1">
              {{ lastVisitedAt ? formatDate(lastVisitedAt) : '—' }}
            </p>
          </div>
        </div>
      </details>

      <!-- Technical document engagement (unified tracking types) -->
      <details
        v-if="analytics.technical_engagement && (analytics.technical_engagement.sessions_reached > 0 || analytics.technical_engagement.total_time_seconds > 0)"
        open
        class="group bg-surface rounded-xl border border-teal-100 shadow-sm"
      >
        <summary class="flex items-center justify-between gap-3 px-4 py-3 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden border-b border-teal-100 dark:border-teal-900/40">
          <div>
            <div class="flex items-center gap-1.5">
              <h3 class="text-sm font-medium text-text-default">Detalle técnico</h3>
              <BaseTooltip position="right" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted transition-colors" />
                </template>
                {{ tt.technicalDetail }}
              </BaseTooltip>
            </div>
            <p class="text-xs text-text-muted mt-0.5">
              Paneles en modo técnico y sección técnica se unifican en métricas.
            </p>
          </div>
          <BaseActionIcon action="expand" class="text-text-subtle transition-transform group-open:rotate-180" />
        </summary>
        <div class="flex flex-wrap gap-6 p-4 text-sm">
          <div>
            <span class="text-xs text-text-subtle uppercase">Sesiones</span>
            <p class="text-xl font-light text-teal-800 dark:text-teal-300">{{ analytics.technical_engagement.sessions_reached }}</p>
          </div>
          <div>
            <span class="text-xs text-text-subtle uppercase">Tiempo total</span>
            <p class="text-xl font-light text-text-default">{{ formatTime(analytics.technical_engagement.total_time_seconds) }}</p>
          </div>
        </div>
      </details>

      <!-- F6: View mode breakdown -->
      <details v-if="analytics.by_view_mode && Object.keys(analytics.by_view_mode).length" open class="group bg-surface rounded-xl border border-border-muted shadow-sm">
        <summary class="flex items-center justify-between gap-3 px-4 sm:px-6 py-4 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden border-b border-border-muted">
          <div>
            <div class="flex items-center gap-1.5">
              <!-- panel-action-icons: allow-content-glyph — identifies this analytics dataset, not the disclosure action. -->
              <h3 class="text-sm font-medium text-text-default">📊 Comparación por Modo de Vista</h3>
              <BaseTooltip position="right" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted transition-colors" />
                </template>
                {{ tt.viewModeComparison }}
              </BaseTooltip>
            </div>
            <p class="text-xs text-text-subtle mt-0.5">Engagement por vista ejecutiva, completa, técnica o contractual</p>
          </div>
          <BaseActionIcon action="expand" class="text-text-subtle transition-transform group-open:rotate-180" />
        </summary>
        <div class="px-4 sm:px-6 py-4">
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
            <div v-for="mode in VIEW_MODES" :key="mode"
              class="rounded-xl border p-4"
              :class="viewModeCardClass(mode)"
            >
              <div class="flex items-center gap-2 mb-3">
                <span class="text-xs px-2 py-0.5 rounded-full font-bold uppercase tracking-wider"
                  :class="viewModeBadgeClass(mode)"
                >{{ mode }}</span>
                <span class="text-xs text-text-subtle">{{ analytics.by_view_mode[mode]?.sessions || 0 }} sesiones</span>
              </div>
              <div v-if="analytics.by_view_mode[mode]?.sections?.length" class="space-y-2">
                <div v-for="sec in analytics.by_view_mode[mode].sections" :key="`${sec.section_type}:${sec.subsection_key || ''}`" class="flex items-center gap-2">
                  <span class="text-xs text-text-muted truncate flex-1 min-w-0">{{ sec.section_title || sec.section_type }}</span>
                  <span class="text-xs text-text-subtle tabular-nums flex-shrink-0">{{ sec.visit_count }}×</span>
                  <span class="text-xs font-medium tabular-nums flex-shrink-0"
                    :class="viewModeTextClass(mode)"
                  >{{ formatTime(sec.total_time_seconds, { compact: true }) }}</span>
                </div>
              </div>
              <p v-else class="text-xs text-text-subtle italic">Sin datos aún</p>
            </div>
          </div>
        </div>
      </details>

      <!-- Comparison badges (Feature 13) -->
      <details v-if="analytics.comparison" open class="group bg-surface rounded-xl border border-border-muted shadow-sm">
        <summary class="flex items-center justify-between gap-3 px-4 py-3 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden border-b border-border-muted">
          <div class="flex items-center gap-1.5">
            <h3 class="text-sm font-medium text-text-default">Comparación con promedio global</h3>
            <BaseTooltip position="right" width="max-w-2xl">
              <template #trigger>
                <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted transition-colors" />
              </template>
              {{ tt.globalComparison }}
            </BaseTooltip>
          </div>
          <BaseActionIcon action="expand" class="text-text-subtle transition-transform group-open:rotate-180" />
        </summary>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 p-4">
          <div class="flex items-center gap-3 p-3 rounded-lg" :class="comparisonClass('ttfv')">
            <div class="text-2xl">{{ comparisonEmoji('ttfv') }}</div>
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
            <div class="text-2xl">{{ comparisonEmoji('ttr') }}</div>
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
            <div class="text-2xl">{{ comparisonEmoji('views') }}</div>
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
      </details>

      <!-- Funnel visualization (Feature 13) -->
      <details v-if="analytics.funnel?.length" open class="group bg-surface rounded-xl border border-border-muted shadow-sm">
        <summary class="flex items-center justify-between gap-3 px-4 sm:px-6 py-4 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden border-b border-border-muted">
          <div>
            <div class="flex items-center gap-1.5">
              <h3 class="text-sm font-medium text-text-default">Funnel de navegación</h3>
              <BaseTooltip position="right" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted transition-colors" />
                </template>
                {{ tt.funnel }}
              </BaseTooltip>
            </div>
            <p class="text-xs text-text-subtle mt-0.5">Porcentaje de sesiones que alcanzaron cada sección</p>
          </div>
          <BaseActionIcon action="expand" class="text-text-subtle transition-transform group-open:rotate-180" />
        </summary>
        <div class="px-4 sm:px-6 pt-4">
          <div class="inline-flex rounded-lg p-0.5 bg-surface-raised">
            <button
              :class="['px-3 py-1 text-xs font-medium rounded-md transition-all',
                funnelTab === 'exec_detail'
                  ? 'bg-surface text-blue-600 dark:text-blue-300 shadow-sm'
                  : 'text-text-muted hover:text-text-default']"
              @click="funnelTab = 'exec_detail'"
            >Executive & Detallado</button>
            <button
              :class="['px-3 py-1 text-xs font-medium rounded-md transition-all',
                funnelTab === 'technical'
                  ? 'bg-surface text-teal-600 dark:text-teal-300 shadow-sm'
                  : 'text-text-muted hover:text-text-default']"
              @click="funnelTab = 'technical'"
            >Técnico</button>
          </div>
        </div>
        <!-- Tab: Executive & Detallado -->
        <div v-show="funnelTab === 'exec_detail'" class="px-4 sm:px-6 py-4 space-y-3">
          <div v-for="(step, idx) in funnelExecDetail" :key="step.section_type" class="flex items-center gap-3">
            <span class="text-xs text-text-subtle w-5 text-right">{{ idx + 1 }}</span>
            <div class="flex-1">
              <div class="flex items-center justify-between mb-1">
                <span class="text-sm text-text-default font-medium truncate">{{ step.section_title }}</span>
                <div class="flex items-center gap-2">
                  <span v-if="step.in_executive_mode === false" class="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-500 font-medium flex-shrink-0">solo detallado</span>
                  <span class="text-xs text-text-muted">{{ step.reached_count }} sesiones</span>
                  <span v-if="step.drop_off_percent > 0" class="text-xs text-red-500 font-medium">
                    -{{ step.drop_off_percent }}%
                  </span>
                </div>
              </div>
              <div class="w-full bg-surface-raised rounded-full h-2">
                <div
                  class="h-2 rounded-full transition-all"
                  :class="funnelBarColor(step.drop_off_percent)"
                  :style="{ width: funnelBarWidth(step) + '%' }"
                />
              </div>
            </div>
          </div>
          <p v-if="!funnelExecDetail.length" class="text-xs text-text-subtle italic">Sin datos para este modo.</p>
        </div>
        <!-- Tab: Técnico -->
        <div v-show="funnelTab === 'technical'" class="px-4 sm:px-6 py-4 space-y-3">
          <div v-for="(step, idx) in funnelTechnical" :key="step.subsection_key || step.section_title" class="flex items-center gap-3" :class="{ 'opacity-45': step.reached_count === 0 }">
            <span class="text-xs text-text-subtle w-5 text-right">{{ idx + 1 }}</span>
            <div class="flex-1">
              <div class="flex items-center justify-between mb-1">
                <span class="text-sm text-text-default font-medium truncate">{{ step.section_title }}</span>
                <div class="flex items-center gap-2">
                  <span v-if="step.reached_count === 0" class="text-[10px] px-1.5 py-0.5 rounded bg-surface-raised text-text-subtle font-medium flex-shrink-0">no visto</span>
                  <span class="text-xs text-text-muted">{{ step.reached_count }} sesiones</span>
                  <span v-if="step.drop_off_percent > 0 && step.reached_count > 0" class="text-xs text-red-500 font-medium">
                    -{{ step.drop_off_percent }}%
                  </span>
                </div>
              </div>
              <div class="w-full bg-surface-raised rounded-full h-2">
                <div
                  class="h-2 rounded-full transition-all"
                  :class="funnelBarColor(step.drop_off_percent)"
                  :style="{ width: funnelBarWidth(step) + '%' }"
                />
              </div>
            </div>
          </div>
          <p v-if="!funnelTechnical.length" class="text-xs text-text-subtle italic">Sin datos técnicos.</p>
        </div>
      </details>

      <!-- Share links (Feature 13) -->
      <details v-if="analytics.share_links?.length" open class="group bg-surface rounded-xl border border-border-muted shadow-sm">
        <summary class="flex items-center justify-between gap-3 px-4 sm:px-6 py-4 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden border-b border-border-muted">
          <div>
            <div class="flex items-center gap-1.5">
              <h3 class="text-sm font-medium text-text-default">Enlaces compartidos</h3>
              <BaseTooltip position="right" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted transition-colors" />
                </template>
                {{ tt.sharedLinks }}
              </BaseTooltip>
            </div>
            <p class="text-xs text-text-subtle mt-0.5">Tracking de propuestas compartidas con otros stakeholders</p>
          </div>
          <BaseActionIcon action="expand" class="text-text-subtle transition-transform group-open:rotate-180" />
        </summary>
        <div class="overflow-x-auto rounded-b-xl overflow-hidden">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-surface-raised text-left text-xs text-text-muted uppercase tracking-wider">
                <th class="px-4 sm:px-6 py-3">Compartido por</th>
                <th class="px-4 py-3">Destinatario</th>
                <th class="px-4 py-3 text-center">Vistas</th>
                <th class="px-4 sm:px-6 py-3">Primera vista</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border-muted">
              <tr v-for="link in analytics.share_links" :key="link.uuid" class="hover:bg-surface-muted/50">
                <td class="px-4 sm:px-6 py-3">
                  <span class="font-medium text-text-default">{{ link.shared_by_name }}</span>
                  <span v-if="link.shared_by_email" class="text-xs text-text-subtle ml-1">({{ link.shared_by_email }})</span>
                </td>
                <td class="px-4 py-3">
                  <span v-if="link.recipient_name" class="text-text-default">{{ link.recipient_name }}</span>
                  <span v-else class="text-text-subtle italic">Pendiente</span>
                  <span v-if="link.recipient_email" class="text-xs text-text-subtle ml-1">({{ link.recipient_email }})</span>
                </td>
                <td class="px-4 py-3 text-center text-text-muted">{{ link.view_count }}</td>
                <td class="px-4 sm:px-6 py-3 text-text-muted">{{ link.first_viewed_at ? formatDate(link.first_viewed_at) : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>

      <!-- Device breakdown -->
      <details v-if="hasDeviceData" open class="group bg-surface rounded-xl border border-border-muted shadow-sm">
        <summary class="flex items-center justify-between gap-3 px-4 py-3 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden border-b border-border-muted">
          <div class="flex items-center gap-1.5">
            <h3 class="text-sm font-medium text-text-default">Dispositivos</h3>
            <BaseTooltip position="right" width="max-w-2xl">
              <template #trigger>
                <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted transition-colors" />
              </template>
              {{ tt.devices }}
            </BaseTooltip>
          </div>
          <BaseActionIcon action="expand" class="text-text-subtle transition-transform group-open:rotate-180" />
        </summary>
        <div class="flex gap-6 text-sm p-4">
          <div class="flex items-center gap-2">
            <span class="text-lg">🖥️</span>
            <span class="text-text-muted">Desktop: <strong>{{ analytics.device_breakdown.desktop }}</strong></span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-lg">📱</span>
            <span class="text-text-muted">Mobile: <strong>{{ analytics.device_breakdown.mobile }}</strong></span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-lg">📋</span>
            <span class="text-text-muted">Tablet: <strong>{{ analytics.device_breakdown.tablet }}</strong></span>
          </div>
        </div>
      </details>

      <!-- Suggested actions -->
      <details v-if="suggestions.length" class="group bg-amber-50 rounded-xl border border-amber-100 shadow-sm">
        <summary class="flex items-center justify-between gap-3 px-4 py-3 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden border-b border-amber-100">
          <div class="flex items-center gap-1.5">
            <!-- panel-action-icons: allow-content-glyph — identifies recommendation content, not the disclosure action. -->
            <h3 class="text-sm font-medium text-amber-900">💡 Acciones sugeridas</h3>
            <BaseTooltip position="right" width="max-w-2xl">
              <template #trigger>
                <QuestionMarkCircleIcon class="w-4 h-4 text-amber-400 hover:text-amber-600 transition-colors" />
              </template>
              {{ tt.suggestedActions }}
            </BaseTooltip>
          </div>
          <BaseActionIcon action="expand" class="text-amber-600 transition-transform group-open:rotate-180" />
        </summary>
        <ul class="space-y-2 p-4">
          <li
            v-for="(s, i) in suggestions"
            :key="i"
            class="flex items-start gap-2 text-sm text-amber-800"
          >
            <span class="mt-0.5 flex-shrink-0 text-amber-500">{{ s.icon }}</span>
            <span>{{ s.text }}</span>
          </li>
        </ul>
      </details>

      <!-- Skipped sections -->
      <details v-if="analytics.skipped_sections?.length" class="group bg-red-50 rounded-xl border border-red-100 shadow-sm">
        <summary class="flex items-center justify-between gap-3 px-4 py-3 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden border-b border-red-100">
          <div class="flex items-center gap-1.5">
            <!-- panel-action-icons: allow-content-glyph — identifies warning content, not the disclosure action. -->
            <h3 class="text-sm font-medium text-red-800">⚠️ Secciones no visitadas</h3>
            <BaseTooltip position="right" width="max-w-2xl">
              <template #trigger>
                <QuestionMarkCircleIcon class="w-4 h-4 text-red-400 hover:text-red-600 transition-colors" />
              </template>
              {{ tt.skippedSections }}
            </BaseTooltip>
          </div>
          <BaseActionIcon action="expand" class="text-red-500 transition-transform group-open:rotate-180" />
        </summary>
        <div class="p-4">
          <p class="text-xs text-red-600 mb-3">El cliente nunca visitó estas secciones — información accionable para follow-up.</p>
          <div class="flex flex-wrap gap-2">
            <span
              v-for="s in analytics.skipped_sections"
              :key="s.section_type"
              class="inline-flex items-center px-3 py-1.5 bg-surface border border-red-200 rounded-lg text-xs text-red-700 font-medium"
            >
              {{ s.section_title }}
            </span>
          </div>
        </div>
      </details>

      <!-- Section time heatmap -->
      <details v-if="sortedSections.length" open class="group bg-surface rounded-xl border border-border-muted shadow-sm">
        <summary class="flex items-center justify-between gap-3 px-4 sm:px-6 py-4 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden border-b border-border-muted">
          <div>
            <div class="flex items-center gap-1.5">
              <!-- panel-action-icons: allow-content-glyph — identifies heatmap content, not the disclosure action. -->
              <h3 class="text-sm font-medium text-text-default">🔥 Heatmap de Interés</h3>
              <BaseTooltip position="right" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted transition-colors" />
                </template>
                {{ tt.heatmap }}
              </BaseTooltip>
            </div>
            <p class="text-xs text-text-subtle mt-0.5">Secciones ordenadas por tiempo total — las más calientes son las que más le importan al cliente</p>
          </div>
          <BaseActionIcon action="expand" class="text-text-subtle transition-transform group-open:rotate-180" />
        </summary>
        <div class="px-4 sm:px-6 py-4 space-y-3">
          <div v-for="(section, idx) in sortedSections" :key="section.section_type" class="flex items-center gap-3">
            <span class="text-base w-5 flex-shrink-0">{{ heatEmoji(idx, sortedSections.length) }}</span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between mb-1 gap-2">
                <span class="text-sm font-medium text-text-default truncate">{{ section.section_title }}</span>
                <span class="text-xs text-text-muted flex-shrink-0 tabular-nums">{{ formatTime(section.total_time_seconds) }}</span>
              </div>
              <div class="w-full bg-surface-raised rounded-full h-2.5">
                <div
                  class="h-2.5 rounded-full transition-all"
                  :class="heatBarColor(idx, sortedSections.length)"
                  :style="{ width: heatBarWidth(section.total_time_seconds) + '%' }"
                />
              </div>
            </div>
          </div>
        </div>
        <!-- Actionable insights -->
        <div v-if="sectionInsights.length" class="px-4 sm:px-6 pb-4 space-y-2">
          <div
            v-for="insight in sectionInsights"
            :key="insight.type"
            class="flex items-start gap-2 bg-primary-soft border border-emerald-100 rounded-xl px-4 py-3"
          >
            <span class="text-base flex-shrink-0">{{ insight.icon }}</span>
            <div>
              <p class="text-xs font-semibold text-emerald-800">{{ insight.label }}</p>
              <p class="text-xs text-text-brand mt-0.5">{{ insight.text }}</p>
            </div>
          </div>
        </div>
      </details>

      <!-- Section engagement table -->
      <details open class="group bg-surface rounded-xl border border-border-muted shadow-sm">
        <summary class="flex items-center justify-between gap-3 px-4 sm:px-6 py-4 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden border-b border-border-muted">
          <div>
            <div class="flex items-center gap-1.5">
              <h3 class="text-sm font-medium text-text-default">Engagement por sección</h3>
              <BaseTooltip position="right" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted transition-colors" />
                </template>
                {{ tt.sectionEngagement }}
              </BaseTooltip>
            </div>
            <p class="text-xs text-text-subtle mt-0.5">Tiempo que el cliente pasó en cada sección</p>
          </div>
          <BaseActionIcon action="expand" class="text-text-subtle transition-transform group-open:rotate-180" />
        </summary>
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
              <tr v-for="section in analytics.sections" :key="section.section_type" class="hover:bg-surface-muted/50">
                <td class="px-4 sm:px-6 py-3">
                  <span class="font-medium text-text-default">{{ section.section_title }}</span>
                  <span class="text-xs text-text-subtle ml-1">({{ sectionAnalyticsTypeLabel(section.section_type) || section.section_type }})</span>
                </td>
                <td class="px-4 py-3 text-center text-text-muted">{{ section.visit_count }}</td>
                <td class="px-4 py-3 text-right text-text-muted">{{ formatTime(section.total_time_seconds) }}</td>
                <td class="px-4 py-3 text-right text-text-muted">{{ formatTime(section.avg_time_seconds) }}</td>
                <td class="px-4 sm:px-6 py-3">
                  <div class="flex items-center gap-2">
                    <div class="flex-1 bg-surface-raised rounded-full h-2 max-w-[120px]">
                      <div
                        class="h-2 rounded-full transition-all"
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
      </details>

      <!-- Activity Timeline -->
      <details open class="group bg-surface rounded-xl border border-border-muted shadow-sm">
        <summary class="flex items-center justify-between gap-3 px-4 sm:px-6 py-4 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden border-b border-border-muted">
          <div>
            <div class="flex items-center gap-1.5">
              <h3 class="text-sm font-medium text-text-default">Historial de actividad</h3>
              <BaseTooltip position="right" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted transition-colors" />
                </template>
                {{ tt.activityTimeline }}
              </BaseTooltip>
            </div>
            <p class="text-xs text-text-subtle mt-0.5">Timeline cronológico de eventos de la propuesta</p>
          </div>
          <BaseActionIcon action="expand" class="text-text-subtle transition-transform group-open:rotate-180" />
        </summary>
        <div v-if="analytics.timeline?.length" class="px-4 sm:px-6 py-4">
          <div class="relative">
            <div class="absolute left-4 top-0 bottom-0 w-px bg-border-default"></div>
            <div v-for="(event, idx) in analytics.timeline" :key="idx" class="relative pl-10 pb-5 last:pb-0">
              <div class="absolute left-2.5 w-3 h-3 rounded-full border-2 border-surface" :class="timelineColor(event.change_type)"></div>
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-xs font-medium px-2 py-0.5 rounded-full" :class="timelineBadge(event.change_type)">
                  {{ timelineIcon(event.change_type) }} {{ timelineLabel(event.change_type) }}
                </span>
                <span class="text-[10px] font-medium px-1.5 py-0.5 rounded-full" :class="actorBadgeClass(event.actor_type)">
                  {{ actorLabel(event.actor_type) }}
                </span>
                <span class="text-xs text-text-subtle">{{ formatDate(event.created_at) }}</span>
              </div>
              <!-- eslint-disable-next-line vue/no-v-html -->
              <div class="text-sm text-text-muted mt-1" v-html="formatTimelineDescription(event)"></div>
              <!-- Collapsible calculator detail -->
              <div v-if="isCalcEvent(event)" class="mt-2">
                <button
                  class="text-xs text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300 font-medium focus:outline-none"
                  @click="toggleCalcDetail(idx)"
                >
                  <BaseActionIcon :action="expandedCalcEvents[idx] ? 'collapse' : 'expand'" />
                  {{ expandedCalcEvents[idx] ? 'Ocultar detalle de módulos' : 'Ver detalle de módulos' }}
                </button>
                <div v-if="expandedCalcEvents[idx]" class="mt-2 ml-2 space-y-2 text-xs">
                  <div v-if="calcDetail(event).selected_names?.length">
                    <span class="font-semibold text-text-brand">Seleccionados:</span>
                    <ul class="ml-3 mt-1 list-disc text-text-muted space-y-0.5">
                      <li v-for="name in calcDetail(event).selected_names" :key="name">{{ name }}</li>
                    </ul>
                  </div>
                  <div v-if="calcDetail(event).deselected_names?.length">
                    <span class="font-semibold text-red-600 dark:text-red-400">Desmarcados:</span>
                    <ul class="ml-3 mt-1 list-disc text-text-muted space-y-0.5">
                      <li v-for="name in calcDetail(event).deselected_names" :key="name">{{ name }}</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="px-6 py-8 text-center text-text-subtle text-sm">
          Aún no hay eventos registrados.
        </div>
      </details>

      <!-- Sessions history -->
      <details open class="group bg-surface rounded-xl border border-border-muted shadow-sm">
        <summary class="flex items-center justify-between gap-3 px-4 sm:px-6 py-4 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden border-b border-border-muted">
          <div>
            <div class="flex items-center gap-1.5">
              <h3 class="text-sm font-medium text-text-default">Historial de sesiones</h3>
              <BaseTooltip position="right" width="max-w-2xl">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-4 h-4 text-text-subtle hover:text-text-muted transition-colors" />
                </template>
                {{ tt.sessionHistory }}
              </BaseTooltip>
            </div>
            <p class="text-xs text-text-subtle mt-0.5">Últimas 50 sesiones de navegación</p>
          </div>
          <BaseActionIcon action="expand" class="text-text-subtle transition-transform group-open:rotate-180" />
        </summary>
        <div v-if="analytics.sessions.length" class="overflow-x-auto rounded-b-xl overflow-hidden">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-surface-raised text-left text-xs text-text-muted uppercase tracking-wider">
                <th class="px-4 sm:px-6 py-3">Sesión</th>
                <th class="px-4 py-3">Fecha</th>
                <th class="px-4 py-3 text-center">Secciones vistas</th>
                <th class="px-4 py-3 text-center">Modo</th>
                <th class="px-4 sm:px-6 py-3 text-right">Tiempo total</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border-muted">
              <tr v-for="session in analytics.sessions" :key="session.session_id" class="hover:bg-surface-muted/50">
                <td class="px-4 sm:px-6 py-3">
                  <span class="font-mono text-xs text-text-muted">{{ session.session_id.slice(0, 12) }}...</span>
                  <span v-if="session.ip_address" class="text-xs text-text-subtle ml-2">{{ session.ip_address }}</span>
                </td>
                <td class="px-4 py-3 text-text-muted">{{ formatDate(session.viewed_at) }}</td>
                <td class="px-4 py-3 text-center text-text-muted">{{ session.sections_viewed }}</td>
                <td class="px-4 py-3 text-center">
                  <span v-if="session.view_mode" class="text-xs px-2 py-0.5 rounded-full font-medium"
                    :class="viewModeBadgeClass(session.view_mode)">
                    {{ session.view_mode }}
                  </span>
                  <span v-else class="text-xs text-text-subtle">—</span>
                </td>
                <td class="px-4 sm:px-6 py-3 text-right text-text-muted">{{ formatTime(session.total_time_seconds) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="px-6 py-8 text-center text-text-subtle text-sm">
          Aún no hay sesiones registradas.
        </div>
      </details>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { QuestionMarkCircleIcon } from '@heroicons/vue/24/outline';
import { usePanelDownload } from '~/composables/usePanelDownload';
const csvDownload = usePanelDownload();
import { usePanelNotify } from '~/composables/usePanelNotify';
// Explicit rather than relying on Nuxt auto-import, so the unit spec that
// mounts this component in isolation resolves it too (same as
// WebAppDiagnostic/admin/DiagnosticAnalytics.vue).
import BaseSkeleton from '~/components/base/BaseSkeleton.vue';
import { formatDateTime as formatDate } from '~/utils/formatDate';

const { analytics: tt } = useTooltipTexts();
const notify = usePanelNotify();

const props = defineProps({
  proposalId: { type: [Number, String], required: true },
  proposal: { type: Object, default: null },
  refreshKey: { type: Number, default: 0 },
});
const emit = defineEmits(['retried']);

const proposalStore = useProposalStore();
const loading = ref(true);
const analytics = ref(null);
const retryingFirstView = ref(false);
const funnelTab = ref<'exec_detail' | 'technical'>('exec_detail');
const VIEW_MODES = ['executive', 'detailed', 'technical', 'legal'];
const VIEW_MODE_CLASSES = {
  executive: {
    card: 'border-purple-200 bg-purple-50/50 dark:border-purple-800 dark:bg-purple-900/20',
    badge: 'bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-400',
    text: 'text-purple-600 dark:text-purple-400',
  },
  detailed: {
    card: 'border-blue-200 bg-blue-50/50 dark:border-blue-800 dark:bg-blue-900/20',
    badge: 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-400',
    text: 'text-blue-600 dark:text-blue-400',
  },
  technical: {
    card: 'border-teal-200 bg-teal-50/50 dark:border-teal-800 dark:bg-teal-900/20',
    badge: 'bg-teal-100 text-teal-800 dark:bg-teal-900/50 dark:text-teal-300',
    text: 'text-teal-700 dark:text-teal-400',
  },
  legal: {
    card: 'border-warning-strong/30 bg-warning-soft',
    badge: 'bg-warning-soft text-warning-strong',
    text: 'text-warning-strong',
  },
};
const viewModeCardClass = mode => VIEW_MODE_CLASSES[mode]?.card || 'border-border-default bg-surface-raised';
const viewModeBadgeClass = mode => VIEW_MODE_CLASSES[mode]?.badge || 'bg-surface-raised text-text-muted';
const viewModeTextClass = mode => VIEW_MODE_CLASSES[mode]?.text || 'text-text-muted';

const suggestions = computed(() => {
  if (!analytics.value) return [];
  const list = [];
  const a = analytics.value;
  const status = props.proposal?.status;

  const techSec = a.technical_engagement;
  const techSessions = a.by_view_mode?.technical?.sessions || 0;
  if (techSec && (techSec.total_time_seconds >= 40 || (techSessions >= 1 && techSec.total_time_seconds >= 15))) {
    list.push({
      icon: '🔧',
      text: 'Hubo lectura del detalle técnico — buena señal si el decisor técnico o un CTO revisó arquitectura y requerimientos. Refuerza ese hilo en el seguimiento.',
    });
  }

  const skippedTypes = (a.skipped_sections || []).map(s => s.section_type);

  if (skippedTypes.includes('investment')) {
    list.push({ icon: '💰', text: 'El cliente no vio la sección de Inversión — envía un resumen de precios por email o menciónalo en el próximo contacto.' });
  }

  if (a.total_views >= 3 && !a.responded_at) {
    list.push({ icon: '🔥', text: `El cliente revisó la propuesta ${a.total_views} veces sin responder — es un señal de interés, haz un follow-up en caliente.` });
  }

  skippedTypes.filter(t => t !== 'investment').forEach(t => {
    const section = (a.skipped_sections || []).find(s => s.section_type === t);
    if (section) {
      list.push({ icon: '👁️', text: `El cliente no vio «${section.section_title}» — menciónala en el próximo contacto.` });
    }
  });

  if (a.time_to_first_view_hours != null && a.time_to_first_view_hours > 24) {
    list.push({ icon: '📬', text: `El cliente tardó ${a.time_to_first_view_hours}h en abrir la propuesta — verifica que el email llegó correctamente o considera reenviarla.` });
  }

  if (status === 'rejected') {
    list.push({ icon: '🔄', text: 'Propuesta rechazada — considera enviar una versión ajustada al presupuesto o un alcance reducido para retomar la negociación.' });
  }

  if (a.unique_sessions === 1 && !a.responded_at && status === 'viewed') {
    list.push({ icon: '📞', text: 'El cliente abrió la propuesta una sola vez — un seguimiento por llamada o WhatsApp puede aumentar la probabilidad de respuesta.' });
  }

  return list;
});

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

const firstViewNotification = computed(
  () => analytics.value?.first_view_notification || props.proposal?.first_view_notification || null,
);
const FIRST_VIEW_NOTIFICATION_LABELS = {
  not_started: 'Sin vista confirmada',
  pending: 'Pendiente',
  sending: 'Enviando',
  sent: 'Enviado',
  failed: 'Falló',
  skipped: 'Omitido',
  legacy_unverified: 'Histórico sin evidencia',
};
const firstViewNotificationLabel = computed(
  () => FIRST_VIEW_NOTIFICATION_LABELS[firstViewNotification.value?.status]
    || firstViewNotification.value?.status
    || 'Desconocido',
);
const firstViewNotificationClass = computed(() => {
  const status = firstViewNotification.value?.status;
  if (status === 'sent') return 'bg-success-soft text-success-strong';
  if (status === 'failed') return 'bg-danger-soft text-danger-strong';
  if (status === 'pending' || status === 'sending') return 'bg-warning-soft text-warning-strong';
  return 'bg-surface-raised text-text-muted';
});

const funnelSplit = computed(() => {
  const funnel = analytics.value?.funnel || [];
  const execDetail: any[] = [];
  const technical: any[] = [];
  for (const s of funnel) {
    (s.section_type === 'technical_document_public' ? technical : execDetail).push(s);
  }
  return { execDetail, technical };
});
const funnelExecDetail = computed(() => funnelSplit.value.execDetail);
const funnelTechnical = computed(() => funnelSplit.value.technical);

const sortedSections = computed(() => {
  if (!analytics.value?.sections?.length) return [];
  return [...analytics.value.sections].sort(
    (a, b) => (b.total_time_seconds || 0) - (a.total_time_seconds || 0),
  );
});

const SECTION_INSIGHTS = {
  timeline: {
    icon: '⏱️',
    label: 'Preocupación: plazos de entrega',
    text: 'El cliente invirtió tiempo en el cronograma. En el follow-up, enfócate en la velocidad de ejecución y el primer entregable rápido.',
  },
  investment: {
    icon: '💰',
    label: 'Señal de interés en precio',
    text: 'Revisó en detalle la inversión. Ofrece opciones de pago o un desglose más claro del ROI para facilitar la decisión.',
  },
  functional_requirements: {
    icon: '📋',
    label: 'Duda sobre el alcance',
    text: 'Le costó entender qué incluye el proyecto. Clarifica las funcionalidades clave y lo que está fuera del alcance en la siguiente llamada.',
  },
  context_diagnostic: {
    icon: '🎯',
    label: 'El problema resonó',
    text: 'Se identificó con el diagnóstico. En el follow-up, refuerza el dolor que resuelves — ya tienes su atención.',
  },
  proposal_closing: {
    icon: '🤔',
    label: 'Evaluando la decisión final',
    text: 'Pasó tiempo en el cierre. Es un buen momento para contactarlo directamente y ofrecer resolver cualquier duda.',
  },
  about_us: {
    icon: '🔍',
    label: 'Investigando tu credibilidad',
    text: 'Quiere saber quién eres antes de decidir. Comparte casos de éxito o testimonios de clientes similares.',
  },
  portfolio: {
    icon: '🖼️',
    label: 'Revisó tu portafolio',
    text: 'Está validando la calidad de tu trabajo. Menciona proyectos similares en el follow-up.',
  },
  technical_document_public: {
    icon: '🔧',
    label: 'Profundizó en lo técnico',
    text: 'Pasó tiempo en el detalle técnico (vista pública). Es señal de validación técnica: ofrece una llamada con perfil técnico o aclara integraciones y riesgos.',
  },
  technical_document: {
    icon: '🔧',
    label: 'Sección técnica vista',
    text: 'Registro en flujo comercial de la sección técnica. Alinea la conversación con arquitectura y alcance técnico acordado.',
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

async function loadAnalytics() {
  loading.value = true;
  const result = await proposalStore.fetchProposalAnalytics(props.proposalId);
  if (result.success) {
    analytics.value = result.data;
  } else {
    notify.error({ title: 'No se pudieron cargar las analíticas.' });
  }
  loading.value = false;
}

async function retryFirstViewNotification() {
  if (retryingFirstView.value) return;
  retryingFirstView.value = true;
  const result = await proposalStore.retryFirstViewNotification(props.proposalId);
  if (result.success) {
    analytics.value.first_view_notification = result.data;
    notify.success({ title: 'Reintento de alerta programado.' });
    emit('retried');
  } else {
    notify.error({ title: 'No se pudo reintentar la alerta.' });
  }
  retryingFirstView.value = false;
}

onMounted(loadAnalytics);
watch(() => props.refreshKey, (next, previous) => {
  if (next !== previous) loadAnalytics();
});

/** Friendly label for raw tracking section_type (technical split). */
function sectionAnalyticsTypeLabel(sectionType) {
  if (sectionType === 'technical_document_public') return 'det. técnico (vista pública)';
  if (sectionType === 'technical_document') return 'det. técnico';
  return '';
}

function downloadCSV() {
  const url = `/api/proposals/${props.proposalId}/analytics/csv/`;
  csvDownload.download(url, 'proposals-analytics.csv', 'text/csv');
}

function formatTime(seconds, { compact = false } = {}) {
  if (!seconds || seconds < 1) return '< 1s';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  if (compact) return `${mins}m`;
  const secs = Math.round(seconds % 60);
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}

function barWidth(avgSeconds) {
  return Math.min(100, (avgSeconds / 180) * 100);
}

function barColor(avgSeconds) {
  if (avgSeconds >= 60) return 'bg-primary';
  if (avgSeconds >= 20) return 'bg-blue-500';
  if (avgSeconds >= 5) return 'bg-amber-400';
  return 'bg-border-default';
}

function heatBarWidth(totalSeconds) {
  if (!sortedSections.value.length) return 0;
  const max = sortedSections.value[0].total_time_seconds || 1;
  return Math.min(100, Math.round((totalSeconds / max) * 100));
}

function heatBarColor(idx, total) {
  const ratio = total <= 1 ? 1 : idx / (total - 1);
  if (ratio <= 0.15) return 'bg-red-500';
  if (ratio <= 0.35) return 'bg-orange-400';
  if (ratio <= 0.55) return 'bg-amber-400';
  if (ratio <= 0.75) return 'bg-yellow-300';
  return 'bg-border-default';
}

function heatEmoji(idx, total) {
  const ratio = total <= 1 ? 1 : idx / (total - 1);
  if (ratio <= 0.15) return '🔴';
  if (ratio <= 0.35) return '🟠';
  if (ratio <= 0.55) return '🟡';
  return '⚪';
}

const TIMELINE_LABELS = {
  created: 'Creada', updated: 'Actualizada', sent: 'Enviada', viewed: 'Vista',
  accepted: 'Aceptada', rejected: 'Rechazada', resent: 'Reenviada',
  expired: 'Expirada', duplicated: 'Duplicada', commented: 'Comentario',
  negotiating: 'Negociando', reengagement: 'Reenganche',
  call: 'Llamada', meeting: 'Reunión', followup: 'Seguimiento', note: 'Nota',
  calc_confirmed: 'Calculadora confirmada', calc_abandoned: 'Calculadora abandonada',
  calc_followup: 'Seguimiento calculadora', auto_archived: 'Archivada automáticamente',
  status_change: 'Cambio de estado', cond_accepted: 'Aceptación condicional',
  req_clicked: 'Módulo consultado', seller_inactivity_escalation: 'Escalación por inactividad',
};

const ACTOR_LABELS = { client: 'Cliente', seller: 'Ventas', system: 'Sistema', '': 'Sistema' };
const ACTOR_BADGE_CLASSES = {
  client: 'bg-blue-50 text-blue-600 border border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-700',
  seller: 'bg-purple-50 text-purple-600 border border-purple-200 dark:bg-purple-900/30 dark:text-purple-400 dark:border-purple-700',
  system: 'bg-surface-raised text-text-muted border border-border-default',
  '': 'bg-surface-raised text-text-muted border border-border-default',
};

const FIELD_LABELS = {
  title: 'Título', total_investment: 'Inversión total', currency: 'Moneda',
  client_name: 'Nombre del cliente', client_email: 'Email del cliente',
  client_phone: 'Teléfono del cliente', discount_percent: 'Descuento (%)',
  status: 'Estado', language: 'Idioma', project_type: 'Tipo de proyecto',
  market_type: 'Tipo de mercado', expires_at: 'Fecha de expiración',
  reminder_days: 'Días de recordatorio', urgency_reminder_days: 'Días de recordatorio de urgencia',
  followup_scheduled_at: 'Seguimiento programado',
};

const expandedCalcEvents = ref({});

function timelineLabel(type) {
  return TIMELINE_LABELS[type] || type;
}

function actorLabel(actorType) {
  return ACTOR_LABELS[actorType || ''] || 'Sistema';
}

function actorBadgeClass(actorType) {
  return ACTOR_BADGE_CLASSES[actorType || ''] || ACTOR_BADGE_CLASSES[''];
}

function isCalcEvent(event) {
  return event.change_type === 'calc_confirmed' || event.change_type === 'calc_abandoned';
}

function toggleCalcDetail(idx) {
  expandedCalcEvents.value[idx] = !expandedCalcEvents.value[idx];
}

function calcDetail(event) {
  try { return JSON.parse(event.description); }
  catch { return {}; }
}

function formatCurrencyValue(val) {
  const num = parseFloat(val);
  if (isNaN(num)) return val || '(vacío)';
  return `<strong>$${num.toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</strong>`;
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function formatTimelineDescription(event) {
  const desc = event.description || '';

  // Calculator events
  if (isCalcEvent(event)) {
    try {
      const data = JSON.parse(desc);
      const count = (data.selected || []).length;
      const total = data.total;
      const elapsed = data.elapsed_seconds || 0;
      const mins = Math.floor(elapsed / 60);
      const secs = Math.round(elapsed % 60);
      const timeStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
      const totalStr = total != null
        ? `<strong>$${Number(total).toLocaleString('es-CO')}</strong>`
        : '';
      if (event.change_type === 'calc_confirmed') {
        return `Confirmó <strong>${count}</strong> módulo${count !== 1 ? 's' : ''}`
          + (totalStr ? ` — Total: ${totalStr}` : '')
          + (elapsed ? ` — Tiempo: <strong>${timeStr}</strong>` : '');
      }
      const deselectedCount = (data.deselected || []).length;
      return `Abandonó calculadora con <strong>${count}</strong> módulo${count !== 1 ? 's' : ''} seleccionado${count !== 1 ? 's' : ''}`
        + (deselectedCount ? `, <strong>${deselectedCount}</strong> desmarcado${deselectedCount !== 1 ? 's' : ''}` : '')
        + (totalStr ? ` — Total: ${totalStr}` : '')
        + (elapsed ? ` — Tiempo: <strong>${timeStr}</strong>` : '');
    } catch { return escapeHtml(desc); }
  }

  // Requirement clicked
  if (event.change_type === 'req_clicked') {
    try {
      const data = JSON.parse(desc);
      return `Cliente consultó <strong>${escapeHtml(data.group_title || 'módulo')}</strong>`;
    } catch { return escapeHtml(desc); }
  }

  // Field updates with old/new values
  if (event.change_type === 'updated' && event.field_name) {
    const fieldLabel = FIELD_LABELS[event.field_name] || event.field_name;
    const isCurrency = ['total_investment'].includes(event.field_name);
    const isDate = ['expires_at', 'followup_scheduled_at'].includes(event.field_name);
    const fmtDate = (val) => {
      if (!val) return '(vacío)';
      return escapeHtml(formatDate(val, { fallback: val }));
    };
    const oldDisplay = isCurrency ? formatCurrencyValue(event.old_value) : isDate ? fmtDate(event.old_value) : escapeHtml(event.old_value || '(vacío)');
    const newDisplay = isCurrency ? formatCurrencyValue(event.new_value) : isDate ? `<strong>${fmtDate(event.new_value)}</strong>` : `<strong>${escapeHtml(event.new_value || '(vacío)')}</strong>`;
    return `<strong>${escapeHtml(fieldLabel)}</strong>: ${oldDisplay} → ${newDisplay}`;
  }

  // Status change
  if (event.change_type === 'status_change' && event.old_value && event.new_value) {
    return `<strong>Estado</strong>: ${escapeHtml(event.old_value)} → <strong>${escapeHtml(event.new_value)}</strong>`;
  }

  // Client comment — bold the comment body
  if (event.change_type === 'commented') {
    const prefix = 'Client left a comment: ';
    if (desc.startsWith(prefix)) {
      return `Client left a comment: <strong>${escapeHtml(desc.slice(prefix.length))}</strong>`;
    }
    return escapeHtml(desc);
  }

  // Negotiating — bold the comment when present
  if (event.change_type === 'negotiating') {
    const key = ' Comment: ';
    const idx = desc.indexOf(key);
    if (idx !== -1) {
      return `${escapeHtml(desc.slice(0, idx))} Comment: <strong>${escapeHtml(desc.slice(idx + key.length))}</strong>`;
    }
    return escapeHtml(desc);
  }

  // Rejected — bold the rejection reason when present
  if (event.change_type === 'rejected') {
    const key = ' Reason: ';
    const idx = desc.indexOf(key);
    if (idx !== -1) {
      return `${escapeHtml(desc.slice(0, idx))} Reason: <strong>${escapeHtml(desc.slice(idx + key.length))}</strong>`;
    }
    return escapeHtml(desc);
  }

  // Conditional acceptance — bold the condition text
  if (event.change_type === 'cond_accepted') {
    const prefix = 'Conditional acceptance: ';
    if (desc.startsWith(prefix)) {
      return `Conditional acceptance: <strong>${escapeHtml(desc.slice(prefix.length))}</strong>`;
    }
    return escapeHtml(desc);
  }

  // Accepted — bold condition when present
  if (event.change_type === 'accepted') {
    const key = ' Condition: ';
    const idx = desc.indexOf(key);
    if (idx !== -1) {
      return `${escapeHtml(desc.slice(0, idx))} Condition: <strong>${escapeHtml(desc.slice(idx + key.length))}</strong>`;
    }
    return escapeHtml(desc);
  }

  // Sent / resent — bold the recipient email
  if (event.change_type === 'sent' || event.change_type === 'resent') {
    const key = ' to ';
    const idx = desc.indexOf(key);
    if (idx !== -1) {
      const afterTo = desc.slice(idx + key.length);
      const email = afterTo.endsWith('.') ? afterTo.slice(0, -1) : afterTo;
      return `${escapeHtml(desc.slice(0, idx))} to <strong>${escapeHtml(email)}</strong>.`;
    }
    return escapeHtml(desc);
  }

  // Created / duplicated — bold the proposal title between quotes
  if (event.change_type === 'created' || event.change_type === 'duplicated') {
    return escapeHtml(desc).replace(/&quot;(.+?)&quot;/, '<strong>&quot;$1&quot;</strong>');
  }

  return escapeHtml(desc);
}

function timelineIcon(type) {
  const icons = {
    created: '📝', updated: '✏️', sent: '📧', viewed: '👁️',
    accepted: '✅', rejected: '❌', resent: '🔁', expired: '⏰', duplicated: '📋',
    commented: '💬', negotiating: '🤝', reengagement: '🔔',
    call: '📞', meeting: '🤝', followup: '📩', note: '📝',
    calc_confirmed: '🧮', calc_abandoned: '🧮', calc_followup: '🧮',
    auto_archived: '📦', status_change: '🔄', cond_accepted: '⚠️',
    req_clicked: '🔍', seller_inactivity_escalation: '🚨',
  };
  return icons[type] || '•';
}

function timelineColor(type) {
  const colors = {
    created: 'bg-blue-400', updated: 'bg-amber-400', sent: 'bg-indigo-400',
    viewed: 'bg-green-400', accepted: 'bg-primary', rejected: 'bg-red-500',
    resent: 'bg-purple-400', expired: 'bg-yellow-500', duplicated: 'bg-text-subtle',
    commented: 'bg-purple-400', negotiating: 'bg-indigo-400', reengagement: 'bg-orange-400',
    call: 'bg-sky-400', meeting: 'bg-indigo-500', followup: 'bg-amber-400', note: 'bg-text-subtle',
    calc_confirmed: 'bg-emerald-400', calc_abandoned: 'bg-red-400', calc_followup: 'bg-orange-400',
    auto_archived: 'bg-text-subtle', status_change: 'bg-blue-400', cond_accepted: 'bg-amber-500',
    req_clicked: 'bg-cyan-400', seller_inactivity_escalation: 'bg-red-500',
  };
  return colors[type] || 'bg-text-subtle';
}

function timelineBadge(type) {
  const badges = {
    created: 'bg-blue-50 text-blue-700', updated: 'bg-amber-50 text-amber-700',
    sent: 'bg-indigo-50 text-indigo-700', viewed: 'bg-green-50 text-green-700',
    accepted: 'bg-primary-soft text-text-brand', rejected: 'bg-red-50 text-red-700',
    resent: 'bg-purple-50 text-purple-700', expired: 'bg-yellow-50 text-yellow-700',
    duplicated: 'bg-surface-raised text-text-default',
    commented: 'bg-purple-50 text-purple-700', negotiating: 'bg-indigo-50 text-indigo-700',
    reengagement: 'bg-orange-50 text-orange-700',
    call: 'bg-sky-50 text-sky-700', meeting: 'bg-indigo-50 text-indigo-700',
    followup: 'bg-amber-50 text-amber-700', note: 'bg-surface-raised text-text-muted',
    calc_confirmed: 'bg-primary-soft text-text-brand', calc_abandoned: 'bg-red-50 text-red-700',
    calc_followup: 'bg-orange-50 text-orange-700',
    auto_archived: 'bg-surface-raised text-text-default', status_change: 'bg-blue-50 text-blue-700',
    cond_accepted: 'bg-amber-50 text-amber-700',
    req_clicked: 'bg-cyan-50 text-cyan-700', seller_inactivity_escalation: 'bg-red-50 text-red-700',
  };
  return badges[type] || 'bg-surface-raised text-text-default';
}

function funnelBarWidth(step) {
  if (!analytics.value?.unique_sessions) return 0;
  return Math.round((step.reached_count / analytics.value.unique_sessions) * 100);
}

function funnelBarColor(dropOff) {
  if (dropOff <= 10) return 'bg-primary';
  if (dropOff <= 30) return 'bg-blue-500';
  if (dropOff <= 50) return 'bg-amber-400';
  return 'bg-red-400';
}

function comparisonClass(metric) {
  const c = analytics.value?.comparison;
  if (!c) return 'bg-surface-muted';
  if (metric === 'ttfv') {
    const val = analytics.value?.time_to_first_view_hours;
    const avg = c.avg_time_to_first_view_hours;
    if (val == null || avg == null) return 'bg-surface-muted';
    return val < avg ? 'bg-primary-soft' : 'bg-amber-50';
  }
  if (metric === 'ttr') {
    const val = analytics.value?.time_to_response_hours;
    const avg = c.avg_time_to_response_hours;
    if (val == null || avg == null) return 'bg-surface-muted';
    return val < avg ? 'bg-primary-soft' : 'bg-amber-50';
  }
  if (metric === 'views') {
    const val = analytics.value?.total_views;
    const avg = c.avg_views;
    if (val == null || avg == null) return 'bg-surface-muted';
    return val > avg ? 'bg-primary-soft' : 'bg-amber-50';
  }
  return 'bg-surface-muted';
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
