<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import Workspace from "~/components/RequirementPackages/Workspace.vue";
import ExampleEditor from "~/components/RequirementPackages/ExampleEditor.vue";
import { get_request, create_request } from "~/stores/services/request_http";
import {
  createRequirementPackagesApi,
  packageError,
} from "~/services/requirementPackagesApi";

definePageMeta({ layout: "admin", middleware: ["admin-auth"] });
const { t, locale } = useI18n();
const tr = (key, params = {}) => t(`requirementPackages.${key}`, params);
const route = useRoute();
const router = useRouter();
const localePath = useLocalePath();
const projectId = computed(() => Number(route.query.project) || 0);
const language = computed(() => (locale.value.startsWith("en") ? "en" : "es"));
const api = computed(() =>
  createRequirementPackagesApi(
    { get: get_request, post: create_request },
    projectId.value,
  ),
);
const search = ref("");
const projects = ref([]);
const queue = ref(null);
const filter = ref("");
const queueSearch = ref("");
const offset = ref(0);
const error = ref("");
let timer;
let projectSequence = 0;
let queueSequence = 0;
const states = ["", "pending", "evaluating", "offered", "objected", "accepted"];
const projectItems = computed(() =>
  projects.value.map((project) => ({
    label: project.name,
    onClick: () =>
      router.push(
        localePath({
          path: "/panel/requirement-packages",
          query: { project: project.id },
        }),
      ),
  })),
);
const stateItems = computed(() =>
  states.map((state) => ({
    label: state ? tr(state) : tr("requests"),
    onClick: () => {
      filter.value = state;
      offset.value = 0;
      loadQueue();
    },
  })),
);

async function loadProjects() {
  const current = ++projectSequence;
  try {
    const response = await get_request(
      `requirement-packages/admin/projects/?search=${encodeURIComponent(search.value)}`,
    );
    if (current === projectSequence) projects.value = response.data.results;
  } catch (err) {
    error.value = packageError(err);
  }
}
async function loadQueue() {
  const current = ++queueSequence;
  try {
    const query = new URLSearchParams({
      search: queueSearch.value,
      status: filter.value,
      offset: offset.value,
    });
    const response = await get_request(
      `requirement-packages/admin/requests/?${query}`,
    );
    if (current === queueSequence) queue.value = response.data;
  } catch (err) {
    error.value = packageError(err);
  }
}
function scheduleProjects() {
  clearTimeout(timer);
  timer = setTimeout(loadProjects, 250);
}
function scheduleQueue() {
  clearTimeout(timer);
  timer = setTimeout(() => {
    offset.value = 0;
    loadQueue();
  }, 250);
}
async function page(amount) {
  offset.value = Math.max(0, offset.value + amount);
  await loadQueue();
}
watch(projectId, loadQueue);
onMounted(() => {
  loadProjects();
  loadQueue();
});
onBeforeUnmount(() => {
  clearTimeout(timer);
  projectSequence++;
  queueSequence++;
});
</script>

<template>
  <div class="min-w-0 space-y-6 [overflow-wrap:anywhere]">
    <h1 class="text-2xl font-bold text-text-default">{{ tr("queue") }}</h1>
    <p v-if="queue" class="text-sm text-text-muted">
      {{ tr("pendingCount", { count: queue.pending_count }) }}
    </p>
    <p v-if="error" role="alert" class="text-sm text-danger-strong">
      {{ error }}
    </p>
    <div class="flex flex-wrap items-end gap-3">
      <label class="min-w-0 flex-1 space-y-2 text-sm text-text-default"
        ><span>{{ tr("projectSearch") }}</span
        ><input
          v-model="search"
          class="w-full rounded-lg border border-input-border bg-input-bg px-3 py-2 text-input-text"
          type="search"
          @input="scheduleProjects" /></label
      ><BaseDropdown :items="projectItems" align="left"
        ><template #trigger
          ><BaseButton variant="secondary">{{
            tr("selectProject")
          }}</BaseButton></template
        ></BaseDropdown
      >
    </div>
    <Workspace
      v-if="projectId"
      :key="projectId"
      :api="api"
      :can-consent="false"
      :initial-request="route.query.request || ''"
    />
    <template v-else>
      <div class="flex flex-wrap items-end gap-3">
        <label class="min-w-0 flex-1 space-y-2 text-sm text-text-default"
          ><span>{{ tr("search") }}</span
          ><input
            v-model="queueSearch"
            class="w-full rounded-lg border border-input-border bg-input-bg px-3 py-2 text-input-text"
            type="search"
            @input="scheduleQueue" /></label
        ><BaseDropdown :items="stateItems"
          ><template #trigger
            ><BaseButton variant="secondary">{{
              filter ? tr(filter) : tr("requests")
            }}</BaseButton></template
          ></BaseDropdown
        >
      </div>
      <p v-if="queue && !queue.results.length" class="text-sm text-text-muted">
        {{ tr("emptyRequests") }}
      </p>
      <ul v-if="queue" class="space-y-3">
        <li
          v-for="row in queue.results"
          :key="row.id"
          class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border-default bg-surface p-4"
        >
          <div>
            <p class="font-semibold text-text-default">{{ row.title }}</p>
            <p class="text-sm text-text-muted">
              {{ row.project_name }} · {{ tr(row.status) }}
            </p>
          </div>
          <BaseButton
            as="NuxtLink"
            :to="
              localePath({
                path: '/panel/requirement-packages',
                query: { project: row.project_id, request: row.id },
              })
            "
            variant="secondary"
            >{{ tr("detail") }}</BaseButton
          >
        </li>
      </ul>
      <div class="flex gap-3">
        <BaseButton v-if="offset" variant="secondary" @click="page(-20)">{{
          tr("previous")
        }}</BaseButton
        ><BaseButton
          v-if="queue && queue.count > offset + 20"
          variant="secondary"
          @click="page(20)"
          >{{ tr("more") }}</BaseButton
        >
      </div>
      <ExampleEditor :api="api" :language="language" global-only />
    </template>
  </div>
</template>
