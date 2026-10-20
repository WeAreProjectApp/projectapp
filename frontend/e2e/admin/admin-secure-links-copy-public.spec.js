import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
import { json, secureLinkRow, secureLinkTypes } from '../helpers/secure-links.js';
import { PANEL_VIEWPORTS, viewportUse } from '../helpers/viewports.js';

test.setTimeout(60_000);

const publicCreateUrl = 'https://projectapp.example/es-co/secure-link?source=client';
const row = secureLinkRow();
const tags = ['@flow:admin-secure-link-manage', '@role:admin'];

async function openWorkspace(page, locale = 'es-co') {
  await page.clock.install({ time: '2026-10-19T12:00:00Z' });
  await setAuthLocalStorage(page, {
    token: 'secure-links-copy-token',
    userAuth: { id: 8901, role: 'admin', is_staff: true },
  });
  await mockApi(page, ({ apiPath }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true } });
    if (apiPath === 'panel/dashboard/') return json({ finance: null, proposals: {}, additional_modules: {}, operations: {}, attention: [] });
    if (apiPath === 'secure-links/public/types/') return json({ types: secureLinkTypes });
    if (apiPath === 'secure-links/') return json({
      results: [row], count: 1, page: 1, page_size: 25,
      counts: { all: 1 }, lifecycle_counts: { all: 1, ready: 1 },
      unopened_received: 0, public_create_url: publicCreateUrl,
    });
    return null;
  });
  // quality: allow-deep-link (this focused regression exercises the header's copy action on its owning list)
  await page.goto(`/${locale}/panel/secure-links`, { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  await expect(page.getByTestId(`secure-link-row-${row.id}`).filter({ visible: true })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  // Keep the two-second result available while measuring on a busy runner.
  await page.clock.pauseAt('2026-10-19T12:05:00Z');
}

const copyButton = (page) => page.getByTestId('secure-links-copy-public');
const status = (page) => page.getByTestId('secure-links-copy-status');

function layoutTargets(page) {
  return [
    copyButton(page), page.getByTestId('secure-links-new'),
    page.getByTestId('secure-links-description'), page.getByTestId('secure-links-header'),
    page.getByTestId('secure-links-tabs'),
    page.getByTestId(`secure-link-row-${row.id}`).filter({ visible: true }),
  ];
}

async function measureLayout(page) {
  return Promise.all(layoutTargets(page).map(async (locator) => {
    const box = await locator.boundingBox();
    expect(box).not.toBeNull();
    return box;
  }));
}

async function expectUnmoved(page, before) {
  const after = await measureLayout(page);
  const differences = after.flatMap((box, index) => (
    ['x', 'y', 'width', 'height'].map((key) => Math.abs(box[key] - before[index][key]))
  ));
  expect(Math.max(...differences), 'Copy feedback must not move or resize the header or list').toBeLessThanOrEqual(1);
  expect(await page.evaluate(() => (
    Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - document.documentElement.clientWidth
  ))).toBeLessThanOrEqual(1);
}

for (const profile of Object.keys(PANEL_VIEWPORTS)) {
  test.describe(`public link copy · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));

    // Bug caught: the longer success label wrapped New link and pushed the list down.
    test('keeps the header stationary while confirming a copied client link', {
      tag: [...tags, '@outcome:success', '@outcome:display'],
    }, async ({ page, context }) => {
      // quality: allow-deep-link (this regression exercises copying from the header rather than sidebar navigation)
      await context.grantPermissions(['clipboard-read', 'clipboard-write']);
      await openWorkspace(page);
      const before = await measureLayout(page);
      expect(Math.abs(before[0].y - before[1].y)).toBeLessThanOrEqual(1);

      await copyButton(page).click();

      await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe(publicCreateUrl);
      await expect(copyButton(page)).toHaveText('Enlace para clientes');
      await expect(copyButton(page)).toHaveAccessibleName('Enlace para clientes');
      await expect(copyButton(page)).toHaveAttribute('data-displayed-action', 'complete');
      await expect(page.getByRole('tooltip')).toHaveText('Copiado');
      await expect(status(page)).toHaveText('Copiado');
      await expectUnmoved(page, before);
      await page.clock.fastForward(2_001);
      await expect(status(page)).toBeEmpty();
      await expect(copyButton(page)).toHaveAttribute('data-displayed-action', 'copy');
      await page.clock.resume();
      await expect(page.getByRole('tooltip')).toBeHidden();
      await expectUnmoved(page, before);
    });
  });
}

test.describe('public link clipboard states', () => {
  test.use(viewportUse('desktop'));

  test('waits for the clipboard to confirm success', {
    tag: [...tags, '@outcome:success'],
  }, async ({ page }) => {
    await openWorkspace(page);
    await page.evaluate(() => {
      Object.defineProperty(navigator.clipboard, 'writeText', {
        configurable: true,
        value: () => new Promise((resolve) => { window.finishClipboardWrite = resolve; }),
      });
    });
    const before = await measureLayout(page);

    await copyButton(page).click();

    await expect(copyButton(page)).toHaveAttribute('data-displayed-action', 'copy');
    await expect(status(page)).toBeEmpty();
    await expect(page.getByRole('tooltip')).toBeHidden();
    await expectUnmoved(page, before);
    await page.evaluate(() => window.finishClipboardWrite());
    await expect(copyButton(page)).toHaveAttribute('data-displayed-action', 'complete');
    await expect(status(page)).toHaveText('Copiado');
  });

  test('keeps the header stationary when clipboard access fails', {
    tag: [...tags, '@outcome:failure', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (this regression measures the header after a failed clipboard interaction)
    await openWorkspace(page);
    await page.evaluate(() => {
      Object.defineProperty(navigator.clipboard, 'writeText', {
        configurable: true, value: () => Promise.reject(new Error('Clipboard denied')),
      });
    });
    const before = await measureLayout(page);

    await copyButton(page).click();

    await expect(page.getByRole('tooltip')).toHaveText('No se pudo copiar');
    await expect(status(page)).toHaveText('No se pudo copiar');
    await expect(copyButton(page)).toHaveAttribute('data-displayed-action', 'copy');
    await expect(copyButton(page)).toHaveText('Enlace para clientes');
    await expectUnmoved(page, before);
    await page.clock.fastForward(3_001);
    await expect(status(page)).toBeEmpty();
    await expectUnmoved(page, before);
  });

  test('permits a successful retry after clipboard access fails', {
    tag: [...tags, '@outcome:success'],
  }, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await openWorkspace(page);
    await page.evaluate(() => {
      Object.defineProperty(navigator.clipboard, 'writeText', {
        configurable: true, value: () => Promise.reject(new Error('Clipboard denied')),
      });
    });
    await copyButton(page).click();
    await expect(status(page)).toHaveText('No se pudo copiar');
    await page.evaluate(() => { delete navigator.clipboard.writeText; });

    await copyButton(page).click();

    await expect(status(page)).toHaveText('Copiado');
    await expect(copyButton(page)).toHaveAttribute('data-displayed-action', 'complete');
    await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe(publicCreateUrl);
  });

  test('renews confirmation after repeated activation', {
    tag: [...tags, '@outcome:success'],
  }, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await openWorkspace(page);
    await page.evaluate(() => {
      const writeText = navigator.clipboard.writeText.bind(navigator.clipboard);
      window.clipboardWrites = 0;
      Object.defineProperty(navigator.clipboard, 'writeText', {
        configurable: true,
        value: async (text) => {
          await writeText(text);
          window.clipboardWrites += 1;
        },
      });
    });
    await copyButton(page).click();
    await expect.poll(() => page.evaluate(() => window.clipboardWrites)).toBe(1);
    await expect(status(page)).toHaveText('Copiado');
    await page.clock.fastForward(1_500);

    await copyButton(page).click();

    await expect.poll(() => page.evaluate(() => window.clipboardWrites)).toBe(2);
    await expect(status(page)).toHaveText('Copiado');
    await page.clock.fastForward(1_000);
    await expect(copyButton(page)).toHaveAttribute('data-displayed-action', 'complete');
    await page.clock.fastForward(1_001);
    await expect(status(page)).toBeEmpty();
    await expect(copyButton(page)).toHaveAttribute('data-displayed-action', 'copy');
  });

  test('confirms a keyboard copy without moving focus', {
    tag: [...tags, '@outcome:success'],
  }, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await openWorkspace(page);
    await copyButton(page).focus();

    await copyButton(page).press('Enter');

    await expect(status(page)).toHaveText('Copiado');
    await expect(copyButton(page)).toBeFocused();
    await expect(copyButton(page)).toHaveAccessibleDescription('Copiado');
    await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe(publicCreateUrl);
  });

  test('confirms copying in English with a stable button label', {
    tag: [...tags, '@outcome:success'],
  }, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await openWorkspace(page, 'en-us');
    const before = await measureLayout(page);

    await copyButton(page).click();

    await expect(copyButton(page)).toHaveText('Client link');
    await expect(page.getByRole('tooltip')).toHaveText('Copied');
    await expectUnmoved(page, before);
  });

  test('confirms copying with reduced motion', {
    tag: [...tags, '@outcome:success', '@outcome:display'],
  }, async ({ page, context }) => {
    // quality: allow-deep-link (this regression exercises copying with the operating system motion preference)
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await openWorkspace(page);
    const before = await measureLayout(page);

    await copyButton(page).click();

    await expect(copyButton(page)).toHaveAttribute('data-displayed-action', 'complete');
    await expect(page.getByRole('tooltip')).toHaveText('Copiado');
    await expectUnmoved(page, before);
  });
});
