<template>
  <div id="platform-complete-profile" class="flex min-h-screen items-center justify-center bg-surface-muted px-4 py-12">
    <div class="w-full max-w-lg">
      <!-- Logo -->
      <div class="mb-8 text-center">
        <div class="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-lg font-bold text-white">
          PA
        </div>
        <h1 class="text-2xl font-bold text-text-default">
          Completa tu perfil
        </h1>
        <p class="mt-2 text-sm text-text-muted">
          Necesitamos algunos datos antes de continuar.
        </p>
      </div>

      <!-- Form card -->
      <form
        class="rounded-3xl border border-border-default bg-surface p-6 shadow-sm sm:p-8"
        @submit.prevent="handleSubmit"
      >
        <!-- Error message -->
        <div
          v-if="errorMessage"
          class="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600"
        >
          {{ errorMessage }}
        </div>

        <!-- Avatar upload -->
        <div class="mb-6 flex flex-col items-center gap-3">
          <div
            class="relative flex h-20 w-20 cursor-pointer items-center justify-center overflow-hidden rounded-full border-2 border-dashed border-border-default bg-surface-muted transition hover:border-border-default"
            @click="triggerFileInput"
          >
            <img
              v-if="avatarPreview"
              :src="avatarPreview"
              alt="Avatar"
              class="h-full w-full object-cover"
            />
            <svg v-else class="h-8 w-8 text-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
          <input
            ref="fileInput"
            type="file"
            accept="image/*"
            class="hidden"
            @change="handleFileChange"
          />
          <BaseButton unstyled
            type="button"
            class="text-xs text-text-muted transition hover:text-text-default"
            @click="triggerFileInput"
          >
            {{ avatarPreview ? 'Cambiar foto' : 'Subir foto (opcional)' }}
          </BaseButton>
        </div>

        <!-- Name row -->
        <div class="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label for="profile-first-name" class="mb-1.5 block text-xs font-medium text-esmerald/70">Nombre</label>
            <input
              id="profile-first-name"
              v-model="form.first_name"
              type="text"
              placeholder="Tu nombre"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default"
            />
          </div>
          <div>
            <label for="profile-last-name" class="mb-1.5 block text-xs font-medium text-esmerald/70">Apellido</label>
            <input
              id="profile-last-name"
              v-model="form.last_name"
              type="text"
              placeholder="Tu apellido"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default"
            />
          </div>
        </div>

        <!-- Company -->
        <div class="mb-4">
          <label for="profile-company" class="mb-1.5 block text-xs font-medium text-esmerald/70">Empresa <span class="text-red-400">*</span></label>
          <input
            id="profile-company"
            v-model="form.company_name"
            type="text"
            required
            placeholder="Nombre de tu empresa"
            class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default"
          />
        </div>

        <!-- Phone + Cedula row -->
        <div class="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label for="profile-phone" class="mb-1.5 block text-xs font-medium text-esmerald/70">Teléfono <span class="text-red-400">*</span></label>
            <input
              id="profile-phone"
              v-model="form.phone"
              type="tel"
              required
              placeholder="+57 300 000 0000"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default"
            />
          </div>
          <div>
            <label for="profile-cedula" class="mb-1.5 block text-xs font-medium text-esmerald/70">Cédula <span class="text-red-400">*</span></label>
            <input
              id="profile-cedula"
              v-model="form.cedula"
              type="text"
              required
              placeholder="1020304050"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default"
            />
          </div>
        </div>

        <!-- Date of birth -->
        <div class="mb-4">
          <label for="profile-birth-date" class="mb-1.5 block text-xs font-medium text-esmerald/70">Fecha de nacimiento <span class="text-red-400">*</span></label>
          <input
            id="profile-birth-date"
            v-model="form.date_of_birth"
            type="date"
            required
            data-testid="date-of-birth"
            class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default"
          />
        </div>

        <!-- Gender + Education row -->
        <div class="mb-6 grid grid-cols-2 gap-3">
          <div>
            <label for="profile-gender" class="mb-1.5 block text-xs font-medium text-esmerald/70">Sexo <span class="text-red-400">*</span></label>
            <select
              id="profile-gender"
              v-model="form.gender"
              required
              data-testid="gender-select"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition focus:border-border-default"
            >
              <option value="" disabled>Selecciona</option>
              <option value="male">Masculino</option>
              <option value="female">Femenino</option>
              <option value="other">Otro</option>
              <option value="prefer_not_to_say">Prefiero no decir</option>
            </select>
          </div>
          <div>
            <label for="profile-education" class="mb-1.5 block text-xs font-medium text-esmerald/70">Nivel de educación <span class="text-red-400">*</span></label>
            <select
              id="profile-education"
              v-model="form.education_level"
              required
              data-testid="education-select"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition focus:border-border-default"
            >
              <option value="" disabled>Selecciona</option>
              <option value="primaria">Primaria</option>
              <option value="secundaria">Secundaria</option>
              <option value="tecnico">Técnico</option>
              <option value="universitario">Universitario</option>
              <option value="posgrado">Posgrado</option>
              <option value="otro">Otro</option>
            </select>
          </div>
        </div>

        <!-- Submit -->
        <BaseButton variant="accent" size="md" type="submit" class="w-full" :disabled="!canSubmit || authStore.isLoading">
          <svg
            v-if="authStore.isLoading"
            class="mr-2 h-4 w-4 animate-spin"
            viewBox="0 0 24 24"
            fill="none"
          >
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          {{ authStore.isLoading ? 'Guardando...' : 'Completar perfil' }}
        </BaseButton>
      </form>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { usePageEntrance } from '~/composables/usePageEntrance'
import { usePlatformAuthStore } from '~/stores/platform-auth'
definePageMeta({
  layout: false,
  middleware: ['platform-auth'],
})

useHead({
  title: 'Completar perfil — ProjectApp',
})

usePageEntrance('#platform-complete-profile')

const authStore = usePlatformAuthStore()
authStore.hydrate()

const fileInput = ref(null)
const avatarFile = ref(null)
const avatarPreview = ref('')
const localError = ref('')

const form = reactive({
  first_name: authStore.user?.first_name || '',
  last_name: authStore.user?.last_name || '',
  company_name: authStore.user?.company_name || '',
  phone: authStore.user?.phone || '',
  cedula: '',
  date_of_birth: '',
  gender: '',
  education_level: '',
})

const errorMessage = computed(() => localError.value || authStore.error)

const canSubmit = computed(() =>
  Boolean(form.company_name.trim())
  && Boolean(form.phone.trim())
  && Boolean(form.cedula.trim())
  && Boolean(form.date_of_birth)
  && Boolean(form.gender)
  && Boolean(form.education_level),
)

function triggerFileInput() {
  fileInput.value?.click()
}

function handleFileChange(event) {
  const file = event.target.files?.[0]
  if (!file) return

  if (!file.type.startsWith('image/')) {
    localError.value = 'Solo se permiten archivos de imagen.'
    return
  }

  if (file.size > 10 * 1024 * 1024) {
    localError.value = 'La imagen no puede pesar más de 10 MB.'
    return
  }

  avatarFile.value = file
  avatarPreview.value = URL.createObjectURL(file)
  localError.value = ''
}

async function handleSubmit() {
  localError.value = ''

  if (!canSubmit.value) {
    localError.value = 'Completa todos los campos obligatorios.'
    return
  }

  const formData = new FormData()
  formData.append('company_name', form.company_name.trim())
  formData.append('phone', form.phone.trim())
  formData.append('cedula', form.cedula.trim())
  formData.append('date_of_birth', form.date_of_birth)
  formData.append('gender', form.gender)
  formData.append('education_level', form.education_level)

  if (form.first_name.trim()) {
    formData.append('first_name', form.first_name.trim())
  }
  if (form.last_name.trim()) {
    formData.append('last_name', form.last_name.trim())
  }
  if (avatarFile.value) {
    formData.append('avatar', avatarFile.value)
  }

  const result = await authStore.completeProfile(formData)
  if (!result.success) {
    localError.value = result.message
    return
  }

  await navigateTo(useLocalePath()(authStore.isClient ? '/platform/documents' : '/platform/dashboard'))
}
</script>
