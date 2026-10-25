<template>
  <form class="space-y-4" @submit.prevent="$emit('save', form)">
    <div class="grid gap-4 lg:grid-cols-2">
      <BaseFormField :label="tr('slug')" for="help-tour-slug"><input id="help-tour-slug" v-model="form.slug" :disabled="Boolean(form.id)" required pattern="[a-zA-Z0-9_-]+" class="w-full rounded-xl border border-border-default bg-surface p-3" /></BaseFormField>
      <BaseFormField :label="tr('context')" for="help-tour-context"><select id="help-tour-context" v-model="form.context" :disabled="Boolean(form.id)" class="w-full rounded-xl border border-border-default bg-surface p-3"><option v-for="context in contexts" :key="context" :value="context">{{ tr(`context${context[0].toUpperCase()}${context.slice(1)}`) }}</option></select></BaseFormField>
      <BaseFormField v-for="language in ['es', 'en']" :key="language" :label="tr(language === 'es' ? 'titleEs' : 'titleEn')" :for="`help-title-${language}`"><input :id="`help-title-${language}`" v-model="form.content[`title_${language}`]" required maxlength="160" class="w-full rounded-xl border border-border-default bg-surface p-3" /></BaseFormField>
      <BaseFormField :label="tr('priority')" for="help-tour-priority"><input id="help-tour-priority" v-model.number="form.priority" type="number" min="0" max="32767" class="w-full rounded-xl border border-border-default bg-surface p-3" /></BaseFormField>
      <label class="flex items-center gap-2"><BaseToggle v-model="form.is_active" :aria-label="tr('active')" /><span>{{ tr('active') }}</span></label>
    </div>
    <fieldset v-for="(step, index) in form.content.steps" :key="index" class="space-y-3 rounded-xl border border-border-default p-4">
      <legend class="px-2 font-medium">{{ index + 1 }}</legend>
      <BaseFormField :label="tr('target')" :for="`tour-target-${index}`"><select :id="`tour-target-${index}`" v-model="step.target" required class="w-full rounded-xl border border-border-default bg-surface p-3"><option v-for="target in targetOptions" :key="target" :value="target">{{ tr(`targets.${target}`) }}</option></select></BaseFormField>
      <div class="grid gap-3 lg:grid-cols-2">
        <template v-for="language in ['es', 'en']" :key="language">
          <BaseFormField :label="tr(language === 'es' ? 'titleEs' : 'titleEn')" :for="`tour-step-title-${index}-${language}`"><input :id="`tour-step-title-${index}-${language}`" v-model="step[`title_${language}`]" required maxlength="160" class="w-full rounded-xl border border-border-default bg-surface p-3" /></BaseFormField>
          <BaseFormField :label="tr(language === 'es' ? 'descriptionEs' : 'descriptionEn')" :for="`tour-step-description-${index}-${language}`"><textarea :id="`tour-step-description-${index}-${language}`" v-model="step[`description_${language}`]" required maxlength="1600" rows="3" class="w-full rounded-xl border border-border-default bg-surface p-3" /></BaseFormField>
        </template>
      </div>
      <div class="flex flex-wrap gap-2">
        <BaseButton variant="ghost" :disabled="index === 0" @click="move(index, -1)">{{ tr('up') }}</BaseButton>
        <BaseButton variant="ghost" :disabled="index === form.content.steps.length - 1" @click="move(index, 1)">{{ tr('down') }}</BaseButton>
        <BaseButton variant="ghost" :disabled="form.content.steps.length === 1" @click="form.content.steps.splice(index, 1)">{{ tr('removeStep') }}</BaseButton>
      </div>
    </fieldset>
    <div class="flex flex-wrap gap-3">
      <BaseButton variant="secondary" :disabled="form.content.steps.length >= 30" @click="addStep">{{ tr('addStep') }}</BaseButton>
      <BaseButton variant="accent" type="submit" :disabled="busy">{{ tr('save') }}</BaseButton>
      <BaseButton v-if="form.id" variant="secondary" :disabled="busy" @click="$emit('publish', form)">{{ tr('publish') }}</BaseButton>
      <BaseButton v-if="form.id" variant="ghost" @click="$emit('preview', form.id)">{{ tr('preview') }}</BaseButton>
      <BaseButton v-if="form.id" variant="ghost" @click="$emit('revisions', form.id)">{{ tr('revisions') }}</BaseButton>
    </div>
  </form>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
const props = defineProps({ tour: { type: Object, required: true }, targets: { type: Object, required: true }, busy: { type: Boolean, default: false } })
defineEmits(['save', 'publish', 'preview', 'revisions'])
const { t } = useI18n()
const tr = (key) => t(`platformHelp.${key}`)
const contexts = ['general', 'project', 'voice']
const form = ref(JSON.parse(JSON.stringify(props.tour)))
watch(() => props.tour, (value) => { form.value = JSON.parse(JSON.stringify(value)) })
const targetOptions = computed(() => Object.keys(props.targets).filter((key) => props.targets[key].context === form.value.context))
function addStep() { form.value.content.steps.push({ target: targetOptions.value[0], title_es: '', title_en: '', description_es: '', description_en: '' }) }
function move(index, offset) { const steps = form.value.content.steps; [steps[index], steps[index + offset]] = [steps[index + offset], steps[index]] }
</script>
