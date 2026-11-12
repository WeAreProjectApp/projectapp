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
        <p class="mt-2 text-sm font-medium uppercase tracking-[0.25em] text-white/50">Recuperación</p>
      </div>

      <div class="rounded-3xl border border-white/[0.1] bg-white/95 p-8 shadow-2xl backdrop-blur-2xl">
        <h2 class="text-xl font-medium text-text-default">¿Olvidaste tu contraseña?</h2>
        <p class="mt-2 text-sm leading-6 text-text-muted">
          Ingresa tu email y te enviaremos un código para restablecerla.
        </p>

        <div v-if="errorMessage" class="mt-6 rounded-2xl border border-red-500/20 bg-red-50 px-4 py-3 text-sm text-red-600">
          {{ errorMessage }}
        </div>

        <form class="mt-8 space-y-5" @submit.prevent="handleSubmit">
          <div>
            <label for="forgot-email" class="mb-2 block text-sm font-medium text-esmerald/70">Email</label>
            <input
              id="forgot-email"
              v-model="email"
              type="email"
              autocomplete="email"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default focus:ring-1 focus:ring-esmerald/10"
              placeholder="cliente@empresa.com"
            >
          </div>

          <BaseButton variant="primary" size="md" type="submit" class="w-full" :disabled="!canSubmit || authStore.isLoading">
            {{ authStore.isLoading ? 'Enviando...' : 'Enviar código' }}
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
import { computed, ref } from 'vue'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import BackgroundGradientAnimation from '~/components/ui/BackgroundGradientAnimation.vue'

definePageMeta({
  layout: false,
  middleware: ['platform-auth'],
})

useHead({ title: 'Recupera tu contraseña — ProjectApp' })

const authStore = usePlatformAuthStore()
const localePath = useLocalePath()

const email = ref('')
const localError = ref('')

const errorMessage = computed(() => localError.value || authStore.error)
const canSubmit = computed(() => Boolean(email.value.trim()))

async function handleSubmit() {
  localError.value = ''
  const trimmed = email.value.trim()
  if (!trimmed.includes('@')) {
    localError.value = 'Ingresa un email válido.'
    return
  }
  const result = await authStore.requestPasswordReset({ email: trimmed })
  if (!result.success) {
    localError.value = result.message
    return
  }
  await navigateTo(localePath('/platform/verify-code'))
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
