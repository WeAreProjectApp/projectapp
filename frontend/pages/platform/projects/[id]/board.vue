<script setup>
definePageMeta({ layout: false, middleware: ['platform-auth'] })
const route = useRoute()
const localePath = useLocalePath()
await navigateTo(localePath(`/platform/projects/${route.params.id}/delivery`), { replace: true, redirectCode: 301 })
</script>
