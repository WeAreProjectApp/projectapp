<template>
  <div class="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-12">
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
      <div class="mb-10 text-center">
        <h1 class="font-bold text-2xl tracking-tight text-white">
          Project<span class="text-white/60">App.</span>
        </h1>
        <p class="mt-2 text-sm font-medium uppercase tracking-[0.25em] text-white/50">Verificación</p>
      </div>

      <div class="rounded-3xl border border-white/[0.1] bg-white/95 p-8 shadow-2xl backdrop-blur-2xl">
        <h2 class="text-xl font-medium text-text-default">Ingresa el código</h2>
        <p class="mt-2 text-sm leading-6 text-text-muted">
          Te enviamos un código de 6 dígitos a <strong>{{ authStore.passwordReset.email || 'tu email' }}</strong>.
        </p>

        <div v-if="errorMessage" class="mt-6 rounded-2xl border border-red-500/20 bg-red-50 px-4 py-3 text-sm text-red-600">
          {{ errorMessage }}
          <span v-if="attemptsLeft !== null"> Te quedan {{ attemptsLeft }} intentos.</span>
        </div>

        <form class="mt-8 space-y-5" @submit.prevent="handleSubmit">
          <div>
            <label for="otp" class="mb-2 block text-sm font-medium text-esmerald/70">Código</label>
            <input
              id="otp"
              name="otp"
              v-model="code"
              inputmode="numeric"
              maxlength="6"
              autocomplete="one-time-code"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-center text-2xl tracking-[0.5em] text-text-default outline-none transition focus:border-border-default focus:ring-1 focus:ring-esmerald/10"
              placeholder="••••••"
            >
          </div>

          <BaseButton variant="primary" size="md" type="submit" class="w-full" :disabled="!canSubmit || authStore.isVerifying">
            {{ authStore.isVerifying ? 'Verificando...' : 'Verificar' }}
          </BaseButton>

          <BaseButton unstyled
            type="button"
            class="w-full text-sm text-esmerald/70 underline transition disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="authStore.isLoading"
            @click="handleResend"
          >
            Reenviar código
          </BaseButton>
        </form>

        <p class="mt-6 text-center text-sm text-text-muted">
          <NuxtLink :to="localePath('/platform/login')" class="underline">Volver al inicio de sesión</NuxtLink>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import BackgroundGradientAnimation from '~/components/ui/BackgroundGradientAnimation.vue'

definePageMeta({
  layout: false,
  middleware: ['platform-auth'],
})

useHead({ title: 'Verifica el código — ProjectApp' })

const authStore = usePlatformAuthStore()
const localePath = useLocalePath()
const code = ref('')
const localError = ref('')
const attemptsLeft = ref(null)

onMounted(() => {
  if (!authStore.passwordReset.requestToken) {
    navigateTo(localePath('/platform/forgot-password'))
  }
})

const errorMessage = computed(() => localError.value || authStore.error)
const canSubmit = computed(() => /^\d{6}$/.test(code.value.trim()))

async function handleSubmit() {
  localError.value = ''
  attemptsLeft.value = null
  const result = await authStore.verifyResetCode({ code: code.value.trim() })
  if (!result.success) {
    localError.value = result.message === 'invalid_code' ? 'Código incorrecto.' : result.message
    if (typeof result.attemptsLeft === 'number') attemptsLeft.value = result.attemptsLeft
    if (result.code === 'invalid_or_expired_token') {
      await navigateTo(localePath('/platform/forgot-password'))
    }
    return
  }
  await navigateTo(localePath('/platform/reset-password'))
}

async function handleResend() {
  if (!authStore.passwordReset.email) return
  await authStore.requestPasswordReset({ email: authStore.passwordReset.email })
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
