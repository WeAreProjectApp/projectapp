<template>
  <div>
    <!-- Header row -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-4">
        <BaseActionButton
          as="NuxtLink"
          :to="localePath('/panel/blog')"
          action="back"
          label="Volver al blog"
          class="text-text-subtle hover:text-text-default"
        />
        <h1 class="text-2xl font-light text-text-default">Editar Blog Post</h1>
      </div>
      <BaseButton
        v-if="loaded"
        type="button"
        class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-colors"
        :class="showPreview
          ? 'bg-primary text-on-primary hover:bg-primary-strong'
          : 'border border-border-default text-text-default hover:bg-surface-raised'"
        @click="togglePreview"
      >
        <BaseActionIcon :action="showPreview ? 'close' : 'view'" />
        {{ showPreview ? 'Cerrar preview' : 'Vista previa' }}
      </BaseButton>
    </div>

    <!-- Loading -->
    <div v-if="blogStore.isLoading" class="flex justify-center py-12">
      <div class="w-6 h-6 border-2 border-focus-ring/30 border-t-focus-ring rounded-full animate-spin" />
    </div>

    <!-- Main layout: form + optional preview -->
    <div v-else-if="loaded" class="flex gap-6" :class="showPreview ? 'lg:flex-row flex-col' : ''">
      <!-- Form column -->
      <form
        class="space-y-6 flex-1 min-w-0"
        :class="showPreview ? '' : 'max-w-3xl'"
        @submit.prevent="handleSubmit"
      >
        <UnsavedChangesNotice
          v-if="hasChanges"
          :title="unsavedTitle"
          :detail="unsavedDetail"
          :can-save="canSaveNow"
          :saving="blogStore.isUpdating"
          testid="blog-unsaved-notice"
          @save="handleSubmit"
          @discard="discardChanges"
        />

        <!-- Slug -->
        <div>
          <label for="slug" class="block text-sm font-medium text-text-default mb-1">Slug</label>
          <input id="slug" v-model="form.slug" type="text" class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" />
          <p class="text-xs text-text-subtle mt-1">URL: /blog/{{ form.slug || '...' }}</p>
        </div>

        <!-- Metadata row -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label for="edit-category" class="block text-sm font-medium text-text-default mb-1">Categoría</label>
            <select id="edit-category" v-model="form.category" class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all">
              <option value="">Sin categoría</option>
              <option v-for="cat in blogStore.availableCategories" :key="cat.slug" :value="cat.slug">{{ cat.label }}</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Autor</label>
            <select v-model="form.author" class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all">
              <option value="projectapp-team">Project App Team</option>
              <option value="gustavo-perez">Gustavo Pérez — CEO</option>
              <option value="carlos-blanco">Carlos Blanco — CFO</option>
            </select>
          </div>
          <div>
            <label for="edit-read-time" class="block text-sm font-medium text-text-default mb-1">Tiempo lectura (min)</label>
            <input id="edit-read-time" v-model.number="form.read_time_minutes" type="number" min="0" class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" />
          </div>
          <div class="flex items-end">
            <label class="inline-flex items-center cursor-pointer select-none gap-3">
              <BaseToggle v-model="form.is_featured" size="sm" />
              <span class="text-sm text-text-default">Destacado</span>
            </label>
          </div>
        </div>

        <!-- Español Section -->
        <fieldset class="w-full min-w-0 max-w-full border border-border-default rounded-xl p-5 space-y-4">
          <legend class="text-sm font-medium text-text-default px-2">Español</legend>
          <div>
            <label for="title_es" class="block text-sm font-medium text-text-default mb-1">Título (ES)</label>
            <input id="title_es" v-model="form.title_es" type="text" required class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" />
          </div>
          <div>
            <label for="excerpt_es" class="block text-sm font-medium text-text-default mb-1">Resumen (ES)</label>
            <textarea id="excerpt_es" v-model="form.excerpt_es" rows="2" required class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all resize-y" />
          </div>
          <div>
            <label for="content_es" class="block text-sm font-medium text-text-default mb-1">Contenido HTML (ES)</label>
            <textarea id="content_es" v-model="form.content_es" rows="6" class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm font-mono focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all resize-y" />
          </div>
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Contenido JSON (ES)</label>
            <textarea v-model="form.content_json_es_raw" rows="10" class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-xs font-mono focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all resize-y" placeholder='{ "intro": "...", "sections": [...], "conclusion": "...", "cta": "..." }' />
            <p class="text-xs text-text-subtle mt-1">JSON estructurado con intro, sections, conclusion y cta. Tiene prioridad sobre el HTML.</p>
          </div>
        </fieldset>

        <!-- English Section -->
        <fieldset class="w-full min-w-0 max-w-full border border-border-default rounded-xl p-5 space-y-4">
          <legend class="text-sm font-medium text-text-default px-2">English</legend>
          <div>
            <label for="title_en" class="block text-sm font-medium text-text-default mb-1">Title (EN)</label>
            <input id="title_en" v-model="form.title_en" type="text" required class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" />
          </div>
          <div>
            <label for="excerpt_en" class="block text-sm font-medium text-text-default mb-1">Excerpt (EN)</label>
            <textarea id="excerpt_en" v-model="form.excerpt_en" rows="2" required class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all resize-y" />
          </div>
          <div>
            <label for="content_en" class="block text-sm font-medium text-text-default mb-1">Content HTML (EN)</label>
            <textarea id="content_en" v-model="form.content_en" rows="6" class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm font-mono focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all resize-y" />
          </div>
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Content JSON (EN)</label>
            <textarea v-model="form.content_json_en_raw" rows="10" class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-xs font-mono focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all resize-y" placeholder='{ "intro": "...", "sections": [...], "conclusion": "...", "cta": "..." }' />
          </div>
        </fieldset>

        <!-- SEO Section -->
        <fieldset class="w-full min-w-0 max-w-full border border-border-default rounded-xl p-5 space-y-6">
          <legend class="text-sm font-medium text-text-default px-2">SEO</legend>
          <div class="space-y-4">
            <div>
              <label for="edit-meta-title-es" class="block text-sm font-medium text-text-default mb-1">Meta título (ES)</label>
              <input id="edit-meta-title-es" v-model="form.meta_title_es" type="text" class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" placeholder="Título SEO en español (60 caracteres recomendado)" />
            </div>
            <div>
              <label class="block text-sm font-medium text-text-default mb-1">Meta title (EN)</label>
              <input v-model="form.meta_title_en" type="text" class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" placeholder="SEO title in English (60 characters recommended)" />
            </div>
          </div>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-text-default mb-1">Meta descripción (ES)</label>
              <textarea v-model="form.meta_description_es" rows="3" class="w-full px-4 py-3 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm leading-relaxed focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all resize-y" placeholder="Descripción SEO en español (150-160 caracteres recomendado)" />
            </div>
            <div>
              <label class="block text-sm font-medium text-text-default mb-1">Meta description (EN)</label>
              <textarea v-model="form.meta_description_en" rows="3" class="w-full px-4 py-3 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm leading-relaxed focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all resize-y" placeholder="SEO description in English (150-160 characters recommended)" />
            </div>
          </div>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-text-default mb-1">Keywords (ES)</label>
              <input v-model="form.meta_keywords_es" type="text" class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" placeholder="cortinas inteligentes, automatización hogar, domotica" />
              <p class="text-xs text-text-subtle mt-1">Separadas por coma. Palabras clave objetivo para SEO.</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-text-default mb-1">Keywords (EN)</label>
              <input v-model="form.meta_keywords_en" type="text" class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" placeholder="smart blinds, home automation, domotics" />
            </div>
          </div>
        </fieldset>

        <!-- LinkedIn Summary -->
        <fieldset class="w-full min-w-0 max-w-full border border-border-default rounded-xl p-5 space-y-4">
          <legend class="text-sm font-medium text-text-default px-2">LinkedIn</legend>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-text-default mb-1">Resumen LinkedIn (ES)</label>
              <textarea v-model="form.linkedin_summary_es" rows="4" maxlength="1300" class="w-full px-4 py-3 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm leading-relaxed focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all resize-y" placeholder="Resumen para publicar en LinkedIn (max ~1300 caracteres)" />
              <p class="text-xs text-text-subtle mt-1">{{ form.linkedin_summary_es.length }} / 1300</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-text-default mb-1">LinkedIn Summary (EN)</label>
              <textarea v-model="form.linkedin_summary_en" rows="4" maxlength="1300" class="w-full px-4 py-3 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm leading-relaxed focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all resize-y" placeholder="Summary for LinkedIn post (max ~1300 chars)" />
              <p class="text-xs text-text-subtle mt-1">{{ form.linkedin_summary_en.length }} / 1300</p>
            </div>
          </div>

          <!-- LinkedIn publish action -->
          <div class="border-t border-border-muted pt-4 mt-2">
            <div v-if="!linkedinStatus.connected" class="flex items-center gap-3">
              <span class="text-sm text-text-muted">LinkedIn no conectado.</span>
              <BaseButton variant="ghost" size="md" @click="connectLinkedIn">
            <BaseActionIcon action="link" />
                Conectar LinkedIn
              </BaseButton>
            </div>
            <div v-else class="space-y-3">
              <div class="flex items-center gap-2 text-sm text-text-muted/60">
                <span class="w-2 h-2 rounded-full bg-primary" />
                Conectado como <strong>{{ linkedinStatus.profile_name }}</strong>
              </div>
              <div class="flex min-w-0 flex-col items-stretch gap-3 panel-portrait:flex-row panel-portrait:items-center">
                <select v-model="linkedinLang" class="w-full min-w-0 px-3 py-2 rounded-lg border border-input-border bg-input-bg text-input-text text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring panel-portrait:w-auto">
                  <option value="en">Publish in English</option>
                  <option value="es">Publicar en Español</option>
                </select>
                <BaseControlGate
                  :reasons="!selectedLinkedInSummary ? ['Escribe el resumen de LinkedIn en el idioma elegido.'] : []"
                  label="Publicar en LinkedIn no disponible"
                  align="stretch"
                  class="w-full min-w-0 panel-portrait:w-auto"
                >
                  <template #default="{ describedBy }">
                    <BaseButton
                      variant="ghost"
                      size="md"
                      :loading="isPublishingLinkedIn"
                      :disabled="!selectedLinkedInSummary"
                      disabled-reason="Escribe el resumen de LinkedIn en el idioma elegido."
                      :aria-describedby="describedBy"
                      class="w-full panel-portrait:w-auto"
                      @click="publishToLinkedIn"
                    >
              <BaseActionIcon action="publish" />
                      {{ isPublishingLinkedIn ? 'Publicando...' : 'Publicar en LinkedIn' }}
                    </BaseButton>
                  </template>
                </BaseControlGate>
              </div>
              <p v-if="post?.linkedin_published_at" class="text-xs text-text-subtle">
                Última publicación: {{ new Date(post.linkedin_published_at).toLocaleString() }}
              </p>
              <p v-if="linkedinMsg" class="text-sm text-text-brand">{{ linkedinMsg }}</p>
              <p v-if="linkedinError" class="text-sm text-danger-strong">{{ linkedinError }}</p>
            </div>
          </div>
        </fieldset>

        <!-- Cover image -->
        <fieldset class="w-full min-w-0 max-w-full border border-border-default rounded-xl p-5 space-y-4">
          <legend class="text-sm font-medium text-text-default px-2">Imagen de portada</legend>

          <!-- File upload -->
          <div>
            <label class="block text-sm font-medium text-text-default mb-2">Subir archivo</label>
            <div class="flex items-center gap-3">
              <label class="inline-flex items-center gap-2 px-4 py-2.5 border border-border-default rounded-xl text-sm text-text-default hover:bg-surface-raised cursor-pointer transition-colors">
            <BaseActionIcon action="upload" />
                Seleccionar imagen
                <input type="file" accept="image/*" class="hidden" @change="handleCoverUpload" />
              </label>
              <span v-if="uploadFileName" class="text-xs text-text-muted">{{ uploadFileName }}</span>
              <span v-if="isUploading" class="text-xs text-text-brand">Subiendo...</span>
            </div>
          </div>

          <!-- OR divider -->
          <div class="flex items-center gap-3">
            <div class="flex-1 border-t border-border-default" />
            <span class="text-xs text-text-subtle">o pegar URL externa</span>
            <div class="flex-1 border-t border-border-default" />
          </div>

          <!-- URL input -->
          <div>
            <label for="cover_image_url" class="block text-sm font-medium text-text-default mb-1">URL de imagen</label>
            <input id="cover_image_url" v-model="form.cover_image_url" type="url" class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" placeholder="https://example.com/image.jpg" />
          </div>

          <!-- Preview -->
          <div v-if="coverImagePreview" class="mt-2 rounded-xl overflow-hidden border border-border-default max-w-md">
            <img :src="coverImagePreview" alt="Preview" class="w-full h-auto" @error="imgError = true" />
            <p v-if="imgError" class="text-xs text-danger-strong p-2">No se pudo cargar la imagen.</p>
          </div>

          <!-- Credit -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-text-default mb-1">Crédito de imagen</label>
              <input v-model="form.cover_image_credit" type="text" class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" placeholder="Foto de John Doe en Unsplash" />
            </div>
            <div>
              <label class="block text-sm font-medium text-text-default mb-1">URL del crédito</label>
              <input v-model="form.cover_image_credit_url" type="url" class="w-full px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" placeholder="https://unsplash.com/@johndoe" />
            </div>
          </div>
        </fieldset>

        <!-- Sources -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <label class="block text-sm font-medium text-text-default">Fuentes</label>
            <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand hover:text-text-brand transition-colors" @click="addSource">
              <BaseActionIcon action="create" />
              Agregar fuente
            </button>
          </div>
          <div v-for="(source, idx) in form.sources" :key="idx" class="flex gap-2 mb-2">
            <input v-model="source.name" type="text" class="flex-1 px-3 py-2 rounded-lg border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" placeholder="Nombre de la fuente" />
            <input v-model="source.url" type="url" class="flex-[2] px-3 py-2 rounded-lg border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" placeholder="https://..." />
            <BaseActionButton action="remove" variant="danger-ghost" label="Quitar fuente" @click="removeSource(idx)" />
          </div>
          <p v-if="form.sources.length === 0" class="text-xs text-text-subtle">No hay fuentes agregadas.</p>
        </div>

        <!-- Publishing options -->
        <fieldset class="w-full min-w-0 max-w-full border border-border-default rounded-xl p-5 space-y-4">
          <legend class="text-sm font-medium text-text-default px-2">Publicación</legend>
          <div class="flex flex-col gap-3">
            <label class="flex items-center gap-3 cursor-pointer">
              <input v-model="publishMode" type="radio" value="draft" name="publishMode" class="w-4 h-4 text-text-brand focus:ring-focus-ring/30" />
              <span class="text-sm text-text-default">Borrador</span>
            </label>
            <label class="flex items-center gap-3 cursor-pointer">
              <input v-model="publishMode" type="radio" value="now" name="publishMode" class="w-4 h-4 text-text-brand focus:ring-focus-ring/30" />
              <span class="text-sm text-text-default">Publicar ahora</span>
            </label>
            <label class="flex items-center gap-3 cursor-pointer">
              <input v-model="publishMode" type="radio" value="schedule" name="publishMode" class="w-4 h-4 text-text-brand focus:ring-focus-ring/30" />
              <span class="text-sm text-text-default">Programar publicación</span>
            </label>
            <div v-if="publishMode === 'schedule'" class="ml-7">
              <input v-model="scheduledDate" type="datetime-local" class="px-4 py-2.5 rounded-xl border border-input-border bg-input-bg text-input-text placeholder-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" />
              <p class="text-xs text-text-subtle mt-1">El post se publicará automáticamente en la fecha seleccionada.</p>
              <p v-if="scheduledOverdue" class="text-xs text-warning-strong mt-2" data-test="scheduled-overdue-banner">
                Programado para una fecha que ya pasó. El sistema lo publicará en el próximo minuto. Si pasa más de 2 minutos, refresca esta página o pulsa "Publicar ahora".
              </p>
            </div>
          </div>
        </fieldset>

        <!-- Error / Success -->
        <p v-if="errorMsg" class="text-sm text-danger-strong">{{ errorMsg }}</p>
        <p v-if="successMsg" class="text-sm text-text-brand">{{ successMsg }}</p>

        <!-- Actions -->
        <div class="flex gap-3 pt-4">
          <BaseButton variant="primary" size="md" type="submit" :disabled="blogStore.isUpdating">
            {{ blogStore.isUpdating ? 'Guardando...' : 'Guardar Cambios' }}
          </BaseButton>
          <a v-if="post?.slug" :href="`/blog/${post.slug}`" target="_blank" rel="noopener noreferrer" class="px-6 py-2.5 border border-border-default text-text-muted rounded-xl text-sm hover:bg-surface-raised transition-colors inline-flex items-center gap-1">
            Ver en blog
          <BaseActionIcon action="open-external" />
          </a>
        </div>
      </form>

      <!-- Preview panel: desktop (inline) -->
      <aside
        v-if="showPreview"
        class="sticky top-20 hidden max-h-[calc(100vh-6rem)] w-[45%] flex-shrink-0 self-start overflow-y-auto rounded-xl border border-border-default bg-surface shadow-sm panel-landscape:block"
      >
        <div class="p-4 border-b border-border-muted flex items-center justify-between">
          <span class="text-sm font-medium text-text-default">Vista previa</span>
          <div class="flex items-center gap-1 bg-surface-raised rounded-lg p-0.5">
            <button
              type="button"
              :class="['px-3 py-1 text-xs rounded-md transition-colors', previewLang === 'es' ? 'bg-surface shadow-sm font-medium text-text-default' : 'text-text-muted']"
              @click="previewLang = 'es'"
            >ES</button>
            <button
              type="button"
              :class="['px-3 py-1 text-xs rounded-md transition-colors', previewLang === 'en' ? 'bg-surface shadow-sm font-medium text-text-default' : 'text-text-muted']"
              @click="previewLang = 'en'"
            >EN</button>
          </div>
        </div>
        <div class="p-6">
          <div v-if="previewCategory" class="mb-4">
            <span class="px-3 py-1.5 rounded-full text-xs bg-primary-soft text-text-brand font-medium capitalize">{{ previewCategory }}</span>
          </div>
          <h1 class="text-2xl font-light text-text-default mb-3 leading-tight">{{ previewTitle }}</h1>
          <p class="text-sm text-text-muted mb-4 leading-relaxed">{{ previewExcerpt }}</p>
          <div v-if="coverImagePreview" class="mb-6 rounded-xl overflow-hidden border border-border-default">
            <img :src="coverImagePreview" alt="Cover" class="w-full h-auto" />
          </div>
          <div v-if="form.read_time_minutes" class="text-xs text-text-subtle mb-6">{{ form.read_time_minutes }} min de lectura</div>
          <BlogContentRenderer :content-json="previewContentJson" :html-content="previewHtmlContent" />
        </div>
      </aside>
    </div>

    <!-- Preview drawer: mobile/tablet -->
    <Teleport to="body">
      <Transition name="drawer">
        <div v-if="showPreview && isMobilePreview" class="fixed inset-0 z-50 flex justify-end" @click.self="showPreview = false">
          <div class="absolute inset-0 bg-black/30" @click="showPreview = false" />
          <div class="relative w-[90vw] max-w-lg h-full bg-surface shadow-2xl overflow-y-auto">
            <div class="sticky top-0 bg-surface z-10 p-4 border-b border-border-muted flex items-center justify-between">
              <span class="text-sm font-medium text-text-default">Vista previa</span>
              <div class="flex items-center gap-3">
                <div class="flex items-center gap-1 bg-surface-raised rounded-lg p-0.5">
                  <button
                    type="button"
                    :class="['px-3 py-1 text-xs rounded-md transition-colors', previewLang === 'es' ? 'bg-surface shadow-sm font-medium text-text-default' : 'text-text-muted']"
                    @click="previewLang = 'es'"
                  >ES</button>
                  <button
                    type="button"
                    :class="['px-3 py-1 text-xs rounded-md transition-colors', previewLang === 'en' ? 'bg-surface shadow-sm font-medium text-text-default' : 'text-text-muted']"
                    @click="previewLang = 'en'"
                  >EN</button>
                </div>
          <BaseActionButton action="close" label="Cerrar vista previa" @click="showPreview = false" />
              </div>
            </div>
            <div class="p-6">
              <div v-if="previewCategory" class="mb-4">
                <span class="px-3 py-1.5 rounded-full text-xs bg-primary-soft text-text-brand font-medium capitalize">{{ previewCategory }}</span>
              </div>
              <h1 class="text-2xl font-light text-text-default mb-3 leading-tight">{{ previewTitle }}</h1>
              <p class="text-sm text-text-muted mb-4 leading-relaxed">{{ previewExcerpt }}</p>
              <div v-if="coverImagePreview" class="mb-6 rounded-xl overflow-hidden border border-border-default">
                <img :src="coverImagePreview" alt="Cover" class="w-full h-auto" />
              </div>
              <div v-if="form.read_time_minutes" class="text-xs text-text-subtle mb-6">{{ form.read_time_minutes }} min de lectura</div>
              <BlogContentRenderer :content-json="previewContentJson" :html-content="previewHtmlContent" />
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <ConfirmModal
      v-model="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :variant="confirmState.variant"
      :require-type-text="confirmState.requireTypeText"
      :hide-cancel="confirmState.hideCancel"
      :secondary-text="confirmState.secondaryText"
      :secondary-variant="confirmState.secondaryVariant"
      :secondary-hint="confirmState.secondaryHint"
      :loading="confirmState.busy"
      @confirm="handleConfirmed"
      @secondary="handleSecondaryAction"
      @cancel="handleCancelled"
    />
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useBlogStore } from '~/stores/blog';
import { useLinkedInStore } from '~/stores/linkedin';

const localePath = useLocalePath();
import BlogContentRenderer from '~/components/blog/BlogContentRenderer.vue';
import { resolveBlogPublishMode } from '~/utils/blogPublishMode.js';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { useUnsavedGuard } from '~/composables/useUnsavedGuard';
import { useIsMobile } from '~/composables/useIsMobile';
import UnsavedChangesNotice from '~/components/panel/UnsavedChangesNotice.vue';

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const route = useRoute();
const blogStore = useBlogStore();
const linkedInStore = useLinkedInStore();
const post = computed(() => blogStore.currentPost);
const loaded = ref(false);
const errorMsg = ref('');
const successMsg = ref('');
const imgError = ref(false);
const uploadFileName = ref('');
const isUploading = ref(false);

const showPreview = ref(false);
const previewLang = ref('es');
const { isMobile: isMobilePreview } = useIsMobile();

const publishMode = ref('draft');
const scheduledDate = ref('');
const scheduledOverdue = ref(false);

function togglePreview() { showPreview.value = !showPreview.value; }

const form = reactive({
  title_es: '',
  title_en: '',
  slug: '',
  excerpt_es: '',
  excerpt_en: '',
  content_es: '',
  content_en: '',
  content_json_es_raw: '',
  content_json_en_raw: '',
  cover_image: '',
  cover_image_url: '',
  sources: [],
  category: '',
  author: 'projectapp-team',
  read_time_minutes: 0,
  is_featured: false,
  is_published: false,
  meta_title_es: '',
  meta_title_en: '',
  meta_description_es: '',
  meta_description_en: '',
  meta_keywords_es: '',
  meta_keywords_en: '',
  cover_image_credit: '',
  cover_image_credit_url: '',
  linkedin_summary_es: '',
  linkedin_summary_en: '',
});

/**
 * `cover_image` queda FUERA del seguimiento a propósito: handleCoverUpload lo
 * escribe con lo que el servidor YA guardó, así que contarlo dejaría un
 * "imagen de portada sin guardar" permanente después de cada subida. Lo que el
 * operador edita a mano es `cover_image_url`, y ese sí se sigue.
 *
 * publishMode y scheduledDate viven fuera de `form` pero son trabajo pendiente
 * igual, así que el snapshot los suma.
 */
const {
  hasChanges,
  unsavedTitle,
  unsavedDetail,
  canSaveNow,
  commit: commitBaseline,
  guardedReload,
  discardChanges,
  confirmState,
  handleConfirmed,
  handleSecondaryAction,
  handleCancelled,
} = useUnsavedGuard({
  snapshot: () => {
    const { cover_image: _serverOwned, ...tracked } = form;
    return { ...tracked, publishMode: publishMode.value, scheduledDate: scheduledDate.value };
  },
  labels: {
    title_es: 'título (ES)',
    title_en: 'título (EN)',
    slug: 'slug',
    excerpt_es: 'resumen (ES)',
    excerpt_en: 'resumen (EN)',
    content_es: 'contenido (ES)',
    content_en: 'contenido (EN)',
    content_json_es_raw: 'contenido JSON (ES)',
    content_json_en_raw: 'contenido JSON (EN)',
    cover_image_url: 'URL de portada',
    sources: 'fuentes',
    category: 'categoría',
    author: 'autor',
    read_time_minutes: 'tiempo de lectura',
    is_featured: 'destacado',
    is_published: 'publicación',
    meta_title_es: 'meta título (ES)',
    meta_title_en: 'meta título (EN)',
    meta_description_es: 'meta descripción (ES)',
    meta_description_en: 'meta descripción (EN)',
    meta_keywords_es: 'meta keywords (ES)',
    meta_keywords_en: 'meta keywords (EN)',
    cover_image_credit: 'crédito de portada',
    cover_image_credit_url: 'URL del crédito',
    linkedin_summary_es: 'resumen LinkedIn (ES)',
    linkedin_summary_en: 'resumen LinkedIn (EN)',
    publishMode: 'publicación',
    scheduledDate: 'fecha programada',
  },
  save: handleSubmit,
  reload: reloadPost,
});

// LinkedIn state
const linkedinStatus = ref({ connected: false });
// English default: LinkedIn content targets the US market.
const linkedinLang = ref('en');
const selectedLinkedInSummary = computed(() => (
  linkedinLang.value === 'es' ? form.linkedin_summary_es : form.linkedin_summary_en
));
const linkedinMsg = ref('');
const linkedinError = ref('');
const isPublishingLinkedIn = ref(false);

async function reloadPost() {
  const [result, liStatus] = await Promise.all([
    blogStore.fetchAdminPost(route.params.id),
    linkedInStore.fetchLinkedInStatus(),
  ]);
  if (result.success && result.data) {
    populateForm(result.data);
  }
  if (liStatus.success) {
    linkedinStatus.value = liStatus.data;
  }
}

// El refresh repuebla el formulario por encima: que pregunte antes.
usePanelRefresh(guardedReload);

onMounted(async () => {
  window.addEventListener('message', handleLinkedInMessage);
  blogStore.fetchCategories();

  await reloadPost();
  loaded.value = true;
});

function handleLinkedInMessage(event) {
  // Only trust messages from our own origin (the /auth/linkedin/callback popup)
  if (event.origin !== window.location.origin) return;
  if (event.data?.type === 'linkedin-connected') {
    linkedinStatus.value = event.data.data || { connected: true };
    linkedinMsg.value = 'LinkedIn conectado correctamente.';
    setTimeout(() => { linkedinMsg.value = ''; }, 5000);
  }
}

onUnmounted(() => {
  window.removeEventListener('message', handleLinkedInMessage);
});

function jsonToStr(val) {
  if (!val || (typeof val === 'object' && Object.keys(val).length === 0)) return '';
  return JSON.stringify(val, null, 2);
}

function strToJson(str) {
  if (!str || !str.trim()) return {};
  try { return JSON.parse(str); }
  catch { return {}; }
}

function populateForm(data) {
  form.title_es = data.title_es || '';
  form.title_en = data.title_en || '';
  form.slug = data.slug || '';
  form.excerpt_es = data.excerpt_es || '';
  form.excerpt_en = data.excerpt_en || '';
  form.content_es = data.content_es || '';
  form.content_en = data.content_en || '';
  form.content_json_es_raw = jsonToStr(data.content_json_es);
  form.content_json_en_raw = jsonToStr(data.content_json_en);
  form.cover_image = data.cover_image_display || data.cover_image || '';
  form.cover_image_url = data.cover_image_url || '';
  form.sources = Array.isArray(data.sources)
    ? data.sources.map(s => ({ ...s }))
    : [];
  form.category = data.category || '';
  form.read_time_minutes = data.read_time_minutes || 0;
  form.is_featured = data.is_featured || false;
  form.is_published = data.is_published || false;
  form.author = data.author || 'projectapp-team';
  form.meta_title_es = data.meta_title_es || '';
  form.meta_title_en = data.meta_title_en || '';
  form.meta_description_es = data.meta_description_es || '';
  form.meta_description_en = data.meta_description_en || '';
  form.meta_keywords_es = data.meta_keywords_es || '';
  form.meta_keywords_en = data.meta_keywords_en || '';
  form.cover_image_credit = data.cover_image_credit || '';
  form.cover_image_credit_url = data.cover_image_credit_url || '';
  form.linkedin_summary_es = data.linkedin_summary_es || '';
  form.linkedin_summary_en = data.linkedin_summary_en || '';

  const resolved = resolveBlogPublishMode(data);
  publishMode.value = resolved.mode;
  scheduledDate.value = resolved.scheduledIso || '';
  scheduledOverdue.value = resolved.overdue;

  // Único punto de hidratación: cubre la carga inicial, el refresh y el
  // repoblado posterior a guardar.
  commitBaseline();
}

const previewTitle = computed(() => previewLang.value === 'en' ? form.title_en : form.title_es);
const previewExcerpt = computed(() => previewLang.value === 'en' ? form.excerpt_en : form.excerpt_es);
const previewCategory = computed(() => form.category);
const previewContentJson = computed(() => {
  const raw = previewLang.value === 'en' ? form.content_json_en_raw : form.content_json_es_raw;
  return strToJson(raw);
});
const previewHtmlContent = computed(() => previewLang.value === 'en' ? form.content_en : form.content_es);

const coverImagePreview = computed(() => form.cover_image || form.cover_image_url || '');

watch(() => form.cover_image_url, () => {
  imgError.value = false;
});

async function handleCoverUpload(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  uploadFileName.value = file.name;
  isUploading.value = true;
  const result = await blogStore.uploadCoverImage(route.params.id, file);
  isUploading.value = false;
  if (result.success) {
    form.cover_image = result.data.cover_image_display || '';
    successMsg.value = 'Imagen subida correctamente.';
    setTimeout(() => { successMsg.value = ''; }, 3000);
  } else {
    errorMsg.value = 'Error al subir la imagen.';
  }
}

function addSource() {
  form.sources.push({ name: '', url: '' });
}

function removeSource(idx) {
  form.sources.splice(idx, 1);
}

async function connectLinkedIn() {
  const result = await linkedInStore.fetchLinkedInAuthUrl();
  if (result.success && result.data?.authorization_url) {
    window.open(result.data.authorization_url, '_blank', 'width=600,height=700');
  }
}

async function publishToLinkedIn() {
  linkedinMsg.value = '';
  linkedinError.value = '';
  isPublishingLinkedIn.value = true;

  const result = await blogStore.publishToLinkedIn(route.params.id, linkedinLang.value);
  isPublishingLinkedIn.value = false;

  if (result.success) {
    linkedinMsg.value = result.data?.message || 'Publicado en LinkedIn correctamente.';
    setTimeout(() => { linkedinMsg.value = ''; }, 5000);
  } else {
    linkedinError.value = result.error || 'Error al publicar en LinkedIn.';
  }
}

async function handleSubmit() {
  errorMsg.value = '';
  successMsg.value = '';

  const payload = {
    title_es: form.title_es,
    title_en: form.title_en,
    slug: form.slug,
    excerpt_es: form.excerpt_es,
    excerpt_en: form.excerpt_en,
    content_es: form.content_es,
    content_en: form.content_en,
    content_json_es: strToJson(form.content_json_es_raw),
    content_json_en: strToJson(form.content_json_en_raw),
    sources: form.sources.filter(s => s.name && s.url),
    category: form.category,
    read_time_minutes: form.read_time_minutes,
    is_featured: form.is_featured,
    author: form.author,
    meta_title_es: form.meta_title_es,
    meta_title_en: form.meta_title_en,
    meta_description_es: form.meta_description_es,
    meta_description_en: form.meta_description_en,
    meta_keywords_es: form.meta_keywords_es,
    meta_keywords_en: form.meta_keywords_en,
    cover_image_credit: form.cover_image_credit,
    cover_image_credit_url: form.cover_image_credit_url,
    linkedin_summary_es: form.linkedin_summary_es,
    linkedin_summary_en: form.linkedin_summary_en,
  };

  if (publishMode.value === 'now') {
    payload.is_published = true;
    payload.published_at = null;
  } else if (publishMode.value === 'schedule') {
    payload.is_published = false;
    payload.published_at = scheduledDate.value ? new Date(scheduledDate.value).toISOString() : null;
  } else {
    payload.is_published = false;
    payload.published_at = null;
  }

  if (form.cover_image_url) {
    payload.cover_image_url = form.cover_image_url;
  }

  const result = await blogStore.updatePost(route.params.id, payload);
  if (result.success) {
    successMsg.value = 'Post actualizado correctamente.';
    setTimeout(() => { successMsg.value = ''; }, 3000);
    commitBaseline();
    return true;
  }
  errorMsg.value = 'Error al actualizar el post. Revisa los campos.';
  // Sin re-baseline: un guardado fallido deja el aviso puesto.
  return false;
}
</script>

<style scoped>
.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.drawer-enter-active > div:last-child,
.drawer-leave-active > div:last-child {
  transition: transform 0.3s ease;
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from > div:last-child,
.drawer-leave-to > div:last-child {
  transform: translateX(100%);
}
</style>
