<template>
  <section class="space-y-4" aria-label="Otras formas de iniciar sesión" data-testid="alternative-login">
    <BaseSegmented v-model="method" :options="methods" size="sm" />
    <BaseAlert v-if="error" variant="danger" role="alert">{{ error }}</BaseAlert>
    <p v-if="notice" class="text-sm text-text-muted" role="status">{{ notice }}</p>
    <form v-if="method === 'code'" class="space-y-4" @submit.prevent="challenge ? verify() : requestCode()">
      <BaseFormField label="Correo electrónico" required>
        <BaseInput v-model="email" type="email" autocomplete="username" :disabled="Boolean(challenge)" data-testid="access-email" />
      </BaseFormField>
      <BaseFormField v-if="challenge" label="Código de acceso" required>
        <BaseInput v-model="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="000000" data-testid="access-code" />
        <p class="mt-2 text-xs text-text-muted">El código dura 10 minutos. Solo funciona el último solicitado.</p>
      </BaseFormField>
      <LoginCaptcha v-if="captchaEnabled && !challenge" :site-key="siteKey" :reset-key="resetKey" :retry-available="captchaUnavailable" @update:token="captcha = $event" />
      <BaseButton type="submit" variant="primary" class="w-full" :loading="busy" :disabled="!ready || busy" :disabled-reason="!ready ? 'Completa el correo y la verificación.' : ''">
        {{ challenge ? 'Verificar e iniciar sesión' : 'Enviar código' }}
      </BaseButton>
      <BaseButton v-if="challenge" type="button" variant="link" :disabled="busy || seconds > 0" :disabled-reason="seconds > 0 ? `Espera ${seconds} segundos.` : ''" @click="restart">
        {{ seconds > 0 ? `Pedir otro código en ${seconds} s` : 'Pedir otro código o cambiar correo' }}
      </BaseButton>
    </form>
    <div v-else class="space-y-4">
      <p class="text-sm text-text-muted">Usa una cuenta Gmail o Google Workspace que el equipo haya habilitado.</p>
      <LoginCaptcha v-if="captchaEnabled && !googleReady" :site-key="siteKey" :reset-key="resetKey" :retry-available="captchaUnavailable" @update:token="captcha = $event" />
      <BaseButton v-if="!googleReady" variant="secondary" class="w-full" :loading="busy" :disabled="busy || !googleClient || (captchaEnabled && !captcha)" disabled-reason="Completa la verificación. Si Google no está disponible, usa código o contraseña." @click="prepareGoogle">Continuar con Google</BaseButton>
      <div ref="googleButton" class="flex justify-center" data-testid="access-google-button" />
    </div>
  </section>
</template>
<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import LoginCaptcha from '~/components/auth/LoginCaptcha.vue';
import { useAccessLogin } from '~/composables/useAccessLogin';
const props = defineProps({ surface: { type: String, required: true }, next: { type: String, default: '' } });
const emit = defineEmits(['authenticated']);
const runtime = useRuntimeConfig();
const captchaEnabled = runtime.public.recaptchaEnabled !== false;
const siteKey = runtime.public.recaptchaSiteKey;
const api = useAccessLogin(props.surface);
const methods = [{ value: 'code', label: 'Código por correo' }, { value: 'google', label: 'Google' }];
const method = ref('code');
const email = ref('');
const code = ref('');
const challenge = ref('');
const captcha = ref('');
const resetKey = ref(0);
const captchaUnavailable = ref(false);
const error = ref('');
const notice = ref('');
const busy = ref(false);
const seconds = ref(0);
const googleClient = ref('');
const configured = ref(false);
const googleReady = ref(false);
const googleButton = ref(null);
let timer;
let active = true;
let generation = 0;
const ready = computed(() => configured.value && (challenge.value ? /^[0-9]{6}$/.test(code.value) : email.value.includes('@') && (!captchaEnabled || Boolean(captcha.value))));
onMounted(async () => {
  try { googleClient.value = (await api.config()).google_client_id; configured.value = true; }
  catch { error.value = 'No pudimos preparar el acceso. Recarga la página para reintentar.'; }
});
onUnmounted(() => { active = false; clearInterval(timer); });
watch(method, () => { restart(); });
function restart() {
  generation += 1;
  challenge.value = ''; code.value = ''; captcha.value = ''; resetKey.value += 1;
  googleReady.value = false; notice.value = ''; error.value = '';
  if (googleButton.value) googleButton.value.replaceChildren();
}
async function attempt(action) {
  if (busy.value) return;
  busy.value = true; error.value = ''; captchaUnavailable.value = false;
  try { await action(); }
  catch (failure) {
    if (!active) return;
    const data = failure.response?.data || {};
    error.value = typeof data.detail === 'string' ? data.detail : 'No pudimos completar el acceso. Revisa los datos e intenta de nuevo.';
    captchaUnavailable.value = data.code === 'captcha_unavailable';
    googleReady.value = false;
    googleButton.value?.replaceChildren();
  } finally { busy.value = false; captcha.value = ''; resetKey.value += 1; }
}
async function requestCode() {
  if (!ready.value) return;
  const requestGeneration = generation;
  await attempt(async () => {
    const response = await api.post('email-request', { email: email.value.trim(), recaptcha_token: captcha.value });
    if (!active || generation !== requestGeneration || method.value !== 'code') return;
    challenge.value = response.challenge_id; notice.value = response.detail;
    seconds.value = response.retry_after; clearInterval(timer);
    timer = setInterval(() => { seconds.value = Math.max(0, seconds.value - 1); }, 1000);
  });
}
async function finish(data) {
  code.value = ''; challenge.value = '';
  if (active) emit('authenticated', data);
}
async function verify() {
  if (!ready.value) return;
  const requestGeneration = generation;
  await attempt(async () => {
    const data = await api.post('email-verify', { challenge_id: challenge.value, code: code.value, next: props.next });
    if (generation === requestGeneration && method.value === 'code') await finish(data);
  });
}
function loadGoogle() {
  if (window.google?.accounts?.id) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client'; script.async = true;
    script.onload = resolve; script.onerror = () => reject(new Error('google_unavailable'));
    document.head.appendChild(script);
  });
}
async function prepareGoogle() {
  if (!configured.value || !googleClient.value || (captchaEnabled && !captcha.value)) return;
  await attempt(async () => {
    const requestGeneration = generation;
    const { nonce } = await api.post('google-challenge', { recaptcha_token: captcha.value });
    await loadGoogle();
    if (!active || method.value !== 'google' || generation !== requestGeneration) return;
    googleReady.value = true; await nextTick();
    window.google.accounts.id.initialize({ client_id: googleClient.value, nonce, auto_select: false, callback: async (response) => {
      if (!active || method.value !== 'google' || generation !== requestGeneration) return;
      await attempt(async () => finish(await api.post('google-verify', { credential: response.credential, next: props.next })));
    } });
    window.google.accounts.id.renderButton(googleButton.value, { theme: 'outline', size: 'large', text: 'continue_with', width: 260 });
  });
}
</script>
