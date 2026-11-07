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
        <p class="mt-2 text-sm font-medium uppercase tracking-[0.25em] text-white/50">Nueva contraseña</p>
      </div>

      <div class="rounded-3xl border border-white/[0.1] bg-white/95 p-8 shadow-2xl backdrop-blur-2xl">
        <h2 class="text-xl font-medium text-text-default">Define tu nueva contraseña</h2>
        <p class="mt-2 text-sm leading-6 text-text-muted">
          Al guardar quedarás conectado a la plataforma automáticamente.
        </p>

        <div v-if="errorMessage" class="mt-6 rounded-2xl border border-red-500/20 bg-red-50 px-4 py-3 text-sm text-red-600">
          {{ errorMessage }}
          <ul v-if="errorList.length" class="mt-2 list-disc space-y-1 pl-4">
            <li v-for="(err, i) in errorList" :key="i">{{ err }}</li>
          </ul>
        </div>

        <form class="mt-8 space-y-5" @submit.prevent="handleSubmit">
          <div>
            <label for="new-pass" class="mb-2 block text-sm font-medium text-esmerald/70">Nueva contraseña</label>
            <input
              id="new-pass"
              v-model="newPassword"
              type="password"
              autocomplete="new-password"
              minlength="8"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default focus:ring-1 focus:ring-esmerald/10"
              placeholder="Mínimo 8 caracteres"
            >
          </div>

          <div>
            <label for="confirm-pass" class="mb-2 block text-sm font-medium text-esmerald/70">Confirmar contraseña</label>
            <input
              id="confirm-pass"
              v-model="confirm"
              type="password"
              autocomplete="new-password"
              minlength="8"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default focus:ring-1 focus:ring-esmerald/10"
              placeholder="Repite la contraseña"
            >
          </div>

          <BaseButton variant="primary" size="md" type="submit" class="w-full" :disabled="!canSubmit || authStore.isLoading">
            {{ authStore.isLoading ? 'Guardando...' : 'Guardar contraseña' }}
          </BaseButton>
        </form>
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

useHead({ title: 'Restablece tu contraseña — ProjectApp' })

const authStore = usePlatformAuthStore()
const localePath = useLocalePath()
const newPassword = ref('')
const confirm = ref('')
const localError = ref('')
const errorList = ref([])

onMounted(() => {
  if (!authStore.passwordReset.verifiedToken) {
    navigateTo(localePath('/platform/forgot-password'))
  }
})

const errorMessage = computed(() => localError.value || authStore.error)
const canSubmit = computed(() => newPassword.value.length >= 8 && newPassword.value === confirm.value)

async function handleSubmit() {
  localError.value = ''
  errorList.value = []
  if (newPassword.value !== confirm.value) {
    localError.value = 'Las contraseñas no coinciden.'
    return
  }
  const result = await authStore.confirmPasswordReset({ newPassword: newPassword.value })
  if (!result.success) {
    localError.value = result.code === 'weak_password' ? 'La contraseña no cumple los requisitos.' : result.message
    if (Array.isArray(result.errors)) errorList.value = result.errors
    if (result.code === 'invalid_or_expired_token') {
      await navigateTo(localePath('/platform/forgot-password'))
    }
    return
  }
  await navigateTo(localePath('/platform'))
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
