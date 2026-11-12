<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { packageError } from "~/services/requirementPackagesApi";

const props = defineProps({
  api: { type: Object, required: true },
  language: { type: String, default: "es" },
  globalOnly: { type: Boolean, default: false },
});
const emit = defineEmits(["saved"]);
const { t } = useI18n();
const tr = (key) => t(`requirementPackages.${key}`);
const globalScope = ref(props.globalOnly);
const data = ref(null);
const values = ref({});
const note = ref("");
const error = ref("");
const busy = ref(false);
const history = ref(null);
const historyOffset = ref(0);
const sizes = ["XS", "S", "M", "L", "XL", "PROJECT"];
const fieldClass =
  "w-full rounded-lg border border-input-border bg-input-bg px-3 py-2 text-sm text-input-text";
const dirty = computed(
  () =>
    data.value &&
    (note.value.trim() || sizes.some((size) => values.value[size]?.trim())),
);
let sequence = 0;

async function load() {
  const current = ++sequence;
  busy.value = true;
  error.value = "";
  history.value = null;
  historyOffset.value = 0;
  try {
    const result = await props.api.examples(props.language, globalScope.value);
    if (current !== sequence) return;
    data.value = result;
    const source = globalScope.value
      ? result.generic_examples
      : result.custom_examples;
    values.value = Object.fromEntries(
      sizes.map((size) => [size, (source[size] || []).join("\n")]),
    );
    note.value = "";
  } catch (err) {
    if (current === sequence) error.value = packageError(err);
  } finally {
    if (current === sequence) busy.value = false;
  }
}
async function save() {
  busy.value = true;
  error.value = "";
  try {
    const examples = Object.fromEntries(
      sizes
        .map((size) => [
          size,
          values.value[size]
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean),
        ])
        .filter(([, rows]) => rows.length),
    );
    await props.api.saveExamples(
      {
        examples,
        note: note.value,
        expected_revision: globalScope.value
          ? data.value.generic_revision
          : data.value.project_revision,
      },
      props.language,
      globalScope.value,
    );
    await load();
    emit("saved");
  } catch (err) {
    error.value = packageError(err);
  } finally {
    busy.value = false;
  }
}
async function showHistory(offset = 0) {
  try {
    const result = await props.api.exampleHistory(
      props.language,
      globalScope.value,
      offset,
    );
    history.value = result;
    historyOffset.value = offset;
  } catch (err) {
    error.value = packageError(err);
  }
}
watch([globalScope, () => props.language], load);
onMounted(load);
</script>

<template>
  <section
    class="space-y-4 rounded-xl border border-border-default p-4"
    data-testid="package-example-editor"
  >
    <h3 class="text-lg font-semibold text-text-default">
      {{ tr("examples") }}
    </h3>
    <div class="flex flex-wrap gap-2">
      <BaseButton
        v-if="!globalOnly"
        :variant="globalScope ? 'secondary' : 'primary'"
        :disabled="busy"
        :disabled-reason="tr('busy')"
        @click="globalScope = false"
        >{{ tr("custom") }}</BaseButton
      >
      <BaseButton
        :variant="globalScope ? 'primary' : 'secondary'"
        :disabled="busy"
        :disabled-reason="tr('busy')"
        @click="globalScope = true"
        >{{ tr("generic") }}</BaseButton
      >
    </div>
    <p class="text-sm text-text-muted">{{ tr("examplesHint") }}</p>
    <p v-if="error" role="alert" class="text-sm text-danger-strong">
      {{ error }}
    </p>
    <form v-if="data" class="space-y-4" @submit.prevent="save">
      <div class="grid gap-4 md:grid-cols-2">
        <label
          v-for="size in sizes"
          :key="size"
          class="space-y-2 text-sm text-text-default"
        >
          <span>{{ size }}</span>
          <textarea
            v-model="values[size]"
            :class="fieldClass"
            rows="3"
            maxlength="20000"
            :data-testid="`package-examples-${size}`"
          />
          <span class="block text-xs text-text-muted">{{ tr("preview") }}</span>
          <ul class="list-inside list-disc text-sm text-text-muted">
            <li
              v-for="(example, index) in values[size].trim()
                ? values[size].split('\n').filter(Boolean)
                : data.generic_examples[size]"
              :key="index"
            >
              {{ example }}
            </li>
          </ul>
        </label>
      </div>
      <label class="block space-y-2 text-sm text-text-default"
        ><span>{{ tr("note") }}</span
        ><input v-model="note" :class="fieldClass" required maxlength="2000"
      /></label>
      <div class="flex flex-wrap gap-3">
        <BaseButton
          type="submit"
          variant="primary"
          :disabled="busy || !dirty || !note.trim()"
          :disabled-reason="busy ? tr('busy') : tr('note')"
          >{{ tr("saveExamples") }}</BaseButton
        >
        <BaseButton
          variant="secondary"
          :disabled="busy"
          :disabled-reason="tr('busy')"
          @click="showHistory()"
          >{{ tr("revisions") }}</BaseButton
        >
      </div>
    </form>
    <div v-if="history" class="space-y-3 text-sm text-text-muted">
      <p v-if="!history.count">{{ tr("none") }}</p>
      <details v-for="row in history.results" :key="row.id" class="space-y-2">
        <summary class="cursor-pointer">
          #{{ row.id }} · {{ row.created_at }} · {{ row.note }}
        </summary>
        <div v-for="(examples, size) in row.examples" :key="size">
          <p class="font-semibold">{{ size }}</p>
          <ul class="list-inside list-disc">
            <li v-for="example in examples" :key="example">{{ example }}</li>
          </ul>
        </div>
      </details>
      <div class="flex flex-wrap gap-3">
        <BaseButton
          v-if="historyOffset"
          variant="secondary"
          @click="showHistory(historyOffset - 20)"
          >{{ tr("previous") }}</BaseButton
        >
        <BaseButton
          v-if="history.count > historyOffset + 20"
          variant="secondary"
          @click="showHistory(historyOffset + 20)"
          >{{ tr("more") }}</BaseButton
        >
      </div>
    </div>
  </section>
</template>
