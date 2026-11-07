/** PA-245: active secondary values must be readable without hover. */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setPlatformAuth, mockPlatformClient } from '../helpers/platform-auth.js';
import { viewportUse } from '../helpers/viewports.js';

test.setTimeout(60_000);

const PROJECT = {
  id: 77, name: 'P'.repeat(177), client_id: mockPlatformClient.id,
  status: 'active', status_label: 'Activo', progress: 0,
  bugs_open_count: 0, changes_pending_count: 0, phases_total_amount: 0,
  last_activity_at: '2026-11-06T12:00:00Z',
};
const enterProjects = {
  compact: async page => {
    await page.getByRole('button', { name: 'Abrir navegación' }).click();
    await page.getByRole('link', { name: /^(Mis proyectos|Proyectos)$/ }).filter({ visible: true }).click();
  },
  portrait: page => page.getByRole('link', { name: /^(Mis proyectos|Proyectos)$/ }).filter({ visible: true }).click(),
  landscape: page => page.getByRole('link', { name: /^(Mis proyectos|Proyectos)$/ }).filter({ visible: true }).click(),
  desktop: page => page.getByRole('link', { name: /^(Mis proyectos|Proyectos)$/ }).filter({ visible: true }).click(),
  wide: page => page.getByRole('link', { name: /^(Mis proyectos|Proyectos)$/ }).filter({ visible: true }).click(),
};

async function contrast(locator) {
  return locator.evaluate(element => {
    const rgba = value => {
      const values = value.match(/[\d.]+/g).map(Number);
      return [...values.slice(0, 3), values[3] ?? 1];
    };
    const blend = (front, back) => front.slice(0, 3).map((channel, i) => channel * front[3] + back[i] * (1 - front[3]));
    const colors = [];
    for (let node = element; node; node = node.parentElement) colors.push(rgba(getComputedStyle(node).backgroundColor));
    const background = colors.reverse().reduce((back, front) => blend(front, back), [255, 255, 255]);
    const foreground = blend(rgba(getComputedStyle(element).color), background);
    const luminance = rgb => rgb.map(channel => {
      const value = channel / 255;
      return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
    }).reduce((sum, value, i) => sum + value * [0.2126, 0.7152, 0.0722][i], 0);
    const values = [luminance(foreground), luminance(background)].sort((a, b) => a - b);
    return (values[1] + 0.05) / (values[0] + 0.05);
  });
}

for (const profile of ['compact', 'portrait', 'landscape', 'desktop', 'wide']) {
  for (const theme of ['light', 'dark']) {
    test.describe(`${profile} ${theme}`, () => {
      test.use(viewportUse(profile));
      test('keeps secondary project values above minimum contrast', {
        tag: ['@flow:platform-project-list', '@outcome:display', `@viewport:${profile}`],
      }, async ({ page }) => {
        await page.clock.install({ time: new Date('2026-11-07T12:00:00Z') });
        await setPlatformAuth(page, { user: mockPlatformClient });
        await page.addInitScript(value => localStorage.setItem('platform_theme', value), theme);
        const writes = [];
        await mockApi(page, async ({ apiPath, method }) => {
          if (apiPath.startsWith('accounts/projects/') && method !== 'GET') writes.push(method);
          const json = body => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
          if (apiPath === 'accounts/me/') return json(mockPlatformClient);
          if (apiPath === 'accounts/projects/') return json([PROJECT]);
          return null;
        });
        // quality: allow-deep-link (authenticated Profile is the shell entry; reach the list through its navigation)
        await page.goto('/es-co/platform/profile', { waitUntil: 'domcontentloaded' });
        await enterProjects[profile](page);

        await expect.poll(() => page.locator('#platform-projects').evaluate(element => Boolean(element.closest('.dark')))).toBe(theme === 'dark');
        const activity = page.getByTestId('project-last-activity-77');
        await expect(activity).toHaveText('Ayer');
        await expect(page.getByTestId('project-bugs-77')).toHaveText('0');
        await expect(page.getByTestId('project-value-77')).toHaveText('—');
        expect(await contrast(activity)).toBeGreaterThanOrEqual(4.5);
        expect(await contrast(page.getByTestId('project-bugs-77'))).toBeGreaterThanOrEqual(4.5);
        expect(await contrast(page.getByTestId('project-value-77'))).toBeGreaterThanOrEqual(4.5);
        expect(writes).toEqual([]);
      });
    });
  }
}
