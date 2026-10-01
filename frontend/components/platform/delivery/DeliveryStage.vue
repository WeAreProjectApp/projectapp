<script setup>
import BaseBadge from '~/components/base/BaseBadge.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import DeliveryDocuments from './DeliveryDocuments.vue'
import DeliveryRequirementGuide from './DeliveryRequirementGuide.vue'
import DeliveryReviewHistory from './DeliveryReviewHistory.vue'

const props = defineProps({
  stage: { type: Object, required: true }, projectId: { type: [String, Number], required: true },
  isAdmin: { type: Boolean, default: false }, busy: { type: Boolean, default: false },
})
const emit = defineEmits(['author', 'remove', 'publish', 'review', 'historical', 'report', 'attach', 'download', 'unlink', 'copy'])
const { t, locale } = useI18n()
const localePath = useLocalePath()
const route = useRoute()
const stageLink = () => localePath({ path: `/platform/projects/${props.projectId}/delivery`, query: { stage: props.stage.id } })
const isFrozen = () => props.stage.status === 'approved'
const reviewAvailable = () => !!props.stage.publication_id && props.stage.requirements.some((item) => item.review_status === 'in_review')
const canReopen = () => props.stage.requirements.some((item) => ['objected', 'rejected'].includes(item.review_status))
const edit = (entity, node) => emit('author', { entity, node })
const add = () => emit('author', { entity: 'requirements', initial: { stage_id: props.stage.id } })
const formattedDate = (value) => value ? new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : ''
</script>

<template>
  <section :id="`stage-${stage.id}`" class="min-w-0 space-y-5 rounded-xl border border-border-default bg-surface-raised p-4 sm:p-5" :data-testid="`delivery-stage-${stage.id}`" :aria-current="String(route.query.stage) === String(stage.id) ? 'location' : undefined">
    <header class="space-y-3">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0 flex-1">
          <p class="text-xs text-text-muted">{{ t('platformDelivery.stage') }} · {{ stage.key }}</p>
          <h4 class="break-words text-lg font-semibold text-text-default"><NuxtLink :to="stageLink()">{{ stage.title }}</NuxtLink></h4>
        </div>
        <div class="flex flex-wrap gap-2">
          <BaseBadge v-if="isAdmin" :variant="stage.editorial_status === 'published' ? 'info' : 'neutral'">{{ t(`platformDelivery.status.${stage.editorial_status}`) }}</BaseBadge>
          <BaseBadge :variant="stage.status === 'approved' ? 'success' : 'warning'">{{ t(`platformDelivery.status.${stage.status || 'pending'}`) }}</BaseBadge>
        </div>
      </div>
      <p v-if="stage.description" class="whitespace-pre-line break-words text-sm text-text-muted">{{ stage.description }}</p>
      <div class="flex flex-wrap gap-2">
        <template v-if="isAdmin && !isFrozen()">
          <BaseButton variant="secondary" size="sm" @click="edit('stages', stage)">{{ t('platformDelivery.edit') }}</BaseButton>
          <BaseButton variant="danger-ghost" size="sm" @click="emit('remove', { entity: 'stages', node: stage })">{{ t('platformDelivery.remove') }}</BaseButton>
          <BaseButton variant="secondary" size="sm" :data-testid="`delivery-add-requirement-${stage.id}`" @click="add">{{ t('platformDelivery.addRequirement') }}</BaseButton>
          <BaseButton v-if="stage.editorial_status !== 'published' || canReopen()" size="sm" :loading="busy" :data-testid="`delivery-publish-${stage.id}`" @click="emit('publish', stage)">{{ t(stage.editorial_status === 'published' ? 'platformDelivery.reopenRound' : 'platformDelivery.publish') }}</BaseButton>
          <BaseButton v-if="stage.publication_id" variant="secondary" size="sm" @click="emit('historical', stage)">{{ t('platformDelivery.historical') }}</BaseButton>
        </template>
        <BaseButton v-if="!isAdmin && reviewAvailable()" size="sm" :data-testid="`delivery-review-open-${stage.id}`" @click="emit('review', stage)">{{ t('platformDelivery.review') }}</BaseButton>
        <BaseButton v-if="isAdmin || stage.publication_id" variant="secondary" size="sm" :data-testid="`delivery-report-open-${stage.id}`" @click="emit('report', stage)">{{ t('platformDelivery.report') }}</BaseButton>
        <BaseButton variant="ghost" size="sm" @click="emit('copy', stage)">{{ t('platformDelivery.copyLink') }}</BaseButton>
      </div>
    </header>
    <DeliveryDocuments :documents="stage.documents" :can-edit="isAdmin && !isFrozen()" @attach="emit('attach', { level: 'stage', node: stage })" @download="emit('download', $event)" @unlink="emit('unlink', $event)" />
    <p v-if="!stage.requirements.length" class="text-sm text-text-muted">{{ t('platformDelivery.emptyStage') }}</p>
    <DeliveryRequirementGuide v-for="requirement in stage.requirements" :key="requirement.id" :requirement="requirement">
      <DeliveryDocuments :documents="requirement.documents" :can-edit="isAdmin && !isFrozen() && requirement.review_status !== 'approved'" @attach="emit('attach', { level: 'requirement', node: requirement })" @download="emit('download', $event)" @unlink="emit('unlink', $event)" />
      <div class="flex flex-wrap gap-2 border-t border-border-muted pt-3">
        <template v-if="isAdmin && !isFrozen() && requirement.review_status !== 'approved'">
          <BaseButton variant="secondary" size="sm" :data-testid="`delivery-edit-requirement-${requirement.id}`" @click="edit('requirements', requirement)">{{ t('platformDelivery.edit') }}</BaseButton>
          <BaseButton variant="danger-ghost" size="sm" @click="emit('remove', { entity: 'requirements', node: requirement })">{{ t('platformDelivery.remove') }}</BaseButton>
        </template>
        <template v-if="stage.publication_id">
          <NuxtLink :to="localePath({ path: `/platform/projects/${projectId}/bugs`, query: { from_req: requirement.id, title: requirement.title } })" class="text-sm font-medium text-text-brand underline">{{ t('platformDelivery.reportBug') }}</NuxtLink>
          <NuxtLink :to="localePath({ path: `/platform/projects/${projectId}/changes`, query: { from_req: requirement.id, title: requirement.title } })" class="text-sm font-medium text-text-brand underline">{{ t('platformDelivery.requestChange') }}</NuxtLink>
        </template>
      </div>
      <DeliveryReviewHistory :reviews="requirement.reviews" @download="emit('download', $event)" />
    </DeliveryRequirementGuide>
    <section class="space-y-3 border-t border-border-muted pt-4">
      <h5 class="text-sm font-semibold text-text-default">{{ t('platformDelivery.history') }}</h5>
      <p v-if="!stage.messages?.length" class="text-sm text-text-muted">{{ t('platformDelivery.noMessages') }}</p>
      <article v-for="message in stage.messages" :key="message.id" class="space-y-2 rounded-xl border border-border-default bg-surface p-4">
        <header class="flex flex-wrap justify-between gap-2 text-xs text-text-muted">
          <span>{{ message.actor_name }}</span><time :datetime="message.created_at">{{ formattedDate(message.created_at) }}</time>
        </header>
        <BaseBadge v-if="message.is_internal" variant="neutral">{{ t('platformDelivery.internalMessage') }}</BaseBadge>
        <p class="whitespace-pre-line break-words text-sm text-text-default">{{ message.message }}</p>
        <ul v-if="message.requirement_ids?.length" class="flex flex-wrap gap-2">
          <li v-for="id in message.requirement_ids" :key="id" class="text-xs text-text-muted">{{ stage.requirements.find((item) => item.id === id)?.title }}</li>
        </ul>
        <DeliveryDocuments v-if="message.documents?.length" :documents="message.documents" @download="emit('download', $event)" />
      </article>
    </section>
  </section>
</template>
