<template>
  <div>
    <!-- Before ConfirmModal: modals stack in template order, so the
         confirmation an entry opens lands above this fading menu. -->
    <BaseRowActionsModal
      :open="actionsRow !== null"
      :title="actionsRow?.title_es || ''"
      :items="actionsRow ? blogActionItems(actionsRow) : []"
      testid="blog-post-actions-modal"
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
    <div class="mb-8 flex flex-col gap-3 panel-portrait:flex-row panel-portrait:items-center panel-portrait:justify-between">
      <h1 class="text-2xl font-light text-text-default">Blog Posts</h1>
      <div class="flex w-full items-center gap-2 panel-portrait:w-auto panel-portrait:gap-3">
        <BaseButton
          as="NuxtLink"
          variant="secondary"
          size="md"
          :to="localePath('/panel/blog/calendar')"
          class="flex-1 justify-center panel-portrait:flex-initial"
        >
          <BaseActionIcon action="calendar" />
          Calendario
        </BaseButton>
        <BaseButton
          as="NuxtLink"
          variant="primary"
          size="md"
          :to="localePath('/panel/blog/create')"
          class="flex-1 justify-center panel-portrait:flex-initial"
        >
          <BaseActionIcon action="create" />
          Nuevo Post
        </BaseButton>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="blogStore.isLoading" class="flex justify-center py-12">
      <div class="w-6 h-6 border-2 border-focus-ring/30 border-t-focus-ring rounded-full animate-spin" />
    </div>

    <!-- Table (desktop) / Cards (mobile) -->
    <div v-else>
      <div v-if="posts.length === 0" class="bg-surface rounded-xl shadow-sm border border-border-muted px-6 py-12 text-center text-text-subtle text-sm">
        No hay posts aún. Crea el primero.
      </div>

      <BaseExploratoryList
        v-else
        :columns="blogColumns"
        :rows="posts"
        caption="Publicaciones del blog"
        card-test-id-prefix="blog-post-row"
        row-actions-layout="menu-start"
      >
        <template #cell-title_es="{ row: post }">
          <NuxtLink
            :to="localePath(`/panel/blog/${post.id}/edit`)"
            class="block min-w-0 max-w-full text-sm font-medium leading-tight text-text-default [overflow-wrap:anywhere] transition-colors hover:text-text-brand"
          >{{ post.title_es }}</NuxtLink>
          <p class="mt-0.5 min-w-0 max-w-full text-xs text-text-subtle [overflow-wrap:anywhere]">{{ post.title_en }} · {{ post.slug }}</p>
        </template>
        <template #cell-status="{ row: post }">
          <span class="inline-flex rounded-full px-2.5 py-1 text-xs font-medium" :class="statusBadgeClass(post)">{{ statusLabel(post) }}</span>
        </template>
        <template #cell-date="{ row: post }">{{ formatDate(post.published_at || post.created_at) }}</template>
        <template #row-actions="{ row: post }">
          <BaseActionButton
            action="more"
            class="h-11 w-11 shrink-0"
            :label="`Acciones de ${post.title_es}`"
            :data-testid="`blog-post-actions-${post.id}`"
            @click.stop="actionsRow = post"
          />
        </template>
      </BaseExploratoryList>

      <!-- Pagination controls -->
      <BasePagination
        v-if="blogStore.adminPagination.totalPages > 1"
        :current-page="blogStore.adminPagination.page"
        :total-pages="blogStore.adminPagination.totalPages"
        :total-items="blogStore.adminPagination.count"
        :range-from="blogRangeFrom"
        :range-to="blogRangeTo"
        class="px-4 panel-portrait:px-6"
        @prev="goToPage(blogStore.adminPagination.page - 1)"
        @next="goToPage(blogStore.adminPagination.page + 1)"
        @go="goToPage"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useBlogStore } from '~/stores/blog';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import BasePagination from '~/components/base/BasePagination.vue';
import BaseActionButton from '~/components/base/BaseActionButton.vue';
import BaseExploratoryList from '~/components/base/BaseExploratoryList.vue';
import BaseRowActionsModal from '~/components/base/BaseRowActionsModal.vue';
import { formatDate } from '~/utils/formatDate';

const localePath = useLocalePath();

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const blogStore = useBlogStore();
const posts = computed(() => blogStore.posts);
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();
const actionsRow = ref(null);
const blogColumns = [
  { key: 'title_es', label: 'Título', mobile: 'primary' },
  { key: 'status', label: 'Estado', mobile: 'secondary' },
  { key: 'date', label: 'Fecha', mobile: 'meta' },
];

function blogActionItems(post) {
  return [
    { action: 'edit', label: 'Editar', to: localePath(`/panel/blog/${post.id}/edit`), testid: `blog-post-edit-${post.id}` },
    { action: 'duplicate', label: 'Duplicar', onClick: () => handleDuplicate(post), testid: `blog-post-duplicate-${post.id}` },
    { divider: true },
    { action: 'delete', label: 'Eliminar', danger: true, onClick: () => handleDelete(post), testid: `blog-post-delete-${post.id}` },
  ];
}

const blogRangeFrom = computed(() => {
  const p = blogStore.adminPagination;
  if (!p.count) return 0;
  return (p.page - 1) * (p.pageSize || 20) + 1;
});
const blogRangeTo = computed(() => {
  const p = blogStore.adminPagination;
  return Math.min(p.page * (p.pageSize || 20), p.count || 0);
});

const visiblePages = computed(() => {
  const total = blogStore.adminPagination.totalPages;
  const current = blogStore.adminPagination.page;
  const pages = [];
  const start = Math.max(1, current - 2);
  const end = Math.min(total, current + 2);
  for (let i = start; i <= end; i++) pages.push(i);
  return pages;
});

function goToPage(page) {
  if (page < 1 || page > blogStore.adminPagination.totalPages) return;
  blogStore.fetchAdminPosts(page);
}

function refreshAdminPosts() {
  return blogStore.fetchAdminPosts(blogStore.adminPagination.page || 1);
}

onMounted(() => {
  blogStore.fetchAdminPosts();
});

usePanelRefresh(refreshAdminPosts);

function isScheduled(post) {
  return !post.is_published && post.published_at && new Date(post.published_at) > new Date();
}

function statusLabel(post) {
  if (post.is_published) return 'Publicado';
  if (isScheduled(post)) return `Programado: ${formatDate(post.published_at)}`;
  return 'Borrador';
}

function statusBadgeClass(post) {
  if (post.is_published) return 'bg-primary-soft text-text-brand';
  if (isScheduled(post)) return 'bg-info-soft text-info-strong';
  return 'bg-surface-raised text-text-muted';
}

function handleDuplicate(post) {
  requestConfirm({
    title: 'Duplicar post',
    message: `¿Duplicar "${post.title_es}"?`,
    variant: 'info',
    confirmText: 'Duplicar',
    // Refetch igual que al eliminar: la lista viene paginada del servidor, y
    // encajar la copia en el array local dejaba la página con una fila de más
    // y el total sin actualizar.
    onConfirm: async () => {
      await blogStore.duplicatePost(post.id);
      await blogStore.fetchAdminPosts(blogStore.adminPagination.page);
    },
  });
}

function handleDelete(post) {
  requestConfirm({
    title: 'Eliminar post',
    message: `¿Eliminar "${post.title_es}"?`,
    variant: 'danger',
    confirmText: 'Eliminar',
    onConfirm: async () => {
      await blogStore.deletePost(post.id);
      blogStore.fetchAdminPosts(blogStore.adminPagination.page);
    },
  });
}
</script>
