<template>
  <SharedFolderSidebar v-bind="$attrs" :adapter="folderStore" v-on="forwarded" />
</template>
<script setup>
import SharedFolderSidebar from '~/components/panel/FolderSidebar.vue';
defineOptions({ inheritAttrs: false });
const emit = defineEmits(['select', 'manage', 'folder-drop', 'edit', 'delete', 'archive', 'view-archived', 'toggle-archived', 'toggle-inactive-projects', 'update:navigation-mode', 'select-entity', 'retry-navigation']);
const forwarded = Object.fromEntries(['select', 'manage', 'folder-drop', 'edit', 'delete', 'archive', 'view-archived', 'toggle-archived', 'toggle-inactive-projects', 'update:navigation-mode', 'select-entity', 'retry-navigation'].map(event => [event, value => emit(event, value)]));
const folderStore = useDocumentFolderStore();
</script>
