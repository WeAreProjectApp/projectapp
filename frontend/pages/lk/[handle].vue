<template>
  <div class="lt-page">
    <div v-if="store.isLoading" class="lt-status" data-testid="linktree-loading">Cargando…</div>

    <div v-else-if="notFound" class="lt-status" data-testid="linktree-not-found">
      <p class="lt-status__title">Este enlace no está disponible.</p>
      <p class="lt-status__hint">Verifica la dirección o vuelve a escanear el código QR.</p>
    </div>

    <LinktreeCard
      v-else-if="tree"
      :tree="tree"
      @action="onButtonAction"
      @install="installApp"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useLinktreesStore } from '~/stores/linktrees';
import LinktreeCard from '~/components/Linktree/LinktreeCard.vue';

definePageMeta({ layout: false });

const route = useRoute();
const { localeProperties } = useI18n();
const store = useLinktreesStore();
const notFound = ref(false);
const installPrompt = ref(null);

const handle = computed(() =>
  String(route.params.handle || '').replace(/^@/, '')
);
const tree = computed(() => store.publicLinktree);

useHead(() => ({
  htmlAttrs: { lang: localeProperties.value.language },
  title: tree.value?.display_name
    ? `${tree.value.display_name} · ProjectApp.`
    : 'ProjectApp.',
  meta: [{ name: 'robots', content: 'noindex' }],
}));

const downloadVcard = () => {
  const t = tree.value;
  const first = t.vcard_first_name || t.display_name || 'ProjectApp';
  const last = t.vcard_last_name || '';
  const lines = [
    'BEGIN:VCARD',
    'VERSION:3.0',
    `N:${last};${first};;;`,
    `FN:${[first, last].filter(Boolean).join(' ')}`,
    t.vcard_org ? `ORG:${t.vcard_org}` : null,
    t.role ? `TITLE:${t.role}` : null,
    t.vcard_email ? `EMAIL;TYPE=WORK:${t.vcard_email}` : null,
    t.vcard_tel ? `TEL;TYPE=CELL:${t.vcard_tel}` : null,
    t.vcard_url ? `URL:${t.vcard_url}` : null,
    'END:VCARD',
  ].filter(Boolean);
  const blob = new Blob([lines.join('\r\n')], { type: 'text/vcard;charset=utf-8' });
  const anchor = document.createElement('a');
  anchor.href = URL.createObjectURL(blob);
  anchor.download = `${[first, last].filter(Boolean).join('-')}-ProjectApp.vcf`.toLowerCase();
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(anchor.href), 2000);
};

const installApp = async () => {
  const prompt = installPrompt.value;
  if (prompt) {
    prompt.prompt();
    await prompt.userChoice;
    installPrompt.value = null;
    return;
  }
  window.alert(
    'Para guardar la tarjeta: abre el menú del navegador y elige "Añadir a la pantalla de inicio".'
  );
};

const onButtonAction = (button) => {
  if (button.kind === 'download-vcard') downloadVcard();
  if (button.kind === 'pwa-install') installApp();
};

const onBeforeInstallPrompt = (event) => {
  event.preventDefault();
  installPrompt.value = event;
};

onMounted(async () => {
  window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt);
  const result = await store.fetchPublicLinktree(handle.value);
  if (!result.success) notFound.value = true;
  else if (result.data.template_url) window.location.replace(result.data.template_url);
});

onUnmounted(() => {
  window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt);
});
</script>

<style scoped>
/* Fixed brand palette by design (Linktree.dc.html) — not theme tokens. */
.lt-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: #121212;
  display: flex;
  justify-content: center;
  font-family: 'Ubuntu', system-ui, sans-serif;
}

.lt-status {
  align-self: center;
  text-align: center;
  color: #809490;
  font-size: 14px;
  padding: 24px;
}
.lt-status__title { color: #ffffff; font-size: 16px; margin: 0 0 6px; }
.lt-status__hint { margin: 0; }
</style>
