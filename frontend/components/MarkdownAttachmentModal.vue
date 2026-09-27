<template>
  <Teleport to="body">
    <div v-if="open"
      class="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm p-0 panel-portrait:p-4"
      @click.self="onClose">
      <div class="bg-surface dark:bg-primary panel-portrait:rounded-2xl shadow-overlay w-full max-w-7xl h-dvh panel-portrait:h-[90dvh] flex flex-col overflow-hidden">

        <!-- Header -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-border-muted dark:border-white/[0.06]">
          <div>
            <h2 class="text-base font-semibold text-text-default dark:text-white">Adjuntar documento PDF al correo</h2>
            <p class="text-xs text-text-muted dark:text-green-light/60 mt-0.5">
              Escribe en markdown, previsualiza el PDF y adjúntalo al composer.
            </p>
          </div>
          <BaseActionButton action="close" label="Cerrar editor de adjunto" @click="onClose" />
        </div>

        <!-- Body: 2 columns -->
        <div class="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-0 overflow-hidden">
          <!-- Editor column -->
          <div class="p-6 overflow-y-auto border-r border-border-muted dark:border-white/[0.06] space-y-4">
            <div>
              <label class="block text-xs font-medium text-text-default dark:text-green-light mb-1">Título del documento</label>
              <input v-model="title" type="text" placeholder="Ej: Resumen de cambios al alcance"
                class="w-full px-3 py-2 text-sm border border-border-default dark:border-white/[0.08] dark:bg-surface/[0.03] dark:text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-focus-ring/30" />
            </div>

            <div v-if="showDiagnosticTemplates">
              <label class="block text-xs font-medium text-text-default dark:text-green-light mb-1">Plantillas base</label>
              <div class="flex flex-wrap gap-2">
                <BaseButton v-for="t in DIAGNOSTIC_TEMPLATES" :key="t.slug"
                  variant="secondary" size="sm"
                  :disabled="templateBusy[t.slug]"
                  @click="copyTemplate(t.slug)">
                  <BaseActionIcon action="copy" />
                  {{ templateCopied[t.slug] ? '¡Copiado!' : `Copiar ${t.label}` }}
                </BaseButton>
              </div>
              <p class="text-[11px] text-text-subtle dark:text-green-light/40 mt-1">
                Copia la plantilla, edítala y pégala en el contenido.
              </p>
            </div>

            <div>
              <label class="block text-xs font-medium text-text-default dark:text-green-light mb-1">Contenido (markdown)</label>
              <textarea v-model="markdown" rows="14"
                placeholder="# Encabezado&#10;&#10;Párrafo de introducción…"
                class="w-full px-3 py-2 text-sm font-mono border border-border-default dark:border-white/[0.08] dark:bg-surface/[0.03] dark:text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-focus-ring/30 resize-y min-h-[280px]"></textarea>
            </div>

            <fieldset class="space-y-2">
              <legend class="text-xs font-medium text-text-default dark:text-green-light mb-1">Portadas</legend>
              <label class="flex items-center gap-2 text-xs text-text-default dark:text-green-light">
                <input type="checkbox" v-model="includePortada" class="rounded border-input-border text-text-brand focus:ring-focus-ring/30" />
                Portada principal
              </label>
              <label class="flex items-center gap-2 text-xs text-text-default dark:text-green-light">
                <input type="checkbox" v-model="includeSubportada" class="rounded border-input-border text-text-brand focus:ring-focus-ring/30" />
                Portada secundaria (carátula con título)
              </label>
              <label class="flex items-center gap-2 text-xs text-text-default dark:text-green-light">
                <input type="checkbox" v-model="includeContraportada" class="rounded border-input-border text-text-brand focus:ring-focus-ring/30" />
                Contraportada
              </label>
            </fieldset>

            <div v-if="error" class="text-xs text-red-500">{{ error }}</div>

            <BaseButton variant="primary" size="sm" :disabled="!canPreview" :loading="loading"
              @click="generatePreview">
              <BaseActionIcon action="view" />
              {{ loading ? 'Generando…' : (previewUrl ? 'Actualizar vista previa' : 'Vista previa') }}
            </BaseButton>
          </div>

          <!-- Preview column -->
          <div class="bg-surface-muted dark:bg-surface/[0.02] flex flex-col overflow-hidden">
            <div v-if="previewUrl" class="flex-1 min-h-0">
              <iframe :src="previewUrl" class="w-full h-full border-0" title="Vista previa PDF"></iframe>
            </div>
            <div v-else class="flex-1 flex items-center justify-center text-center p-8">
              <div class="max-w-xs">
                <svg class="w-12 h-12 mx-auto text-text-subtle dark:text-white/20 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p class="text-xs text-text-subtle dark:text-green-light/40">
                  Escribe un título y contenido, luego pulsa <span class="font-medium">Vista previa</span> para ver cómo queda el PDF.
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <BaseModalActions class="pb-[max(1rem,env(safe-area-inset-bottom))]">
          <BaseButton variant="ghost" size="sm" @click="onClose">
            Cancelar
          </BaseButton>
          <BaseButton variant="primary" size="sm" :disabled="!canAttach" :loading="loading"
            @click="attachToEmail">
            <BaseActionIcon action="attach" />
            {{ loading ? 'Procesando…' : 'Adjuntar al correo' }}
          </BaseButton>
        </BaseModalActions>

      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';
import axios from 'axios';
import { get_request, getCookie } from '~/stores/services/request_http';

const props = defineProps({
  open: { type: Boolean, default: false },
  endpoint: { type: String, required: true },
  showDiagnosticTemplates: { type: Boolean, default: false },
});

const DIAGNOSTIC_TEMPLATES = [
  { slug: 'diagnostico-aplicacion', label: 'Diagnóstico de Aplicación' },
  { slug: 'diagnostico-tecnico', label: 'Diagnóstico Técnico' },
  { slug: 'anexo', label: 'Anexo' },
];

const templateCache = reactive({});
const templateBusy = reactive({});
const templateCopied = reactive({});
let copyFeedbackTimer = null;

const emit = defineEmits(['close', 'attach']);

const title = ref('');
const markdown = ref('');
const includePortada = ref(true);
const includeSubportada = ref(true);
const includeContraportada = ref(true);

const previewUrl = ref(null);
const previewSnapshot = ref(null);
const loading = ref(false);
const error = ref('');

const canPreview = computed(() => title.value.trim() && markdown.value.trim());
const canAttach = computed(() => canPreview.value);

const currentSnapshot = computed(() => JSON.stringify({
  title: title.value.trim(),
  markdown: markdown.value,
  p: includePortada.value,
  s: includeSubportada.value,
  c: includeContraportada.value,
}));

function revokePreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value);
    previewUrl.value = null;
  }
}

async function fetchPdfBlob() {
  const payload = {
    title: title.value.trim(),
    markdown: markdown.value,
    include_portada: includePortada.value,
    include_subportada: includeSubportada.value,
    include_contraportada: includeContraportada.value,
  };
  const response = await axios.post(
    `/api/${props.endpoint}`,
    payload,
    {
      responseType: 'blob',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken'),
      },
    },
  );
  return response.data;
}

async function generatePreview() {
  if (!canPreview.value) return;
  loading.value = true;
  error.value = '';
  try {
    const blob = await fetchPdfBlob();
    revokePreview();
    previewUrl.value = URL.createObjectURL(blob);
    previewSnapshot.value = currentSnapshot.value;
  } catch (e) {
    error.value = 'No se pudo generar la vista previa.';
  } finally {
    loading.value = false;
  }
}

function slugify(s) {
  return (s || 'documento')
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'documento';
}

async function attachToEmail() {
  if (!canAttach.value) return;
  loading.value = true;
  error.value = '';
  try {
    let blob;
    if (previewUrl.value && previewSnapshot.value === currentSnapshot.value) {
      blob = await (await fetch(previewUrl.value)).blob();
    } else {
      blob = await fetchPdfBlob();
    }
    const filename = `${slugify(title.value)}.pdf`;
    const file = new File([blob], filename, { type: 'application/pdf' });
    emit('attach', file);
    emit('close');
  } catch (e) {
    error.value = 'No se pudo adjuntar el documento.';
  } finally {
    loading.value = false;
  }
}

async function copyTemplate(slug) {
  templateBusy[slug] = true;
  try {
    if (!templateCache[slug]) {
      const res = await get_request(`diagnostic-templates/${slug}/`);
      templateCache[slug] = res.data?.content_markdown || '';
    }
    await navigator.clipboard.writeText(templateCache[slug]);
    templateCopied[slug] = true;
    clearTimeout(copyFeedbackTimer);
    copyFeedbackTimer = setTimeout(() => { templateCopied[slug] = false; }, 2000);
  } catch (e) {
    error.value = 'No se pudo copiar la plantilla.';
  } finally {
    templateBusy[slug] = false;
  }
}

function onClose() {
  emit('close');
}

function resetState() {
  title.value = '';
  markdown.value = '';
  includePortada.value = true;
  includeSubportada.value = true;
  includeContraportada.value = true;
  revokePreview();
  previewSnapshot.value = null;
  error.value = '';
  clearTimeout(copyFeedbackTimer);
  for (const k of Object.keys(templateCopied)) templateCopied[k] = false;
  for (const k of Object.keys(templateBusy)) templateBusy[k] = false;
}

watch(() => props.open, (isOpen) => {
  if (!isOpen) resetState();
});

onBeforeUnmount(() => {
  revokePreview();
  clearTimeout(copyFeedbackTimer);
});
</script>
