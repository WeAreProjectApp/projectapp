<template>
  <div class="min-w-0">
    <!-- Desktop / landscape: column widths must not depend on project names. -->
    <div v-if="!isMobile" class="overflow-x-auto rounded-2xl border border-border-default bg-surface" data-testid="projects-table-container">
    <table class="w-full table-fixed text-left text-sm [overflow-wrap:anywhere]">
      <colgroup>
        <col class="w-1/3" />
        <col v-if="isAdmin" />
        <col />
        <col v-if="showBugs" />
        <col v-if="isAdmin" />
        <col v-if="showDeliveryValue" />
        <col />
        <col class="w-12" />
      </colgroup>
      <thead class="bg-surface-muted/40 text-xs font-medium uppercase tracking-wider text-text-muted">
        <tr>
          <th class="px-4 py-3">Proyecto</th>
          <th v-if="isAdmin" class="px-4 py-3">Cliente</th>
          <th class="px-4 py-3">Progreso</th>
          <th v-if="showBugs" class="px-4 py-3">Bugs abiertos</th>
          <th v-if="isAdmin" class="px-4 py-3">Solicitudes pendientes</th>
          <th v-if="showDeliveryValue" class="px-4 py-3">Valor total</th>
          <th class="px-4 py-3">Última actividad</th>
          <th class="px-2"></th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="p in projects"
          :key="p.id"
          :data-testid="`project-row-${p.id}`"
          class="cursor-pointer border-t border-border-muted transition hover:bg-primary-soft"
          @click="$emit('navigate', p.id)"
        >
          <td class="px-4 py-3">
            <div class="whitespace-normal font-medium text-text-default" :data-testid="`project-name-${p.id}`">{{ p.name }}</div>
            <span :class="statusChipClass(p.current_state)">{{ p.status_label }}</span>
          </td>
          <td v-if="isAdmin" class="px-4 py-3 text-text-muted">
            {{ p.client_name }}<br>
            <span class="text-xs text-text-muted">{{ p.client_email }}</span>
          </td>
          <td class="px-4 py-3">
            <div class="flex min-w-0 items-center gap-2">
              <div class="h-1.5 min-w-0 max-w-20 flex-1 overflow-hidden rounded-full bg-surface-muted">
                <div class="h-full bg-primary" :style="{ width: `${p.progress || 0}%` }"></div>
              </div>
              <span class="shrink-0 text-xs">{{ p.progress || 0 }}%</span>
            </div>
          </td>
          <td v-if="showBugs" class="px-4 py-3">
            <span :data-testid="`project-bugs-${p.id}`" :class="(p.bugs_open_count || 0) > 0 ? 'rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700' : 'text-text-muted'">
              {{ p.bugs_open_count || 0 }}
            </span>
          </td>
          <td v-if="isAdmin" class="px-4 py-3">
            <span :class="(p.changes_pending_count || 0) > 0 ? 'rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700' : 'text-text-muted'">
              {{ p.changes_pending_count || 0 }}
            </span>
          </td>
          <td v-if="showDeliveryValue" class="px-4 py-3 text-sm">
            <span :data-testid="`project-value-${p.id}`" :class="(Number(p.phases_total_amount) > 0) ? 'font-medium text-text-default' : 'text-text-muted'">
              {{ formatCurrency(p.phases_total_amount) }}
            </span>
          </td>
          <td class="px-4 py-3 text-sm text-text-muted" :data-testid="`project-last-activity-${p.id}`">{{ relativeTime(p.last_activity_at) }}</td>
          <td class="px-2 py-3 text-right text-text-muted">›</td>
        </tr>
        <tr v-if="!projects.length">
          <td :colspan="4 + (isAdmin ? 2 : 0) + Number(showBugs) + Number(showDeliveryValue)" class="px-4 py-12 text-center text-text-muted">
            No hay proyectos para mostrar.
          </td>
        </tr>
      </tbody>
    </table>
    </div>

    <!-- Compact / portrait: retain the complete project name in each card. -->
    <div v-else class="space-y-3">
      <BaseButton unstyled
        v-for="p in projects"
        :key="p.id"
        type="button"
        :data-testid="`project-card-${p.id}`"
        class="block w-full rounded-2xl border border-border-default bg-surface p-4 text-left transition hover:bg-primary-soft"
        @click="$emit('navigate', p.id)"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="whitespace-normal font-medium text-text-default [overflow-wrap:anywhere]" :data-testid="`project-name-${p.id}`">{{ p.name }}</div>
            <span :class="statusChipClass(p.current_state)">{{ p.status_label }}</span>
          </div>
          <span class="shrink-0 text-text-muted">›</span>
        </div>

        <div v-if="isAdmin" class="mt-3 text-sm text-text-muted">
          {{ p.client_name }}
          <span class="block truncate text-xs text-text-muted">{{ p.client_email }}</span>
        </div>

        <div class="mt-3 flex items-center gap-2">
          <div class="h-1.5 w-full max-w-[8rem] overflow-hidden rounded-full bg-surface-muted">
            <div class="h-full bg-primary" :style="{ width: `${p.progress || 0}%` }"></div>
          </div>
          <span class="text-xs text-text-muted">{{ p.progress || 0 }}%</span>
        </div>

        <dl class="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <div v-if="showBugs" class="flex items-center justify-between gap-2">
            <dt class="text-xs uppercase tracking-wide text-text-muted">Bugs</dt>
            <dd>
              <span :data-testid="`project-bugs-${p.id}`" :class="(p.bugs_open_count || 0) > 0 ? 'rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700' : 'text-text-muted'">{{ p.bugs_open_count || 0 }}</span>
            </dd>
          </div>
          <div v-if="isAdmin" class="flex items-center justify-between gap-2">
            <dt class="text-xs uppercase tracking-wide text-text-muted">Solicitudes</dt>
            <dd>
              <span :class="(p.changes_pending_count || 0) > 0 ? 'rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700' : 'text-text-muted'">{{ p.changes_pending_count || 0 }}</span>
            </dd>
          </div>
          <div v-if="showDeliveryValue" class="flex items-center justify-between gap-2">
            <dt class="text-xs uppercase tracking-wide text-text-muted">Valor</dt>
            <dd :data-testid="`project-value-${p.id}`" :class="(Number(p.phases_total_amount) > 0) ? 'font-medium text-text-default' : 'text-text-muted'">{{ formatCurrency(p.phases_total_amount) }}</dd>
          </div>
          <div class="flex items-center justify-between gap-2">
            <dt class="text-xs uppercase tracking-wide text-text-muted">Actividad</dt>
            <dd class="text-text-muted" :data-testid="`project-last-activity-${p.id}`">{{ relativeTime(p.last_activity_at) }}</dd>
          </div>
        </dl>
      </BaseButton>

      <div v-if="!projects.length" class="rounded-2xl border border-border-default bg-surface px-4 py-12 text-center text-text-muted">
        No hay proyectos para mostrar.
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useIsMobile } from '~/composables/useIsMobile'

const props = defineProps({
  projects: { type: Array, required: true },
  role: { type: String, default: 'admin' },
  showBugs: { type: Boolean, default: true },
  showDeliveryValue: { type: Boolean, default: true },
})

defineEmits(['navigate'])

const { isMobile } = useIsMobile()

const isAdmin = computed(() => props.role === 'admin')

function statusChipClass(state) {
  const base = 'mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium'
  const map = {
    emerald: 'bg-green-100 text-green-700',
    yellow: 'bg-amber-100 text-amber-700',
    orange: 'bg-orange-100 text-orange-700',
    blue: 'bg-sky-100 text-sky-700',
    red: 'bg-red-100 text-red-700',
    purple: 'bg-purple-100 text-purple-700',
    gray: 'bg-slate-100 text-slate-600',
  }
  return `${base} ${map[state?.color] || map.gray}`
}

function formatCurrency(value) {
  const n = Number(value || 0)
  if (!n) return '—'
  return new Intl.NumberFormat('es-CO', {
    style: 'currency', currency: 'COP', maximumFractionDigits: 0,
  }).format(n)
}

function relativeTime(iso) {
  if (!iso) return '—'
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60 * 24))
  if (days < 1) return 'Hoy'
  if (days === 1) return 'Ayer'
  if (days < 30) return `Hace ${days} días`
  if (days < 365) return `Hace ${Math.floor(days / 30)} meses`
  return `Hace ${Math.floor(days / 365)} años`
}
</script>
