<template>
  <div id="platform-verify" class="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-12">
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
        <p class="mt-2 text-sm font-medium uppercase tracking-[0.25em] text-white/50">Verificación</p>
      </div>

      <div class="rounded-3xl border border-white/[0.1] bg-white/95 p-8 shadow-2xl backdrop-blur-2xl" data-enter>
        <h2 class="text-xl font-medium text-text-default">Confirma tu identidad</h2>
        <p class="mt-2 text-sm leading-6 text-text-muted">
          Enviamos un código de 6 dígitos a
          <span class="font-medium text-text-default">{{ authStore.pendingEmail || 'tu correo' }}</span>.
          Ingresa el código y define tu contraseña definitiva.
        </p>

        <div v-if="feedbackMessage" class="mt-6 rounded-2xl border px-4 py-3 text-sm" :class="feedbackVariant === 'success' ? 'border-emerald-500/20 bg-primary-soft text-text-brand' : 'border-red-500/20 bg-red-50 text-red-600'">
          {{ feedbackMessage }}
        </div>

        <form class="mt-8 space-y-6" @submit.prevent="handleSubmit">
          <div>
            <label class="mb-3 block text-sm font-medium text-esmerald/70">Código de verificación</label>
            <div class="grid grid-cols-6 gap-2" @paste="handlePaste">
              <input
                v-for="(_, index) in codeDigits"
                :key="index"
                :ref="(el) => setDigitRef(el, index)"
                v-model="codeDigits[index]"
                type="text"
                inputmode="numeric"
                maxlength="1"
                class="h-12 rounded-xl border border-border-default bg-surface-muted/40 text-center text-lg font-semibold text-text-default outline-none transition focus:border-border-default focus:ring-1 focus:ring-esmerald/10"
                @input="handleDigitInput(index, $event)"
                @keydown="handleKeydown(index, $event)"
              >
            </div>
          </div>

          <div>
            <label for="platform-new-password" class="mb-2 block text-sm font-medium text-esmerald/70">Nueva contraseña</label>
            <input
              id="platform-new-password"
              v-model="form.newPassword"
              type="password"
              autocomplete="new-password"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default focus:ring-1 focus:ring-esmerald/10"
              placeholder="Mínimo 8 caracteres"
            >
          </div>

          <div>
            <label for="platform-confirm-password" class="mb-2 block text-sm font-medium text-esmerald/70">Confirmar contraseña</label>
            <input
              id="platform-confirm-password"
              v-model="form.confirmPassword"
              type="password"
              autocomplete="new-password"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default focus:ring-1 focus:ring-esmerald/10"
              placeholder="Repite tu contraseña"
            >
          </div>

          <BaseButton variant="primary" size="md" type="submit" class="w-full" :disabled="authStore.isVerifying">
            {{ authStore.isVerifying ? 'Validando...' : 'Completar verificación' }}
          </BaseButton>
        </form>

        <button
          type="button"
          class="mt-5 text-sm font-medium text-text-muted transition hover:text-text-default disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="authStore.isVerifying"
          @click="handleResendCode"
        >
          Reenviar código
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { usePageEntrance } from '~/composables/usePageEntrance'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import BackgroundGradientAnimation from '~/components/ui/BackgroundGradientAnimation.vue'

definePageMeta({
  layout: false,
  middleware: ['platform-auth'],
})

useHead({
  title: 'Verificación de acceso — ProjectApp',
})

usePageEntrance('#platform-verify')

const authStore = usePlatformAuthStore()
const codeDigits = ref(['', '', '', '', '', ''])
const digitRefs = ref([])
const form = reactive({
  newPassword: '',
  confirmPassword: '',
})
const feedbackMessage = ref('')
const feedbackVariant = ref('error')

authStore.hydrate()

const verificationCode = computed(() => codeDigits.value.join(''))

function setDigitRef(element, index) {
  if (element) {
    digitRefs.value[index] = element
  }
}

function focusDigit(index) {
  nextTick(() => {
    digitRefs.value[index]?.focus()
    digitRefs.value[index]?.select?.()
  })
}

function handleDigitInput(index, event) {
  const rawValue = `${event.target.value || ''}`.replace(/\D/g, '')
  const digit = rawValue.slice(-1)
  codeDigits.value[index] = digit

  if (digit && index < codeDigits.value.length - 1) {
    focusDigit(index + 1)
  }
}

function handleKeydown(index, event) {
  if (event.key === 'Backspace' && !codeDigits.value[index] && index > 0) {
    focusDigit(index - 1)
    return
  }

  if (event.key === 'ArrowLeft' && index > 0) {
    focusDigit(index - 1)
    return
  }

  if (event.key === 'ArrowRight' && index < codeDigits.value.length - 1) {
    focusDigit(index + 1)
  }
}

function handlePaste(event) {
  const pastedValue = `${event.clipboardData?.getData('text') || ''}`
    .replace(/\D/g, '')
    .slice(0, 6)

  if (!pastedValue) return

  codeDigits.value = Array.from({ length: 6 }, (_, index) => pastedValue[index] || '')
  focusDigit(Math.min(pastedValue.length, 6) - 1)
  event.preventDefault()
}

async function handleSubmit() {
  feedbackMessage.value = ''
  feedbackVariant.value = 'error'

  if (!/^\d{6}$/.test(verificationCode.value)) {
    feedbackMessage.value = 'Ingresa el código completo de 6 dígitos.'
    return
  }

  if (form.newPassword.length < 8) {
    feedbackMessage.value = 'La contraseña debe tener al menos 8 caracteres.'
    return
  }

  if (form.newPassword !== form.confirmPassword) {
    feedbackMessage.value = 'Las contraseñas no coinciden.'
    return
  }

  const result = await authStore.verify({
    code: verificationCode.value,
    newPassword: form.newPassword,
  })

  if (!result.success) {
    feedbackMessage.value = result.message
    return
  }

  const localePath = useLocalePath()

  if (authStore.needsProfileCompletion) {
    await navigateTo(localePath('/platform/complete-profile'))
    return
  }

  await navigateTo(localePath(authStore.isClient ? '/platform/documents' : '/platform/dashboard'))
}

async function handleResendCode() {
  feedbackMessage.value = ''
  feedbackVariant.value = 'error'

  const result = await authStore.resendCode()
  if (!result.success) {
    feedbackMessage.value = result.message
    return
  }

  feedbackVariant.value = 'success'
  feedbackMessage.value = result.message
  codeDigits.value = ['', '', '', '', '', '']
  focusDigit(0)
}

onMounted(() => {
  focusDigit(0)
})
</script>

<style scoped>
.grain-overlay {
  position: absolute;
  inset: -50%;
  width: 200%;
  height: 200%;
  z-index: 1;
  pointer-events: none;
  opacity: 0.3;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  animation: grainDrift 8s linear infinite;
}

@keyframes grainDrift {
  0% { transform: translate(0, 0); }
  25% { transform: translate(-5%, 5%); }
  50% { transform: translate(5%, -3%); }
  75% { transform: translate(-3%, -5%); }
  100% { transform: translate(0, 0); }
}
</style>
