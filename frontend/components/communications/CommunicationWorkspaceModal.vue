<template>
  <BaseModal
    :model-value="modelValue"
    kind="workspace"
    full-height
    :close-on-backdrop="false"
    @update:model-value="handleOpenChange"
  >
    <div class="flex h-full min-h-0 flex-col" data-testid="communication-workspace">
      <header class="shrink-0 border-b border-border-muted bg-surface px-4 py-3 panel-portrait:px-6">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0 flex-1">
            <p class="text-xs font-semibold uppercase tracking-wider text-text-muted">{{ currentThread ? t('communicationFiling.threadId', { id: currentThread.id }) : 'Hilo de comunicación' }}</p>
            <template v-if="currentThread">
              <h2 class="mt-1 truncate text-xl font-semibold text-text-default" :title="currentThread.title">
                {{ currentThread.title }}
              </h2>
              <p class="mt-1 truncate text-sm text-text-muted">
                <NuxtLink
                  :to="{ path: '/panel/clients', query: { client: currentThread.client_id } }"
                  class="text-text-brand hover:underline"
                >
                  {{ currentThread.client_name }}
                </NuxtLink>
                <template v-if="currentThread.project_name"> · {{ currentThread.project_name }}</template>
                <template v-else> · Sin proyecto</template>
              </p>
            </template>
            <BaseSkeleton v-else-if="store.isThreadLoading" class="mt-2 h-8 max-w-xl rounded-lg" />
          </div>

          <div class="flex shrink-0 flex-wrap items-center justify-end gap-2">
            <BaseActionButton v-if="currentThread?.thread_kind === 'manual'" action="folders" :label="t('communicationFiling.move')" data-testid="communication-move-folder" @click="openMoveFolder" />
            <BaseButton
              v-if="currentThread"
              :variant="currentThread.status === 'open' ? 'secondary' : 'primary'"
              size="sm"
              :loading="store.isMutating"
              :data-testid="`communication-thread-toggle-${currentThread.id}`"
              @click="toggleThread"
            >
              {{ currentThread.status === 'open' ? 'Cerrar hilo' : 'Reabrir hilo' }}
            </BaseButton>
            <BaseActionButton action="close" label="Cerrar detalle del hilo" size="md" @click="close" />
          </div>
        </div>
        <div v-if="currentThread" class="mt-2 flex items-center justify-between gap-2">
          <p class="min-w-0 truncate text-xs text-text-muted">{{ currentThread.folder_name || t('communicationFiling.unfiled') }}</p>
          <div class="flex shrink-0 gap-2">
            <BaseButton variant="ghost" size="sm" data-testid="communication-scroll-start" @click="scrollTimeline('start')">{{ t('communicationFiling.start') }}</BaseButton>
            <BaseButton variant="ghost" size="sm" data-testid="communication-scroll-end" @click="scrollTimeline('end')">{{ t('communicationFiling.end') }}</BaseButton>
          </div>
        </div>
      </header>

      <div v-if="store.isThreadLoading && !currentThread" class="flex-1 space-y-4 overflow-hidden bg-surface-muted p-4 panel-portrait:p-6">
        <BaseSkeleton v-for="index in 4" :key="index" class="mx-auto h-28 max-w-4xl rounded-xl" />
      </div>

      <div v-else-if="store.threadError && !currentThread" class="flex flex-1 items-center justify-center bg-surface-muted p-6">
        <BaseEmptyState
          title="No se pudo abrir el hilo"
          :description="store.threadError"
          class="max-w-lg"
        >
          <template #actions>
            <BaseButton variant="primary" size="sm" @click="loadThread">Reintentar</BaseButton>
          </template>
        </BaseEmptyState>
      </div>

      <template v-else-if="currentThread">
        <div
          class="min-h-0 flex-1 overflow-y-auto overscroll-contain bg-surface-muted px-3 py-4 panel-portrait:px-6"
          ref="timelineRef"
          data-testid="communication-timeline"
        >
          <div class="mx-auto max-w-4xl space-y-4">
            <BaseEmptyState
              v-if="currentThread.messages.length === 0"
              title="Este hilo todavía no tiene mensajes"
              description="Registra lo enviado o la respuesta del cliente para iniciar el histórico."
            />

            <template v-else>
            <article
              v-for="message in currentThread.messages"
              :id="`communication-message-${message.id}`"
              :key="message.id"
              class="max-w-[96%] rounded-xl border p-4 shadow-card panel-portrait:max-w-[82%]"
              :class="[
                message.direction === 'outgoing'
                  ? 'ml-auto border-primary/20 bg-primary-soft'
                  : 'mr-auto border-border-default bg-surface',
                message.voided_at ? 'opacity-70' : '',
              ]"
              :data-testid="`communication-message-${message.id}`"
            >
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-xs tabular-nums text-text-muted">{{ t('communicationFiling.messageId', { id: message.id }) }}</span>
                <BaseBadge :variant="message.channel === 'whatsapp' ? 'success' : 'info'" size="sm">
                  {{ message.channel_display }}
                </BaseBadge>
                <BaseBadge :variant="statusTone(message.status)" size="sm">
                  {{ message.status_display }}
                </BaseBadge>
                <BaseBadge v-if="message.direction === 'outgoing' && message.has_reply" variant="info" size="sm">
                  Respondido
                </BaseBadge>
                <BaseBadge v-if="message.voided_at" variant="neutral" size="sm">Anulado</BaseBadge>
                <span class="ml-auto text-2xs text-text-subtle">{{ formatDateTime(message.occurred_at) }}</span>
              </div>

              <p v-if="message.subject" class="mt-3 text-sm font-semibold text-text-default [overflow-wrap:anywhere]">
                {{ message.subject }}
              </p>
              <a
                v-if="message.reply_to_id"
                :href="`#communication-message-${message.reply_to_id}`"
                class="mt-2 block rounded-lg border border-border-muted bg-surface/70 px-3 py-2 text-xs text-text-subtle hover:border-border-default hover:text-text-default"
              >
                <span class="font-semibold">En respuesta al mensaje #{{ message.reply_to_id }}</span>
                <span v-if="replyOriginPreview(message)" class="ml-1">· “{{ replyOriginPreview(message) }}”</span>
              </a>
              <p class="mt-2 whitespace-pre-wrap text-sm text-text-default [overflow-wrap:anywhere]">{{ message.content }}</p>

              <div v-if="message.documents.length" class="mt-3 space-y-1 border-t border-border-muted pt-3">
                <p class="text-2xs font-semibold uppercase tracking-wide text-text-subtle">Documentos referenciados</p>
                <BaseButton
                  v-for="document in message.documents"
                  :key="document.id"
                  as="NuxtLink"
                  :to="`/panel/documents/${document.id}/edit`"
                  variant="link"
                  size="sm"
                  class="mr-3 max-w-full whitespace-normal [overflow-wrap:anywhere]"
                >
                  <BaseActionIcon action="view" /> #{{ document.id }} {{ document.title }}
                </BaseButton>
              </div>

              <p v-if="message.voided_at" class="mt-3 text-xs text-danger-strong">
                Motivo: {{ message.void_reason }}
              </p>
              <details v-if="message.date_corrections.length" class="mt-3 text-xs text-text-subtle">
                <summary class="cursor-pointer">{{ message.date_corrections.length }} corrección(es) de fecha</summary>
                <ul class="mt-2 space-y-1">
                  <li v-for="correction in message.date_corrections" :key="correction.id">
                    {{ formatDateTime(correction.previous_occurred_at) }} →
                    {{ formatDateTime(correction.corrected_occurred_at) }} · {{ correction.reason }}
                  </li>
                </ul>
              </details>

              <div v-if="!message.voided_at" class="mt-4 flex flex-wrap items-center justify-end gap-2 border-t border-border-muted pt-3">
                <BaseActionButton
                  action="copy"
                  :label="t('communicationFiling.copy')"
                  :data-testid="`communication-copy-${message.id}`"
                  @click="copyMessage(message)"
                />
                <BaseButton
                  v-if="message.status !== 'draft'"
                  variant="secondary"
                  size="sm"
                  @click="replyTo(message)"
                >Responder</BaseButton>
                <BaseActionMenu
                  :items="secondaryActions(message)"
                  label="Más"
                  variant="ghost"
                  placement="top"
                  :testid="`communication-message-actions-${message.id}`"
                />
              </div>
            </article>
            </template>
          </div>
        </div>

        <section class="shrink-0 border-t border-border-muted bg-surface">
          <div v-if="actionState.kind" class="mx-auto max-h-[48vh] max-w-4xl overflow-y-auto p-4 panel-portrait:p-5" data-testid="communication-inline-action">
            <div class="rounded-xl border border-border-default bg-surface-raised p-4">
              <h3 class="text-base font-semibold text-text-default">{{ actionTitle }}</h3>
              <p class="mt-1 text-sm text-text-muted">{{ actionDescription }}</p>

              <BaseFormField v-if="actionState.kind === 'date'" label="Fecha y hora corregida" class="mt-4">
                <BaseInput v-model="actionState.occurred_at" type="datetime-local" />
              </BaseFormField>
              <BaseFormField v-if="['date', 'void'].includes(actionState.kind)" label="Motivo" class="mt-4">
                <BaseTextarea v-model="actionState.reason" :rows="3" placeholder="Explica el motivo para conservar la trazabilidad." />
              </BaseFormField>

              <div class="mt-4 flex flex-col-reverse gap-2 panel-portrait:flex-row panel-portrait:justify-end">
                <BaseButton variant="secondary" size="md" @click="cancelAction">Cancelar</BaseButton>
                <BaseButton
                  :variant="actionState.kind === 'date' ? 'primary' : 'danger'"
                  size="md"
                  :loading="store.isMutating"
                  :disabled="!canSubmitAction"
                  disabled-reason="Completa los campos requeridos."
                  data-testid="communication-action-submit"
                  @click="submitInlineAction"
                >
                  {{ actionSubmitLabel }}
                </BaseButton>
              </div>
            </div>
          </div>

          <template v-else-if="currentThread.status === 'open'">
          <div class="mx-auto max-w-4xl px-4 py-2">
            <BaseButton variant="secondary" size="sm" :aria-expanded="composerOpen" aria-controls="communication-composer-body" data-testid="communication-composer-toggle" @click="composerOpen = !composerOpen">
              <BaseActionIcon :action="composerOpen ? 'collapse' : 'expand'" />
              {{ t(composerOpen ? 'communicationFiling.hideComposer' : 'communicationFiling.compose') }}
            </BaseButton>
          </div>
          <BaseCollapse id="communication-composer-body" :open="composerOpen">
          <form
            ref="composerRef"
            class="mx-auto max-h-[50vh] max-w-4xl overflow-y-auto p-4 panel-portrait:p-5"
            data-testid="communication-composer"
            @submit.prevent="submitMessage()"
          >
            <div v-if="messageForm.reply_to" class="mb-3 flex items-center justify-between rounded-lg bg-info-soft px-3 py-2 text-xs text-info-strong">
              <span>Respuesta al mensaje #{{ messageForm.reply_to }}</span>
              <BaseButton variant="ghost" size="sm" @click="messageForm.reply_to = null">Quitar</BaseButton>
            </div>

            <BaseButton variant="ghost" size="sm" :aria-expanded="detailsOpen" aria-controls="communication-message-details" data-testid="communication-details-toggle" @click="detailsOpen = !detailsOpen">
              <BaseActionIcon :action="detailsOpen ? 'collapse' : 'expand'" />{{ t('communicationFiling.details') }}
            </BaseButton>
            <p class="mb-2 text-xs text-text-muted" data-testid="communication-details-summary">{{ detailsSummary }}</p>
            <BaseCollapse id="communication-message-details" :open="detailsOpen">
            <BaseFormRow :cols="3" :gap="3" at="sm">
              <BaseFormField label="Dirección">
                <BaseSelect
                  v-model="messageForm.direction"
                  :options="DIRECTION_OPTIONS"
                  :disabled="Boolean(editingMessageId)"
                  disabled-reason="La dirección del borrador no se puede cambiar."
                  data-testid="communication-message-direction"
                  @update:model-value="onDirectionChange"
                />
              </BaseFormField>
              <BaseFormField label="Canal">
                <BaseSelect
                  v-model="messageForm.channel"
                  :options="CHANNEL_OPTIONS"
                  data-testid="communication-message-channel"
                  @update:model-value="onChannelChange"
                />
              </BaseFormField>
              <BaseFormField label="Fecha y hora">
                <BaseInput v-model="messageForm.occurred_at" type="datetime-local" data-testid="communication-message-date" />
              </BaseFormField>
            </BaseFormRow>
            </BaseCollapse>

            <BaseFormField v-if="messageForm.channel === 'email'" label="Asunto" class="mt-3">
              <BaseInput v-model="messageForm.subject" placeholder="Asunto del correo" data-testid="communication-message-subject" />
            </BaseFormField>
            <BaseFormField label="Contenido" class="mt-3">
              <BaseTextarea
                v-model="messageForm.content"
                :rows="3"
                placeholder="Escribe o pega el texto exacto de la comunicación..."
                data-testid="communication-message-content"
              />
            </BaseFormField>

            <details v-if="availableDocuments.length" class="mt-3 rounded-lg border border-border-muted p-3">
              <summary class="cursor-pointer text-sm font-medium text-text-default">
                Adjuntar documentos existentes ({{ messageForm.document_ids.length }} elegidos)
              </summary>
              <div class="mt-3 grid gap-2 panel-portrait:grid-cols-2">
                <BaseCheckbox
                  v-for="document in availableDocuments"
                  :key="document.id"
                  v-model="messageForm.document_ids"
                  :value="document.id"
                >
                  {{ document.title }}
                </BaseCheckbox>
              </div>
            </details>

            <div class="mt-4 flex flex-col-reverse gap-2 panel-portrait:flex-row panel-portrait:justify-end">
              <BaseButton v-if="editingMessageId" variant="secondary" size="md" @click="resetMessageForm">
                Cancelar edición
              </BaseButton>
              <BaseButton v-if="editingMessageId" type="submit" variant="primary" size="md" :loading="store.isMutating">
                Guardar cambios
              </BaseButton>
              <template v-else-if="messageForm.direction === 'outgoing'">
                <BaseButton
                  variant="secondary"
                  size="md"
                  :loading="store.isMutating"
                  data-testid="communication-save-draft"
                  @click="submitMessage('draft')"
                >
                  Guardar borrador
                </BaseButton>
                <BaseButton
                  variant="primary"
                  size="md"
                  :loading="store.isMutating"
                  data-testid="communication-register-sent"
                  @click="submitMessage('sent')"
                >
                  Registrar enviado
                </BaseButton>
              </template>
              <BaseButton
                v-else
                variant="primary"
                size="md"
                :loading="store.isMutating"
                data-testid="communication-register-received"
                @click="submitMessage('received')"
              >
                Registrar recibido
              </BaseButton>
            </div>
          </form>
          </BaseCollapse>
          </template>

          <div v-else class="mx-auto max-w-4xl p-4 text-sm text-text-muted panel-portrait:p-5">
            Este hilo está cerrado. Reábrelo para registrar o editar mensajes.
          </div>
        </section>
      </template>
      <BaseModal v-model="moveFolderOpen" kind="confirm">
        <form :id="modalFormId" v-if="currentThread" @submit.prevent="moveThread">
          <h2 class="mb-4 text-lg font-semibold">{{ t('communicationFiling.move') }}</h2>
          <CommunicationFolderPicker v-model="targetFolder" :client-id="currentThread.client_id" :project-id="currentThread.project_id" />
          <BaseAlert v-if="moveError" variant="danger" class="mt-3">{{ moveError }}</BaseAlert>
        </form>
        <template #footer>
          <BaseModalActions v-if="(currentThread)">
            <BaseButton variant="secondary" @click="moveFolderOpen = false">{{ t('communicationFiling.cancel') }}</BaseButton>
            <BaseButton type="submit" :form="modalFormId" variant="primary" :loading="store.isMutating" data-testid="communication-move-save">{{ t('communicationFiling.save') }}</BaseButton>
          </BaseModalActions>
        </template>
      </BaseModal>
    </div>
  </BaseModal>
</template>

<script setup>
import { useId, computed, nextTick, reactive, ref, watch } from 'vue';
import CommunicationFolderPicker from '~/components/communications/CommunicationFolderPicker.vue';
import BaseCollapse from '~/components/base/BaseCollapse.vue';
import BaseActionMenu from '~/components/base/BaseActionMenu.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useCommunicationsStore } from '~/stores/communications';
import { useDocumentStore } from '~/stores/documents';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  threadId: { type: [Number, String], default: null },
  defaultChannel: {
    type: String,
    default: 'whatsapp',
    validator: (value) => ['email', 'whatsapp'].includes(value),
  },
});

const emit = defineEmits(['update:modelValue', 'changed']);
const store = useCommunicationsStore();
const documentStore = useDocumentStore();
const notify = usePanelNotify();
const { t } = useI18n();
const composerRef = ref(null);
const timelineRef = ref(null);
const composerOpen = ref(false);
const detailsOpen = ref(false);
const moveFolderOpen = ref(false);
const targetFolder = ref('');
const moveError = ref('');
const editingMessageId = ref(null);
const currentThread = computed(() => store.currentThread);
const availableDocuments = computed(() => documentStore.documents || []);

const CHANNEL_OPTIONS = [
  { value: 'email', label: 'Correo' },
  { value: 'whatsapp', label: 'WhatsApp' },
];
const DIRECTION_OPTIONS = [
  { value: 'outgoing', label: 'Saliente' },
  { value: 'incoming', label: 'Entrante' },
];

function localDateTime(date = new Date()) {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function initialChannel() {
  return props.defaultChannel === 'email' ? 'email' : 'whatsapp';
}

const messageForm = reactive({
  direction: 'outgoing',
  channel: initialChannel(),
  subject: '',
  content: '',
  occurred_at: localDateTime(),
  reply_to: null,
  document_ids: [],
});

const actionState = reactive({
  kind: '',
  message: null,
  occurred_at: '',
  reason: '',
});

const actionTitle = computed(() => ({
  delete: 'Eliminar borrador',
  void: 'Anular mensaje',
  date: 'Corregir fecha',
})[actionState.kind] || '');
const actionDescription = computed(() => ({
  delete: 'El borrador se eliminará de forma permanente. Esta acción no se puede deshacer.',
  void: 'El mensaje se conservará en el histórico como anulado junto con el motivo.',
  date: 'La fecha anterior y el motivo quedarán en el historial de correcciones.',
})[actionState.kind] || '');
const actionSubmitLabel = computed(() => ({
  delete: 'Eliminar borrador',
  void: 'Anular mensaje',
  date: 'Guardar corrección',
})[actionState.kind] || 'Continuar');
const canSubmitAction = computed(() => {
  if (actionState.kind === 'delete') return true;
  if (actionState.kind === 'date') return Boolean(actionState.occurred_at && actionState.reason.trim());
  return Boolean(actionState.reason.trim());
});

watch(
  () => [props.modelValue, props.threadId],
  async ([open, threadId], previous) => {
    if (!open || !threadId) return;
    const previousId = previous?.[1];
    if (!previous?.[0] || Number(previousId) !== Number(threadId)) {
      resetMessageForm();
      detailsOpen.value = false;
      composerOpen.value = false;
      moveFolderOpen.value = false;
    }
    if (Number(currentThread.value?.id) !== Number(threadId) || Number(previousId) !== Number(threadId)) {
      await loadThread();
    }
  },
  { immediate: true },
);

async function loadThread() {
  if (!props.threadId) return;
  store.clearCurrentThread();
  const result = await store.fetchThread(props.threadId);
  if (!result.success) return;
  composerOpen.value = currentThread.value?.messages.length === 0;
  await loadDocumentsForThread();
}

async function loadDocumentsForThread() {
  if (!currentThread.value?.client_id) return;
  await documentStore.fetchDocuments({
    scope: 'all', client: currentThread.value.client_id, project: null,
  });
}

function handleOpenChange(open) {
  if (!open) close();
}

function close() {
  resetMessageForm();
  cancelAction();
  store.clearCurrentThread();
  emit('update:modelValue', false);
}

async function toggleThread() {
  const shouldOpen = currentThread.value.status === 'closed';
  const result = await store.setThreadOpen(currentThread.value.id, shouldOpen);
  if (!result.success) {
    notify.error({ title: shouldOpen ? 'No se pudo reabrir' : 'No se pudo cerrar', detail: result.message });
    return;
  }
  emit('changed');
  notify.success({ title: shouldOpen ? 'Hilo reabierto' : 'Hilo cerrado' });
}

function onDirectionChange(direction) {
  if (direction === 'incoming' && messageForm.reply_to) {
    const original = currentThread.value?.messages.find((item) => item.id === messageForm.reply_to);
    if (original?.direction === 'incoming') messageForm.reply_to = null;
  }
}

function onChannelChange(channel) {
  if (channel === 'whatsapp') messageForm.subject = '';
}

function resetMessageForm() {
  editingMessageId.value = null;
  Object.assign(messageForm, {
    direction: 'outgoing',
    channel: initialChannel(),
    subject: '',
    content: '',
    occurred_at: localDateTime(),
    reply_to: null,
    document_ids: [],
  });
}

function messagePayload(statusOverride) {
  return {
    direction: messageForm.direction,
    channel: messageForm.channel,
    subject: messageForm.channel === 'email' ? messageForm.subject.trim() : '',
    content: messageForm.content.trim(),
    occurred_at: new Date(messageForm.occurred_at).toISOString(),
    reply_to: messageForm.reply_to,
    document_ids: [...messageForm.document_ids],
    ...(statusOverride ? { status: statusOverride } : {}),
  };
}

async function submitMessage(statusOverride = null) {
  if (!messageForm.occurred_at || Number.isNaN(new Date(messageForm.occurred_at).getTime())) {
    composerOpen.value = true;
    detailsOpen.value = true;
    notify.warning({ title: t('communicationFiling.invalidDate') });
    return;
  }
  if (!messageForm.content.trim()) {
    notify.warning({ title: 'Escribe el contenido del mensaje' });
    return;
  }
  if (messageForm.channel === 'email' && !messageForm.subject.trim()) {
    notify.warning({ title: 'El asunto es obligatorio para correo' });
    return;
  }
  const payload = messagePayload(
    messageForm.direction === 'incoming' ? 'received' : statusOverride,
  );
  const wasEditing = Boolean(editingMessageId.value);
  const result = editingMessageId.value
    ? await store.updateDraft(editingMessageId.value, payload)
    : await store.createMessage(currentThread.value.id, payload);
  if (!result.success) {
    composerOpen.value = true;
    if (Object.keys(result.fieldErrors || {}).some((key) => ['direction', 'channel', 'occurred_at'].includes(key))) detailsOpen.value = true;
    notify.error({ title: 'No se pudo guardar el mensaje', detail: result.message });
    return;
  }
  resetMessageForm();
  await nextTick();
  scrollToMessage(result.data?.id);
  emit('changed');
  notify.success({
    title: wasEditing
      ? 'Borrador actualizado'
      : (payload.status === 'draft' ? 'Borrador guardado' : 'Mensaje registrado'),
  });
}

function editDraft(message) {
  cancelAction();
  editingMessageId.value = message.id;
  Object.assign(messageForm, {
    direction: message.direction,
    channel: message.channel,
    subject: message.subject || '',
    content: message.content,
    occurred_at: localDateTime(new Date(message.occurred_at)),
    reply_to: message.reply_to_id,
    document_ids: message.documents.map((document) => document.id),
  });
  openComposer();
}

async function markSent(message) {
  const result = await store.markSent(message.id, new Date().toISOString());
  if (!result.success) {
    notify.error({ title: 'No se pudo marcar como enviado', detail: result.message });
    return;
  }
  emit('changed');
  notify.success({ title: 'Mensaje marcado como enviado' });
}

function replyTo(message) {
  cancelAction();
  resetMessageForm();
  messageForm.reply_to = message.id;
  messageForm.direction = message.direction === 'incoming' ? 'outgoing' : 'incoming';
  messageForm.channel = message.channel;
  if (messageForm.channel === 'email' && message.subject) {
    messageForm.subject = message.subject.startsWith('Re:') ? message.subject : `Re: ${message.subject}`;
  }
  openComposer();
}

async function copyMessage(message) {
  try {
    await navigator.clipboard.writeText(message.content);
    notify.success({ title: 'Texto copiado' });
  } catch {
    notify.error({ title: 'No se pudo copiar el texto' });
  }
}

function beginAction(kind, message) {
  resetMessageForm();
  Object.assign(actionState, {
    kind,
    message,
    occurred_at: kind === 'date' ? localDateTime(new Date(message.occurred_at)) : '',
    reason: '',
  });
}

function cancelAction() {
  Object.assign(actionState, {
    kind: '', message: null, occurred_at: '', reason: '',
  });
}

async function submitInlineAction() {
  let result;
  if (actionState.kind === 'delete') {
    result = await store.deleteDraft(actionState.message);
  } else if (actionState.kind === 'void') {
    result = await store.voidMessage(actionState.message.id, actionState.reason);
  } else {
    result = await store.correctDate(
      actionState.message.id,
      new Date(actionState.occurred_at).toISOString(),
      actionState.reason,
    );
  }
  if (!result.success) {
    notify.error({ title: 'No se pudo actualizar el histórico', detail: result.message });
    return;
  }
  const completedKind = actionState.kind;
  cancelAction();
  emit('changed');
  notify.success({
    title: ({ delete: 'Borrador eliminado', void: 'Mensaje anulado', date: 'Fecha corregida' })[completedKind],
  });
}

function secondaryActions(message) {
  const actions = [];
  if (message.status === 'draft' && message.direction === 'outgoing') {
    actions.push({ action: 'send', label: 'Marcar enviado', disabled: store.isMutating, disabledReason: 'Espera a que termine la operación.', onClick: () => markSent(message) });
  }
  if (message.status === 'draft') {
    actions.push({ action: 'edit', label: 'Editar borrador', onClick: () => editDraft(message) });
    actions.push({
      action: 'delete', label: 'Eliminar borrador', danger: true,
      onClick: () => beginAction('delete', message),
    });
  } else {
    actions.push({ action: 'edit', label: 'Corregir fecha', onClick: () => beginAction('date', message) });
    actions.push({
      action: 'remove', label: 'Anular mensaje', danger: true,
      onClick: () => beginAction('void', message),
    });
  }
  return actions;
}

function statusTone(status) {
  return ({ draft: 'warning', sent: 'success', received: 'info', failed: 'danger' })[status] || 'neutral';
}

function replyOriginPreview(message) {
  if (!message.reply_to_id) return '';
  const origin = currentThread.value?.messages.find(
    (candidate) => candidate.id === message.reply_to_id,
  );
  if (!origin?.content) return '';
  return origin.content.length > 110 ? `${origin.content.slice(0, 107)}…` : origin.content;
}

function formatDateTime(value) {
  if (!value || Number.isNaN(new Date(value).getTime())) return '—';
  return new Intl.DateTimeFormat('es-CO', {
    dateStyle: 'medium', timeStyle: 'short',
  }).format(new Date(value));
}
const detailsSummary = computed(() => [
  DIRECTION_OPTIONS.find((option) => option.value === messageForm.direction)?.label,
  CHANNEL_OPTIONS.find((option) => option.value === messageForm.channel)?.label,
  messageForm.occurred_at ? formatDateTime(messageForm.occurred_at) : '—',
].join(' · '));
function scrollBehavior() {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
}
function scrollTimeline(position) {
  const timeline = timelineRef.value;
  if (timeline) timeline.scrollTo({ top: position === 'end' ? timeline.scrollHeight : 0, behavior: scrollBehavior() });
}
function scrollToMessage(id) {
  const timeline = timelineRef.value;
  const message = timeline?.querySelector(`[data-testid="communication-message-${id}"]`);
  if (!timeline || !message) return;
  timeline.scrollTo({ top: timeline.scrollTop + message.getBoundingClientRect().top - timeline.getBoundingClientRect().top, behavior: scrollBehavior() });
}
function openComposer() {
  composerOpen.value = true;
  nextTick(() => composerRef.value?.querySelector('textarea')?.focus({ preventScroll: true }));
}
function openMoveFolder() {
  targetFolder.value = currentThread.value.folder_id ? String(currentThread.value.folder_id) : '';
  moveError.value = '';
  moveFolderOpen.value = true;
}
async function moveThread() {
  const result = await store.updateThread(currentThread.value.id, { folder: targetFolder.value ? Number(targetFolder.value) : null });
  if (!result.success) { moveError.value = result.message; return; }
  moveFolderOpen.value = false;
  emit('changed');
  notify.success({ title: t('communicationFiling.threadMoved') });
}

const modalFormId = useId();
</script>
