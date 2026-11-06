<template>
  <div id="platform-profile" class="mx-auto max-w-3xl">
    <h1 class="mb-1 text-xl font-bold text-text-default">Configuracion</h1>
    <p class="mb-8 text-sm text-text-muted">Revisa y actualiza tu informacion personal.</p>

    <!-- Success message -->
    <div
      v-if="successMessage"
      class="mb-6 rounded-xl border border-emerald-200 bg-primary-soft px-4 py-3 text-sm text-text-brand dark:border-emerald-500/20 dark:bg-emerald-500/10"
    >
      {{ successMessage }}
    </div>

    <!-- Error message -->
    <div
      v-if="errorMessage"
      class="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-400"
    >
      {{ errorMessage }}
    </div>

    <div class="grid gap-6 lg:grid-cols-3">
      <!-- Avatar card -->
      <div class="rounded-3xl border border-border-default bg-surface p-6 shadow-sm">
        <div class="flex flex-col items-center gap-4">
          <button
            type="button"
            class="touch-target group relative h-24 w-24 cursor-pointer rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2"
            aria-label="Cambiar foto de perfil"
            data-responsive-touch-target
            @click="triggerFileInput"
          >
            <div class="h-full w-full overflow-hidden rounded-full border-2 border-border-default">
              <img
                v-if="avatarPreview || avatarUrl"
                :src="avatarPreview || avatarUrl"
                alt="Avatar"
                class="h-full w-full object-cover"
              />
              <div v-else class="flex h-full w-full items-center justify-center bg-primary text-2xl font-bold text-white dark:bg-accent dark:text-on-accent">
                {{ authStore.userInitials }}
              </div>
            </div>
            <!-- Pencil overlay -->
            <div class="touch-reveal absolute inset-0 flex items-center justify-center rounded-full bg-black/40 opacity-0 transition group-hover:opacity-100 group-focus-visible:opacity-100">
              <svg class="h-6 w-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
            </div>
            <!-- Upload spinner -->
            <div v-if="isUploadingAvatar" class="absolute inset-0 flex items-center justify-center rounded-full bg-black/50">
              <div class="h-6 w-6 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            </div>
          </button>
          <input
            ref="fileInput"
            type="file"
            accept="image/*"
            class="hidden"
            @change="handleFileSelect"
          />
          <div class="text-center">
            <p class="text-base font-semibold text-text-default">{{ authStore.displayName }}</p>
            <p class="text-xs text-text-muted">{{ authStore.user?.email }}</p>
            <span
              class="mt-2 inline-block rounded-full px-3 py-1 text-[10px] font-semibold uppercase tracking-wider"
              :class="authStore.isAdmin
                ? 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400'
                : 'bg-primary-soft text-text-brand dark:bg-emerald-500/15'"
            >
              {{ authStore.isAdmin ? 'Administrador' : 'Cliente' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Profile form -->
      <form
        class="rounded-3xl border border-border-default bg-surface p-6 shadow-sm lg:col-span-2"
        @submit.prevent="handleUpdate"
      >
        <h2 class="mb-5 text-base font-semibold text-text-default">Informacion personal</h2>

        <div class="grid gap-4 sm:grid-cols-2">
          <div>
            <label for="profile-first-name" class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Nombre</label>
            <input
              id="profile-first-name"
              v-model="form.first_name"
              type="text"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default dark:bg-surface-muted dark:text-white dark:focus:border-lemon/40"
            />
          </div>
          <div>
            <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Apellido</label>
            <input
              v-model="form.last_name"
              type="text"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default dark:bg-surface-muted dark:text-white dark:focus:border-lemon/40"
            />
          </div>
          <div>
            <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Empresa</label>
            <input
              v-model="form.company_name"
              type="text"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default dark:bg-surface-muted dark:text-white dark:focus:border-lemon/40"
            />
          </div>
          <div>
            <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Telefono</label>
            <input
              v-model="form.phone"
              type="tel"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default dark:bg-surface-muted dark:text-white dark:focus:border-lemon/40"
            />
          </div>
          <div>
            <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Cedula</label>
            <input
              v-model="form.cedula"
              type="text"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default dark:bg-surface-muted dark:text-white dark:focus:border-lemon/40"
            />
          </div>
          <div>
            <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Fecha de nacimiento</label>
            <input
              v-model="form.date_of_birth"
              type="date"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default dark:bg-surface-muted dark:text-white dark:focus:border-lemon/40"
            />
          </div>
          <div>
            <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Sexo</label>
            <select
              v-model="form.gender"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition focus:border-border-default dark:bg-surface-muted dark:text-white dark:focus:border-lemon/40"
            >
              <option value="">Sin especificar</option>
              <option value="male">Masculino</option>
              <option value="female">Femenino</option>
              <option value="other">Otro</option>
              <option value="prefer_not_to_say">Prefiero no decir</option>
            </select>
          </div>
          <div>
            <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Nivel de educacion</label>
            <select
              v-model="form.education_level"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition focus:border-border-default dark:bg-surface-muted dark:text-white dark:focus:border-lemon/40"
            >
              <option value="">Sin especificar</option>
              <option value="primaria">Primaria</option>
              <option value="secundaria">Secundaria</option>
              <option value="tecnico">Tecnico</option>
              <option value="universitario">Universitario</option>
              <option value="posgrado">Posgrado</option>
              <option value="otro">Otro</option>
            </select>
          </div>
        </div>

        <div class="mt-6 flex justify-end">
          <BaseButton variant="accent" size="md" type="submit" :disabled="authStore.isLoading">
            {{ authStore.isLoading ? 'Guardando...' : 'Guardar cambios' }}
          </BaseButton>
        </div>
      </form>
    </div>

    <!-- Theme customization -->
    <div class="mt-6 rounded-3xl border border-border-default bg-surface p-6 shadow-sm">
      <h2 class="mb-5 text-base font-semibold text-text-default">Personalizar interfaz</h2>
      <ThemePicker />
    </div>

    <!-- Image crop modal -->
    <Teleport to="body">
      <Transition name="modal-overlay">
        <div
          v-if="showCropModal"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 backdrop-blur-sm"
          @click.self="cancelCrop"
        >
          <div class="w-full max-w-sm rounded-3xl border border-border-default bg-surface p-6 shadow-2xl">
            <h3 class="mb-4 text-base font-semibold text-text-default">Ajustar foto de perfil</h3>

            <div class="relative mx-auto mb-4 h-64 w-64 overflow-hidden rounded-full border-2 border-border-default bg-black">
              <img
                v-if="cropSrc"
                ref="cropImage"
                :src="cropSrc"
                alt="Recorte"
                class="absolute h-full w-full object-cover"
                :style="cropTransformStyle"
                draggable="false"
              />
            </div>

            <!-- Zoom slider -->
            <div class="mb-4 flex items-center gap-3 px-2">
              <svg class="h-4 w-4 shrink-0 text-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35M8 11h6" /></svg>
              <input
                v-model.number="cropZoom"
                type="range"
                min="1"
                max="3"
                step="0.05"
                class="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-esmerald/10 accent-esmerald dark:bg-white/10 dark:accent-lemon"
              />
              <svg class="h-4 w-4 shrink-0 text-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35M8 11h6M11 8v6" /></svg>
            </div>

            <div class="flex gap-3">
              <BaseButton variant="ghost" size="md" class="flex-1" @click="cancelCrop">
                Cancelar
              </BaseButton>
              <BaseButton variant="accent" size="md" class="flex-1" :disabled="isUploadingAvatar" @click="confirmCrop">
                {{ isUploadingAvatar ? 'Subiendo...' : 'Guardar' }}
              </BaseButton>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { usePageEntrance } from '~/composables/usePageEntrance'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import ThemePicker from '~/components/platform/ThemePicker.vue'

definePageMeta({
  layout: 'platform',
  middleware: ['platform-auth'],
})


usePageEntrance('#platform-profile')

const authStore = usePlatformAuthStore()
authStore.hydrate()

const localError = ref('')
const successMessage = ref('')
const fileInput = ref(null)
const isUploadingAvatar = ref(false)
const avatarPreview = ref('')

// Crop state
const showCropModal = ref(false)
const cropSrc = ref('')
const cropZoom = ref(1)
const selectedFile = ref(null)

const form = reactive({
  first_name: '',
  last_name: '',
  company_name: '',
  phone: '',
  cedula: '',
  date_of_birth: '',
  gender: '',
  education_level: '',
})

const errorMessage = computed(() => localError.value || authStore.error)

const avatarUrl = computed(() => authStore.user?.avatar_display_url || '')

const cropTransformStyle = computed(() => ({
  transform: `scale(${cropZoom.value})`,
  transformOrigin: 'center center',
}))

onMounted(() => {
  if (authStore.user) {
    form.first_name = authStore.user.first_name || ''
    form.last_name = authStore.user.last_name || ''
    form.company_name = authStore.user.company_name || ''
    form.phone = authStore.user.phone || ''
    form.cedula = authStore.user.cedula || ''
    form.date_of_birth = authStore.user.date_of_birth || ''
    form.gender = authStore.user.gender || ''
    form.education_level = authStore.user.education_level || ''
  }
})

function triggerFileInput() {
  fileInput.value?.click()
}

function handleFileSelect(event) {
  const file = event.target.files?.[0]
  if (!file) return

  if (!file.type.startsWith('image/')) {
    localError.value = 'Solo se permiten archivos de imagen.'
    return
  }

  if (file.size > 10 * 1024 * 1024) {
    localError.value = 'La imagen no puede superar 10 MB.'
    return
  }

  selectedFile.value = file
  cropSrc.value = URL.createObjectURL(file)
  cropZoom.value = 1
  showCropModal.value = true

  // Reset input so the same file can be re-selected
  event.target.value = ''
}

function cancelCrop() {
  showCropModal.value = false
  if (cropSrc.value) URL.revokeObjectURL(cropSrc.value)
  cropSrc.value = ''
  selectedFile.value = null
}

async function confirmCrop() {
  if (!selectedFile.value) return

  isUploadingAvatar.value = true
  localError.value = ''

  try {
    const optimized = await optimizeImageClient(selectedFile.value, cropZoom.value)
    const result = await authStore.uploadAvatar(optimized)

    if (result.success) {
      avatarPreview.value = ''
      successMessage.value = 'Foto de perfil actualizada.'
      setTimeout(() => { successMessage.value = '' }, 4000)
    } else {
      localError.value = result.message
    }
  } catch {
    localError.value = 'Error procesando la imagen.'
  } finally {
    isUploadingAvatar.value = false
    showCropModal.value = false
    if (cropSrc.value) URL.revokeObjectURL(cropSrc.value)
    cropSrc.value = ''
    selectedFile.value = null
  }
}

/**
 * Client-side image optimization:
 * - Draws the image on a canvas with the crop zoom
 * - Crops to a centered square (like WhatsApp)
 * - Resizes to max 512x512
 * - Exports as JPEG at 0.8 quality
 */
function optimizeImageClient(file, zoom = 1) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const size = Math.min(img.width, img.height) / zoom
      const sx = (img.width - size) / 2
      const sy = (img.height - size) / 2

      const outputSize = Math.min(512, Math.round(size))
      const canvas = document.createElement('canvas')
      canvas.width = outputSize
      canvas.height = outputSize

      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, sx, sy, size, size, 0, 0, outputSize, outputSize)

      canvas.toBlob(
        (blob) => {
          if (!blob) return reject(new Error('Failed to create blob'))
          const optimized = new File([blob], 'avatar.jpg', { type: 'image/jpeg' })
          resolve(optimized)
        },
        'image/jpeg',
        0.8,
      )
    }
    img.onerror = () => reject(new Error('Failed to load image'))
    img.src = URL.createObjectURL(file)
  })
}

async function handleUpdate() {
  localError.value = ''
  successMessage.value = ''

  const result = await authStore.updateProfile({
    first_name: form.first_name.trim(),
    last_name: form.last_name.trim(),
    company_name: form.company_name.trim(),
    phone: form.phone.trim(),
    cedula: form.cedula.trim(),
    date_of_birth: form.date_of_birth || null,
    gender: form.gender,
    education_level: form.education_level,
  })

  if (!result.success) {
    localError.value = result.message
    return
  }

  successMessage.value = 'Perfil actualizado correctamente.'
  setTimeout(() => { successMessage.value = '' }, 4000)
}
</script>

<style scoped>
.modal-overlay-enter-active,
.modal-overlay-leave-active {
  transition: opacity 0.25s ease;
}
.modal-overlay-enter-from,
.modal-overlay-leave-to {
  opacity: 0;
}
</style>
