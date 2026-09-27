<template>
  <div>
    <ConfirmModal
      v-model="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :variant="confirmState.variant"
      @confirm="handleConfirmed"
      @cancel="handleCancelled"
    />
    <p class="text-sm text-text-muted mb-6">
      Configura los valores iniciales que se aplicarán a las nuevas propuestas.
    </p>

    <!-- Tabs -->
    <BaseTabs v-model="activeTab" :tabs="tabs" />

    <!-- ═══ TAB: Vista General ═══ -->
    <div v-show="activeTab === 'general'" class="max-w-5xl mx-auto">
      <p class="text-sm text-text-muted mb-6">
        Estos son los valores por defecto que se aplican al crear una nueva propuesta. Puedes modificarlos aquí para que se pre-llenen automáticamente.
      </p>
      <form class="bg-surface rounded-xl shadow-sm border border-border-muted p-4 sm:p-8 space-y-6" @submit.prevent="handleSaveGeneral">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Idioma por defecto</label>
            <BaseSelect
              v-model="generalForm.language"
              :options="[{ value: 'es', label: 'Español' }, { value: 'en', label: 'English' }]"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Moneda</label>
            <BaseSelect
              v-model="generalForm.currency"
              :options="[{ value: 'COP', label: 'COP' }, { value: 'USD', label: 'USD' }]"
            />
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Inversión total por defecto</label>
            <BaseCurrencyInput v-model="generalForm.total_investment" :decimals="2" />
          </div>
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Hosting (% de inversión)</label>
            <div class="flex items-center gap-3">
              <BaseInput v-model.number="generalForm.hosting_percent" type="number" min="0" max="100" class="w-32" />
              <span class="text-sm text-text-muted">%</span>
            </div>
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Dcto. 9 meses hosting (%)</label>
            <BaseInput v-model.number="generalForm.hosting_discount_nine_month" type="number" min="0" max="100" class="w-32" />
          </div>
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Dcto. semestral hosting (%)</label>
            <BaseInput v-model.number="generalForm.hosting_discount_semiannual" type="number" min="0" max="100" class="w-32" />
          </div>
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Dcto. trimestral hosting (%)</label>
            <BaseInput v-model.number="generalForm.hosting_discount_quarterly" type="number" min="0" max="100" class="w-32" />
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Recordatorio (días después de enviar)</label>
            <BaseInput v-model.number="generalForm.reminder_days" type="number" min="1" max="30" />
          </div>
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Urgencia (días después de enviar)</label>
            <BaseInput v-model.number="generalForm.urgency_reminder_days" type="number" min="1" max="30" />
          </div>
        </div>
        <div>
          <label class="block text-sm font-medium text-text-default mb-1">Fecha de expiración</label>
          <div class="flex items-center gap-3">
            <BaseInput v-model.number="generalForm.expiration_days" type="number" min="1" max="365" class="w-32" />
            <span class="text-sm text-text-muted">días</span>
          </div>
          <p class="text-xs text-text-subtle mt-1">3 semanas = 21 días.</p>
        </div>
        <div>
          <label class="block text-sm font-medium text-text-default mb-1">Descuento por defecto (%)</label>
          <BaseInput v-model.number="generalForm.discount_percent" type="number" min="0" max="100" />
          <p class="text-xs text-text-subtle mt-1">0 = sin descuento en email de urgencia.</p>
        </div>
        <div>
          <label class="flex items-center gap-2 text-sm font-medium text-text-default mb-1">
            Patrón de URL personalizada
            <BaseTooltip position="right" width="max-w-xs">
              <div class="space-y-2 text-left">
                <p>Puedes usar <strong>texto libre</strong> o combinarlo con placeholders.</p>
                <p>
                  Placeholders disponibles:
                  <code>{client_name}</code>, <code>{project_type}</code>, <code>{year}</code>.
                </p>
                <p class="text-xs opacity-80">Reglas (se aplican automáticamente):</p>
                <ul class="list-disc pl-4 text-xs opacity-80 space-y-0.5">
                  <li>Se convierte a minúsculas</li>
                  <li>Los espacios se reemplazan por guiones <code>-</code></li>
                  <li>Se eliminan tildes y caracteres especiales</li>
                </ul>
                <p class="text-xs opacity-80">
                  Ejemplos: <code>mi-propuesta</code>, <code>{client_name}-2026</code>, <code>promo especial</code>.
                </p>
              </div>
            </BaseTooltip>
          </label>
          <BaseInput
            v-model="generalForm.default_slug_pattern"
            type="text"
            data-testid="defaults-slug-pattern"
            class="font-mono"
            placeholder="{client_name}"
          />
          <p class="text-xs text-text-subtle mt-1">
            Texto libre permitido. Se aplica al crear una propuesta si el vendedor no escribe una URL manualmente.
          </p>
          <p class="text-xs text-text-muted mt-1">
            Vista previa: <span class="font-mono text-text-brand">/proposal/{{ slugPatternPreview }}</span>
          </p>
        </div>
        <div class="flex items-center gap-3 pt-2">
          <BaseButton variant="primary" size="md" type="submit" :disabled="isSaving">
            {{ isSaving ? 'Guardando...' : 'Guardar Vista General' }}
          </BaseButton>
        </div>
      </form>
    </div>

    <!-- ═══ TAB: Secciones ═══ -->
    <div v-show="activeTab === 'sections'" class="max-w-7xl mx-auto">
      <p class="text-sm text-text-muted mb-4 max-w-3xl">
        Edita las secciones comerciales del modelo por defecto. El
        <strong class="text-text-default">detalle técnico</strong>
        (<code class="text-xs bg-surface-raised px-1 rounded">technical_document</code>)
        tiene su propia pestaña <strong class="text-text-default">Det. técnico</strong>
        con editor estructurado y JSON, igual que al editar una propuesta.
      </p>
      <!-- Language selector -->
      <div class="mb-6 flex items-center gap-3">
        <span class="text-xs font-medium text-text-muted uppercase tracking-wider">Idioma:</span>
        <div class="flex gap-2">
          <button
            v-for="opt in languageOptions"
            :key="opt.value"
            type="button"
            class="px-4 py-2 rounded-xl text-sm font-medium border transition-colors"
            :class="selectedLang === opt.value
              ? 'bg-primary text-on-primary border-primary'
              : 'bg-surface text-text-muted border-border-default hover:border-text-muted'"
            @click="switchLanguage(opt.value)"
          >
            {{ opt.label }}
          </button>
        </div>
        <span v-if="configUpdatedAt" class="text-[11px] text-text-subtle ml-4">
          Última actualización: {{ formatDate(configUpdatedAt) }}
        </span>
      </div>

      <!-- Loading -->
      <div v-if="isLoading" class="text-center py-12 text-text-subtle text-sm">
        Cargando configuración...
      </div>

      <!-- Sections list (commercial only; technical → tab Det. técnico) -->
      <div v-else-if="sections.length" class="space-y-3">
        <div
          v-for="{ section, idx } in commercialDefaultsEntries"
          :key="`${selectedLang}-${section.section_type}-${idx}`"
          class="bg-surface rounded-xl shadow-sm border border-border-muted overflow-hidden"
        >
          <div
            class="px-4 sm:px-6 py-4 flex flex-wrap items-center justify-between gap-2 cursor-pointer hover:bg-surface-muted transition-colors"
            @click="toggleSection(idx)"
          >
            <div class="flex items-center gap-4">
              <span class="text-xs text-text-subtle font-mono w-6">{{ section.order + 1 }}</span>
              <span class="text-sm font-medium text-text-default">{{ section.title }}</span>
              <span class="text-xs text-text-subtle">({{ section.section_type }})</span>
            </div>
            <div class="flex items-center gap-3">
              <span
                v-if="savedSections.has(idx)"
                class="text-xs text-text-brand font-medium"
              >✓ Modificado</span>
                <BaseActionButton action="view" label="Vista previa" @click.stop="handleSectionPreview(idx)" />
              <BaseActionIcon
                :action="expandedSections.has(idx) ? 'collapse' : 'expand'"
                class="text-text-subtle"
              />
            </div>
          </div>

          <div v-if="expandedSections.has(idx)" class="border-t border-border-muted px-3 sm:px-6 py-4 sm:py-6">
            <SectionEditor
              :key="`editor-${selectedLang}-${section.section_type}-${idx}`"
              :section="toVirtualSection(section, idx)"
              :proposalData="{}"
              :all-sections="sections"
              @save="handleSaveSection"
            />
          </div>
        </div>
      </div>

      <div v-else class="text-center py-16">
        <p class="text-text-muted text-sm">No se encontraron secciones por defecto.</p>
      </div>

      <!-- Sticky action bar for sections -->
      <div v-if="sections.length && !isLoading" class="sticky bottom-0 mt-6 bg-surface/95 backdrop-blur-sm border border-border-muted rounded-xl shadow-lg px-5 py-3 flex flex-col sm:flex-row items-center justify-between gap-3 z-10">
        <div class="flex items-center gap-2 text-xs text-text-muted">
          <span v-if="savedSections.size > 0" class="text-text-brand font-medium">
            {{ savedSections.size }} sección(es) modificada(s)
          </span>
          <span v-else>Sin cambios pendientes</span>
        </div>
        <div class="flex items-center gap-3">
          <BaseButton variant="secondary" size="sm" :disabled="isSaving" @click="handleReset">
            Restaurar valores originales
          </BaseButton>
          <BaseButton variant="primary" size="md" :loading="isSaving" :disabled="savedSections.size === 0" disabled-reason="Modifica al menos una sección antes de guardar." @click="handleSaveAll">
            {{ isSaving ? 'Guardando...' : 'Guardar Todos los Cambios' }}
          </BaseButton>
        </div>
      </div>
    </div>

    <!-- ═══ TAB: Det. técnico (misma UX que editar propuesta) ═══ -->
    <div v-show="activeTab === 'technical'" class="max-w-7xl mx-auto">
      <p class="text-sm text-text-muted mb-4">
        Valores por defecto del bloque técnico (nuevas propuestas). Idioma actual:
        <strong>{{ selectedLang === 'es' ? 'Español' : 'English' }}</strong> — cambia el idioma en la pestaña Secciones si necesitas la otra plantilla.
      </p>
      <div class="flex gap-1 mb-4 bg-surface-raised rounded-xl p-1 max-w-sm">
        <button
          type="button"
          :class="[
            'flex-1 px-3 py-2 text-sm rounded-lg transition-all',
            defaultsTechnicalSubTab === 'editor'
              ? 'bg-surface shadow-sm font-medium text-text-default'
              : 'text-text-muted',
          ]"
          @click="defaultsTechnicalSubTab = 'editor'"
        >
          Editor
        </button>
        <button
          type="button"
          :class="[
            'flex-1 px-3 py-2 text-sm rounded-lg transition-all',
            defaultsTechnicalSubTab === 'json'
              ? 'bg-surface shadow-sm font-medium text-text-default'
              : 'text-text-muted',
          ]"
          @click="defaultsTechnicalSubTab = 'json'"
        >
          JSON
        </button>
      </div>

      <div v-show="defaultsTechnicalSubTab === 'editor'">
        <p
          v-if="technicalDocumentIndex < 0"
          class="text-sm text-warning-strong bg-warning-soft border border-warning-strong/30 rounded-lg px-4 py-3"
        >
          No hay sección <code class="text-xs">technical_document</code> en la plantilla.
          Restaura valores originales desde Secciones o añade la entrada en la pestaña JSON.
        </p>
        <div v-else class="defaults-technical-editor">
          <TechnicalDocumentEditor
            :key="`defaults-tech-${selectedLang}-${technicalDocumentIndex}`"
            :section="technicalDefaultVirtualSection"
            :item-link-options="defaultsItemLinkOptions"
            @save="handleSaveSection"
          />
        </div>
      </div>

      <div v-show="defaultsTechnicalSubTab === 'json'" class="space-y-4">
        <p class="text-xs text-text-muted">
          Solo el objeto <code class="bg-surface-raised px-1 rounded">content_json</code> del detalle técnico. Mismo esquema que en el editor. Pulsa «Aplicar» para actualizar la plantilla en memoria; luego
          <strong>Guardar todos los cambios</strong> en Secciones o guarda desde JSON global.
        </p>
        <BaseTextarea
          v-model="defaultsTechnicalJsonRaw"
          :rows="24"
          class="font-mono"
        />
        <div v-if="defaultsTechnicalJsonError" class="text-sm text-danger-strong bg-danger-soft px-4 py-2 rounded-lg">
          {{ defaultsTechnicalJsonError }}
        </div>
        <div
          v-if="defaultsTechnicalJsonMsg"
          class="text-sm px-4 py-2 rounded-lg"
          :class="defaultsTechnicalJsonMsg.type === 'success' ? 'bg-success-soft text-success-strong' : 'bg-danger-soft text-danger-strong'"
        >
          {{ defaultsTechnicalJsonMsg.text }}
        </div>
        <BaseButton variant="primary" size="lg" @click="handleApplyDefaultsTechnicalJson">
          Aplicar a plantilla
        </BaseButton>
      </div>
    </div>

    <!-- ═══ TAB: Plantillas de Email ═══ -->
    <div v-show="activeTab === 'emails'">
      <TabSplitLayout ratio="2:3">
        <template #main>
          <div class="mb-4 flex flex-wrap items-center gap-2">
            <span class="text-xs font-medium text-text-muted uppercase tracking-wider mr-1">Filtrar:</span>
            <button
              v-for="cat in emailCategoryOptions"
              :key="cat.value"
              type="button"
              class="px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors"
              :class="emailSelectedCategory === cat.value
                ? 'bg-primary text-on-primary border-primary'
                : 'bg-surface text-text-muted border-border-default hover:border-text-muted'"
              @click="emailSelectedCategory = cat.value"
            >
              {{ cat.label }}
              <span class="ml-1 opacity-70">({{ countByCategory(cat.value) }})</span>
            </button>
          </div>

          <div v-if="emailIsLoading" class="text-center py-12 text-text-subtle text-sm">
            Cargando plantillas...
          </div>

          <div v-else-if="filteredEmailTemplates.length" class="space-y-2">
            <button
              v-for="tpl in filteredEmailTemplates"
              :key="tpl.template_key"
              type="button"
              class="w-full text-left bg-surface rounded-xl shadow-sm border transition-colors px-4 py-3 cursor-pointer hover:bg-surface-raised"
              :class="emailSelectedTemplate === tpl.template_key
                ? 'border-focus-ring ring-1 ring-focus-ring/30'
                : 'border-border-muted'"
              @click="selectEmailTemplate(tpl.template_key)"
            >
              <div class="flex items-start gap-3 min-w-0">
                <span class="text-lg flex-shrink-0">{{ emailCategoryIcon(tpl.category) }}</span>
                <div class="min-w-0 flex-1">
                  <div class="text-sm font-medium text-text-default truncate">{{ tpl.name }}</div>
                  <div class="text-xs text-text-subtle truncate">{{ tpl.description }}</div>
                  <div class="mt-1.5 flex flex-wrap items-center gap-1.5">
                    <span v-if="tpl.is_customized" class="text-[10px] text-text-brand font-medium bg-primary-soft px-1.5 py-0.5 rounded-full">Personalizado</span>
                    <span v-if="!tpl.is_active" class="text-[10px] text-danger-strong font-medium bg-danger-soft px-1.5 py-0.5 rounded-full">Desactivado</span>
                    <span class="text-[10px] text-text-subtle">{{ tpl.editable_fields_count }} campos</span>
                  </div>
                </div>
              </div>
            </button>
          </div>

          <div v-else class="text-center py-16">
            <p class="text-text-muted text-sm">No se encontraron plantillas de email.</p>
          </div>
        </template>

        <template #aside>
          <div
            v-if="!emailSelectedTemplate"
            class="bg-surface rounded-xl shadow-sm border border-dashed border-border-default px-6 py-16 text-center"
          >
            <p class="text-sm text-text-subtle">Selecciona una plantilla a la izquierda para editar sus campos.</p>
          </div>
          <div
            v-else-if="emailIsLoadingDetail && !emailTemplateDetail"
            class="bg-surface rounded-xl shadow-sm border border-border-muted px-6 py-12 text-center text-text-subtle text-sm"
          >
            Cargando campos editables...
          </div>
          <div
            v-else-if="emailTemplateDetail"
            class="bg-surface rounded-xl shadow-sm border border-border-muted px-4 sm:px-6 py-4 sm:py-6 space-y-5"
          >
            <div class="flex flex-wrap items-start justify-between gap-3 pb-4 border-b border-border-muted">
              <div class="flex items-start gap-3 min-w-0">
                <span class="text-2xl flex-shrink-0">{{ emailCategoryIcon(emailTemplateDetail.category) }}</span>
                <div class="min-w-0">
                  <h3 class="text-base font-medium text-text-default truncate">{{ emailTemplateDetail.name }}</h3>
                  <p class="text-xs text-text-subtle mt-0.5">{{ emailTemplateDetail.description }}</p>
                </div>
              </div>
              <BaseButton variant="ghost" size="sm" :disabled="emailIsPreviewLoading" @click="handleEmailPreview(emailSelectedTemplate)">
            <BaseActionIcon v-if="!emailIsPreviewLoading" action="view" />
            {{ emailIsPreviewLoading ? 'Cargando...' : 'Vista previa' }}
              </BaseButton>
            </div>

            <div class="flex items-center justify-between">
              <div>
                <span class="text-sm font-medium text-text-default">Estado del email</span>
                <p class="text-xs text-text-subtle mt-0.5">Desactiva para dejar de enviar este correo.</p>
              </div>
              <BaseToggle
                v-model="emailEditIsActive"
                size="md"
                aria-label="Activar / desactivar plantilla"
              />
            </div>

            <div v-for="field in emailTemplateDetail.editable_fields" :key="field.key" class="space-y-1.5">
              <div class="flex items-center justify-between">
                <label class="text-xs font-medium text-text-muted uppercase tracking-wider flex items-center gap-2">
                  {{ field.label }}
                  <span v-if="field.is_overridden" class="text-[10px] text-text-brand bg-primary-soft px-1.5 py-0.5 rounded-full normal-case tracking-normal">modificado</span>
                </label>
                <BaseButton variant="link" size="sm" v-if="emailEditFields[field.key] && emailEditFields[field.key] !== field.default_value" @click="emailEditFields[field.key] = field.default_value || ''">restaurar campo</BaseButton>
              </div>
              <BaseInput
                v-if="field.type === 'text'"
                v-model="emailEditFields[field.key]"
                type="text"
                :placeholder="field.default_value"
                :ref="el => { if (el?.$el) emailFieldRefs[field.key] = el.$el; else if (el) emailFieldRefs[field.key] = el }"
                @focus="emailLastFocusedField = field.key"
              />
              <BaseTextarea
                v-else
                v-model="emailEditFields[field.key]"
                :rows="3"
                :placeholder="field.default_value"
                :ref="el => { if (el?.$el) emailFieldRefs[field.key] = el.$el; else if (el) emailFieldRefs[field.key] = el }"
                @focus="emailLastFocusedField = field.key"
              />
              <p v-if="field.default_value" class="text-[11px] text-text-subtle">
                Por defecto: {{ truncateText(field.default_value, 100) }}
              </p>
            </div>

            <div v-if="emailTemplateDetail.available_variables?.length" class="pt-3 border-t border-border-muted">
              <p class="text-xs font-medium text-text-muted mb-2">
                Variables disponibles
                <span v-if="emailLastFocusedField" class="text-text-brand font-normal">(click para insertar en {{ emailLastFocusedField }})</span>
                <span v-else class="text-text-subtle font-normal">(haz clic en un campo primero)</span>
              </p>
              <div class="flex flex-wrap gap-1.5">
                <code
                  v-for="v in emailTemplateDetail.available_variables"
                  :key="v"
                  class="text-[11px] bg-surface-raised text-text-muted px-2 py-1 rounded-lg cursor-pointer hover:bg-primary-soft hover:text-text-brand transition-colors"
                  @click="emailInsertVariable(v)"
                >
                  {<span>{{ v }}</span>}
                </code>
              </div>
            </div>

            <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-4 border-t border-border-muted">
              <BaseButton
                variant="ghost"
                size="md"
                class="!text-danger-strong hover:!bg-danger-soft"
                @click="handleResetEmailTemplate(emailSelectedTemplate)"
              >
                Restaurar
              </BaseButton>
              <BaseButton
                variant="primary"
                size="lg"
                :loading="isSaving"
                :disabled="isSaving"
                @click="handleSaveEmailTemplate(emailSelectedTemplate)"
              >
                {{ isSaving ? 'Guardando...' : 'Guardar Cambios' }}
              </BaseButton>
            </div>
          </div>
        </template>
      </TabSplitLayout>
    </div>

    <!-- ═══ TAB: Prompt IA ═══ -->
    <div v-show="activeTab === 'prompt'" class="max-w-7xl mx-auto">
      <PromptSubTabsPanel v-model="defaultsPromptSubTab" dark-track>
        <template #commercial>
        <p class="text-sm text-text-muted mb-6">
          Este prompt se usa con IA (ChatGPT, Claude, etc.) para generar propuestas comerciales personalizadas a partir del JSON plantilla.
          El detalle técnico por defecto se edita en la pestaña <strong class="text-text-default">Det. técnico</strong>;
          para la IA solo técnica usa la subpestaña <strong class="text-text-default">Técnico</strong> aquí abajo.
        </p>

        <!-- Action bar -->
        <div class="flex flex-wrap items-center gap-2 mb-4">
          <template v-if="!promptIsEditing">
            <BaseButton variant="secondary" size="md" @click="startEditPrompt">
              <BaseActionIcon action="edit" />
              Editar
            </BaseButton>
            <BaseButton variant="secondary" size="md" @click="handleCopyPrompt">
              <BaseActionIcon action="copy" />
              {{ promptCopied ? '¡Copiado!' : 'Copiar' }}
            </BaseButton>
            <BaseButton variant="secondary" size="md" @click="promptDownload">
              <BaseActionIcon action="download" />
              Descargar .md
            </BaseButton>
            <BaseButton variant="secondary" size="sm" v-if="promptText !== promptDefault" @click="handleResetPrompt">
              Restaurar original
            </BaseButton>
          </template>
          <template v-else>
            <BaseButton variant="primary" size="md" @click="saveEditPrompt">
              Guardar cambios
            </BaseButton>
            <BaseButton variant="ghost" size="md" @click="cancelEditPrompt">
              Cancelar
            </BaseButton>
          </template>
        </div>

        <!-- Editing mode -->
        <div v-if="promptIsEditing" class="bg-surface rounded-xl shadow-sm border border-border-muted overflow-hidden">
          <textarea
            v-model="promptEditBuffer"
            rows="30"
            class="w-full px-4 sm:px-6 py-4 text-xs font-mono leading-relaxed text-text-default bg-transparent border-0 outline-none resize-y focus:ring-0"
          ></textarea>
        </div>

        <!-- Read-only mode -->
        <div v-else class="bg-surface rounded-xl shadow-sm border border-border-muted overflow-hidden">
          <div class="px-4 sm:px-6 py-4 max-h-[70vh] overflow-y-auto">
            <pre class="text-xs leading-relaxed text-text-default whitespace-pre-wrap font-mono break-words">{{ promptText }}</pre>
          </div>
        </div>

        <p v-if="promptText !== promptDefault" class="text-xs text-warning-strong mt-3">
          Este prompt ha sido personalizado. Usa "Restaurar original" para volver al valor por defecto.
        </p>
        </template>

        <template #technical>
        <p class="text-sm text-text-muted mb-6">
          Prompt para generar la clave <code class="text-xs bg-surface-raised px-1 rounded">technicalDocument</code> (arquitectura, módulos del producto, requerimientos). Sin narrativa comercial ni precios.
          La estructura por defecto del detalle técnico está en la pestaña <strong class="text-text-default">Det. técnico</strong> (editor o JSON) y en la pestaña <strong class="text-text-default">JSON</strong> global.
        </p>
        <div class="flex flex-wrap items-center gap-2 mb-4">
          <template v-if="!technicalDefaultsPromptIsEditing">
            <BaseButton variant="secondary" size="md" @click="startEditTechnicalDefaultsPrompt">
              Editar
            </BaseButton>
            <BaseButton variant="secondary" size="md" @click="handleCopyTechnicalDefaultsPrompt">
              {{ technicalDefaultsPromptCopied ? '¡Copiado!' : 'Copiar' }}
            </BaseButton>
            <BaseButton variant="secondary" size="md" @click="technicalDefaultsPromptDownload">
              <BaseActionIcon action="download" />
              Descargar .md
            </BaseButton>
            <BaseButton variant="secondary" size="sm" v-if="technicalDefaultsPromptText !== technicalDefaultsPromptDefault" @click="handleResetTechnicalDefaultsPrompt">
              Restaurar original
            </BaseButton>
          </template>
          <template v-else>
            <BaseButton variant="primary" size="md" @click="saveEditTechnicalDefaultsPrompt">
              Guardar cambios
            </BaseButton>
            <BaseButton variant="ghost" size="md" @click="cancelEditTechnicalDefaultsPrompt">
              Cancelar
            </BaseButton>
          </template>
        </div>
        <div v-if="technicalDefaultsPromptIsEditing" class="bg-surface rounded-xl shadow-sm border border-border-muted overflow-hidden">
          <textarea
            v-model="technicalDefaultsPromptEditBuffer"
            rows="28"
            class="w-full px-4 sm:px-6 py-4 text-xs font-mono leading-relaxed text-text-default bg-transparent border-0 outline-none resize-y focus:ring-0"
          ></textarea>
        </div>
        <div v-else class="bg-surface rounded-xl shadow-sm border border-border-muted overflow-hidden">
          <div class="px-4 sm:px-6 py-4 max-h-[70vh] overflow-y-auto">
            <pre class="text-xs leading-relaxed text-text-default whitespace-pre-wrap font-mono break-words">{{ technicalDefaultsPromptText }}</pre>
          </div>
        </div>
        <p v-if="technicalDefaultsPromptText !== technicalDefaultsPromptDefault" class="text-xs text-warning-strong mt-3">
          Prompt técnico personalizado. «Restaurar original» vuelve al valor por defecto.
        </p>
        </template>
      </PromptSubTabsPanel>
    </div>

    <!-- ═══ TAB: JSON ═══ -->
    <div v-show="activeTab === 'json'" class="max-w-7xl mx-auto">
      <p class="text-sm text-text-muted mb-2">
        Representación JSON de la configuración por defecto (secciones plantilla). Puedes editar directamente el JSON y guardar los cambios.
      </p>
      <ul class="text-xs text-text-muted mb-4 list-disc list-inside space-y-1">
        <li>
          Debe existir una entrada con <code class="bg-surface-raised px-1 rounded">section_type: &quot;technical_document&quot;</code> y su
          <code class="bg-surface-raised px-1 rounded">content_json</code> (arquitectura, módulos del producto, <code class="text-[10px]">epicKey</code> / <code class="text-[10px]">flowKey</code>, etc.).
        </li>
        <li>
          Al importar una propuesta desde JSON global, la clave camelCase es <code class="bg-surface-raised px-1 rounded">technicalDocument</code> — distinta de este formato de plantilla.
        </li>
      </ul>
      <p
        v-if="defaultsTechnicalEpicCount !== null"
        class="text-xs text-success-strong bg-success-soft border border-success-strong/30 rounded-lg px-3 py-2 mb-4"
      >
        Vista rápida: <strong>{{ defaultsTechnicalEpicCount }}</strong> módulo(s) en el detalle técnico por defecto (idioma {{ selectedLang }}).
      </p>

      <!-- Action bar -->
      <div class="flex flex-wrap items-center gap-2 mb-4">
        <template v-if="!jsonIsEditing">
          <BaseButton variant="secondary" size="md" @click="startEditJson">
              <BaseActionIcon action="edit" />
            Editar
          </BaseButton>
          <BaseButton variant="secondary" size="md" @click="copyDefaultsJson">
              <BaseActionIcon action="copy" />
            {{ defaultsJsonCopied ? '¡Copiado!' : 'Copiar' }}
          </BaseButton>
          <BaseButton variant="secondary" size="md" @click="downloadDefaultsJson">
              <BaseActionIcon action="download" />
            Descargar .json
          </BaseButton>
        </template>
        <template v-else>
          <BaseButton variant="primary" size="md" :disabled="isSaving" @click="saveEditJson">
            {{ isSaving ? 'Guardando...' : 'Guardar cambios' }}
          </BaseButton>
          <BaseButton variant="ghost" size="md" @click="cancelEditJson">
            Cancelar
          </BaseButton>
        </template>
      </div>

      <div v-if="defaultsJsonLoading" class="text-center py-8 text-text-subtle text-sm">
        Cargando JSON...
      </div>

      <!-- Editing mode -->
      <div v-else-if="jsonIsEditing" class="space-y-2">
        <div class="bg-surface rounded-xl shadow-sm border border-border-muted overflow-hidden">
          <textarea
            v-model="jsonEditBuffer"
            rows="24"
            class="w-full px-4 py-3 border-0 text-xs font-mono leading-relaxed
                   bg-transparent text-text-default outline-none resize-y focus:ring-0"
          />
        </div>
        <p v-if="jsonEditError" class="text-xs text-danger-strong px-1">
          {{ jsonEditError }}
        </p>
      </div>

      <!-- Read-only mode -->
      <div v-else class="bg-surface rounded-xl shadow-sm border border-border-muted overflow-hidden">
        <div class="px-4 py-3 max-h-[70vh] overflow-y-auto">
          <pre class="text-xs leading-relaxed text-text-default whitespace-pre-wrap font-mono break-words">{{ defaultsJsonString }}</pre>
        </div>
      </div>
    </div>

    <!-- ═══ Shared modals ═══ -->

    <!-- Email preview modal -->
    <Teleport to="body">
      <Transition name="fade-modal">
        <div v-if="emailShowPreview" class="fixed inset-0 z-[9990] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4" @click.self="emailShowPreview = false">
          <div class="bg-surface rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden">
            <div class="flex items-center justify-between px-6 py-4 border-b border-border-muted">
              <div>
                <h3 class="text-lg font-semibold text-text-default">Vista Previa</h3>
                <p v-if="emailPreviewSubject" class="text-xs text-text-muted mt-0.5 truncate max-w-md">Asunto: {{ emailPreviewSubject }}</p>
              </div>
              <BaseActionButton action="close" label="Cerrar vista previa" @click="emailShowPreview = false" />
            </div>
            <div class="flex-1 overflow-auto">
              <iframe v-if="emailPreviewHtml" :srcdoc="emailPreviewHtml" class="w-full h-full min-h-[500px] border-0" sandbox="allow-same-origin" />
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Email reset confirmation modal -->
    <BaseModal v-model="emailShowResetConfirm" kind="confirm">
      <div class="p-6 text-center">
        <div class="text-4xl mb-3">⚠️</div>
        <h3 class="text-lg font-bold text-text-default mb-2">¿Restaurar valores originales?</h3>
        <p class="text-sm text-text-muted mb-6">Esto eliminará las personalizaciones de esta plantilla y volverá al contenido por defecto del sistema.</p>
      </div>
      <template #footer>
        <BaseModalActions>
          <BaseButton variant="danger" size="md" :disabled="isSaving" @click="confirmResetEmailTemplate">
            {{ isSaving ? 'Restaurando...' : 'Sí, restaurar' }}
          </BaseButton>
          <BaseButton variant="ghost" size="md" @click="emailShowResetConfirm = false">Cancelar</BaseButton>
        </BaseModalActions>
      </template>
    </BaseModal>

    <!-- Section reset confirmation modal -->
    <BaseModal v-model="showResetConfirm" kind="confirm">
      <div class="p-6 text-center">
        <div class="text-4xl mb-3">⚠️</div>
        <h3 class="text-lg font-bold text-text-default mb-2">¿Restaurar valores originales?</h3>
        <p class="text-sm text-text-muted mb-6">
          Esto eliminará toda la configuración personalizada para <strong>{{ selectedLang === 'es' ? 'Español' : 'English' }}</strong>
          y volverá a los valores del sistema. Las propuestas existentes no se verán afectadas.
        </p>
      </div>
      <template #footer>
        <BaseModalActions>
          <BaseButton variant="danger" size="md" :disabled="isSaving" @click="confirmReset">
            {{ isSaving ? 'Restaurando...' : 'Sí, restaurar' }}
          </BaseButton>
          <BaseButton variant="ghost" size="md" @click="showResetConfirm = false">
            Cancelar
          </BaseButton>
        </BaseModalActions>
      </template>
    </BaseModal>

    <!-- Section preview modal -->
    <SectionPreviewModal
      :visible="showSectionPreview"
      :section="previewSection"
      :proposalData="{}"
      @close="showSectionPreview = false"
    />

    <!-- Feedback messages -->
    <Transition name="fade-modal">
      <div v-if="feedbackMsg" class="fixed bottom-6 right-6 z-50 px-5 py-3 rounded-xl shadow-lg text-sm font-medium"
        :class="feedbackType === 'success' ? 'bg-primary text-on-primary' : 'bg-danger-strong text-on-danger'"
      >
        {{ feedbackMsg }}
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import SectionEditor from '~/components/BusinessProposal/admin/SectionEditor.vue';
import TechnicalDocumentEditor from '~/components/BusinessProposal/admin/TechnicalDocumentEditor.vue';
import SectionPreviewModal from '~/components/BusinessProposal/admin/SectionPreviewModal.vue';
import PromptSubTabsPanel from '~/components/panel/PromptSubTabsPanel.vue';
import TabSplitLayout from '~/components/panel/TabSplitLayout.vue';
import { DEFAULT_HOSTING_PERCENT } from '~/stores/proposals_constants';
import { buildProposalItemLinkOptions } from '~/utils/proposalModuleLinkOptions';
import { useSellerPrompt } from '~/composables/useSellerPrompt';
import { useTechnicalPrompt } from '~/composables/useTechnicalPrompt';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { toSlug } from '~/utils/slugify';
import { formatDateTime } from '~/utils/formatDate';


const proposalStore = useProposalStore();
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();

const tabs = [
  { id: 'general', label: 'Vista General' },
  { id: 'sections', label: 'Secciones' },
  { id: 'technical', label: 'Det. técnico' },
  { id: 'emails', label: 'Plantillas de Email' },
  { id: 'prompt', label: 'Prompt Proposal' },
  { id: 'json', label: 'JSON' },
];
const route = useRoute();
const initialTab = ['general', 'sections', 'technical', 'emails', 'prompt', 'json'].includes(route.query.tab)
  ? route.query.tab
  : 'general';
const activeTab = ref(initialTab);

const languageOptions = [
  { value: 'es', label: 'Español' },
  { value: 'en', label: 'English' },
];

// ── Shared state ──
const isRefreshing = ref(false);
const isSaving = ref(false);
const feedbackMsg = ref('');
const feedbackType = ref('success');

function showFeedback(msg, type = 'success') {
  feedbackMsg.value = msg;
  feedbackType.value = type;
  setTimeout(() => { feedbackMsg.value = ''; }, 3500);
}

function formatDate(dateStr) {
  return formatDateTime(dateStr, { fallback: '' });
}

// ── Vista General ──
const generalForm = ref({
  language: 'es',
  currency: 'COP',
  total_investment: 0,
  hosting_percent: DEFAULT_HOSTING_PERCENT,
  hosting_discount_nine_month: 40,
  hosting_discount_semiannual: 20,
  hosting_discount_quarterly: 10,
  expiration_days: 21,
  reminder_days: 3,
  urgency_reminder_days: 7,
  discount_percent: 0,
  default_slug_pattern: '{client_name}',
});

const slugPatternPreview = computed(() => {
  const pattern = (generalForm.value.default_slug_pattern || '').trim() || '{client_name}';
  const sample = {
    '{client_name}': 'María López',
    '{project_type}': 'E-commerce',
    '{year}': String(new Date().getFullYear()),
  };
  let rendered = pattern;
  for (const [key, val] of Object.entries(sample)) rendered = rendered.split(key).join(val);
  return toSlug(rendered, { fallback: 'propuesta' });
});

async function handleSaveGeneral() {
  isSaving.value = true;
  try {
    const result = await proposalStore.saveProposalDefaults(
      generalForm.value.language,
      null,
      generalForm.value,
    );
    if (result.success) {
      if (generalForm.value.language !== selectedLang.value) {
        selectedLang.value = generalForm.value.language;
        await loadDefaults(selectedLang.value);
      }
      showFeedback('Valores generales guardados correctamente.', 'success');
    } else {
      showFeedback('Error al guardar los valores generales.', 'error');
    }
  } finally {
    isSaving.value = false;
  }
}

// ── Secciones ──
const selectedLang = ref('es');
const sections = ref([]);
const configUpdatedAt = ref(null);
const isLoading = ref(false);
const expandedSections = ref(new Set());
const savedSections = ref(new Set());
const showResetConfirm = ref(false);
const showSectionPreview = ref(false);
const previewSection = ref({});

/** Commercial sections only — technical defaults live in tab Det. técnico. */
const commercialDefaultsEntries = computed(() =>
  sections.value.map((section, idx) => ({ section, idx })).filter(
    ({ section }) => section.section_type !== 'technical_document',
  ),
);

const technicalDocumentIndex = computed(() =>
  sections.value.findIndex((s) => s.section_type === 'technical_document'),
);

const technicalDefaultVirtualSection = computed(() => {
  const idx = technicalDocumentIndex.value;
  if (idx < 0) return null;
  return toVirtualSection(sections.value[idx], idx);
});

const defaultsItemLinkOptions = computed(() =>
  buildProposalItemLinkOptions(sections.value),
);

const defaultsTechnicalSubTab = ref('editor');
const defaultsTechnicalJsonRaw = ref('{}');
const defaultsTechnicalJsonError = ref('');
const defaultsTechnicalJsonMsg = ref(null);

const defaultsTechnicalEpicCount = computed(() => {
  const idx = technicalDocumentIndex.value;
  if (idx < 0) return null;
  const epics = sections.value[idx]?.content_json?.epics;
  if (!Array.isArray(epics)) return 0;
  return epics.length;
});

function refreshDefaultsTechnicalJson() {
  defaultsTechnicalJsonError.value = '';
  defaultsTechnicalJsonMsg.value = null;
  const idx = technicalDocumentIndex.value;
  if (idx < 0) {
    defaultsTechnicalJsonRaw.value = '{}';
    return;
  }
  const cj = sections.value[idx]?.content_json;
  try {
    defaultsTechnicalJsonRaw.value = JSON.stringify(
      cj && typeof cj === 'object' ? cj : {},
      null,
      2,
    );
  } catch {
    defaultsTechnicalJsonRaw.value = '{}';
  }
}

function handleApplyDefaultsTechnicalJson() {
  defaultsTechnicalJsonError.value = '';
  defaultsTechnicalJsonMsg.value = null;
  const idx = technicalDocumentIndex.value;
  if (idx < 0) {
    defaultsTechnicalJsonError.value = 'No hay sección technical_document en la plantilla.';
    return;
  }
  let parsed;
  try {
    parsed = JSON.parse(defaultsTechnicalJsonRaw.value.trim());
  } catch (e) {
    defaultsTechnicalJsonError.value = `JSON inválido: ${e.message}`;
    return;
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    defaultsTechnicalJsonError.value = 'El contenido debe ser un objeto JSON.';
    return;
  }
  sections.value[idx] = {
    ...sections.value[idx],
    content_json: parsed,
  };
  savedSections.value = new Set([...savedSections.value, idx]);
  defaultsTechnicalJsonMsg.value = {
    type: 'success',
    text: 'Plantilla técnica actualizada en memoria. Usa «Guardar todos los cambios» en Secciones (o guarda desde JSON global).',
  };
}

watch(defaultsTechnicalSubTab, (sub) => {
  if (sub === 'json') {
    refreshDefaultsTechnicalJson();
  }
});

watch(activeTab, (tab) => {
  if (tab === 'technical' && defaultsTechnicalSubTab.value === 'json') {
    refreshDefaultsTechnicalJson();
  }
});

function handleSectionPreview(idx) {
  if (idx >= 0 && idx < sections.value.length) {
    previewSection.value = toVirtualSection(sections.value[idx], idx);
    showSectionPreview.value = true;
  }
}

function toVirtualSection(section, idx) {
  return {
    id: `default-${idx}`,
    section_type: section.section_type,
    title: section.title,
    content_json: section.content_json || {},
    is_wide_panel: section.is_wide_panel || false,
    is_enabled: true,
  };
}

function toggleSection(idx) {
  const s = new Set(expandedSections.value);
  if (s.has(idx)) s.delete(idx);
  else s.add(idx);
  expandedSections.value = s;
}

function handleSaveSection({ sectionId, payload }) {
  const idx = typeof sectionId === 'string' && sectionId.startsWith('default-')
    ? parseInt(sectionId.replace('default-', ''), 10)
    : sectionId;

  if (idx >= 0 && idx < sections.value.length) {
    sections.value[idx] = {
      ...sections.value[idx],
      title: payload.title,
      content_json: payload.content_json,
    };
    savedSections.value = new Set([...savedSections.value, idx]);
    showFeedback('Sección actualizada localmente. Guarda todos los cambios para persistir.', 'success');
  }
}

/**
 * Adopt the version just written as the base for the next save. Without a
 * fresh updated_at the following save would look stale and be rejected, so
 * fall back to re-reading the config rather than inventing a timestamp.
 */
async function syncConfigVersion(result) {
  const updatedAt = result.data?.updated_at;
  if (updatedAt) {
    configUpdatedAt.value = updatedAt;
    return;
  }
  await loadDefaults(selectedLang.value);
}

async function loadDefaults(lang) {
  isLoading.value = true;
  expandedSections.value = new Set();
  savedSections.value = new Set();
  try {
    const result = await proposalStore.fetchProposalDefaults(lang);
    if (result.success && result.data) {
      sections.value = result.data.sections_json || [];
      configUpdatedAt.value = result.data.updated_at;
      const d = result.data;
      const num = (v, fallback) => {
        const n = Number(v);
        return Number.isFinite(n) ? n : fallback;
      };
      generalForm.value = {
        ...generalForm.value,
        language: lang,
        currency: typeof d.default_currency === 'string' ? d.default_currency : 'COP',
        total_investment: num(d.default_total_investment, 0),
        hosting_percent: num(d.hosting_percent, DEFAULT_HOSTING_PERCENT),
        hosting_discount_nine_month: num(d.hosting_discount_nine_month, 40),
        hosting_discount_semiannual: num(d.hosting_discount_semiannual, 20),
        hosting_discount_quarterly: num(d.hosting_discount_quarterly, 10),
        expiration_days: num(d.expiration_days, 21),
        reminder_days: num(d.reminder_days, 3),
        urgency_reminder_days: num(d.urgency_reminder_days, 7),
        discount_percent: num(d.default_discount_percent, 0),
        default_slug_pattern: typeof d.default_slug_pattern === 'string'
          ? d.default_slug_pattern
          : '{client_name}',
      };
    }
  } finally {
    isLoading.value = false;
  }
}

async function switchLanguage(lang) {
  if (lang === selectedLang.value) return;
  if (savedSections.value.size > 0) {
    requestConfirm({
      title: 'Cambios sin guardar',
      message: 'Tienes cambios sin guardar. ¿Deseas cambiar de idioma y perder los cambios?',
      variant: 'warning',
      confirmText: 'Cambiar idioma',
      onConfirm: async () => {
        selectedLang.value = lang;
        await loadDefaults(lang);
      },
    });
    return;
  }
  selectedLang.value = lang;
  await loadDefaults(lang);
}

async function handleSaveAll() {
  isSaving.value = true;
  try {
    const result = await proposalStore.saveProposalDefaults(
      selectedLang.value, sections.value, null, configUpdatedAt.value,
    );
    if (result.success) {
      savedSections.value = new Set();
      await syncConfigVersion(result);
      showFeedback('Valores por defecto guardados correctamente.', 'success');
    } else if (result.code === 'stale_defaults') {
      // Edits are kept on screen on purpose: the admin decides whether to
      // refresh (losing them) or copy them over the current version.
      showFeedback(result.message, 'error');
    } else {
      showFeedback('Error al guardar los valores por defecto.', 'error');
    }
  } finally {
    isSaving.value = false;
  }
}

function handleReset() {
  showResetConfirm.value = true;
}

async function confirmReset() {
  isSaving.value = true;
  try {
    const result = await proposalStore.resetProposalDefaults(selectedLang.value);
    if (result.success) {
      showResetConfirm.value = false;
      savedSections.value = new Set();
      await loadDefaults(selectedLang.value);
      showFeedback('Valores restaurados a los originales del sistema.', 'success');
    } else {
      showFeedback('Error al restaurar los valores por defecto.', 'error');
    }
  } finally {
    isSaving.value = false;
  }
}

// ── Plantillas de Email ──
const emailCategoryOptions = [
  { value: 'all', label: 'Todos' },
  { value: 'client', label: 'Cliente' },
  { value: 'internal', label: 'Interno' },
  { value: 'contact', label: 'Contacto' },
];

const emailTemplates = ref([]);
const emailSelectedCategory = ref('all');
const emailSelectedTemplate = ref(null);
const emailTemplateDetail = ref(null);
const emailEditFields = ref({});
const emailEditIsActive = ref(true);
const emailIsLoading = ref(false);
const emailLastFocusedField = ref('');
const emailFieldRefs = ref({});
const emailIsLoadingDetail = ref(false);
const emailIsPreviewLoading = ref(false);
const emailShowPreview = ref(false);
const emailPreviewHtml = ref('');
const emailPreviewSubject = ref('');
const emailShowResetConfirm = ref(false);
const emailResetTargetKey = ref('');

const filteredEmailTemplates = computed(() => {
  if (emailSelectedCategory.value === 'all') return emailTemplates.value;
  return emailTemplates.value.filter(t => t.category === emailSelectedCategory.value);
});

function countByCategory(cat) {
  if (cat === 'all') return emailTemplates.value.length;
  return emailTemplates.value.filter(t => t.category === cat).length;
}

function emailInsertVariable(name) {
  const varText = `{${name}}`;
  if (emailLastFocusedField.value && emailEditFields.value[emailLastFocusedField.value] !== undefined) {
    emailEditFields.value[emailLastFocusedField.value] += varText;
    showFeedback(`Variable ${varText} insertada`, 'success');
  } else {
    navigator.clipboard?.writeText(varText);
    showFeedback(`Variable ${varText} copiada (selecciona un campo para insertar directamente)`, 'success');
  }
}

function emailCategoryIcon(cat) {
  const icons = { client: '📧', internal: '🔔', contact: '📨' };
  return icons[cat] || '📧';
}

function truncateText(str, len) {
  if (!str) return '';
  return str.length > len ? str.slice(0, len) + '...' : str;
}

async function loadEmailTemplateDetail(key) {
  emailLastFocusedField.value = '';
  emailFieldRefs.value = {};
  emailIsLoadingDetail.value = true;
  try {
    const result = await proposalStore.fetchEmailTemplateDetail(key);
    if (result.success) {
      emailTemplateDetail.value = result.data;
      emailEditIsActive.value = result.data.is_active;
      emailEditFields.value = {};
      for (const field of result.data.editable_fields) {
        emailEditFields.value[field.key] = field.current_value || '';
      }
    }
  } finally {
    emailIsLoadingDetail.value = false;
  }
}

async function selectEmailTemplate(key) {
  if (emailSelectedTemplate.value === key && emailTemplateDetail.value) return;
  emailSelectedTemplate.value = key;
  emailTemplateDetail.value = null;
  await loadEmailTemplateDetail(key);
}

async function handleSaveEmailTemplate(templateKey) {
  isSaving.value = true;
  try {
    const result = await proposalStore.saveEmailTemplate(templateKey, {
      content_overrides: emailEditFields.value,
      is_active: emailEditIsActive.value,
    });
    if (result.success) {
      showFeedback('Plantilla guardada correctamente.', 'success');
      await loadEmailTemplates();
    } else {
      showFeedback('Error al guardar la plantilla.', 'error');
    }
  } finally {
    isSaving.value = false;
  }
}

async function handleEmailPreview(templateKey) {
  emailIsPreviewLoading.value = true;
  try {
    const result = await proposalStore.previewEmailTemplate(templateKey);
    if (result.success) {
      emailPreviewHtml.value = result.data.html_preview;
      emailPreviewSubject.value = result.data.subject;
      emailShowPreview.value = true;
    } else {
      showFeedback('Error al generar la vista previa.', 'error');
    }
  } finally {
    emailIsPreviewLoading.value = false;
  }
}

function handleResetEmailTemplate(templateKey) {
  emailResetTargetKey.value = templateKey;
  emailShowResetConfirm.value = true;
}

async function confirmResetEmailTemplate() {
  isSaving.value = true;
  try {
    const result = await proposalStore.resetEmailTemplate(emailResetTargetKey.value);
    if (result.success) {
      emailShowResetConfirm.value = false;
      showFeedback('Plantilla restaurada a los valores originales.', 'success');
      await loadEmailTemplates();
      if (emailSelectedTemplate.value === emailResetTargetKey.value) {
        await loadEmailTemplateDetail(emailResetTargetKey.value);
      }
    } else {
      showFeedback('Error al restaurar la plantilla.', 'error');
    }
  } finally {
    isSaving.value = false;
  }
}

async function loadEmailTemplates() {
  emailIsLoading.value = true;
  try {
    const result = await proposalStore.fetchEmailTemplates();
    if (result.success) {
      emailTemplates.value = result.data;
    }
  } finally {
    emailIsLoading.value = false;
  }
}

// ── Prompt IA ──
const {
  promptText,
  isEditing: promptIsEditing,
  DEFAULT_PROMPT: promptDefault,
  loadSavedPrompt,
  savePrompt: promptSave,
  resetPrompt: promptReset,
  copyPrompt: promptCopy,
  downloadPrompt: promptDownload,
} = useSellerPrompt();

const promptEditBuffer = ref('');
const promptCopied = ref(false);

function startEditPrompt() {
  promptEditBuffer.value = promptText.value;
  promptIsEditing.value = true;
}

function cancelEditPrompt() {
  promptIsEditing.value = false;
}

function saveEditPrompt() {
  promptSave(promptEditBuffer.value);
  promptIsEditing.value = false;
  showFeedback('Prompt guardado correctamente.', 'success');
}

function handleResetPrompt() {
  promptReset();
  promptIsEditing.value = false;
  showFeedback('Prompt restaurado al valor original.', 'success');
}

async function handleCopyPrompt() {
  await promptCopy();
  promptCopied.value = true;
  setTimeout(() => { promptCopied.value = false; }, 2000);
  showFeedback('Prompt copiado al portapapeles.', 'success');
}

const defaultsPromptSubTab = ref('commercial');

const {
  promptText: technicalDefaultsPromptText,
  isEditing: technicalDefaultsPromptIsEditing,
  DEFAULT_PROMPT: technicalDefaultsPromptDefault,
  loadSavedPrompt: loadTechnicalDefaultsPrompt,
  savePrompt: technicalDefaultsPromptSave,
  resetPrompt: technicalDefaultsPromptReset,
  copyPrompt: technicalDefaultsPromptCopy,
  downloadPrompt: technicalDefaultsPromptDownload,
} = useTechnicalPrompt();

const technicalDefaultsPromptEditBuffer = ref('');
const technicalDefaultsPromptCopied = ref(false);

function startEditTechnicalDefaultsPrompt() {
  technicalDefaultsPromptEditBuffer.value = technicalDefaultsPromptText.value;
  technicalDefaultsPromptIsEditing.value = true;
}
function cancelEditTechnicalDefaultsPrompt() {
  technicalDefaultsPromptIsEditing.value = false;
}
function saveEditTechnicalDefaultsPrompt() {
  technicalDefaultsPromptSave(technicalDefaultsPromptEditBuffer.value);
  technicalDefaultsPromptIsEditing.value = false;
  showFeedback('Prompt técnico guardado correctamente.', 'success');
}
async function handleCopyTechnicalDefaultsPrompt() {
  await technicalDefaultsPromptCopy();
  technicalDefaultsPromptCopied.value = true;
  setTimeout(() => { technicalDefaultsPromptCopied.value = false; }, 2000);
  showFeedback('Prompt técnico copiado al portapapeles.', 'success');
}
function handleResetTechnicalDefaultsPrompt() {
  technicalDefaultsPromptReset();
  technicalDefaultsPromptIsEditing.value = false;
  showFeedback('Prompt técnico restaurado al valor original.', 'success');
}

// ── JSON tab ──
const defaultsJsonLoading = ref(false);
const defaultsJsonCopied = ref(false);
const jsonIsEditing = ref(false);
const jsonEditBuffer = ref('');
const jsonEditError = ref('');

const defaultsJsonString = computed(() => {
  try {
    const payload = {
      language: selectedLang.value,
      general: generalForm.value,
      sections: sections.value,
    };
    return JSON.stringify(payload, null, 2);
  } catch {
    return '{}';
  }
});

function startEditJson() {
  jsonEditBuffer.value = defaultsJsonString.value;
  jsonEditError.value = '';
  jsonIsEditing.value = true;
}

function cancelEditJson() {
  jsonIsEditing.value = false;
  jsonEditError.value = '';
}

async function saveEditJson() {
  jsonEditError.value = '';

  let parsed;
  try {
    parsed = JSON.parse(jsonEditBuffer.value);
  } catch (e) {
    jsonEditError.value = `JSON inválido: ${e.message}`;
    return;
  }

  if (!parsed.sections || !Array.isArray(parsed.sections)) {
    jsonEditError.value = 'El JSON debe contener un array "sections".';
    return;
  }

  const requiredKeys = ['section_type', 'title', 'order', 'content_json'];
  for (let i = 0; i < parsed.sections.length; i++) {
    const section = parsed.sections[i];
    if (typeof section !== 'object' || section === null) {
      jsonEditError.value = `La sección en índice ${i} debe ser un objeto.`;
      return;
    }
    const missing = requiredKeys.filter(k => !(k in section));
    if (missing.length > 0) {
      jsonEditError.value = `La sección en índice ${i} le faltan campos: ${missing.join(', ')}`;
      return;
    }
  }

  const lang = parsed.language || selectedLang.value;

  isSaving.value = true;
  try {
    const result = await proposalStore.saveProposalDefaults(
      lang, parsed.sections, null, configUpdatedAt.value,
    );
    if (result.success) {
      sections.value = parsed.sections;
      if (parsed.general) {
        Object.assign(generalForm.value, parsed.general);
      }
      savedSections.value = new Set();
      await syncConfigVersion(result);
      jsonIsEditing.value = false;
      showFeedback('JSON guardado correctamente.', 'success');
    } else if (result.code === 'stale_defaults') {
      jsonEditError.value = result.message;
      showFeedback(result.message, 'error');
    } else {
      jsonEditError.value = 'Error al guardar. Verifica la estructura del JSON.';
      showFeedback('Error al guardar el JSON.', 'error');
    }
  } finally {
    isSaving.value = false;
  }
}

async function copyDefaultsJson() {
  if (typeof navigator !== 'undefined' && navigator.clipboard) {
    await navigator.clipboard.writeText(defaultsJsonString.value);
    defaultsJsonCopied.value = true;
    setTimeout(() => { defaultsJsonCopied.value = false; }, 2000);
    showFeedback('JSON copiado al portapapeles.', 'success');
  }
}

function downloadDefaultsJson() {
  const blob = new Blob([defaultsJsonString.value], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `defaults-${selectedLang.value}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function refreshData() {
  isRefreshing.value = true;
  try {
    await loadDefaults(selectedLang.value);
    await loadEmailTemplates();
  } finally {
    isRefreshing.value = false;
  }
}

onMounted(() => {
  loadDefaults(selectedLang.value);
  loadEmailTemplates();
  loadSavedPrompt();
  loadTechnicalDefaultsPrompt();
});

usePanelRefresh(refreshData);
</script>

<style scoped>
.defaults-technical-editor :deep(.technical-document-editor textarea) {
  min-height: 5.5rem;
}
</style>
