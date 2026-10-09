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

    <header class="mb-8 flex flex-col gap-3 panel-portrait:flex-row panel-portrait:items-center panel-portrait:justify-between">
      <div>
        <h1 class="text-2xl font-semibold text-text-default">LinkedIn</h1>
        <p class="text-sm text-text-muted mt-1">
          Crea, programa y publica posts en tu perfil de LinkedIn.
        </p>
      </div>
      <BaseButton variant="primary" @click="openCreate">Nuevo post</BaseButton>
    </header>

    <!-- Connection card -->
    <section class="bg-surface border border-border-default rounded-xl p-5 mb-6">
      <div v-if="!connection.connected" class="flex flex-col gap-3 panel-portrait:flex-row panel-portrait:items-center">
        <span class="text-sm text-text-muted">LinkedIn no conectado.</span>
        <BaseButton variant="ghost" size="md" @click="connectLinkedIn">
          Conectar LinkedIn
        </BaseButton>
      </div>
      <div v-else class="space-y-1">
        <p class="text-sm text-text-default">
          Conectado como <strong>{{ connection.profile_name }}</strong>
          <button
            type="button"
            class="ml-3 text-xs text-text-brand hover:underline"
            @click="connectLinkedIn"
          >
            Reconectar
          </button>
        </p>
        <p
          v-if="connection.expires_at"
          class="text-xs"
          :class="expiresSoon ? 'text-danger-strong' : 'text-text-subtle'"
        >
          <template v-if="expiresSoon">⚠ </template>La conexión expira el {{ expiryDate }}
        </p>
      </div>
      <p v-if="actionMsg" class="text-sm text-text-brand mt-2">{{ actionMsg }}</p>
      <p v-if="actionError" class="text-sm text-danger-strong mt-2">{{ actionError }}</p>
    </section>

    <!-- Posts list -->
    <section>
      <p v-if="!loaded" class="text-sm text-text-muted">Cargando posts…</p>

      <div
        v-else-if="!posts.length"
        class="bg-surface border border-border-default rounded-xl p-8 text-center"
      >
        <p class="text-sm text-text-muted">
          Aún no hay posts de LinkedIn. Crea el primero con "Nuevo post".
        </p>
      </div>

      <BaseExploratoryList
        v-else
        :columns="linkedinColumns"
        :rows="posts"
        caption="Publicaciones de LinkedIn"
        card-test-id-prefix="linkedin-post-row"
      >
        <template #cell-commentary="{ row: post }">
          <p class="line-clamp-3 min-w-0 max-w-full text-sm text-text-default [overflow-wrap:anywhere]">{{ post.commentary }}</p>
          <p v-if="post.status === 'failed' && post.error_message" class="mt-1 truncate text-xs text-danger-strong" :title="post.error_message">{{ post.error_message }}</p>
        </template>
        <template #cell-status="{ row: post }"><span class="inline-flex rounded-full px-2 py-0.5 text-xs font-medium" :class="statusClass(post.status)">{{ statusLabel(post.status) }}</span></template>
        <template #cell-scheduled_at="{ row: post }">{{ post.scheduled_at ? formatDateTime(post.scheduled_at) : '—' }}</template>
        <template #cell-published_at="{ row: post }">
          <a v-if="post.status === 'published' && post.linkedin_post_id" :href="linkedinPostUrl(post)" target="_blank" rel="noopener noreferrer" class="text-text-brand hover:underline">{{ formatDateTime(post.published_at) }}</a>
          <span v-else>—</span>
        </template>
        <template #row-actions="{ row: post }">
          <BaseActionMenu :items="linkedinActionItems(post)" :testid="`linkedin-post-actions-${post.id}`" />
        </template>
      </BaseExploratoryList>
    </section>

    <!-- Create / edit modal -->
    <BaseModal v-model="showModal" kind="form">
      <form :id="modalFormId" novalidate @submit.prevent="savePost">
        <div class="space-y-4 px-6 py-5">
          <h2 class="text-lg font-semibold text-text-default">
            {{ editingPost ? 'Editar post' : 'Nuevo post' }}
          </h2>

          <BaseFormField
            v-slot="{ invalid, errorId }"
            label="Texto del post"
            required
            :error="formError"
          >
            <BaseTextarea
              v-model="form.commentary"
              :rows="6"
              maxlength="3000"
              placeholder="Escribe el contenido para LinkedIn (máx. 3000 caracteres)"
              :error="invalid"
              :aria-describedby="errorId"
              @update:model-value="formError = ''"
            />
            <p class="mt-1 text-xs text-text-subtle">{{ form.commentary.length }} / 3000</p>
          </BaseFormField>

          <BaseFormField label="Imagen">
          <input
            type="file"
            accept="image/*"
            class="block w-full text-sm text-text-muted file:mr-3 file:px-3 file:py-2 file:rounded-lg file:border-0 file:bg-surface-raised file:text-text-default file:text-sm file:cursor-pointer"
            @change="onFileChange"
          />
          <img
            v-if="imagePreview"
            :src="imagePreview"
            alt="Imagen del post"
            class="mt-2 max-h-40 rounded-lg border border-border-default"
          />
          </BaseFormField>

          <BaseFormRow
            :cols="2"
            :gap="4"
            help="Si queda vacío, el post se guarda como borrador."
            help-testid="linkedin-post-schedule-hint"
          >
            <BaseFormField label="Programar publicación">
              <BaseInput
                v-model="form.scheduledLocal"
                type="datetime-local"
              />
            </BaseFormField>
          </BaseFormRow>

          <BaseAlert v-if="formGeneralError" variant="danger">{{ formGeneralError }}</BaseAlert>
        </div>

      </form>
      <template #footer>
        <BaseModalActions>
          <BaseButton type="button" variant="ghost" @click="showModal = false">Cancelar</BaseButton>
          <BaseButton
            v-if="editingPost"
            type="button"
            variant="secondary"
            :loading="publishingId === editingPost.id"
            @click="askPublish(editingPost, true)"
          >
            Publicar ahora
          </BaseButton>
          <BaseButton type="submit" :form="modalFormId" variant="primary" :loading="saving">
            {{ form.scheduledLocal ? 'Programar' : 'Guardar' }}
          </BaseButton>
        </BaseModalActions>
      </template>
    </BaseModal>
  </div>
</template>

<script setup>
import { useId, computed, onMounted, onUnmounted, reactive, ref } from 'vue';
import { useLinkedInStore } from '~/stores/linkedin';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import ConfirmModal from '~/components/ConfirmModal.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import BaseActionMenu from '~/components/base/BaseActionMenu.vue';
import BaseExploratoryList from '~/components/base/BaseExploratoryList.vue';
import { formatDate, formatDateTime } from '~/utils/formatDate';

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const store = useLinkedInStore();
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();
const linkedinColumns = [
  { key: 'commentary', label: 'Texto', mobile: 'primary' },
  { key: 'status', label: 'Estado', mobile: 'secondary' },
  { key: 'scheduled_at', label: 'Programado', mobile: 'meta' },
  { key: 'published_at', label: 'Publicado', mobile: 'meta' },
];

const loaded = ref(false);
const posts = computed(() => store.posts);
const connection = computed(() => store.connectionStatus);

const showModal = ref(false);
const editingPost = ref(null);
const form = reactive({ commentary: '', scheduledLocal: '' });
const imageFile = ref(null);
const imagePreview = ref('');
const formError = ref('');
const formGeneralError = ref('');
const saving = ref(false);
const publishingId = ref(null);
const actionMsg = ref('');
const actionError = ref('');

function linkedinActionItems(post) {
  const items = [];
  if (post.status !== 'published') {
    items.push(
      { action: 'edit', label: 'Editar', onClick: () => openEdit(post) },
      {
        action: 'publish',
        label: publishingId.value === post.id ? 'Publicando…' : 'Publicar ahora',
        disabled: publishingId.value === post.id,
        description: publishingId.value === post.id ? 'La publicación ya está en curso.' : '',
        onClick: () => askPublish(post),
      },
    );
  } else if (post.linkedin_post_id) {
    items.push({ action: 'open-external', label: 'Ver en LinkedIn', href: linkedinPostUrl(post) });
  }
  items.push(
    { divider: true },
    { action: 'delete', label: 'Eliminar', danger: true, onClick: () => askDelete(post) },
  );
  return items;
}

async function loadData() {
  await Promise.all([store.fetchLinkedInStatus(), store.fetchPosts()]);
  loaded.value = true;
}

usePanelRefresh(loadData);

onMounted(async () => {
  window.addEventListener('message', handleLinkedInMessage);
  await loadData();
});

onUnmounted(() => {
  window.removeEventListener('message', handleLinkedInMessage);
});

function handleLinkedInMessage(event) {
  // Only trust messages from our own origin (the /auth/linkedin/callback popup)
  if (event.origin !== window.location.origin) return;
  if (event.data?.type === 'linkedin-connected') {
    store.connectionStatus = event.data.data || { connected: true };
    flashMessage('LinkedIn conectado correctamente.');
    store.fetchLinkedInStatus();
  }
}

async function connectLinkedIn() {
  const result = await store.fetchLinkedInAuthUrl();
  if (result.success && result.data?.authorization_url) {
    window.open(result.data.authorization_url, '_blank', 'width=600,height=700');
  } else {
    actionError.value = 'No se pudo obtener la URL de autorización.';
  }
}

// ── Expiry helpers ──

const expiryDate = computed(() => formatDate(connection.value.expires_at, { fallback: '' }));

const expiresSoon = computed(() => {
  if (!connection.value.expires_at) return false;
  const msLeft = new Date(connection.value.expires_at).getTime() - Date.now();
  return msLeft < 7 * 24 * 60 * 60 * 1000;
});

// ── Modal / form ──

function resetForm() {
  form.commentary = '';
  form.scheduledLocal = '';
  imageFile.value = null;
  imagePreview.value = '';
  formError.value = '';
  formGeneralError.value = '';
}

function openCreate() {
  resetForm();
  editingPost.value = null;
  showModal.value = true;
}

function openEdit(post) {
  resetForm();
  editingPost.value = post;
  form.commentary = post.commentary;
  form.scheduledLocal = post.scheduled_at ? isoToLocalInput(post.scheduled_at) : '';
  imagePreview.value = post.image || '';
  showModal.value = true;
}

function onFileChange(event) {
  const file = event.target.files?.[0];
  imageFile.value = file || null;
  imagePreview.value = file ? URL.createObjectURL(file) : (editingPost.value?.image || '');
}

function isoToLocalInput(iso) {
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function buildFormData() {
  const data = new FormData();
  data.append('commentary', form.commentary);
  data.append('scheduled_at', form.scheduledLocal ? new Date(form.scheduledLocal).toISOString() : '');
  if (imageFile.value) data.append('image', imageFile.value);
  return data;
}

function extractError(error) {
  if (!error) return 'Ocurrió un error. Intenta de nuevo.';
  if (typeof error === 'string') return error;
  if (error.error) return error.error;
  const firstKey = Object.keys(error)[0];
  const value = error[firstKey];
  return Array.isArray(value) ? value[0] : String(value);
}

async function savePost() {
  formError.value = '';
  formGeneralError.value = '';
  if (!form.commentary.trim()) {
    formError.value = 'Escribe el texto del post.';
    return;
  }
  saving.value = true;
  const payload = buildFormData();
  const result = editingPost.value
    ? await store.updatePost(editingPost.value.id, payload)
    : await store.createPost(payload);
  saving.value = false;

  if (!result.success) {
    const commentaryError = result.error?.commentary;
    formError.value = Array.isArray(commentaryError)
      ? commentaryError[0]
      : (typeof commentaryError === 'string' ? commentaryError : '');
    if (!formError.value) formGeneralError.value = extractError(result.error);
    return;
  }
  showModal.value = false;
  flashMessage(form.scheduledLocal ? 'Post programado.' : 'Post guardado.');
  await store.fetchPosts();
}

// ── Publish / delete ──

function askPublish(post, fromModal = false) {
  requestConfirm({
    title: 'Publicar en LinkedIn',
    message: 'El post se publicará inmediatamente en tu perfil de LinkedIn. ¿Continuar?',
    confirmText: 'Publicar',
    variant: 'warning',
    onConfirm: () => publishNow(post, fromModal),
  });
}

async function publishNow(post, fromModal = false) {
  actionError.value = '';
  publishingId.value = post.id;
  const result = await store.publishPost(post.id);
  publishingId.value = null;

  if (result.success) {
    if (fromModal) showModal.value = false;
    flashMessage('Publicado en LinkedIn correctamente.');
  } else {
    const msg = extractError(result.error);
    if (fromModal) {
      formError.value = msg;
    } else {
      actionError.value = msg;
    }
  }
  await store.fetchPosts();
}

function askDelete(post) {
  requestConfirm({
    title: 'Eliminar post',
    message: 'Se eliminará el registro local del post. Esta acción no borra nada en LinkedIn. ¿Continuar?',
    confirmText: 'Eliminar',
    variant: 'danger',
    onConfirm: () => removePost(post),
  });
}

async function removePost(post) {
  const result = await store.deletePost(post.id);
  if (result.success) {
    flashMessage('Post eliminado.');
  } else {
    actionError.value = extractError(result.error);
  }
  await store.fetchPosts();
}

// ── Display helpers ──

let msgTimeout = null;
function flashMessage(text) {
  actionMsg.value = text;
  clearTimeout(msgTimeout);
  msgTimeout = setTimeout(() => { actionMsg.value = ''; }, 5000);
}

function statusLabel(status) {
  return {
    draft: 'Borrador',
    scheduled: 'Programado',
    published: 'Publicado',
    failed: 'Fallido',
  }[status] || status;
}

function statusClass(status) {
  return {
    draft: 'bg-surface-muted text-text-muted',
    scheduled: 'bg-warning-soft text-warning-strong',
    published: 'bg-primary-soft text-text-brand',
    failed: 'bg-danger-soft text-danger-strong',
  }[status] || 'bg-surface-muted text-text-muted';
}

function linkedinPostUrl(post) {
  return `https://www.linkedin.com/feed/update/${post.linkedin_post_id}/`;
}

const modalFormId = useId();
</script>
