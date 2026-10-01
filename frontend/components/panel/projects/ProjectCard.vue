<script setup>
import { computed } from 'vue'
import ProjectStateHelpBadge from '~/components/panel/projects/ProjectStateHelpBadge.vue'
import { stateBadgeVariant } from '~/utils/documentState'
import { formatDate } from '~/utils/formatDate'

const props = defineProps({
  project: { type: Object, required: true },
  isSuperuser: { type: Boolean, default: false },
  highlighted: { type: Boolean, default: false },
})

const emit = defineEmits(['actions', 'assign', 'change-state'])

const statusTone = computed(() => stateBadgeVariant(props.project.current_state))
const isTerminal = computed(() => ['completed', 'decommissioned'].includes(
  props.project.current_state?.operational_effect,
))

const unlinkedTotal = computed(() => (
  (props.project.unlinked_hostings_count ?? 0)
  + (props.project.unlinked_incomes_count ?? 0)
  + (props.project.unlinked_documents_count ?? 0)
))
</script>

<template>
  <article
    class="flex min-w-0 flex-col rounded-xl border border-border-muted bg-surface p-4 shadow-card"
    :class="highlighted ? 'ring-2 ring-focus-ring/40 bg-primary-soft' : ''"
    :data-testid="`project-card-${project.id}`"
  >
    <div class="min-w-0 max-w-full">
      <div class="min-w-0 max-w-full">
        <h2 class="min-w-0 max-w-full text-base font-semibold text-text-default [overflow-wrap:anywhere]" :title="project.name">{{ project.name }}</h2>
        <p class="mt-1 min-w-0 max-w-full text-sm text-text-muted [overflow-wrap:anywhere]">{{ project.client_name || 'Sin cliente' }}</p>
        <p v-if="project.client_company" class="min-w-0 max-w-full text-xs text-text-subtle [overflow-wrap:anywhere]">
          {{ project.client_company }}
        </p>
      </div>
      <div class="mt-3 flex items-center gap-1.5">
        <BaseBadge
          :variant="statusTone"
          size="sm"
          :data-testid="`project-card-status-${project.id}`"
        >
          {{ project.status_label }}
        </BaseBadge>
        <ProjectStateHelpBadge
          v-if="project.current_state"
          :state="project.current_state"
          position="bottom"
          :test-id="`project-card-state-help-${project.id}`"
        />
      </div>
    </div>

    <dl class="mt-4 grid grid-cols-3 gap-2 rounded-lg bg-surface-muted p-3 text-center">
      <div>
        <dt class="text-2xs uppercase tracking-wide text-text-subtle">Creado</dt>
        <dd class="mt-1 text-xs font-medium text-text-default">{{ formatDate(project.created_at) }}</dd>
      </div>
      <div>
        <dt class="text-2xs uppercase tracking-wide text-text-subtle">Hostings</dt>
        <dd class="mt-1 text-sm font-semibold tabular-nums">
          <NuxtLink
            v-if="isSuperuser && project.hostings_count > 0"
            :to="{ path: '/panel/accounting/hostings', query: { project: project.id } }"
            class="text-text-brand hover:underline"
            :data-testid="`project-hostings-link-${project.id}`"
          >
            {{ project.hostings_count }}
          </NuxtLink>
          <span v-else class="text-text-default">{{ project.hostings_count }}</span>
        </dd>
      </div>
      <div>
        <dt class="text-2xs uppercase tracking-wide text-text-subtle">Ingresos</dt>
        <dd class="mt-1 text-sm font-semibold tabular-nums">
          <NuxtLink
            v-if="isSuperuser && project.incomes_count > 0"
            :to="{
              path: '/panel/accounting/incomes',
              query: { accounting_incomeTab: 'all', project: project.id },
            }"
            class="text-text-brand hover:underline"
            :data-testid="`project-incomes-link-${project.id}`"
          >
            {{ project.incomes_count }}
          </NuxtLink>
          <span v-else class="text-text-default">{{ project.incomes_count }}</span>
        </dd>
      </div>
    </dl>

    <BaseButton
      v-if="project.state_review_required || project.state_suggestion"
      variant="ghost"
      size="sm"
      class="mt-3 w-full justify-start text-warning-strong"
      :data-testid="`project-state-review-${project.id}`"
      @click="emit('change-state', project)"
    >
      {{ project.state_suggestion ? 'Revisar suspensión sugerida' : 'Confirmar estado real' }}
    </BaseButton>

    <BaseButton
      v-if="unlinkedTotal > 0 && !isTerminal"
      variant="ghost"
      size="sm"
      class="mt-3 w-full justify-start text-warning-strong"
      :data-testid="`project-assign-unlinked-${project.id}`"
      @click="emit('assign', project)"
    >
      {{ unlinkedTotal }} {{ unlinkedTotal === 1 ? 'registro' : 'registros' }} sin proyecto
    </BaseButton>

    <div class="mt-auto flex items-center justify-start pt-4">
      <BaseActionButton
        action="more"
        variant="ghost"
        size="md"
        :label="$t('projectAccess.projectActions.label', { name: project.name })"
        :data-testid="`project-actions-${project.id}`"
        @click="emit('actions', project)"
      />
    </div>
  </article>
</template>
