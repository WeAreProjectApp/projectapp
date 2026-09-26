<template>
  <main class="min-h-screen bg-surface-muted px-4 py-10 panel-portrait:py-16" data-testid="secure-link-view-page">
    <div class="mx-auto w-full max-w-2xl space-y-6">
      <p class="text-lg font-bold text-text-default">{{ t('secureLinks.brand') }}</p>

      <section class="space-y-5 rounded-2xl border border-border-default bg-surface p-6 shadow-sm panel-portrait:p-8">
        <div v-if="state === 'loading'" class="py-10 text-center text-sm text-text-muted" role="status">
          {{ t('secureLinks.loading') }}
        </div>

        <template v-else-if="state === 'active'">
          <h1 class="text-2xl font-light text-text-default">{{ t('secureLinks.viewTitle') }}</h1>
          <p class="text-sm text-text-muted">
            {{ info.type_label }} · {{ t('secureLinks.viewFrom', { sender: info.sender }) }}
          </p>
          <p class="text-sm text-text-muted">{{ t('secureLinks.viewExpires', { date: formatDateTime(info.expires_at, { locale: language }) }) }}</p>
          <BaseAlert variant="warning">{{ t('secureLinks.viewWarning') }}</BaseAlert>
          <BaseButton variant="primary" :loading="revealing" data-testid="secure-link-reveal" @click="reveal">
            {{ revealing ? t('secureLinks.revealing') : t('secureLinks.reveal') }}
          </BaseButton>
        </template>

        <template v-else-if="state === 'revealed'">
          <h1 class="text-2xl font-light text-text-default">{{ content.title || t('secureLinks.revealedTitle') }}</h1>
          <p class="text-sm text-text-muted">{{ content.type_label }}</p>
          <BaseAlert variant="warning">{{ t('secureLinks.revealedNotice') }}</BaseAlert>
          <SecureLinkContent :fields="content.fields" />
        </template>

        <template v-else-if="state === 'staff_only'">
          <h1 class="text-2xl font-light text-text-default">{{ t('secureLinks.staffOnlyTitle') }}</h1>
          <p class="text-sm text-text-muted">{{ t('secureLinks.staffOnlyBody') }}</p>
          <BaseButton variant="primary" data-testid="secure-link-staff-login" @click="goToLogin">
            {{ t('secureLinks.staffLogin') }}
          </BaseButton>
        </template>

        <template v-else-if="['consumed', 'expired', 'revoked'].includes(state)">
          <h1 class="text-2xl font-light text-text-default" :data-testid="`secure-link-state-${state}`">{{ t(`secureLinks.${state}Title`) }}</h1>
          <p class="text-sm text-text-muted">{{ t('secureLinks.reactivateHint') }}</p>
        </template>

        <template v-else-if="state === 'not_found'">
          <h1 class="text-2xl font-light text-text-default" data-testid="secure-link-state-not_found">{{ t('secureLinks.notFoundTitle') }}</h1>
          <p class="text-sm text-text-muted">{{ t('secureLinks.notFoundBody') }}</p>
        </template>

        <template v-else>
          <h1 class="text-2xl font-light text-text-default">{{ errorMessage || t('secureLinks.genericError') }}</h1>
          <BaseButton variant="secondary" data-testid="secure-link-retry" @click="load">{{ t('secureLinks.retry') }}</BaseButton>
        </template>
      </section>
    </div>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import BaseAlert from '~/components/base/BaseAlert.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import SecureLinkContent from '~/components/secureLinks/SecureLinkContent.vue';
import { useSecureLinksStore } from '~/stores/secure_links';
import { formatDateTime } from '~/utils/formatDate';

definePageMeta({ layout: false });

const PENDING_KEY = 'secure-link-pending-token';
const { t, locale } = useI18n();
const store = useSecureLinksStore();
const language = computed(() => (locale.value.startsWith('en') ? 'en' : 'es'));

const state = ref('loading');
const info = ref({});
const content = ref(null);
const revealing = ref(false);
const errorMessage = ref('');
let token = '';

useHead(() => ({
  title: t('secureLinks.pageTitle'),
  meta: [
    { name: 'robots', content: 'noindex,nofollow,noarchive' },
    { name: 'referrer', content: 'no-referrer' },
  ],
}));

function readToken() {
  // The token lives in the URL fragment so it never reaches server logs.
  const fromHash = decodeURIComponent(window.location.hash.replace(/^#/, ''));
  if (fromHash) return fromHash;
  try {
    const pending = sessionStorage.getItem(PENDING_KEY) || '';
    sessionStorage.removeItem(PENDING_KEY);
    if (pending) window.history.replaceState(null, '', `${window.location.pathname}#${pending}`);
    return pending;
  } catch {
    return '';
  }
}

function applyError(error) {
  const byCode = {
    link_not_found: 'not_found', link_consumed: 'consumed', link_expired: 'expired',
    link_revoked: 'revoked', staff_only: 'staff_only',
  };
  state.value = byCode[error?.code] || 'error';
  errorMessage.value = state.value === 'error' ? error?.message || '' : '';
}

async function load() {
  state.value = 'loading';
  if (!token) {
    state.value = 'not_found';
    return;
  }
  const result = await store.publicStatus(token);
  if (!result.success) {
    applyError(result.error);
    return;
  }
  info.value = result.data;
  if (result.data.status !== 'active') state.value = result.data.status;
  else state.value = result.data.can_reveal ? 'active' : 'staff_only';
}

async function reveal() {
  revealing.value = true;
  const result = await store.publicReveal(token);
  revealing.value = false;
  if (!result.success) {
    applyError(result.error);
    return;
  }
  content.value = result.data;
  state.value = 'revealed';
}

function goToLogin() {
  try {
    sessionStorage.setItem(PENDING_KEY, token);
  } catch {
    // Without storage the team can still open it from the panel.
  }
  window.location.assign(`/admin/login/?next=${encodeURIComponent(window.location.pathname)}`);
}

onMounted(() => {
  token = readToken();
  load();
});

onBeforeUnmount(() => {
  content.value = null;
});
</script>
