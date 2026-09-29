<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-light text-text-default">Editar linktree</h1>
        <p v-if="form.handle" class="text-sm text-text-subtle mt-1">
          URL pública:
          <a
            :href="`/lk/@${form.handle}`"
            target="_blank"
            rel="noopener noreferrer"
            class="text-text-brand underline"
            data-testid="linktree-public-link"
          >/lk/@{{ form.handle }}</a>
        </p>
      </div>
      <div class="flex items-center gap-2">
        <BaseButton
          variant="ghost"
          size="sm"
          @click="navigateTo(localePath('/panel/linktrees'))"
        >
          Volver
        </BaseButton>
        <BaseButton
          variant="primary"
          size="sm"
          :loading="store.isUpdating"
          data-testid="linktree-save"
          :disabled="!loaded"
          disabled-reason="Espera a que cargue el linktree"
          @click="onSave"
        >
          Guardar cambios
        </BaseButton>
      </div>
    </div>

    <div v-if="!loaded" class="text-center py-16 text-text-subtle text-sm">
      {{ loadError || 'Cargando linktree...' }}
    </div>

    <div v-else class="panel-landscape:flex panel-landscape:items-start panel-landscape:gap-6">
      <div class="flex-1 min-w-0 space-y-6">
      <!-- "error" no es una variante de BaseAlert: caía en `info` sin avisar y
           pintaba de azul un error de los botones. -->
      <BaseAlert v-if="buttonsError" variant="danger" data-testid="linktree-buttons-error">
        {{ buttonsError }}
      </BaseAlert>

      <UnsavedChangesNotice
        v-if="hasChanges"
        :title="unsavedTitle"
        :detail="unsavedDetail"
        :can-save="canSaveNow"
        :saving="store.isUpdating"
        :can-discard="false"
        testid="linktree-unsaved-notice"
        @save="onSave"
      />

      <!-- Identity -->
      <section class="bg-surface border border-border-default rounded-xl shadow-card p-5">
        <h2 class="text-base font-semibold text-text-default mb-4">Identidad</h2>
        <div class="space-y-4">
          <BaseFormRow :cols="2" :gap="4" at="md">
            <BaseFormField label="Nombre interno" for="lt-name" required :error="fieldErrors.name">
              <BaseInput id="lt-name" v-model="form.name" data-testid="linktree-name-input" />
            </BaseFormField>

            <BaseFormField label="Handle" for="lt-handle" required :error="fieldErrors.handle">
              <BaseInput id="lt-handle" v-model="form.handle" data-testid="linktree-handle-input" />
            </BaseFormField>
          </BaseFormRow>

          <BaseFormRow
            :cols="2"
            :gap="4"
            at="md"
            help="Ejemplo de badge: TECH WEEK CO. Déjalo vacío para ocultarlo."
          >
            <BaseFormField label="Tipo" for="lt-kind">
              <BaseSegmented
                id="lt-kind"
                v-model="form.kind"
                :options="[
                  { value: 'personal', label: 'Personal' },
                  { value: 'company', label: 'Empresa' },
                ]"
              />
            </BaseFormField>

            <BaseFormField label="Badge del evento" for="lt-badge">
              <BaseInput id="lt-badge" v-model="form.badge_text" data-testid="linktree-badge-input" />
            </BaseFormField>
          </BaseFormRow>

          <template v-if="form.kind === 'personal'">
            <BaseFormRow :cols="2" :gap="4" at="md">
            <BaseFormField label="Nombre a mostrar" for="lt-display-name">
              <BaseInput id="lt-display-name" v-model="form.display_name" data-testid="linktree-display-name-input" />
            </BaseFormField>

            <BaseFormField label="Cargo" for="lt-role">
              <BaseInput id="lt-role" v-model="form.role" />
            </BaseFormField>
            </BaseFormRow>

            <BaseFormRow
              :cols="1"
              :gap="4"
              help="JPG, PNG o WebP, máximo 5 MB. Sin foto se muestran las iniciales."
            >
            <BaseFormField
              label="Foto de perfil"
              for="lt-avatar"
              :error="fieldErrors.avatar"
            >
              <div class="flex items-center gap-3">
                <img
                  v-if="avatarUrl"
                  :src="avatarUrl"
                  alt="Foto de perfil"
                  class="h-12 w-12 rounded-full object-cover border border-border-default"
                  data-testid="linktree-avatar-preview"
                />
                <div
                  v-else
                  class="h-12 w-12 rounded-full bg-surface-muted border border-border-default flex items-center justify-center text-xs font-semibold text-text-muted"
                >
                  {{ formInitials }}
                </div>
                <input
                  id="lt-avatar"
                  ref="avatarInput"
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  class="hidden"
                  data-testid="linktree-avatar-input"
                  @change="onAvatarSelected"
                />
                <BaseButton type="button" variant="secondary" size="sm" @click="avatarInput?.click()">
                  {{ avatarUrl ? 'Cambiar foto' : 'Subir foto' }}
                </BaseButton>
                <BaseButton
                  v-if="avatarUrl"
                  type="button"
                  variant="danger-ghost"
                  size="sm"
                  @click="onRemoveAvatar"
                >
                  Quitar
                </BaseButton>
              </div>
            </BaseFormField>
            </BaseFormRow>
          </template>

          <BaseFormRow v-else :cols="2" :gap="4" at="md">
            <BaseFormField label="Claim — línea 1" for="lt-claim-1">
              <BaseInput id="lt-claim-1" v-model="form.claim_line_1" placeholder="En 30 días deja" />
            </BaseFormField>

            <BaseFormField label="Claim — línea 2 (resaltada)" for="lt-claim-2">
              <BaseInput id="lt-claim-2" v-model="form.claim_line_2" placeholder="de ser una idea." />
            </BaseFormField>
          </BaseFormRow>

          <BaseFormField label="Bio" for="lt-bio">
            <BaseTextarea id="lt-bio" v-model="form.bio" :rows="2" />
          </BaseFormField>

          <BaseFormRow :cols="2" :gap="4" at="md">
            <BaseFormField label="Tagline del pie" for="lt-tagline">
              <BaseInput id="lt-tagline" v-model="form.footer_tagline" />
            </BaseFormField>

            <BaseFormField label="Mostrar logo o marca" for="lt-brand">
              <BaseToggle id="lt-brand" v-model="form.show_brand_header" aria-label="Mostrar marca" />
            </BaseFormField>
          </BaseFormRow>
        </div>
      </section>

      <LinktreeAppearance :form="form" :logo="logoUrl" :errors="fieldErrors" :busy="store.isUpdating"
        :template-active="Boolean(templatesStore.activeVersionId)"
        @upload-logo="onLogoSelected" @remove-logo="onRemoveLogo" @update-field="(key, value) => form[key] = value">
        <template #template>
          <LinktreeTemplateEditor :tree-id="String(route.params.id)" :has-unsaved-changes="hasChanges" />
        </template>
      </LinktreeAppearance>

      <!-- Buttons -->
      <section class="bg-surface border border-border-default rounded-xl shadow-card p-5">
        <div class="flex items-center justify-between mb-1">
          <h2 class="text-base font-semibold text-text-default">Botones</h2>
          <BaseButton variant="secondary" size="sm" data-testid="linktree-add-button" @click="addButton">
            Agregar botón
          </BaseButton>
        </div>
        <p class="text-xs text-text-subtle mb-4">
          Jerarquía del diseño: 1 principal (obligatorio), hasta 1 destacado, los de par van de a 2, hasta 6 filas.
          Un botón sin destino se muestra como PENDIENTE.
        </p>

        <BaseEmptyState
          v-if="form.buttons.length === 0"
          title="Sin botones"
          description="Agregá el primer botón del linktree."
        />

        <div v-else class="space-y-3">
          <div
            v-for="(button, index) in form.buttons"
            :key="index"
            class="border border-border-muted rounded-lg p-3 grid grid-cols-1 md:grid-cols-12 gap-3 items-end"
            :data-testid="`linktree-button-row-${index}`"
          >
            <BaseFormField label="Nivel" :for="`lt-btn-tier-${index}`" class="md:col-span-2">
              <BaseSelect
                :id="`lt-btn-tier-${index}`"
                v-model="button.tier"
                :options="TIER_OPTIONS"
              />
            </BaseFormField>

            <BaseFormField label="Acción" :for="`lt-btn-action-${index}`" class="md:col-span-2">
              <BaseSelect
                :id="`lt-btn-action-${index}`"
                v-model="button.action"
                :options="ACTION_OPTIONS"
              />
            </BaseFormField>

            <BaseFormField label="Etiqueta" :for="`lt-btn-label-${index}`" class="md:col-span-3">
              <BaseInput
                :id="`lt-btn-label-${index}`"
                v-model="button.label"
                :data-testid="`linktree-button-label-${index}`"
              />
            </BaseFormField>

            <BaseFormField
              v-if="needsHref(button)"
              label="Destino"
              :for="`lt-btn-href-${index}`"
              class="md:col-span-3"
            >
              <BaseInput
                :id="`lt-btn-href-${index}`"
                v-model="button.href"
                placeholder="https://... o mailto:..."
                :data-testid="`linktree-button-href-${index}`"
              />
            </BaseFormField>
            <div v-else class="md:col-span-3 text-xs text-text-subtle pb-2">
              {{ button.action === 'vcard' ? 'Descarga el contacto (vCard) con los datos de abajo.' : 'Abre el prompt de instalación de la tarjeta.' }}
            </div>

            <div class="md:col-span-2 flex items-center justify-end gap-1 pb-1">
              <BaseActionButton
                action="move-up"
                variant="ghost"
                size="sm"
                label="Subir botón"
                :disabled="index === 0"
                disabled-reason="Este botón ya está en la primera posición."
                @click="moveButton(index, -1)"
              />
              <BaseActionButton
                action="move-down"
                variant="ghost"
                size="sm"
                label="Bajar botón"
                :disabled="index === form.buttons.length - 1"
                disabled-reason="Este botón ya está en la última posición."
                @click="moveButton(index, 1)"
              />
              <BaseToggle
                :model-value="button.is_active"
                :aria-label="`Activar botón ${button.label || index + 1}`"
                @update:model-value="(value) => (button.is_active = value)"
              />
              <BaseActionButton
                action="delete"
                variant="danger-ghost"
                size="sm"
                :label="`Eliminar botón ${index + 1}`"
                :data-testid="`linktree-button-delete-${index}`"
                @click="form.buttons.splice(index, 1)"
              />
            </div>
          </div>
        </div>
      </section>

      <!-- Save-the-card block -->
      <section class="bg-surface border border-border-default rounded-xl shadow-card p-5">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-base font-semibold text-text-default">Bloque "Guardar en el teléfono"</h2>
          <BaseToggle v-model="form.pwa_enabled" aria-label="Mostrar bloque de instalación" data-testid="linktree-pwa-toggle" />
        </div>
        <BaseFormRow v-if="form.pwa_enabled" :cols="2" :gap="4" at="md">
          <BaseFormField label="Título" for="lt-pwa-title">
            <BaseInput id="lt-pwa-title" v-model="form.pwa_title" />
          </BaseFormField>
          <BaseFormField label="Descripción" for="lt-pwa-description">
            <BaseInput id="lt-pwa-description" v-model="form.pwa_description" />
          </BaseFormField>
        </BaseFormRow>
      </section>

      <!-- vCard -->
      <section class="bg-surface border border-border-default rounded-xl shadow-card p-5">
        <h2 class="text-base font-semibold text-text-default mb-1">Datos del contacto (vCard)</h2>
        <p class="text-xs text-text-subtle mb-4">Lo que descarga el botón "Guardar contacto".</p>
        <BaseFormRow :cols="3" :gap="4" at="md">
          <BaseFormField label="Nombre" for="lt-vcard-first">
            <BaseInput id="lt-vcard-first" v-model="form.vcard_first_name" />
          </BaseFormField>
          <BaseFormField label="Apellido" for="lt-vcard-last">
            <BaseInput id="lt-vcard-last" v-model="form.vcard_last_name" />
          </BaseFormField>
          <BaseFormField label="Organización" for="lt-vcard-org">
            <BaseInput id="lt-vcard-org" v-model="form.vcard_org" />
          </BaseFormField>
          <BaseFormField label="Correo" for="lt-vcard-email" :error="fieldErrors.vcard_email">
            <BaseInput id="lt-vcard-email" v-model="form.vcard_email" type="email" />
          </BaseFormField>
          <BaseFormField label="Teléfono" for="lt-vcard-tel">
            <BaseInput id="lt-vcard-tel" v-model="form.vcard_tel" placeholder="+57..." />
          </BaseFormField>
          <BaseFormField label="Sitio web" for="lt-vcard-url" :error="fieldErrors.vcard_url">
            <BaseInput id="lt-vcard-url" v-model="form.vcard_url" placeholder="https://..." />
          </BaseFormField>
        </BaseFormRow>
      </section>
      </div>

      <!-- Live preview available on every viewport -->
      <aside class="mt-6 w-full shrink-0 panel-landscape:sticky panel-landscape:top-6 panel-landscape:mt-0 panel-landscape:w-96" data-testid="linktree-preview">
        <div class="bg-surface border border-border-default rounded-xl shadow-card p-4">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-sm font-semibold text-text-default">Vista previa</h2>
            <span class="text-xs text-text-subtle">se actualiza mientras editas</span>
          </div>
          <div class="lt-preview-frame">
            <LinktreeCard :tree="previewTree" />
          </div>
        </div>
      </aside>
    </div>

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
import { LINKTREE_DEFAULTS } from '~/utils/linktreeTheme';
import LinktreeAppearance from '~/components/panel/linktrees/LinktreeAppearance.vue';
import LinktreeTemplateEditor from '~/components/panel/linktrees/LinktreeTemplateEditor.vue';
import { computed, onMounted, reactive, ref } from 'vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseTextarea from '~/components/base/BaseTextarea.vue';
import BaseFormField from '~/components/base/BaseFormField.vue';
import BaseFormRow from '~/components/base/BaseFormRow.vue';
import BaseToggle from '~/components/base/BaseToggle.vue';
import BaseSelect from '~/components/base/BaseSelect.vue';
import UnsavedChangesNotice from '~/components/panel/UnsavedChangesNotice.vue';
import { useUnsavedGuard } from '~/composables/useUnsavedGuard';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import BaseAlert from '~/components/base/BaseAlert.vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useLinktreesStore } from '~/stores/linktrees';
import { useLinktreeTemplatesStore } from '~/stores/linktree-templates';
import LinktreeCard from '~/components/Linktree/LinktreeCard.vue';

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

// Ubuntu is the linktree brand font — loaded here so the live preview
// matches the public page exactly.
// Mirror of the backend LINKTREE_ACTIONS catalog (icon + behavior kind)
// so the preview derives the same render hints the public API returns.
const ACTION_META = {
  linkedin: { icon: 'linkedin', kind: 'url' },
  whatsapp: { icon: 'whatsapp', kind: 'url' },
  email: { icon: 'mail', kind: 'mailto' },
  web: { icon: 'globe', kind: 'url' },
  instagram: { icon: 'instagram', kind: 'url' },
  vcard: { icon: 'user-round-plus', kind: 'download-vcard' },
  install: { icon: 'smartphone', kind: 'pwa-install' },
  custom: { icon: 'globe', kind: 'url' },
};

const TIER_OPTIONS = [
  { value: 'primary', label: 'Principal' },
  { value: 'featured', label: 'Destacado' },
  { value: 'pair', label: 'Par' },
  { value: 'row', label: 'Fila' },
];

const ACTION_OPTIONS = [
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'email', label: 'Correo' },
  { value: 'web', label: 'Web' },
  { value: 'instagram', label: 'Instagram' },
  { value: 'vcard', label: 'Guardar contacto' },
  { value: 'install', label: 'Instalar tarjeta' },
  { value: 'custom', label: 'Personalizado' },
];

const FORM_FIELDS = [
  ...Object.keys(LINKTREE_DEFAULTS),
  'handle', 'name', 'kind', 'display_name', 'role', 'bio',
  'claim_line_1', 'claim_line_2', 'badge_text', 'footer_tagline',
  'show_brand_header', 'pwa_enabled', 'pwa_title', 'pwa_description',
  'vcard_first_name', 'vcard_last_name', 'vcard_org', 'vcard_email',
  'vcard_tel', 'vcard_url', 'is_active',
];

const route = useRoute();
const store = useLinktreesStore();
const templatesStore = useLinktreeTemplatesStore();
const notify = usePanelNotify();
const localePath = useLocalePath();

const loaded = ref(false);
const loadError = ref('');
const buttonsError = ref('');
const fieldErrors = reactive({});
const avatarInput = ref(null);
const avatarUrl = ref('');
const logoUrl = ref('');
const form = reactive({
  ...LINKTREE_DEFAULTS,
  handle: '', name: '', kind: 'personal',
  display_name: '', role: '', bio: '',
  claim_line_1: '', claim_line_2: '', badge_text: '',
  footer_tagline: '', show_brand_header: true,
  pwa_enabled: true, pwa_title: '', pwa_description: '',
  vcard_first_name: '', vcard_last_name: '', vcard_org: '',
  vcard_email: '', vcard_tel: '', vcard_url: '',
  is_active: true,
  buttons: [],
});

// `avatarUrl` es un ref aparte, fuera de `form`: la foto se sube y se borra
// contra el servidor al instante, así que no es trabajo pendiente y queda
// naturalmente fuera del snapshot.
const {
  hasChanges,
  unsavedTitle,
  unsavedDetail,
  canSaveNow,
  commit: commitBaseline,
  confirmState,
  handleConfirmed,
  handleSecondaryAction,
  handleCancelled,
} = useUnsavedGuard({
  snapshot: () => ({ ...form }),
  labels: {
    background_color: 'color de fondo', accent_color: 'color de acento',
    text_color: 'color de texto', muted_color: 'texto secundario',
    button_text_color: 'texto del botón principal', font_family: 'tipografía',
    handle: 'handle',
    name: 'nombre interno',
    kind: 'tipo',
    display_name: 'nombre visible',
    role: 'rol',
    bio: 'bio',
    claim_line_1: 'claim 1',
    claim_line_2: 'claim 2',
    badge_text: 'badge',
    footer_tagline: 'pie',
    show_brand_header: 'cabecera de marca',
    pwa_enabled: 'PWA',
    pwa_title: 'título PWA',
    pwa_description: 'descripción PWA',
    vcard_first_name: 'nombre (vCard)',
    vcard_last_name: 'apellido (vCard)',
    vcard_org: 'empresa (vCard)',
    vcard_email: 'email (vCard)',
    vcard_tel: 'teléfono (vCard)',
    vcard_url: 'sitio (vCard)',
    is_active: 'estado',
    // Nombrar el botón concreto exigiría rastrear la fila; el grupo alcanza
    // para saber dónde mirar.
    buttons: 'botones',
  },
  save: onSave,
});

function needsHref(button) {
  return !['vcard', 'install'].includes(button.action);
}

const formInitials = computed(() =>
  (form.display_name || '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join('') || '—'
);

async function onAvatarSelected(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  fieldErrors.avatar = '';
  const result = await store.uploadAvatar(route.params.id, file);
  if (!result.success) {
    fieldErrors.avatar = result.errors?.avatar || 'No se pudo subir la foto.';
    return;
  }
  avatarUrl.value = result.data.avatar || '';
  notify.success({ title: 'Foto actualizada' });
  event.target.value = '';
}

const previewTree = computed(() => ({
  ...form,
  avatar: avatarUrl.value || null,
  logo: logoUrl.value || null,
  buttons: form.buttons
    .filter((button) => button.is_active)
    .map((button, index) => {
      const meta = ACTION_META[button.action] || ACTION_META.custom;
      return {
        id: `preview-${index}`,
        ...button,
        resolved_icon: button.action === 'custom' && button.icon ? button.icon : meta.icon,
        kind: meta.kind,
        is_pending: ['url', 'mailto'].includes(meta.kind) && !button.href,
      };
    }),
}));

async function onLogoSelected(file) {
  fieldErrors.logo = '';
  const result = await store.uploadLogo(route.params.id, file);
  if (!result.success) {
    fieldErrors.logo = result.errors?.logo || 'No se pudo subir el logo.';
    return;
  }
  logoUrl.value = result.data.logo || '';
  notify.success({ title: 'Logo actualizado' });
}

async function onRemoveLogo() {
  fieldErrors.logo = '';
  const result = await store.removeLogo(route.params.id);
  if (!result.success) {
    fieldErrors.logo = 'No se pudo quitar el logo.';
    return;
  }
  logoUrl.value = '';
  notify.success({ title: 'Logo eliminado' });
}

async function onRemoveAvatar() {
  const result = await store.removeAvatar(route.params.id);
  if (!result.success) {
    notify.error({ title: 'No se pudo quitar la foto' });
    return;
  }
  avatarUrl.value = '';
  notify.success({ title: 'Foto eliminada' });
}

function addButton() {
  form.buttons.push({
    tier: form.buttons.length === 0 ? 'primary' : 'row',
    action: 'web',
    label: '',
    href: '',
    icon: '',
    is_active: true,
  });
}

function moveButton(index, delta) {
  const target = index + delta;
  if (target < 0 || target >= form.buttons.length) return;
  const [moved] = form.buttons.splice(index, 1);
  form.buttons.splice(target, 0, moved);
}

onMounted(async () => {
  const result = await store.fetchLinktree(route.params.id);
  if (!result.success) {
    loadError.value = 'No se pudo cargar el linktree. Recarga la página para intentarlo de nuevo.';
    notify.error({ title: 'No se pudo cargar el linktree' });
    return;
  }
  for (const field of FORM_FIELDS) form[field] = result.data[field] ?? form[field];
  logoUrl.value = result.data.logo || '';
  avatarUrl.value = result.data.avatar || '';
  form.buttons = result.data.buttons.map((button) => ({
    tier: button.tier,
    action: button.action,
    label: button.label,
    href: button.href,
    icon: button.icon,
    is_active: button.is_active,
  }));
  loaded.value = true;
  // La página no tenía baseline ni re-baseline: sin esto no hay contra qué
  // comparar y el aviso nunca podría distinguir lo cargado de lo editado.
  commitBaseline();
});

async function onSave() {
  buttonsError.value = '';
  for (const key of Object.keys(fieldErrors)) fieldErrors[key] = '';

  const payload = {};
  for (const field of FORM_FIELDS) payload[field] = form[field];
  payload.buttons = form.buttons.map((button, index) => ({ ...button, order: index }));

  const result = await store.updateLinktree(route.params.id, payload);
  if (!result.success) {
    const errors = result.errors || {};
    buttonsError.value = Array.isArray(errors.buttons) ? errors.buttons[0] : '';
    for (const [key, value] of Object.entries(errors)) {
      if (key !== 'buttons') fieldErrors[key] = Array.isArray(value) ? value[0] : String(value);
    }
    if (!result.errors) notify.error({ title: 'No se pudo guardar el linktree' });
    // Sin re-baseline: un guardado fallido deja el aviso puesto.
    return false;
  }
  notify.success({ title: 'Linktree guardado' });
  commitBaseline();
  return true;
}
</script>

<style scoped>
/* Phone-like dark frame around the live preview — the card inside uses the
   custom palette, same as the public page. */
.lt-preview-frame {
  background: #121212;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  justify-content: center;
  max-height: calc(100vh - 140px);
  overflow-y: auto;
}
</style>
