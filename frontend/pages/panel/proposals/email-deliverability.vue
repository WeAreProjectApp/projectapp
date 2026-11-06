<script setup>
definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });
const localePath = useLocalePath();
await navigateTo({ path: localePath('/panel/emails'), query: { tab: 'status' } }, { replace: true, redirectCode: 301 });
</script>
