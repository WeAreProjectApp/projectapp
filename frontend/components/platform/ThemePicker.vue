<template>
  <div class="space-y-6">
    <!-- Color palette -->
    <div>
      <p class="mb-3 text-xs font-semibold uppercase tracking-widest text-text-muted">Color del tema</p>
      <div class="grid grid-cols-9 gap-2">
        <button
          v-for="(shade, idx) in allShades"
          :key="idx"
          type="button"
          class="h-8 w-8 rounded-lg border-2 transition hover:scale-110"
          :class="themeColor === shade ? 'border-input-border ring-2 ring-esmerald/30 dark:border-white dark:ring-white/30' : 'border-transparent'"
          :style="{ backgroundColor: shade }"
          :title="THEME_COLORS[Math.floor(idx / 9)]?.name"
          @click="handleColorSelect(shade)"
        />
      </div>
      <button
        v-if="themeColor"
        type="button"
        class="mt-2 text-[10px] text-text-muted transition hover:text-text-brand dark:hover:text-white"
        @click="handleClearColor"
      >
        Restablecer color
      </button>
    </div>

    <!-- Cover image -->
    <div>
      <div class="mb-3 flex items-center justify-between">
        <p class="text-xs font-semibold uppercase tracking-widest text-text-muted">Imagen de fondo</p>
        <div v-if="hasCover" class="flex items-center gap-3">
          <div class="h-8 w-14 overflow-hidden rounded-md border border-input-border dark:border-white/10">
            <img :src="currentCoverUrl" alt="Cover" class="h-full w-full object-cover" />
          </div>
          <BaseButton variant="danger-ghost" size="sm" @click="handleClearCover">
            Quitar
          </BaseButton>
        </div>
      </div>

      <!-- Upload custom -->
      <BaseButton variant="secondary" size="sm" class="mb-4 w-full" @click="coverInputRef?.click()">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <polyline points="21 15 16 10 5 21" />
        </svg>
        Subir imagen personalizada
      </BaseButton>
      <input ref="coverInputRef" type="file" accept="image/*" class="hidden" @change="handleCustomCoverUpload" />

      <!-- Gallery (auto-loads on mount, always visible) -->
      <div v-if="isLoadingGallery" class="py-8 text-center text-xs text-text-muted">Cargando galeria...</div>
      <div v-else-if="gallery.length" class="max-h-[50vh] space-y-5 overflow-y-auto pr-1">
        <div v-for="category in gallery" :key="category.name">
          <p class="sticky top-0 z-10 mb-2.5 bg-surface/90 py-1 text-[11px] font-semibold text-text-muted backdrop-blur dark:bg-surface/90">{{ category.name }}</p>
          <div class="grid grid-cols-3 gap-2 sm:grid-cols-4">
            <button
              v-for="img in category.images"
              :key="img.path"
              type="button"
              class="group relative aspect-[4/3] overflow-hidden rounded-xl border-2 transition hover:shadow-lg"
              :class="coverImage === img.path ? 'border-input-border ring-2 ring-esmerald/40 dark:border-lemon dark:ring-lemon/40' : 'border-transparent hover:border-input-border dark:hover:border-white/20'"
              @click="handleCoverSelect(img.path)"
            >
              <img :src="img.url" :alt="img.name" loading="lazy" class="h-full w-full object-cover transition group-hover:scale-105" />
              <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 to-transparent px-2 py-1.5">
                <p class="truncate text-[10px] leading-tight text-white">{{ img.name }}</p>
              </div>
            </button>
          </div>
        </div>
      </div>
      <p v-else-if="!isLoadingGallery" class="py-4 text-center text-xs text-text-muted">No se encontraron imagenes en la galeria.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { usePlatformCustomTheme } from '~/composables/usePlatformCustomTheme'
import { usePlatformApi } from '~/composables/usePlatformApi'

const {
  THEME_COLORS,
  themeColor,
  coverImage,
  customCoverImageUrl,
  hasCover,
  setThemeColor,
  setCoverImage,
  setCustomCoverImage,
  clearCover,
} = usePlatformCustomTheme()

const coverInputRef = ref(null)
const gallery = ref([])
const isLoadingGallery = ref(false)
let galleryLoaded = false

const allShades = computed(() => THEME_COLORS.flatMap((c) => c.shades))

const currentCoverUrl = computed(() => {
  if (customCoverImageUrl.value) return customCoverImageUrl.value
  if (coverImage.value) return encodeURI(`/static/cover_gallery/${coverImage.value}`)
  return ''
})

onMounted(() => {
  if (!galleryLoaded) loadGallery()
})

async function handleColorSelect(shade) {
  await setThemeColor(shade)
}

async function handleClearColor() {
  await setThemeColor('')
}

async function handleCoverSelect(path) {
  await setCoverImage(path)
}

async function handleClearCover() {
  await clearCover()
}

async function handleCustomCoverUpload(event) {
  const file = event.target.files?.[0]
  if (!file) return
  await setCustomCoverImage(file)
  event.target.value = ''
}

async function loadGallery() {
  isLoadingGallery.value = true
  try {
    const { get } = usePlatformApi()
    const response = await get('cover-gallery/')
    gallery.value = response.data || []
    galleryLoaded = true
  } catch {
    gallery.value = []
  } finally {
    isLoadingGallery.value = false
  }
}
</script>
