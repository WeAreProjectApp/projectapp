<template>
  <div id="platform-login" class="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-12">
    <BackgroundGradientAnimation
      gradient-background-start="rgb(0, 41, 33)"
      gradient-background-end="rgb(0, 25, 20)"
      first-color="0, 120, 100"
      second-color="0, 80, 90"
      third-color="30, 80, 60"
      fourth-color="0, 60, 80"
      fifth-color="20, 100, 70"
      pointer-color="0, 100, 80"
      size="100%"
      blending-value="hard-light"
      :interactive="true"
      container-class-name="!w-full !h-full !absolute !inset-0"
    />

    <div class="grain-overlay"></div>

    <div class="relative z-10 w-full max-w-md">
      <div class="mb-10 text-center" data-enter>
        <h1 class="font-bold text-2xl tracking-tight text-white">
          Project<span class="text-white/60">App.</span>
        </h1>
        <p class="mt-2 text-sm font-medium uppercase tracking-[0.25em] text-white/50">Portal</p>
      </div>

      <div class="rounded-3xl border border-white/[0.1] bg-white/95 p-8 shadow-2xl backdrop-blur-2xl" data-enter>
        <h2 class="text-xl font-medium text-text-default">Inicia sesión</h2>
        <p class="mt-2 text-sm leading-6 text-text-muted">
          Ingresa con tu email y contraseña para acceder al portal.
        </p>

        <div v-if="errorMessage" class="mt-6 rounded-2xl border border-red-500/20 bg-red-50 px-4 py-3 text-sm text-red-600">
          {{ errorMessage }}
        </div>

        <form class="mt-8 space-y-5" @submit.prevent="handleSubmit">
          <div>
            <label for="platform-email" class="mb-2 block text-sm font-medium text-esmerald/70">Email</label>
            <input
              id="platform-email"
              v-model="form.email"
              type="email"
              autocomplete="email"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default focus:ring-1 focus:ring-esmerald/10"
              placeholder="cliente@empresa.com"
            >
          </div>

          <div>
            <label for="platform-password" class="mb-2 block text-sm font-medium text-esmerald/70">Contraseña</label>
            <input
              id="platform-password"
              v-model="form.password"
              type="password"
              autocomplete="current-password"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default focus:ring-1 focus:ring-esmerald/10"
              placeholder="••••••••"
            >
          </div>

          <LoginCaptcha v-if="recaptchaEnabled" :site-key="recaptchaSiteKey" :reset-key="captchaResetKey" :retry-available="captchaUnavailable" @update:token="recaptchaToken = $event" />

          <BaseButton variant="primary" size="md" type="submit" class="w-full" :disabled="!canSubmit || authStore.isLoading" :disabled-reason="recaptchaEnabled && !recaptchaToken ? t('captcha.required') : ''">
            {{ authStore.isLoading ? 'Ingresando...' : 'Iniciar sesión' }}
          </BaseButton>
        </form>

        <p class="mt-6 text-center text-sm text-text-muted">
          <NuxtLink :to="localePath('/platform/forgot-password')" class="underline">¿Olvidaste tu contraseña?</NuxtLink>
        </p>
      </div>

      <p class="mt-8 text-center text-sm leading-6 text-white/40" data-enter>
        Si es tu primer acceso, después de validar tus credenciales temporales te guiaremos para configurar tu contraseña definitiva.
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { usePageEntrance } from '~/composables/usePageEntrance'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import LoginCaptcha from '~/components/auth/LoginCaptcha.vue'
import BackgroundGradientAnimation from '~/components/ui/BackgroundGradientAnimation.vue'

definePageMeta({
  layout: false,
  middleware: ['platform-auth'],
})

useHead({
  title: 'Acceso a plataforma — ProjectApp',
})

const config = useRuntimeConfig()
const recaptchaSiteKey = config.public.recaptchaSiteKey
const recaptchaEnabled = config.public.recaptchaEnabled !== false
const recaptchaToken = ref('')
const captchaResetKey = ref(0)
const captchaUnavailable = ref(false)
const { t } = useI18n()

onMounted(() => localStorage.setItem('platform_theme', 'light'))

usePageEntrance('#platform-login')

const route = useRoute()
const authStore = usePlatformAuthStore()
const localePath = useLocalePath()
const form = reactive({
  email: '',
  password: '',
})
const localError = ref('')

authStore.hydrate()

const errorMessage = computed(() => localError.value || authStore.error)
const canSubmit = computed(() => {
  const hasCredentials = Boolean(form.email.trim()) && Boolean(form.password)
  if (recaptchaEnabled) return hasCredentials && Boolean(recaptchaToken.value)
  return hasCredentials
})

async function handleSubmit() {
  if (authStore.isLoading) return
  localError.value = ''
  captchaUnavailable.value = false

  const email = form.email.trim()
  if (!email.includes('@')) {
    localError.value = 'Ingresa un email válido.'
    return
  }

  if (recaptchaEnabled && !recaptchaToken.value) {
    localError.value = t('captcha.required')
    return
  }

  const payload = { ...form }
  if (recaptchaToken.value) {
    payload.recaptcha_token = recaptchaToken.value
  }

  const result = await authStore.login(payload)
  if (!result.success) {
    captchaUnavailable.value = result.code === 'captcha_unavailable'
    localError.value = ['captcha_required', 'captcha_invalid', 'captcha_unavailable'].includes(result.code)
      ? t(`captcha.${result.code}`) : result.message
    recaptchaToken.value = ''
    captchaResetKey.value += 1
    return
  }

  if (result.requiresVerification) {
    await navigateTo(localePath('/platform/verify'))
    return
  }

  if (authStore.needsProfileCompletion) {
    await navigateTo(localePath('/platform/complete-profile'))
    return
  }

  const defaultTarget = localePath(authStore.isClient ? '/platform/documents' : '/platform/dashboard')
  const redirectTarget = typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/')
    ? route.query.redirect
    : defaultTarget

  await navigateTo(redirectTarget)
}
</script>

<style scoped>
.grain-overlay {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  opacity: 0.3;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
}
</style>
