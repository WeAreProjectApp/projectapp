<template>
  <main class="min-h-screen bg-surface-muted px-4 py-10 panel-portrait:py-16" data-testid="secure-link-create-page">
    <div class="mx-auto w-full max-w-2xl space-y-6">
      <p class="text-lg font-bold text-text-default">{{ t('secureLinks.brand') }}</p>

      <section v-if="created" class="space-y-5 rounded-2xl border border-border-default bg-surface p-6 shadow-sm panel-portrait:p-8" data-testid="secure-link-create-result">
        <h1 class="text-2xl font-light text-text-default">{{ t('secureLinks.createdTitle') }}</h1>
        <p class="text-sm text-text-muted">
          {{ t('secureLinks.createdBody', { date: formatDateTime(created.expires_at, { locale: language }) }) }}
        </p>
        <code class="block break-all rounded-xl bg-surface-muted p-3 text-sm" data-testid="secure-link-create-url">{{ created.url }}</code>
        <div class="flex flex-col gap-2 panel-portrait:flex-row">
          <BaseButton variant="primary" data-testid="secure-link-create-copy" @click="copyLink">
            <BaseActionIcon action="copy" />
            {{ copyFeedback.label || t('secureLinks.copyLink') }}
          </BaseButton>
          <BaseButton as="a" variant="secondary" :to="mailtoHref" data-testid="secure-link-create-mail">
            <BaseActionIcon action="send" />
            {{ t('secureLinks.emailIt') }}
          </BaseButton>
          <BaseButton variant="ghost" data-testid="secure-link-create-another" @click="reset">
            {{ t('secureLinks.createAnother') }}
          </BaseButton>
        </div>
      </section>

      <form
        v-else
        novalidate
        class="space-y-5 rounded-2xl border border-border-default bg-surface p-6 shadow-sm panel-portrait:p-8"
        data-testid="secure-link-create-form"
        @submit.prevent="submit"
      >
        <div class="space-y-2">
          <h1 class="text-2xl font-light text-text-default">{{ t('secureLinks.createTitle') }}</h1>
          <p class="text-sm text-text-muted">{{ t('secureLinks.createSubtitle') }}</p>
        </div>

        <BaseFormField v-slot="{ invalid, errorId }" :label="t('secureLinks.type')" for="secure-link-public-type" required :error="errors.secret_type">
          <BaseSelect
            id="secure-link-public-type"
            v-model="form.secretType"
            :options="typeOptions"
            :error="invalid"
            :aria-describedby="errorId"
            data-testid="secure-link-public-type"
          />
        </BaseFormField>

        <SecureLinkFields
          v-model="form.fields"
          :type="selectedType"
          :language="language"
          :errors="errors"
          id-prefix="secure-link-public"
        />

        <BaseFormField v-slot="{ invalid, errorId }" :label="t('secureLinks.yourName')" for="secure-link-public-name" required :error="errors.creator_name">
          <BaseInput id="secure-link-public-name" v-model="form.creatorName" :error="invalid" :aria-describedby="errorId" maxlength="120" data-testid="secure-link-public-name" />
        </BaseFormField>
        <BaseFormField v-slot="{ invalid, errorId }" :label="t('secureLinks.yourEmail')" for="secure-link-public-email" :error="errors.creator_email">
          <BaseInput id="secure-link-public-email" v-model="form.creatorEmail" type="email" :error="invalid" :aria-describedby="errorId" data-testid="secure-link-public-email" />
        </BaseFormField>
        <BaseFormField :label="t('secureLinks.titleLabel')" :hint="t('secureLinks.titleHint')" for="secure-link-public-title">
          <BaseInput id="secure-link-public-title" v-model="form.title" maxlength="160" data-testid="secure-link-public-title" />
        </BaseFormField>
        <BaseFormField :label="t('secureLinks.validity')" for="secure-link-public-validity" :error="errors.validity_days">
          <BaseSegmented id="secure-link-public-validity" v-model="form.validityDays" :options="validityOptions" data-testid="secure-link-public-validity" />
        </BaseFormField>

        <!-- Honeypot: hidden from people and assistive technology. -->
        <div class="absolute -left-[9999px] h-px w-px overflow-hidden" aria-hidden="true">
          <label for="secure-link-website">Website</label>
          <input id="secure-link-website" v-model="form.website" type="text" tabindex="-1" autocomplete="off">
        </div>

        <LoginCaptcha
          v-if="recaptchaEnabled"
          :site-key="recaptchaSiteKey"
          :reset-key="captchaResetKey"
          :retry-available="captchaUnavailable"
          @update:token="recaptchaToken = $event"
        />

        <BaseAlert v-if="generalError" variant="danger" data-testid="secure-link-public-error">{{ generalError }}</BaseAlert>

        <BaseButton
          type="submit"
          variant="primary"
          class="w-full"
          :loading="submitting"
          :disabled="recaptchaEnabled && !recaptchaToken"
          :disabled-reason="recaptchaEnabled && !recaptchaToken ? t('secureLinks.captchaRequired') : ''"
          data-testid="secure-link-public-submit"
        >
          {{ submitting ? t('secureLinks.submitting') : t('secureLinks.submit') }}
        </BaseButton>
      </form>
    </div>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue';
import LoginCaptcha from '~/components/auth/LoginCaptcha.vue';
import BaseActionIcon from '~/components/base/BaseActionIcon.vue';
import BaseAlert from '~/components/base/BaseAlert.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseFormField from '~/components/base/BaseFormField.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import BaseSelect from '~/components/base/BaseSelect.vue';
import SecureLinkFields from '~/components/secureLinks/SecureLinkFields.vue';
import { useClipboardFeedback } from '~/composables/useClipboardFeedback';
import { useSecureLinksStore } from '~/stores/secure_links';
import { formatDateTime } from '~/utils/formatDate';

definePageMeta({ layout: false });

const TEAM_EMAIL = 'team@projectapp.co';
const { t, locale } = useI18n();
const config = useRuntimeConfig();
const store = useSecureLinksStore();
const clipboard = useClipboardFeedback();
const language = computed(() => (locale.value.startsWith('en') ? 'en' : 'es'));
const recaptchaSiteKey = config.public.recaptchaSiteKey;
const recaptchaEnabled = config.public.recaptchaEnabled !== false;

const form = reactive({
  secretType: 'credentials', fields: {}, creatorName: '', creatorEmail: '', title: '',
  validityDays: 7, website: '',
});
const errors = ref({});
const generalError = ref('');
const submitting = ref(false);
const created = ref(null);
const recaptchaToken = ref('');
const captchaResetKey = ref(0);
const captchaUnavailable = ref(false);

const typeOptions = computed(() => store.types.map((type) => ({
  value: type.key,
  label: language.value === 'en' ? type.label_en : type.label_es,
})));
const selectedType = computed(() => store.typeByKey(form.secretType));
const validityOptions = computed(() => [1, 3, 7].map((days) => ({ value: days, label: t('secureLinks.days', days) })));
const copyFeedback = computed(() => clipboard.feedbackFor('secure-link-public-url'));
const mailtoHref = computed(() => (
  created.value
    ? `mailto:${TEAM_EMAIL}?subject=${encodeURIComponent(t('secureLinks.mailSubject'))}&body=${encodeURIComponent(created.value.url)}`
    : undefined
));

useHead(() => ({
  title: t('secureLinks.pageTitle'),
  meta: [
    { name: 'robots', content: 'noindex,nofollow,noarchive' },
    { name: 'referrer', content: 'no-referrer' },
  ],
}));

watch(() => form.secretType, () => { form.fields = {}; });

onMounted(() => store.fetchTypes());

function mapErrors(error) {
  const fieldErrors = error?.fieldErrors || {};
  errors.value = Object.fromEntries(
    Object.entries(fieldErrors).map(([key, value]) => [key, Array.isArray(value) ? value[0] : value]),
  );
  const handled = Object.keys(errors.value).some((key) => key !== 'fields');
  generalError.value = errors.value.fields || (handled ? '' : (error?.message || t('secureLinks.genericError')));
}

async function submit() {
  errors.value = {};
  generalError.value = '';
  submitting.value = true;
  const result = await store.publicCreate({
    secret_type: form.secretType,
    fields: form.fields,
    creator_name: form.creatorName,
    creator_email: form.creatorEmail,
    title: form.title,
    language: language.value,
    validity_days: form.validityDays,
    recaptcha_token: recaptchaToken.value,
    website: form.website,
  });
  submitting.value = false;
  if (!result.success) {
    mapErrors(result.error);
    captchaUnavailable.value = result.error?.code === 'captcha_unavailable';
    captchaResetKey.value += 1;
    return;
  }
  form.fields = {};
  created.value = result.data;
}

function copyLink() {
  return clipboard.copyText({
    key: 'secure-link-public-url',
    text: created.value.url,
    successLabel: t('secureLinks.copied'),
    errorLabel: t('secureLinks.copyFailed'),
  });
}

function reset() {
  created.value = null;
  form.title = '';
  captchaResetKey.value += 1;
}
</script>
