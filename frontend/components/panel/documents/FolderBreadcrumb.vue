<template>
  <SharedFolderBreadcrumb v-bind="$attrs" :adapter="folderStore" v-on="forwarded" />
</template>
<script setup>
import SharedFolderBreadcrumb from '~/components/panel/FolderBreadcrumb.vue';
defineOptions({ inheritAttrs: false });
const emit = defineEmits(['select', 'nest']);
const forwarded = Object.fromEntries(['select', 'nest'].map(event => [event, value => emit(event, value)]));
const folderStore = useDocumentFolderStore();
</script>
