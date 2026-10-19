<script setup>
import BaseBadge from '~/components/base/BaseBadge.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import PocketMovementRowActionsButton from './PocketMovementRowActionsButton.vue'
import { formatDate } from '~/utils/formatDate'
import { formatMoney } from '~/utils/formatMoney'
import { pocketAttributionLabel, signedPocketAmount } from '~/utils/pocketPresentation'

defineProps({
  rows: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  hasActiveFilters: { type: Boolean, default: false },
  highlightId: { type: [String, Number], default: null },
  detailToFor: { type: Function, default: null },
})

const emit = defineEmits(['open-actions', 'open-allocations'])
const { t } = useI18n()

</script>

<template>
  <section
    class="min-w-0 space-y-3"
    aria-label="Movimientos del bolsillo"
    data-testid="pocket-card-list"
    :aria-busy="loading ? 'true' : undefined"
  >
    <p class="sr-only" aria-live="polite">
      {{ loading ? 'Cargando movimientos...' : `${rows.length} movimientos` }}
    </p>

    <template v-if="loading">
      <div
        v-for="index in 3"
        :key="index"
        class="rounded-xl border border-border-muted bg-surface p-4 shadow-sm"
        data-testid="pocket-card-skeleton"
      >
        <div class="flex gap-3">
          <div class="h-11 w-11 shrink-0 rounded-lg bg-surface-raised motion-safe:animate-pulse" />
          <div class="min-w-0 flex-1 space-y-3">
            <div class="h-4 w-3/4 rounded bg-surface-raised motion-safe:animate-pulse" />
            <div class="h-7 w-1/2 rounded bg-surface-raised motion-safe:animate-pulse" />
            <div class="h-14 w-full rounded bg-surface-raised motion-safe:animate-pulse" />
          </div>
        </div>
      </div>
    </template>

    <article
      v-for="row in loading ? [] : rows"
      :key="row.id"
      class="min-w-0 rounded-xl border border-border-muted bg-surface p-4 shadow-sm"
      :class="row.id === highlightId ? 'accounting-row-flash' : ''"
      :data-testid="`pocket-card-${row.id}`"
    >
      <div class="flex min-w-0 items-start gap-3">
        <PocketMovementRowActionsButton
          :row="row"
          @open="emit('open-actions', $event)"
        />

        <div class="min-w-0 flex-1">
          <h2 class="break-words text-sm font-semibold leading-5 text-text-default">
            <BaseRowLink :to="detailToFor?.(row.id)" :data-testid="`pocket-open-${row.id}`">{{ row.concept }}</BaseRowLink>
          </h2>

          <div class="mt-2 flex min-w-0 flex-wrap items-center gap-2">
            <BaseButton
              v-if="Array.isArray(row.allocations) && row.allocations.length > 1"
              variant="ghost"
              size="sm"
              :title="`Ver reparto entre ${row.allocations.length} ingresos`"
              :aria-label="`Ver reparto del abono entre ${row.allocations.length} ingresos`"
              :data-testid="`pocket-allocations-${row.id}`"
              @click="emit('open-allocations', row)"
            >
              Abono · {{ row.allocations.length }}
            </BaseButton>
            <BaseBadge
              v-else-if="row.is_auto_managed"
              size="sm"
              title="Sincronizado con el ingreso o gasto vinculado"
              :data-testid="`pocket-linked-${row.id}`"
            >
              Vinculado
            </BaseBadge>
          </div>

          <p
            class="mt-3 break-normal text-xl font-semibold tabular-nums"
            :class="row.direction === 'out' ? 'text-danger-strong' : 'text-success-strong'"
            :data-testid="`pocket-amount-${row.id}`"
          >
            {{ signedPocketAmount(row) }}
          </p>

          <dl class="mt-4 grid min-w-0 grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-3 border-t border-border-muted pt-4 text-sm">
            <dt class="text-text-muted">{{ t('accountingPocket.belongsTo') }}</dt>
            <dd class="min-w-0 text-right text-text-default" :data-testid="`pocket-attribution-${row.id}`">{{ pocketAttributionLabel(row.linked_ledger, t) }}</dd>
            <dt class="text-text-muted">Fecha</dt>
            <dd class="min-w-0 text-right text-text-default" :data-testid="`pocket-date-${row.id}`">
              {{ formatDate(row.movement_date) }}
            </dd>

            <dt class="text-text-muted">Tipo</dt>
            <dd class="flex min-w-0 justify-end">
              <BaseBadge
                :variant="row.direction === 'in' ? 'success' : 'danger'"
                :data-testid="`pocket-direction-${row.id}`"
              >
                {{ row.direction_label }}
              </BaseBadge>
            </dd>

            <dt class="text-text-muted">
              {{ hasActiveFilters ? 'Acumulado filtrado' : 'Saldo después' }}
            </dt>
            <dd
              class="min-w-0 text-right font-medium tabular-nums text-text-default"
              :data-testid="`pocket-running-balance-${row.id}`"
            >
              {{ formatMoney(row.running_balance) }}
            </dd>
          </dl>
        </div>
      </div>
    </article>
  </section>
</template>
