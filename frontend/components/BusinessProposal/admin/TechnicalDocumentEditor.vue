<template>
  <div class="technical-document-editor space-y-8" data-testid="technical-document-editor">
    <p class="text-xs text-text-muted">
      Detalle técnico: cómo se construye el sistema. Módulos del producto y requerimientos con <code class="text-[10px] bg-surface-raised px-1 rounded">epicKey</code> /
      <code class="text-[10px] bg-surface-raised px-1 rounded">flowKey</code> para enlazar después con el tablero en plataforma.
      <code class="text-[10px] bg-surface-raised px-1 rounded">linked_module_ids</code> alinea el detalle técnico con módulos comerciales de la propuesta. Los ids legacy se normalizan automáticamente al guardar.
    </p>

    <div
      v-if="itemLinkOptions.length"
      data-testid="technical-item-coverage"
      class="rounded-xl border p-4 space-y-2"
      :class="coverageSummary.missingRequired.length
        ? 'border-red-200 bg-red-50 text-red-900'
        : 'border-emerald-200 bg-success-soft text-emerald-900'"
    >
      <p class="text-sm font-semibold">
        Trazabilidad comercial ↔ técnica:
        {{ coverageSummary.coveredRequiredCount }}/{{ coverageSummary.requiredCount }} items incluidos enlazados
      </p>
      <p v-if="coverageSummary.missingRequired.length" class="text-xs leading-relaxed">
        Faltan {{ coverageSummary.missingRequired.length }} items obligatorios. El detalle no se puede guardar hasta enlazarlos desde al menos un requerimiento:
        <span class="font-semibold">{{ missingRequiredLabels }}</span>.
      </p>
      <p v-else class="text-xs leading-relaxed">
        Todos los items del alcance incluido tienen al menos un requerimiento técnico enlazado.
      </p>
      <details v-if="coverageSummary.missingOptional.length" class="text-xs">
        <summary class="cursor-pointer font-medium">
          {{ coverageSummary.missingOptional.length }} items opcionales aún no enlazados (no bloquean el guardado)
        </summary>
        <p class="mt-2 leading-relaxed opacity-80">{{ missingOptionalLabels }}</p>
      </details>
    </div>

    <div
      v-if="moduleLinkOptions.length"
      class="rounded-xl border border-dashed border-emerald-200 bg-primary-soft p-4 space-y-2"
    >
      <p class="text-xs font-medium text-text-default">Plantilla genérica por módulo comercial</p>
      <p class="text-[11px] text-text-muted">
        Inserta un módulo con texto neutro y vínculo al alcance comercial. Si el vínculo apunta a alcance opcional, solo será visible cuando el cliente lo incluya.
      </p>
      <div class="flex flex-wrap items-end gap-2">
        <label class="text-xs text-text-muted/60 flex flex-col gap-1">
          <span>Módulo</span>
          <select
            v-model="stubModuleId"
            class="px-2 py-1.5 border dark:border-white/[0.08] rounded-lg text-sm min-w-[12rem] bg-surface dark:text-white"
          >
            <option value="">— Elegir —</option>
            <option v-for="opt in moduleLinkOptions" :key="'stub-'+opt.id" :value="opt.id">
              {{ opt.label }}
            </option>
          </select>
        </label>
        <BaseButton variant="primary" size="sm" :disabled="!stubModuleId" disabled-reason="Selecciona un módulo antes de insertar su bloque." @click="insertGenericStub">
          Insertar módulo genérico
        </BaseButton>
      </div>
    </div>

    <!-- Propósito -->
    <section class="space-y-2">
      <button
        type="button"
        class="w-full flex items-center justify-between gap-2 text-left"
        :aria-expanded="openSections.has('purpose')"
        data-testid="technical-section-toggle-purpose"
        @click="toggleSection('purpose')"
      >
        <span class="text-sm font-semibold text-text-default">Propósito</span>
        <span class="flex items-center gap-1 text-xs text-text-subtle">{{ sectionCounts.purpose }} <BaseActionIcon :action="openSections.has('purpose') ? 'collapse' : 'expand'" /></span>
      </button>
      <template v-if="openSections.has('purpose')">
      <BaseRichTextEditor
        v-model="doc.purpose"
        data-testid="technical-purpose-textarea"
        class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 outline-none"
        placeholder="Una frase sobre qué cubre este documento..."
       :format="doc.text_formats?.['/purpose'] || 'plain'" @update:format="doc.text_formats = { ...doc.text_formats, '/purpose': $event }" />
      </template>
    </section>

    <!-- Stack -->
    <section class="space-y-3">
      <button
        type="button"
        class="w-full flex items-center justify-between gap-2 text-left"
        :aria-expanded="openSections.has('stack')"
        data-testid="technical-section-toggle-stack"
        @click="toggleSection('stack')"
      >
        <span class="text-sm font-semibold text-text-default">Stack tecnológico</span>
        <span class="flex items-center gap-1 text-xs text-text-subtle">{{ sectionCounts.stack }} <BaseActionIcon :action="openSections.has('stack') ? 'collapse' : 'expand'" /></span>
      </button>
      <template v-if="openSections.has('stack')">
      <div class="flex justify-end">
        <BaseButton variant="link" size="sm" @click="addStackRow"><BaseActionIcon action="create" /> Fila</BaseButton>
      </div>
      <div v-for="(row, i) in doc.stack" :key="'st-' + i" class="grid grid-cols-1 md:grid-cols-3 gap-2 p-3 bg-surface-raised rounded-xl border border-border-muted">
        <input v-model="row.layer" placeholder="Capa" class="px-2 py-1.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm">
        <input v-model="row.technology" placeholder="Tecnología" class="px-2 py-1.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm">
        <div class="flex gap-2">
          <input v-model="row.rationale" placeholder="Justificación técnica" class="flex-1 px-2 py-1.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm">
          <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar fila" size="sm" class="shrink-0" @click="doc.stack.splice(i, 1)" />
        </div>
      </div>
      </template>
    </section>

    <!-- Arquitectura -->
    <section class="space-y-3">
      <button
        type="button"
        class="w-full flex items-center justify-between gap-2 text-left"
        :aria-expanded="openSections.has('architecture')"
        data-testid="technical-section-toggle-architecture"
        @click="toggleSection('architecture')"
      >
        <span class="text-sm font-semibold text-text-default">Arquitectura</span>
        <span class="flex items-center gap-1 text-xs text-text-subtle">{{ sectionCounts.architecture }} <BaseActionIcon :action="openSections.has('architecture') ? 'collapse' : 'expand'" /></span>
      </button>
      <template v-if="openSections.has('architecture')">
      <BaseRichTextEditor v-model="doc.architecture.summary" class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm" placeholder="Resumen de capas y comunicación..."  :format="doc.architecture.text_formats?.['/summary'] || 'plain'" @update:format="doc.architecture.text_formats = { ...doc.architecture.text_formats, '/summary': $event }" />
      <div class="flex items-center justify-between">
        <span class="text-xs text-text-muted">Patrones por componente</span>
        <BaseButton variant="link" size="sm" @click="addPatternRow"><BaseActionIcon action="create" /> Fila</BaseButton>
      </div>
      <div v-for="(row, i) in doc.architecture.patterns" :key="'pat-' + i" class="grid grid-cols-1 md:grid-cols-3 gap-2 p-3 bg-surface-raised rounded-xl border border-border-muted">
        <input v-model="row.component" placeholder="Componente" class="px-2 py-1.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm">
        <input v-model="row.pattern" placeholder="Patrón" class="px-2 py-1.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm">
        <div class="flex gap-2">
          <input v-model="row.description" placeholder="Descripción" class="flex-1 px-2 py-1.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm">
          <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar fila" size="sm" @click="doc.architecture.patterns.splice(i, 1)" />
        </div>
      </div>
      <p class="text-xs text-text-muted">Diagramas / anexo</p>
      <BaseRichTextEditor
        v-model="doc.architecture.diagramNote"
        class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm"
        placeholder="Nota breve si hay diagrama en anexo o URL externa..."
       :format="doc.architecture.text_formats?.['/diagramNote'] || 'plain'" @update:format="doc.architecture.text_formats = { ...doc.architecture.text_formats, '/diagramNote': $event }" />
      </template>
    </section>

    <!-- Modelo de datos -->
    <section class="space-y-3">
      <button
        type="button"
        class="w-full flex items-center justify-between gap-2 text-left"
        :aria-expanded="openSections.has('data-model')"
        data-testid="technical-section-toggle-data-model"
        @click="toggleSection('data-model')"
      >
        <span class="text-sm font-semibold text-text-default">Modelo de datos</span>
        <span class="flex items-center gap-1 text-xs text-text-subtle">{{ sectionCounts['data-model'] }} <BaseActionIcon :action="openSections.has('data-model') ? 'collapse' : 'expand'" /></span>
      </button>
      <template v-if="openSections.has('data-model')">
      <BaseRichTextEditor v-model="doc.dataModel.summary" class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm" placeholder="Resumen..."  :format="doc.dataModel.text_formats?.['/summary'] || 'plain'" @update:format="doc.dataModel.text_formats = { ...doc.dataModel.text_formats, '/summary': $event }" />
      <p class="text-xs text-text-muted">Relaciones entre entidades (texto)</p>
      <textarea
        v-model="doc.dataModel.relationships"
        v-auto-resize
        class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm"
        placeholder="Ej. Usuario tiene muchos Pedidos..."
      />
      <div class="flex justify-end">
        <BaseButton variant="link" size="sm" @click="addEntityRow"><BaseActionIcon action="create" /> Entidad</BaseButton>
      </div>
      <div v-for="(row, i) in doc.dataModel.entities" :key="'ent-' + i" class="grid grid-cols-1 md:grid-cols-3 gap-2 p-3 bg-surface-raised rounded-xl border border-border-muted">
        <input v-model="row.name" placeholder="Entidad" class="px-2 py-1.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm">
        <input v-model="row.description" placeholder="Descripción" class="px-2 py-1.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm">
        <div class="flex gap-2">
          <input v-model="row.keyFields" placeholder="Campos clave (texto libre)" class="flex-1 px-2 py-1.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm">
          <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar entidad" size="sm" @click="doc.dataModel.entities.splice(i, 1)" />
        </div>
      </div>
      </template>
    </section>

    <!-- Preparación para el crecimiento -->
    <section class="space-y-3">
      <button
        type="button"
        class="w-full flex items-center justify-between gap-2 text-left"
        :aria-expanded="openSections.has('growth')"
        data-testid="technical-section-toggle-growth"
        @click="toggleSection('growth')"
      >
        <span class="text-sm font-semibold text-text-default">Preparación para el crecimiento</span>
        <span class="flex items-center gap-1 text-xs text-text-subtle">{{ sectionCounts.growth }} <BaseActionIcon :action="openSections.has('growth') ? 'collapse' : 'expand'" /></span>
      </button>
      <template v-if="openSections.has('growth')">
      <p class="text-xs text-text-muted">
        Cómo se prepara el sistema para crecer (tráfico, datos, equipos, integraciones). Complementa «Rendimiento»; aquí el foco es capacidad de evolución, no solo métricas puntuales.
      </p>
      <BaseRichTextEditor
        v-model="doc.growthReadiness.summary"
        class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 outline-none"
        placeholder="Resumen: enfoque de crecimiento sin rediseño completo, supuestos y límites..."
       :format="doc.growthReadiness.text_formats?.['/summary'] || 'plain'" @update:format="doc.growthReadiness.text_formats = { ...doc.growthReadiness.text_formats, '/summary': $event }" />
      <div class="flex items-center justify-between">
        <span class="text-xs text-text-muted">Estrategias por dimensión (tabla)</span>
        <BaseButton variant="link" size="sm" @click="addGrowthStrategyRow"><BaseActionIcon action="create" /> Fila</BaseButton>
      </div>
      <div
        v-for="(row, i) in doc.growthReadiness.strategies"
        :key="'gr-' + i"
        class="grid grid-cols-1 md:grid-cols-3 gap-2 p-3 bg-surface-raised rounded-xl border border-border-muted"
      >
        <input v-model="row.dimension" placeholder="Dimensión (ej. tráfico, datos)" class="px-2 py-1.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm">
        <input v-model="row.preparation" placeholder="Preparación actual" class="px-2 py-1.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm">
        <div class="flex gap-2">
          <input v-model="row.evolution" placeholder="Evolución ante crecimiento" class="flex-1 px-2 py-1.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm">
          <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar estrategia" size="sm" class="shrink-0" @click="doc.growthReadiness.strategies.splice(i, 1)" />
        </div>
      </div>
      </template>
    </section>

    <!-- Módulos del producto -->
    <section class="space-y-4">
      <button
        type="button"
        class="w-full flex items-center justify-between gap-2 text-left"
        :aria-expanded="openSections.has('epics')"
        data-testid="technical-section-toggle-epics"
        @click="toggleSection('epics')"
      >
        <span class="text-sm font-semibold text-text-default">Módulos del producto</span>
        <span class="flex items-center gap-1 text-xs text-text-subtle">{{ sectionCounts.epics }} <BaseActionIcon :action="openSections.has('epics') ? 'collapse' : 'expand'" /></span>
      </button>
      <template v-if="openSections.has('epics')">
      <div class="flex justify-end">
        <BaseButton variant="primary" size="sm" @click="addEpic">
          <BaseActionIcon action="create" />
          Módulo
        </BaseButton>
      </div>
      <div
        v-for="(epic, ei) in doc.epics"
        :key="'epic-' + ei"
        class="border border-border-default dark:border-white/[0.08] rounded-xl p-4 space-y-3 bg-surface"
      >
        <div class="flex flex-wrap gap-2 items-start justify-between">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 flex-1 min-w-0">
            <input v-model="epic.epicKey" placeholder="epicKey (slug único)" class="px-2 py-1.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm font-mono text-xs">
            <input v-model="epic.title" placeholder="Título del módulo" class="px-2 py-1.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm">
          </div>
          <BaseButton variant="danger-ghost" size="sm" @click="doc.epics.splice(ei, 1)">Eliminar módulo</BaseButton>
        </div>
        <BaseRichTextEditor v-model="epic.description" data-testid="technical-epic-description-textarea" class="w-full px-2 py-1.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm" placeholder="Descripción del módulo"  :format="epic.text_formats?.['/description'] || 'plain'" @update:format="epic.text_formats = { ...epic.text_formats, '/description': $event }" />
        <div v-if="moduleLinkOptions.length" class="space-y-1">
          <p class="text-[11px] text-text-muted">Vincular este módulo técnico con alcance comercial (modo técnico / PDF técnico):</p>
          <div class="flex flex-wrap gap-x-3 gap-y-1">
            <label
              v-for="opt in moduleLinkOptions"
              :key="'epl-'+ei+'-'+opt.id"
              class="flex items-center gap-1.5 text-xs text-text-default cursor-pointer"
            >
              <input
                type="checkbox"
                :checked="epic.linked_module_ids.includes(opt.id)"
                class="rounded border-input-border text-text-brand"
                @change="toggleLinkedId(epic.linked_module_ids, opt.id)"
              >
              <span class="max-w-[14rem] truncate" :title="opt.label">{{ opt.label }}</span>
            </label>
          </div>
        </div>
        <div class="pl-3 border-l-2 border-emerald-200 space-y-2">
          <div class="flex justify-between items-center">
            <span class="text-xs font-medium text-text-muted/60">Requerimientos</span>
            <BaseButton variant="link" size="sm" @click="addRequirement(epic)"><BaseActionIcon action="create" /> Requerimiento</BaseButton>
          </div>
          <div
            v-for="(req, ri) in epic.requirements"
            :key="'req-' + ei + '-' + ri"
            class="p-3 bg-surface-raised rounded-lg space-y-2 text-sm"
          >
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <input v-model="req.flowKey" placeholder="flowKey (slug único global)" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded font-mono text-xs">
              <input v-model="req.title" placeholder="Título (obligatorio)" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
              <select v-model="req.priority" class="px-2 py-1 border border-input-border bg-input-bg text-input-text rounded text-xs">
                <option value="">Prioridad (opc.)</option>
                <option value="critical">Crítico</option>
                <option value="high">Alta</option>
                <option value="medium">Media</option>
                <option value="low">Baja</option>
              </select>
            </div>
            <BaseRichTextEditor v-model="req.description" data-testid="technical-req-description-textarea" class="w-full px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded text-xs" placeholder="Descripción"  :format="req.text_formats?.['/description'] || 'plain'" @update:format="req.text_formats = { ...req.text_formats, '/description': $event }" />
            <BaseRichTextEditor v-model="req.configuration" class="w-full px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded text-xs" placeholder="Configuración (roles, permisos...)"  :format="req.text_formats?.['/configuration'] || 'plain'" @update:format="req.text_formats = { ...req.text_formats, '/configuration': $event }" />
            <BaseRichTextEditor v-model="req.usageFlow" class="w-full px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded text-xs" placeholder="Flujo de uso (ej. Login → Dashboard → ...)"  :format="req.text_formats?.['/usageFlow'] || 'plain'" @update:format="req.text_formats = { ...req.text_formats, '/usageFlow': $event }" />
            <TechnicalRequirementLinks
              :req="req"
              :module-link-options="moduleLinkOptions"
              :item-link-options="itemLinkOptions"
              :force-open="expandAll"
            />
            <BaseButton variant="danger-ghost" size="sm" @click="epic.requirements.splice(ri, 1)">Quitar requerimiento</BaseButton>
          </div>
        </div>
      </div>
      </template>
    </section>

    <!-- API (resumen por dominio) -->
    <section class="space-y-3">
      <button
        type="button"
        class="w-full flex items-center justify-between gap-2 text-left"
        :aria-expanded="openSections.has('api')"
        data-testid="technical-section-toggle-api"
        @click="toggleSection('api')"
      >
        <span class="text-sm font-semibold text-text-default">API y endpoints (resumen)</span>
        <span class="flex items-center gap-1 text-xs text-text-subtle">{{ sectionCounts.api }} <BaseActionIcon :action="openSections.has('api') ? 'collapse' : 'expand'" /></span>
      </button>
      <template v-if="openSections.has('api')">
      <textarea
        v-model="doc.apiSummary"
        v-auto-resize
        class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm"
        placeholder="Resumen de la API sin enumerar cada ruta..."
      />
      <div class="flex items-center justify-between">
        <span class="text-xs text-text-muted">Por dominio / módulo</span>
        <BaseButton variant="link" size="sm" @click="addApiDomain"><BaseActionIcon action="create" /> Dominio</BaseButton>
      </div>
      <div v-for="(row, i) in doc.apiDomains" :key="'api-' + i" class="grid grid-cols-1 md:grid-cols-2 gap-2 p-3 bg-surface-raised rounded-xl border border-border-muted">
        <input v-model="row.domain" placeholder="Dominio o área" class="px-2 py-1.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm">
        <div class="flex gap-2">
          <input v-model="row.summary" placeholder="Resumen de endpoints / contratos" class="flex-1 px-2 py-1.5 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm">
          <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar dominio" size="sm" @click="doc.apiDomains.splice(i, 1)" />
        </div>
      </div>
      </template>
    </section>

    <!-- Integraciones -->
    <section class="space-y-4">
      <button
        type="button"
        class="w-full flex items-center justify-between gap-2 text-left"
        :aria-expanded="openSections.has('integrations')"
        data-testid="technical-section-toggle-integrations"
        @click="toggleSection('integrations')"
      >
        <span class="text-sm font-semibold text-text-default">Integraciones</span>
        <span class="flex items-center gap-1 text-xs text-text-subtle">{{ sectionCounts.integrations }} <BaseActionIcon :action="openSections.has('integrations') ? 'collapse' : 'expand'" /></span>
      </button>
      <template v-if="openSections.has('integrations')">
      <h3 class="text-sm font-semibold text-text-default">Integraciones incluidas</h3>
      <BaseButton variant="link" size="sm" @click="addIncluded"><BaseActionIcon action="create" /> Fila</BaseButton>
      <div v-for="(row, i) in doc.integrations.included" :key="'inc-' + i" class="grid grid-cols-1 md:grid-cols-5 gap-2 p-2 bg-surface-raised rounded-lg text-xs">
        <input v-model="row.service" placeholder="Servicio" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <input v-model="row.provider" placeholder="Proveedor" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <input v-model="row.connection" placeholder="Conexión" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <input v-model="row.dataExchange" placeholder="Datos" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <div class="flex gap-1">
          <input v-model="row.accountOwner" placeholder="Responsable cuenta" class="flex-1 px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
          <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar integración" size="sm" @click="doc.integrations.included.splice(i, 1)" />
        </div>
      </div>
      <h3 class="text-sm font-semibold text-text-default pt-2">No incluidas</h3>
      <BaseButton variant="link" size="sm" @click="addExcluded"><BaseActionIcon action="create" /> Fila</BaseButton>
      <div v-for="(row, i) in doc.integrations.excluded" :key="'exc-' + i" class="grid grid-cols-1 md:grid-cols-3 gap-2 p-2 bg-surface-raised rounded-lg text-xs">
        <input v-model="row.service" placeholder="Servicio" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <input v-model="row.reason" placeholder="Motivo" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <div class="flex gap-1">
          <input v-model="row.availability" placeholder="Disponibilidad futura" class="flex-1 px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
          <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar exclusión" size="sm" @click="doc.integrations.excluded.splice(i, 1)" />
        </div>
      </div>
      <p class="text-xs text-text-muted pt-2">Notas técnicas (viñetas, una por línea)</p>
      <BaseRichTextEditor
        v-model="doc.integrations.notes"
        class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm font-mono text-xs"
        placeholder="Línea por línea..."
       :format="doc.integrations.text_formats?.['/notes'] || 'plain'" @update:format="doc.integrations.text_formats = { ...doc.integrations.text_formats, '/notes': $event }" />
      </template>
    </section>

    <!-- Ambientes -->
    <section class="space-y-3">
      <button
        type="button"
        class="w-full flex items-center justify-between gap-2 text-left"
        :aria-expanded="openSections.has('environments')"
        data-testid="technical-section-toggle-environments"
        @click="toggleSection('environments')"
      >
        <span class="text-sm font-semibold text-text-default">Ambientes</span>
        <span class="flex items-center gap-1 text-xs text-text-subtle">{{ sectionCounts.environments }} <BaseActionIcon :action="openSections.has('environments') ? 'collapse' : 'expand'" /></span>
      </button>
      <template v-if="openSections.has('environments')">
      <BaseRichTextEditor
        v-model="doc.environmentsNote"
        class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm"
        placeholder="Nota general sobre ambientes si no usas tabla..."
       :format="doc.text_formats?.['/environmentsNote'] || 'plain'" @update:format="doc.text_formats = { ...doc.text_formats, '/environmentsNote': $event }" />
      <div class="flex items-center justify-between">
        <span class="text-xs text-text-muted">Tabla por ambiente</span>
        <BaseButton variant="link" size="sm" @click="addEnvironmentRow"><BaseActionIcon action="create" /> Fila</BaseButton>
      </div>
      <div v-for="(row, i) in doc.environments" :key="'env-' + i" class="grid grid-cols-1 md:grid-cols-5 gap-2 p-2 bg-surface-raised rounded-lg text-xs">
        <input v-model="row.name" placeholder="Nombre" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <input v-model="row.purpose" placeholder="Propósito" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <input v-model="row.url" placeholder="URL / acceso" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <input v-model="row.database" placeholder="Base de datos" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <div class="flex gap-1">
          <input v-model="row.whoAccesses" placeholder="Quién accede" class="flex-1 px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
          <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar ambiente" size="sm" @click="doc.environments.splice(i, 1)" />
        </div>
      </div>
      </template>
    </section>

    <!-- Seguridad -->
    <section class="space-y-2">
      <button
        type="button"
        class="w-full flex items-center justify-between gap-2 text-left"
        :aria-expanded="openSections.has('security')"
        data-testid="technical-section-toggle-security"
        @click="toggleSection('security')"
      >
        <span class="text-sm font-semibold text-text-default">Seguridad técnica</span>
        <span class="flex items-center gap-1 text-xs text-text-subtle">{{ sectionCounts.security }} <BaseActionIcon :action="openSections.has('security') ? 'collapse' : 'expand'" /></span>
      </button>
      <template v-if="openSections.has('security')">
      <div class="flex justify-end">
        <BaseButton variant="link" size="sm" @click="addSecurityRow"><BaseActionIcon action="create" /> Fila</BaseButton>
      </div>
      <div v-for="(row, i) in doc.security" :key="'sec-' + i" class="flex gap-2 p-2 bg-surface-raised rounded-lg">
        <input v-model="row.aspect" placeholder="Aspecto" class="flex-1 px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded text-sm">
        <input v-model="row.implementation" placeholder="Implementación" class="flex-[2] px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded text-sm">
        <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar control" size="sm" @click="doc.security.splice(i, 1)" />
      </div>
      </template>
    </section>

    <!-- Rendimiento y calidad -->
    <section class="space-y-3">
      <button
        type="button"
        class="w-full flex items-center justify-between gap-2 text-left"
        :aria-expanded="openSections.has('performance')"
        data-testid="technical-section-toggle-performance"
        @click="toggleSection('performance')"
      >
        <span class="text-sm font-semibold text-text-default">Rendimiento y calidad</span>
        <span class="flex items-center gap-1 text-xs text-text-subtle">{{ sectionCounts.performance }} <BaseActionIcon :action="openSections.has('performance') ? 'collapse' : 'expand'" /></span>
      </button>
      <template v-if="openSections.has('performance')">
      <p class="text-xs text-text-muted">Métricas</p>
      <BaseButton variant="link" size="sm" @click="addMetric"><BaseActionIcon action="create" /> Métrica</BaseButton>
      <div v-for="(row, i) in doc.performanceQuality.metrics" :key="'met-' + i" class="grid grid-cols-1 md:grid-cols-3 gap-2 p-2 bg-surface-raised rounded-lg text-sm">
        <input v-model="row.metric" placeholder="Métrica" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <input v-model="row.target" placeholder="Objetivo" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <div class="flex gap-1">
          <input v-model="row.howMeasured" placeholder="Cómo se mide" class="flex-1 px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
          <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar métrica" size="sm" @click="doc.performanceQuality.metrics.splice(i, 1)" />
        </div>
      </div>
      <p class="text-xs text-text-muted">Prácticas</p>
      <BaseButton variant="link" size="sm" @click="addPractice"><BaseActionIcon action="create" /> Práctica</BaseButton>
      <div v-for="(row, i) in doc.performanceQuality.practices" :key="'prac-' + i" class="flex gap-2 p-2 bg-surface-raised rounded-lg">
        <input v-model="row.strategy" placeholder="Estrategia" class="w-1/3 px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded text-sm">
        <input v-model="row.description" placeholder="Descripción" class="flex-1 px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded text-sm">
        <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar práctica" size="sm" @click="doc.performanceQuality.practices.splice(i, 1)" />
      </div>
      </template>
    </section>

    <!-- Backups -->
    <section class="space-y-2">
      <button
        type="button"
        class="w-full flex items-center justify-between gap-2 text-left"
        :aria-expanded="openSections.has('backups')"
        data-testid="technical-section-toggle-backups"
        @click="toggleSection('backups')"
      >
        <span class="text-sm font-semibold text-text-default">Backups</span>
        <span class="flex items-center gap-1 text-xs text-text-subtle">{{ sectionCounts.backups }} <BaseActionIcon :action="openSections.has('backups') ? 'collapse' : 'expand'" /></span>
      </button>
      <template v-if="openSections.has('backups')">
      <BaseRichTextEditor
        v-model="doc.backupsNote"
        class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm"
        placeholder="Hosting propio vs según proveedor del cliente..."
       :format="doc.text_formats?.['/backupsNote'] || 'plain'" @update:format="doc.text_formats = { ...doc.text_formats, '/backupsNote': $event }" />
      </template>
    </section>

    <!-- Calidad (pruebas) -->
    <section class="space-y-3">
      <button
        type="button"
        class="w-full flex items-center justify-between gap-2 text-left"
        :aria-expanded="openSections.has('quality')"
        data-testid="technical-section-toggle-quality"
        @click="toggleSection('quality')"
      >
        <span class="text-sm font-semibold text-text-default">Calidad y pruebas</span>
        <span class="flex items-center gap-1 text-xs text-text-subtle">{{ sectionCounts.quality }} <BaseActionIcon :action="openSections.has('quality') ? 'collapse' : 'expand'" /></span>
      </button>
      <template v-if="openSections.has('quality')">
      <div class="flex items-center justify-between">
        <span class="text-xs text-text-muted">Dimensiones</span>
        <BaseButton variant="link" size="sm" @click="addQualityDimension"><BaseActionIcon action="create" /> Fila</BaseButton>
      </div>
      <div v-for="(row, i) in doc.quality.dimensions" :key="'qd-' + i" class="grid grid-cols-1 md:grid-cols-3 gap-2 p-2 bg-surface-raised rounded-lg text-sm">
        <input v-model="row.dimension" placeholder="Dimensión" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <input v-model="row.evaluates" placeholder="Qué evalúa" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <div class="flex gap-1">
          <input v-model="row.standard" placeholder="Estándar / umbral" class="flex-1 px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
          <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar dimensión" size="sm" @click="doc.quality.dimensions.splice(i, 1)" />
        </div>
      </div>
      <div class="flex items-center justify-between">
        <span class="text-xs text-text-muted">Tipos de prueba</span>
        <BaseButton variant="link" size="sm" @click="addTestType"><BaseActionIcon action="create" /> Fila</BaseButton>
      </div>
      <div v-for="(row, i) in doc.quality.testTypes" :key="'qt-' + i" class="grid grid-cols-1 md:grid-cols-4 gap-2 p-2 bg-surface-raised rounded-lg text-xs">
        <input v-model="row.type" placeholder="Tipo" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <input v-model="row.validates" placeholder="Qué valida" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <input v-model="row.tool" placeholder="Herramienta" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <div class="flex gap-1">
          <input v-model="row.whenRun" placeholder="Cuándo" class="flex-1 px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
          <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar tipo de prueba" size="sm" @click="doc.quality.testTypes.splice(i, 1)" />
        </div>
      </div>
      <p class="text-xs text-text-muted">Flujos críticos de aceptación (texto; no duplicar módulos)</p>
      <BaseRichTextEditor
        v-model="doc.quality.criticalFlowsNote"
        class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-xl text-sm"
        placeholder="Alineación con requerimientos priorizados..."
       :format="doc.quality.text_formats?.['/criticalFlowsNote'] || 'plain'" @update:format="doc.quality.text_formats = { ...doc.quality.text_formats, '/criticalFlowsNote': $event }" />
      </template>
    </section>

    <!-- Decisiones -->
    <section class="space-y-2">
      <button
        type="button"
        class="w-full flex items-center justify-between gap-2 text-left"
        :aria-expanded="openSections.has('decisions')"
        data-testid="technical-section-toggle-decisions"
        @click="toggleSection('decisions')"
      >
        <span class="text-sm font-semibold text-text-default">Decisiones técnicas (ADRs)</span>
        <span class="flex items-center gap-1 text-xs text-text-subtle">{{ sectionCounts.decisions }} <BaseActionIcon :action="openSections.has('decisions') ? 'collapse' : 'expand'" /></span>
      </button>
      <template v-if="openSections.has('decisions')">
      <div class="flex justify-end">
        <BaseButton variant="link" size="sm" @click="addDecision"><BaseActionIcon action="create" /> Fila</BaseButton>
      </div>
      <div v-for="(row, i) in doc.decisions" :key="'dec-' + i" class="grid grid-cols-1 md:grid-cols-3 gap-2 p-2 bg-surface-raised rounded-lg text-sm">
        <input v-model="row.decision" placeholder="Decisión" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <input v-model="row.alternative" placeholder="Alternativa descartada" class="px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
        <div class="flex gap-1">
          <input v-model="row.reason" placeholder="Razón" class="flex-1 px-2 py-1 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded">
          <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar decisión" size="sm" @click="doc.decisions.splice(i, 1)" />
        </div>
      </div>
      </template>
    </section>

    <div class="flex items-center gap-4 pt-4 border-t dark:border-white/[0.06]">
      <BaseButton variant="primary" size="md" :disabled="isSaving" @click="handleSave">
        {{ isSaving ? 'Guardando...' : 'Guardar detalle técnico' }}
      </BaseButton>
      <span v-if="savedMsg" class="text-sm text-text-brand">{{ savedMsg }}</span>
      <span v-if="validationError" class="text-sm text-red-600">{{ validationError }}</span>
    </div>
  </div>
</template>

<script setup>
import { withEditorialFormats } from '~/utils/editorialMetadata';
import { computed, reactive, ref, watch } from 'vue';
import { createGenericTechnicalEpicStub } from '~/utils/technicalModuleStub';
import {
  buildTechnicalItemCoverage,
  buildProposalModuleIdAliasMapFromOptions,
  normalizeLinkedModuleIds,
} from '~/utils/proposalModuleLinkOptions';
import { vAutoResize } from '~/utils/autoResizeDirective';
import TechnicalRequirementLinks from '~/components/BusinessProposal/admin/TechnicalRequirementLinks.vue';

const props = defineProps({
  section: { type: Object, required: true },
  /** { id, label }[] from proposal FR + investment modules */
  moduleLinkOptions: { type: Array, default: () => [] },
  /** Grouped FR items plus isRequiredForCoverage, for linked_item_ids. */
  itemLinkOptions: { type: Array, default: () => [] },
  /** Render every collapsible/disclosure open (unit tests, defaults panel). */
  expandAll: { type: Boolean, default: false },
});

const emit = defineEmits(['save']);

const isSaving = ref(false);
const savedMsg = ref('');
const validationError = ref('');
const stubModuleId = ref('');
const moduleAliasMap = computed(() =>
  buildProposalModuleIdAliasMapFromOptions(props.moduleLinkOptions),
);

function normLinkedIds(raw) {
  return normalizeLinkedModuleIds(raw, moduleAliasMap.value);
}

function toggleLinkedId(arr, id) {
  const i = arr.indexOf(id);
  if (i >= 0) arr.splice(i, 1);
  else arr.push(id);
}

function insertGenericStub() {
  if (!stubModuleId.value) return;
  const opt = props.moduleLinkOptions.find((o) => o.id === stubModuleId.value);
  doc.epics.push(createGenericTechnicalEpicStub(stubModuleId.value, opt?.label || ''));
  // Reveal the inserted module even if the section was collapsed.
  openSections.value = new Set([...openSections.value, 'epics']);
}

function emptyDoc() {
  return {
    purpose: '',
    stack: [],
    architecture: { summary: '', patterns: [], diagramNote: '' },
    dataModel: { summary: '', relationships: '', entities: [] },
    growthReadiness: { summary: '', strategies: [] },
    epics: [],
    apiSummary: '',
    apiDomains: [],
    integrations: { included: [], excluded: [], notes: '' },
    environments: [],
    environmentsNote: '',
    security: [],
    performanceQuality: { metrics: [], practices: [] },
    backupsNote: '',
    quality: { dimensions: [], testTypes: [], criticalFlowsNote: '' },
    decisions: [],
  };
}

function mergeContent(src) {
  const e = emptyDoc();
  if (!src || typeof src !== 'object') return e;
  return withEditorialFormats(src, {
    purpose: typeof src.purpose === 'string' ? src.purpose : e.purpose,
    stack: Array.isArray(src.stack) ? src.stack.map((r) => ({
      layer: r.layer || '',
      technology: r.technology || '',
      rationale: r.rationale || '',
    })) : e.stack,
    architecture: {
      summary: src.architecture?.summary || '',
      diagramNote: typeof src.architecture?.diagramNote === 'string' ? src.architecture.diagramNote : '',
      patterns: Array.isArray(src.architecture?.patterns)
        ? src.architecture.patterns.map((r) => ({
          component: r.component || '',
          pattern: r.pattern || '',
          description: r.description || '',
        }))
        : [],
    },
    dataModel: {
      summary: src.dataModel?.summary || '',
      relationships: typeof src.dataModel?.relationships === 'string' ? src.dataModel.relationships : '',
      entities: Array.isArray(src.dataModel?.entities)
        ? src.dataModel.entities.map((r) => ({
          name: r.name || '',
          description: r.description || '',
          keyFields: r.keyFields || '',
        }))
        : [],
    },
    growthReadiness: {
      summary: typeof src.growthReadiness?.summary === 'string' ? src.growthReadiness.summary : '',
      strategies: Array.isArray(src.growthReadiness?.strategies)
        ? src.growthReadiness.strategies.map((r) => ({
          dimension: r.dimension || '',
          preparation: r.preparation || '',
          evolution: r.evolution || '',
        }))
        : [],
    },
    apiSummary: typeof src.apiSummary === 'string' ? src.apiSummary : '',
    apiDomains: Array.isArray(src.apiDomains)
      ? src.apiDomains.map((r) => ({
        domain: r.domain || '',
        summary: r.summary || '',
      }))
      : [],
    epics: Array.isArray(src.epics)
      ? src.epics.map((ep) => ({
        epicKey: ep.epicKey || '',
        title: ep.title || '',
        description: ep.description || '',
        linked_module_ids: normLinkedIds(ep.linked_module_ids || ep.linkedModuleIds),
        requirements: Array.isArray(ep.requirements)
          ? ep.requirements.map((req) => ({
            flowKey: req.flowKey || '',
            title: req.title || '',
            description: req.description || '',
            configuration: req.configuration || '',
            usageFlow: req.usageFlow || '',
            priority: typeof req.priority === 'string' ? req.priority : '',
            linked_module_ids: normLinkedIds(req.linked_module_ids || req.linkedModuleIds),
            linked_item_ids: normalizeLinkedModuleIds(req.linked_item_ids || req.linkedItemIds),
          }))
          : [],
      }))
      : [],
    integrations: {
      notes: typeof src.integrations?.notes === 'string' ? src.integrations.notes : '',
      included: Array.isArray(src.integrations?.included)
        ? src.integrations.included.map((r) => ({
          service: r.service || '',
          provider: r.provider || '',
          connection: r.connection || '',
          dataExchange: r.dataExchange || '',
          accountOwner: r.accountOwner || '',
        }))
        : [],
      excluded: Array.isArray(src.integrations?.excluded)
        ? src.integrations.excluded.map((r) => ({
          service: r.service || '',
          reason: r.reason || '',
          availability: r.availability || '',
        }))
        : [],
    },
    environments: Array.isArray(src.environments)
      ? src.environments.map((r) => ({
        name: r.name || '',
        purpose: r.purpose || '',
        url: r.url || '',
        database: r.database || '',
        whoAccesses: r.whoAccesses || '',
      }))
      : [],
    environmentsNote: typeof src.environmentsNote === 'string' ? src.environmentsNote : '',
    security: Array.isArray(src.security)
      ? src.security.map((r) => ({ aspect: r.aspect || '', implementation: r.implementation || '' }))
      : [],
    performanceQuality: {
      metrics: Array.isArray(src.performanceQuality?.metrics)
        ? src.performanceQuality.metrics.map((r) => ({
          metric: r.metric || '',
          target: r.target || '',
          howMeasured: r.howMeasured || '',
        }))
        : [],
      practices: Array.isArray(src.performanceQuality?.practices)
        ? src.performanceQuality.practices.map((r) => ({
          strategy: r.strategy || '',
          description: r.description || '',
        }))
        : [],
    },
    backupsNote: typeof src.backupsNote === 'string' ? src.backupsNote : '',
    quality: {
      dimensions: Array.isArray(src.quality?.dimensions)
        ? src.quality.dimensions.map((r) => ({
          dimension: r.dimension || '',
          evaluates: r.evaluates || '',
          standard: r.standard || '',
        }))
        : [],
      testTypes: Array.isArray(src.quality?.testTypes)
        ? src.quality.testTypes.map((r) => ({
          type: r.type || '',
          validates: r.validates || '',
          tool: r.tool || '',
          whenRun: r.whenRun || '',
        }))
        : [],
      criticalFlowsNote: typeof src.quality?.criticalFlowsNote === 'string' ? src.quality.criticalFlowsNote : '',
    },
    decisions: Array.isArray(src.decisions)
      ? src.decisions.map((r) => ({
        decision: r.decision || '',
        alternative: r.alternative || '',
        reason: r.reason || '',
      }))
      : [],
  });
}

const doc = reactive(mergeContent(props.section.content_json));
const coverageSummary = computed(() => buildTechnicalItemCoverage(props.itemLinkOptions, doc));
const missingRequiredLabels = computed(() => coverageSummary.value.missingRequired
  .slice(0, 8)
  .map((item) => `${item.groupLabel}: ${item.label}`)
  .join(' · '));
const missingOptionalLabels = computed(() => coverageSummary.value.missingOptional
  .slice(0, 12)
  .map((item) => `${item.groupLabel}: ${item.label}`)
  .join(' · '));

// Every external write path replaces the section object (store updateSection /
// applySync splice a new section; fetchProposal swaps currentProposal), so a
// reference watch is enough — deep traversal of the whole document is not.
watch(
  () => props.section.content_json,
  (cj) => {
    const merged = mergeContent(cj);
    // A normal save round-trips identical content; skip the doc rebuild so the
    // whole editor does not re-render (and drop focus) after every save.
    if (JSON.stringify(merged) === JSON.stringify(doc)) return;
    Object.assign(doc, merged);
  },
);

/** Section keys of the collapse-by-default layout (order = template order). */
const TECH_SECTION_KEYS = [
  'purpose', 'stack', 'architecture', 'data-model', 'growth', 'epics', 'api',
  'integrations', 'environments', 'security', 'performance', 'backups',
  'quality', 'decisions',
];

// Only Propósito starts open: the tab's first paint should be 14 headers, not
// tens of thousands of matrix nodes. Bodies mount on expand (plain v-if).
const openSections = ref(new Set(props.expandAll ? TECH_SECTION_KEYS : ['purpose']));

function toggleSection(key) {
  const next = new Set(openSections.value); // reassign so Set changes are reactive
  if (next.has(key)) next.delete(key);
  else next.add(key);
  openSections.value = next;
}

const sectionCounts = computed(() => {
  const reqTotal = doc.epics.reduce((n, e) => n + (e.requirements?.length || 0), 0);
  return {
    purpose: doc.purpose?.trim() ? '✓' : 'vacío',
    stack: `${doc.stack.length} filas`,
    architecture: `${doc.architecture.patterns.length} patrones`,
    'data-model': `${doc.dataModel.entities.length} entidades`,
    growth: `${doc.growthReadiness.strategies.length} filas`,
    epics: `${doc.epics.length} módulos · ${reqTotal} reqs`,
    api: `${doc.apiDomains.length} dominios`,
    integrations: `${doc.integrations.included.length} incl. · ${doc.integrations.excluded.length} excl.`,
    environments: `${doc.environments.length} filas`,
    security: `${doc.security.length} filas`,
    performance: `${doc.performanceQuality.metrics.length} métricas · ${doc.performanceQuality.practices.length} prácticas`,
    backups: doc.backupsNote?.trim() ? '✓' : 'vacío',
    quality: `${doc.quality.dimensions.length} dim. · ${doc.quality.testTypes.length} tipos`,
    decisions: `${doc.decisions.length} filas`,
  };
});

function addStackRow() {
  doc.stack.push({ layer: '', technology: '', rationale: '' });
}
function addPatternRow() {
  doc.architecture.patterns.push({ component: '', pattern: '', description: '' });
}
function addEntityRow() {
  doc.dataModel.entities.push({ name: '', description: '', keyFields: '' });
}
function addGrowthStrategyRow() {
  doc.growthReadiness.strategies.push({ dimension: '', preparation: '', evolution: '' });
}
function addEpic() {
  doc.epics.push({
    epicKey: '',
    title: '',
    description: '',
    linked_module_ids: [],
    requirements: [],
  });
}
function addRequirement(epic) {
  epic.requirements.push({
    flowKey: '',
    title: '',
    description: '',
    configuration: '',
    usageFlow: '',
    priority: '',
    linked_module_ids: [],
    linked_item_ids: [],
  });
}
function addApiDomain() {
  doc.apiDomains.push({ domain: '', summary: '' });
}
function addEnvironmentRow() {
  doc.environments.push({
    name: '',
    purpose: '',
    url: '',
    database: '',
    whoAccesses: '',
  });
}
function addQualityDimension() {
  doc.quality.dimensions.push({ dimension: '', evaluates: '', standard: '' });
}
function addTestType() {
  doc.quality.testTypes.push({ type: '', validates: '', tool: '', whenRun: '' });
}
function addIncluded() {
  doc.integrations.included.push({
    service: '',
    provider: '',
    connection: '',
    dataExchange: '',
    accountOwner: '',
  });
}
function addExcluded() {
  doc.integrations.excluded.push({ service: '', reason: '', availability: '' });
}
function addSecurityRow() {
  doc.security.push({ aspect: '', implementation: '' });
}
function addMetric() {
  doc.performanceQuality.metrics.push({ metric: '', target: '', howMeasured: '' });
}
function addPractice() {
  doc.performanceQuality.practices.push({ strategy: '', description: '' });
}
function addDecision() {
  doc.decisions.push({ decision: '', alternative: '', reason: '' });
}

const slugRe = /^[a-z0-9]+(-[a-z0-9]+)*$/;
// epicKey mirrors the commercial group id verbatim (e.g. admin_module), so
// underscores are valid here while flowKey stays strictly kebab.
const epicKeyRe = /^[a-z0-9_]+([-_][a-z0-9_]+)*$/;

function validate() {
  const keys = new Set();
  for (let ei = 0; ei < doc.epics.length; ei++) {
    const ep = doc.epics[ei];
    if (ep.epicKey && !epicKeyRe.test(ep.epicKey)) {
      return `epicKey inválido en módulo "${ep.title || ei + 1}": use solo minúsculas, números, guiones y guiones bajos.`;
    }
    if (ep.epicKey) {
      if (keys.has(`e:${ep.epicKey}`)) return `epicKey duplicado: ${ep.epicKey}`;
      keys.add(`e:${ep.epicKey}`);
    }
    for (let ri = 0; ri < ep.requirements.length; ri++) {
      const req = ep.requirements[ri];
      if (req.flowKey && !slugRe.test(req.flowKey)) {
        return `flowKey inválido: ${req.flowKey}`;
      }
      if (req.flowKey) {
        if (keys.has(`f:${req.flowKey}`)) return `flowKey duplicado: ${req.flowKey}`;
        keys.add(`f:${req.flowKey}`);
      }
      if ((req.title || '').trim() === '' && (req.flowKey || req.description || req.configuration || req.usageFlow)) {
        return 'Cada requerimiento con contenido debe tener título.';
      }
    }
  }
  if (coverageSummary.value.missingRequired.length) {
    return `Faltan ${coverageSummary.value.missingRequired.length} items obligatorios por enlazar con requerimientos técnicos.`;
  }
  return '';
}

function toJson() {
  return JSON.parse(JSON.stringify(doc));
}

function handleSave() {
  validationError.value = '';
  const err = validate();
  if (err) {
    validationError.value = err;
    return;
  }
  isSaving.value = true;
  savedMsg.value = '';
  emit('save', {
    sectionId: props.section.id,
    payload: {
      ...(props.section.proposal_source_hash ? { source_hash: props.section.proposal_source_hash } : {}),
      title: props.section.title,
      is_wide_panel: props.section.is_wide_panel,
      content_json: toJson(),
    },
  });
  savedMsg.value = '✓ Guardado';
  setTimeout(() => { savedMsg.value = ''; }, 3000);
  isSaving.value = false;
}
</script>
