import { expect } from '@playwright/test'

/** Google is the sole simulated boundary; the app still submits real tokens. */
export async function mockCaptchaProvider(page, testId, { mode = 'valid', failScript = false } = {}) {
  await page.route('https://www.google.com/recaptcha/api.js*', async (route) => {
    if (failScript) return route.abort('failed')
    const callback = new URL(route.request().url()).searchParams.get('onload')
    await route.fulfill({
      contentType: 'application/javascript',
      body: `(() => {
        let counter = 0;
        const widgets = [];
        window.grecaptcha = {
          render(container, options) {
            const target = typeof container === 'string' ? document.getElementById(container) : container;
            const label = document.createElement('label');
            const box = document.createElement('input');
            box.type = 'checkbox';
            label.append(box, 'No soy un robot (prueba)');
            const token = document.createElement('input');
            token.type = 'hidden'; token.name = 'g-recaptcha-response';
            const expire = document.createElement('button');
            expire.type = 'button'; expire.textContent = 'Expirar verificación (prueba)';
            expire.onclick = () => { box.checked = false; token.value = ''; options['expired-callback'](); };
            box.onchange = () => {
              token.value = ${JSON.stringify(`${mode}-${testId}-`)} + (++counter);
              options.callback(token.value);
            };
            target.append(label, token, expire);
            widgets.push({box, token}); return widgets.length - 1;
          },
          reset(id) { widgets[id].box.checked = false; widgets[id].token.value = ''; }
        };
        window[${JSON.stringify(callback)}]();
      })();`,
    })
  })
}

export const captchaCredentials = {
  email: 'browser-captcha@example.com',
  password: 'Browser-test-password-1',
}

export async function prepareLocallyDeliveredCode(page, surface) {
  const form = page.getByRole('region', { name: 'Otras formas de iniciar sesión' })
  await form.getByRole('tab', { name: 'Código por correo' }).click()
  const email = form.getByRole('textbox', { name: 'Correo electrónico', exact: true })
  await email.focus()
  await expect(email).toBeFocused()
  expect(await email.evaluate(input => input.labels[0]?.control === input)).toBe(true)
  await form.getByRole('checkbox', { name: 'No soy un robot (prueba)' }).check()
  await email.fill('correo-invalido')
  const requestCode = form.getByRole('button', { name: 'Enviar código' })
  await expect(requestCode).toBeDisabled()
  await email.fill(`browser-${surface}-code@example.test`)
  await requestCode.click()

  const codeInput = form.getByRole('textbox', { name: 'Código de acceso', exact: true })
  await codeInput.focus()
  await expect(codeInput).toBeFocused()
  expect(await codeInput.evaluate(input => input.labels[0]?.control === input)).toBe(true)
  const verify = form.getByRole('button', { name: 'Verificar e iniciar sesión' })
  await codeInput.fill('12345')
  await expect(verify).toBeDisabled()
  const message = await page.request.post(`http://127.0.0.1:3198/__captcha_mailbox__/${surface}`)
  expect(message.ok()).toBe(true)
  const { code } = await message.json()
  expect(/^[0-9]{6}$/.test(code)).toBe(true)
  await codeInput.fill(code)
  await expect(verify).toBeEnabled()
  return verify
}
