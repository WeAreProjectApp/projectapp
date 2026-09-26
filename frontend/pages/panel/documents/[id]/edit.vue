<template>
  <div class="w-full">
    <header
      class="mb-6 grid grid-cols-1 gap-4 panel-landscape:grid-cols-[minmax(0,1fr)_auto] panel-landscape:items-end"
      data-testid="doc-editor-header"
    >
      <div class="min-w-0">
        <NuxtLink
          :to="returnTarget"
          class="inline-flex items-center gap-1 text-sm text-text-muted hover:text-text-default transition-colors"
          :aria-label="returnLabel"
        >
          <BaseActionIcon action="back" />
          {{ returnLabel }}
        </NuxtLink>
        <p v-if="documentStore.currentDocument" class="mt-2 text-xs tabular-nums text-text-muted" data-testid="document-detail-id">#{{ documentStore.currentDocument.id }}</p>
        <h1
          class="mt-2 line-clamp-2 break-words text-2xl font-light leading-tight text-text-default"
          :title="documentStore.currentDocument?.title || 'Editar Documento'"
          data-testid="doc-editor-title"
        >
          {{ documentStore.currentDocument?.title || 'Editar Documento' }}
        </h1>
        <nav
          v-if="documentStore.currentDocument"
          class="mt-1.5 flex min-w-0 flex-wrap items-center gap-x-1 text-xs text-text-subtle"
          aria-label="Ubicación del documento"
          :title="documentLocationPath"
          data-testid="doc-location-path"
        >
          <BaseActionIcon action="folders" class="mr-0.5 flex-shrink-0" />
          <template v-for="(segment, index) in documentLocationSegments" :key="`${index}-${segment.label}`">
            <span
              v-if="index"
              class="select-none text-text-subtle"
              aria-hidden="true"
            >/</span>
            <NuxtLink
              :to="segment.to"
              class="cursor-pointer break-words rounded px-1 py-0.5 transition-colors hover:bg-surface-muted hover:text-text-default focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              :data-testid="`doc-location-segment-${index}`"
            >
              {{ segment.label }}
            </NuxtLink>
          </template>
        </nav>
        <p
          v-if="documentStore.currentDocument"
          class="mt-1 flex min-w-0 items-center gap-1 text-sm text-text-muted"
          data-testid="doc-editor-metadata"
        >
          <span class="flex-shrink-0">
            {{ form.is_client_visible ? 'Visible en el portal' : 'No visible en el portal' }}
          </span>
          <span aria-hidden="true">·</span>
          <span class="min-w-0 truncate" :title="headerClientLabel || 'Sin cliente'">
            {{ headerClientLabel || 'Sin cliente' }}
          </span>
        </p>
        <BaseBadge
          v-if="documentStore.currentDocument?.display_state"
          class="mt-2"
          :variant="documentStore.currentDocument.display_state.variant"
          size="sm"
          data-testid="doc-derived-state"
        >
          {{ documentStore.currentDocument.display_state.label }}
        </BaseBadge>
        <DocumentStateList
          v-else-if="documentStore.currentDocument && !isCollectionAccount"
          class="mt-2"
          :episodes="workflowEpisodes"
          :max-visible="4"
          show-history
          @history="showStateHistory = true"
        />
      </div>
      <div
        v-if="documentStore.currentDocument && !loadError"
        class="flex min-w-0 flex-col gap-2 panel-portrait:flex-row panel-portrait:items-center panel-landscape:flex-shrink-0 panel-landscape:justify-end"
        data-testid="doc-header-actions"
      >
        <BaseButton
          variant="secondary"
          size="md"
          class="w-full whitespace-nowrap panel-portrait:w-auto"
          data-testid="doc-thread-action"
          @click="showThreadModal = true"
        >
          <BaseActionIcon action="link" />
          {{ documentStore.currentDocument?.thread_summary
            ? `Hilo · ${documentStore.currentDocument.thread_summary.document_count}`
            : 'Enlazar documentos' }}
        </BaseButton>
        <div class="flex justify-end whitespace-nowrap" data-testid="doc-document-actions">
          <BaseActionMenu
            :items="downloadItems"
            :label="isDownloading ? 'Descargando…' : 'Acciones'"
            :disabled="isDownloading"
            variant="ghost"
            testid="doc-document-actions-trigger"
          />
        </div>
        <div
          class="grid grid-cols-2 gap-2 border-t border-border-muted pt-2 panel-portrait:flex panel-portrait:items-center panel-portrait:border-l panel-portrait:border-t-0 panel-portrait:pl-3 panel-portrait:pt-0"
          role="group"
          aria-label="Acciones de edición"
          data-testid="doc-edit-actions"
        >
          <BaseButton
            as="NuxtLink"
            :to="returnTarget"
            variant="secondary"
            size="md"
            class="w-full whitespace-nowrap panel-portrait:w-auto"
            data-testid="doc-cancel"
          >
            Cancelar
          </BaseButton>
          <BaseButton
            variant="primary"
            size="md"
            type="submit"
            form="doc-edit-form"
            class="w-full whitespace-nowrap panel-portrait:w-auto"
            data-testid="doc-save"
            :loading="documentStore.isUpdating"
            :disabled="Boolean(saveBlockReasons.length)"
            :disabled-reason="saveBlockReasons.join(' ')"
          >
            {{ documentStore.isUpdating ? 'Guardando...' : (hasChanges ? 'Guardar cambios' : 'Guardar') }}
          </BaseButton>
        </div>
      </div>
    </header>

    <!-- Llegar por URL directa a un archivado no daría ninguna señal de que
         está fuera de circulación: la lista ya no lo muestra. -->
    <BaseAlert
      v-if="documentStore.currentDocument?.is_archived && !loadError"
      variant="warning"
      title="Este documento está archivado"
      class="mb-6"
      data-testid="document-archived-banner"
    >
      <p>No aparece en el listado, en la búsqueda ni en los contadores.</p>
      <div class="mt-3">
        <BaseButton
          variant="secondary"
          size="sm"
          :loading="documentStore.isUpdating"
          @click="handleUnarchive"
        >
          Restaurar
        </BaseButton>
      </div>
    </BaseAlert>

    <BaseAlert
      v-if="documentEmailUsage.count > 0 && !loadError"
      variant="info"
      class="mb-6"
      data-testid="document-email-usage"
    >
      <div>
        <p class="font-medium">
          Este documento se envió en {{ documentEmailUsage.count }}
          correo{{ documentEmailUsage.count === 1 ? '' : 's' }}.
        </p>
        <div class="mt-3 grid gap-2 sm:grid-cols-2">
          <NuxtLink
            v-for="usage in documentEmailUsage.results"
            :key="usage.email_log_id"
            :to="localePath({
              path: '/panel/emails',
              query: { tab: 'history', email: usage.email_log_id },
            })"
            class="rounded-lg border border-border-muted bg-surface/70 px-3 py-2 text-sm hover:border-border-default"
            :data-testid="`document-email-${usage.email_log_id}`"
          >
            <span class="block break-words font-semibold text-text-default">{{ usage.subject }}</span>
            <span class="mt-0.5 block break-all text-xs text-text-subtle">
              {{ usage.recipient }} · {{ formatDate(usage.sent_at) }}
            </span>
            <span class="mt-1 block break-words text-xs text-text-muted">
              {{ usage.attachments.map(item => item.filename).join(', ') }}
            </span>
          </NuxtLink>
        </div>
      </div>
    </BaseAlert>

    <BaseAlert
      v-if="documentCommunications.count > 0 && !loadError"
      variant="info"
      class="mb-6"
      data-testid="document-communications-usage"
    >
      <div>
        <p class="font-medium">
          Este documento se usó en {{ documentCommunications.count }}
          comunicación{{ documentCommunications.count === 1 ? '' : 'es' }} con clientes.
        </p>
        <div class="mt-3 grid gap-2 sm:grid-cols-2">
          <NuxtLink
            v-for="usage in documentCommunications.results"
            :key="usage.message.id"
            :to="{
              path: '/panel/communications',
              query: { thread: usage.thread.id },
            }"
            class="rounded-lg border border-border-muted bg-surface/70 px-3 py-2 text-sm hover:border-border-default"
            :data-testid="`document-communication-${usage.message.id}`"
          >
            <span class="block font-semibold text-text-default">{{ usage.thread.title }}</span>
            <span class="mt-0.5 block text-xs text-text-subtle">
              {{ usage.message.direction_display }} · {{ usage.message.channel_display }} ·
              {{ usage.message.subject || usage.message.content.slice(0, 80) }}
            </span>
          </NuxtLink>
        </div>
      </div>
    </BaseAlert>

    <div
      v-if="documentStore.isLoading"
      class="grid grid-cols-1 gap-6 panel-landscape:grid-cols-[20rem_minmax(0,1fr)] panel-desktop:grid-cols-[24rem_minmax(0,1fr)]"
      role="status"
    >
      <span class="sr-only">Cargando documento...</span>
      <div class="bg-surface rounded-xl shadow-sm border border-border-muted p-6 space-y-4" aria-hidden="true">
        <BaseSkeleton class="w-1/3" />
        <BaseSkeleton variant="card" class="!h-10" />
        <BaseSkeleton variant="card" class="!h-10" />
        <BaseSkeleton variant="card" class="!h-10" />
      </div>
      <div class="bg-surface rounded-xl shadow-sm border border-border-muted p-6" aria-hidden="true">
        <BaseSkeleton variant="card" class="!h-96" />
      </div>
    </div>

    <BaseAlert v-else-if="loadError" variant="danger" title="No se pudo cargar el documento">
      <p>Verifica tu conexión e inténtalo de nuevo.</p>
      <div class="mt-3 flex items-center gap-4">
        <BaseButton variant="secondary" size="sm" @click="reloadDocument">Reintentar</BaseButton>
        <BaseButton as="NuxtLink" :to="returnTarget" variant="link" size="sm">
          <BaseActionIcon action="back" />
          {{ returnLabel }}
        </BaseButton>
      </div>
    </BaseAlert>

    <EntityHistoryTabs v-else-if="documentStore.currentDocument" entity-type="document" :object-id="route.params.id">
    <form
      id="doc-edit-form"
      class="grid grid-cols-1 gap-6 panel-landscape:grid-cols-[20rem_minmax(0,1fr)] panel-desktop:grid-cols-[24rem_minmax(0,1fr)]"
      @submit.prevent="handleSave"
    >
      <!-- Requisito 6: un documento emitido no se reasigna ni se reescribe.
           El form queda visible (consultarlo sigue valiendo) con el guardado
           apagado; el backend rechaza igual con collection_account_locked. -->
      <BaseAlert
        v-if="lockedCuenta && !generatedSnapshot"
        variant="warning"
        class="panel-landscape:col-span-2"
        data-testid="doc-locked-cuenta-alert"
      >
        Cuenta de cobro emitida: este documento es de sólo lectura aquí.
        Si hubo un error, anúlala y emite una nueva desde
        Contabilidad → Cuentas de cobro.
      </BaseAlert>

      <BaseAlert
        v-if="contractMirror"
        variant="info"
        class="panel-landscape:col-span-2"
        data-testid="doc-contract-mirror-alert"
      >
        Contrato vigente, en solo lectura. Este documento muestra en vivo el
        mismo contrato que ven los clientes en la sección legal de su propuesta.
        Se consulta y se descarga en PDF o en Markdown; se modifica únicamente
        por migración de la plantilla del contrato.
      </BaseAlert>

      <BaseAlert
        v-if="generatedSnapshot"
        variant="info"
        class="panel-landscape:col-span-2"
        data-testid="doc-generated-snapshot-alert"
      >
        <template v-if="isCollectionAccount">
          Cuenta de cobro archivada como PDF inmutable al emitirla. El archivo,
          sus datos contables y su ubicación son de sólo lectura; las
          observaciones privadas siguen disponibles.
        </template>
        <template v-else>
          Versión {{ documentStore.currentDocument.source_version }} archivada al enviar
          la propuesta. El PDF, el nombre y la carpeta son de sólo lectura; las
          observaciones y el historial siguen disponibles.
        </template>
      </BaseAlert>

      <!-- El botón Guardar habilitado se lee como "puedes guardar"; esto se
           lee como "te falta guardar", y nombra qué falta. -->
      <UnsavedChangesNotice
        v-if="hasChanges"
        class="panel-landscape:col-span-2"
        :title="unsavedTitle"
        :detail="unsavedDetail"
        :message="readOnlyDocument
          ? 'Esta versión es de sólo lectura: estos cambios no se pueden guardar y se pierden al salir.'
          : 'Si sales de esta página, se pierden. Guardar los deja registrados.'"
        :can-save="canSaveNow"
        :saving="documentStore.isUpdating"
        testid="doc-unsaved-notice"
        @save="handleSave"
        @discard="discardChanges"
      />

      <aside
        class="bg-surface rounded-xl shadow-sm border border-border-muted p-5 sm:p-6
               panel-landscape:sticky panel-landscape:top-6 panel-landscape:self-start panel-landscape:max-h-[calc(100vh-7rem)] panel-landscape:overflow-y-auto"
      >
        <div class="space-y-6">
          <div class="space-y-4">
            <h2 class="text-xs uppercase tracking-wide font-semibold text-text-muted">Identificación</h2>
            <div>
              <!-- La marca va FUERA del <label>: dentro se sumaba al nombre
                   accesible del campo ("Título Sin guardar"). -->
              <div class="flex items-center gap-2 mb-1">
                <label for="edit-title" class="block text-sm font-medium text-text-default">Título</label>
                <BaseBadge
                  v-if="isFieldDirty('title')"
                  variant="warning"
                  size="sm"
                  data-testid="doc-field-dirty-title"
                >
                  Sin guardar
                </BaseBadge>
              </div>
              <input
                id="edit-title"
                v-model="form.title"
                type="text"
                required
                :readonly="readOnlyDocument"
                class="w-full px-4 py-2.5 border border-border-default rounded-xl text-sm bg-surface text-text-default
                       focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              />
            </div>
            <div class="rounded-xl border border-border-default bg-surface-raised p-3">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="flex items-center gap-2">
                    <p class="text-sm font-medium text-text-default">Notas</p>
                    <BaseBadge v-if="notesDirty" variant="warning" size="sm">Sin guardar</BaseBadge>
                    <BaseBadge v-else-if="hasNotes" variant="success" size="sm">Agregadas</BaseBadge>
                  </div>
                  <p class="text-xs text-text-subtle mt-1">Asunto, correo, WhatsApp y notas personalizadas.</p>
                </div>
                <BaseButton
                  type="button"
                  variant="secondary"
                  size="sm"
                  :icon-only="!readOnlyDocument"
                  :aria-label="notesActionLabel"
                  :title="notesActionLabel"
                  :disabled="lockedCuenta && !hasNotes"
                  data-testid="doc-client-note-open"
                  @click="showClientNote = true"
                >
                  <BaseActionIcon action="notes" />
                  <span v-if="readOnlyDocument">
                    {{ pdfPreviewDocument ? 'Observaciones' : 'Notas' }}
                  </span>
                </BaseButton>
              </div>
            </div>
            <div>
              <div class="flex items-center gap-2 mb-1">
                <label class="block text-sm font-medium text-text-default">Cliente</label>
                <BaseBadge
                  v-if="isFieldDirty('client')"
                  variant="warning"
                  size="sm"
                  data-testid="doc-field-dirty-client"
                >
                  Sin guardar
                </BaseBadge>
              </div>
              <ClientAutocomplete
                v-model="form.client"
                :initial-label="clientDisplayName"
                :disabled="readOnlyDocument"
                :disabled-reason="readOnlyReason"
                test-id="doc-client-autocomplete"
                allow-create
                @select="onClientSelect"
                @create-new="onCreateNewClient"
              />
              <p
                v-if="!form.client && legacyClientName"
                class="text-xs text-text-subtle mt-1"
                data-testid="doc-legacy-client-name"
              >
                Nombre guardado (texto libre): {{ legacyClientName }}
              </p>
              <!-- La relación sirve en las dos direcciones: desde el documento
                   se llega a su cliente y a su proyecto. -->
              <div
                v-if="savedClientId || savedProjectId"
                class="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs"
              >
                <NuxtLink
                  v-if="savedClientId"
                  data-testid="document-client-link"
                  :to="localePath({ path: '/panel/clients', query: { highlight: String(savedClientId) } })"
                  class="text-text-brand hover:underline"
                >
                  Ver cliente{{ savedClientLabel ? `: ${savedClientLabel}` : '' }}
                </NuxtLink>
                <NuxtLink
                  v-if="savedProjectId"
                  data-testid="document-project-link"
                  :to="localePath({ path: '/panel/projects', query: { highlight: String(savedProjectId) } })"
                  class="text-text-brand hover:underline"
                >
                  Ver proyecto{{ savedProjectName ? `: ${savedProjectName}` : '' }}
                </NuxtLink>
              </div>
            </div>

            <!-- Inline client creation: the clients module without leaving the form -->
            <div
              v-if="inlineClientOpen"
              class="rounded-xl border border-border-default bg-surface-raised p-4 space-y-3"
              data-testid="doc-inline-client"
            >
              <p class="text-sm font-medium text-text-default">Crear cliente nuevo</p>
              <ClientFormFields
                v-model="inlineClient"
                testid-prefix="doc-inline-client"
                dense
              />
              <div class="flex justify-end gap-2">
                <BaseButton type="button" variant="secondary" size="sm" @click="inlineClientOpen = false">
                  Cancelar
                </BaseButton>
                <BaseButton
                  type="button"
                  variant="primary"
                  size="sm"
                  :disabled="creatingClient"
                  data-testid="doc-inline-client-save"
                  @click="createInlineClient"
                >
                  {{ creatingClient ? 'Creando...' : 'Crear cliente' }}
                </BaseButton>
              </div>
            </div>

            <div>
              <ProjectSelect
                v-model="form.project"
                :client-profile-id="form.client"
                :client-label="clientDisplayName"
                :allow-no-client="true"
                :disabled="readOnlyDocument"
                testid="doc-project-select"
                @select="onProjectSelect"
              />
              <!-- ProjectSelect dibuja su propia etiqueta, así que la marca va
                   debajo del campo en vez de al lado del rótulo. -->
              <BaseBadge
                v-if="isFieldDirty('project')"
                variant="warning"
                size="sm"
                class="mt-1"
                data-testid="doc-field-dirty-project"
              >
                Sin guardar
              </BaseBadge>
            </div>
            <DocumentStateSelector
              v-if="!isCollectionAccount && !generatedSnapshot"
              :document-id="route.params.id"
              :episodes="workflowEpisodes"
              :disabled="readOnlyDocument"
              @changed="refreshWorkflow"
              @history="showStateHistory = true"
            />
          </div>

          <hr v-if="!pdfPreviewDocument" class="border-border-muted" />

          <div v-if="!pdfPreviewDocument" class="space-y-4">
            <h2 class="text-xs uppercase tracking-wide font-semibold text-text-muted">Organización</h2>
            <label class="flex items-start justify-between gap-4 rounded-xl border border-border-default bg-surface-raised p-3">
              <span>
                <span class="block text-sm font-medium text-text-default">Visible en el portal del cliente</span>
                <span class="mt-0.5 block text-xs text-text-subtle">Controla la publicación sin mezclarla con el ciclo de trabajo.</span>
              </span>
              <BaseToggle
                v-model="form.is_client_visible"
                :disabled="readOnlyDocument"
                :disabled-reason="readOnlyReason"
              />
            </label>
            <div>
              <label class="block text-sm font-medium text-text-default mb-1">Carpeta</label>
              <select
                v-model="form.folder_id"
                :disabled="readOnlyDocument"
                :title="readOnlyDocument ? readOnlyReason : undefined"
                class="w-full px-4 py-2.5 border border-border-default rounded-xl text-sm bg-surface text-text-default
                       focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              >
                <option :value="null">Sin carpeta</option>
                <option
                  v-for="folder in folderStore.activeFolders"
                  :key="folder.id"
                  :value="folder.id"
                  :disabled="folder.is_system_managed && folder.id !== form.folder_id"
                >
                  {{ folder.name }}
                </option>
              </select>
            </div>
          </div>

          <hr class="border-border-muted" />

          <div class="space-y-4">
            <h2 class="text-xs uppercase tracking-wide font-semibold text-text-muted">Opciones de exportación</h2>
            <div>
              <label class="block text-sm font-medium text-text-default mb-1">Idioma</label>
              <select
                v-model="form.language"
                :disabled="readOnlyDocument"
                :title="readOnlyDocument ? readOnlyReason : undefined"
                class="w-full px-4 py-2.5 border border-border-default rounded-xl text-sm bg-surface text-text-default
                       focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              >
                <option value="es">Español</option>
                <option value="en">English</option>
              </select>
            </div>
            <div class="space-y-1">
              <label
                v-for="option in coverOptions"
                :key="option.key"
                class="flex items-center gap-3 cursor-pointer py-1.5 px-1 select-none"
                :data-testid="option.testId"
              >
                <BaseToggle
                  v-model="form[option.key]"
                  :disabled="readOnlyDocument"
                  :disabled-reason="readOnlyReason"
                />
                <span class="text-sm font-medium text-text-default">{{ option.label }}</span>
              </label>
              <!-- Traduce las casillas a páginas: sin esto, saber qué trae el
                   archivo obligaba a descargarlo. -->
              <p class="text-xs text-text-subtle pt-1 px-1" data-testid="doc-included-pages">
                El PDF incluirá: {{ includedPagesLabel }}
              </p>
              <BaseButton
                variant="secondary"
                size="sm"
                class="mt-2 w-full"
                data-testid="doc-preview-pdf"
                @click="handlePreviewPdf"
              >
                Previsualizar PDF
              </BaseButton>
            </div>
          </div>
        </div>
      </aside>

      <section
        v-if="pdfPreviewDocument"
        class="w-full max-w-4xl justify-self-center bg-surface rounded-xl shadow-sm border border-border-muted p-5 sm:p-6 flex min-w-0 flex-col"
        data-testid="doc-generated-snapshot-panel"
      >
        <div class="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <p class="text-sm font-semibold text-text-default">
              {{ contractMirror
                ? 'Contrato vigente'
                : isCollectionAccount ? 'Cuenta de cobro en PDF' : 'PDF inmutable archivado' }}
            </p>
            <p class="mt-1 text-sm text-text-muted">
              {{ contractMirror
                ? 'Se genera en vivo desde el contrato único: es el mismo borrador que el cliente descarga desde la sección legal de su propuesta.'
                : isCollectionAccount
                  ? generatedSnapshot
                    ? 'Es el archivo definitivo creado al emitir la cuenta; no se vuelve a generar ni se puede reemplazar.'
                    : 'Esta cuenta histórica se consulta como PDF mientras se completa su archivado definitivo.'
                  : 'Esta vista conserva la versión exacta que se adjuntó al correo; no se vuelve a generar desde la propuesta actual.' }}
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <BaseButton
              variant="secondary"
              size="sm"
              data-testid="doc-generated-download"
              @click="handleDownloadPdf()"
            >
              <BaseActionIcon action="download" />
              Descargar PDF
            </BaseButton>
            <template v-if="contractMirror">
              <BaseButton
                variant="secondary"
                size="sm"
                data-testid="doc-contract-markdown-download"
                @click="handleDownloadMarkdown"
              >
                <BaseActionIcon action="download" />
                Descargar Markdown
              </BaseButton>
              <BaseButton
                variant="ghost"
                size="sm"
                data-testid="doc-contract-markdown-copy"
                @click="handleCopyContent"
              >
                <BaseActionIcon action="copy" />
                {{ copiedMarkdown ? 'Copiado' : 'Copiar Markdown' }}
              </BaseButton>
            </template>
          </div>
        </div>
        <dl
          v-if="isCollectionAccount"
          class="mb-4 grid gap-3 rounded-xl border border-border-muted bg-surface-raised p-4 text-sm sm:grid-cols-2"
          data-testid="doc-collection-account-facts"
        >
          <div v-if="documentStore.currentDocument.public_number">
            <dt class="text-xs font-semibold uppercase tracking-wide text-text-subtle">Consecutivo</dt>
            <dd class="mt-1 text-text-default">{{ documentStore.currentDocument.public_number }}</dd>
          </div>
          <div v-if="documentStore.currentDocument.total != null">
            <dt class="text-xs font-semibold uppercase tracking-wide text-text-subtle">Total</dt>
            <dd class="mt-1 text-text-default">
              {{ formatMoney(documentStore.currentDocument.total, documentStore.currentDocument.currency) }}
            </dd>
          </div>
          <div v-if="documentStore.currentDocument.issue_date">
            <dt class="text-xs font-semibold uppercase tracking-wide text-text-subtle">Emisión</dt>
            <dd class="mt-1 text-text-default">{{ formatBusinessDate(documentStore.currentDocument.issue_date) }}</dd>
          </div>
          <div v-if="documentStore.currentDocument.due_date">
            <dt class="text-xs font-semibold uppercase tracking-wide text-text-subtle">Vencimiento</dt>
            <dd class="mt-1 text-text-default">{{ formatBusinessDate(documentStore.currentDocument.due_date) }}</dd>
          </div>
          <div
            v-if="documentStore.currentDocument.billing_notes"
            class="sm:col-span-2"
          >
            <dt class="text-xs font-semibold uppercase tracking-wide text-text-subtle">Notas de cobro</dt>
            <dd class="mt-1 whitespace-pre-wrap text-text-default">{{ documentStore.currentDocument.billing_notes }}</dd>
          </div>
          <div
            v-if="documentStore.currentDocument.collection_account_observations"
            class="sm:col-span-2"
          >
            <dt class="text-xs font-semibold uppercase tracking-wide text-text-subtle">Observaciones de emisión</dt>
            <dd class="mt-1 whitespace-pre-wrap text-text-default">{{ documentStore.currentDocument.collection_account_observations }}</dd>
          </div>
        </dl>
        <PdfPreviewPane
          class="h-[clamp(20rem,52vh,34rem)] min-h-0"
          :src="storedPdfSrc"
          :active="Boolean(documentStore.currentDocument)"
          error-message="El archivo archivado no está disponible. Puedes intentar descargarlo o informar el problema."
          test-id-prefix="doc-generated-pdf"
        />
      </section>

      <section
        v-else
        class="bg-surface rounded-xl shadow-sm border border-border-muted p-5 sm:p-6
               flex flex-col min-w-0"
        data-testid="doc-markdown-editor-panel"
      >
        <div class="flex items-center justify-between mb-3 gap-3 flex-wrap">
          <label for="edit-markdown" class="block text-sm font-medium text-text-default">Contenido Markdown</label>
          <div class="flex items-center gap-2 flex-wrap">
            <span v-if="form.content_markdown" class="text-xs text-text-subtle tabular-nums">
              {{ form.content_markdown.length.toLocaleString() }} caracteres
            </span>
            <BaseButton
              type="button"
              variant="ghost"
              size="sm"
              :disabled="!form.content_markdown.trim()"
              disabled-reason="Agrega contenido Markdown antes de copiarlo."
              @click="handleCopyContent"
            >
              <BaseActionIcon action="copy" />
              {{ copiedMarkdown ? 'Copiado' : 'Copiar' }}
            </BaseButton>
            <BaseButton
              type="button"
              variant="ghost"
              size="sm"
              @click="handlePasteContent"
            >
              <BaseActionIcon action="paste" />
              {{ pastedMarkdown ? 'Pegado' : 'Pegar' }}
            </BaseButton>
            <BaseSegmented
              v-model="form.template_style"
              size="sm"
              :options="templateStyleOptions"
              aria-label="Estilo de plantilla"
            />
            <BaseButton variant="secondary" size="sm" :disabled="!form.content_markdown.trim()" disabled-reason="Agrega contenido Markdown antes de abrir la vista completa." @click="showFullPreview = true">
              <BaseActionIcon action="enter-fullscreen" />
              Vista completa
            </BaseButton>
            <BaseButton
              type="button"
              variant="ghost"
              size="sm"
              @click="showPreview = !showPreview"
            >
              <BaseActionIcon :action="showPreview ? 'hide' : 'view'" />
              {{ showPreview ? 'Ocultar vista previa' : 'Vista previa' }}
            </BaseButton>
          </div>
        </div>
        <div :class="showPreview ? 'grid grid-cols-1 panel-desktop:grid-cols-2 gap-4 flex-1 min-h-0' : 'flex-1 min-h-0 flex'">
          <textarea
            id="edit-markdown"
            ref="markdownTextareaRef"
            v-model="form.content_markdown"
            placeholder="# Contenido del documento..."
            class="w-full px-4 py-3 border border-border-default rounded-xl text-sm font-mono leading-relaxed bg-surface text-text-default placeholder:text-text-subtle
                   focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none resize-none
                   min-h-[24rem] panel-desktop:h-[calc(100vh-18rem)]"
          ></textarea>
          <div
            v-if="showPreview"
            class="w-full max-w-4xl justify-self-center self-start overflow-y-auto rounded-xl border border-border-default bg-surface
                   min-h-64 max-h-[calc(100vh-16rem)]"
            data-testid="doc-markdown-preview-pane"
          >
            <div class="sticky top-0 px-3 py-2 border-b border-border-default bg-surface-raised rounded-t-xl z-10">
              <span class="text-xs font-medium text-text-muted uppercase tracking-wide">Vista previa</span>
            </div>
            <DocumentMarkdownBody
              v-if="form.content_markdown.trim()"
              :markdown="form.content_markdown"
              :theme="form.template_style"
              class="mx-auto w-full max-w-3xl px-5 py-4"
            />
            <div
              v-else
              class="flex items-center justify-center h-64 text-sm text-text-subtle"
            >
              Escribe markdown para ver la vista previa...
            </div>
          </div>
        </div>

      </section>
    </form>
    </EntityHistoryTabs>

    <DocumentClientNoteModal
      v-model="showClientNote"
      :document-id="route.params.id"
      :subject="form.client_email_subject"
      :email-body="form.client_email_body"
      :whatsapp-message="form.client_whatsapp_message"
      :custom-notes="form.client_custom_notes"
      :notes="normalizedNotes"
      :immutable-content="pdfPreviewDocument"
      :saving="documentStore.isUpdating"
      @submit="saveClientNote"
      @workflow-changed="refreshWorkflow"
    />

    <DocumentStateHistoryModal
      v-if="!isCollectionAccount"
      v-model="showStateHistory"
      :document-id="route.params.id"
      :readonly="generatedSnapshot"
      @changed="refreshWorkflow"
    />

    <MarkdownPreviewModal
      v-model="showFullPreview"
      :title="form.title || 'Vista previa'"
      contained
    >
      <DocumentMarkdownBody
        v-if="form.content_markdown.trim()"
        :markdown="form.content_markdown"
        variant="full"
        :theme="form.template_style"
        class="max-w-4xl mx-auto"
      />
      <div v-else class="flex items-center justify-center h-full text-sm text-text-subtle">
        No hay contenido para mostrar.
      </div>
    </MarkdownPreviewModal>

    <!-- El PDF de verdad, el mismo que entrega la descarga: es lo único que
         muestra las portadas, que la vista previa de markdown no rinde. -->
    <DocumentPdfPreviewModal
      v-model="showPdfPreview"
      :document-id="route.params.id"
      :title="form.title || 'Vista previa del PDF'"
      :template-style="form.template_style"
      :version="documentStore.currentDocument?.updated_at || ''"
      :cover-options="savedCoverOptions"
    />

    <DocumentThreadModal
      v-model="showThreadModal"
      :document="documentStore.currentDocument"
      @saved="handleThreadSaved"
    />

    <!-- Las tres salidas del guard: [Seguir editando] [Salir sin guardar]
         [Guardar y salir]. Sin este modal el guard abriría un diálogo que
         nadie renderiza y la navegación se bloquearía en silencio. -->
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
  </div>
</template>

<script setup>
import EntityHistoryTabs from '~/components/history/EntityHistoryTabs.vue';
import { reactive, ref, computed, onMounted, nextTick } from 'vue';
import MarkdownPreviewModal from '~/components/panel/documents/MarkdownPreviewModal.vue';
import DocumentPdfPreviewModal from '~/components/panel/documents/DocumentPdfPreviewModal.vue';
import PdfPreviewPane from '~/components/base/PdfPreviewPane.vue';
import DocumentMarkdownBody from '~/components/panel/documents/DocumentMarkdownBody.vue';
import DocumentClientNoteModal from '~/components/panel/documents/DocumentClientNoteModal.vue';
import DocumentStateHistoryModal from '~/components/panel/documents/DocumentStateHistoryModal.vue';
import DocumentStateList from '~/components/panel/documents/DocumentStateList.vue';
import DocumentStateSelector from '~/components/panel/documents/DocumentStateSelector.vue';
import DocumentThreadModal from '~/components/panel/documents/DocumentThreadModal.vue';
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue';
import ProjectSelect from '~/components/accounting/ProjectSelect.vue';
import ClientFormFields from '~/components/clients/ClientFormFields.vue';
import UnsavedChangesNotice from '~/components/panel/UnsavedChangesNotice.vue';
import { clientFormPayload, emptyClientForm } from '~/utils/billingCode';
import { useProposalClientsStore } from '~/stores/proposal_clients';
import { useClientProjectCascade } from '~/composables/useClientProjectCascade';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useUnsavedGuard } from '~/composables/useUnsavedGuard';
import { joinEs } from '~/utils/spanishList';
import { describeIncludedPages } from '~/utils/documentCoverPages';
import { documentReturnLabel, resolveDocumentReturn } from '~/utils/documentReturnNavigation';
import { formatDate as formatBusinessDate, formatDateTime } from '~/utils/formatDate';
import { formatMoney } from '~/utils/formatMoney';
import { downloadBlob } from '~/utils/downloadFile';

const localePath = useLocalePath();
const route = useRoute();
const router = useRouter();
definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const documentStore = useDocumentStore();
const folderStore = useDocumentFolderStore();
const stateStore = useDocumentStateStore();
const clientsStore = useProposalClientsStore();
const notify = usePanelNotify();
const returnNavigation = computed(() => resolveDocumentReturn(
  route.query.from,
  router,
  localePath('/panel/documents'),
));
const returnTarget = computed(() => returnNavigation.value.target);
const returnLabel = computed(() => documentReturnLabel({
  hasOrigin: returnNavigation.value.hasOrigin,
  query: returnNavigation.value.query,
  folderById: (id) => folderStore.folderById(id),
}));
const loadError = ref(false);
// Requisito 6: an issued cuenta is a fact — read-only here, forever.
const lockedCuenta = ref(false);
const generatedSnapshot = ref(false);
// The window onto the one contract: rendered live, never edited here.
const contractMirror = ref(false);
const readOnlyDocument = computed(
  () => lockedCuenta.value || generatedSnapshot.value || contractMirror.value,
);
const pdfPreviewDocument = computed(
  () => generatedSnapshot.value || lockedCuenta.value || contractMirror.value,
);
const readOnlyReason = computed(() => {
  if (contractMirror.value) {
    return 'Este es el contrato vigente: se consulta y se descarga aquí; se modifica únicamente por migración de la plantilla.';
  }
  if (generatedSnapshot.value) {
    if (lockedCuenta.value) {
      return 'Esta cuenta de cobro conserva el PDF emitido y sólo permite gestionar observaciones privadas.';
    }
    return 'Esta versión archivada es de sólo lectura; las observaciones y el historial siguen disponibles.';
  }
  if (lockedCuenta.value) {
    return 'Esta cuenta de cobro ya fue emitida. Anúlala y crea una nueva para cambiar sus datos.';
  }
  return '';
});
const clientDisplayName = ref('');
// El nombre libre heredado sigue existiendo (lo lee el PDF); se muestra como
// referencia mientras el documento no tenga cliente relacional.
const legacyClientName = ref('');
const inlineClientOpen = ref(false);
const inlineClient = ref(emptyClientForm());
const creatingClient = ref(false);
// Los enlaces apuntan a lo GUARDADO, no a una selección sin guardar.
const savedClientId = ref(null);
const savedClientLabel = ref('');
const savedProjectId = ref(null);
const savedProjectName = ref('');
const isDownloading = ref(false);
const showPreview = ref(true);
const showFullPreview = ref(false);
const showPdfPreview = ref(false);
const showClientNote = ref(false);
const showStateHistory = ref(false);
const showThreadModal = ref(false);
const workflowEpisodes = ref([]);
const normalizedNotes = ref([]);
const copiedMarkdown = ref(false);
const documentCommunications = ref({ count: 0, results: [] });
const documentEmailUsage = ref({ count: 0, results: [] });
const pastedMarkdown = ref(false);
const markdownTextareaRef = ref(null);

const form = reactive({
  title: '',
  client: null,
  project: null,
  language: 'es',
  include_portada: true,
  include_subportada: true,
  include_contraportada: true,
  is_client_visible: false,
  content_markdown: '',
  client_email_subject: '',
  client_email_body: '',
  client_whatsapp_message: '',
  client_custom_notes: [],
  folder_id: null,
  template_style: 'professional',
});

function formatDate(value) {
  return formatDateTime(value, { fallback: '' });
}

// Nombres sin artículo: se encadenan como los encadenaría una persona
// ("cliente y proyecto sin guardar").
const FIELD_LABELS = {
  title: 'título',
  client: 'cliente',
  project: 'proyecto',
  language: 'idioma',
  include_portada: 'portada',
  include_subportada: 'subportada',
  include_contraportada: 'contraportada',
  is_client_visible: 'visibilidad en portal',
  content_markdown: 'contenido',
  client_email_subject: 'asunto del correo',
  client_email_body: 'correo para el cliente',
  client_whatsapp_message: 'WhatsApp para el cliente',
  client_custom_notes: 'notas adicionales',
  folder_id: 'carpeta',
  template_style: 'estilo de plantilla',
};

const NOTE_FIELDS = [
  'client_email_subject',
  'client_email_body',
  'client_whatsapp_message',
  'client_custom_notes',
];

// Se desestructura para que los refs queden como bindings de primer nivel: a
// través del objeto (`guard.hasChanges`) el template no los desenvuelve.
const {
  hasChanges,
  isFieldDirty,
  dirtyLabels,
  unsavedTitle,
  unsavedDetail,
  canSaveNow,
  commit: commitBaseline,
  guardedReload,
  guardedExport,
  discardChanges,
  confirmState,
  handleConfirmed,
  handleSecondaryAction,
  handleCancelled,
} = useUnsavedGuard({
  snapshot: () => ({ ...form }),
  labels: FIELD_LABELS,
  save: handleSave,
  // Una cuenta de cobro emitida no se guarda: el backend contesta 400
  // collection_account_locked. Ofrecer "Guardar y salir" ahí sería mentir.
  canSave: () => !readOnlyDocument.value,
  blockedReason: 'Este documento es de sólo lectura y no se puede modificar.',
  reload: reloadDocument,
});

const saveBlockReasons = computed(() => [
  lockedCuenta.value
    ? 'Esta cuenta de cobro ya fue emitida. Anúlala y crea una nueva para modificarla.'
    : '',
  generatedSnapshot.value
    ? 'Esta versión conserva el PDF exacto enviado y no se puede modificar.'
    : '',
  contractMirror.value
    ? 'Este es el contrato vigente y no se edita desde el Gestor.'
    : '',
  !hasChanges.value ? 'No hay cambios por guardar.' : '',
].filter(Boolean));

const headerClientLabel = computed(() => clientDisplayName.value || legacyClientName.value);
const documentLocationSegments = computed(() => {
  const document = documentStore.currentDocument;
  if (!document) return [];
  const scopeQuery = document.is_archived ? { scope: 'archived' } : {};
  const locationTarget = (folder) => localePath({
    path: '/panel/documents',
    query: { ...scopeQuery, folder: String(folder) },
  });
  const rootTarget = locationTarget('root');
  const segments = [{ label: 'Documentos', to: rootTarget }];
  if (document.folder == null) {
    return [
      ...segments,
      { label: 'Sin carpeta', to: locationTarget('none') },
    ];
  }

  const folderId = Number(document.folder);
  const ancestors = Number.isFinite(folderId)
    ? folderStore.ancestorsOf(folderId)
    : [];
  const folderSegments = ancestors
    .filter((folder) => folder.name)
    .map((folder) => ({
      label: folder.name,
      to: locationTarget(folder.id),
    }));
  if (!folderSegments.length) {
    folderSegments.push({
      label: document.folder_name || 'Ubicación no disponible',
      to: locationTarget(document.folder),
    });
  }
  return [...segments, ...folderSegments];
});
const documentLocationPath = computed(
  () => documentLocationSegments.value.map((segment) => segment.label).join(' / '),
);
const isCollectionAccount = computed(
  () => documentStore.currentDocument?.document_type_code === 'collection_account',
);
const storedPdfSrc = computed(() => {
  const id = documentStore.currentDocument?.id;
  if (!id) return '';
  const version = documentStore.currentDocument?.updated_at || '';
  return `/api/documents/${id}/pdf/?inline=1&v=${encodeURIComponent(version)}`;
});

const hasNotes = computed(() => [
  form.client_email_subject,
  form.client_email_body,
  form.client_whatsapp_message,
].some((value) => value.trim())
  || form.client_custom_notes.length > 0
  || normalizedNotes.value.length > 0);

const notesActionLabel = computed(() => {
  if (pdfPreviewDocument.value) return 'Gestionar observaciones privadas';
  if (readOnlyDocument.value) return 'Ver notas';
  return hasNotes.value ? 'Editar notas' : 'Agregar notas';
});

const notesDirty = computed(() => NOTE_FIELDS.some((field) => isFieldDirty(field)));

function assignClientNote(note) {
  form.client_email_subject = note.subject;
  form.client_email_body = note.emailBody;
  form.client_whatsapp_message = note.whatsappMessage;
  form.client_custom_notes = note.customNotes;
}

async function refreshWorkflow() {
  const result = await documentStore.fetchDocument(route.params.id);
  if (!result.success || !result.data) return;
  workflowEpisodes.value = Array.isArray(result.data.active_states)
    ? result.data.active_states
    : [];
  normalizedNotes.value = Array.isArray(result.data.notes) ? result.data.notes : [];
}

function notePayload(note) {
  return {
    client_email_subject: note.subject,
    client_email_body: note.emailBody,
    client_whatsapp_message: note.whatsappMessage,
    client_custom_notes: note.customNotes,
  };
}

function notifySaveError(result, title = 'No se pudo guardar el documento') {
  if (result.code === 'collection_account_locked') {
    lockedCuenta.value = true;
    notify.error({ title: 'Documento emitido', detail: result.message });
    return;
  }
  if (result.code === 'generated_snapshot_read_only') {
    generatedSnapshot.value = true;
    notify.error({ title: 'Versión archivada', detail: result.message });
    return;
  }
  const fieldDetail = result.fieldErrors
    ? Object.entries(result.fieldErrors).map(([key, value]) => `${key}: ${value}`).join(' · ')
    : '';
  notify.error({
    title,
    detail: fieldDetail || result.message,
  });
}

async function saveClientNote(note) {
  const result = await documentStore.updateDocument(route.params.id, notePayload(note));
  if (!result.success) {
    notifySaveError(result, 'No se pudieron guardar las notas');
    return;
  }
  assignClientNote(note);
  commitBaseline(NOTE_FIELDS);
  showClientNote.value = false;
  notify.success({
    title: 'Notas guardadas',
    detail: 'Los cambios quedaron guardados en el documento.',
    duration: 6000,
  });
}

const { onClientSelect, onProjectSelect } = useClientProjectCascade(
  form,
  clientDisplayName,
);

function onCreateNewClient(typedName) {
  inlineClientOpen.value = true;
  inlineClient.value = { ...emptyClientForm(), name: typedName || '' };
}

async function createInlineClient() {
  creatingClient.value = true;
  const result = await clientsStore.createClient(clientFormPayload(inlineClient.value));
  creatingClient.value = false;
  if (result.success && result.data?.id) {
    inlineClientOpen.value = false;
    onClientSelect(result.data);
  }
}

function applyAssociationSnapshot(data) {
  savedClientId.value = data.client ?? null;
  savedClientLabel.value = data.client_display_name || '';
  savedProjectId.value = data.project ?? null;
  savedProjectName.value = data.project_name || '';
  legacyClientName.value = data.client_name || '';
}

const coverOptions = [
  { key: 'include_portada', label: 'Incluir portada', testId: 'doc-cover-portada' },
  { key: 'include_subportada', label: 'Incluir subportada', testId: 'doc-cover-subportada' },
  { key: 'include_contraportada', label: 'Incluir contraportada', testId: 'doc-cover-contraportada' },
];

// Las casillas dicen qué se incluye; esto dice qué va a salir, en el orden en
// que sale. Se lee del formulario vivo, así el efecto de desmarcar una casilla
// se ve antes de guardar (el PDF, en cambio, se arma con lo guardado).
const includedPagesLabel = computed(() => describeIncludedPages(form));

// La vista previa muestra el PDF GUARDADO: su encabezado tiene que describir
// esa configuración, no la de la pantalla, o volvería a prometer algo que el
// archivo no cumple.
const savedCoverOptions = computed(() => {
  const saved = documentStore.currentDocument || {};
  return {
    include_portada: saved.include_portada,
    include_subportada: saved.include_subportada,
    include_contraportada: saved.include_contraportada,
  };
});

const templateStyleOptions = [
  { value: 'friendly', label: 'Amigable', testId: 'doc-style-friendly' },
  { value: 'professional', label: 'Profesional', testId: 'doc-style-professional' },
];

async function handleCopyContent() {
  try {
    await navigator.clipboard.writeText(form.content_markdown);
    copiedMarkdown.value = true;
    setTimeout(() => { copiedMarkdown.value = false; }, 2000);
  } catch {
    notify.error({
      title: 'No se pudo copiar al portapapeles',
      detail: 'Tu navegador bloqueó el acceso al portapapeles.',
    });
  }
}

async function handlePasteContent() {
  try {
    const pasted = await navigator.clipboard.readText();
    if (!pasted) return;
    const textarea = markdownTextareaRef.value;
    const start = textarea ? textarea.selectionStart : form.content_markdown.length;
    const end = textarea ? textarea.selectionEnd : form.content_markdown.length;
    form.content_markdown = form.content_markdown.slice(0, start) + pasted + form.content_markdown.slice(end);
    const cursor = start + pasted.length;
    if (textarea) {
      nextTick(() => {
        textarea.focus();
        textarea.setSelectionRange(cursor, cursor);
      });
    }
    pastedMarkdown.value = true;
    setTimeout(() => { pastedMarkdown.value = false; }, 2000);
  } catch {
    notify.error({
      title: 'No se pudo pegar desde el portapapeles',
      detail: 'Tu navegador bloqueó el acceso al portapapeles.',
    });
  }
}

async function handleUnarchive() {
  const id = documentStore.currentDocument?.id;
  if (!id) return;
  const result = await documentStore.unarchiveDocument(id);
  if (result.success) {
    notify.success({ title: 'Documento restaurado' });
    await documentStore.fetchDocument(id);
  } else {
    notify.error({ title: 'No se pudo restaurar el documento', detail: result.message });
  }
}

function handleThreadSaved({ thread }) {
  if (!documentStore.currentDocument) return;
  documentStore.currentDocument = {
    ...documentStore.currentDocument,
    thread_summary: thread
      ? {
        id: thread.id,
        title: thread.title,
        document_count: thread.document_count,
      }
      : null,
  };
}

async function reloadDocument() {
  const id = route.params.id;
  loadError.value = false;
  const [result, , , usageResult, emailUsageResult] = await Promise.all([
    documentStore.fetchDocument(id),
    folderStore.fetchFolders(),
    stateStore.fetchCatalog(),
    documentStore.fetchDocumentCommunications(id),
    documentStore.fetchDocumentEmailUsage(id),
  ]);
  documentCommunications.value = usageResult.success
    ? usageResult.data
    : { count: 0, results: [] };
  documentEmailUsage.value = emailUsageResult.success
    ? emailUsageResult.data
    : { count: 0, results: [] };
  if (result.success && result.data) {
    form.title = result.data.title || '';
    form.client = result.data.client ?? null;
    form.project = result.data.project ?? null;
    clientDisplayName.value = result.data.client_display_name || '';
    applyAssociationSnapshot(result.data);
    form.language = result.data.language || 'es';
    form.include_portada = result.data.include_portada !== undefined ? result.data.include_portada : true;
    form.include_subportada = result.data.include_subportada !== undefined ? result.data.include_subportada : true;
    form.include_contraportada = result.data.include_contraportada !== undefined ? result.data.include_contraportada : true;
    form.is_client_visible = Boolean(result.data.is_client_visible);
    form.content_markdown = result.data.content_markdown || '';
    form.client_email_subject = result.data.client_email_subject || '';
    form.client_email_body = result.data.client_email_body || '';
    form.client_whatsapp_message = result.data.client_whatsapp_message || '';
    form.client_custom_notes = Array.isArray(result.data.client_custom_notes)
      ? result.data.client_custom_notes.map((note) => ({ ...note }))
      : [];
    form.folder_id = result.data.folder || null;
    workflowEpisodes.value = Array.isArray(result.data.active_states)
      ? result.data.active_states
      : [];
    normalizedNotes.value = Array.isArray(result.data.notes) ? result.data.notes : [];
    form.template_style = result.data.template_style || 'professional';
    lockedCuenta.value = (
      result.data.document_type_code === 'collection_account'
      && result.data.commercial_status !== 'draft'
    );
    generatedSnapshot.value = Boolean(result.data.is_generated_snapshot);
    contractMirror.value = Boolean(result.data.is_contract_mirror);
    commitBaseline();
  } else {
    loadError.value = true;
  }
}

onMounted(reloadDocument);
// El refresh global vuelve a pedir el documento y pisa el formulario sin
// avisar: se registra la versión que pregunta primero. `onMounted` y el botón
// "Reintentar" siguen llamando al crudo — ahí no hay nada que perder.
usePanelRefresh(guardedReload);

async function handleSave() {
  const payload = {
    title: form.title.trim(),
    // Siempre presentes, null incluido: es lo que permite desvincular.
    client: form.client ?? null,
    project: form.project ?? null,
    language: form.language,
    include_portada: form.include_portada,
    include_subportada: form.include_subportada,
    include_contraportada: form.include_contraportada,
    is_client_visible: form.is_client_visible,
    content_markdown: form.content_markdown,
    client_email_subject: form.client_email_subject,
    client_email_body: form.client_email_body,
    client_whatsapp_message: form.client_whatsapp_message,
    client_custom_notes: form.client_custom_notes,
    folder_id: form.folder_id,
    template_style: form.template_style,
  };

  // Se capturan ANTES de guardar: guardar limpia la lista.
  const savedLabels = [...dirtyLabels.value];

  const result = await documentStore.updateDocument(route.params.id, payload);
  if (result.success) {
    commitBaseline();
    if (result.data) {
      applyAssociationSnapshot(result.data);
      clientDisplayName.value = result.data.client_display_name || clientDisplayName.value;
    }
    // Confirmar QUÉ se guardó, no sólo que algo se guardó: sin eso la duda
    // pasa al otro lado —no se sabe si guardó o si el aviso sólo desapareció—.
    notify.success({
      title: 'Documento guardado',
      detail: savedLabels.length ? `Se guardó: ${joinEs(savedLabels)}.` : '',
      duration: 6000,
    });
    return true;
  }
  // The server is the truth: the cuenta may have been issued in another tab.
  notifySaveError(result);
  // Sin re-fijar la baseline a propósito: un guardado fallido deja el aviso
  // puesto y, desde el guard de salida, bloquea la navegación.
  return false;
}

const downloadItems = computed(() => {
  if (contractMirror.value) {
    return [
      { action: 'download', label: 'Descargar PDF', onClick: () => handleDownloadPdf() },
      { action: 'download', label: 'Descargar Markdown', onClick: () => handleDownloadMarkdown() },
      { action: 'copy', label: 'Copiar Markdown', onClick: () => handleCopyContent() },
    ];
  }
  if (lockedCuenta.value) {
    return [{ action: 'download', label: 'Descargar cuenta de cobro', onClick: () => handleDownloadPdf() }];
  }
  if (generatedSnapshot.value) {
    return [{ action: 'download', label: 'Descargar versión archivada', onClick: () => handleDownloadPdf() }];
  }
  return [
    { action: 'download', label: 'Descargar PDF · Amigable', onClick: () => handleDownloadPdf('friendly') },
    { action: 'download', label: 'Descargar PDF · Profesional', onClick: () => handleDownloadPdf('professional') },
  ];
});

async function handleDownloadPdf(template = null) {
  // El archivo lo arma el servidor con lo guardado: con cambios en pantalla
  // hay que decidir primero cuál de las dos versiones se descarga.
  if (!(await guardedExport('download'))) return;
  isDownloading.value = true;
  const result = await documentStore.downloadPdf(
    route.params.id, form.title || 'document', template);
  isDownloading.value = false;
  if (!result.success) {
    notify.error({ title: 'No se pudo descargar el PDF', detail: result.message });
  }
}

async function handlePreviewPdf() {
  if (!(await guardedExport('preview'))) return;
  showPdfPreview.value = true;
}

function handleDownloadMarkdown() {
  // The contract window's Markdown is the live draft the server sent.
  const blob = new Blob([form.content_markdown || ''], { type: 'text/markdown;charset=utf-8' });
  downloadBlob(blob, `${documentStore.currentDocument?.slug || 'contrato-vigente'}.md`);
}
</script>
