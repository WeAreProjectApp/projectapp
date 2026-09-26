<template>
  <Teleport to="body">
    <Transition name="fade-modal">
      <div
        v-if="modelValue && document"
        class="fixed inset-0 z-[9990] flex items-end justify-center bg-black/40 p-0 backdrop-blur-sm panel-portrait:items-center panel-portrait:p-4"
        @click.self="close"
      >
        <div class="flex max-h-[100dvh] w-full flex-col overflow-hidden rounded-t-2xl bg-surface shadow-2xl panel-portrait:max-h-[calc(100dvh-2rem)] panel-portrait:max-w-sm panel-portrait:rounded-2xl">
          <!-- Header -->
          <div class="flex shrink-0 items-center justify-between px-5 py-4 border-b border-border-muted">
            <div class="min-w-0">
              <h3 class="text-sm font-semibold text-text-default truncate">{{ document.title }}</h3>
              <p v-if="document.client_name" class="text-xs text-text-subtle mt-0.5 truncate">
                {{ document.client_name }}
              </p>
            </div>
            <BaseActionButton
              action="close"
              label="Cerrar acciones del documento"
              class="flex-shrink-0 ml-2"
              @click="close"
            />
          </div>

          <!-- Actions list -->
          <div class="min-h-0 flex-1 overflow-y-auto overscroll-contain p-2" data-testid="document-actions-list">
            <component
              :is="action.newTab ? 'a' : 'button'"
              v-for="action in actions"
              :key="action.template ? `${action.event}-${action.template}` : action.event"
              v-bind="action.newTab
                ? { href: editTo, target: '_blank', rel: 'noopener noreferrer', 'data-testid': 'document-open-new-tab' }
                : { type: 'button' }"
              class="w-full flex items-center gap-3 px-3 py-3 rounded-xl text-left transition-all active:scale-[0.98] hover:bg-surface-muted"
              :class="action.danger ? 'text-danger-strong hover:bg-danger-soft' : 'text-text-default'"
              @click="trigger(action)"
            >
              <div
                class="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                :class="action.danger ? 'bg-danger-soft text-danger-strong' : 'bg-surface-raised text-text-subtle'"
              >
                <BaseActionIcon :action="action.action" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium">{{ action.label }}</div>
                <div v-if="action.description" class="text-xs text-text-subtle mt-0.5">{{ action.description }}</div>
              </div>
            </component>
          </div>

          <!-- Footer (mobile-only safe area + cancel) -->
          <div class="shrink-0 px-5 py-3 border-t border-border-muted">
            <BaseButton variant="ghost" size="md" class="w-full" @click="close">
              Cancelar
            </BaseButton>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  document: { type: Object, default: null },
  archived: { type: Boolean, default: false },
  // Dirección del editor, ya resuelta por la página. Llega como prop y no se
  // arma acá porque esta hoja es presentacional: sus specs la montan fuera del
  // contexto de Nuxt, donde `useLocalePath` no existe.
  editTo: { type: String, default: null },
});
const emit = defineEmits([
  'update:modelValue',
  'edit',
  'rename',
  'move',
  'download-pdf',
  'copy-markdown',
  'duplicate',
  'send-email',
  'thread',
  'archive',
  'unarchive',
  'delete',
]);

// La etiqueta de vuelta es "Restaurar", no "Desarchivar": es el término que ya
// usa el tablero de tareas, y además evita que un buscador por substring de
// "Archivar" matchee también la acción inversa.
const ARCHIVE_ACTION = {
  event: 'archive',
  action: 'archive',
  label: 'Archivar',
  description: 'Lo saca de la lista y de los contadores; podrás restaurarlo',
};

const UNARCHIVE_ACTION = {
  event: 'unarchive',
  action: 'restore',
  label: 'Restaurar',
  description: 'Lo devuelve a su carpeta original',
};

const THREAD_ACTION = {
  event: 'thread',
  action: 'link',
  label: 'Hilo de documentos',
  description: 'Enlazar o consultar documentos relacionados',
};

const BASE_ACTIONS = [
  {
    event: 'edit',
    action: 'edit',
    label: 'Editar contenido',
    description: 'Abrir el editor del documento',
  },
  // Un <a> de verdad, no un botón que llame a window.open: así la acción existe
  // también en pantallas táctiles, donde ctrl+clic no está, y sigue siendo
  // copiable y abrible desde el menú contextual.
  {
    event: 'open-new-tab',
    action: 'open-external',
    newTab: true,
    label: 'Abrir en pestaña nueva',
    description: 'Abre el editor en otra pestaña, sin salir de la lista',
  },
  THREAD_ACTION,
  {
    event: 'rename',
    action: 'rename',
    label: 'Renombrar',
    description: 'Cambiar el nombre del documento',
  },
  {
    event: 'move',
    action: 'move',
    label: 'Mover a carpeta',
    description: 'Cambiar la carpeta',
  },
  {
    event: 'send-email',
    action: 'send',
    label: 'Enviar por correo',
    description: 'Componer y enviar correo con el documento',
  },
  {
    event: 'download-pdf', template: 'friendly',
    action: 'download',
    label: 'Descargar PDF · Amigable',
  },
  {
    event: 'download-pdf', template: 'professional',
    action: 'download',
    label: 'Descargar PDF · Profesional',
  },
  {
    event: 'copy-markdown',
    action: 'copy',
    label: 'Copiar markdown',
  },
  {
    event: 'duplicate',
    action: 'duplicate',
    label: 'Duplicar',
  },
  ARCHIVE_ACTION,
  {
    event: 'delete',
    action: 'delete',
    label: 'Eliminar',
    description: 'Esta acción no se puede deshacer',
    danger: true,
  },
];

// The window onto the one contract is rendered live and never edited, moved,
// duplicated, archived or deleted here: only consulted, shared and exported.
const CONTRACT_MIRROR_ACTIONS = [
  {
    event: 'edit',
    action: 'view',
    label: 'Ver contrato vigente',
    description: 'Consultar el contrato y descargarlo en PDF o Markdown',
  },
  BASE_ACTIONS.find((action) => action.event === 'open-new-tab'),
  THREAD_ACTION,
  BASE_ACTIONS.find((action) => action.event === 'send-email'),
  {
    event: 'download-pdf',
    action: 'download',
    label: 'Descargar PDF',
  },
  BASE_ACTIONS.find((action) => action.event === 'copy-markdown'),
].filter(Boolean);

const isArchived = computed(() => props.archived || !!props.document?.is_archived);

// Un documento archivado está fuera de circulación: editarlo, renombrarlo,
// moverlo, enviarlo por correo o duplicarlo sería incoherente. Queda lo que
// tiene sentido sobre algo guardado: consultarlo, restaurarlo o borrarlo.
const ARCHIVED_EVENTS = new Set(['thread', 'download-pdf', 'copy-markdown', 'delete']);

const GENERATED_ACTIONS = [
  {
    event: 'edit',
    action: 'view',
    label: 'Ver versión archivada',
    description: 'Consultar el PDF y los datos guardados de esta versión',
  },
  BASE_ACTIONS.find((action) => action.event === 'open-new-tab'),
  THREAD_ACTION,
  {
    event: 'download-pdf',
    action: 'download',
    label: 'Descargar versión archivada',
  },
  ARCHIVE_ACTION,
].filter(Boolean);

const ISSUED_ACCOUNT_ACTIONS = [
  {
    event: 'edit',
    action: 'view',
    label: 'Ver cuenta de cobro',
    description: 'Consultar el documento emitido y sus datos',
  },
  BASE_ACTIONS.find((action) => action.event === 'open-new-tab'),
  THREAD_ACTION,
  {
    event: 'download-pdf',
    action: 'download',
    label: 'Descargar cuenta de cobro',
  },
  ARCHIVE_ACTION,
].filter(Boolean);

const isIssuedAccount = computed(() => (
  props.document?.document_type_code === 'collection_account'
  && props.document?.commercial_status !== 'draft'
));

const actions = computed(() => {
  if (props.document?.is_contract_mirror) {
    return CONTRACT_MIRROR_ACTIONS.filter((action) => !action.newTab || props.editTo);
  }
  if (isIssuedAccount.value || props.document?.is_generated_snapshot) {
    // A stored account is both an issued account and a generated snapshot;
    // its accounting identity wins over the generic proposal-version copy.
    const readOnlyActions = isIssuedAccount.value
      ? ISSUED_ACCOUNT_ACTIONS
      : GENERATED_ACTIONS;
    if (isArchived.value) {
      return [
        UNARCHIVE_ACTION,
        readOnlyActions.find((action) => action.event === 'thread'),
        readOnlyActions.find((action) => action.event === 'download-pdf'),
      ].filter(Boolean);
    }
    return readOnlyActions.filter((action) => !action.newTab || props.editTo);
  }
  if (isArchived.value) {
    return [
      UNARCHIVE_ACTION,
      ...BASE_ACTIONS.filter((a) => ARCHIVED_EVENTS.has(a.event)),
    ];
  }
  // Sin dirección no hay enlace: una acción que no lleva a ningún lado no se
  // ofrece.
  return BASE_ACTIONS.filter((a) => !a.newTab || props.editTo);
});

function close() {
  emit('update:modelValue', false);
}

function trigger(action) {
  // El enlace navega solo; la hoja únicamente se aparta.
  if (!action.newTab) emit(action.event, action.template);
  close();
}
</script>
