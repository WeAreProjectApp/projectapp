export default defineNuxtRouteMiddleware((to) => {
  // Redirect before mounting a page inside the out-in transition's Suspense.
  const path = to.path.replace(
    /^\/(en-us\/|es-co\/)?panel\/proposals\/email-deliverability\/?$/,
    (_match, locale) => `/${locale || 'es-co/'}panel/emails`,
  );
  if (path === to.path) return;
  return navigateTo(
    { path, query: { tab: 'status' } },
    { replace: true, redirectCode: 301 },
  );
});
