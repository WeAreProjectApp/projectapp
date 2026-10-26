<template>
  <div class="max-w-4xl mx-auto space-y-8">

    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
      <div>
        <h1 class="text-2xl font-light text-text-default">Emails</h1>
        <p class="text-sm text-text-muted mt-1">Envía correos con el branding de la marca a cualquier destinatario.</p>
      </div>
    </div>

    <!-- ── Page tabs ── -->
    <BaseTabs v-model="activeTab" :tabs="PAGE_TABS" variant="underline" />

    <!-- ── Email composer ── -->
    <section v-if="activeTab === 'compose'" class="rounded-xl border border-border-muted bg-surface p-4 sm:p-5">
      <div class="flex items-center gap-2 mb-5">
        <svg class="w-5 h-5 text-text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
        <h3 class="text-sm font-semibold text-text-default">Correo general con branding</h3>
      </div>

      <!-- Sub-tab switcher -->
      <div class="flex gap-4 border-b border-border-muted  mb-5">
        <button type="button"
          class="pb-2 text-sm transition-colors border-b-2"
          :class="activeSubTab === 'edit'
            ? 'border-emerald-600 text-text-brand  font-semibold'
            : 'border-transparent text-text-muted hover:text-text-default'"
          @click="activeSubTab = 'edit'">
          Editar
        </button>
        <button type="button"
          class="pb-2 text-sm transition-colors border-b-2"
          :class="activeSubTab === 'preview'
            ? 'border-emerald-600 text-text-brand  font-semibold'
            : 'border-transparent text-text-muted hover:text-text-default'"
          @click="activeSubTab = 'preview'">
          Vista previa
        </button>
      </div>

      <!-- ── Edit sub-tab ── -->
      <div v-if="activeSubTab === 'edit'" class="space-y-4">
        <EmailRecipientFields
          v-model:toRecipients="toRecipients"
          v-model:ccRecipients="ccRecipients"
          test-id-prefix="standalone-email"
        />

        <!-- Subject -->
        <div>
          <label class="block text-xs text-text-muted mb-1">Asunto</label>
          <input v-model="subject" type="text" placeholder="Asunto del correo"
            class="w-full px-3 py-2 border border-border-default rounded-lg text-sm bg-surface focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring" />
        </div>

        <!-- Greeting -->
        <div>
          <label class="block text-xs text-text-muted mb-1">Saludo</label>
          <input v-model="greeting" type="text" placeholder="Hola"
            class="w-full px-3 py-2 border border-border-default rounded-lg text-sm bg-surface focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring" />
        </div>

        <!-- Sections (draggable) -->
        <div>
          <label class="block text-xs text-text-muted mb-2">Secciones del correo</label>
          <draggable v-model="sections" item-key="id" handle=".drag-handle" ghost-class="opacity-30"
            class="space-y-3">
            <template #item="{ element: section, index: idx }">
              <div class="bg-surface-muted  rounded-lg p-3 border border-border-muted ">
                <div class="mb-2 flex flex-wrap items-center gap-2">
                  <span class="drag-handle cursor-grab text-text-subtle hover:text-text-muted select-none text-sm">⠿</span>
                  <span class="text-[10px] text-text-muted uppercase tracking-wide">Sección {{ idx + 1 }}</span>

                  <BaseButton v-if="sections.length > 1" variant="danger-ghost" icon-only size="sm" aria-label="Eliminar" title="Eliminar" @click="removeSection(idx)">
                    <BaseActionIcon action="delete" />
                  </BaseButton>
                </div>
                <BaseRichTextEditor v-model="section.text" :format="section.markdown ? 'markdown_html_v1' : 'plain'" @update:format="section.markdown = true" rows="3" placeholder="Escribe el contenido de esta sección..."
                  class="w-full px-3 py-2 border border-border-default rounded-lg text-sm bg-surface  focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring resize-none"  />

              </div>
            </template>
          </draggable>
          <BaseButton variant="secondary" size="sm" class="mt-3" @click="addSection">
            <BaseActionIcon action="create" />
            Agregar sección
          </BaseButton>
        </div>

        <!-- Footer -->
        <div>
          <label class="block text-xs text-text-muted mb-1">Pie de correo</label>
          <BaseRichTextEditor v-model="footer" :format="textFormats['/footer'] || 'plain'" @update:format="textFormats['/footer'] = $event" rows="2" placeholder="Texto de cierre..."
            class="w-full px-3 py-2 border border-border-default rounded-lg text-sm bg-surface focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring resize-none"  />
        </div>

        <!-- Attachments -->
        <div>
          <label class="block text-xs text-text-muted mb-1">Adjuntos</label>
          <input ref="fileInput" type="file" multiple
            accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg"
            class="max-w-full text-xs file:mr-2 file:rounded-lg file:border-0 file:bg-primary-soft file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-text-brand hover:file:bg-primary-soft"
            @change="handleFilesChange" />
          <div v-if="attachments.length" class="mt-2 space-y-1">
            <div v-for="(file, idx) in attachments" :key="idx"
              class="flex min-w-0 items-center justify-between gap-2 rounded-lg bg-surface-muted px-3 py-1.5">
              <span class="min-w-0 truncate text-xs text-text-default">{{ file.name }}</span>
              <BaseButton variant="danger-ghost" icon-only size="sm" aria-label="Eliminar" title="Eliminar" @click="removeAttachment(idx)">
                <BaseActionIcon action="delete" />
              </BaseButton>
            </div>
          </div>
        </div>

        <!-- Send button -->
        <div class="flex flex-col items-stretch gap-3 pt-2 panel-portrait:flex-row panel-portrait:items-center panel-portrait:justify-between">
          <p v-if="sendError" class="min-w-0 max-w-full text-xs text-danger-strong [overflow-wrap:anywhere]">{{ sendError }}</p>
          <span v-else />
          <BaseButton variant="primary" size="sm" class="panel-portrait:ml-auto" :disabled="!canSend" :loading="sending" @click="handleSend">
            <BaseActionIcon v-if="!sending" action="send" />
            {{ sending ? 'Enviando...' : 'Enviar correo' }}
          </BaseButton>
        </div>
      </div>

      <!-- ── Preview sub-tab ── -->
      <div v-else>
        <div class="mb-3 space-y-1 rounded-lg bg-surface-muted px-3 py-2 text-xs text-text-muted">
          <p><span class="font-medium text-text-default">Para:</span> {{ recipientSummary(toRecipients) || '—' }}</p>
          <p v-if="ccRecipients.length"><span class="font-medium text-text-default">CC:</span> {{ recipientSummary(ccRecipients) }}</p>
        </div>
        <!-- Subject badge -->
        <div class="mb-4 flex min-w-0 flex-col gap-1 rounded-lg bg-surface-muted px-3 py-2 text-xs text-text-muted panel-portrait:flex-row panel-portrait:items-center panel-portrait:gap-2">
          <span class="font-medium text-text-default">Asunto:</span>
          <span class="min-w-0 max-w-full [overflow-wrap:anywhere]">{{ subject || '(sin asunto)' }}</span>
        </div>

        <!-- Server-rendered preview: the real branded template (emails/branded_email.html) -->
        <ComposedEmailPreview
          :subject="subject"
          :greeting="greeting"
          :sections="sections"
          :footer="footer"
          :textFormats="textFormats"
          :attachment-names="attachments.map(f => f.name)"
        />
      </div>
    </section>

    <!-- ── Defaults config ── -->
    <section v-else-if="activeTab === 'defaults'" class="rounded-xl border border-border-muted bg-surface p-4 sm:p-5">
      <div class="flex items-center gap-2 mb-2">
        <svg class="w-5 h-5 text-text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        <h3 class="text-sm font-semibold text-text-default">Configuración de emails</h3>
      </div>
      <p class="text-xs text-text-muted mb-5">
        Administra los valores de redacción y las copias internas de todas las salidas de correo de la plataforma.
      </p>

      <div v-if="emailStore.isLoadingDefaults" class="text-xs text-text-subtle py-4 text-center">Cargando valores...</div>

      <div v-else class="space-y-4 max-w-xl">
        <h4 class="text-sm font-semibold text-text-default">Valores por defecto</h4>
        <UnsavedChangesNotice
          v-if="hasChanges"
          :title="unsavedTitle"
          :detail="unsavedDetail"
          :can-save="canSaveNow"
          :saving="emailStore.isSavingDefaults"
          testid="emails-defaults-unsaved-notice"
          @save="handleSaveDefaults"
          @discard="discardChanges"
        />

        <div>
          <label class="block text-xs text-text-muted mb-1">Saludo por defecto</label>
          <BaseInput v-model="cfgGreeting" placeholder="Hola {client_name}" />
          <p v-if="availableVariables.length" class="mt-1 text-[11px] text-text-muted">
            Variables disponibles: <span class="font-mono">{{ variablesHint }}</span>
          </p>
        </div>

        <div>
          <label class="block text-xs text-text-muted mb-1">Pie de correo por defecto</label>
          <BaseRichTextEditor v-model="cfgFooter" profile="email" :format="cfgTextFormats['/footer'] || 'plain'" @update:format="cfgTextFormats['/footer'] = $event" :rows="3" placeholder="Texto de cierre..."  />
        </div>

        <div>
          <label class="block text-xs text-text-muted mb-1">Firmante por defecto</label>
          <BaseSelect v-model="cfgSigner" :options="signerOptions" placeholder="Selecciona un firmante" />
          <p class="mt-1 text-[11px] text-text-muted">La firma aparece al final del correo con nombre y cargo.</p>
        </div>

        <div class="flex flex-col sm:flex-row sm:items-center gap-2 pt-2">
          <BaseButton size="sm" :disabled="emailStore.isSavingDefaults" @click="handleSaveDefaults">
            {{ emailStore.isSavingDefaults ? 'Guardando...' : 'Guardar valores' }}
          </BaseButton>
          <BaseButton size="sm" variant="ghost" :disabled="emailStore.isSavingDefaults" @click="handleRestoreDefaults">
            Restaurar valores originales
          </BaseButton>
        </div>
      </div>

      <ClientEmailCopySettings class="mt-8" />
    </section>

    <!-- ── History ── -->
    <section v-else class="rounded-xl border border-border-muted bg-surface p-4 sm:p-5">
      <div class="flex items-center gap-2 mb-4">
        <svg class="w-5 h-5 text-info-strong" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <h3 class="text-sm font-semibold text-text-default">Historial de correos enviados</h3>
      </div>

      <form class="mb-4 grid gap-3 rounded-lg border border-border-muted bg-surface-muted p-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7" data-testid="email-history-filters" @submit.prevent="applyHistoryFilters">
        <BaseInput v-model="historyFilters.recipient" type="search" placeholder="Buscar destinatario" aria-label="Buscar destinatario" />
        <BaseSelect v-model="historyFilters.family" :options="familyFilterOptions" aria-label="Filtrar por familia" />
        <BaseSelect v-model="historyFilters.status" :options="statusFilterOptions" aria-label="Filtrar por estado" />
        <BaseSelect v-model="historyFilters.has_attachments" :options="attachmentPresenceOptions" aria-label="Filtrar por presencia de adjuntos" />
        <BaseSelect v-model="historyFilters.attachment_type" :options="attachmentTypeFilterOptions" aria-label="Filtrar por tipo de adjunto" />
        <BaseInput v-model="historyFilters.date_from" type="date" aria-label="Fecha inicial" />
        <BaseInput v-model="historyFilters.date_to" type="date" aria-label="Fecha final" />
        <div class="flex flex-wrap gap-2 sm:col-span-2 lg:col-span-4 xl:col-span-7 xl:justify-end">
          <BaseButton type="button" variant="ghost" size="sm" @click="clearHistoryFilters">Limpiar</BaseButton>
          <BaseButton type="submit" variant="secondary" size="sm">Aplicar filtros</BaseButton>
        </div>
      </form>

      <div v-if="emailStore.isLoadingHistory" class="text-xs text-text-subtle py-4 text-center">Cargando historial...</div>

      <div v-else-if="!emailStore.history.length" class="text-xs text-text-subtle py-4 text-center">
        No se han enviado correos aún.
      </div>

      <div v-else class="space-y-2">
        <div v-for="entry in emailStore.history" :key="entry.id"
          :data-testid="`email-history-record-${entry.id}`"
          class="border border-border-muted  rounded-lg overflow-hidden">
          <!-- Summary row -->
          <button type="button" @click="toggleExpand(entry.id)"
            class="flex w-full min-w-0 items-center gap-3 px-3 py-3 text-left transition-colors hover:bg-surface-muted sm:px-4">
            <div class="flex-1 min-w-0">
              <div class="flex min-w-0 flex-wrap items-center gap-2">
                <span class="min-w-0 max-w-full text-xs font-medium text-text-default [overflow-wrap:anywhere]">{{ entry.subject }}</span>
                <span class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium"
                  :class="{
                    'bg-primary-soft text-text-brand ': entry.status === 'sent' || entry.status === 'delivered',
                    'bg-danger-soft text-danger-strong': entry.status === 'failed' || entry.status === 'bounced',
                  }">
                  {{ statusLabel(entry.status) }}
                </span>
                <span class="shrink-0 rounded bg-surface-raised px-1.5 py-0.5 text-[10px] text-text-muted">{{ entry.family_label }}</span>
              </div>
              <div class="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5">
                <span class="break-all text-[11px] text-text-muted">Para: {{ historyRecipientSummary(entry.to_recipients, entry.recipient) }}</span>
                <span v-if="entry.cc_recipients?.length" class="break-all text-[11px] text-text-muted">CC: {{ historyRecipientSummary(entry.cc_recipients) }}</span>
                <span class="text-[10px] text-text-subtle">{{ entry.template_label }}</span>
                <span class="text-[10px] text-text-subtle">{{ entry.audience_label }}</span>
                <span class="text-[10px] text-text-subtle">{{ formatDate(entry.sent_at) }}</span>
              </div>
            </div>
            <BaseActionIcon :action="expandedIds[entry.id] ? 'collapse' : 'expand'" />
          </button>

          <!-- Expanded detail -->
          <div v-if="expandedIds[entry.id]" class="border-t border-border-muted  px-4 py-3 bg-surface-muted  space-y-3">
            <div class="flex flex-wrap justify-end gap-2">
              <BaseButton v-if="entry.has_body" variant="secondary" size="sm" :data-testid="`email-history-view-body-${entry.id}`" @click="openEmailBody(entry)">
                Ver contenido completo
              </BaseButton>
              <BaseButton
                v-if="entry.can_resend"
                variant="secondary"
                size="sm"
                :data-testid="`email-history-resend-${entry.id}`"
                @click="openResend(entry)"
              >
                Reenviar exacto
              </BaseButton>
            </div>
            <div v-if="entry.to_recipients?.length || entry.cc_recipients?.length">
              <p class="mb-1 text-[10px] uppercase tracking-wide text-text-subtle">Destinatarios</p>
              <div class="space-y-1">
                <div
                  v-for="recipientEntry in [...(entry.to_recipients || []), ...(entry.cc_recipients || [])]"
                  :key="`${recipientEntry.email}-${entry.id}`"
                  class="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border-muted bg-surface px-3 py-2"
                >
                  <span class="break-all text-xs text-text-default">
                    {{ entry.cc_recipients?.includes(recipientEntry) ? 'CC' : 'Para' }} · {{ recipientEntry.email }}
                  </span>
                  <span class="text-[10px] font-medium" :class="copyStatusClass(recipientEntry.status)">
                    {{ statusLabel(recipientEntry.status) }}
                  </span>
                </div>
              </div>
            </div>
            <div v-if="entry.metadata?.greeting">
              <p class="text-[10px] text-text-subtle uppercase tracking-wide mb-0.5">Saludo</p>
              <p class="text-xs text-text-default">{{ entry.metadata.greeting }}</p>
            </div>
            <div v-if="entry.metadata?.sections?.length">
              <p class="text-[10px] text-text-subtle uppercase tracking-wide mb-1">Secciones</p>
              <div v-for="(section, idx) in entry.metadata.sections" :key="idx"
                class="bg-surface rounded-lg px-3 py-2 mb-1.5 border border-border-muted ">
                <span v-if="sectionIsMarkdown(section)"
                  class="inline-block mb-1 px-1.5 py-0.5 bg-primary-soft text-text-brand rounded text-[9px] font-medium uppercase tracking-wide">MD</span>
                <p class="min-w-0 max-w-full whitespace-pre-wrap text-xs text-text-default [overflow-wrap:anywhere]">{{ sectionText(section) }}</p>
              </div>
            </div>
            <div v-if="entry.metadata?.footer">
              <p class="text-[10px] text-text-subtle uppercase tracking-wide mb-0.5">Pie de correo</p>
              <p class="text-xs text-text-default">{{ entry.metadata.footer }}</p>
            </div>
            <div :data-testid="`email-history-attachments-${entry.id}`">
              <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p class="text-[10px] uppercase tracking-wide text-text-subtle">Adjuntos</p>
                <p v-if="entry.message_size_bytes !== null" class="text-[11px] text-text-subtle">
                  Envío total: <strong class="text-text-default">{{ formatBytes(entry.message_size_bytes) }}</strong>
                  <span v-if="entry.attachment_count"> · adjuntos {{ formatBytes(entry.attachment_size_bytes) }}</span>
                </p>
              </div>

              <BaseAlert
                v-if="entry.snapshot_state !== 'captured'"
                variant="warning"
                title="Información histórica incompleta"
                class="mb-2"
                :data-testid="`email-history-legacy-${entry.id}`"
              >
                {{ entry.snapshot_notice }}
              </BaseAlert>
              <p
                v-else-if="entry.has_attachments === false"
                class="rounded-lg border border-border-muted bg-surface px-3 py-2 text-xs text-text-muted"
                :data-testid="`email-history-no-attachments-${entry.id}`"
              >
                Este correo no llevaba adjuntos.
              </p>

              <div v-if="entry.attachments?.length" class="grid gap-2 sm:grid-cols-2">
                <article
                  v-for="attachment in entry.attachments"
                  :key="attachment.id || attachment.filename"
                  class="min-w-0 rounded-lg border border-border-muted bg-surface px-3 py-2"
                  :data-testid="attachment.id ? `email-attachment-${attachment.id}` : undefined"
                >
                  <p class="break-words text-xs font-medium text-text-default">{{ attachment.filename }}</p>
                  <p class="mt-1 text-[10px] text-text-subtle">
                    {{ attachment.business_kind_label || attachment.format_label }}
                    <template v-if="attachment.business_kind_label && attachment.format_label"> · {{ attachment.format_label }}</template>
                    <template v-if="attachment.size_bytes !== null"> · {{ formatBytes(attachment.size_bytes) }}</template>
                  </p>
                  <NuxtLink
                    v-if="attachment.source_document"
                    :to="localePath(`/panel/documents/${attachment.source_document.id}/edit`)"
                    class="mt-1 block break-words text-[11px] font-medium text-text-brand hover:underline"
                  >
                    {{ attachment.source_document.title }}
                  </NuxtLink>
                  <div v-if="attachment.exact_available" class="mt-2 flex flex-wrap gap-2">
                    <BaseButton
                      v-if="attachment.preview_url"
                      variant="ghost"
                      size="sm"
                      @click="openPdfPreview(attachment)"
                    >
                      Previsualizar
                    </BaseButton>
                    <a
                      :href="attachment.download_url"
                      class="inline-flex min-h-9 items-center rounded-lg px-3 text-xs font-medium text-text-brand hover:bg-surface-muted"
                      download
                    >
                      Descargar
                    </a>
                  </div>
                </article>
              </div>
            </div>

            <div v-if="hasLinks(entry)" :data-testid="`email-history-links-${entry.id}`">
              <p class="mb-1 text-[10px] uppercase tracking-wide text-text-subtle">Enlaces enviados</p>
              <div class="grid gap-2 sm:grid-cols-2">
                <div v-for="group in linkGroups(entry)" :key="group.key" class="rounded-lg border border-border-muted bg-surface px-3 py-2">
                  <p class="text-[10px] font-medium uppercase tracking-wide text-text-subtle">{{ group.label }}</p>
                  <a
                    v-for="link in group.links"
                    :key="link.url"
                    :href="link.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="mt-1 block break-all text-xs text-text-brand hover:underline"
                  >
                    {{ link.label || link.url }}
                  </a>
                </div>
              </div>
            </div>
            <div v-if="entry.copies?.length" :data-testid="`email-copy-list-${entry.id}`">
              <p class="text-[10px] text-text-subtle uppercase tracking-wide mb-1">Copias internas (BCC)</p>
              <div class="space-y-1.5">
                <div
                  v-for="copy in entry.copies"
                  :key="copy.id"
                  class="rounded-lg border border-border-muted bg-surface px-3 py-2"
                >
                  <div class="flex flex-wrap items-center justify-between gap-2">
                    <span class="break-all text-xs text-text-default">{{ copy.recipient }}</span>
                    <span class="text-[10px] font-medium" :class="copyStatusClass(copy.status)">
                      {{ statusLabel(copy.status) }}
                    </span>
                  </div>
                  <p v-if="copy.error_message" class="mt-1 min-w-0 max-w-full text-[10px] [overflow-wrap:anywhere]" :class="copy.status === 'skipped' ? 'text-warning-strong' : 'text-danger-strong'">{{ copy.error_message }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Load more -->
        <div v-if="emailStore.historyPagination.has_next" class="pt-3 text-center">
          <BaseButton variant="secondary" size="sm" :disabled="emailStore.isLoadingHistory" @click="loadMore">
            {{ emailStore.isLoadingHistory ? 'Cargando...' : 'Cargar más' }}
          </BaseButton>
        </div>
      </div>
    </section>

    <ConfirmModal
      v-model="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :variant="confirmState.variant"
      :require-type-text="confirmState.requireTypeText"
      :hide-cancel="confirmState.hideCancel"
      :secondary-text="confirmState.secondaryText"
      :secondary-variant="confirmState.secondaryVariant"
      :secondary-hint="confirmState.secondaryHint"
      :loading="confirmState.busy"
      @confirm="handleConfirmed"
      @secondary="handleSecondaryAction"
      @cancel="handleCancelled"
    />
    <EmailBodyModal
      :open="Boolean(selectedBodyEntry)"
      :entry="selectedBodyEntry"
      :fetcher="fetchEmailBody"
      @close="selectedBodyEntry = null"
    />
    <PdfPreviewModal
      :model-value="Boolean(selectedPdfAttachment)"
      :src="selectedPdfAttachment?.preview_url || ''"
      :title="selectedPdfAttachment?.filename || 'Vista previa del adjunto'"
      description="Archivo exacto conservado en el historial del correo."
      test-id-prefix="email-pdf-preview"
      @update:model-value="value => { if (!value) selectedPdfAttachment = null; }"
    />
    <EmailResendModal
      :open="Boolean(selectedResendEntry)"
      :entry="selectedResendEntry"
      @close="selectedResendEntry = null"
      @resent="handleResent"
    />
  </div>
</template>

<script setup>
import { useRadarFocus } from '~/composables/useRadarFocus';
import { useDashboardAttentionText } from '~/composables/useDashboardAttentionText';
import { ref, computed, watch, onMounted } from 'vue';
import draggable from 'vuedraggable';
import ComposedEmailPreview from '~/components/ComposedEmailPreview.vue';
import ClientEmailCopySettings from '~/components/emails/ClientEmailCopySettings.vue';
import EmailRecipientFields from '~/components/emails/EmailRecipientFields.vue';
import EmailBodyModal from '~/components/accounting/EmailBodyModal.vue';
import EmailResendModal from '~/components/emails/EmailResendModal.vue';
import PdfPreviewModal from '~/components/base/PdfPreviewModal.vue';
import { useEmailStore } from '~/stores/emails';
import { validateEmailAttachments } from '~/utils/emailAttachments';
import { vAutoResize } from '~/utils/autoResizeDirective';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { useUnsavedGuard } from '~/composables/useUnsavedGuard';
import UnsavedChangesNotice from '~/components/panel/UnsavedChangesNotice.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { formatDateTime } from '~/utils/formatDate';
import { appendEmailRecipients, recipientSummary } from '~/utils/emailRecipients';

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const emailStore = useEmailStore();
const notify = usePanelNotify();
const localePath = useLocalePath();
const route = useRoute();
const radarFocus = useRadarFocus();
const radarText = useDashboardAttentionText();
const router = useRouter();

// ── Page tabs (synced to ?tab= for deep-linking) ──
const PAGE_TABS = [
  { id: 'compose', label: 'Redactar' },
  { id: 'history', label: 'Historial' },
  { id: 'defaults', label: 'Configuración' },
];
const TAB_IDS = PAGE_TABS.map(t => t.id);
const activeTab = ref(
  route.query.email
    ? 'history'
    : (TAB_IDS.includes(route.query.tab) ? route.query.tab : 'compose'),
);
watch(activeTab, (tab) => {
  // El default no se escribe: la URL limpia es la vista de reposo, y un
  // `?tab=compose` colgado es estado que el usuario no puede ver ni corregir.
  const query = { ...route.query };
  if (tab === 'compose') delete query.tab;
  else query.tab = tab;
  router.replace({ query });
});

let sectionIdSeq = 0;
const nextSectionId = () => ++sectionIdSeq;

// ── Defaults (declared early so resetForm can reference them) ──
const defaultGreeting = ref('Hola');
const defaultFooter = ref('Quedamos atentos a tus comentarios.\nUn abrazo, el equipo de Project App.');

// ── Composer state ──
const activeSubTab = ref('edit');
const toRecipients = ref([]);
const ccRecipients = ref([]);
const subject = ref('');
const greeting = ref(defaultGreeting.value);
const sections = ref([{ id: nextSectionId(), text: '', markdown: false }]);
const footer = ref(defaultFooter.value);
const textFormats = ref({});
const attachments = ref([]);
const fileInput = ref(null);
const sending = ref(false);
const sendError = ref('');

// ── History state ──
const expandedIds = ref({});
const selectedBodyEntry = ref(null);
const selectedPdfAttachment = ref(null);
const selectedResendEntry = ref(null);
const historyFilters = ref({
  recipient: '',
  family: '',
  status: '',
  has_attachments: '',
  attachment_type: '',
  date_from: '',
  date_to: '',
  email_id: route.query.email || '',
});
const familyFilterOptions = computed(() => [
  { value: '', label: 'Todas las familias' },
  ...emailStore.copyFamilies,
]);
const statusFilterOptions = [
  { value: '', label: 'Todos los estados' },
  { value: 'sent', label: 'Enviado' },
  { value: 'delivered', label: 'Entregado' },
  { value: 'bounced', label: 'Rebotado' },
  { value: 'failed', label: 'Fallido' },
];
const attachmentPresenceOptions = [
  { value: '', label: 'Con o sin adjuntos' },
  { value: 'true', label: 'Con adjuntos' },
  { value: 'false', label: 'Sin adjuntos confirmados' },
];
const attachmentTypeFilterOptions = computed(() => [
  { value: '', label: 'Todos los tipos' },
  ...emailStore.attachmentTypeOptions.map(option => ({
    value: option.value,
    label: `${option.group === 'format' ? 'Formato' : 'Documento'} · ${option.label}`,
  })),
]);

// ── Sections ──
function addSection() {
  sections.value.push({ id: nextSectionId(), text: '', markdown: false });
}

function removeSection(idx) {
  if (sections.value.length > 1) {
    sections.value.splice(idx, 1);
  }
}

function handleFilesChange(e) {
  const { validFiles, errors } = validateEmailAttachments(Array.from(e.target.files || []));
  sendError.value = errors.length ? errors.join(', ') : '';
  if (validFiles.length) attachments.value.push(...validFiles);
  if (fileInput.value) fileInput.value.value = '';
}

function removeAttachment(idx) {
  attachments.value.splice(idx, 1);
}

// ── Validation ──
const canSend = computed(() => {
  if (!toRecipients.value.length) return false;
  if (!subject.value.trim()) return false;
  if (!sections.value.some(s => s.text.trim())) return false;
  return true;
});

// ── Send ──
async function handleSend() {
  sending.value = true;
  sendError.value = '';

  const formData = new FormData();
  appendEmailRecipients(formData, toRecipients.value, ccRecipients.value);
  formData.append('subject', subject.value.trim());
  formData.append('greeting', greeting.value.trim());
  formData.append('sections', JSON.stringify(
    sections.value.filter(s => s.text.trim()).map(s => ({ text: s.text, markdown: !!s.markdown })),
  ));
  formData.append('footer', footer.value.trim());
  formData.append('text_formats', JSON.stringify(textFormats.value));
  for (const file of attachments.value) {
    formData.append('attachments', file);
  }

  const result = await emailStore.sendEmail(formData);
  sending.value = false;

  if (result.success) {
    notify.success({ title: 'Correo enviado correctamente.' });
    resetForm();
    await emailStore.fetchHistory(1);
  } else {
    sendError.value = result.error || 'Error al enviar el correo. Intenta de nuevo.';
    notify.error({ title: 'No se pudo enviar el correo', detail: sendError.value });
  }
}

function resetForm() {
  toRecipients.value = [];
  ccRecipients.value = [];
  subject.value = '';
  greeting.value = defaultGreeting.value;
  footer.value = defaultFooter.value;
  sections.value = [{ id: nextSectionId(), text: '', markdown: false }];
  attachments.value = [];
  if (fileInput.value) fileInput.value.value = '';
}

// ── Defaults config form ──
const cfgGreeting = ref('');
const cfgFooter = ref('');
const cfgTextFormats = ref({});
const cfgSigner = ref('');

/**
 * Sólo los valores por defecto: son los que tienen "Guardar valores".
 *
 * El borrador de la pestaña Redactar (destinatario, asunto, secciones,
 * adjuntos) también se pierde al salir, pero ese no se guarda: se envía. Es
 * "sin enviar", no "sin guardar", y mezclarlos confundiría las dos cosas.
 * Queda anotado como pendiente aparte.
 */
const {
  hasChanges,
  unsavedTitle,
  unsavedDetail,
  canSaveNow,
  commit: commitBaseline,
  discardChanges,
  confirmState,
  handleConfirmed,
  handleSecondaryAction,
  handleCancelled,
} = useUnsavedGuard({
  snapshot: () => ({
    greeting: cfgGreeting.value,
    footer: cfgFooter.value,
    text_formats: { ...cfgTextFormats.value },
    signer: cfgSigner.value,
  }),
  labels: { greeting: 'saludo', footer: 'cierre', signer: 'firmante' },
  save: handleSaveDefaults,
  reload: loadDefaults,
});

const availableVariables = computed(() => emailStore.defaults?.available_variables || []);
// Built in script: the literal "}}" inside a template interpolation would
// close the interpolation early and break the SFC compiler.
const variablesHint = computed(() =>
  availableVariables.value.map(v => '{' + v + '}').join(', '),
);
const signerOptions = computed(() =>
  (emailStore.defaults?.available_signers || []).map(s => ({
    value: s.key,
    label: `${s.name} — ${s.role}`,
  })),
);

/**
 * Apply a defaults payload: update the composer seeds (only overwriting
 * composer fields the user hasn't touched) and the config form values.
 */
function applyDefaults(data) {
  const prevGreeting = defaultGreeting.value;
  const prevFooter = defaultFooter.value;
  if (data.greeting) defaultGreeting.value = data.greeting;
  if (data.footer) defaultFooter.value = data.footer;
  if (greeting.value === prevGreeting) greeting.value = defaultGreeting.value;
  if (footer.value === prevFooter) footer.value = defaultFooter.value;

  const cfg = data.config || {};
  cfgGreeting.value = cfg.greeting || '';
  cfgFooter.value = cfg.footer || '';
  cfgTextFormats.value = { ...cfg.text_formats };
  if (footer.value === defaultFooter.value) textFormats.value = { ...cfgTextFormats.value };
  cfgSigner.value = cfg.signer || '';
  // Único punto de hidratación de los valores por defecto: sirve para la carga
  // y para el eco posterior a guardar.
  commitBaseline();
}

async function loadDefaults() {
  const result = await emailStore.fetchDefaults();
  if (result.success && result.data) {
    applyDefaults(result.data);
  }
}

async function handleSaveDefaults() {
  const result = await emailStore.saveDefaults({
    greeting: cfgGreeting.value.trim(),
    footer: cfgFooter.value.trim(),
    text_formats: { ...cfgTextFormats.value },
    signer: cfgSigner.value,
  });
  if (result.success && result.data) {
    // applyDefaults re-fija la baseline con el eco del servidor.
    applyDefaults(result.data);
    notify.success({ title: 'Valores por defecto guardados' });
    return true;
  }
  notify.error({
    title: 'No se pudieron guardar los valores por defecto',
    detail: result.error || 'Intenta de nuevo.',
  });
  // Sin re-baseline: un guardado fallido deja el aviso puesto.
  return false;
}

async function handleRestoreDefaults() {
  const originals = emailStore.defaults?.defaults || {};
  cfgGreeting.value = originals.greeting || '';
  cfgFooter.value = originals.footer || '';
  cfgTextFormats.value = {};
  cfgSigner.value = originals.signer || '';
  await handleSaveDefaults();
}

// ── History helpers ──
async function loadMore() {
  const nextPage = emailStore.historyPagination.page + 1;
  await emailStore.fetchHistory(nextPage);
}

async function applyHistoryFilters() {
  expandedIds.value = {};
  await emailStore.fetchHistory(1, historyFilters.value);
}

async function clearHistoryFilters() {
  historyFilters.value = {
    recipient: '',
    family: '',
    status: '',
    has_attachments: '',
    attachment_type: '',
    date_from: '',
    date_to: '',
    email_id: '',
  };
  const query = { ...route.query };
  delete query.email;
  await router.replace({ query });
  await applyHistoryFilters();
}

function openEmailBody(entry) {
  selectedBodyEntry.value = entry;
}

function openPdfPreview(attachment) {
  selectedPdfAttachment.value = attachment;
}

function openResend(entry) {
  selectedResendEntry.value = entry;
}

async function handleResent(result) {
  selectedResendEntry.value = null;
  notify.success({
    title: 'Correo reenviado correctamente',
    detail: result.copy_notice,
  });
  await emailStore.fetchHistory(1, historyFilters.value);
}

function fetchEmailBody(logId) {
  return emailStore.fetchEmailBody(logId);
}

function toggleExpand(id) {
  if (expandedIds.value[id]) {
    delete expandedIds.value[id];
  } else {
    expandedIds.value[id] = true;
  }
}

// History metadata stores legacy plain strings and new {text, markdown} dicts.
function sectionText(section) {
  return typeof section === 'string' ? section : (section?.text || '');
}

function sectionIsMarkdown(section) {
  return typeof section === 'object' && !!section?.markdown;
}

const STATUS_LABELS = { sent: 'Enviado', delivered: 'Entregado', bounced: 'Rebotado', failed: 'Fallido', skipped: 'Omitida' };
function statusLabel(s) {
  return STATUS_LABELS[s] || s;
}

function copyStatusClass(status) {
  if (status === 'failed' || status === 'bounced') return 'text-danger-strong';
  if (status === 'skipped') return 'text-warning-strong';
  return 'text-success-strong';
}

function historyRecipientSummary(recipients, fallback = '') {
  return recipientSummary(recipients?.length ? recipients : [fallback]);
}

function formatBytes(value) {
  if (value === null || value === undefined) return 'No archivado';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function hasLinks(entry) {
  return Boolean(entry.links?.content?.length || entry.links?.template?.length);
}

function linkGroups(entry) {
  return [
    { key: 'content', label: 'Contenido', links: entry.links?.content || [] },
    { key: 'template', label: 'Plantilla y firma', links: entry.links?.template || [] },
  ].filter(group => group.links.length);
}

function formatDate(isoString) {
  return formatDateTime(isoString, { fallback: '' });
}

async function refreshEmails() {
  await Promise.all([
    loadDefaults(),
    emailStore.fetchCopyRecipients(),
    emailStore.fetchHistory(1, historyFilters.value),
  ]);
  const emailId = Number(route.query.email);
  if (emailId) {
    // The history groups To/CC siblings; the requested log can be a CC bounce.
    const entry = emailStore.history[0];
    if (entry) {
      expandedIds.value[entry.id] = true;
      await radarFocus(`[data-testid="email-history-record-${entry.id}"]`);
    } else if (!emailStore.error) {
      notify.error({ title: radarText.value.missing });
    }
  }
}

watch(() => route.query.email, (email) => {
  if (email) {
    activeTab.value = 'history';
    historyFilters.value = { recipient: '', family: '', status: '', has_attachments: '', attachment_type: '', date_from: '', date_to: '', email_id: email };
    refreshEmails();
  }
});
onMounted(refreshEmails);
usePanelRefresh(refreshEmails);
</script>
