/**
 * PA-211 proposal-reader counterpart for the global editorial color rule.
 *
 * The public executive-summary reader uses useLinkify(), whose extended
 * Markdown branch renders the .editorial-rendered surface covered by CSS.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PROPOSAL_VIEW } from '../helpers/flow-tags.js';

const UUID = '74111111-1111-4111-8111-211000000006';
const editorialSource = '<p>QA006 texto <span style="color: rgb(255, 0, 0);"><strong><em><s><u><mark style="background-color: rgb(255, 255, 0);">prueba</mark></u></s></em></strong></span></p>';

const proposal = {
  id: 741,
  uuid: UUID,
  title: 'Lector editorial PA-211',
  client_name: 'Cliente lector',
  client_email: 'lector@example.com',
  language: 'es',
  status: 'sent',
  total_investment: '10000000',
  currency: 'COP',
  view_count: 1,
  expires_at: null,
  requirement_groups: [],
  sections: [
    {
      id: 1,
      section_type: 'greeting',
      title: 'Bienvenido',
      order: 0,
      is_enabled: true,
      content_json: { clientName: 'Cliente lector', inspirationalQuote: 'Una prueba verificable.' },
    },
    {
      id: 2,
      section_type: 'executive_summary',
      title: 'Resumen editorial',
      order: 1,
      is_enabled: true,
      content_json: {
        index: '1',
        title: 'Resumen editorial',
        paragraphs: [editorialSource],
        highlightsTitle: 'Incluye',
        highlights: [],
        text_formats: { '/paragraphs/0': 'markdown_html_v1' },
      },
    },
  ],
};

async function openReader(page) {
  await page.addInitScript(() => localStorage.setItem('proposal_onboarding_seen', 'true'));
  await mockApi(page, async ({ apiPath }) => {
    if (apiPath === `proposals/${UUID}/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(proposal) };
    }
    if (apiPath === `proposals/${UUID}/record-view/`) {
      return { status: 200, contentType: 'application/json', body: '{}' };
    }
    return null;
  });
  await page.goto(`/proposal/${UUID}?mode=detailed`, { waitUntil: 'domcontentloaded' });
  await page.getByTestId('nav-next').click();
}

test.describe('Proposal editorial reader foreground', () => {
  test.setTimeout(60_000);

  // Bug caught: .editorial-rendered could render a highlighted red source span with mark's black foreground.
  test('keeps red foreground in the proposal reader', {
    tag: [...PROPOSAL_VIEW, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the emailed proposal permalink is the documented reader entry; the test then uses panel navigation to reach editorial content)
    await openReader(page);

    const text = page.getByText('prueba', { exact: true });
    await expect(text).toHaveCSS('color', 'rgb(255, 0, 0)');
    await expect(text).toHaveCSS('background-color', 'rgb(255, 255, 0)');
    await expect(page.getByRole('heading', { name: 'Resumen editorial', level: 2 })).toHaveText('Resumen editorial');
  });
});
