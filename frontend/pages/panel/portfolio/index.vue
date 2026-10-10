<template>
  <div>
    <!-- Before ConfirmModal: modals stack in template order, so the
         confirmation an entry opens lands above this fading menu. -->
    <BaseRowActionsModal
      :open="actionsRow !== null"
      :title="actionsRow?.title_es || ''"
      :items="actionsRow ? portfolioActionItems(actionsRow) : []"
      testid="portfolio-work-actions-modal"
      @close="actionsRow = null"
    />
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
    <div class="mb-8 flex flex-col items-start gap-3 panel-portrait:flex-row panel-portrait:items-center panel-portrait:justify-between">
      <h1 class="text-2xl font-light text-text-default">Portfolio Works</h1>
      <BaseButton
        as="NuxtLink"
        variant="primary"
        size="md"
        :to="localePath('/panel/portfolio/create')"
      >
        <BaseActionIcon action="create" />
        Nuevo Proyecto
      </BaseButton>
    </div>

    <!-- Loading -->
    <div v-if="portfolioStore.isLoading" class="flex justify-center py-12">
      <div class="w-6 h-6 border-2 border-focus-ring/30 border-t-focus-ring rounded-full animate-spin" />
    </div>

    <div v-else>
      <div v-if="works.length === 0" class="bg-surface rounded-xl shadow-sm border border-border-muted px-6 py-12 text-center text-text-subtle text-sm">
        No hay proyectos aún. Crea el primero.
      </div>

      <BaseExploratoryList
        v-else
        :columns="portfolioColumns"
        :rows="pagedWorks"
        caption="Trabajos del portafolio"
        card-test-id-prefix="portfolio-work-row"
        row-actions-layout="menu-start"
      >
        <template #cell-title_es="{ row: work }">
          <NuxtLink :to="localePath(`/panel/portfolio/${work.id}/edit`)" class="block min-w-0 max-w-full text-sm font-medium leading-tight text-text-default [overflow-wrap:anywhere] transition-colors hover:text-text-brand">{{ work.title_es }}</NuxtLink>
          <p class="mt-0.5 min-w-0 max-w-full text-xs text-text-subtle [overflow-wrap:anywhere]">{{ work.title_en }} · {{ work.slug }}</p>
        </template>
        <template #cell-status="{ row: work }">
          <span class="inline-flex rounded-full px-2.5 py-1 text-xs font-medium" :class="statusBadgeClass(work)">{{ statusLabel(work) }}</span>
        </template>
        <template #cell-date="{ row: work }">{{ formatDate(work.published_at || work.created_at) }}</template>
        <template #row-actions="{ row: work }">
          <BaseActionButton
            action="more"
            class="h-11 w-11 shrink-0"
            :label="`Acciones de ${work.title_es}`"
            :data-testid="`portfolio-work-actions-${work.id}`"
            @click.stop="actionsRow = work"
          />
        </template>
      </BaseExploratoryList>

      <BasePagination
        v-if="works.length > 0"
        :current-page="worksPage"
        :total-pages="worksTotalPages"
        :total-items="worksTotalItems"
        :range-from="worksRangeFrom"
        :range-to="worksRangeTo"
        class="mt-4"
        @prev="worksPrev"
        @next="worksNext"
        @go="worksGoTo"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { usePortfolioWorksStore } from '~/stores/portfolio_works';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import BasePagination from '~/components/base/BasePagination.vue';
import BaseActionButton from '~/components/base/BaseActionButton.vue';
import BaseExploratoryList from '~/components/base/BaseExploratoryList.vue';
import BaseRowActionsModal from '~/components/base/BaseRowActionsModal.vue';
import { usePagination } from '~/composables/usePagination';
import { formatDate } from '~/utils/formatDate';

const localePath = useLocalePath();

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const portfolioStore = usePortfolioWorksStore();
const works = computed(() => portfolioStore.works);
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();
const actionsRow = ref(null);
const portfolioColumns = [
  { key: 'title_es', label: 'Título', mobile: 'primary' },
  { key: 'status', label: 'Estado', mobile: 'secondary' },
  { key: 'order', label: 'Orden', mobile: 'meta' },
  { key: 'date', label: 'Fecha', mobile: 'meta' },
];

function portfolioActionItems(work) {
  return [
    { action: 'edit', label: 'Editar', to: localePath(`/panel/portfolio/${work.id}/edit`), testid: `portfolio-work-edit-${work.id}` },
    { action: 'duplicate', label: 'Duplicar', onClick: () => handleDuplicate(work), testid: `portfolio-work-duplicate-${work.id}` },
    { divider: true },
    { action: 'delete', label: 'Eliminar', danger: true, onClick: () => handleDelete(work), testid: `portfolio-work-delete-${work.id}` },
  ];
}

const {
  currentPage: worksPage,
  totalPages: worksTotalPages,
  totalItems: worksTotalItems,
  rangeFrom: worksRangeFrom,
  rangeTo: worksRangeTo,
  paginatedItems: pagedWorks,
  goTo: worksGoTo,
  next: worksNext,
  prev: worksPrev,
} = usePagination(works, { pageSize: 10 });

onMounted(() => { portfolioStore.fetchAdminWorks(); });
usePanelRefresh(() => portfolioStore.fetchAdminWorks());

function statusLabel(work) {
  return work.is_published ? 'Publicado' : 'Borrador';
}

function statusBadgeClass(work) {
  return work.is_published
    ? 'bg-primary-soft text-text-brand'
    : 'bg-surface-raised text-text-muted';
}

function handleDuplicate(work) {
  requestConfirm({
    title: 'Duplicar trabajo',
    message: `¿Duplicar "${work.title_es}"?`,
    variant: 'info',
    confirmText: 'Duplicar',
    onConfirm: () => portfolioStore.duplicateWork(work.id),
  });
}

function handleDelete(work) {
  requestConfirm({
    title: 'Eliminar trabajo',
    message: `¿Eliminar "${work.title_es}"?`,
    variant: 'danger',
    confirmText: 'Eliminar',
    onConfirm: () => portfolioStore.deleteWork(work.id),
  });
}
</script>
