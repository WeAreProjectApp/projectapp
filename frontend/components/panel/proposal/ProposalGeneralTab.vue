<template>
  <div>
  <TabSplitLayout ratio="1:1" :aside-first-mobile="true">
    <template #aside>
  <!-- Editable slug (URL personalizada) -->
  <div class="bg-surface border border-border-muted rounded-xl p-4 sm:p-5 mb-4">
    <label class="text-xs font-medium text-text-muted uppercase tracking-wider" for="proposal-slug-input">
      URL personalizada
    </label>
    <div class="mt-2 flex flex-wrap items-stretch gap-2">
      <div class="flex-1 min-w-[260px] flex items-stretch rounded-lg border border-border-default bg-surface-raised focus-within:border-focus-ring focus-within:ring-1 focus-within:ring-focus-ring/30">
        <span class="px-3 flex items-center text-xs text-text-subtle border-r border-border-default select-none">/proposal/</span>
        <input
          id="proposal-slug-input"
          v-model="slugDraft"
          type="text"
          data-testid="proposal-slug-input"
          class="flex-1 bg-transparent px-3 py-2 text-sm text-text-default placeholder:text-text-subtle focus:outline-none font-mono"
          placeholder="maria-lopez"
          maxlength="120"
          @keydown.enter.prevent="saveSlug"
        />
      </div>
      <BaseButton variant="primary" size="sm" :loading="slugSaving" :disabled="slugDraft === (proposal.slug || '')" disabled-reason="Cambia la URL personalizada antes de guardarla." @click="saveSlug">
        {{ slugSaving ? 'Guardando…' : (slugSaved ? 'Guardado' : 'Guardar') }}
      </BaseButton>
      <BaseButton variant="secondary" size="sm" :title="'Regenerar desde el nombre del cliente'" @click="regenerateSlugFromName">
        Regenerar
      </BaseButton>
    </div>
    <p v-if="slugError" class="text-xs text-danger-strong mt-2">{{ slugError }}</p>
    <p v-else class="text-xs text-text-subtle mt-2">
      Solo minúsculas, números y guiones. El cliente verá esta URL en el enlace.
    </p>
  </div>

  <div
    class="mb-4 rounded-xl border border-primary/30 bg-primary-soft px-4 py-3 sm:px-5 sm:py-4 text-sm"
    aria-label="Identificación y estado de la propuesta"
  >
    <span class="inline-flex items-center gap-1 mb-3 px-2 py-0.5 rounded-full bg-primary-soft text-[10px] font-medium uppercase tracking-wider text-text-brand">
      Identificación
    </span>
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div>
        <span class="text-text-subtle text-xs">UUID</span>
        <p class="text-text-muted font-mono text-xs mt-0.5">{{ proposal.uuid }}</p>
      </div>
      <div>
        <div class="flex items-center gap-1">
          <span class="text-text-subtle text-xs">URL pública</span>
          <BaseActionButton
            action="copy"
            :label="copyFeedback('public').label || 'Copiar URL pública'"
            :status-label="copyFeedback('public').label"
            :status-tone="copyFeedback('public').tone"
            @click="copyUrl"
            class="-my-1 text-text-subtle hover:text-text-brand"
          />
        </div>
        <p class="mt-0.5">
          <a :href="'/proposal/' + publicIdentifier" target="_blank" rel="noopener noreferrer" class="text-text-brand hover:underline text-xs break-all">
            /proposal/{{ publicIdentifier }}
          </a>
        </p>
        <div v-for="link in proposalModeLinks" :key="link.mode" class="mt-2">
          <div class="flex items-center gap-1">
            <span class="text-text-subtle text-xs">{{ link.labelUrl }}</span>
            <BaseActionButton
              action="copy"
              :label="copyFeedback(link.mode).label || `Copiar ${link.labelUrl}`"
              :status-label="copyFeedback(link.mode).label"
              :status-tone="copyFeedback(link.mode).tone"
              @click="copyModeUrl(link.mode)"
              class="-my-1 text-text-subtle hover:text-text-brand"
            />
          </div>
          <p class="mt-0.5">
            <a :href="'/proposal/' + publicIdentifier + '?mode=' + link.mode" target="_blank" rel="noopener noreferrer" class="text-text-brand hover:underline text-xs break-all">
              /proposal/{{ publicIdentifier }}?mode={{ link.mode }}
            </a>
          </p>
        </div>
      </div>
      <div>
        <span class="text-text-subtle text-xs">Vistas</span>
        <p class="text-text-muted mt-0.5">{{ proposal.view_count }}</p>
      </div>
      <div>
        <span class="text-text-subtle text-xs">Enviada</span>
        <p class="text-text-muted mt-0.5">
          {{ proposal.sent_at ? new Date(proposal.sent_at).toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric' }) : '—' }}
        </p>
      </div>
      <div v-if="proposal.platform_onboarding_completed_at">
        <span class="text-text-subtle text-xs">Plataforma lanzada</span>
        <p class="text-text-muted mt-0.5 text-xs">
          {{ new Date(proposal.platform_onboarding_completed_at).toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' }) }}
        </p>
      </div>
      <div v-if="!hasDocumentsTab">
        <span class="text-text-subtle text-xs">PDFs</span>
        <div class="flex items-center gap-3 mt-0.5 flex-wrap">
          <PanelDownloadLink :url="'/api/proposals/' + proposal.id + '/pdf/'"
            filename="propuesta-comercial.pdf" variant="link" label="Propuesta comercial" />
          <span class="text-text-subtle text-xs">|</span>
          <PanelDownloadLink :url="'/api/proposals/' + proposal.id + '/pdf/?doc=technical'"
            filename="detalle-tecnico.pdf" variant="link" label="Detalle técnico" />
        </div>
      </div>
      <div class="sm:col-span-2">
        <div class="flex items-start gap-6 flex-wrap">
          <div>
            <div class="flex items-center gap-1">
              <span class="text-text-subtle text-xs">Estado activo</span>
              <BaseTooltip position="right">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-3 h-3 text-text-subtle hover:text-text-muted transition-colors" />
                </template>
                {{ tt.activeStatus }}
              </BaseTooltip>
            </div>
            <div class="flex items-center gap-2 mt-1">
              <BaseToggle
                :model-value="proposal.is_active"
                size="sm"
                aria-label="Activar propuesta"
                @update:model-value="emit('toggle-active')"
              />
              <span class="text-xs" :class="proposal.is_active ? 'text-primary' : 'text-text-subtle'">
                {{ proposal.is_active ? 'Activa' : 'Inactiva' }}
              </span>
            </div>
          </div>
          <div>
            <div class="flex items-center gap-1">
              <span class="text-text-subtle text-xs">Automatizaciones</span>
              <BaseTooltip position="right">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-3 h-3 text-text-subtle hover:text-text-muted transition-colors" />
                </template>
                {{ tt.automations }}
              </BaseTooltip>
            </div>
            <div class="flex items-center gap-2 mt-1">
              <!-- ON = automations running (knob right, like "Estado activo");
                   the stored field is the negation (automations_paused). -->
              <BaseToggle
                :model-value="!form.automations_paused"
                size="sm"
                aria-label="Activar automatizaciones"
                @update:model-value="emit('toggle-automations')"
              />
              <span class="text-xs" :class="form.automations_paused ? 'text-warning-strong' : 'text-primary'">
                {{ form.automations_paused ? '⏸ Pausadas' : 'Activas' }}
              </span>
            </div>
            <p class="text-[10px] text-text-subtle mt-1">Pausar emails automáticos (recordatorio, urgencia, inactividad).</p>
          </div>
          <div>
            <div class="flex items-center gap-1">
              <span class="text-text-subtle text-xs">Contrato y condiciones</span>
              <BaseTooltip position="right">
                <template #trigger>
                  <QuestionMarkCircleIcon class="w-3 h-3 text-text-subtle hover:text-text-muted transition-colors" />
                </template>
                Muestra al cliente la plantilla contractual global vigente, enmascarada y sin firmas. Solo está disponible en propuestas en español.
              </BaseTooltip>
            </div>
            <div class="flex items-center gap-2 mt-1">
              <BaseToggle
                :model-value="form.show_contract_terms"
                :disabled="form.language !== 'es'"
                disabled-reason="El contrato y las condiciones solo están disponibles para propuestas en español."
                size="sm"
                aria-label="Mostrar contrato y condiciones"
                data-testid="proposal-contract-terms-toggle"
                @update:model-value="emit('toggle-contract-terms')"
              />
              <span
                class="text-xs"
                :class="form.show_contract_terms && form.language === 'es' ? 'text-primary' : 'text-text-subtle'"
              >
                {{ form.language !== 'es' ? 'No disponible en inglés' : (form.show_contract_terms ? 'Visible' : 'Oculto') }}
              </span>
            </div>
            <p class="text-[10px] text-text-subtle mt-1">No modifica el prompt ni las secciones JSON de la propuesta.</p>
          </div>
          <ProposalExplainerToggle
            :proposal="proposal"
            :model-value="form.show_explainer_video"
            :language="form.language"
            :show-legal="form.show_contract_terms"
            :saving="proposalStore.isUpdating"
            @update:model-value="emit('toggle-explainer-video', $event)"
          />
        </div>
      </div>
    </div>
  </div>

  <div data-testid="general-finance-sidebar" class="bg-surface border border-border-muted rounded-xl p-4 sm:p-5 mb-4 space-y-5">
    <h3 class="text-xs font-medium text-text-muted uppercase tracking-wider">
      Inversión, pagos y hosting
    </h3>
    <div data-testid="general-finance-investment-card" class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div>
        <label class="block text-sm font-medium text-text-default mb-1">Inversión total</label>
        <BaseCurrencyInput v-model="form.total_investment" :decimals="2" data-testid="general-finance-total-investment" />
        <p
          v-if="hasCustomizedEffectiveTotal"
          data-testid="general-finance-effective-total-note"
          class="text-xs text-warning-strong mt-1.5"
        >
          Total efectivo visible al cliente:
          <strong>{{ formatInvestment(effectiveTotalInvestment, proposal.currency) }}</strong>
          (incluye módulos adicionales seleccionados).
        </p>
      </div>
      <div>
        <label class="block text-sm font-medium text-text-default mb-1">Moneda</label>
        <BaseSelect
          v-model="form.currency"
          data-testid="general-finance-currency"
          :options="[{ value: 'COP', label: 'COP' }, { value: 'USD', label: 'USD' }]"
        />
      </div>
    </div>
    <div v-if="investmentSection" class="bg-primary-soft border border-primary/30 rounded-xl px-4 py-3">
      <label class="block text-sm font-medium text-text-brand mb-2">Porcentajes de pago (sección Inversión)</label>
      <div v-if="investmentPaymentPercentages.length" class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <label
          v-for="(_, idx) in investmentPaymentPercentages"
          :key="`payment-percent-${idx}`"
          class="block"
        >
          <span class="block text-xs text-text-brand mb-1">Pago {{ idx + 1 }}</span>
          <div class="flex items-center gap-2">
            <BaseInput
              v-model.number="investmentPaymentPercentages[idx]"
              type="number"
              size="sm"
              min="0"
              max="100"
              step="0.01"
              @blur="emit('normalize-payment-percentage', idx)"
            />
            <span class="text-sm text-text-brand">%</span>
          </div>
          <span
            v-if="form.total_investment > 0 && investmentPaymentPercentages[idx] > 0"
            class="block text-xs text-text-brand mt-1 font-medium"
          >
            {{ paymentAmounts[idx] }}
          </span>
        </label>
      </div>
      <p v-else class="text-xs text-text-brand">No se detectaron porcentajes en "Secciones → Inversión → Opciones de pago".</p>
      <p class="text-xs text-text-brand mt-2">Se sincroniza con los porcentajes definidos en "Secciones → Inversión → Opciones de pago".</p>
    </div>
    <div data-testid="general-finance-hosting-card">
      <div class="flex items-center gap-1.5 mb-1">
        <label class="block text-sm font-medium text-text-default">Hosting (% de inversión total)</label>
        <BaseTooltip position="right">
          <template #trigger>
            <QuestionMarkCircleIcon class="w-3.5 h-3.5 text-text-subtle hover:text-text-muted transition-colors" />
          </template>
          {{ tt.hostingPercent }}
        </BaseTooltip>
      </div>
      <div class="flex items-center gap-3">
        <BaseInput
          v-model.number="form.hosting_percent"
          data-testid="general-finance-hosting-percent"
          type="number"
          min="0"
          max="100"
          class="w-32"
        />
        <span class="text-sm text-text-muted">%</span>
      </div>
      <div v-if="form.hosting_percent > 0 && form.total_investment > 0" class="mt-3 bg-info-soft border border-info-strong/30 rounded-xl overflow-hidden">
        <div class="px-4 py-2 text-[11px] uppercase tracking-wider text-info-strong/70 border-b border-info-strong/20">
          Precio que verá el cliente (por mes)
        </div>
        <div class="grid grid-cols-[1fr_auto_auto] gap-x-4 text-sm divide-y divide-info-strong/20">
          <div class="px-4 py-2 text-info-strong font-medium">Base mensual</div>
          <div class="px-4 py-2 text-info-strong font-semibold text-right whitespace-nowrap">
            ${{ hostingMonthlyBase.toLocaleString() }} {{ form.currency }}/mes
          </div>
          <div class="px-4 py-2 text-[11px] text-info-strong/70 text-right whitespace-nowrap">referencia</div>

          <div class="px-4 py-2 text-info-strong font-medium">
            Cada 9 meses
            <span v-if="form.hosting_discount_nine_month" class="ml-1 text-xs text-text-brand font-normal">({{ form.hosting_discount_nine_month }}% dcto)</span>
          </div>
          <div class="px-4 py-2 font-semibold text-right whitespace-nowrap"
               :class="form.hosting_discount_nine_month ? 'text-text-brand' : 'text-info-strong'">
            ${{ hostingMonthlyWithDiscount(form.hosting_discount_nine_month).toLocaleString() }} {{ form.currency }}/mes
          </div>
          <div class="px-4 py-2 text-[11px] text-info-strong/70 text-right whitespace-nowrap">
            total ${{ hostingPeriodTotal(form.hosting_discount_nine_month, 9).toLocaleString() }} {{ form.currency }} / 9 meses
          </div>

          <div class="px-4 py-2 text-info-strong font-medium">
            Semestral
            <span v-if="form.hosting_discount_semiannual" class="ml-1 text-xs text-text-brand font-normal">({{ form.hosting_discount_semiannual }}% dcto)</span>
          </div>
          <div class="px-4 py-2 font-semibold text-right whitespace-nowrap"
               :class="form.hosting_discount_semiannual ? 'text-text-brand' : 'text-info-strong'">
            ${{ hostingMonthlyWithDiscount(form.hosting_discount_semiannual).toLocaleString() }} {{ form.currency }}/mes
          </div>
          <div class="px-4 py-2 text-[11px] text-info-strong/70 text-right whitespace-nowrap">
            total ${{ hostingPeriodTotal(form.hosting_discount_semiannual, 6).toLocaleString() }} / 6 meses
          </div>

          <div class="px-4 py-2 text-info-strong font-medium">
            Trimestral
            <span v-if="form.hosting_discount_quarterly" class="ml-1 text-xs text-text-brand font-normal">({{ form.hosting_discount_quarterly }}% dcto)</span>
          </div>
          <div class="px-4 py-2 font-semibold text-right whitespace-nowrap"
               :class="form.hosting_discount_quarterly ? 'text-text-brand' : 'text-info-strong'">
            ${{ hostingMonthlyWithDiscount(form.hosting_discount_quarterly).toLocaleString() }} {{ form.currency }}/mes
          </div>
          <div class="px-4 py-2 text-[11px] text-info-strong/70 text-right whitespace-nowrap">
            total ${{ hostingPeriodTotal(form.hosting_discount_quarterly, 3).toLocaleString() }} / 3 meses
          </div>
        </div>
      </div>
      <p class="text-xs text-text-subtle mt-1">Sincronizado automáticamente con el Plan de Hosting que ve el cliente en "Tu inversión y cómo pagar".</p>
    </div>
    <div data-testid="general-finance-discounts-card" class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div>
        <label class="block text-sm font-medium text-text-default mb-1">Dcto. 9 meses (%)</label>
        <BaseInput
          v-model.number="form.hosting_discount_nine_month"
          data-testid="general-finance-nine-month-discount"
          type="number"
          min="0"
          max="100"
          class="w-32"
        />
      </div>
      <div>
        <label class="block text-sm font-medium text-text-default mb-1">Dcto. semestral (%)</label>
        <BaseInput
          v-model.number="form.hosting_discount_semiannual"
          data-testid="general-finance-semiannual-discount"
          type="number"
          min="0"
          max="100"
          class="w-32"
        />
      </div>
      <div>
        <label class="block text-sm font-medium text-text-default mb-1">Dcto. trimestral (%)</label>
        <BaseInput
          v-model.number="form.hosting_discount_quarterly"
          data-testid="general-finance-quarterly-discount"
          type="number"
          min="0"
          max="100"
          class="w-32"
        />
      </div>
    </div>
  </div>

    </template>

    <template #main>
  <!-- Editable form -->
  <form class="bg-surface rounded-xl shadow-sm border border-border-muted" @submit.prevent="emit('update')">
    <div class="p-4 sm:p-8 space-y-6">
    <div>
      <label class="block text-sm font-medium text-text-default mb-1">Título</label>
      <BaseInput v-model="form.title" type="text" required />
    </div>
    <!-- Client picker (autocomplete + snapshot fields) -->
    <div class="space-y-4 border border-border-muted rounded-xl p-4 bg-surface-raised">
      <div>
        <label class="block text-sm font-medium text-text-default mb-1">Cliente</label>
        <ClientAutocomplete
          v-model="form.client_id"
          :initial-label="form.client_name"
          test-id="proposal-edit-client-autocomplete"
          allow-create
          @select="emit('client-selected', $event)"
          @create-new="emit('create-inline-client', $event)"
        />
        <p class="text-xs text-text-subtle mt-1">
          Busca un cliente existente o escribe uno nuevo. Si no eliges email, se generará uno temporal y las automatizaciones quedarán pausadas.
        </p>
      </div>

      <!-- Placeholder warning badge -->
      <div
        v-if="proposal?.client?.is_email_placeholder"
        class="flex items-start gap-2 px-3 py-2 rounded-lg bg-warning-soft border border-warning-strong/30"
      >
        <span class="text-warning-strong text-xs font-medium">
          📧 Email pendiente — las automatizaciones de correo están pausadas para este cliente.
        </span>
      </div>

      <!-- Snapshot fields (still editable, but clearly subordinated) -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-medium text-text-muted mb-1">Nombre snapshot</label>
          <BaseInput
            id="edit-client-name"
            v-model="form.client_name"
            type="text"
            required
            size="sm"
            data-testid="edit-client-name"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-text-muted mb-1">Email del cliente</label>
          <BaseInput
            id="edit-client-email"
            v-model="form.client_email"
            type="email"
            size="sm"
            data-testid="edit-client-email"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-text-muted mb-1">Teléfono / WhatsApp</label>
          <BaseInput
            id="edit-client-phone"
            v-model="form.client_phone"
            type="tel"
            size="sm"
            placeholder="+57 300 123 4567"
            data-testid="edit-client-phone"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-text-muted mb-1">Empresa</label>
          <BaseInput
            id="edit-client-company"
            v-model="form.client_company"
            type="text"
            size="sm"
            placeholder="Acme Inc."
            data-testid="edit-client-company"
          />
        </div>
      </div>

    </div>

    <div class="space-y-3 pt-2 border-t border-input-border">
      <div class="flex items-start justify-between gap-3">
        <div>
          <h4 class="text-sm font-medium text-text-default">Configuración del correo (diseño nuevo)</h4>
          <p class="text-xs text-text-muted mt-1">
            Estos campos llenan los bloques del correo comercial: lista "Qué incluye", card "Método en 3 fases" y firma. Si los dejas vacíos se omiten o se usa el método estándar de marca.
          </p>
        </div>
        <BaseButton variant="secondary" size="sm" class="shrink-0" data-testid="edit-email-preview-btn" @click="emit('open-email-preview')">
          <BaseActionIcon action="view" /> Vista previa
        </BaseButton>
      </div>

      <div>
        <label class="block text-sm font-medium text-text-default mb-1">Firmado por</label>
        <BaseSelect v-model="form.email_signed_by" data-testid="edit-email-signed-by">
          <option value="gustavo">Gustavo Pérez · CEO</option>
          <option value="carlos">Carlos Blanco · CTO</option>
        </BaseSelect>
        <p class="text-xs text-text-subtle mt-1">Nombre y cargo que firman al pie del correo.</p>
      </div>

      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="block text-sm font-medium text-text-default">Qué incluye (bullets)</label>
          <button
            type="button"
            class="text-xs text-primary hover:underline disabled:opacity-50"
            :disabled="form.email_features.length >= MAX_EMAIL_FEATURES"
            :title="form.email_features.length >= MAX_EMAIL_FEATURES ? `Ya alcanzaste el máximo de ${MAX_EMAIL_FEATURES} ítems.` : undefined"
            data-testid="edit-add-feature"
            @click="addEmailFeature"
          >
            <BaseActionIcon action="create" />
            Agregar ítem
          </button>
        </div>
        <p class="text-xs text-text-muted mb-2">
          Hasta 8 ítems. Si queda vacío el bloque no se renderiza.
        </p>
        <div v-if="form.email_features.length === 0" class="text-xs text-text-subtle italic">
          Sin ítems — el bloque no aparecerá en el correo.
        </div>
        <div
          v-for="(_, idx) in form.email_features"
          :key="`feature-${idx}`"
          class="flex items-start gap-2 mb-2"
        >
          <span class="text-xs font-medium text-text-muted pt-2 w-6">
            {{ String(idx + 1).padStart(2, '0') }}
          </span>
          <BaseTextarea
            v-model="form.email_features[idx]"
            :rows="2"
            size="sm"
            class="flex-1"
            placeholder="Ej. Dashboard en tiempo real con filtros por ruta, conductor y estado."
          />
          <BaseButton variant="danger-ghost" size="sm" @click="removeEmailFeature(idx)">
            Quitar
          </BaseButton>
        </div>
      </div>

      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="block text-sm font-medium text-text-default">Método en 3 fases</label>
          <button
            type="button"
            class="text-xs text-primary hover:underline"
            @click="ensureMethodPhases"
          >
            Restaurar método estándar
          </button>
        </div>
        <p class="text-xs text-text-muted mb-2">
          Card oscura del correo. Si lo dejas con los valores estándar usa los textos de marca; puedes personalizarlos por propuesta.
        </p>
        <div
          v-for="(phase, idx) in form.email_method_phases"
          :key="`phase-${idx}`"
          class="grid grid-cols-1 sm:grid-cols-[60px,1fr,90px,1fr] gap-2 mb-2 items-start"
        >
          <BaseInput
            v-model="form.email_method_phases[idx].number"
            size="sm"
            placeholder="01"
            class="text-center"
          />
          <BaseInput
            v-model="form.email_method_phases[idx].title"
            size="sm"
            placeholder="Diagnóstico"
          />
          <BaseInput
            v-model="form.email_method_phases[idx].duration"
            size="sm"
            placeholder="5 días"
          />
          <BaseTextarea
            v-model="form.email_method_phases[idx].description"
            :rows="2"
            size="sm"
            placeholder="Mapeo de procesos y alcance final."
          />
        </div>
        <p class="text-xs text-text-subtle">Orden de columnas: número · título · duración · descripción.</p>
      </div>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div>
        <label class="block text-sm font-medium text-text-default mb-1">Tipo de proyecto</label>
        <BaseSelect v-model="form.project_type">
          <option value="">— Sin definir —</option>
          <option value="website">Sitio Web</option>
          <option value="ecommerce">E-commerce</option>
          <option value="webapp">Aplicación Web</option>
          <option value="landing">Landing Page</option>
          <option value="redesign">Rediseño</option>
          <option value="mobile_app">App Móvil</option>
          <option value="branding">Branding / Identidad Visual</option>
          <option value="cms">Sistema CMS</option>
          <option value="portal">Portal / Intranet</option>
          <option value="api_integration">Integración de APIs</option>
          <option value="marketplace">Marketplace</option>
          <option value="erp">Sistema ERP / Administrativo</option>
          <option value="booking">Sistema de Reservas</option>
          <option value="dashboard">Dashboard / Reportes</option>
          <option value="crm">Sistema CRM</option>
          <option value="saas">SaaS / Plataforma</option>
          <option value="chatbot">Chatbot / Asistente Virtual</option>
          <option value="ai_tool">Herramienta con IA</option>
          <option value="automation">Automatización / RPA</option>
          <option value="data_analytics">Analítica de Datos / BI</option>
          <option value="plugin_extension">Plugin / Extensión</option>
          <option value="other">Otro</option>
        </BaseSelect>
        <BaseInput
          v-if="form.project_type === 'other'"
          v-model="form.project_type_custom"
          type="text"
          placeholder="Especificar tipo de proyecto..."
          class="mt-2"
        />
      </div>
      <div>
        <label class="block text-sm font-medium text-text-default mb-1">Tipo de mercado</label>
        <BaseSelect v-model="form.market_type">
          <option value="">— Sin definir —</option>
          <option value="b2b">B2B</option>
          <option value="b2c">B2C</option>
          <option value="saas">SaaS</option>
          <option value="retail">Retail</option>
          <option value="services">Servicios profesionales</option>
          <option value="health">Salud</option>
          <option value="education">Educación</option>
          <option value="real_estate">Inmobiliaria</option>
          <option value="fintech">Fintech / Finanzas</option>
          <option value="restaurant">Restaurantes / F&amp;B</option>
          <option value="tourism">Turismo / Hospitalidad</option>
          <option value="logistics">Logística / Transporte</option>
          <option value="sports">Deportes / Fitness</option>
          <option value="legal">Servicios Legales / Jurídico</option>
          <option value="construction">Construcción / Arquitectura</option>
          <option value="media">Medios / Entretenimiento</option>
          <option value="ngo">ONG / Sector Público</option>
          <option value="agriculture">Agro / Tecnología Agrícola</option>
          <option value="tech">Tecnología / Software</option>
          <option value="consulting">Consultoría / Asesoría</option>
          <option value="automotive">Automotriz</option>
          <option value="fashion">Moda / Textil</option>
          <option value="beauty">Belleza / Cuidado Personal</option>
          <option value="manufacturing">Manufactura / Industrial</option>
          <option value="energy">Energía / Utilities</option>
          <option value="gaming">Videojuegos / Gaming</option>
          <option value="other">Otro</option>
        </BaseSelect>
        <BaseInput
          v-if="form.market_type === 'other'"
          v-model="form.market_type_custom"
          type="text"
          placeholder="Especificar tipo de mercado..."
          class="mt-2"
        />
      </div>
    </div>
    <div>
      <label class="block text-sm font-medium text-text-default mb-1">Idioma</label>
      <BaseSelect
        v-model="form.language"
        :options="[{ value: 'es', label: 'Español' }, { value: 'en', label: 'English' }]"
      />
      <p class="text-xs text-text-subtle mt-1">Solo afecta los títulos por defecto al crear. Cambiar aquí no regenera las secciones existentes.</p>
    </div>
    <div>
      <div class="flex items-center gap-1.5 mb-1">
        <label class="block text-sm font-medium text-text-default">Fecha de expiración</label>
        <BaseTooltip position="right">
          <template #trigger>
            <QuestionMarkCircleIcon class="w-3.5 h-3.5 text-text-subtle hover:text-text-muted transition-colors" />
          </template>
          {{ tt.expirationDate }}
        </BaseTooltip>
      </div>
      <div class="flex items-center gap-2">
        <BaseInput
          v-model="form.expires_at"
          type="datetime-local"
          class="flex-1"
        />
        <BaseInput
          v-model.number="expiryDaysInput"
          type="number"
          min="1"
          max="365"
          class="w-20 text-center"
        />
        <span class="text-xs text-text-subtle whitespace-nowrap">días</span>
      </div>
    </div>
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div>
        <label class="block text-sm font-medium text-text-default mb-1">Recordatorio (días después de enviar)</label>
        <BaseInput v-model.number="form.reminder_days" type="number" min="1" max="30" />
        <p class="text-xs text-text-subtle mt-1">Se enviará un email recordatorio al cliente X días después de enviar la propuesta.</p>
      </div>
      <div>
        <label class="block text-sm font-medium text-text-default mb-1">Urgencia (días después de enviar)</label>
        <BaseInput v-model.number="form.urgency_reminder_days" type="number" min="1" max="30" />
        <p class="text-xs text-text-subtle mt-1">Se enviará un email de urgencia X días después de enviar (incluye descuento si % > 0).</p>
      </div>
    </div>
    <div>
      <div class="flex items-center gap-1.5 mb-1">
        <label class="block text-sm font-medium text-text-default">Descuento (%)</label>
        <BaseTooltip position="right">
          <template #trigger>
            <QuestionMarkCircleIcon class="w-3.5 h-3.5 text-text-subtle hover:text-text-muted transition-colors" />
          </template>
          {{ tt.discount }}
        </BaseTooltip>
      </div>
      <BaseInput
        v-model.number="form.discount_percent"
        data-testid="general-finance-general-discount"
        type="number"
        min="0"
        max="100"
      />
      <p class="text-xs text-text-subtle mt-1">0 = sin descuento en email de urgencia.</p>
    </div>

    </div>

    <!-- Sticky action bar -->
    <div class="sticky bottom-0 rounded-b-xl bg-surface/95 backdrop-blur-sm border-t border-border-muted px-4 sm:px-5 py-3 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)] z-20">
      <div class="flex flex-col-reverse sm:flex-row sm:flex-wrap sm:items-center gap-2 sm:gap-3">
        <div class="flex items-center gap-2 sm:gap-3 w-full sm:w-auto">
          <BaseButton
            type="submit"
            variant="primary"
            size="md"
            :loading="proposalStore.isUpdating"
            :disabled="proposalStore.isUpdating"
            data-testid="proposal-edit-submit"
            class="flex-1 sm:flex-none"
          >
            {{ proposalStore.isUpdating ? 'Guardando...' : 'Guardar Cambios' }}
          </BaseButton>

          <BaseButton
            variant="secondary"
            size="md"
            data-testid="proposal-actions-menu"
            aria-label="Acciones de la propuesta"
            title="Más acciones"
            class="!w-10 !h-10 !p-0 flex-shrink-0"
            @click="emit('open-actions')"
          >
          <BaseActionIcon action="more" />
          </BaseButton>
        </div>

        <BaseButton
          v-if="nextAction"
          type="button"
          variant="primary"
          size="md"
          :disabled="nextAction.disabled"
          :title="nextAction.disabled ? 'El lanzamiento a la plataforma ya está en curso. Espera a que termine.' : undefined"
          :data-testid="'proposal-next-action-' + nextAction.key"
          class="w-full sm:w-auto sm:ml-auto shadow-sm"
          @click="emit('next-action')"
        >
          {{ nextAction.label }}
        </BaseButton>
      </div>
    </div>
  </form>
    </template>
  </TabSplitLayout>
  </div>
</template>

<script setup>
import PanelDownloadLink from '~/components/panel/PanelDownloadLink.vue';
import { computed, ref, watch } from 'vue';
import {
  QuestionMarkCircleIcon,
} from '@heroicons/vue/24/outline';
import ProposalExplainerToggle from '~/components/panel/proposal/ProposalExplainerToggle.vue';
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue';
import TabSplitLayout from '~/components/panel/TabSplitLayout.vue';
import { DEFAULT_METHOD_PHASES } from '~/stores/proposals_constants';
import { useProposalStore } from '~/stores/proposals';
import { useClipboardFeedback } from '~/composables/useClipboardFeedback';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useTooltipTexts } from '~/composables/useTooltipTexts';
import { toSlug } from '~/utils/slugify';

const props = defineProps({
  proposal: { type: Object, required: true },
  /** Page-owned reactive form — fields bind via v-model on this shared object. */
  form: { type: Object, required: true },
  /** getProposalNextAction result decorated by the page (launch pending state). */
  nextAction: { type: Object, default: null },
  hasDocumentsTab: { type: Boolean, default: false },
  /** Live effective total (page computed — the header shows it too). */
  effectiveTotalInvestment: { type: [Number, String], default: 0 },
  hasCustomizedEffectiveTotal: { type: Boolean, default: false },
  /** Page-owned editable percentages array (synced into the investment section on save). */
  investmentPaymentPercentages: { type: Array, default: () => [] },
  paymentAmounts: { type: Array, default: () => [] },
});

const emit = defineEmits([
  'update',
  'toggle-automations',
  'open-email-preview',
  'toggle-active',
  'toggle-contract-terms',
  'toggle-explainer-video',
  'next-action',
  'open-actions',
  'client-selected',
  'create-inline-client',
  'normalize-payment-percentage',
]);

const proposalStore = useProposalStore();
const notify = usePanelNotify();
const clipboardFeedback = useClipboardFeedback();
const { proposalEdit: tt } = useTooltipTexts();

// Aliases so the code moved verbatim from the edit page keeps reading
// `proposal.value` / `form.x` / `effectiveTotalInvestment.value`.
const proposal = computed(() => props.proposal);
const form = props.form;
const effectiveTotalInvestment = computed(() => props.effectiveTotalInvestment);

const investmentSection = computed(() =>
  (props.proposal?.sections || []).find(s => s.section_type === 'investment') || null
);

function formatInvestment(value, currency = 'COP') {
  if (!value) return '';
  const num = Number(value);
  return '$' + num.toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + ' ' + currency;
}

const proposalModeLinks = computed(() => {
  const links = [
    { label: 'Propuesta completa', labelUrl: 'URL propuesta completa', mode: 'detailed' },
    { label: 'Detalle técnico', labelUrl: 'URL detalle técnico', mode: 'technical' },
  ];
  if (proposal.value?.language === 'es' && proposal.value?.show_contract_terms) {
    links.push({
      label: 'Contrato y condiciones',
      labelUrl: 'URL contrato y condiciones',
      mode: 'legal',
    });
  }
  return links;
});

const publicIdentifier = computed(
  () => proposal.value?.slug || proposal.value?.uuid || ''
);

async function copyUrl() {
  const url = `${window.location.origin}/proposal/${publicIdentifier.value}`;
  await clipboardFeedback.copyText({
    key: 'public',
    text: url,
    successLabel: 'Copiado: URL pública',
    errorLabel: 'No se pudo copiar la URL',
    onError: notifyCopyError,
  });
}

async function copyModeUrl(mode) {
  const url = `${window.location.origin}/proposal/${publicIdentifier.value}?mode=${mode}`;
  const link = proposalModeLinks.value.find((candidate) => candidate.mode === mode);
  await clipboardFeedback.copyText({
    key: mode,
    text: url,
    successLabel: `Copiado: ${link?.labelUrl || 'URL de la propuesta'}`,
    errorLabel: 'No se pudo copiar la URL',
    onError: notifyCopyError,
  });
}

function copyFeedback(key) {
  return clipboardFeedback.feedbackFor(key);
}

function notifyCopyError() {
  notify.error({
    title: 'No se pudo copiar la URL',
    detail: 'Tu navegador bloqueó el acceso al portapapeles.',
  });
}

// Editable slug UI state
const slugDraft = ref('');
const slugError = ref('');
const slugSaving = ref(false);
const slugSaved = ref(false);
const slugRegex = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

watch(
  () => proposal.value?.slug,
  (value) => { slugDraft.value = value || ''; },
  { immediate: true },
);

function regenerateSlugFromName() {
  slugDraft.value = toSlug(proposal.value?.client_name);
  slugError.value = '';
}

async function saveSlug() {
  const value = (slugDraft.value || '').trim();
  slugError.value = '';
  slugSaved.value = false;
  if (value === (proposal.value?.slug || '')) return;
  if (value && !slugRegex.test(value)) {
    slugError.value = 'Solo minúsculas, números y guiones (sin espacios ni acentos).';
    return;
  }
  if (value.length > 120) {
    slugError.value = 'La URL personalizada no puede superar 120 caracteres.';
    return;
  }
  slugSaving.value = true;
  try {
    const result = await proposalStore.updateProposal(proposal.value.id, { slug: value });
    if (result?.success) {
      slugDraft.value = proposal.value?.slug || value;
      slugSaved.value = true;
      setTimeout(() => { slugSaved.value = false; }, 2000);
    } else {
      slugError.value = result?.errors?.slug?.[0]
        || result?.error
        || 'No se pudo guardar la URL personalizada.';
    }
  } finally {
    slugSaving.value = false;
  }
}

const MAX_EMAIL_FEATURES = 8;
function addEmailFeature() {
  if (form.email_features.length >= MAX_EMAIL_FEATURES) return;
  form.email_features = [...form.email_features, ''];
}
function removeEmailFeature(idx) {
  form.email_features = form.email_features.filter((_, i) => i !== idx);
}
function ensureMethodPhases() {
  if (!form.email_method_phases || form.email_method_phases.length === 0) {
    form.email_method_phases = DEFAULT_METHOD_PHASES.map((p) => ({ ...p }));
  }
}

const DEFAULT_EXPIRY_DAYS = 21;
const padDate = (n) => String(n).padStart(2, '0');
function getExpiryDaysFromStr(datetimeStr) {
  if (!datetimeStr) return DEFAULT_EXPIRY_DAYS;
  const diff = new Date(datetimeStr) - Date.now();
  return Math.max(1, Math.round(diff / (24 * 60 * 60 * 1000)));
}
const expiryDaysInput = ref(getExpiryDaysFromStr(form.expires_at));
watch(() => form.expires_at, (val) => {
  expiryDaysInput.value = getExpiryDaysFromStr(val);
});
watch(expiryDaysInput, (days) => {
  const safeDays = Number.isInteger(days) && days > 0 ? days : DEFAULT_EXPIRY_DAYS;
  const expiry = new Date(Date.now() + safeDays * 24 * 60 * 60 * 1000);
  const dateStr = `${expiry.getFullYear()}-${padDate(expiry.getMonth() + 1)}-${padDate(expiry.getDate())}`;
  const timeStr = form.expires_at ? form.expires_at.slice(11, 16) : `${padDate(expiry.getHours())}:${padDate(expiry.getMinutes())}`;
  form.expires_at = `${dateStr}T${timeStr}`;
});

// Must match Investment.vue's hostingTwelveMonthReference / computedBillingTiers so admin preview
// shows the exact same numbers the client will see (avoids rounding drift).
// Client-facing basis is the effective total (base + admin-default additional
// modules), same input the client's "Inversión Total" line uses.
const hostingTwelveMonthReference = computed(() => {
  const effective = Number(effectiveTotalInvestment.value);
  const basis = effective > 0 ? effective : Number(form.total_investment) || 0;
  const percent = Number(form.hosting_percent) || 0;
  return Math.round(basis * percent / 100);
});
const hostingMonthlyBase = computed(() =>
  Math.round(hostingTwelveMonthReference.value / 12)
);
function hostingMonthlyWithDiscount(discountPercent) {
  return Math.round(hostingMonthlyBase.value * (100 - (discountPercent || 0)) / 100);
}
function hostingPeriodTotal(discountPercent, months) {
  return hostingMonthlyWithDiscount(discountPercent) * months;
}
</script>
