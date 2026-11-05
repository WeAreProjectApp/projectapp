<template>
  <main class="flex min-h-screen items-center justify-center bg-surface-muted px-4 py-10">
    <div class="w-full max-w-md space-y-6 rounded-2xl border border-border-default bg-surface p-6 shadow-sm">
      <div><h1 class="text-2xl font-light text-text-default">Acceso al panel</h1><p class="mt-2 text-sm text-text-muted">Inicia sesión con una cuenta habilitada por el equipo.</p></div>
      <BaseButton as="a" :to="passwordUrl" variant="secondary" class="w-full">Entrar con contraseña</BaseButton>
      <AlternativeLogin surface="panel" :next="target" @authenticated="enterPanel" />
    </div>
  </main>
</template>
<script setup>
import { computed } from 'vue';
import AlternativeLogin from '~/components/auth/AlternativeLogin.vue';
definePageMeta({ layout: false });
useHead({ title: 'Acceso al panel — ProjectApp' });
const route = useRoute();
const target = computed(() => typeof route.query.next === 'string' ? route.query.next : '/panel/');
const passwordUrl = computed(() => `/admin/login/?next=${encodeURIComponent(target.value)}`);
function enterPanel(data) { window.location.assign(data.redirect); }
</script>
