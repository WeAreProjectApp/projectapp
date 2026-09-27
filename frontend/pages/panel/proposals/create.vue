<template>
  <div>
    <div class="mb-8">
      <BaseButton as="NuxtLink" :to="localePath('/panel/proposals')" variant="link" size="sm">
        <BaseActionIcon action="back" />
        Volver a propuestas
      </BaseButton>
      <h1 class="text-2xl font-light text-text-default mt-2">Nueva Propuesta</h1>
    </div>

    <!-- Tab toggle -->
    <div class="flex gap-1 mb-6 bg-surface-raised rounded-xl p-1 w-full max-w-md">
      <!-- design-tokens: allow-raw-button (mode tabs, not actions) -->
      <button
        type="button"
        :class="[
          'flex-1 min-w-0 px-2 sm:px-4 py-2 text-xs sm:text-sm rounded-lg transition-all whitespace-nowrap truncate',
          mode === 'json' ? 'bg-surface shadow-sm font-medium text-text-default' : 'text-text-muted hover:text-text-default'
        ]"
        @click="mode = 'json'"
      >
        <span class="sm:hidden">JSON</span>
        <span class="hidden sm:inline">Importar JSON</span>
      </button>
      <!-- design-tokens: allow-raw-button (mode tabs, not actions) -->
      <button
        type="button"
        :class="[
          'flex-1 min-w-0 px-2 sm:px-4 py-2 text-xs sm:text-sm rounded-lg transition-all whitespace-nowrap truncate',
          mode === 'prompt' ? 'bg-surface shadow-sm font-medium text-text-default' : 'text-text-muted hover:text-text-default'
        ]"
        @click="mode = 'prompt'"
      >
        <span class="sm:hidden">Prompt</span>
        <span class="hidden sm:inline">Prompt IA</span>
      </button>
      <!-- design-tokens: allow-raw-button (mode tabs, not actions) -->
      <button
        type="button"
        :class="[
          'flex-1 min-w-0 px-2 sm:px-4 py-2 text-xs sm:text-sm rounded-lg transition-all whitespace-nowrap truncate',
          mode === 'manual' ? 'bg-surface shadow-sm font-medium text-text-default' : 'text-text-muted hover:text-text-default'
        ]"
        @click="mode = 'manual'"
      >
        Manual
      </button>
    </div>

    <!-- ============================================================ -->
    <!-- MANUAL MODE (existing form, unchanged) -->
    <!-- ============================================================ -->
    <form v-if="mode === 'manual'" class="bg-surface rounded-xl shadow-sm border border-border-muted p-4 sm:p-8 max-w-2xl" @submit.prevent="handleSubmit">
      <div class="space-y-6">
        <!-- Title -->
        <div>
          <label for="create-title" class="block text-sm font-medium text-text-default mb-1">Título</label>
          <input
            id="create-title"
            v-model="form.title"
            type="text"
            required
            placeholder="Propuesta Desarrollo Web — Cliente"
            class="w-full px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
          />
        </div>

        <!-- Client picker (autocomplete + snapshot fields) -->
        <div class="space-y-4 border border-border-muted rounded-xl p-4 bg-surface-raised">
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Cliente</label>
            <ClientAutocomplete
              v-model="form.client_id"
              :initial-label="form.client_name"
              allow-create
              @select="onClientSelected"
              @create-new="onCreateInlineClient"
            />
            <p class="text-xs text-text-subtle mt-1">
              Busca un cliente existente o escribe uno nuevo. Si no tiene email, generaremos uno temporal y pausaremos automatizaciones hasta que lo agregues.
            </p>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label for="create-client-name" class="block text-xs font-medium text-text-muted mb-1">Nombre</label>
              <input
                id="create-client-name"
                v-model="form.client_name"
                type="text"
                required
                placeholder="María García"
                class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              />
            </div>
            <div>
              <label for="create-client-email" class="block text-xs font-medium text-text-muted mb-1">Email</label>
              <input
                id="create-client-email"
                v-model="form.client_email"
                type="email"
                placeholder="maria@gmail.com"
                class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-text-muted mb-1">Teléfono / WhatsApp</label>
              <input
                v-model="form.client_phone"
                type="tel"
                placeholder="+57 300 123 4567"
                class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-text-muted mb-1">Empresa</label>
              <input
                v-model="form.client_company"
                type="text"
                placeholder="Acme Inc."
                class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              />
            </div>
          </div>
        </div>

        <!-- Project type + Market type -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Tipo de proyecto</label>
            <select v-model="form.project_type" class="w-full px-4 py-2.5 border border-border-default rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none bg-surface text-text-default">
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
            </select>
            <input
              v-if="form.project_type === 'other'"
              v-model="form.project_type_custom"
              type="text"
              placeholder="Especificar tipo de proyecto..."
              class="mt-2 w-full px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Tipo de mercado</label>
            <select v-model="form.market_type" class="w-full px-4 py-2.5 border border-border-default rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none bg-surface text-text-default">
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
            </select>
            <input
              v-if="form.market_type === 'other'"
              v-model="form.market_type_custom"
              type="text"
              placeholder="Especificar tipo de mercado..."
              class="mt-2 w-full px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
            />
          </div>
        </div>

        <!-- Language -->
        <div>
          <label class="block text-sm font-medium text-text-default mb-1">Idioma de la propuesta</label>
          <select
            v-model="form.language"
            class="w-full px-4 py-2.5 border border-border-default rounded-xl text-sm
                   focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none bg-surface text-text-default"
          >
            <option value="es">Español</option>
            <option value="en">English</option>
          </select>
          <p class="text-xs text-text-subtle mt-1">Define los títulos e índices por defecto de las secciones.</p>
        </div>

        <div class="rounded-xl border border-border-default bg-surface-raised p-4">
          <div class="flex items-start justify-between gap-4">
            <div>
              <p class="text-sm font-medium text-text-default">Contrato y condiciones</p>
              <p class="mt-1 text-xs leading-relaxed text-text-subtle">
                Muestra la plantilla contractual global vigente como borrador enmascarado. No cambia el prompt ni el JSON de secciones.
              </p>
            </div>
            <BaseToggle
              v-model="form.show_contract_terms"
              :disabled="form.language !== 'es'"
              disabled-reason="El contrato y las condiciones solo están disponibles para propuestas en español."
              aria-label="Mostrar contrato y condiciones"
              data-testid="create-contract-terms-toggle"
            />
          </div>
          <p class="mt-2 text-xs" :class="form.language === 'es' ? 'text-text-muted' : 'text-warning-strong'">
            {{ form.language === 'es'
              ? (form.show_contract_terms ? 'Visible para el cliente.' : 'Oculto para el cliente.')
              : 'Este módulo solo está disponible en propuestas en español.' }}
          </p>
        </div>

        <!-- Nationality -->
        <div>
          <label class="block text-sm font-medium text-text-default mb-1">Nacionalidad del cliente</label>
          <select
            v-model="form.nationality"
            class="w-full px-4 py-2.5 border border-border-default rounded-xl text-sm
                   focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none bg-surface text-text-default"
          >
            <option value="COL">Colombia</option>
            <option value="EXT">Extranjeros</option>
            <option value="USA">Estados Unidos</option>
          </select>
          <p class="text-xs text-text-subtle mt-1">Define qué paquetes de horas se siembran en Condiciones comerciales y sugiere la moneda.</p>
        </div>

        <!-- Investment + Currency -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Inversión total</label>
            <BaseCurrencyInput
              v-model="form.total_investment"
              :decimals="2"
              placeholder="3.500.000"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Moneda</label>
            <select
              v-model="form.currency"
              class="w-full px-4 py-2.5 border border-border-default rounded-xl text-sm
                     focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none bg-surface text-text-default"
            >
              <option value="COP">COP</option>
              <option value="USD">USD</option>
            </select>
          </div>
        </div>

        <!-- Hosting percent -->
        <div>
          <label class="block text-sm font-medium text-text-default mb-1">Hosting (% de inversión total)</label>
          <div class="flex items-center gap-3">
            <input
              v-model.number="form.hosting_percent"
              type="number"
              min="0"
              max="100"
              class="w-32 px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
            />
            <span class="text-sm text-text-muted">%</span>
          </div>
          <div v-if="form.hosting_percent > 0 && form.total_investment > 0" class="mt-3 bg-info-soft border border-info-strong/30 rounded-xl overflow-hidden">
            <div class="grid grid-cols-[1fr_auto] gap-x-4 text-sm divide-y divide-info-strong/20">
              <div class="px-4 py-2 text-info-strong font-medium">Base mensual <span class="text-xs font-normal text-text-subtle">(referencia)</span></div>
              <div class="px-4 py-2 text-info-strong font-semibold text-right">
                ${{ Math.round(form.total_investment * form.hosting_percent / 100 / 12).toLocaleString() }} {{ form.currency }}
              </div>
              <div class="px-4 py-2 text-info-strong font-medium">Trimestral</div>
              <div class="px-4 py-2 text-info-strong font-semibold text-right">
                ${{ Math.round(form.total_investment * form.hosting_percent / 100 / 12 * 3).toLocaleString() }} {{ form.currency }}
              </div>
              <template v-if="form.hosting_discount_quarterly">
                <div class="px-4 py-2 text-info-strong font-medium">
                  Trimestral
                  <span class="ml-1 text-xs text-text-brand font-normal">({{ form.hosting_discount_quarterly }}% dcto)</span>
                </div>
                <div class="px-4 py-2 text-text-brand font-semibold text-right">
                  ${{ Math.round(Math.round(form.total_investment * form.hosting_percent / 100 / 12) * (100 - form.hosting_discount_quarterly) / 100 * 3).toLocaleString() }} {{ form.currency }}
                </div>
              </template>
              <div class="px-4 py-2 text-info-strong font-medium">Semestral</div>
              <div class="px-4 py-2 text-info-strong font-semibold text-right">
                ${{ Math.round(form.total_investment * form.hosting_percent / 100 / 12 * 6).toLocaleString() }} {{ form.currency }}
              </div>
              <template v-if="form.hosting_discount_semiannual">
                <div class="px-4 py-2 text-info-strong font-medium">
                  Semestral
                  <span class="ml-1 text-xs text-text-brand font-normal">({{ form.hosting_discount_semiannual }}% dcto)</span>
                </div>
                <div class="px-4 py-2 text-text-brand font-semibold text-right">
                  ${{ Math.round(Math.round(form.total_investment * form.hosting_percent / 100 / 12) * (100 - form.hosting_discount_semiannual) / 100 * 6).toLocaleString() }} {{ form.currency }}
                </div>
              </template>
              <div class="px-4 py-2 text-info-strong font-medium">☁️ Cada 9 meses</div>
              <div class="px-4 py-2 text-info-strong font-semibold text-right">
                ${{ Math.round(form.total_investment * form.hosting_percent / 100 / 12 * 9).toLocaleString() }} {{ form.currency }}
              </div>
              <template v-if="form.hosting_discount_nine_month">
                <div class="px-4 py-2 text-info-strong font-medium">
                  Cada 9 meses
                  <span class="ml-1 text-xs text-text-brand font-normal">({{ form.hosting_discount_nine_month }}% dcto)</span>
                </div>
                <div class="px-4 py-2 text-text-brand font-semibold text-right">
                  ${{ Math.round(Math.round(form.total_investment * form.hosting_percent / 100 / 12) * (100 - form.hosting_discount_nine_month) / 100 * 9).toLocaleString() }} {{ form.currency }}
                </div>
              </template>
            </div>
          </div>
          <p class="text-xs text-text-subtle mt-1">Se sincroniza con el % del Plan de Hosting en la sección "Tu inversión y cómo pagar".</p>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Dcto. 9 meses (%)</label>
            <input v-model.number="form.hosting_discount_nine_month" type="number" min="0" max="100"
              class="w-32 px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none" />
          </div>
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Dcto. semestral (%)</label>
            <input v-model.number="form.hosting_discount_semiannual" type="number" min="0" max="100"
              class="w-32 px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none" />
          </div>
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Dcto. trimestral (%)</label>
            <input v-model.number="form.hosting_discount_quarterly" type="number" min="0" max="100"
              class="w-32 px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none" />
          </div>
        </div>

        <!-- Expires at -->
        <div>
          <label class="block text-sm font-medium text-text-default mb-1">Fecha de expiración</label>
          <div class="flex items-center gap-2">
            <input
              v-model="form.expires_at"
              type="datetime-local"
              class="flex-1 px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
            />
            <input
              v-model.number="expiryDaysInput"
              type="number"
              min="1"
              max="365"
              class="w-20 px-3 py-2.5 border border-input-border bg-input-bg text-input-text rounded-xl text-sm text-center focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
            />
            <span class="text-xs text-text-subtle whitespace-nowrap">días</span>
          </div>
        </div>

        <!-- Reminder days -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Recordatorio (días después de enviar)</label>
            <input
              v-model.number="form.reminder_days"
              type="number"
              min="1"
              max="30"
              class="w-full px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
            />
            <p class="text-xs text-text-subtle mt-1">Se enviará un email recordatorio al cliente X días después de enviar la propuesta.</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Urgencia (días después de enviar)</label>
            <input
              v-model.number="form.urgency_reminder_days"
              type="number"
              min="1"
              max="30"
              class="w-full px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
            />
            <p class="text-xs text-text-subtle mt-1">Se enviará un email de urgencia X días después de enviar (incluye descuento si % > 0).</p>
          </div>
        </div>

        <!-- Discount -->
        <div>
          <label class="block text-sm font-medium text-text-default mb-1">Descuento (%)</label>
          <input
            v-model.number="form.discount_percent"
            type="number"
            min="0"
            max="100"
            class="w-full px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
          />
          <p class="text-xs text-text-subtle mt-1">Si es mayor a 0, se enviará un email de urgencia con descuento 2 días antes de expirar. 0 = sin descuento.</p>
        </div>

        <div class="space-y-2 border-t border-input-border pt-4">
          <label for="create-email-intro" class="block text-sm font-medium text-text-default">
            Mensaje personalizado del correo de envío
          </label>
          <p class="text-xs leading-relaxed text-text-muted">
            Explica el problema concreto del cliente, cómo lo resuelve esta propuesta y el resultado de negocio esperado. Puedes guardar el borrador vacío, pero necesitarás este mensaje para enviarlo.
          </p>
          <textarea
            id="create-email-intro"
            v-model="form.email_intro"
            rows="6"
            class="w-full resize-y rounded-xl border border-input-border bg-input-bg px-4 py-2.5 text-sm text-input-text placeholder-input-placeholder outline-none focus:border-focus-ring focus:ring-2 focus:ring-focus-ring/30"
            placeholder="Ej. Esta propuesta resuelve… mediante… para lograr…"
            data-testid="create-email-intro"
          ></textarea>
          <p class="text-xs text-text-subtle">Texto plano con saltos de línea; no HTML ni Markdown.</p>
        </div>

        <!-- Email design metadata -->
        <div class="space-y-3 pt-4 border-t border-input-border">
          <div>
            <h3 class="text-sm font-medium text-text-default">Configuración del correo</h3>
            <p class="text-xs text-text-muted mt-1">
              Datos que llenan los bloques del correo comercial: lista "Qué incluye", card "Método en 3 fases" y firma. Si los dejas vacíos se omiten o se usa el método estándar de marca.
            </p>
          </div>

          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Firmado por</label>
            <select
              v-model="form.email_signed_by"
              class="w-full px-4 py-2.5 border border-input-border bg-input-bg text-input-text rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              data-testid="create-email-signed-by"
            >
              <option value="gustavo">Gustavo Pérez · CEO</option>
              <option value="carlos">Carlos Blanco · CTO</option>
            </select>
            <p class="text-xs text-text-subtle mt-1">Nombre y cargo que firman al pie del correo.</p>
          </div>

          <div>
            <div class="flex items-center justify-between mb-2">
              <label class="block text-sm font-medium text-text-default">
                Qué incluye (bullets)
                <span class="text-xs text-text-subtle font-normal ml-1">{{ form.email_features.length }}/{{ MAX_EMAIL_FEATURES }}</span>
              </label>
              <button
                type="button"
                class="text-xs text-primary hover:underline disabled:opacity-50"
                :disabled="form.email_features.length >= MAX_EMAIL_FEATURES"
                :title="form.email_features.length >= MAX_EMAIL_FEATURES ? `Ya alcanzaste el máximo de ${MAX_EMAIL_FEATURES} ítems.` : undefined"
                data-testid="create-add-feature"
                @click="addEmailFeature"
              >
                <BaseActionIcon action="create" />
                Agregar ítem
              </button>
            </div>
            <p class="text-xs text-text-muted mb-2">
              Hasta {{ MAX_EMAIL_FEATURES }} ítems. Si queda vacío el bloque no se renderiza.
            </p>
            <div v-if="form.email_features.length === 0" class="text-xs text-text-subtle italic">
              Sin ítems — el bloque no aparecerá en el correo.
            </div>
            <div
              v-for="(_, idx) in form.email_features"
              :key="`create-feature-${idx}`"
              class="flex min-w-0 items-start gap-2 mb-2"
            >
              <span class="text-xs font-medium text-text-muted pt-2 w-6">
                {{ String(idx + 1).padStart(2, '0') }}
              </span>
              <textarea
                v-model="form.email_features[idx]"
                rows="2"
                class="min-w-0 flex-1 px-3 py-2 border border-input-border bg-input-bg text-input-text rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none resize-y"
                placeholder="Ej. Dashboard en tiempo real con filtros por ruta, conductor y estado."
              ></textarea>
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
                @click="resetEmailMethodPhases"
              >
                Restaurar método estándar
              </button>
            </div>
            <p class="text-xs text-text-muted mb-2">
              Card oscura del correo. Siempre 3 fases (es el layout del diseño).
            </p>
            <div
              v-for="(phase, idx) in form.email_method_phases"
              :key="`create-phase-${idx}`"
              class="grid min-w-0 grid-cols-1 gap-2 mb-2 items-start sm:grid-cols-[60px_minmax(0,1fr)_90px_minmax(0,1.5fr)]"
            >
              <input
                v-model="form.email_method_phases[idx].number"
                class="min-w-0 px-3 py-2 border border-input-border bg-input-bg text-input-text rounded-xl text-sm text-center focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
                placeholder="01"
                maxlength="3"
              />
              <input
                v-model="form.email_method_phases[idx].title"
                class="min-w-0 px-3 py-2 border border-input-border bg-input-bg text-input-text rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
                placeholder="Diagnóstico"
                maxlength="40"
              />
              <input
                v-model="form.email_method_phases[idx].duration"
                class="min-w-0 px-3 py-2 border border-input-border bg-input-bg text-input-text rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
                placeholder="5 días"
                maxlength="20"
              />
              <textarea
                v-model="form.email_method_phases[idx].description"
                rows="2"
                class="min-w-0 px-3 py-2 border border-input-border bg-input-bg text-input-text rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none resize-y"
                placeholder="Mapeo de procesos y alcance final."
                maxlength="120"
              ></textarea>
            </div>
            <p class="text-xs text-text-subtle">Columnas: número · título · duración · descripción.</p>
          </div>
        </div>

        <!-- Errors -->
        <div v-if="errorMsg" class="text-sm text-danger-strong bg-danger-soft px-4 py-3 rounded-xl">
          {{ errorMsg }}
        </div>

        <!-- Submit -->
        <div class="flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-3 sm:gap-4 pt-2">
          <BaseButton variant="primary" size="md" type="submit" class="w-full sm:w-auto sm:px-6" :disabled="proposalStore.isUpdating">
            {{ proposalStore.isUpdating ? 'Creando...' : 'Crear Propuesta' }}
          </BaseButton>
          <BaseButton variant="ghost" size="md" class="w-full sm:w-auto sm:px-6" v-if="canSendDirectly" :disabled="proposalStore.isUpdating" @click="handleCreateAndSend">
            {{ proposalStore.isUpdating ? 'Creando...' : 'Crear y Enviar' }}
          </BaseButton>
          <NuxtLink :to="localePath('/panel/proposals')" class="text-sm text-text-muted hover:text-text-default text-center sm:text-left">
            Cancelar
          </NuxtLink>
        </div>
        <p v-if="canSendDirectly" class="text-xs text-text-subtle mt-2">Envía directamente si los datos del cliente están completos.</p>
      </div>
    </form>

    <!-- ============================================================ -->
    <!-- JSON IMPORT MODE -->
    <!-- ============================================================ -->
    <div v-else-if="mode === 'json'" class="max-w-3xl space-y-6">

      <!-- Download template row -->
      <div class="bg-surface rounded-xl shadow-sm border border-border-muted p-4 sm:p-6">
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h3 class="text-sm font-medium text-text-default">Plantilla JSON</h3>
            <p class="text-xs text-text-subtle mt-0.5">Incluye secciones comerciales y la clave <code class="text-[10px]">technicalDocument</code> (detalle técnico).</p>
          </div>
          <div class="flex items-center gap-3">
            <select
              v-model="jsonForm.language"
              class="px-3 py-2 border border-border-default rounded-lg text-sm bg-surface text-text-default
                     focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
            >
              <option value="es">Español</option>
              <option value="en">English</option>
            </select>
            <BaseButton variant="secondary" size="md" @click="copyTemplate">
            <BaseActionIcon action="copy" />
              {{ templateCopied ? '¡Copiado!' : 'Copiar' }}
            </BaseButton>
            <BaseButton variant="secondary" size="md" :disabled="isDownloading" @click="downloadTemplate">
            <BaseActionIcon action="download" />
              {{ isDownloading ? 'Descargando...' : 'Descargar' }}
            </BaseButton>
          </div>
        </div>
      </div>

      <div class="rounded-xl border border-border-default bg-surface p-4 sm:p-6">
        <div class="flex items-start justify-between gap-4">
          <div>
            <h3 class="text-sm font-medium text-text-default">Contrato y condiciones</h3>
            <p class="mt-1 text-xs leading-relaxed text-text-subtle">
              Es una opción de la propuesta, independiente del contenido importado. No agrega ninguna clave al JSON de secciones.
            </p>
          </div>
          <BaseToggle
            v-model="jsonForm.show_contract_terms"
            :disabled="jsonForm.language !== 'es'"
            disabled-reason="El contrato y las condiciones solo están disponibles para propuestas en español."
            aria-label="Mostrar contrato y condiciones"
            data-testid="json-contract-terms-toggle"
          />
        </div>
        <p class="mt-2 text-xs" :class="jsonForm.language === 'es' ? 'text-text-muted' : 'text-warning-strong'">
          {{ jsonForm.language === 'es'
            ? (jsonForm.show_contract_terms ? 'Visible para el cliente.' : 'Oculto para el cliente.')
            : 'Este módulo solo está disponible en propuestas en español.' }}
        </p>
      </div>

      <!-- JSON input -->
      <div class="bg-surface rounded-xl shadow-sm border border-border-muted p-4 sm:p-6">
        <h3 class="text-sm font-medium text-text-default mb-3">Pegar o subir JSON</h3>

        <div class="flex items-center gap-3 mb-3">
          <label
            class="inline-flex items-center gap-2 px-4 py-2 border border-border-default rounded-lg text-sm
                   text-text-default hover:bg-surface-raised cursor-pointer transition-colors"
          >
              <BaseActionIcon action="upload" />
            Subir archivo .json
            <input type="file" accept=".json" class="hidden" @change="handleFileUpload" />
          </label>
          <span v-if="uploadedFileName" class="text-xs text-text-muted">{{ uploadedFileName }}</span>
        </div>

        <textarea
          v-model="jsonRaw"
          rows="14"
          placeholder='{ "general": { "clientName": "..." }, "executiveSummary": { ... }, ... }'
          class="w-full px-4 py-3 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-xs font-mono leading-relaxed focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none resize-y"
          @input="parseJson"
        ></textarea>

        <!-- Parse error -->
        <div v-if="jsonError" class="mt-2 text-sm text-danger-strong bg-danger-soft px-4 py-2 rounded-lg">
          {{ jsonError }}
        </div>

        <!-- Preview -->
        <div v-if="jsonParsed && !jsonError" class="mt-3 bg-primary-soft border border-primary/30 rounded-lg px-4 py-3">
          <div class="flex flex-wrap gap-x-6 gap-y-1 text-sm">
            <span><span class="text-text-muted">Cliente:</span> <span class="font-medium text-text-default">{{ jsonPreview.clientName }}</span></span>
            <span><span class="text-text-muted">Secciones:</span> <span class="font-medium text-text-default">{{ jsonPreview.sectionCount }}</span></span>
            <span v-if="jsonPreview.epicCount != null"><span class="text-text-muted">Módulos (det. técnico):</span> <span class="font-medium text-text-default">{{ jsonPreview.epicCount }}</span></span>
            <span v-if="jsonPreview.investment"><span class="text-text-muted">Inversión:</span> <span class="font-medium text-text-default">{{ jsonPreview.investment }}</span></span>
          </div>
        </div>

        <LegacyFormatWarning
          v-if="jsonParsed && !jsonError"
          :issues="legacyFormatIssues"
          :field-labels="LEGACY_FIELD_LABELS"
          @download="downloadMigratedProposalJson(jsonParsed)"
        />
      </div>

      <!-- Metadata form -->
      <form v-if="jsonParsed && !jsonError && !legacyFormatIssues.length" class="bg-surface rounded-xl shadow-sm border border-border-muted p-4 sm:p-6" @submit.prevent="handleJsonSubmit">
        <h3 class="text-sm font-medium text-text-default mb-4">Datos de la propuesta</h3>
        <div class="space-y-4">
          <!-- Title -->
          <div>
            <label class="block text-xs font-medium text-text-muted mb-1">Título</label>
            <input
              v-model="jsonForm.title"
              type="text"
              required
              class="w-full px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
            />
          </div>

          <!-- Client picker (autocomplete + snapshot fields) -->
          <div class="space-y-4 border border-border-muted rounded-xl p-4 bg-surface-raised">
            <div>
              <label class="block text-sm font-medium text-text-default mb-1">Cliente</label>
              <ClientAutocomplete
                v-model="jsonForm.client_id"
                :initial-label="jsonForm.client_name"
                test-id="json-client-autocomplete"
                allow-create
                @select="onJsonClientSelected"
                @create-new="onCreateInlineJsonClient"
              />
              <p class="text-xs text-text-subtle mt-1">
                Busca un cliente existente o escribe uno nuevo. Si no tiene email, generaremos uno temporal y pausaremos automatizaciones hasta que lo agregues.
              </p>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label for="json-client-name" class="block text-xs font-medium text-text-muted mb-1">Nombre</label>
                <input
                  id="json-client-name"
                  v-model="jsonForm.client_name"
                  type="text"
                  required
                  placeholder="María García"
                  data-testid="json-client-name"
                  class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
                />
              </div>
              <div>
                <label for="json-client-email" class="block text-xs font-medium text-text-muted mb-1">Email</label>
                <input
                  id="json-client-email"
                  v-model="jsonForm.client_email"
                  type="email"
                  placeholder="maria@gmail.com"
                  data-testid="json-client-email"
                  class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
                />
              </div>
              <div>
                <label class="block text-xs font-medium text-text-muted mb-1">Teléfono / WhatsApp</label>
                <input
                  v-model="jsonForm.client_phone"
                  type="tel"
                  placeholder="+57 300 123 4567"
                  class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
                />
              </div>
              <div>
                <label class="block text-xs font-medium text-text-muted mb-1">Empresa</label>
                <input
                  v-model="jsonForm.client_company"
                  type="text"
                  placeholder="Acme Inc."
                  class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
                />
              </div>
            </div>
          </div>

          <div>
            <label for="json-email-intro" class="block text-xs font-medium text-text-muted mb-1">
              Mensaje personalizado del correo de envío
            </label>
            <p class="text-xs leading-relaxed text-text-muted mb-2">
              Se toma de <code>_meta.optional_metadata.email_intro</code>. Debe conectar problema, solución y resultado de negocio antes de enviar.
            </p>
            <textarea
              id="json-email-intro"
              v-model="jsonForm.email_intro"
              rows="6"
              class="w-full resize-y rounded-xl border border-input-border bg-input-bg px-4 py-2.5 text-sm text-input-text placeholder-input-placeholder outline-none focus:border-focus-ring focus:ring-2 focus:ring-focus-ring/30"
              placeholder="Ej. Esta propuesta resuelve… mediante… para lograr…"
              data-testid="json-email-intro"
            ></textarea>
          </div>

          <!-- Investment + Currency -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-medium text-text-muted mb-1">Inversión total</label>
              <BaseCurrencyInput
                v-model="jsonForm.total_investment"
                :decimals="2"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-text-muted mb-1">Moneda</label>
              <select
                v-model="jsonForm.currency"
                class="w-full px-4 py-2.5 border border-border-default rounded-xl text-sm
                       focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none bg-surface text-text-default"
              >
                <option value="COP">COP</option>
                <option value="USD">USD</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-medium text-text-muted mb-1">Nacionalidad</label>
              <select
                v-model="jsonForm.nationality"
                class="w-full px-4 py-2.5 border border-border-default rounded-xl text-sm
                       focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none bg-surface text-text-default"
              >
                <option value="COL">Colombia</option>
                <option value="EXT">Extranjeros</option>
                <option value="USA">Estados Unidos</option>
              </select>
            </div>
          </div>

          <!-- Project type / Market type -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-medium text-text-muted mb-1">Tipo de proyecto</label>
              <select v-model="jsonForm.project_type"
                class="w-full px-4 py-2.5 border border-border-default rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none bg-surface text-text-default">
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
              </select>
              <input
                v-if="jsonForm.project_type === 'other'"
                v-model="jsonForm.project_type_custom"
                type="text"
                placeholder="Especificar tipo de proyecto..."
                class="mt-2 w-full px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-text-muted mb-1">Tipo de mercado</label>
              <select v-model="jsonForm.market_type"
                class="w-full px-4 py-2.5 border border-border-default rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none bg-surface text-text-default">
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
              </select>
              <input
                v-if="jsonForm.market_type === 'other'"
                v-model="jsonForm.market_type_custom"
                type="text"
                placeholder="Especificar tipo de mercado..."
                class="mt-2 w-full px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              />
            </div>
          </div>

          <!-- Expires at -->
          <div>
            <label class="block text-xs font-medium text-text-muted mb-1">Fecha de expiración</label>
            <div class="flex items-center gap-2">
              <input
                v-model="jsonForm.expires_at"
                type="datetime-local"
                class="flex-1 px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              />
              <input
                v-model.number="expiryDaysInput"
                type="number"
                min="1"
                max="365"
                data-testid="json-expires-days"
                class="w-20 px-3 py-2.5 border border-input-border bg-input-bg text-input-text rounded-xl text-sm text-center focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              />
              <span class="text-xs text-text-subtle whitespace-nowrap">días</span>
            </div>
          </div>

          <!-- Reminder / Urgency / Discount -->
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label class="block text-xs font-medium text-text-muted mb-1">Recordatorio (día)</label>
              <input
                v-model.number="jsonForm.reminder_days"
                type="number" min="1" max="30"
                class="w-full px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-text-muted mb-1">Urgencia (día)</label>
              <input
                v-model.number="jsonForm.urgency_reminder_days"
                type="number" min="1" max="30"
                class="w-full px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-text-muted mb-1">Descuento (%)</label>
              <input
                v-model.number="jsonForm.discount_percent"
                type="number" min="0" max="100"
                class="w-full px-4 py-2.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              />
            </div>
          </div>

          <!-- Errors -->
          <div v-if="errorMsg" class="text-sm text-danger-strong bg-danger-soft px-4 py-3 rounded-xl">
            {{ errorMsg }}
          </div>

          <!-- Submit -->
          <div class="flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-3 sm:gap-4 pt-2">
            <BaseButton variant="primary" size="md" type="submit" class="w-full sm:w-auto sm:px-6" :disabled="proposalStore.isUpdating">
              {{ proposalStore.isUpdating ? 'Creando...' : 'Crear desde JSON' }}
            </BaseButton>
            <NuxtLink :to="localePath('/panel/proposals')" class="text-sm text-text-muted hover:text-text-default text-center sm:text-left">
              Cancelar
            </NuxtLink>
          </div>
        </div>
      </form>
    </div>

    <!-- ============================================================ -->
    <!-- PROMPT IA MODE -->
    <!-- ============================================================ -->
    <div v-if="mode === 'prompt'" class="max-w-3xl space-y-6">
      <div class="bg-surface rounded-xl shadow-sm border border-border-muted p-4 sm:p-6">
        <PromptSubTabsPanel v-model="createPromptSubTab">
          <template #commercial>
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
            <div>
              <h3 class="text-sm font-medium text-text-default">Prompt comercial</h3>
              <p class="text-xs text-text-subtle mt-0.5">Para rellenar el JSON de propuesta comercial (plantilla en «Importar JSON»).</p>
            </div>
          </div>
          <div class="flex flex-wrap items-center gap-2 mb-4">
            <template v-if="!createCommercialPromptIsEditing">
              <BaseButton variant="secondary" size="md" @click="startEditCreateCommercialPrompt">
                Editar
              </BaseButton>
              <BaseButton variant="secondary" size="md" @click="handleCopyCreateCommercialPrompt">
              <BaseActionIcon action="copy" />
                {{ createCommercialPromptCopied ? '¡Copiado!' : 'Copiar' }}
              </BaseButton>
              <BaseButton variant="secondary" size="md" @click="createCommercialPromptDownload">
              <BaseActionIcon action="download" />
                Descargar .md
              </BaseButton>
              <BaseButton variant="secondary" size="sm" v-if="createCommercialPromptText !== createCommercialPromptDefault" @click="handleResetCreateCommercialPrompt">
                Restaurar original
              </BaseButton>
            </template>
            <template v-else>
              <BaseButton variant="primary" size="md" @click="saveEditCreateCommercialPrompt">
                Guardar cambios
              </BaseButton>
              <BaseButton variant="ghost" size="md" @click="cancelEditCreateCommercialPrompt">
                Cancelar
              </BaseButton>
            </template>
          </div>
          <div v-if="createCommercialPromptIsEditing" class="bg-surface-raised rounded-xl border border-border-default overflow-hidden">
            <textarea
              v-model="createCommercialPromptEditBuffer"
              rows="28"
              class="w-full px-4 sm:px-6 py-4 text-xs font-mono leading-relaxed text-text-default bg-transparent border-0 outline-none resize-y focus:ring-0"
            />
          </div>
          <div v-else class="bg-surface-raised rounded-xl border border-border-default overflow-hidden">
            <div class="px-4 sm:px-6 py-4 max-h-[60vh] overflow-y-auto">
              <pre class="text-xs leading-relaxed text-text-default whitespace-pre-wrap font-mono break-words">{{ createCommercialPromptText }}</pre>
            </div>
          </div>
          <p v-if="createCommercialPromptText !== createCommercialPromptDefault" class="text-xs text-warning-strong mt-3">
            Prompt personalizado. «Restaurar original» vuelve al texto por defecto.
          </p>
          </template>

          <template #technical>
          <p class="text-sm text-text-muted mb-4">
            Para generar solo la clave <code class="text-xs bg-surface-raised px-1 rounded">technicalDocument</code> del JSON (sin narrativa comercial ni precios). Combínalo con la plantilla que incluye esa clave.
          </p>
          <div class="flex flex-wrap items-center gap-2 mb-4">
            <template v-if="!createTechnicalPromptIsEditing">
              <BaseButton variant="secondary" size="md" @click="startEditCreateTechnicalPrompt">
                Editar
              </BaseButton>
              <BaseButton variant="secondary" size="md" @click="handleCopyCreateTechnicalPrompt">
                {{ createTechnicalPromptCopied ? '¡Copiado!' : 'Copiar' }}
              </BaseButton>
              <BaseButton variant="secondary" size="md" @click="createTechnicalPromptDownload">
              <BaseActionIcon action="download" />
                Descargar .md
              </BaseButton>
              <BaseButton variant="secondary" size="sm" v-if="createTechnicalPromptText !== createTechnicalPromptDefault" @click="handleResetCreateTechnicalPrompt">
                Restaurar original
              </BaseButton>
            </template>
            <template v-else>
              <BaseButton variant="primary" size="md" @click="saveEditCreateTechnicalPrompt">
                Guardar cambios
              </BaseButton>
              <BaseButton variant="ghost" size="md" @click="cancelEditCreateTechnicalPrompt">
                Cancelar
              </BaseButton>
            </template>
          </div>
          <div v-if="createTechnicalPromptIsEditing" class="bg-surface-raised rounded-xl border border-border-default overflow-hidden">
            <textarea
              v-model="createTechnicalPromptEditBuffer"
              rows="26"
              class="w-full px-4 sm:px-6 py-4 text-xs font-mono leading-relaxed text-text-default bg-transparent border-0 outline-none resize-y focus:ring-0"
            />
          </div>
          <div v-else class="bg-surface-raised rounded-xl border border-border-default overflow-hidden">
            <div class="px-4 sm:px-6 py-4 max-h-[60vh] overflow-y-auto">
              <pre class="text-xs leading-relaxed text-text-default whitespace-pre-wrap font-mono break-words">{{ createTechnicalPromptText }}</pre>
            </div>
          </div>
          <p v-if="createTechnicalPromptText !== createTechnicalPromptDefault" class="text-xs text-warning-strong mt-3">
            Prompt técnico personalizado. «Restaurar original» vuelve al texto por defecto.
          </p>
          </template>
        </PromptSubTabsPanel>

        <div class="mt-4 bg-info-soft border border-info-strong/30 rounded-lg px-4 py-3">
          <p class="text-xs text-info-strong">
            <strong>Flujo recomendado:</strong><br/>
            1) Descarga la plantilla JSON desde «Importar JSON» (incluye <code class="text-[11px]">technicalDocument</code>).<br/>
            → 2) Usa el prompt comercial y/o el técnico según lo que quieras generar.<br/>
            → 3) Pega plantilla + prompts en tu IA.<br/>
            → 4) Pega el JSON resultante en «Importar JSON».
          </p>
        </div>
      </div>
    </div>

    <!-- Post-creation interstitial modal -->
    <BaseModal :model-value="showPostCreateModal && Boolean(createdProposal)" kind="confirm" :close-on-backdrop="false" :close-on-esc="false">
      <template v-if="createdProposal">
        <div class="p-6 panel-portrait:p-8 text-center">
          <div class="text-5xl mb-4">✅</div>
          <h3 class="text-xl font-bold text-text-default mb-2">Propuesta creada</h3>
          <p class="text-sm text-text-muted mb-4">{{ createdProposal.title }}</p>
          <div v-if="jsonWarnings.length" class="mb-4 text-left bg-warning-soft border border-warning-strong/30 rounded-lg px-4 py-3">
            <p class="text-xs font-semibold text-warning-strong mb-1">⚠️ Advertencias del JSON</p>
            <p v-for="(warn, i) in jsonWarnings" :key="i" class="text-xs text-warning-strong">{{ warn }}</p>
          </div>

        </div>
      </template>
      <template #footer>
        <BaseModalActions v-if="createdProposal">
          <a
            :href="'/proposal/' + createdProposal.uuid + '?preview=1'"
            target="_blank"
            class="w-full px-5 py-2.5 bg-surface-raised text-text-default rounded-xl font-medium text-sm hover:bg-surface-raised transition-colors inline-flex items-center justify-center gap-2"
          >
            <BaseActionIcon action="view" />
            Ver Preview
          </a>
          <BaseButton variant="ghost" size="md" class="w-full" v-if="canSendDirectly" :disabled="proposalStore.isUpdating" @click="handleSendCreated">
            {{ proposalStore.isUpdating ? 'Enviando...' : 'Enviar al Cliente' }}
          </BaseButton>
          <BaseButton variant="primary" size="md" class="w-full" @click="router.push(localePath(`/panel/proposals/${createdProposal.id}/edit`))">
            Ir a Editar
          </BaseButton>
        </BaseModalActions>
      </template>
    </BaseModal>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted, watch } from 'vue';
import PromptSubTabsPanel from '~/components/panel/PromptSubTabsPanel.vue';
import { get_request } from '~/stores/services/request_http';
import { DEFAULT_HOSTING_PERCENT } from '~/stores/proposals_constants';
import { useSellerPrompt } from '~/composables/useSellerPrompt';
import { useTechnicalPrompt } from '~/composables/useTechnicalPrompt';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { detectLegacyTechnicalFormat, downloadMigratedProposalJson, LEGACY_FIELD_LABELS } from '~/utils/proposalJsonMigration';
import LegacyFormatWarning from '~/components/panel/LegacyFormatWarning.vue';
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue';

const localePath = useLocalePath();
definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const router = useRouter();
const notify = usePanelNotify();

// The proposal already exists when a send fails, so we still land on its edit
// view (re-submitting the form would duplicate it) — but the failure must be
// surfaced instead of a silent success redirect.
function notifyFailedSend(sendResult) {
  notify.error({
    title: 'Propuesta creada, pero el envío falló.',
    detail: sendResult?.message || 'Reenvíala desde la vista de edición.',
  });
}
const proposalStore = useProposalStore();
const errorMsg = ref('');
const mode = ref('json');
const createdProposal = ref(null);
const showPostCreateModal = ref(false);

// ── Prompt IA ──
const createPromptSubTab = ref('commercial');

const {
  promptText: createCommercialPromptText,
  isEditing: createCommercialPromptIsEditing,
  DEFAULT_PROMPT: createCommercialPromptDefault,
  loadSavedPrompt: loadCreateCommercialPrompt,
  savePrompt: saveCreateCommercialPrompt,
  resetPrompt: resetCreateCommercialPrompt,
  copyPrompt: copyCreateCommercialPrompt,
  downloadPrompt: createCommercialPromptDownload,
} = useSellerPrompt();

const createCommercialPromptEditBuffer = ref('');
const createCommercialPromptCopied = ref(false);

function startEditCreateCommercialPrompt() {
  createCommercialPromptEditBuffer.value = createCommercialPromptText.value;
  createCommercialPromptIsEditing.value = true;
}
function cancelEditCreateCommercialPrompt() {
  createCommercialPromptIsEditing.value = false;
}
function saveEditCreateCommercialPrompt() {
  saveCreateCommercialPrompt(createCommercialPromptEditBuffer.value);
  createCommercialPromptIsEditing.value = false;
}
async function handleCopyCreateCommercialPrompt() {
  await copyCreateCommercialPrompt();
  createCommercialPromptCopied.value = true;
  setTimeout(() => { createCommercialPromptCopied.value = false; }, 2000);
}
function handleResetCreateCommercialPrompt() {
  resetCreateCommercialPrompt();
  createCommercialPromptIsEditing.value = false;
}

const {
  promptText: createTechnicalPromptText,
  isEditing: createTechnicalPromptIsEditing,
  DEFAULT_PROMPT: createTechnicalPromptDefault,
  loadSavedPrompt: loadCreateTechnicalPrompt,
  savePrompt: saveCreateTechnicalPrompt,
  resetPrompt: resetCreateTechnicalPrompt,
  copyPrompt: copyCreateTechnicalPrompt,
  downloadPrompt: createTechnicalPromptDownload,
} = useTechnicalPrompt();

const createTechnicalPromptEditBuffer = ref('');
const createTechnicalPromptCopied = ref(false);

function startEditCreateTechnicalPrompt() {
  createTechnicalPromptEditBuffer.value = createTechnicalPromptText.value;
  createTechnicalPromptIsEditing.value = true;
}
function cancelEditCreateTechnicalPrompt() {
  createTechnicalPromptIsEditing.value = false;
}
function saveEditCreateTechnicalPrompt() {
  saveCreateTechnicalPrompt(createTechnicalPromptEditBuffer.value);
  createTechnicalPromptIsEditing.value = false;
}
async function handleCopyCreateTechnicalPrompt() {
  await copyCreateTechnicalPrompt();
  createTechnicalPromptCopied.value = true;
  setTimeout(() => { createTechnicalPromptCopied.value = false; }, 2000);
}
function handleResetCreateTechnicalPrompt() {
  resetCreateTechnicalPrompt();
  createTechnicalPromptIsEditing.value = false;
}

async function refreshCreateDefaults({ seedHosting = false } = {}) {
  loadCreateCommercialPrompt();
  loadCreateTechnicalPrompt();
  await applyCreationDefaults(form.language, { seedHosting });
}

// Hosting is seeded only on mount: the manual panel-refresh button must not
// clobber values the user already typed into the form.
onMounted(() => refreshCreateDefaults({ seedHosting: true }));
usePanelRefresh(() => refreshCreateDefaults());

// -------------------------------------------------------------------------
// Shared helpers
// -------------------------------------------------------------------------
const DEFAULT_EXPIRATION_DAYS = 21;
const defaultExpirationDays = ref(DEFAULT_EXPIRATION_DAYS);
const pad = (n) => String(n).padStart(2, '0');

function buildDefaultExpiryStr(days = defaultExpirationDays.value) {
  const safeDays = Number.isInteger(days) && days > 0 ? days : DEFAULT_EXPIRATION_DAYS;
  const expiry = new Date(Date.now() + safeDays * 24 * 60 * 60 * 1000);
  return `${expiry.getFullYear()}-${pad(expiry.getMonth() + 1)}-${pad(expiry.getDate())}T${pad(expiry.getHours())}:${pad(expiry.getMinutes())}`;
}

function getExpiryDaysFromStr(datetimeStr) {
  if (!datetimeStr) return DEFAULT_EXPIRATION_DAYS;
  const diff = new Date(datetimeStr) - Date.now();
  return Math.max(1, Math.round(diff / (24 * 60 * 60 * 1000)));
}

const defaultExpiryStr = buildDefaultExpiryStr();
const expiryDaysInput = ref(getExpiryDaysFromStr(defaultExpiryStr));

// Updates both form.expires_at and jsonForm.expires_at regardless of active mode.
// This cross-mode sync is intentional: only one mode is visible at a time, and
// keeping both in sync avoids stale expiration dates when the user switches modes.
// With seedHosting (mount only, before the user touches the form) it also seeds
// the hosting fields from the admin-editable ProposalDefaultConfig — the
// constants in the form init are just the offline fallback.
const HOSTING_DEFAULT_FIELDS = [
  'hosting_percent',
  'hosting_discount_nine_month',
  'hosting_discount_semiannual',
  'hosting_discount_quarterly',
];

async function applyCreationDefaults(lang = 'es', { seedHosting = false } = {}) {
  const result = await proposalStore.fetchProposalDefaults(lang);
  if (!result.success || !result.data) return;
  const days = Number(result.data.expiration_days);
  if (Number.isInteger(days) && days > 0) {
    defaultExpirationDays.value = days;
    const expiryStr = buildDefaultExpiryStr(days);
    form.expires_at = expiryStr;
    jsonForm.expires_at = expiryStr;
  }
  if (seedHosting) {
    for (const field of HOSTING_DEFAULT_FIELDS) {
      const value = Number(result.data[field]);
      if (Number.isFinite(value) && value >= 0) {
        form[field] = value;
        jsonForm[field] = value;
      }
    }
  }
}

function parseInvestmentString(str) {
  if (!str) return 0;
  if (typeof str === 'number') return str;
  const cleaned = String(str).replace(/[^0-9]/g, '');
  return cleaned ? Number(cleaned) : 0;
}

function formatError(errors) {
  if (errors && typeof errors === 'object') {
    return Object.entries(errors)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
      .join(' | ');
  }
  return 'Error al crear la propuesta.';
}

// -------------------------------------------------------------------------
// MANUAL mode
// -------------------------------------------------------------------------
const form = reactive({
  title: '',
  client_id: null,
  client_name: '',
  client_email: '',
  client_phone: '',
  client_company: '',
  project_type: '',
  market_type: '',
  project_type_custom: '',
  market_type_custom: '',
  language: 'es',
  total_investment: 0,
  currency: 'COP',
  nationality: 'COL',
  hosting_percent: DEFAULT_HOSTING_PERCENT,
  hosting_discount_nine_month: 40,
  hosting_discount_semiannual: 20,
  hosting_discount_quarterly: 10,
  expires_at: defaultExpiryStr,
  reminder_days: 10,
  urgency_reminder_days: 15,
  discount_percent: 0,
  show_contract_terms: true,
  email_intro: '',
  email_features: [],
  email_method_phases: [
    { number: '01', title: 'Diagnóstico', duration: '', description: 'Mapeo de procesos y alcance final.' },
    { number: '02', title: 'Construcción', duration: '', description: 'Sprints con demo cada viernes.' },
    { number: '03', title: 'Lanzamiento', duration: '', description: 'Deploy, capacitación y soporte.' },
  ],
  email_signed_by: 'gustavo',
});

const MAX_EMAIL_FEATURES = 8;
function addEmailFeature() {
  if (form.email_features.length >= MAX_EMAIL_FEATURES) return;
  form.email_features = [...form.email_features, ''];
}
function removeEmailFeature(idx) {
  form.email_features = form.email_features.filter((_, i) => i !== idx);
}
function resetEmailMethodPhases() {
  form.email_method_phases = [
    { number: '01', title: 'Diagnóstico', duration: '', description: 'Mapeo de procesos y alcance final.' },
    { number: '02', title: 'Construcción', duration: '', description: 'Sprints con demo cada viernes.' },
    { number: '03', title: 'Lanzamiento', duration: '', description: 'Deploy, capacitación y soporte.' },
  ];
}

function onClientSelected(client) {
  if (!client) return;
  form.client_id = client.id;
  form.client_name = client.name || form.client_name;
  form.client_email = client.is_email_placeholder ? '' : client.email || '';
  form.client_phone = client.phone || form.client_phone;
  form.client_company = client.company || form.client_company;
}

function onCreateInlineClient(typedName) {
  form.client_id = null;
  if (typedName) {
    form.client_name = typedName;
  }
}

const canSendDirectly = computed(() => {
  const candidate = mode.value === 'json' ? jsonForm : form;
  return !!(
    candidate.client_email
    && candidate.client_name
    && candidate.total_investment > 0
    && candidate.email_intro?.trim()
  );
});

function sanitizeEmailMetadata(payload) {
  payload.email_intro = (payload.email_intro || '').trim();
  payload.email_features = (payload.email_features || [])
    .map((f) => (typeof f === 'string' ? f.trim() : ''))
    .filter(Boolean);
  payload.email_method_phases = (payload.email_method_phases || []).map((p) => ({
    number: (p.number || '').trim(),
    title: (p.title || '').trim(),
    duration: (p.duration || '').trim(),
    description: (p.description || '').trim(),
  }));
  return payload;
}

async function handleSubmit() {
  errorMsg.value = '';

  const payload = sanitizeEmailMetadata({ ...form });
  if (payload.expires_at) {
    payload.expires_at = new Date(payload.expires_at).toISOString();
  }

  const result = await proposalStore.createProposal(payload);
  if (result.success) {
    createdProposal.value = result.data;
    showPostCreateModal.value = true;
  } else {
    errorMsg.value = formatError(result.errors);
  }
}

async function handleCreateAndSend() {
  errorMsg.value = '';

  const payload = sanitizeEmailMetadata({ ...form });
  if (payload.expires_at) {
    payload.expires_at = new Date(payload.expires_at).toISOString();
  }

  const result = await proposalStore.createProposal(payload);
  if (result.success) {
    const sendResult = await proposalStore.sendProposal(result.data.id);
    if (!sendResult.success) {
      notifyFailedSend(sendResult);
    }
    router.push(localePath(`/panel/proposals/${result.data.id}/edit`));
  } else {
    errorMsg.value = formatError(result.errors);
  }
}

async function handleSendCreated() {
  if (!createdProposal.value?.id) return;
  const sendResult = await proposalStore.sendProposal(createdProposal.value.id);
  if (!sendResult.success) {
    notifyFailedSend(sendResult);
  }
  router.push(localePath(`/panel/proposals/${createdProposal.value.id}/edit`));
}

// -------------------------------------------------------------------------
// JSON IMPORT mode
// -------------------------------------------------------------------------
const EXPECTED_SECTION_KEYS = [
  'general', 'executiveSummary', 'contextDiagnostic', 'conversionStrategy',
  'designUX', 'creativeSupport', 'developmentStages', 'processMethodology',
  'valueAddedModules', 'functionalRequirements', 'timeline', 'investment',
  'proposalSummary', 'finalNote', 'nextSteps', 'technicalDocument',
];

const jsonRaw = ref('');
const jsonParsed = ref(null);
const jsonError = ref('');
const jsonWarnings = ref([]);
const uploadedFileName = ref('');
const isDownloading = ref(false);
const templateCopied = ref(false);
const legacyFormatIssues = ref([]);

const jsonForm = reactive({
  title: '',
  client_id: null,
  client_name: '',
  client_email: 'usuario@temp.example.com',
  client_phone: '',
  client_company: '',
  project_type: '',
  market_type: '',
  project_type_custom: '',
  market_type_custom: '',
  language: 'es',
  total_investment: 0,
  currency: 'COP',
  nationality: 'COL',
  hosting_percent: DEFAULT_HOSTING_PERCENT,
  hosting_discount_nine_month: 40,
  hosting_discount_semiannual: 20,
  hosting_discount_quarterly: 10,
  expires_at: defaultExpiryStr,
  reminder_days: 10,
  urgency_reminder_days: 15,
  discount_percent: 0,
  show_contract_terms: true,
  email_intro: '',
});

const jsonPreview = computed(() => {
  if (!jsonParsed.value) return {};
  const p = jsonParsed.value;
  const clientName = p.general?.clientName || '';
  const sectionCount = EXPECTED_SECTION_KEYS.filter((k) => k in p).length;
  const investment = p.investment?.totalInvestment || '';
  const epics = p.technicalDocument?.epics;
  const epicCount = Array.isArray(epics) ? epics.length : null;
  return { clientName, sectionCount, investment, epicCount };
});

function onJsonClientSelected(client) {
  if (!client) {
    jsonForm.client_id = null;
    return;
  }
  jsonForm.client_id = client.id;
  jsonForm.client_name = client.name || jsonForm.client_name;
  jsonForm.client_email = client.is_email_placeholder ? '' : (client.email || '');
  jsonForm.client_phone = client.phone || jsonForm.client_phone;
  jsonForm.client_company = client.company || jsonForm.client_company;
}

function onCreateInlineJsonClient(typedName) {
  jsonForm.client_id = null;
  if (typedName) {
    jsonForm.client_name = typedName;
  }
}

watch(
  [() => form.language, () => jsonForm.language],
  ([langA, langB], [prevA, prevB]) => {
    const changed = langA !== prevA ? langA : langB !== prevB ? langB : null;
    if (changed) applyCreationDefaults(changed);
  },
);

// Nationality suggests the currency (COL→COP, EXT/USA→USD); it stays editable.
watch(() => form.nationality, (nationality) => {
  form.currency = nationality === 'COL' ? 'COP' : 'USD';
});

watch(() => jsonForm.nationality, (nationality) => {
  jsonForm.currency = nationality === 'COL' ? 'COP' : 'USD';
});

watch(() => form.expires_at, (val) => {
  expiryDaysInput.value = getExpiryDaysFromStr(val);
});

watch(() => jsonForm.expires_at, (val) => {
  expiryDaysInput.value = getExpiryDaysFromStr(val);
});

watch(expiryDaysInput, (days) => {
  const safeDays = Number.isInteger(days) && days > 0 ? days : DEFAULT_EXPIRATION_DAYS;
  const expiry = new Date(Date.now() + safeDays * 24 * 60 * 60 * 1000);
  const dateStr = `${expiry.getFullYear()}-${pad(expiry.getMonth() + 1)}-${pad(expiry.getDate())}`;
  const timeStr = form.expires_at ? form.expires_at.slice(11, 16) : `${pad(expiry.getHours())}:${pad(expiry.getMinutes())}`;
  const str = `${dateStr}T${timeStr}`;
  form.expires_at = str;
  jsonForm.expires_at = str;
});

function parseJson() {
  // Re-parses fired by every textarea keystroke must not clobber values
  // the user already edited in the metadata form.
  const isFirstParse = jsonParsed.value === null;

  jsonError.value = '';
  jsonParsed.value = null;
  legacyFormatIssues.value = [];

  const raw = jsonRaw.value.trim();
  if (!raw) return;

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    jsonError.value = 'JSON inválido. Revisa la sintaxis.';
    return;
  }

  if (typeof parsed !== 'object' || Array.isArray(parsed)) {
    jsonError.value = 'El JSON debe ser un objeto, no un array.';
    return;
  }

  if (!parsed.general || !parsed.general.clientName) {
    jsonError.value = 'El JSON debe incluir "general" con "clientName".';
    return;
  }

  legacyFormatIssues.value = detectLegacyTechnicalFormat(parsed).issues;

  jsonParsed.value = parsed;

  if (!isFirstParse) return;

  const clientName = parsed.general.clientName;
  const proposalTitle = parsed.general?.proposalTitle?.trim();
  jsonForm.title = proposalTitle || `Propuesta — ${clientName}`;
  jsonForm.client_id = null;
  jsonForm.client_name = clientName;
  jsonForm.total_investment = parseInvestmentString(parsed.investment?.totalInvestment);
  jsonForm.currency = parsed.investment?.currency || 'COP';

  const rawMeta = parsed._meta || {};
  const meta = {
    ...(rawMeta.optional_metadata || {}),
    ...rawMeta,
  };
  if (meta.client_email) jsonForm.client_email = meta.client_email;
  if (typeof meta.email_intro === 'string') jsonForm.email_intro = meta.email_intro;
  if (meta.client_phone) jsonForm.client_phone = meta.client_phone;
  if (meta.client_company) jsonForm.client_company = meta.client_company;
  if (meta.project_type) jsonForm.project_type = meta.project_type;
  if (meta.market_type) jsonForm.market_type = meta.market_type;
  if (meta.language) jsonForm.language = meta.language;
  // Expiration is a business default (admin-configured); it is intentionally
  // NOT taken from the imported JSON. The seller can adjust the date manually.
}

function handleFileUpload(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  uploadedFileName.value = file.name;

  const reader = new FileReader();
  reader.onload = (e) => {
    jsonRaw.value = e.target.result;
    parseJson();
  };
  reader.readAsText(file);
}

async function copyTemplate() {
  try {
    const response = await get_request(`proposals/json-template/?lang=${jsonForm.language}`);
    const jsonStr = JSON.stringify(response.data, null, 2);
    await navigator.clipboard.writeText(jsonStr);
    templateCopied.value = true;
    setTimeout(() => { templateCopied.value = false; }, 2000);
  } catch (err) {
    console.error('Error copying template:', err);
  }
}

async function downloadTemplate() {
  isDownloading.value = true;
  try {
    const response = await get_request(`proposals/json-template/?lang=${jsonForm.language}`);
    const jsonStr = JSON.stringify(response.data, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `proposal-template-${jsonForm.language}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    console.error('Error downloading template:', err);
  } finally {
    isDownloading.value = false;
  }
}

async function handleJsonSubmit() {
  errorMsg.value = '';

  if (!jsonParsed.value) {
    errorMsg.value = 'Pega o sube un JSON válido primero.';
    return;
  }

  const sections = { ...jsonParsed.value };
  delete sections._meta;
  // Keep the greeting consistent with the linked/typed client.
  if (sections.general) {
    sections.general = { ...sections.general, clientName: jsonForm.client_name };
  }

  const payload = {
    title: jsonForm.title,
    client_name: jsonForm.client_name,
    client_email: jsonForm.client_email || '',
    email_intro: (jsonForm.email_intro || '').trim(),
    client_phone: jsonForm.client_phone || '',
    client_company: jsonForm.client_company || '',
    project_type: jsonForm.project_type || '',
    market_type: jsonForm.market_type || '',
    project_type_custom: jsonForm.project_type_custom || '',
    market_type_custom: jsonForm.market_type_custom || '',
    language: jsonForm.language,
    total_investment: jsonForm.total_investment || 0,
    currency: jsonForm.currency,
    nationality: jsonForm.nationality,
    expires_at: jsonForm.expires_at ? new Date(jsonForm.expires_at).toISOString() : null,
    reminder_days: jsonForm.reminder_days,
    urgency_reminder_days: jsonForm.urgency_reminder_days,
    discount_percent: jsonForm.discount_percent,
    show_contract_terms: jsonForm.show_contract_terms,
    sections,
    ...(jsonForm.client_id ? { client_id: jsonForm.client_id } : {}),
  };

  const result = await proposalStore.createProposalFromJSON(payload);
  if (result.success) {
    createdProposal.value = result.data;
    jsonWarnings.value = result.data?.warnings || [];
    showPostCreateModal.value = true;
  } else {
    errorMsg.value = formatError(result.errors);
  }
}
</script>
