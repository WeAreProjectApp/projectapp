<script setup>
definePageMeta({
  layout: false,
  middleware: ['platform-auth'],
})

const localePath = useLocalePath()
await navigateTo(localePath('/platform/projects'))
</script>
