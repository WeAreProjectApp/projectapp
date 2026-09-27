<template>
  <BaseModal v-model="open" kind="form" padding="md">
    <div data-testid="qr-download-modal">
      <h3 class="text-lg font-bold text-text-default mb-4">Descargar QR — {{ card?.name }}</h3>

      <div class="flex justify-center mb-4">
        <canvas ref="canvasRef" data-testid="qr-canvas" />
      </div>

      <div class="space-y-3 mb-4">
        <BaseFormField label="Color del QR" for="qr-color">
          <input
            id="qr-color"
            v-model="foregroundColor"
            type="color"
            data-testid="qr-foreground-color"
            class="h-10 w-16 rounded-md border border-input-border bg-input-bg cursor-pointer"
          />
        </BaseFormField>

        <BaseFormField label="Color de fondo" for="qr-bg-color">
          <input
            id="qr-bg-color"
            v-model="backgroundColor"
            type="color"
            :disabled="transparentBackground"
            :title="transparentBackground ? 'Desactiva el fondo transparente para elegir un color de fondo.' : undefined"
            data-testid="qr-background-color"
            class="h-10 w-16 rounded-md border border-input-border bg-input-bg cursor-pointer disabled:opacity-50"
          />
        </BaseFormField>

        <p v-if="transparentBackground" class="text-xs text-text-subtle">
          Desactiva el fondo transparente para elegir un color de fondo.
        </p>

        <BaseCheckbox v-model="transparentBackground" data-testid="qr-transparent-toggle">
          Fondo transparente
        </BaseCheckbox>

        <BaseFormField label="Formato de descarga">
          <BaseSegmented
            v-model="downloadFormat"
            :options="[
              { value: 'png', label: 'PNG', testId: 'qr-format-png' },
              { value: 'svg', label: 'SVG', testId: 'qr-format-svg' },
            ]"
          />
        </BaseFormField>
      </div>

    </div>
    <template #footer>
      <BaseModalActions>
        <BaseButton variant="ghost" size="sm" @click="open = false">Cerrar</BaseButton>
        <BaseButton variant="primary" size="sm" data-testid="qr-download-button" @click="download">
          Descargar {{ downloadFormat.toUpperCase() }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue';
import QRCode from 'qrcode';
import BaseModal from '~/components/base/BaseModal.vue';
import BaseFormField from '~/components/base/BaseFormField.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseCheckbox from '~/components/base/BaseCheckbox.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  card: { type: Object, default: null },
});
const emit = defineEmits(['update:modelValue']);

const open = ref(props.modelValue);
watch(() => props.modelValue, (value) => { open.value = value; });
watch(open, (value) => emit('update:modelValue', value));

const canvasRef = ref(null);
const foregroundColor = ref('#000000');
const backgroundColor = ref('#ffffff');
const transparentBackground = ref(false);
const downloadFormat = ref('png');

function shortLinkFor(card) {
  return `${window.location.origin}/t/${card.id}/`;
}

function currentColors() {
  const lightColor = transparentBackground.value
    ? `${backgroundColor.value}00`
    : `${backgroundColor.value}ff`;
  return { dark: `${foregroundColor.value}ff`, light: lightColor };
}

async function renderQr() {
  if (!open.value || !props.card || !canvasRef.value) return;
  await QRCode.toCanvas(canvasRef.value, shortLinkFor(props.card), {
    width: 240,
    margin: 2,
    color: currentColors(),
  });
}

watch(
  [open, foregroundColor, backgroundColor, transparentBackground, () => props.card],
  async () => {
    await nextTick();
    await renderQr();
  },
);

onMounted(async () => {
  await nextTick();
  await renderQr();
});

function triggerDownload(href, filename) {
  const link = document.createElement('a');
  link.download = filename;
  link.href = href;
  link.click();
}

async function downloadSvg(filenameBase) {
  const svgString = await QRCode.toString(shortLinkFor(props.card), {
    type: 'svg',
    width: 240,
    margin: 2,
    color: currentColors(),
  });
  const blob = new Blob([svgString], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(blob);
  triggerDownload(url, `${filenameBase}.svg`);
  URL.revokeObjectURL(url);
}

function downloadPng(filenameBase) {
  if (!canvasRef.value) return;
  triggerDownload(canvasRef.value.toDataURL('image/png'), `${filenameBase}.png`);
}

async function download() {
  if (!props.card) return;
  const filenameBase = `qr-${props.card.name.replace(/\s+/g, '-').toLowerCase()}`;
  if (downloadFormat.value === 'svg') {
    await downloadSvg(filenameBase);
  } else {
    downloadPng(filenameBase);
  }
}
</script>
