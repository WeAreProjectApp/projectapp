<template>
  <ProjectShell>
    <ProjectHostingOverview :project-id="projectId" :show-payments="false" />
    <div id="platform-project-payments">
    <div v-if="payStore.isLoading" class="py-20 text-center">
      <div class="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-border-default border-t-esmerald dark:border-t-lemon" />
    </div>

    <template v-else>
      <!-- Header -->
      <div class="mb-6" data-enter>
        <h1 class="text-xl font-bold text-text-default sm:text-2xl">Hosting</h1>
      </div>

      <!-- No subscription — client picks plan; admin sees tiers + start dates -->
      <div v-if="!sub" data-enter>
        <div v-if="authStore.isAdmin" class="space-y-4">
          <!-- Per-phase tiers -->
          <div
            v-for="phase in payStore.phases"
            :key="phase.id"
            class="rounded-2xl border border-border-default bg-surface p-5"
          >
            <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p class="text-xs font-semibold uppercase tracking-wider text-text-muted">Fase {{ phase.order }}</p>
                <p class="mt-0.5 text-sm font-medium text-text-default">{{ phase.proposal?.title || '—' }}</p>
              </div>
              <!-- Date input -->
              <div class="flex items-center gap-2">
                <label class="text-xs text-text-muted whitespace-nowrap">Fecha inicio servicio:</label>
                <input
                  :value="phaseEditDates[phase.id] ?? phase.hosting_start_date ?? ''"
                  type="date"
                  class="rounded-lg border border-border-default bg-surface-muted/40 px-3 py-1.5 text-sm text-text-default outline-none focus:border-text-brand"
                  @input="phaseEditDates[phase.id] = $event.target.value"
                  @change="savePhasDate(phase.id)"
                />
                <span v-if="phaseSaving[phase.id]" class="text-xs text-text-muted">Guardando…</span>
                <span v-else-if="phaseSaved[phase.id]" class="text-xs text-text-brand">✓ Guardado</span>
              </div>
            </div>

            <!-- Tiers table -->
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-border-default">
                    <th class="pb-2 text-left text-xs font-medium text-text-muted">Frecuencia</th>
                    <th class="pb-2 text-right text-xs font-medium text-text-muted">Descuento</th>
                    <th class="pb-2 text-right text-xs font-medium text-text-muted">Equiv. mensual</th>
                    <th class="pb-2 text-right text-xs font-medium text-text-muted">Cobro por ciclo</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="tier in phase.hosting_tiers"
                    :key="tier.frequency"
                    class="border-b border-border-default/40 last:border-0"
                  >
                    <td class="py-2.5 font-medium text-text-default">{{ tier.label }}</td>
                    <td class="py-2.5 text-right text-text-muted">
                      <span v-if="tier.discount_percent" class="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-text-brand">{{ tier.discount_percent }}%</span>
                      <span v-else class="text-xs text-text-muted">—</span>
                    </td>
                    <td class="py-2.5 text-right text-text-default">${{ formatMoney(tier.monthly_equivalent) }}</td>
                    <td class="py-2.5 text-right font-semibold text-text-default">${{ formatMoney(tier.billing_amount) }} COP</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <p v-if="!payStore.phases.length" class="rounded-3xl border border-dashed border-border-default py-12 text-center text-sm text-text-muted">
            Este proyecto no tiene fases configuradas.
          </p>

          <p class="text-center text-xs text-text-muted">El cliente aún no ha activado su plan de hosting.</p>
        </div>
        <div v-else-if="payStore.phases.length" class="rounded-2xl border border-border-default bg-surface p-6">
          <h2 class="mb-1 text-lg font-bold text-text-default">Activa tu plan de hosting</h2>
          <p class="mb-4 text-xs text-green-light">
            El costo se calcula sumando el hosting de cada fase de tu proyecto. Elige con qué frecuencia quieres pagar.
          </p>

          <!-- Frequency pills -->
          <div class="mb-5 flex flex-wrap gap-2">
            <button
              v-for="opt in frequencyOptions"
              :key="opt.value"
              type="button"
              class="rounded-full border px-4 py-2 text-xs font-semibold transition"
              :class="selectedPlan === opt.value
                ? 'border-accent bg-accent text-text-default'
                : 'border-border-default bg-surface text-green-light hover:text-text-default'"
              @click="selectPlan(opt.value)"
            >{{ opt.label }}</button>
          </div>

          <!-- Per-phase breakdown table -->
          <div class="overflow-x-auto rounded-xl border border-border-default">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-border-default bg-surface-muted/30">
                  <th class="px-4 py-2.5 text-left text-xs font-medium text-text-muted">Fase</th>
                  <th class="px-4 py-2.5 text-right text-xs font-medium text-text-muted">Costo {{ selectedFrequencyLabel.toLowerCase() }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in phaseRows" :key="row.id" class="border-b border-border-default/40 last:border-0">
                  <td class="px-4 py-3">
                    <p class="font-medium text-text-default">Fase {{ row.order }} · {{ row.title }}</p>
                    <p v-if="!row.active" class="mt-0.5 text-[11px] text-amber-600 dark:text-amber-400">
                      Inicia el {{ formatDate(row.startDate) }} — se sumará entonces
                    </p>
                  </td>
                  <td class="px-4 py-3 text-right">
                    <span v-if="row.active" class="font-semibold text-text-default">${{ formatMoney(row.amount) }}</span>
                    <span v-else class="text-xs text-green-light/50">—</span>
                  </td>
                </tr>
              </tbody>
              <tfoot>
                <tr class="border-t-2 border-border-default bg-surface-muted/30">
                  <td class="px-4 py-3 text-sm font-bold text-text-default">Total a pagar ahora</td>
                  <td class="px-4 py-3 text-right text-lg font-bold text-text-brand">${{ formatMoney(hostingTotal) }} COP</td>
                </tr>
                <tr v-if="hostingSavings > 0" class="bg-surface-muted/30">
                  <td class="px-4 pb-3 text-xs font-medium text-text-brand">Ahorras con el plan {{ selectedFrequencyLabel.toLowerCase() }}</td>
                  <td class="px-4 pb-3 text-right text-xs font-semibold text-text-brand">− ${{ formatMoney(hostingSavings) }} COP</td>
                </tr>
              </tfoot>
            </table>
          </div>

          <p v-if="futurePhaseCount > 0" class="mt-3 text-[11px] text-green-light/60">
            Las fases con inicio futuro se cobrarán prorrateadas (solo los días que falten del ciclo) cuando llegue su fecha.
          </p>

          <div v-if="planError" class="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-600 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-400">
            {{ planError }}
          </div>

          <BaseButton variant="accent" size="md" class="mt-4 w-full" :disabled="!selectedPlan || isCreatingSub || hostingTotal <= 0" @click="handleCreateSubscription">
            <svg v-if="isCreatingSub" class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
            {{ isCreatingSub ? 'Activando...' : `Activar plan ${selectedFrequencyLabel.toLowerCase()}` }}
          </BaseButton>
          <p v-if="hostingTotal <= 0" class="mt-2 text-center text-[11px] text-amber-600 dark:text-amber-400">
            Ninguna fase tiene su hosting iniciado todavía. Espera a que el equipo configure las fechas de inicio.
          </p>
        </div>

        <div v-else class="rounded-3xl border border-dashed border-border-default py-16 text-center">
          <p class="text-sm text-green-light">Este proyecto no tiene suscripción de hosting.</p>
        </div>
      </div>

      <template v-else>
        <div
          v-if="sub.is_archived && authStore.isAdmin"
          class="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border-muted bg-surface-muted px-4 py-3"
          data-enter
        >
          <div class="flex items-center gap-2 text-xs text-green-light">
            <span class="rounded-full bg-surface-raised px-2 py-0.5 text-[10px] font-semibold uppercase text-text-muted dark:text-text-subtle">Suscripción archivada</span>
            <span v-if="sub.archived_at">desde {{ formatDate(sub.archived_at) }}</span>
          </div>
          <BaseButton variant="primary" size="sm" :disabled="payStore.isUpdating" @click="handleRestoreSubscription">
            {{ payStore.isUpdating ? '…' : 'Restaurar suscripción' }}
          </BaseButton>
        </div>

        <!-- Subscription summary -->
        <div
          class="mb-4 rounded-2xl border bg-surface p-6"
          :class="payStore.subscriptionUpToDate ? 'border-emerald-500/20 dark:border-emerald-500/15' : 'border-border-default'"
          data-enter
        >
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div class="flex items-center gap-4">
              <span
                v-if="payStore.subscriptionUpToDate"
                class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-emerald-500/10"
              >
                <svg class="h-7 w-7 text-text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              </span>
              <div>
                <div class="flex items-center gap-2">
                  <h2 class="text-lg font-bold text-text-default">Hosting {{ sub.plan_display }}</h2>
                  <span class="rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase" :class="subStatusClass(sub.status)">{{ sub.status_display }}</span>
                </div>
                <p class="mt-0.5 text-xs text-green-light">Inicio: {{ formatDate(sub.start_date) }}</p>
              </div>
            </div>
            <div class="text-right">
              <p class="text-2xl font-bold text-text-brand">${{ formatMoney(sub.billing_amount) }}</p>
              <p class="text-xs text-green-light">COP / {{ sub.plan_display.toLowerCase() }}</p>
            </div>
          </div>

          <div v-if="payStore.subscriptionUpToDate" class="mt-5 flex items-center gap-3 rounded-xl bg-primary-soft px-4 py-3">
            <svg class="h-4 w-4 shrink-0 text-text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
            <p class="text-sm text-text-brand">
              Se renueva y cobra automáticamente el <strong>{{ formatDate(payStore.nextRenewalDate) }}</strong>
            </p>
          </div>
        </div>

        <!-- Per-phase cost breakdown -->
        <div v-if="phaseRows.length" class="mb-4 rounded-2xl border border-border-default bg-surface p-5" data-enter>
          <h3 class="mb-3 text-sm font-medium text-text-default">Desglose por fase · {{ selectedFrequencyLabel }}</h3>

          <!-- Frequency still changeable while the subscription is pending -->
          <div v-if="frequencyEditable" class="mb-3">
            <div class="flex flex-wrap gap-2">
              <button
                v-for="opt in frequencyOptions"
                :key="opt.value"
                type="button"
                class="rounded-full border px-4 py-2 text-xs font-semibold transition"
                :class="selectedPlan === opt.value
                  ? 'border-accent bg-accent text-text-default'
                  : 'border-border-default bg-surface text-green-light hover:text-text-default'"
                @click="selectPlan(opt.value)"
              >{{ opt.label }}</button>
            </div>
            <p class="mt-2 text-[11px] text-green-light/60">
              Aún puedes cambiar la frecuencia. Quedará fija cuando registres tu tarjeta y se concrete el primer pago.
            </p>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <tbody>
                <tr v-for="row in phaseRows" :key="row.id" class="border-b border-border-default/40 last:border-0">
                  <td class="py-2.5">
                    <span class="text-text-default">Fase {{ row.order }} · {{ row.title }}</span>
                    <span v-if="!row.active" class="ml-2 text-[11px] text-amber-600 dark:text-amber-400">inicia el {{ formatDate(row.startDate) }}</span>
                  </td>
                  <td class="py-2.5 text-right">
                    <span v-if="row.active" class="font-medium text-text-default">${{ formatMoney(row.amount) }}</span>
                    <span v-else class="text-xs text-green-light/50">—</span>
                  </td>
                </tr>
                <tr class="border-t-2 border-border-default">
                  <td class="py-2.5 text-sm font-bold text-text-default">Total {{ selectedFrequencyLabel.toLowerCase() }}</td>
                  <td class="py-2.5 text-right text-base font-bold text-text-brand">${{ formatMoney(hostingTotal) }} COP</td>
                </tr>
                <tr v-if="hostingSavings > 0">
                  <td class="py-2 text-xs font-medium text-text-brand">Ahorras con el plan {{ selectedFrequencyLabel.toLowerCase() }}</td>
                  <td class="py-2 text-right text-xs font-semibold text-text-brand">− ${{ formatMoney(hostingSavings) }} COP</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Stored card on file -->
        <div v-if="sub.has_payment_source" class="mb-4 rounded-2xl border border-border-default bg-surface p-5" data-enter>
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div class="flex items-center gap-3">
              <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10">
                <svg class="h-5 w-5 text-text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>
              </span>
              <div>
                <p class="text-sm font-medium text-text-default">
                  {{ sub.card_brand || 'Tarjeta' }} •••• {{ sub.card_last_four || '••••' }}
                </p>
                <p class="mt-0.5 text-xs text-green-light">
                  <span v-if="sub.card_exp_month">Vence {{ sub.card_exp_month }}/{{ sub.card_exp_year }} · </span>Cobro automático activado
                </p>
              </div>
            </div>
            <div v-if="!authStore.isAdmin && !sub.is_archived" class="flex shrink-0 items-center gap-2">
              <BaseButton variant="secondary" size="sm" @click="openCardModal">
                Cambiar tarjeta
              </BaseButton>
              <BaseButton variant="danger-ghost" size="sm" @click="openDeleteCard">
                Eliminar tarjeta
              </BaseButton>
            </div>
          </div>
          <p v-if="!authStore.isAdmin" class="mt-3 text-[11px] text-green-light/60">
            ¿Necesitas cancelar o pausar tu suscripción? Escríbenos y lo gestionamos por ti.
          </p>
        </div>

        <!-- No card yet — client must register one -->
        <div
          v-else-if="!sub.is_archived"
          class="mb-4 rounded-2xl border border-amber-500/20 bg-amber-50/50 p-5 dark:border-amber-500/15 dark:bg-amber-500/5"
          data-enter
        >
          <div class="flex items-start gap-3">
            <svg class="h-5 w-5 shrink-0 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>
            <div class="flex-1">
              <p class="text-sm font-semibold text-text-default">Activa el cobro automático</p>
              <p class="mt-1 text-xs text-green-light">
                Registra una tarjeta una sola vez. Tu hosting se cobrará y renovará automáticamente al vencer cada periodo.
              </p>
              <BaseButton variant="accent" size="md" class="mt-3" v-if="!authStore.isAdmin" @click="openCardModal">
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>
                Registrar tarjeta
              </BaseButton>
              <p v-else class="mt-2 text-xs text-text-muted">El cliente aún no ha registrado una tarjeta.</p>
            </div>
          </div>
        </div>

        <!-- Payment action card -->
        <div v-if="currentPayment" class="mb-4 rounded-2xl border bg-surface p-5" :class="currentPeriodBorderClass" data-enter>
          <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div class="flex items-start gap-3">
              <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" :class="paymentIconBg(currentPayment.status)">
                <span class="text-base">{{ paymentIcon(currentPayment.status) }}</span>
              </span>
              <div>
                <p class="text-sm font-semibold text-text-default">
                  {{ currentPayment.status === 'pending' ? (authStore.isAdmin ? 'Pago pendiente del cliente' : 'Próximo cobro') : currentPayment.status === 'processing' ? 'Procesando pago' : (authStore.isAdmin ? 'Requiere accion del cliente' : 'Cobro pendiente') }}
                </p>
                <p class="mt-0.5 text-xs text-green-light">
                  {{ formatDate(currentPayment.billing_period_start) }} — {{ formatDate(currentPayment.billing_period_end) }}
                </p>
                <p v-if="currentPayment.status === 'failed'" class="mt-1 text-xs text-red-500 dark:text-red-400">
                  {{ currentPayment.last_charge_error || 'El cobro falló.' }}
                  <span v-if="currentPayment.next_retry_at">Reintentaremos el {{ formatDate(currentPayment.next_retry_at) }}.</span>
                </p>
                <p v-else-if="currentPayment.status === 'overdue'" class="mt-1 text-xs text-red-500 dark:text-red-400">
                  Cobro vencido. Renueva para mantener tu servicio.
                </p>
                <p v-else-if="currentPayment.status === 'processing'" class="mt-1 text-xs text-blue-500 dark:text-blue-400">
                  Tu pago está siendo procesado. Esto puede tomar unos minutos.
                </p>
                <p v-else-if="currentPayment.status === 'pending' && sub.has_payment_source && !authStore.isAdmin" class="mt-1 text-xs text-green-light">
                  Se cobrará automáticamente a tu tarjeta el {{ formatDate(currentPayment.due_date) }}.
                </p>
              </div>
            </div>

            <div class="flex items-center gap-4">
              <p class="text-2xl font-bold text-text-default">${{ formatMoney(currentPayment.amount) }}</p>
              <!-- No card: must register one -->
              <BaseButton variant="accent" size="md" class="shrink-0" v-if="!authStore.isAdmin && !sub.has_payment_source && canPay(currentPayment)" @click="openCardModal">
                Registrar tarjeta
              </BaseButton>
              <!-- Card on file: manual retry / pay now -->
              <BaseButton variant="accent" size="md" class="shrink-0" v-else-if="!authStore.isAdmin && sub.has_payment_source && canPay(currentPayment)" :disabled="retryingId === currentPayment.id" @click="retryCharge(currentPayment)">
                <svg v-if="retryingId === currentPayment.id" class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                {{ retryingId === currentPayment.id ? 'Cobrando…' : (currentPayment.status === 'pending' ? 'Pagar ahora' : 'Reintentar cobro') }}
              </BaseButton>
            </div>
          </div>
          <p v-if="retryError" class="mt-3 rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-xs text-red-600 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-400">
            {{ retryError }}
          </p>
          <PlatformPaymentStatusHistory :payment="currentPayment" />
        </div>

        <!-- Admin info alert -->
        <div v-if="authStore.isAdmin && currentPayment && canPay(currentPayment)" class="mb-4 rounded-2xl border border-amber-500/20 bg-amber-50/50 px-5 py-3 dark:border-amber-500/15 dark:bg-amber-500/5">
          <div class="flex items-center gap-3">
            <svg class="h-5 w-5 shrink-0 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            <p class="text-xs text-amber-700 dark:text-amber-400">
              {{ currentPayment.status === 'overdue' ? 'Este pago esta vencido. El cliente debe renovar su suscripcion.' : currentPayment.status === 'failed' ? 'El ultimo intento de cobro automatico fallo. El cliente debe reintentar o cambiar su tarjeta.' : 'Este pago esta pendiente. Se cobrara automaticamente si el cliente tiene tarjeta registrada.' }}
            </p>
          </div>
        </div>

        <!-- Payment history (collapsible) -->
        <div v-if="payStore.otherPayments.length > 0" data-enter>
          <button
            type="button"
            class="mb-3 flex w-full items-center gap-2 text-xs font-semibold uppercase tracking-wider text-green-light/60 transition hover:text-green-light"
            @click="showHistory = !showHistory"
          >
            <svg class="h-3.5 w-3.5 transition-transform" :class="showHistory ? 'rotate-90' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
            Historial y pagos programados ({{ payStore.otherPayments.length }})
          </button>

          <transition name="slide">
            <div v-show="showHistory" class="space-y-2">
              <div
                v-for="payment in payStore.otherPayments"
                :key="payment.id"
                class="rounded-xl border border-border-muted bg-surface px-5 py-3.5"
              >
                <div class="flex items-center justify-between gap-4">
                  <div class="flex items-center gap-2.5">
                    <span class="flex h-7 w-7 items-center justify-center rounded-lg" :class="paymentIconBg(payment.status)">
                      <span class="text-xs">{{ paymentIcon(payment.status) }}</span>
                    </span>
                    <div>
                      <p class="text-xs font-medium text-text-default">
                        {{ formatDate(payment.billing_period_start) }} — {{ formatDate(payment.billing_period_end) }}
                      </p>
                      <div v-if="payment.status === 'paid' && payment.paid_at" class="mt-0.5 text-[10px] text-text-brand/70">
                        Pagado el {{ formatDate(payment.paid_at) }}
                      </div>
                    </div>
                  </div>
                  <div class="flex items-center gap-3">
                    <p class="text-sm font-semibold text-text-default">${{ formatMoney(payment.amount) }}</p>
                    <span class="rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase" :class="paymentStatusClass(payment.status)">
                      {{ paymentStatusLabel(payment.status) }}
                    </span>
                  </div>
                </div>
                <PlatformPaymentStatusHistory :payment="payment" />
              </div>
            </div>
          </transition>
        </div>

        <div v-else-if="payStore.payments.length === 0" class="py-8 text-center text-sm text-green-light" data-enter>
          No hay pagos registrados aún.
        </div>
</template>

      <!-- Admin: registrar pago manual -->
      <div v-if="authStore.isAdmin" class="mt-6" data-enter>
        <button
          type="button"
          class="mb-3 flex w-full items-center gap-2 text-xs font-semibold uppercase tracking-wider text-green-light/60 transition hover:text-green-light"
          @click="showManualForm = !showManualForm"
        >
          <svg class="h-3.5 w-3.5 transition-transform" :class="showManualForm ? 'rotate-90' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
          Registrar pago manual
        </button>

        <transition name="slide">
          <div v-show="showManualForm" class="rounded-2xl border border-border-default bg-surface p-5">
            <p class="mb-4 text-xs text-text-muted">Registra un pago que fue recibido fuera de la plataforma (transferencia, efectivo, etc.).</p>

            <!-- Frecuencia -->
            <div class="mb-4">
              <p class="mb-2 text-xs font-medium text-text-muted">Frecuencia del intervalo pagado</p>
              <div class="grid grid-cols-3 gap-2">
                <button
                  v-for="opt in manualFreqOptions"
                  :key="opt.value"
                  type="button"
                  class="rounded-xl border-2 py-2.5 text-xs font-semibold transition"
                  :class="manualForm.frequency === opt.value ? '' : 'border-border-default text-text-muted'"
                  :style="freqButtonStyle(opt.value)"
                  @click="manualForm.frequency = opt.value"
                >
                  {{ opt.label }}
                </button>
              </div>
            </div>

            <!-- Monto y fecha -->
            <div class="mb-4 grid gap-3 sm:grid-cols-2">
              <div>
                <label class="mb-1.5 block text-xs font-medium text-text-muted">Monto cobrado (COP)</label>
                <input
                  v-model="manualForm.amount"
                  type="number"
                  min="1"
                  step="1"
                  placeholder="ej: 1200000"
                  class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-2.5 text-sm text-text-default outline-none focus:border-text-brand"
                />
              </div>
              <div>
                <label class="mb-1.5 block text-xs font-medium text-text-muted">Inicio del periodo pagado</label>
                <input
                  v-model="manualForm.billing_period_start"
                  type="date"
                  class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-2.5 text-sm text-text-default outline-none focus:border-text-brand"
                />
              </div>
            </div>

            <!-- Descripción -->
            <div class="mb-4">
              <label class="mb-1.5 block text-xs font-medium text-text-muted">Nota / descripción (opcional)</label>
              <input
                v-model="manualForm.description"
                type="text"
                maxlength="300"
                placeholder="ej: Transferencia bancaria Bancolombia"
                class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-2.5 text-sm text-text-default outline-none focus:border-text-brand"
              />
            </div>

            <!-- Error -->
            <div v-if="manualError" class="mb-3 rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-xs text-red-600 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-400">
              {{ manualError }}
            </div>

            <div class="flex items-center justify-end gap-3">
              <button
                type="button"
                class="text-xs text-text-muted transition hover:text-text-default"
                @click="resetManualForm"
              >
                Limpiar
              </button>
              <BaseButton variant="accent" size="sm" :disabled="payStore.isUpdating || !manualFormValid" @click="handleRegisterManualPayment">
                <svg v-if="payStore.isUpdating" class="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                {{ payStore.isUpdating ? 'Registrando…' : 'Registrar pago' }}
              </BaseButton>
            </div>
          </div>
        </transition>
      </div>
    </template>

    <!-- Card setup modal (3DS) -->
    <Teleport to="body">
      <Transition name="modal-overlay">
        <div v-if="cardModalOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 backdrop-blur-sm" @click.self="closeCardModal">
          <Transition name="modal-content" appear>
            <div v-if="cardModalOpen" class="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-3xl border border-border-default bg-surface p-6 shadow-2xl sm:p-8">
              <!-- Header -->
              <div class="mb-5 flex items-center justify-between">
                <div>
                  <h2 class="text-lg font-bold text-text-default">{{ sub?.has_payment_source ? 'Cambiar tarjeta' : 'Registrar tarjeta' }}</h2>
                  <p class="mt-0.5 text-xs text-green-light">Cobro automático de tu hosting</p>
                </div>
                <BaseButton
                  unstyled
                  icon-only
                  v-if="cardStep !== 'three_ds'"
                  type="button"
                  aria-label="Cerrar registro de tarjeta"
                  class="flex h-8 w-8 items-center justify-center rounded-full text-green-light transition hover:bg-surface-muted hover:text-text-default dark:hover:bg-white/10 dark:hover:text-white"
                  @click="closeCardModal"
                >
                  <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </BaseButton>
              </div>

              <!-- Step: card form -->
              <form v-if="cardStep === 'form'" class="space-y-3" @submit.prevent="submitCard">
                <div>
                  <label class="mb-1 block text-xs font-medium text-esmerald/70 dark:text-white/70">Número de tarjeta</label>
                  <input :value="cardForm.card_number" type="text" inputmode="numeric" maxlength="19" placeholder="4242 4242 4242 4242" required autocomplete="cc-number" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 font-mono text-sm tracking-wider text-text-default outline-none transition placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" @input="formatCardNumber" />
                </div>
                <div>
                  <label class="mb-1 block text-xs font-medium text-esmerald/70 dark:text-white/70">Titular de la tarjeta</label>
                  <input v-model="cardForm.card_holder" type="text" placeholder="Nombre como aparece en la tarjeta" required minlength="5" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                </div>
                <div class="grid grid-cols-3 gap-3">
                  <div>
                    <label class="mb-1 block text-xs font-medium text-esmerald/70 dark:text-white/70">Mes</label>
                    <input v-model="cardForm.exp_month" type="text" inputmode="numeric" maxlength="2" placeholder="MM" required class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-3 py-3 text-center text-sm text-text-default outline-none transition placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                  </div>
                  <div>
                    <label class="mb-1 block text-xs font-medium text-esmerald/70 dark:text-white/70">Año</label>
                    <input v-model="cardForm.exp_year" type="text" inputmode="numeric" maxlength="2" placeholder="AA" required class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-3 py-3 text-center text-sm text-text-default outline-none transition placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                  </div>
                  <div>
                    <label class="mb-1 block text-xs font-medium text-esmerald/70 dark:text-white/70">CVC</label>
                    <input v-model="cardForm.cvc" type="text" inputmode="numeric" maxlength="4" placeholder="123" required class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-3 py-3 text-center text-sm text-text-default outline-none transition placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                  </div>
                </div>

                <div v-if="cardError" class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-600 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-400">
                  {{ cardError }}
                </div>

                <BaseButton variant="accent" size="md" type="submit" class="mt-2 w-full" :disabled="cardBusy">
                  <svg v-if="cardBusy" class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                  <svg v-else class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
                  {{ cardBusy ? 'Registrando…' : 'Guardar tarjeta' }}
                </BaseButton>

                <p class="text-center text-[10px] text-green-light/50">
                  Tu tarjeta se guarda de forma segura en Wompi. Los cobros se hacen automáticamente al vencer cada periodo.
                </p>
              </form>

              <!-- Step: 3DS authentication -->
              <div v-else-if="cardStep === 'three_ds'" class="space-y-3">
                <div class="rounded-xl border border-border-default bg-surface-muted/20 p-4 text-center">
                  <div class="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-border-default border-t-esmerald dark:border-t-lemon" />
                  <p class="mt-3 text-sm font-medium text-text-default">{{ threeDsMessage }}</p>
                  <p class="mt-1 text-xs text-green-light">No cierres esta ventana.</p>
                </div>
                <!-- 3DS frame: tiny/hidden for BROWSER_INFO & FINGERPRINT, visible for CHALLENGE -->
                <iframe
                  v-if="threeDsHtml"
                  :srcdoc="threeDsHtml"
                  title="Verificación 3D Secure"
                  class="w-full overflow-hidden rounded-xl border transition-all"
                  :class="threeDsStep === 'CHALLENGE'
                    ? 'h-[420px] border-border-default'
                    : 'h-px w-px border-transparent opacity-0'"
                />
              </div>

              <!-- Step: done -->
              <div v-else-if="cardStep === 'done'" class="space-y-3 text-center">
                <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500/10">
                  <svg class="h-7 w-7 text-text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                </div>
                <p class="text-sm font-semibold text-text-default">Tarjeta registrada</p>
                <p class="text-xs text-green-light">{{ cardDoneMessage }}</p>
                <BaseButton variant="accent" size="md" class="mt-2 w-full" @click="closeCardModal">
                  Listo
                </BaseButton>
              </div>

              <!-- Step: error -->
              <div v-else-if="cardStep === 'error'" class="space-y-3 text-center">
                <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-red-500/10">
                  <svg class="h-7 w-7 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </div>
                <p class="text-sm font-semibold text-text-default">No se pudo registrar la tarjeta</p>
                <p class="text-xs text-red-500 dark:text-red-400">{{ cardError }}</p>
                <BaseButton variant="accent" size="md" class="mt-2 w-full" @click="cardStep = 'form'">
                  Intentar de nuevo
                </BaseButton>
              </div>

              <!-- Security footer -->
              <div class="mt-4 flex items-center justify-center gap-2">
                <svg class="h-3.5 w-3.5 text-green-light/40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
                <span class="text-[10px] text-green-light/40">Conexión segura · 3D Secure · Procesado por Wompi</span>
              </div>
            </div>
          </Transition>
        </div>
      </Transition>
    </Teleport>

    <!-- Delete card confirmation modal -->
    <Teleport to="body">
      <Transition name="modal-overlay">
        <div v-if="deleteCardOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 backdrop-blur-sm" @click.self="closeDeleteCard">
          <Transition name="modal-content" appear>
            <div v-if="deleteCardOpen" class="w-full max-w-md rounded-3xl border border-border-default bg-surface p-6 shadow-2xl sm:p-8">
              <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-red-500/10">
                <svg class="h-7 w-7 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
              </div>
              <h2 class="text-center text-lg font-bold text-text-default">¿Eliminar tarjeta?</h2>
              <p class="mt-2 text-center text-sm text-green-light">
                Se eliminará la tarjeta {{ sub?.card_brand || '' }} •••• {{ sub?.card_last_four || '••••' }} y se desactivará el cobro automático. Tendrás que registrar una tarjeta de nuevo para reactivarlo.
              </p>

              <div v-if="deleteCardError" class="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-600 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-400">
                {{ deleteCardError }}
              </div>

              <div class="mt-6 flex flex-col gap-2 sm:flex-row-reverse">
                <BaseButton variant="danger-ghost" size="sm" :disabled="deleteCardBusy" @click="confirmDeleteCard">
                  <svg v-if="deleteCardBusy" class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                  {{ deleteCardBusy ? 'Eliminando…' : 'Sí, eliminar' }}
                </BaseButton>
                <BaseButton variant="ghost" size="md" class="flex-1" :disabled="deleteCardBusy" @click="closeDeleteCard">
                  Cancelar
                </BaseButton>
              </div>
            </div>
          </Transition>
        </div>
      </Transition>
    </Teleport>
  </div>
  </ProjectShell>
</template>

<script setup>
import ProjectHostingOverview from '~/components/platform/billing/ProjectHostingOverview.vue'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { usePageEntrance } from '~/composables/usePageEntrance'
import { usePlatformApi } from '~/composables/usePlatformApi'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformPaymentsStore } from '~/stores/platform-payments'
import { usePlatformProjectsStore } from '~/stores/platform-projects'
import { formatDate } from '~/utils/formatDate'
import ProjectShell from '~/components/platform/projects/ProjectShell.vue'

definePageMeta({ layout: 'platform', middleware: ['platform-auth'] })
usePageEntrance('#platform-project-payments')

const route = useRoute()
const authStore = usePlatformAuthStore()
const payStore = usePlatformPaymentsStore()
const projectsStore = usePlatformProjectsStore()

const projectId = computed(() => route.params.id)
const project = computed(() => projectsStore.currentProject)
const sub = computed(() => payStore.currentSubscription)
const currentPayment = computed(() => payStore.currentPeriodPayment)
const showHistory = ref(false)

const selectedPlan = ref('semiannual')
const isCreatingSub = ref(false)
const planError = ref('')

const frequencyOptions = [
  { value: 'quarterly', label: 'Trimestral' },
  { value: 'semiannual', label: 'Semestral' },
  { value: 'nine_month', label: 'Cada 9 meses' },
]
const selectedFrequencyLabel = computed(
  () => frequencyOptions.find((o) => o.value === selectedPlan.value)?.label
    || sub.value?.plan_display
    || '',
)

// The frequency stays editable until the first payment settles (the
// subscription leaves 'pending'); the breakdown table values it by selectedPlan.
const frequencyEditable = computed(() => !sub.value || sub.value.status === 'pending')
const tableFrequency = computed(
  () => (frequencyEditable.value ? selectedPlan.value : sub.value.plan),
)

async function selectPlan(value) {
  selectedPlan.value = value
  // A pending subscription already exists — persist the new frequency.
  if (sub.value && sub.value.status === 'pending') {
    await payStore.updateSubscription(projectId.value, { plan: value })
  }
}

function phaseTier(phase, frequency) {
  return (phase.hosting_tiers || []).find((t) => t.frequency === frequency) || null
}

const phaseRows = computed(() => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return (payStore.phases || []).map((p) => {
    const tier = phaseTier(p, tableFrequency.value)
    const amount = tier ? tier.billing_amount : 0
    // Undiscounted list price for the same span (base monthly × months).
    const fullPrice = tier && tier.base_monthly
      ? tier.base_monthly * tier.months
      : amount
    return {
      id: p.id,
      order: p.order,
      title: p.proposal?.title || `Fase ${p.order}`,
      startDate: p.hosting_start_date,
      active: sub.value
        ? !!p.hosting_activated_at
        : (!p.hosting_start_date || new Date(p.hosting_start_date) <= today),
      amount,
      savings: Math.max(fullPrice - amount, 0),
    }
  })
})

const hostingTotal = computed(
  () => phaseRows.value.filter((r) => r.active).reduce((sum, r) => sum + r.amount, 0),
)
const hostingSavings = computed(
  () => phaseRows.value.filter((r) => r.active).reduce((sum, r) => sum + r.savings, 0),
)
const futurePhaseCount = computed(() => phaseRows.value.filter((r) => !r.active).length)

// Phase hosting-date editing (admin only)
const phaseEditDates = reactive({})
const phaseSaving = reactive({})
const phaseSaved = reactive({})

// Manual payment form (admin only)
const showManualForm = ref(false)
const manualError = ref('')
const manualFreqOptions = [
  { value: 'quarterly', label: 'Trimestral' },
  { value: 'semiannual', label: 'Semestral' },
  { value: 'nine_month', label: 'Cada 9 meses' },
]
const manualForm = reactive({ frequency: '', amount: '', billing_period_start: '', description: '' })
const manualFormValid = computed(() =>
  manualForm.frequency && manualForm.amount > 0 && manualForm.billing_period_start,
)
const freqSelectedColor = ref('#002921')
function freqButtonStyle(optValue) {
  if (manualForm.frequency !== optValue) return ''
  return `background-color: ${freqSelectedColor.value} !important; border-color: ${freqSelectedColor.value} !important; color: #ffffff !important`
}

async function savePhasDate(phaseId) {
  const dateVal = phaseEditDates[phaseId]
  if (dateVal === undefined) return
  phaseSaving[phaseId] = true
  phaseSaved[phaseId] = false
  const result = await payStore.patchPhaseHostingDate(projectId.value, phaseId, dateVal || null)
  phaseSaving[phaseId] = false
  if (result.success) {
    phaseSaved[phaseId] = true
    setTimeout(() => { phaseSaved[phaseId] = false }, 2500)
  }
}

// --- Delete card ---
const deleteCardOpen = ref(false)
const deleteCardBusy = ref(false)
const deleteCardError = ref('')

function openDeleteCard() {
  deleteCardError.value = ''
  deleteCardOpen.value = true
}

function closeDeleteCard() {
  if (deleteCardBusy.value) return
  deleteCardOpen.value = false
}

async function confirmDeleteCard() {
  deleteCardBusy.value = true
  deleteCardError.value = ''
  const r = await payStore.deletePaymentMethod(projectId.value)
  deleteCardBusy.value = false
  if (!r.success) {
    deleteCardError.value = r.message
    return
  }
  deleteCardOpen.value = false
  await payStore.fetchProjectSubscription(projectId.value)
}

// --- Card setup (3DS) ---
const cardModalOpen = ref(false)
const cardStep = ref('form') // form | three_ds | done | error
const cardBusy = ref(false)
const cardError = ref('')
const cardDoneMessage = ref('')
const cardForm = reactive({ card_number: '', card_holder: '', exp_month: '', exp_year: '', cvc: '' })

const paymentSourceId = ref(null)
const cardBrand = ref('')
const cardLastFour = ref('')
const threeDsStep = ref('')
const threeDsHtml = ref('')

const threeDsMessage = computed(() => {
  if (threeDsStep.value === 'CHALLENGE') return 'Tu banco requiere que confirmes la operación en el recuadro de abajo.'
  if (threeDsStep.value === 'AUTHENTICATION') return 'Finalizando la verificación…'
  return 'Verificando tu tarjeta con el banco…'
})

// --- Manual retry of a charge using the stored card ---
const retryingId = ref(null)
const retryError = ref('')

// Card transactions settle asynchronously. When a payment is left PROCESSING
// (the webhook can't reach localhost in dev), poll the verify endpoint until
// it resolves to paid/failed.
const isPollingPayment = ref(false)
async function pollProcessingPayment() {
  if (isPollingPayment.value) return
  isPollingPayment.value = true
  const pollingProjectId = projectId.value
  try {
    for (let i = 0; i < 12; i += 1) {
      const p = payStore.currentPeriodPayment
      if (!p || p.status !== 'processing') return
      await sleep(3000)
      if (String(projectId.value) !== String(pollingProjectId)) return
      await payStore.verifyTransaction(pollingProjectId, p.id)
      await payStore.fetchProjectSubscription(projectId.value)
    }
  } finally {
    isPollingPayment.value = false
  }
}

const currentPeriodBorderClass = computed(() => {
  if (!currentPayment.value) return 'border-border-default'
  return paymentBorderClass(currentPayment.value.status)
})

function canPay(payment) {
  return ['pending', 'overdue', 'failed'].includes(payment.status)
}

function subStatusClass(s) {
  const map = {
    active: 'bg-emerald-500/15 text-text-brand',
    pending: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
    suspended: 'bg-red-500/15 text-red-600 dark:text-red-400',
    cancelled: 'bg-surface-raised text-text-muted',
  }
  return map[s] || map.pending
}

function paymentBorderClass(s) {
  const map = {
    pending: 'border-amber-500/20 dark:border-amber-500/15',
    overdue: 'border-red-500/20 dark:border-red-500/15',
    paid: 'border-border-default',
    processing: 'border-blue-500/20 dark:border-blue-500/15',
    failed: 'border-red-500/20 dark:border-red-500/15',
    voided: 'border-border-default',
  }
  return map[s] || 'border-border-default'
}

function paymentIconBg(s) {
  const map = {
    pending: 'bg-amber-500/10', overdue: 'bg-red-500/10',
    paid: 'bg-emerald-500/10', processing: 'bg-blue-500/10', failed: 'bg-red-500/10',
    voided: 'bg-surface-raised',
  }
  return map[s] || 'bg-surface-raised'
}

function paymentIcon(s) {
  const map = { pending: '⏳', overdue: '⚠️', paid: '✅', processing: '🔄', failed: '❌', voided: '➖' }
  return map[s] || '💳'
}

function paymentStatusClass(s) {
  const map = {
    pending: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
    overdue: 'bg-red-500/15 text-red-600 dark:text-red-400',
    paid: 'bg-emerald-500/15 text-text-brand',
    processing: 'bg-blue-500/15 text-blue-600 dark:text-blue-400',
    failed: 'bg-red-500/15 text-red-600 dark:text-red-400',
    voided: 'bg-surface-raised text-text-muted',
  }
  return map[s] || map.pending
}

function paymentStatusLabel(s) {
  const map = { pending: 'Pendiente', overdue: 'Vencido', paid: 'Pagado', processing: 'Procesando', failed: 'Fallido', voided: 'Anulado' }
  return map[s] || s
}

function formatMoney(val) {
  if (!val) return '0'
  return Number(val).toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).replace(/,/g, '.')
}

function formatCardNumber(event) {
  const raw = event.target.value.replace(/\D/g, '').slice(0, 16)
  const formatted = raw.replace(/(.{4})/g, '$1 ').trim()
  cardForm.card_number = formatted
  event.target.value = formatted
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

// Decode HTML entities in the 3DS method data without using innerHTML.
function decodeHtml(s) {
  if (!s) return ''
  return s
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&#0?39;/g, "'")
    .replace(/&#x27;/gi, "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCharCode(parseInt(n, 16)))
    .replace(/&amp;/g, '&')
}

function openCardModal() {
  cardModalOpen.value = true
  cardStep.value = 'form'
  cardBusy.value = false
  cardError.value = ''
  cardDoneMessage.value = ''
  cardForm.card_number = ''
  cardForm.card_holder = ''
  cardForm.exp_month = ''
  cardForm.exp_year = ''
  cardForm.cvc = ''
  paymentSourceId.value = null
  cardBrand.value = ''
  cardLastFour.value = ''
  threeDsStep.value = ''
  threeDsHtml.value = ''
}

function closeCardModal() {
  if (cardStep.value === 'three_ds') return
  cardModalOpen.value = false
}

async function submitCard() {
  cardBusy.value = true
  cardError.value = ''

  const result = await payStore.startCardSetup(projectId.value, {
    card_number: cardForm.card_number.replace(/\s/g, ''),
    exp_month: cardForm.exp_month,
    exp_year: cardForm.exp_year,
    cvc: cardForm.cvc,
    card_holder: cardForm.card_holder,
  })

  cardBusy.value = false

  if (!result.success) {
    cardError.value = result.message
    return
  }

  const d = result.data
  paymentSourceId.value = d.payment_source_id
  cardBrand.value = d.card_brand || ''
  cardLastFour.value = d.card_last_four || ''

  if (d.status === 'AVAILABLE') {
    cardStep.value = 'three_ds'
    await confirmCard()
    return
  }
  if (d.status === 'DECLINED' || d.status === 'ERROR') {
    cardStep.value = 'error'
    cardError.value = 'Tu banco rechazó la tarjeta. Verifica los datos o usa otra tarjeta.'
    return
  }

  // PENDING — run the 3DS / verification flow.
  cardStep.value = 'three_ds'
  const auth = d.three_ds_auth || {}
  threeDsStep.value = auth.current_step || ''
  threeDsHtml.value = decodeHtml(auth.three_ds_method_data)
  await pollCardStatus()
}

async function pollCardStatus() {
  for (let i = 0; i < 90; i++) {
    await sleep(2000)
    if (!cardModalOpen.value) return
    const r = await payStore.getCardSetupStatus(projectId.value, paymentSourceId.value)
    if (!r.success) continue

    const d = r.data
    const auth = d.three_ds_auth || {}
    if (auth.current_step) threeDsStep.value = auth.current_step
    if (auth.three_ds_method_data) {
      const decoded = decodeHtml(auth.three_ds_method_data)
      if (decoded !== threeDsHtml.value) threeDsHtml.value = decoded
    }

    if (d.status === 'AVAILABLE') {
      await confirmCard()
      return
    }
    if (d.status === 'DECLINED' || d.status === 'ERROR') {
      cardStep.value = 'error'
      cardError.value = 'La verificación con tu banco no se completó. Intenta de nuevo o usa otra tarjeta.'
      return
    }
  }
  cardStep.value = 'error'
  cardError.value = 'La verificación tardó demasiado. Intenta de nuevo.'
}

async function confirmCard() {
  const r = await payStore.confirmCardSetup(projectId.value, paymentSourceId.value, {
    card_brand: cardBrand.value,
    card_last_four: cardLastFour.value,
    exp_month: cardForm.exp_month,
    exp_year: cardForm.exp_year,
  })

  if (!r.success) {
    cardStep.value = 'error'
    cardError.value = r.message
    return
  }

  const charge = r.data.charge
  if (charge && charge.transaction_status === 'APPROVED') {
    cardDoneMessage.value = 'Tu primer pago fue procesado. Las próximas renovaciones se cobrarán automáticamente.'
  } else if (charge && charge.transaction_status === 'PENDING') {
    cardDoneMessage.value = 'Tu pago se está procesando. Las próximas renovaciones se cobrarán automáticamente.'
  } else if (charge && charge.error) {
    cardDoneMessage.value = 'Tu tarjeta quedó guardada, pero el primer cobro falló. Puedes reintentarlo desde esta página.'
  } else {
    cardDoneMessage.value = 'Tu tarjeta quedó guardada. Las renovaciones se cobrarán automáticamente.'
  }
  cardStep.value = 'done'
  await payStore.fetchProjectSubscription(projectId.value)
  pollProcessingPayment()
}

async function retryCharge(payment) {
  retryingId.value = payment.id
  retryError.value = ''
  const r = await payStore.chargeStored(projectId.value, payment.id)
  retryingId.value = null
  if (!r.success) {
    retryError.value = r.message
    return
  }
  await payStore.fetchProjectSubscription(projectId.value)
  pollProcessingPayment()
}

async function handleCreateSubscription() {
  if (!selectedPlan.value) return
  isCreatingSub.value = true
  planError.value = ''

  try {
    const { post } = usePlatformApi()
    await post(`projects/${projectId.value}/subscription/`, { plan: selectedPlan.value })
    await Promise.all([
      payStore.fetchProjectSubscription(projectId.value),
      payStore.fetchProjectPhases(projectId.value),
    ])
  } catch (error) {
    planError.value = error.response?.data?.detail || 'Error activando el plan de hosting.'
  } finally {
    isCreatingSub.value = false
  }
}

async function handleRestoreSubscription() {
  const result = await payStore.updateSubscription(projectId.value, { is_archived: false })
  if (result.success) {
    await payStore.fetchProjectSubscription(projectId.value)
  }
}

function resetManualForm() {
  manualForm.frequency = ''
  manualForm.amount = ''
  manualForm.billing_period_start = ''
  manualForm.description = ''
  manualError.value = ''
}

async function handleRegisterManualPayment() {
  manualError.value = ''
  const result = await payStore.registerManualPayment(projectId.value, {
    frequency: manualForm.frequency,
    amount: Number(manualForm.amount),
    billing_period_start: manualForm.billing_period_start,
    description: manualForm.description,
  })
  if (result.success) {
    resetManualForm()
    showManualForm.value = false
    await payStore.fetchProjectSubscription(projectId.value)
  } else {
    manualError.value = result.message
  }
}

watch(projectId, async id => {
  Object.keys(phaseEditDates).forEach(key => delete phaseEditDates[key])
  await Promise.all([payStore.fetchProjectSubscription(id), payStore.fetchProjectPhases(id), projectsStore.fetchProject(id)])
  if (sub.value) selectedPlan.value = sub.value.plan
})

onMounted(async () => {
  const dark = getComputedStyle(document.documentElement).getPropertyValue('--theme-dark').trim()
  if (dark) freqSelectedColor.value = dark

  await Promise.all([
    payStore.fetchProjectSubscription(projectId.value),
    projectsStore.currentProject?.id !== Number(projectId.value) ? projectsStore.fetchProject(projectId.value) : Promise.resolve(),
    payStore.fetchProjectPhases(projectId.value),
  ])
  // Preselect the established frequency so the breakdown table values match.
  if (sub.value) selectedPlan.value = sub.value.plan
  pollProcessingPayment()
})
</script>

<style scoped>
.freq-selected {
  background-color: var(--theme-dark, #002921) !important;
  border-color: var(--theme-dark, #002921) !important;
  color: #ffffff !important;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
}
.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 1000px;
}
</style>
