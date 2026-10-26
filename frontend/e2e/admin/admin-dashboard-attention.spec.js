import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { radarApi, radarRecord, radarTypes } from '../helpers/dashboard-attention-fixture.js';
import { ADMIN_DASHBOARD_ATTENTION_RADAR } from '../helpers/flow-tags.js';

test.setTimeout(60_000);
async function setup(page, options = {}) {
  await setAuthLocalStorage(page, { token: 'radar-token', userAuth: { id: 1, role: 'admin', is_staff: true, is_superuser: true } });
  await mockApi(page, radarApi(options));
  // quality: allow-deep-link (the Dashboard is the starting surface; every detail is reached by a real click)
  await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
}
async function openDetail(page, type) {
  await page.getByTestId(`attention-item-${type}`).click();
  await page.getByTestId(`radar-record-${type}-42`).click();
}
const destinationSelectors = {
  emails_failed: '[data-testid="email-history-record-42"]',
  recurring_due: '[data-testid="accounting-row-42"]',
  tasks_overdue: '[data-testid="task-title-input"]',
  documents_overdue: '[data-testid="doc-editor-title"]',
  proposals_stale: '[data-testid="proposal-record-header"]',
};
const destinationAssertions = Object.fromEntries(radarTypes.map((type) => [type, type === 'tasks_overdue' ? (record, title) => expect(record).toHaveValue(title) : (record, title) => expect(record).toContainText(title)]));
for (const type of radarTypes) {
  test(`opens the exact ${type} record from its detail`, { tag: [...ADMIN_DASHBOARD_ATTENTION_RADAR, '@role:admin', '@outcome:success'] }, async ({ page }) => {
    await setup(page);
    await openDetail(page, type);
    await expect(page.getByTestId('radar-detail-modal')).toContainText(radarRecord(type).title);
    await page.getByTestId('radar-detail-destination').click();
    await expect(page).toHaveURL(new RegExp(type === 'tasks_overdue' ? 'task=42' : type === 'emails_failed' ? 'email=42' : type === 'recurring_due' ? 'recurring=42' : '/42/edit'));
    const record = page.locator(destinationSelectors[type]);
    await expect(record).toBeVisible();
    await destinationAssertions[type](record, radarRecord(type).title);
  });
}
test('loads the sixth item inside the Dashboard', { tag: [...ADMIN_DASHBOARD_ATTENTION_RADAR, '@role:admin', '@outcome:success'] }, async ({ page }) => {
  await setup(page);
  await page.getByTestId('attention-item-emails_failed').click();
  await page.getByTestId('radar-more-emails_failed').click();
  await expect(page.getByTestId('radar-record-emails_failed-47')).toContainText('Pendiente emails_failed 47');
  await expect(page.getByTestId('radar-more-emails_failed')).toHaveCount(0);
});
test('recovers the accordion after a request failure', { tag: [...ADMIN_DASHBOARD_ATTENTION_RADAR, '@role:admin', '@outcome:failure'] }, async ({ page }) => {
  await setup(page, { failList: true });
  await page.getByTestId('attention-item-emails_failed').click();
  await expect(page.getByTestId('radar-records-emails_failed')).toContainText('No se pudieron cargar los elementos.');
  await page.getByTestId('radar-records-emails_failed').getByRole('button', { name: 'Reintentar', exact: true }).click();
  await expect(page.getByTestId('radar-record-emails_failed-42')).toContainText('Pendiente emails_failed 42');
});
test('explains a deleted record in the detail', { tag: [...ADMIN_DASHBOARD_ATTENTION_RADAR, '@role:admin', '@outcome:error'] }, async ({ page }) => {
  await setup(page, { missing: true });
  await openDetail(page, 'emails_failed');
  await expect(page.getByTestId('radar-detail-modal')).toContainText('ya no existe');
  await expect(page.getByTestId('radar-detail-destination')).toHaveCount(0);
});
test('explains denied access without offering navigation', { tag: [...ADMIN_DASHBOARD_ATTENTION_RADAR, '@role:admin', '@outcome:error'] }, async ({ page }) => {
  await setup(page, { forbidden: true });
  await openDetail(page, 'recurring_due');
  await expect(page.getByTestId('radar-detail-modal')).toContainText('No tienes permiso');
  await expect(page.getByTestId('radar-detail-destination')).toHaveCount(0);
});
for (const width of [412, 835, 1440]) {
  test(`keeps the radar detail usable at width ${width}`, { tag: [...ADMIN_DASHBOARD_ATTENTION_RADAR, '@role:admin', '@outcome:display'] }, async ({ page }) => {
    // quality: allow-deep-link (Dashboard is the application entry; the accordion and modal are reached through clicks)
    await page.setViewportSize({ width, height: 1000 });
    await setup(page);
    await openDetail(page, 'emails_failed');
    await expect(page.getByTestId('radar-detail-modal')).toContainText('cliente@example.test');
    await expect(page.getByTestId('radar-detail-destination')).toBeInViewport();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('radar-record-emails_failed-42')).toBeFocused();
  });
}
