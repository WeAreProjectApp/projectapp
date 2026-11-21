export async function fillContactForm(form, locale = 'en', email = 'test@example.com') {
  const labels = locale === 'en'
    ? ['Full name', 'Phone number', 'Your email', 'Tell us about your web project']
    : ['Nombre completo', 'Número de teléfono', 'Tu correo electrónico', 'Cuéntanos sobre tu proyecto web'];
  await form.getByRole('textbox', { name: labels[0], exact: true }).fill('Test User');
  await form.getByRole('textbox', { name: labels[1], exact: true }).fill('+573001234567');
  await form.getByRole('textbox', { name: labels[2], exact: true }).fill(email);
  await form.getByRole('textbox', { name: labels[3], exact: true }).fill('E2E contact project description');
  await form.getByRole('button', { name: '500-5K', exact: true }).click();
}
