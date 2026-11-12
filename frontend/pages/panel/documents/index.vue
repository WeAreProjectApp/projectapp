<template>
  <div :class="[PAGE_MAX_WIDTH, 'flex min-h-full flex-col']" data-testid="documents-page">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4" data-enter>
      <div>
        <h1 class="text-2xl font-light text-text-default">Gestor Documental</h1>
        <p class="text-sm text-text-subtle mt-1">Crea, organiza y comparte documentos con tu marca.</p>
      </div>
      <BaseButton as="NuxtLink" :to="createLink" variant="primary" class="shadow-sm">
        <BaseActionIcon action="create" />
        Nuevo Documento
      </BaseButton>
    </div>

    <!-- Toolbar: search + list/gallery toggle -->
    <DocumentsToolbar
      v-model:search="searchQuery"
      v-model:view-mode="viewMode"
      :scope="effectiveScope"
      :scope-locked="isSearching"
      :compact="isPanelStacked"
      class="mb-5"
      data-enter
      style="--enter-delay: 60ms"
      @update:scope="handleScopeChange"
    >
      <template #actions>
        <BaseButton
          v-if="showToolbarDateOrderControl"
          variant="secondary"
          size="sm"
          class="flex-shrink-0"
          :disabled="isListLoading"
          disabled-reason="Se está actualizando el orden de los documentos."
          :aria-label="dateOrderButtonLabel"
          data-testid="documents-date-sort-compact"
          @click="toggleDateOrder"
        >
          <BaseActionIcon :action="dateOrderAction" />
          {{ dateOrderCompactLabel }}
        </BaseButton>
        <BaseButton
          variant="secondary"
          size="sm"
          class="flex-shrink-0"
          aria-label="Ver los hilos de documentos"
          data-testid="documents-threads-index"
          @click="showThreadIndex = true"
        >
          Hilos
        </BaseButton>
      </template>
    </DocumentsToolbar>

    <BaseButton
      v-if="isPanelStacked"
      variant="secondary"
      size="md"
      class="mb-4 w-full justify-between"
      data-testid="folder-drawer-trigger"
      aria-haspopup="dialog"
      :aria-expanded="showFolderDrawer"
      @click="showFolderDrawer = true"
    >
      <span class="flex min-w-0 items-center gap-2">
        <BaseActionIcon action="folders" />
        <span class="truncate">{{ compactFolderLabel }}</span>
      </span>
      <span class="shrink-0 text-xs font-medium text-text-brand">Cambiar navegación</span>
    </BaseButton>

    <!--
      La columna del panel es una variable CSS que sólo `panel-landscape:` consume:
      bajo ese ancho el grid sigue siendo de una columna y el ancho guardado queda
      inerte (el panel apilado no lo lee). El track medio de 1.5rem es el gap-6
      de siempre, ahora habitado por la manija de redimensionado.
    -->
    <div
      ref="foldersGridRef"
      class="grid flex-1 grid-cols-1 items-stretch gap-6 panel-landscape:grid-cols-[var(--folders-panel-w,24rem)_1.5rem_minmax(0,1fr)] panel-landscape:gap-0"
      :class="panelDragging ? 'select-none' : ''"
      :style="folderPanelStyle"
    >
      <FolderSidebar
        v-if="!isPanelStacked"
        data-testid="folder-panel"
        data-enter
        style="--enter-delay: 120ms"
        :folders="sidebarFolders"
        :active-id="documentStore.activeFolderId"
        :archive-scope="effectiveScope"
        :archived-count="documentStore.counts.documents.archived"
        :show-inactive-projects="showInactiveProjects"
        :unfiled-count="sidebarUnfiledCount"
        :navigation-mode="navigationMode"
        :navigation-selection="navigationSelection"
        :navigation-facets="navigationStore.facets"
        :navigation-loading="navigationStore.isLoading"
        :navigation-saving="navigationStore.isSavingPreference"
        :navigation-error="navigationStore.error"
        :scope-locked="isSearching"
        :is-dragging="!!draggingDoc"
        :dragging-folder-id="draggingFolder?.id ?? null"
        @select="handleSelectFolder"
        @manage="openFolderManager"
        @edit="openFolderForm"
        @folder-drop="handleDropOnFolder"
        @delete="handleDeleteFolder"
        @archive="handleArchiveFolder"
        @view-archived="handleViewArchivedFolder"
        @toggle-archived="handleToggleArchivedMode"
        @toggle-inactive-projects="handleToggleInactiveProjects"
        @update:navigation-mode="handleNavigationModeChange"
        @select-entity="handleSelectNavigationEntity"
        @retry-navigation="navigationStore.fetchNavigation"
      />

      <!--
        Manija de redimensionado: separator ARIA operable con teclado, con
        pointer capture para que el drag no se pierda al salir del track.
        `touch-none` evita que una tableta apaisada scrollee en vez
        de redimensionar. Persiste al soltar; doble clic vuelve al default.
      -->
      <BaseResizeHandle
        v-if="!isPanelStacked"
        :value="panelWidth"
        :min="FOLDER_PANEL_MIN"
        :max="FOLDER_PANEL_MAX"
        label="Ajustar el ancho del panel de navegación"
        test-id="folder-panel-resize-handle"
        data-enter
        style="--enter-delay: 150ms"
        @pointer-start="onHandleDown"
        @pointer-move="onHandleMove"
        @pointer-end="onHandleUp"
        @resize="resizePanelWidth"
        @reset="resetWidth"
      />

      <section
        class="min-w-0 flex flex-col transition-colors"
        :class="isArchived ? 'rounded-xl bg-warning-soft p-3' : ''"
        data-enter
        style="--enter-delay: 180ms"
      >
        <!--
          Rótulo del ámbito, siempre visible mientras no sea el de reposo.
          Sin él, «Todos» con el modo encendido listaba archivados sin que nada
          en la vista lo dijera: se leían como documentos perdidos, y la única
          forma de recuperar la vista normal era editar la URL a mano.
        -->
        <div
          v-if="scopeNotice"
          class="mb-4 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg px-3 py-2 text-sm"
          :class="scopeNotice.tone"
          data-testid="doc-scope-banner"
        >
          <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
          </svg>
          <span class="font-medium">{{ scopeNotice.label }}</span>
          <span class="text-text-muted">{{ scopeNotice.detail }}</span>
        </div>

        <FolderHeader :folder="currentFolder" @edit="openFolderForm" />

        <!-- La búsqueda ignora carpeta y estado: decirlo evita la lectura de
             que el filtro visible está acotando los resultados. -->
        <BaseAlert v-if="isSearching" variant="info" class="mb-4">
          Buscando «{{ searchQuery.trim() }}» en todo el gestor, activos y archivados.
        </BaseAlert>

        <!-- Parado DENTRO de una carpeta archivada: restaurar la carpeta
             completa vive aquí — las filas del listado solo restauran hijas.
             No depende del modo: apagarlo estando dentro deja al usuario en la
             misma carpeta (req 19), y ahí la salida tiene que seguir a la vista. -->
        <BaseAlert
          v-if="currentFolder?.is_archived"
          variant="info"
          class="mb-4"
          data-testid="current-folder-archived-alert"
        >
          <div class="flex flex-wrap items-center justify-between gap-3">
            <span>Estás dentro de una carpeta archivada.</span>
            <BaseButton
              variant="secondary"
              size="sm"
              :loading="folderStore.isUpdating"
              data-testid="doc-restore-current-folder"
              @click="handleUnarchiveFolder(currentFolder, { follow: true })"
            >
              Restaurar esta carpeta
            </BaseButton>
          </div>
        </BaseAlert>

        <!-- Multi-state filters and recurring queries -->
        <div class="bg-surface rounded-xl shadow-sm border border-border-muted p-3 mb-4" data-testid="doc-state-filters">
          <StateFilterChips
            :states="stateStore.activeStates"
            :active-ids="documentStore.activeStateIds"
            :without-ids="documentStore.withoutStateIds"
            :active-preset="documentStore.activeStatePreset"
            @toggle="handleToggleState"
            @toggle-absence="handleToggleStateAbsence"
            @clear="handleClearStateFilters"
            @preset="handleStatePreset"
          />
        </div>

        <!-- Filtros de asociación (ocultos en búsqueda: la búsqueda es global
             y estos ejes no la acotan) -->
        <div
          v-if="!isSearching"
          class="bg-surface rounded-xl shadow-sm border border-border-muted p-3 mb-4"
          data-testid="doc-association-filters"
        >
          <DocumentsAssociationFilters
            :client="documentStore.activeClientId"
            :project="documentStore.activeProjectId"
            :client-label="associationClientLabel"
            @update:client="handleClientFilter"
            @update:project="handleProjectFilter"
          />
        </div>

        <FolderBreadcrumb
          v-if="showBreadcrumb"
          :active-id="documentStore.activeFolderId"
          :dragging-folder-id="draggingFolder?.id ?? null"
          :root-label="navigationRootLabel"
          :root-value="navigationRootValue"
          @select="handleSelectFolder"
          @nest="handleNestFolder"
        />

        <!-- Loading -->
        <DocumentListSkeleton v-if="isListLoading" :mode="viewMode" />

        <!-- Load error (persistent: a toast would get lost) -->
        <BaseAlert
          v-else-if="loadError"
          variant="danger"
          title="No se pudieron cargar los documentos"
        >
          <p>{{ loadError }}</p>
          <div class="mt-3">
            <BaseButton variant="secondary" size="sm" @click="loadDocuments">Reintentar</BaseButton>
          </div>
        </BaseAlert>

        <!-- Empty states, one per context -->
        <BaseEmptyState
          v-else-if="!hasContent && searchQuery"
          title="Sin resultados"
          :description="`No se encontraron documentos para &quot;${searchQuery}&quot;.`"
        >
          <template #icon>
            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </template>
          <template #actions>
            <BaseButton variant="secondary" size="sm" @click="searchQuery = ''">Limpiar búsqueda</BaseButton>
          </template>
        </BaseEmptyState>
        <BaseEmptyState
          v-else-if="!hasContent && hasStateFilters"
          title="Ningún documento coincide"
          description="Ningún documento coincide con los estados seleccionados."
        >
          <template #icon>
            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
            </svg>
          </template>
          <template #actions>
            <BaseButton variant="secondary" size="sm" @click="handleClearStateFilters">Quitar filtros</BaseButton>
          </template>
        </BaseEmptyState>
        <!-- Una carpeta sin nada archivado tiene que decirlo por su nombre: el
             vacío genérico se leía como que la carpeta no existía en este modo. -->
        <BaseEmptyState
          v-else-if="!hasContent && isArchived && currentFolder"
          :title="`«${currentFolder.name}» no tiene nada archivado`"
          description="La carpeta sigue ahí y puede tener documentos activos. Apaga el modo archivado para verlos."
          data-testid="folder-archived-empty"
        >
          <template #icon>
            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
            </svg>
          </template>
          <template #actions>
            <BaseButton variant="secondary" size="sm" @click="handleToggleArchivedMode(false)">
              Ver su contenido activo
            </BaseButton>
          </template>
        </BaseEmptyState>
        <BaseEmptyState
          v-else-if="!hasContent && isArchived"
          title="No hay nada archivado"
          description="Lo que archives saldrá de la vista principal y de los contadores, pero seguirá aquí."
        >
          <template #icon>
            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
            </svg>
          </template>
          <template #actions>
            <BaseButton variant="secondary" size="sm" @click="handleBackToActive">
              Volver a los activos
            </BaseButton>
          </template>
        </BaseEmptyState>
        <!-- Con el modo apagado dentro de una carpeta archivada: ofrecer «crea un
             documento aquí» sería mandar al usuario a un 400, porque el backend
             no admite contenido activo bajo una carpeta archivada. -->
        <BaseEmptyState
          v-else-if="!hasContent && currentFolder?.is_archived"
          title="Esta carpeta está archivada"
          description="Su contenido salió de la vista principal. Restáurala para volver a trabajar aquí, o enciende el modo archivado para ver lo que guarda."
          data-testid="folder-archived-inactive-empty"
        >
          <template #icon>
            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
            </svg>
          </template>
          <template #actions>
            <BaseButton variant="secondary" size="sm" @click="handleToggleArchivedMode(true)">
              Ver lo que guarda
            </BaseButton>
          </template>
        </BaseEmptyState>
        <BaseEmptyState
          v-else-if="!hasContent && documentStore.activeFolderId !== 'all'"
          title="Esta carpeta está vacía"
          description="Crea un documento aquí o arrastra uno desde otra carpeta."
        >
          <template #icon>
            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 7a2 2 0 012-2h4l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
            </svg>
          </template>
          <template #actions>
            <BaseButton as="NuxtLink" :to="createLink" variant="secondary" size="sm">Crear documento aquí</BaseButton>
          </template>
        </BaseEmptyState>
        <BaseEmptyState
          v-else-if="!hasContent"
          title="No hay documentos todavía"
          description="Crea tu primer documento desde markdown y descárgalo como PDF con tu marca."
        >
          <template #icon>
            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </template>
          <template #actions>
            <BaseButton as="NuxtLink" :to="localePath('/panel/documents/create')" variant="primary" size="sm">
              Crear el primero
            </BaseButton>
          </template>
        </BaseEmptyState>

        <!-- Collection: table (list mode, desktop) / card grid -->
        <Transition v-else-if="hasContent" name="view-swap" mode="out-in">
          <div :key="viewMode">
          <DocumentsTable
            v-if="!isPanelStacked && viewMode === 'list'"
            :documents="pagedDocuments"
            :subfolders="currentSubfolders"
            :edit-to-for="editToFor"
            :folder-to-for="folderToFor"
            :dragging-doc-id="draggingDoc?.id ?? null"
            :drag-over-folder-id="dragOverFolderId"
            :newly-created-id="newlyCreatedId"
            :scope="effectiveScope"
            :date-order="dateOrder"
            :sorting="isListLoading"
            :folder-summary="subfolderSummary"
            :updating="folderStore.isUpdating || documentStore.isUpdating"
            @open="openDocument"
            @action="actionDoc = $event"
            @thread="handleOpenThread"
            @unarchive-folder="handleUnarchiveFolder"
            @view-archived-folder="handleViewArchivedFolder"
            @select-folder="handleSelectFolder"
            @doc-dragstart="handleDragStart"
            @doc-dragend="handleDragEnd"
            @folder-dragstart="handleFolderDragStart"
            @folder-dragend="handleFolderDragEnd"
            @folder-dragover="onFolderRowDragOver"
            @folder-dragleave="dragOverFolderId = null"
            @drop-on-folder="handleDropOnFolder"
            @sort-date="handleDateOrderChange"
          />
          <!-- En compacto la tarjeta es la única representación interactiva. -->
          <DocumentsGrid
            v-else
            :documents="pagedDocuments"
            :subfolders="currentSubfolders"
            :edit-to-for="editToFor"
            :folder-to-for="folderToFor"
            :dragging-doc-id="draggingDoc?.id ?? null"
            :drag-over-folder-id="dragOverFolderId"
            :newly-created-id="newlyCreatedId"
            :scope="effectiveScope"
            :folder-summary="subfolderSummary"
            :updating="folderStore.isUpdating || documentStore.isUpdating"
            @open="openDocument"
            @action="actionDoc = $event"
            @thread="handleOpenThread"
            @unarchive-folder="handleUnarchiveFolder"
            @view-archived-folder="handleViewArchivedFolder"
            @select-folder="handleSelectFolder"
            @doc-dragstart="handleDragStart"
            @doc-dragend="handleDragEnd"
            @folder-dragstart="handleFolderDragStart"
            @folder-dragend="handleFolderDragEnd"
            @folder-dragover="onFolderRowDragOver"
            @folder-dragleave="dragOverFolderId = null"
            @drop-on-folder="handleDropOnFolder"
          />
          </div>
        </Transition>

        <!-- Pagination -->
        <BasePagination
          v-if="!isListLoading && !loadError && filteredDocuments.length > 0"
          :current-page="docPage"
          :total-pages="docTotalPages"
          :total-items="docTotalItems"
          :range-from="docRangeFrom"
          :range-to="docRangeTo"
          class="mt-4"
          @prev="goToPreviousDocumentPage"
          @next="goToNextDocumentPage"
          @go="goToDocumentPage"
        />

      </section>
    </div>

    <BaseDrawer
      v-model="showFolderDrawer"
      placement="left"
      title="Navegación"
      test-id="folder-drawer"
    >
      <FolderSidebar
        class="h-full rounded-none border-0 shadow-none"
        :folders="sidebarFolders"
        :active-id="documentStore.activeFolderId"
        :archive-scope="effectiveScope"
        :archived-count="documentStore.counts.documents.archived"
        :show-inactive-projects="showInactiveProjects"
        :unfiled-count="sidebarUnfiledCount"
        :navigation-mode="navigationMode"
        :navigation-selection="navigationSelection"
        :navigation-facets="navigationStore.facets"
        :navigation-loading="navigationStore.isLoading"
        :navigation-saving="navigationStore.isSavingPreference"
        :navigation-error="navigationStore.error"
        :scope-locked="isSearching"
        touch-mode
        :is-dragging="false"
        :dragging-folder-id="null"
        @select="selectFolderFromDrawer"
        @manage="openFolderManagerFromDrawer"
        @edit="openFolderFormFromDrawer"
        @delete="deleteFolderFromDrawer"
        @archive="archiveFolderFromDrawer"
        @view-archived="viewArchivedFolderFromDrawer"
        @toggle-archived="handleToggleArchivedMode"
        @toggle-inactive-projects="handleToggleInactiveProjects"
        @update:navigation-mode="handleNavigationModeChange"
        @select-entity="selectNavigationEntityFromDrawer"
        @retry-navigation="navigationStore.fetchNavigation"
      />
    </BaseDrawer>

    <FolderManagerModal
      v-model="showFolderManager"
      :initial-parent="typeof documentStore.activeFolderId === 'number' ? documentStore.activeFolderId : null"
      @changed="handleFoldersChanged"
      @archived="handleFolderArchived"
      @change-client="openFolderCascade"
    />
    <FolderFormModal
      v-model="showFolderForm"
      :folder="editingFolder"
      @saved="handleFoldersChanged"
      @change-client="openFolderCascade"
    />
    <FolderChangeClientModal
      :open="showFolderCascade"
      :folder="cascadeFolder"
      :initial-client-profile-id="cascadeClientId"
      @close="showFolderCascade = false"
      @changed="handleFolderClientChanged"
    />
    <DeleteFolderModal
      v-model="showDeleteFolderModal"
      :folder="deletingFolder"
      @deleted="handleFolderDeleted"
      @archived="handleFolderArchived"
    />
    <MoveFolderModal v-model="showMoveModal" :document="movingDoc" @changed="handleMoved" />
    <RenameDocumentModal v-model="showRenameModal" :document="renamingDoc" @changed="handleRenamed" />
    <SendDocumentEmailModal v-model="showEmailModal" :document="emailingDoc" />
    <DocumentThreadModal
      v-model="showThreadModal"
      :document="threadDoc"
      @saved="handleThreadSaved"
    />
    <DocumentThreadIndexModal
      v-model="showThreadIndex"
      @open-thread="handleOpenThreadFromIndex"
    />
    <DocumentActionsSheet
      v-model="showActionsSheet"
      :document="actionDoc"
      :archived="!!actionDoc?.is_archived"
      :edit-to="editToFor(actionDoc)"
      @archive="handleArchiveDoc(actionDoc)"
      @unarchive="handleUnarchiveDoc(actionDoc)"
      @edit="handleEditDoc(actionDoc)"
      @rename="handleRenameDoc(actionDoc)"
      @move="handleMoveDoc(actionDoc)"
      @download-pdf="(tpl) => handleDownloadPdf(actionDoc, tpl)"
      @copy-markdown="handleCopyMarkdown(actionDoc.id)"
      @duplicate="handleDuplicate(actionDoc.id)"
      @send-email="handleSendEmail(actionDoc)"
      @thread="handleOpenThread(actionDoc)"
      @delete="handleDelete(actionDoc)"
    />

    <!-- Delete confirmation modal -->
    <ConfirmModal
      v-model="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :variant="confirmState.variant"
      :require-type-text="confirmState.requireTypeText"
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
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import FolderSidebar from '~/components/panel/documents/FolderSidebar.vue';
import FolderBreadcrumb from '~/components/panel/documents/FolderBreadcrumb.vue';
import FolderHeader from '~/components/panel/documents/FolderHeader.vue';
import FolderFormModal from '~/components/panel/documents/FolderFormModal.vue';
import FolderChangeClientModal from '~/components/panel/documents/FolderChangeClientModal.vue';
import StateFilterChips from '~/components/panel/documents/StateFilterChips.vue';
import DocumentsAssociationFilters from '~/components/panel/documents/DocumentsAssociationFilters.vue';
import FolderManagerModal from '~/components/panel/documents/FolderManagerModal.vue';
import DeleteFolderModal from '~/components/panel/documents/DeleteFolderModal.vue';
import MoveFolderModal from '~/components/panel/documents/MoveFolderModal.vue';
import RenameDocumentModal from '~/components/panel/documents/RenameDocumentModal.vue';
import SendDocumentEmailModal from '~/components/panel/documents/SendDocumentEmailModal.vue';
import DocumentActionsSheet from '~/components/panel/documents/DocumentActionsSheet.vue';
import DocumentThreadModal from '~/components/panel/documents/DocumentThreadModal.vue';
import DocumentThreadIndexModal from '~/components/panel/documents/DocumentThreadIndexModal.vue';
import DocumentListSkeleton from '~/components/panel/documents/DocumentListSkeleton.vue';
import DocumentsToolbar from '~/components/panel/documents/DocumentsToolbar.vue';
import DocumentsTable from '~/components/panel/documents/DocumentsTable.vue';
import DocumentsGrid from '~/components/panel/documents/DocumentsGrid.vue';
import ConfirmModal from '~/components/ConfirmModal.vue';
import BasePagination from '~/components/base/BasePagination.vue';
import BaseDrawer from '~/components/base/BaseDrawer.vue';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { folderSummaryFrom, scopedCounts } from '~/utils/documentStatus';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useDocumentViewMode } from '~/composables/useDocumentViewMode';
import { useDocumentFilterQuery } from '~/composables/useDocumentFilterQuery';
import { useReducedMotion } from '~/composables/useReducedMotion';
import { useRowNavigation } from '~/composables/useRowNavigation';
import { useIsMobile } from '~/composables/useIsMobile';
import { PANEL_BREAKPOINTS } from '~/config/responsive';
import { PAGE_MAX_WIDTH } from '~/utils/tableLayout';
import { documentOriginWithFocus } from '~/utils/documentReturnNavigation';
import {
  contextualFolderFilters,
  navigationEntityFilters,
} from '~/utils/documentNavigationFilters';
import {
  FOLDER_PANEL_MAX, FOLDER_PANEL_MIN, useFolderPanelWidth,
} from '~/composables/useFolderPanelWidth';

const localePath = useLocalePath();
const route = useRoute();
const router = useRouter();
const { openRow } = useRowNavigation();
definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const documentStore = useDocumentStore();
const folderStore = useDocumentFolderStore();
const stateStore = useDocumentStateStore();
const navigationStore = useDocumentNavigationStore();
const navigationMode = computed({
  get: () => navigationStore.mode,
  set: (mode) => navigationStore.setTransientMode(mode),
});
const navigationSelection = computed(() => {
  const value = navigationMode.value === 'project'
    ? documentStore.activeProjectId
    : documentStore.activeClientId;
  return value == null ? 'all' : value;
});
const selectedNavigationEntry = computed(() => {
  const entries = navigationMode.value === 'project'
    ? navigationStore.facets.projects || []
    : navigationStore.facets.clients || [];
  return entries.find((entry) => entry.id === navigationSelection.value) || null;
});

const notify = usePanelNotify();
const {
  confirmState, requestConfirm,
  handleConfirmed, handleSecondaryAction, handleCancelled,
} = useConfirmModal();
const { viewMode } = useDocumentViewMode();
const { reducedMotion } = useReducedMotion();

// Bajo el límite landscape canónico el panel apila a ancho completo: la manija
// no aplica ahí, y se quita con v-if para no duplicar nodos ante Playwright.
const { isMobile: isPanelStacked } = useIsMobile(PANEL_BREAKPOINTS.landscape - 1);
const foldersGridRef = ref(null);
const {
  width: panelWidth, dragging: panelDragging, gridStyle: folderPanelStyle,
  onHandleDown, onHandleMove, onHandleUp, resizeWidth: resizePanelWidth, resetWidth,
} = useFolderPanelWidth(foldersGridRef);

const searchQuery = ref('');
// El ciclo de vida del proyecto es un eje de catálogo, no el archivo de
// documentos. Este control empieza apagado en cada visita y no se serializa en
// URL ni preferencias: sólo abre temporalmente el grupo no operativo.
const showInactiveProjects = ref(false);
const focusedDocumentId = ref(null);
const newlyCreatedId = ref(null);
let newlyCreatedTimer = null;
// El estado es un eje propio: `activeFolderId` dice DÓNDE ('all' | 'root' |
// 'none' | id) y `archiveScope` dice EN QUÉ ESTADO. Antes compartían campo, y
// por eso no se podía entrar a una carpeta archivada ni filtrar dentro de ella.
const isSearching = computed(() => searchQuery.value.trim().length > 0);
// La búsqueda es global sin destruir el scope de origen. La interfaz muestra
// el ámbito efectivo ('all'), mientras la URL conserva el modo que reaparece
// al limpiar el término o al volver desde el editor.
const effectiveScope = computed(() => (isSearching.value ? 'all' : documentStore.archiveScope));
const isArchived = computed(() => effectiveScope.value === 'archived');
const dateOrder = computed(() => documentStore.dateOrder);
const nextDateOrder = computed(() => (dateOrder.value === 'oldest' ? 'recent' : 'oldest'));
const dateOrderAction = computed(() => (
  dateOrder.value === 'oldest' ? 'sort-ascending' : 'sort-descending'
));
const dateOrderCompactLabel = computed(() => (
  dateOrder.value === 'oldest' ? 'Más antiguos' : 'Más nuevos'
));
const dateColumnLabel = computed(() => {
  if (effectiveScope.value === 'archived') return 'Archivado';
  return effectiveScope.value === 'all' ? 'Fecha' : 'Creado';
});
const dateOrderButtonLabel = computed(() => {
  const current = dateOrder.value === 'oldest'
    ? 'más antiguos primero'
    : 'más nuevos primero';
  const next = nextDateOrder.value === 'oldest'
    ? 'más antiguos primero'
    : 'más nuevos primero';
  return `${dateColumnLabel.value}: ${current}. Ordenar con ${next}.`;
});
const showToolbarDateOrderControl = computed(() => (
  isPanelStacked.value || viewMode.value === 'grid'
));

const showBreadcrumb = computed(
  () => !isSearching.value
    && documentStore.activeFolderId !== 'all'
    && !(documentStore.activeFolderId === 'root' && !isArchived.value),
);

const currentFolder = computed(() => (
  typeof documentStore.activeFolderId === 'number'
    ? folderStore.folderById(documentStore.activeFolderId)
    : null
));

const compactFolderLabel = computed(() => {
  if (isSearching.value) return 'Resultados globales';
  if (currentFolder.value) return currentFolder.value.name;
  if (documentStore.activeFolderId === 'none') return 'Sin carpeta';
  if (documentStore.activeFolderId === 'root' && navigationSelection.value !== 'all') {
    if (navigationSelection.value === 'none') {
      return navigationMode.value === 'project' ? 'Sin proyecto' : 'Sin cliente';
    }
    return selectedNavigationEntry.value?.name
      || `${navigationMode.value === 'project' ? 'Proyecto' : 'Cliente'} #${navigationSelection.value}`;
  }
  if (documentStore.activeFolderId === 'root') return 'Raíz de archivados';
  return 'Todos los documentos';
});
const navigationRootLabel = computed(() => {
  if (navigationSelection.value !== 'all') return compactFolderLabel.value;
  return isArchived.value ? 'Archivados' : 'Todos';
});
const navigationRootValue = computed(() => (
  navigationSelection.value !== 'all' || isArchived.value ? 'root' : 'all'
));

// ── El panel lateral sigue al modo ───────────────────────────────────────────
// Antes listaba siempre el árbol activo con contadores de activos, incluso con
// el archivo encendido: una carpeta archivada entera no aparecía por ningún
// lado y «Todos» decía un número mientras el listado mostraba otro.
//
// El eje de RENDERIZADO es el scope de la vista, no `treeScopeFor`. Ése abre el
// árbol completo y es la regla del ROLLUP —cuántos archivados cuelgan de una
// carpeta activa—, no la de «qué filas se listan». Mezclarlos hacía que el modo
// archivado pintara el árbol entero. Quién puede aparecer lo decide
// `belongsToScope`, que suma las carpetas activas con archivados dentro para
// que se pueda bajar hasta ellos, y el panel lateral y el listado lo comparten:
// si discrepan, el panel promete «0 subcarpetas» y al entrar aparecen N.
const sidebarFolders = computed(() => folderStore.scopedRootFolders(effectiveScope.value));

const sidebarUnfiledCount = computed(() => {
  const { unfiled_active: unfiledActive, unfiled_archived: unfiledArchived } = documentStore.counts.documents;
  if (effectiveScope.value === 'archived') return unfiledArchived;
  if (effectiveScope.value === 'all') return unfiledActive + unfiledArchived;
  return unfiledActive;
});

// El ámbito en palabras. 'active' es el estado de reposo y no lleva rótulo:
// anunciar lo normal entrena a ignorar el aviso que sí importa.
const SCOPE_NOTICES = {
  archived: {
    label: 'Modo archivado',
    detail: 'Estás viendo lo archivado; los contadores del panel cuentan archivados.',
    // Sólido sobre el panel teñido: repetir el tinte lo volvería invisible.
    tone: 'bg-surface text-text-default',
  },
  all: {
    label: 'Activos y archivados',
    detail: 'La lista mezcla los dos estados; cada fila declara el suyo.',
    tone: 'bg-info-soft text-text-default',
  },
};

const scopeNotice = computed(() => SCOPE_NOTICES[effectiveScope.value] || null);

function folderMatchesNavigation(folder) {
  const selection = navigationSelection.value;
  if (selection === 'all') return true;
  const association = navigationMode.value === 'project' ? folder.project : folder.client;
  if (selection === 'none') return association == null;
  return Number(association) === Number(selection);
}

const navigationFolders = computed(() => folderStore.folders.filter(
  (folder) => folderStore.belongsToScope(folder, effectiveScope.value)
    && folderMatchesNavigation(folder),
));
const navigationFolderIds = computed(
  () => new Set(navigationFolders.value.map((folder) => folder.id)),
);
// La raíz gestionada de la entidad seleccionada no se lista: sería una carpeta
// con su mismo nombre conteniéndolo todo. Vale para proyectos y para clientes
// —los que ya adoptaron una carpeta madre—, que es el mismo caso con otro dueño.
const suppressedManagedRootId = computed(() => (
  typeof navigationSelection.value === 'number'
    ? selectedNavigationEntry.value?.managed_root_id ?? null
    : null
));
const navigationRootFolders = computed(() => navigationFolders.value.filter((folder) => {
  if (folder.id === suppressedManagedRootId.value) return false;
  if (folder.parent === suppressedManagedRootId.value) return true;
  return folder.parent == null || !navigationFolderIds.value.has(folder.parent);
}));

// La API ya aplica carpeta, raíz contextual, asociaciones, estado y búsqueda
// antes de paginar. Refiltrar aquí rompería el total autoritativo del servidor.
const filteredDocuments = computed(() => (
  isSearching.value ? documentStore.searchResults : documentStore.documents
));

// Filas de carpeta del listado: las raíces del scope en la cima, las hijas
// dentro de una carpeta, y las coincidencias mientras se busca.
const currentSubfolders = computed(() => {
  if (isSearching.value) return searchFolders.value;
  const id = documentStore.activeFolderId;
  if (id === 'root' && navigationSelection.value !== 'all') {
    return navigationRootFolders.value;
  }
  if (id === 'root') return folderStore.scopedRootFolders(effectiveScope.value);
  if (typeof id !== 'number') return [];
  const children = folderStore.childrenOf(id, effectiveScope.value);
  return navigationSelection.value === 'all'
    ? children
    : children.filter(folderMatchesNavigation);
});

const hasContent = computed(
  () => filteredDocuments.value.length > 0 || currentSubfolders.value.length > 0,
);

/**
 * Inventario de una fila de subcarpeta del listado.
 *
 * Es el mismo defecto del panel lateral un clic más adentro: entrar a «Familia»
 * y ver sus tres subcarpetas diciendo «Vacía» cuando entre las tres guardan 12.
 * Los documentos se cuentan del subárbol; las subcarpetas siguen siendo las
 * directas, que es lo que la fila promete si se hace clic.
 */
function subfolderSummary(folder, scope) {
  const { docs } = folderStore.rollupOf(folder, scope);
  return folderSummaryFrom({ docs, subs: scopedCounts(folder, scope).subs });
}

const docPage = ref(1);
const docPageSize = computed(() => (viewMode.value === 'grid' ? 12 : 10));
const activeDocPagination = computed(() => (
  isSearching.value ? documentStore.searchPagination : documentStore.browsePagination
));
const docTotalPages = computed(() => activeDocPagination.value.total_pages || 1);
const docTotalItems = computed(() => activeDocPagination.value.count || 0);
const docRangeFrom = computed(() => (
  docTotalItems.value ? ((docPage.value - 1) * docPageSize.value) + 1 : 0
));
const docRangeTo = computed(() => Math.min(
  docPage.value * docPageSize.value,
  docTotalItems.value,
));
const pagedDocuments = filteredDocuments;
documentStore.browsePageSize = docPageSize.value;

let filterQuery;
let managerMounted = false;

function resetDocumentListPosition() {
  if (filterQuery?.isApplyingQuery.value) return;
  focusedDocumentId.value = null;
  docPage.value = 1;
}

// 12 divides evenly into the 2/3/4-column grid; 10 matches the table rhythm.
watch(viewMode, async () => {
  documentStore.browsePageSize = docPageSize.value;
  resetDocumentListPosition();
  if (managerMounted && !filterQuery?.isApplyingQuery.value) {
    await fetchCurrentDocumentPage(1);
  }
});

watch(searchQuery, resetDocumentListPosition);
watch(dateOrder, resetDocumentListPosition);
watch(() => documentStore.activeFolderId, resetDocumentListPosition);
watch(() => documentStore.archiveScope, resetDocumentListPosition);
watch(() => documentStore.activeStateIds, resetDocumentListPosition, { deep: true });
watch(() => documentStore.withoutStateIds, resetDocumentListPosition, { deep: true });
watch(() => documentStore.activeStatePreset, resetDocumentListPosition);
watch(() => documentStore.activeClientId, resetDocumentListPosition);
watch(() => documentStore.activeProjectId, resetDocumentListPosition);

async function goToDocumentPage(page) {
  focusedDocumentId.value = null;
  await fetchCurrentDocumentPage(page);
}

function goToNextDocumentPage() {
  return goToDocumentPage(Math.min(docPage.value + 1, docTotalPages.value));
}

function goToPreviousDocumentPage() {
  return goToDocumentPage(Math.max(docPage.value - 1, 1));
}

// ── Búsqueda global ──────────────────────────────────────────────────────────
// Recorre todo el gestor y los dos estados: buscar sirve para encontrar algo
// cuya ubicación no se recuerda, y acotarlo a la vista era justo lo que impedía
// dar con lo archivado.
const searchFolders = ref([]);
let searchTimer = null;
let skipNextSearchClearFetch = false;

async function runSearch(term, { page = docPage.value } = {}) {
  const includeFolders = page === 1;
  const [docs, folders] = await Promise.all([
    documentStore.searchDocuments(term, {
      order: documentStore.dateOrder,
      page,
      pageSize: docPageSize.value,
    }),
    includeFolders ? folderStore.searchFolders(term) : Promise.resolve({ data: [] }),
  ]);
  searchFolders.value = folders.data || [];
  if (docs.success) {
    docPage.value = docs.data.page;
  } else if (!docs.cancelled) {
    notify.error({ title: 'No se pudo completar la búsqueda', detail: docs.message });
  }
  return docs;
}

watch(searchQuery, (value) => {
  clearTimeout(searchTimer);
  // La hidratación desde la URL tiene su propio camino de carga: disparar el
  // debounce acá duplicaría la búsqueda al entrar o usar atrás/adelante.
  if (filterQuery?.isApplyingQuery.value) return;
  const term = value.trim();
  if (!term) {
    searchFolders.value = [];
    documentStore.cancelDocumentSearch();
    if (skipNextSearchClearFetch) {
      skipNextSearchClearFetch = false;
    } else if (managerMounted) {
      fetchCurrentDocumentPage(1);
    }
    return;
  }
  // Los resultados de la búsqueda anterior no sobreviven al debounce: verlos
  // mientras se escribe otro término los hace pasar por resultados nuevos.
  documentStore.searchResults = [];
  searchFolders.value = [];
  documentStore.isSearchLoading = true;
  searchTimer = setTimeout(() => runSearch(term, { page: 1 }), 300);
});

/**
 * Sale de la búsqueda y navega en un solo gesto.
 *
 * Como la búsqueda ya no muta el scope de origen, navegar desde un resultado
 * sólo limpia `q` y cambia explícitamente los ejes pedidos.
 */
function exitSearchAndNavigate({ folder, scope, client, project } = {}) {
  clearTimeout(searchTimer);
  searchFolders.value = [];
  documentStore.cancelDocumentSearch();
  skipNextSearchClearFetch = true;
  searchQuery.value = '';
  return documentStore.setBrowseFilters({
    folder,
    scope: scope ?? documentStore.archiveScope,
    client,
    project,
  });
}

onBeforeUnmount(() => {
  clearTimeout(searchTimer);
  clearTimeout(newlyCreatedTimer);
  documentStore.cancelDocumentBrowse();
  documentStore.cancelDocumentSearch();
});

const showFolderManager = ref(false);
const showFolderDrawer = ref(false);
const showFolderForm = ref(false);
const editingFolder = ref(null);
const showFolderCascade = ref(false);
const cascadeFolder = ref(null);
const cascadeClientId = ref(null);
const deletingFolder = ref(null);
const movingDoc = ref(null);
const renamingDoc = ref(null);
const emailingDoc = ref(null);
const threadDoc = ref(null);
const showThreadIndex = ref(false);
const actionDoc = ref(null);
const draggingDoc = ref(null);
const draggingFolder = ref(null);
const dragOverFolderId = ref(null);
const showMoveModal = computed({
  get: () => !!movingDoc.value,
  set: (v) => { if (!v) movingDoc.value = null; },
});
const showRenameModal = computed({
  get: () => !!renamingDoc.value,
  set: (v) => { if (!v) renamingDoc.value = null; },
});
const showEmailModal = computed({
  get: () => !!emailingDoc.value,
  set: (v) => { if (!v) emailingDoc.value = null; },
});
const showThreadModal = computed({
  get: () => !!threadDoc.value,
  set: (v) => { if (!v) threadDoc.value = null; },
});
const showActionsSheet = computed({
  get: () => !!actionDoc.value,
  set: (v) => { if (!v) actionDoc.value = null; },
});
const showDeleteFolderModal = computed({
  get: () => !!deletingFolder.value,
  set: (v) => { if (!v) deletingFolder.value = null; },
});

const createLink = computed(() => {
  const folder = documentStore.activeFolderId;
  if (folder && folder !== 'all' && folder !== 'root' && folder !== 'none') {
    return localePath(`/panel/documents/create?folder=${folder}`);
  }
  return localePath('/panel/documents/create');
});

// La búsqueda comparte el skeleton de la lista: sin esto no tenía ningún
// indicador de carga y los 300 ms de debounce parecían un buscador roto.
const isListLoading = computed(
  () => (isSearching.value
    ? documentStore.isSearchLoading
    : documentStore.isBrowseLoading),
);
const hasStateFilters = computed(() => (
  documentStore.activeStateIds.length > 0
  || documentStore.withoutStateIds.length > 0
  || !!documentStore.activeStatePreset
));

const loadError = ref(null);

async function fetchBrowsePage(page = docPage.value) {
  loadError.value = null;
  const result = await documentStore.browseDocuments({
    scope: documentStore.archiveScope,
    order: documentStore.dateOrder,
    page,
    pageSize: docPageSize.value,
  });
  if (result.success) {
    docPage.value = result.data.page;
  } else if (!result.cancelled) {
    loadError.value = result.message || 'No se pudieron cargar los documentos.';
  }
  return result;
}

function fetchCurrentDocumentPage(page = docPage.value) {
  if (isSearching.value) {
    return runSearch(searchQuery.value.trim(), { page });
  }
  return fetchBrowsePage(page);
}

/**
 * Única ruta de refresco de la vista.
 *
 * Antes cada handler decidía qué refetchear, y por eso los contadores del panel
 * lateral quedaban desactualizados según por dónde se hubiera archivado. Con un
 * solo camino, ningún handler puede olvidarse de una de las tres piezas.
 */
async function refreshView({ states = false } = {}) {
  loadError.value = null;
  const documentsRequest = isSearching.value
    ? runSearch(searchQuery.value.trim(), { page: docPage.value })
    : fetchBrowsePage(docPage.value);
  const [docsResult] = await Promise.all([
    documentsRequest,
    folderStore.fetchFolders(),
    documentStore.fetchCounts(),
    navigationStore.fetchNavigation(),
    states ? stateStore.fetchCatalog() : Promise.resolve(),
  ]);
  if (docsResult && !docsResult.success && !docsResult.cancelled) {
    loadError.value = docsResult.message || 'No se pudieron cargar los documentos.';
  }
}

function loadDocuments() {
  return refreshView({ states: true });
}

async function restoreFocusedDocument() {
  const id = focusedDocumentId.value;
  if (!id || typeof document === 'undefined') return;
  await nextTick();
  const item = document.querySelector(
    `[data-testid="document-row-${id}"], [data-testid="document-card-${id}"]`,
  );
  if (!item) return;
  item.scrollIntoView?.({ block: 'center', behavior: 'auto' });
  const link = item.querySelector(
    `[data-testid="document-open-${id}"], [data-testid="document-card-open-${id}"]`,
  );
  link?.focus({ preventScroll: true });
}

async function handleQueryNavigation(summary) {
  clearTimeout(searchTimer);
  if (isSearching.value) {
    await runSearch(searchQuery.value.trim(), { page: docPage.value });
  } else {
    searchFolders.value = [];
    documentStore.cancelDocumentSearch();
    if (
      summary.filtersChanged
      || summary.searchChanged
      || summary.pageChanged
      || summary.viewChanged
    ) {
      await fetchBrowsePage(docPage.value);
    }
  }
  await restoreFocusedDocument();
}

// La URL describe la vista completa: filtros, búsqueda, modo, página y foco.
// Se aplica ANTES del primer fetch y el mismo contrato gobierna popstate.
filterQuery = useDocumentFilterQuery(documentStore, {
  searchQuery,
  viewMode,
  navigationMode,
  currentPage: docPage,
  focusedDocumentId,
  onNavigate: handleQueryNavigation,
});

onMounted(async () => {
  await navigationStore.fetchPreference();
  filterQuery.applyQueryToStore();
  documentStore.browsePageSize = docPageSize.value;
  await loadDocuments();
  if (!showInactiveProjects.value && selectedProjectIsInactive.value) {
    await handleSelectNavigationEntity('all');
  }
  // La carpeta del deep link ya no existe: se cae a Todos y se refetchea.
  if (filterQuery.validateFolder(folderStore)) {
    docPage.value = 1;
    await fetchBrowsePage(1);
  }
  managerMounted = true;
  await restoreFocusedDocument();
});
usePanelRefresh(loadDocuments);

async function handleNavigationModeChange(mode) {
  const result = await navigationStore.persistMode(mode);
  if (!result.success) {
    notify.error({
      title: 'No se pudo guardar el modo de navegación',
      detail: result.message,
    });
    return;
  }

  const selected = mode === 'project'
    ? documentStore.activeProjectId
    : documentStore.activeClientId;
  await documentStore.setBrowseFilters(navigationEntityFilters(
    mode,
    mode === 'project'
      && !showInactiveProjects.value
      && selectedProjectIsInactive.value
      ? 'all'
      : selected ?? 'all',
    documentStore.archiveScope,
  ));
}

function handleSelectNavigationEntity(value) {
  const filters = navigationEntityFilters(
    navigationMode.value,
    value,
    documentStore.archiveScope,
  );
  if (isSearching.value) return exitSearchAndNavigate(filters);
  return documentStore.setBrowseFilters(filters);
}

const selectedProjectIsInactive = computed(() => (
  navigationMode.value === 'project'
  && selectedNavigationEntry.value
  && (
    selectedNavigationEntry.value.catalog_bucket === 'archived'
    || selectedNavigationEntry.value.is_visible === false
  )
));

// El toggle es excluyente en ambos sentidos, así que cualquiera de los dos
// giros puede dejar fuera del listado al proyecto seleccionado. Sin soltar la
// selección, el listado seguiría filtrado por una fila que ya no se ve.
const selectedProjectHiddenByToggle = computed(() => (
  navigationMode.value === 'project'
  && Boolean(selectedNavigationEntry.value)
  && showInactiveProjects.value !== Boolean(selectedProjectIsInactive.value)
));

function handleToggleInactiveProjects(on) {
  showInactiveProjects.value = Boolean(on);
  if (selectedProjectHiddenByToggle.value) {
    return handleSelectNavigationEntity('all');
  }
  return undefined;
}

function selectNavigationEntityFromDrawer(value) {
  const result = handleSelectNavigationEntity(value);
  showFolderDrawer.value = false;
  return result;
}

function filtersForFolder(id) {
  return contextualFolderFilters({
    folderId: id,
    folder: typeof id === 'number' ? folderStore.folderById(id) : null,
    mode: navigationMode.value,
    selection: navigationSelection.value,
  });
}

function handleSelectFolder(id) {
  const filters = filtersForFolder(id);
  if (isSearching.value) {
    // Elegir una carpeta en plena búsqueda es navegación: se sale de la
    // búsqueda hacia esa carpeta. Antes el filtro cambiaba por debajo y la
    // vista seguía mostrando los resultados, como si el clic no hiciera nada.
    exitSearchAndNavigate(filters);
    return;
  }
  // Navegar entre carpetas NO toca el estado: el control de la barra dice qué
  // se está viendo y cambiarlo por debajo lo volvería mentiroso.
  documentStore.setBrowseFilters(filters);
}

function selectFolderFromDrawer(id) {
  handleSelectFolder(id);
  showFolderDrawer.value = false;
}

function openFolderManagerFromDrawer() {
  showFolderDrawer.value = false;
  openFolderManager();
}

function openFolderFormFromDrawer(folder) {
  showFolderDrawer.value = false;
  openFolderForm(folder);
}

function deleteFolderFromDrawer(folder) {
  showFolderDrawer.value = false;
  handleDeleteFolder(folder);
}

function archiveFolderFromDrawer(folder) {
  showFolderDrawer.value = false;
  handleArchiveFolder(folder);
}

function viewArchivedFolderFromDrawer(folder) {
  showFolderDrawer.value = false;
  handleViewArchivedFolder(folder);
}

/** Devuelve los dos ejes a su posición de reposo. */
function handleBackToActive() {
  documentStore.setBrowseFilters({ folder: 'all', scope: 'active' });
}

/**
 * Enciende y apaga el modo archivado.
 *
 * Cambiar de ámbito no mueve al usuario de sitio: dentro de una carpeta se
 * queda en ella y sólo cambia lo que se lista. Las dos vistas de cima sí se
 * traducen una en otra, porque no son la misma en cada ámbito: «Todos» es la
 * lista plana de activos y el archivo se recorre como árbol desde su raíz, que
 * es lo que conserva las carpetas como contenedores en vez de aplanarlas junto
 * a sus documentos.
 */
function handleToggleArchivedMode(on) {
  const folderId = documentStore.activeFolderId;
  let folder;
  if (on && folderId === 'all') folder = 'root';
  if (
    !on
    && folderId === 'root'
    && navigationSelection.value === 'all'
  ) folder = 'all';
  documentStore.setBrowseFilters({ folder, scope: on ? 'archived' : 'active' });
}

/** Entra a la carpeta en su scope archivado — el destino de la insignia. */
function handleViewArchivedFolder(folder) {
  if (!folder) return;
  exitSearchAndNavigate({ folder: folder.id, scope: 'archived' });
}

function handleScopeChange(scope) {
  documentStore.setBrowseFilters({ scope });
}

async function handleDateOrderChange(order) {
  if (!['recent', 'oldest'].includes(order) || order === documentStore.dateOrder) return;

  const result = isSearching.value
    ? await documentStore.searchDocuments(searchQuery.value.trim(), {
      order,
      page: 1,
      pageSize: docPageSize.value,
    })
    : await documentStore.browseDocuments({
      scope: documentStore.archiveScope,
      order,
      page: 1,
      pageSize: docPageSize.value,
    });

  if (result.success) {
    documentStore.dateOrder = order;
    docPage.value = result.data.page;
    return;
  }
  notify.error({
    title: 'No se pudo cambiar el orden',
    detail: result.message,
  });
}

function toggleDateOrder() {
  return handleDateOrderChange(nextDateOrder.value);
}

async function handleArchiveDoc(doc) {
  if (!doc) return;
  const result = await documentStore.archiveDocument(doc.id);
  if (result.success) {
    notify.success({ title: 'Documento archivado' });
    await refreshView();
  } else {
    notify.error({ title: 'No se pudo archivar el documento', detail: result.message });
  }
}

async function handleUnarchiveDoc(doc) {
  if (!doc) return;
  const result = await documentStore.unarchiveDocument(doc.id);
  if (result.success) {
    notify.success({
      title: 'Documento restaurado',
      detail: restoredChainDetail(result),
    });
    await refreshView();
  } else {
    notify.error({ title: 'No se pudo restaurar el documento', detail: result.message });
  }
}

/**
 * Explica la carpeta que volvió con el elemento.
 *
 * Restaurar reabre la cadena contenedora, y sin decirlo el usuario ve reaparecer
 * una carpeta que él había archivado sin entender por qué.
 */
function restoredChainDetail(result) {
  if (result.movedToRoot) {
    return 'No se pudo reconstruir su carpeta, así que quedó en «Sin carpeta».';
  }
  const chain = result.restoredChain || [];
  if (!chain.length) return undefined;
  const names = chain.map((f) => `«${f.name}»`).join(' › ');
  return `Se restauró también ${names} para que tenga dónde volver.`;
}

async function handleUnarchiveFolder(folder, { follow = false } = {}) {
  if (!folder) return;
  const result = await folderStore.unarchiveFolder(folder.id);
  if (result.success) {
    // Se reporta el conteo que devuelve la API, nunca "todo su contenido":
    // lo archivado a mano se queda archivado a propósito.
    const restored = result.restoredDocuments;
    const chainDetail = restoredChainDetail(result);
    const details = [
      restored ? `Se restauraron ${restored} documento(s) que archivó esta carpeta.` : null,
      chainDetail,
    ].filter(Boolean);
    notify.success({
      title: 'Carpeta restaurada',
      detail: details.length ? details.join(' ') : undefined,
    });
    // Seguir la restauración: la carpeta vuelve a los activos y la vista va
    // con ella, en vez de quedarse mirando su hueco en Archivados.
    if (follow) documentStore.archiveScope = 'active';
    await refreshView();
  } else {
    notify.error({
      title: 'No se pudo restaurar la carpeta',
      detail: result.message,
    });
  }
}

function handleArchiveFolder(folder) {
  if (!folder) return;
  requestConfirm({
    title: `Archivar "${folder.name}"`,
    // El aviso tiene que nombrar lo que la cascada se va a llevar, que es todo
    // el subárbol y no sólo lo que cuelga directo: archivar Vastago avisaba
    // «1 documento» antes de arrastrar 36.
    message: `Se archivará junto con su contenido (${folderSummaryFrom(folderStore.cascadeContentOf(folder))}). `
      + 'Sale de la vista y de los contadores, pero podrás restaurarla cuando quieras.',
    variant: 'warning',
    confirmText: 'Archivar',
    waitForConfirm: true,
    onConfirm: async () => {
      const result = await folderStore.archiveFolder(folder.id);
      if (!result.success) {
        notify.error({ title: 'No se pudo archivar la carpeta', detail: result.message });
        return;
      }
      notify.success({
        title: 'Carpeta archivada',
        detail: result.archivedDocuments
          ? `Se archivaron también ${result.archivedDocuments} documento(s).`
          : undefined,
      });
      exitFolderIfViewing(folder);
      await refreshView();
    },
  });
}

/**
 * ¿La vista actual está parada en esta carpeta o en una descendiente?
 *
 * El check de identidad se quedaba corto: archivar un ancestro desde el
 * sidebar dejaba al usuario dentro de una descendiente recién archivada,
 * viendo un empty state falso en una carpeta fantasma.
 */
function isViewingFolderOrDescendant(folderId) {
  const active = documentStore.activeFolderId;
  if (typeof active !== 'number') return false;
  return active === folderId || folderStore.descendantIdsOf(folderId).has(active);
}

/** Destino al retirarse de una carpeta que dejó de existir: su padre, o Todos. */
function folderExitTarget(folder) {
  return folder?.parent ?? 'all';
}

/**
 * Retira la vista ANTES del refreshView del caller: la escritura directa no
 * dispara fetch propio, así el refresco llega ya apuntando al destino y no
 * parpadea un empty state falso de la carpeta que acaba de irse.
 */
function exitFolderIfViewing(folder) {
  if (folder && isViewingFolderOrDescendant(folder.id)) {
    documentStore.activeFolderId = folderExitTarget(folder);
  }
}

async function applyStateFilter(change) {
  loadError.value = null;
  const result = await change();
  if (!result?.success) {
    loadError.value = result?.message || 'No se pudieron aplicar los filtros de estado.';
  }
}

function handleToggleState(id) {
  return applyStateFilter(() => documentStore.toggleBrowseStateFilter(id));
}

function handleToggleStateAbsence(id) {
  return applyStateFilter(() => documentStore.toggleBrowseStateAbsenceFilter(id));
}

function handleStatePreset(value) {
  return applyStateFilter(() => documentStore.setBrowseStatePreset(value));
}

function handleClearStateFilters() {
  return applyStateFilter(() => documentStore.setBrowseFilters({
    states: [], withoutStates: [], preset: '',
  }));
}

function handleClientFilter(value) {
  documentStore.setBrowseFilters({ client: value });
}

function handleProjectFilter(value) {
  documentStore.setBrowseFilters({ project: value });
}

// Label para rehidratar el autocomplete en un deep link (?client=<id>): se
// resuelve de las filas ya cargadas para no gastar un fetch extra; sin filas
// el fallback numérico al menos dice QUÉ filtro está puesto.
const associationClientLabel = computed(() => {
  const id = documentStore.activeClientId;
  if (typeof id !== 'number') return '';
  const row = documentStore.documents.find((d) => d.client === id);
  return row?.client_display_name || `Cliente #${id}`;
});

/** Editar la carpeta desde donde se la está usando: su fila o su cabecera. */
function openFolderForm(folder) {
  editingFolder.value = folder;
  showFolderForm.value = true;
}

/**
 * Cambiar de cliente una carpeta CON contenido no lo resuelve el formulario:
 * el backend responde 409 y el camino es la cascada, que sí sabe decir a qué
 * afecta antes de confirmar.
 */
function openFolderCascade({ folder, clientProfileId }) {
  showFolderForm.value = false;
  cascadeFolder.value = folder;
  cascadeClientId.value = clientProfileId ?? null;
  showFolderCascade.value = true;
}

async function handleFolderClientChanged() {
  showFolderCascade.value = false;
  await handleFoldersChanged();
}

function openFolderManager() {
  showFolderManager.value = true;
}

function handleDeleteFolder(folder) {
  if (!folder) return;
  deletingFolder.value = folder;
}

async function handleFolderArchived({ folder, documents } = {}) {
  notify.success({
    title: 'Carpeta archivada',
    detail: documents
      ? `Se archivaron también ${documents} documento(s).`
      : undefined,
  });
  exitFolderIfViewing(folder);
  await refreshView();
}

async function handleFolderDeleted(folder) {
  notify.success({ title: 'Carpeta eliminada' });
  // La carpeta borrada era el filtro activo: no queda vista que mostrar.
  exitFolderIfViewing(folder);
  await refreshView();
}

function handleFoldersChanged() {
  return refreshView();
}

function handleMoveDoc(doc) {
  movingDoc.value = doc;
}

function handleMoved() {
  return refreshView();
}

// Fuente única de la dirección: la lee el <a> del título de cada fila/tarjeta
// y la lee el atajo de clic, así que no pueden apuntar a lugares distintos.
function editToFor(doc) {
  if (!doc) return null;
  const origin = documentOriginWithFocus(route, router, doc.id);
  return localePath({
    path: `/panel/documents/${doc.id}/edit`,
    query: { from: origin },
  });
}

/**
 * Dirección de una subcarpeta. Existe desde antes — `?folder=` ya es deep link
 * (useDocumentFilterQuery) —, sólo que ninguna fila la publicaba.
 *
 * Devuelve null durante una búsqueda: ahí entrar a una carpeta significa salir
 * de la búsqueda hacia ella, y eso no lo puede expresar un cambio de query.
 */
function folderToFor(sub) {
  if (!sub || isSearching.value) return null;
  const filters = filtersForFolder(sub.id);
  const query = { ...route.query };
  delete query.page;
  delete query.focus;
  query.folder = String(sub.id);
  if (filters.project == null) delete query.project;
  else query.project = String(filters.project);
  if (filters.client == null) delete query.client;
  else query.client = String(filters.client);
  return localePath({ path: '/panel/documents', query });
}

function handleEditDoc(doc) {
  openRow(editToFor(doc));
}

// El evento decide: clic simple navega acá, ctrl/cmd o rueda abren pestaña
// nueva, y un clic nacido en un control de la fila no navega en absoluto.
function openDocument(doc, event) {
  openRow(editToFor(doc), event);
}

function handleRenameDoc(doc) {
  renamingDoc.value = doc;
}

function handleRenamed() {
  return refreshView();
}

function handleSendEmail(doc) {
  emailingDoc.value = doc;
}

function handleOpenThread(doc) {
  if (doc) threadDoc.value = doc;
}

// Dos modales de workspace apilados no se turnan: el índice queda encima y se
// come los clics del hilo. El índice cede el paso y se reabre desde «Hilos».
function handleOpenThreadFromIndex(doc) {
  showThreadIndex.value = false;
  handleOpenThread(doc);
}

async function handleThreadSaved() {
  await refreshView();
  if (threadDoc.value) {
    threadDoc.value = documentStore.documents.find(
      item => item.id === threadDoc.value.id,
    ) || threadDoc.value;
  }
}

function handleDragStart(event, doc) {
  draggingDoc.value = doc;
  // Sin setData, Firefox no inicia el drag nativo (no dispara dragover/drop).
  event.dataTransfer.setData('text/plain', `doc:${doc.id}`);
  event.dataTransfer.effectAllowed = 'move';
}

function handleDragEnd() {
  draggingDoc.value = null;
}

function handleFolderDragStart(event, folder) {
  draggingFolder.value = folder;
  event.dataTransfer.setData('text/plain', `folder:${folder.id}`);
  event.dataTransfer.effectAllowed = 'move';
}

function handleFolderDragEnd() {
  draggingFolder.value = null;
  dragOverFolderId.value = null;
}

// ¿La carpeta en arrastre puede soltarse sobre este destino sin crear un ciclo?
function canDropFolderOn(destId) {
  const folder = draggingFolder.value;
  if (!folder) return false;
  if (destId === folder.id) return false;
  if (destId != null && folderStore.descendantIdsOf(folder.id).has(destId)) return false;
  // Soltar algo activo dentro de una carpeta archivada lo dejaría sin ubicación
  // alcanzable; el backend además lo rechaza con 400.
  if (destId != null && folderStore.folderById(destId)?.is_archived) return false;
  return true;
}

function onFolderRowDragOver(event, folderId) {
  if (draggingDoc.value || canDropFolderOn(folderId)) {
    event.preventDefault();
    dragOverFolderId.value = folderId;
  }
}

// Reasigna el padre de una carpeta (drag-to-nest). destId null = carpeta raíz.
async function reparentFolder(folder, destId) {
  if (!folder) return;
  if (destId === folder.id) return;
  if (destId != null && folderStore.descendantIdsOf(folder.id).has(destId)) return;
  if ((folder.parent ?? null) === (destId ?? null)) return;
  const result = await folderStore.updateFolder(folder.id, { parent: destId });
  if (result.success) {
    await refreshView();
  } else {
    notify.error({ title: 'No se pudo mover la carpeta' });
  }
}

function handleNestFolder({ destId, draggedFolderId }) {
  draggingFolder.value = null;
  dragOverFolderId.value = null;
  return reparentFolder(folderStore.folderById(draggedFolderId), destId);
}

async function handleDropOnFolder(folderId) {
  dragOverFolderId.value = null;
  const folder = draggingFolder.value;
  if (folder) {
    draggingFolder.value = null;
    await reparentFolder(folder, folderId);
    return;
  }
  if (!draggingDoc.value) return;
  const doc = draggingDoc.value;
  draggingDoc.value = null;
  if (doc.folder === folderId) return;
  const result = await documentStore.updateDocument(doc.id, { folder_id: folderId });
  if (result.success) {
    const folderName = folderStore.folderById(folderId)?.name;
    notify.success({ title: folderName ? `Documento movido a "${folderName}"` : 'Documento movido' });
  } else {
    notify.error({ title: 'No se pudo mover el documento', detail: result.message });
  }
  await refreshView();
}

async function handleDownloadPdf(doc, template = null) {
  const result = await documentStore.downloadPdf(doc.id, doc.title || 'document', template);
  if (!result.success) {
    notify.error({ title: 'No se pudo descargar el PDF', detail: result.message });
  }
}

async function handleDuplicate(id) {
  const result = await documentStore.duplicateDocument(id);
  if (!result.success) {
    notify.error({ title: 'No se pudo duplicar el documento', detail: result.message });
    return;
  }
  notify.success({ title: 'Documento duplicado' });
  clearTimeout(newlyCreatedTimer);
  docPage.value = 1;
  await refreshView();
  newlyCreatedId.value = result.data.id;
  newlyCreatedTimer = setTimeout(() => { newlyCreatedId.value = null; }, 2500);
  // The duplicate lands at the top of the list; bring it into view.
  window.scrollTo({ top: 0, behavior: reducedMotion.value ? 'auto' : 'smooth' });
}

async function handleCopyMarkdown(id) {
  const result = await documentStore.getDocumentMarkdown(id);
  if (!result.success) {
    notify.error({ title: 'No se pudo obtener el markdown', detail: result.message });
    return;
  }
  try {
    await navigator.clipboard.writeText(result.markdown);
    notify.success('Markdown copiado al portapapeles');
  } catch {
    notify.error({
      title: 'No se pudo copiar al portapapeles',
      detail: 'Tu navegador bloqueó el acceso al portapapeles.',
    });
  }
}

function handleDelete(doc) {
  if (!doc) return;
  // Ya archivado: no hay salida alternativa que ofrecer.
  const alreadyArchived = !!doc.is_archived;
  requestConfirm({
    title: 'Eliminar documento',
    message: `Se eliminará permanentemente "${doc.title}". Esta acción no se puede deshacer.`,
    variant: 'danger',
    confirmText: 'Eliminar',
    requireTypeText: 'DELETE',
    secondaryText: alreadyArchived ? '' : 'Archivar en su lugar',
    secondaryHint: alreadyArchived
      ? ''
      : 'Archivar lo saca de la lista y de los contadores, pero lo conserva: podrás consultarlo o restaurarlo desde Archivados.',
    onSecondary: () => handleArchiveDoc(doc),
    waitForConfirm: true,
    onConfirm: async () => {
      const result = await documentStore.deleteDocument(doc.id);
      if (result.success) {
        notify.success({ title: 'Documento eliminado' });
      } else {
        notify.error({ title: 'No se pudo eliminar el documento', detail: result.message });
      }
      // También al eliminar: los contadores de carpeta salen del backend y sin
      // esto la fila desaparece pero el número de al lado se queda viejo.
      await refreshView();
    },
  });
}
</script>

<style scoped>
/* Staggered fade-up entrance, CSS-driven like the accounting dashboard:
 * the list loads async, so the animation must not depend on JS timing. */
@keyframes documents-enter {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
}
[data-enter] {
  animation: documents-enter 0.45s ease-out both;
  animation-delay: var(--enter-delay, 0ms);
}

/* List <-> gallery swap: quick fade + settle, out-in so layouts never overlap. */
.view-swap-enter-active,
.view-swap-leave-active {
  transition: opacity 150ms cubic-bezier(0.22, 1, 0.36, 1),
              transform 150ms cubic-bezier(0.22, 1, 0.36, 1);
}
.view-swap-enter-from,
.view-swap-leave-to {
  opacity: 0;
  transform: scale(0.98);
}

@media (prefers-reduced-motion: reduce) {
  [data-enter] {
    animation: none;
  }
  .view-swap-enter-active,
  .view-swap-leave-active {
    transition: none;
  }
}
</style>
