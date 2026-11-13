/**
 * E2E tests for the functional requirements detail modal in the proposal viewer.
 *
 * Covers: clicking a requirement group card opens modal with items,
 * closing modal, navigating between groups.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PROPOSAL_FUNCTIONAL_REQUIREMENTS_MODAL } from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const MOCK_UUID = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';

const mockProposal = {
  id: 1,
  uuid: MOCK_UUID,
  title: 'Requirements Modal Test',
  client_name: 'Test Client',
  status: 'sent',
  language: 'es',
  total_investment: '5000000',
  currency: 'COP',
  sections: [
    {
      id: 1,
      section_type: 'greeting',
      title: '👋 Bienvenido',
      order: 0,
      is_enabled: true,
      content_json: { clientName: 'Test Client', inspirationalQuote: '' },
    },
    {
      id: 2,
      section_type: 'functional_requirements',
      title: '📋 Requerimientos',
      order: 1,
      is_enabled: true,
      content_json: {
        index: '2',
        title: 'Requerimientos funcionales',
        intro: 'A continuación se detallan los requerimientos.',
        groups: [
          {
            id: 'views',
            icon: '🖥️',
            title: 'Vistas',
            description: 'Páginas principales del sitio.',
            items: [
              { icon: '🏠', name: 'Home', description: 'Página principal con hero y servicios' },
              { icon: '📞', name: 'Contacto', description: 'Formulario de contacto' },
            ],
          },
          {
            id: 'components',
            icon: '🧩',
            title: 'Componentes',
            description: 'Elementos reutilizables.',
            items: [
              { icon: '📱', name: 'Navbar', description: 'Barra de navegación responsive' },
            ],
          },
          {
            id: 'features',
            icon: '⚙️',
            title: 'Funcionalidades Específicas',
            description: 'Comportamientos propios del negocio.',
            items: [
              { icon: '🔎', name: 'Búsqueda', description: 'Búsqueda por criterios del negocio' },
            ],
          },
          {
            id: 'cross_cutting_features',
            icon: '🔗',
            title: 'Funcionalidades Transversales',
            description: 'Calidades que atraviesan las experiencias del proyecto.',
            items: [
              { icon: '📱', name: 'Diseño Responsive', description: 'Experiencia adaptada a los dispositivos priorizados' },
            ],
          },
        ],
        additionalModules: [],
      },
    },
  ],
  requirement_groups: [],
};

async function navigateToRequirements(page) {
  await page.goto(`/proposal/${MOCK_UUID}?mode=detailed`);

  const nextBtn = page.getByTestId('nav-next');
  await expect(nextBtn).toBeVisible({ timeout: 15000 });
  await nextBtn.click();

  await expect(page.getByText('Requerimientos funcionales')).toBeVisible({ timeout: 5000 });
}

test.describe('Proposal Functional Requirements Modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript((_uuid) => {
      localStorage.setItem('proposal_onboarding_seen', 'true');
      localStorage.setItem(`requirements_onboarding_seen_${_uuid}`, 'true');
    }, MOCK_UUID);
  });

  test('clicking a group card opens detail modal with items', {
    tag: [...PROPOSAL_FUNCTIONAL_REQUIREMENTS_MODAL, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === `proposals/${MOCK_UUID}/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposal) };
      }
      return null;
    });

    // quality: allow-deep-link (the shared proposal permalink is the guest's
    // documented entry point; this test then exercises the requirement cards)
    await navigateToRequirements(page);

    // The four core group cards should be visible
    await expect(page.getByText('Vistas')).toBeVisible();
    await expect(page.getByText('Componentes')).toBeVisible();
    await expect(page.getByText('Funcionalidades Específicas')).toBeVisible();
    await expect(page.getByText('Funcionalidades Transversales')).toBeVisible();

    // Click the Vistas group card using the "Ver detalle" link inside it
    const vistasCard = page.getByText('Vistas').first();
    await vistasCard.click();

    // Modal should show group items
    await expect(page.getByText('Página principal con hero y servicios')).toBeVisible({ timeout: 3000 });
  });

  test('clicking a different group card shows its items', {
    tag: [...PROPOSAL_FUNCTIONAL_REQUIREMENTS_MODAL, '@role:guest'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === `proposals/${MOCK_UUID}/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposal) };
      }
      return null;
    });

    await navigateToRequirements(page);

    // Click the Componentes group card
    const componentesCard = page.getByText('Componentes').first();
    await componentesCard.click();

    // Modal should show Componentes items
    await expect(page.getByText('Navbar')).toBeVisible({ timeout: 3000 });
    await expect(page.getByText('Barra de navegación responsive')).toBeVisible();
  });

  test('cross-cutting card opens its contextual items', {
    tag: [...PROPOSAL_FUNCTIONAL_REQUIREMENTS_MODAL, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === `proposals/${MOCK_UUID}/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposal) };
      }
      return null;
    });

    // quality: allow-deep-link (the shared proposal permalink is the guest's
    // documented entry point; this test then exercises the requirement card)
    await navigateToRequirements(page);
    await page.getByText('Funcionalidades Transversales').first().click();

    await expect(page.getByText('Diseño Responsive')).toBeVisible({ timeout: 3000 });
    await expect(page.getByText('Experiencia adaptada a los dispositivos priorizados')).toBeVisible();
  });
});

// ── Item ↔ technical requirement traceability (nested modal) ────────────────

const mockProposalWithTech = {
  ...mockProposal,
  sections: [
    mockProposal.sections[0],
    {
      ...mockProposal.sections[1],
      content_json: {
        ...mockProposal.sections[1].content_json,
        groups: [
          {
            id: 'views',
            icon: '🖥️',
            title: 'Vistas',
            description: 'Páginas principales del sitio.',
            items: [
              { icon: '🏠', name: 'Home', description: 'Página principal con hero y servicios', id: 'item-views-home' },
              { icon: '📞', name: 'Contacto', description: 'Formulario de contacto', id: 'item-views-contacto' },
            ],
          },
        ],
      },
    },
    {
      id: 3,
      section_type: 'technical_document',
      title: '🔧 Detalle técnico',
      order: 2,
      is_enabled: true,
      content_json: {
        epics: [{
          epicKey: 'views',
          title: 'Vistas',
          description: 'Páginas del sitio.',
          requirements: [{
            flowKey: 'req-home',
            title: 'Home dinámico con secciones administrables',
            description: 'Hero, servicios y testimonios editables desde el panel.',
            configuration: 'Secciones persistidas con permisos de edición en el servidor.',
            usageFlow: 'Editar una sección → guardar → consultar la portada actualizada.',
            priority: 'high',
            linked_item_ids: ['item-views-home'],
          }, {
            flowKey: 'req-home-seo',
            title: 'SEO técnico y metadatos del Home',
            description: 'Metaetiquetas, Open Graph y datos estructurados de la página principal.',
            priority: 'medium',
            linked_item_ids: ['item-views-home'],
          }, {
            flowKey: 'req-home-estados',
            title: 'Estados vacío y de error del Home',
            description: 'Comportamiento de la portada sin contenido cargado y ante fallas.',
            priority: 'medium',
            linked_item_ids: ['item-views-home'],
          }, {
            flowKey: 'req-contacto-envio',
            title: 'Envío validado del formulario de contacto',
            description: 'Validación de campos y confirmación al enviar el mensaje.',
            priority: 'high',
            linked_item_ids: ['item-views-contacto'],
          }],
        }],
      },
    },
  ],
};

test.describe('Nested linked-requirements modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript((_uuid) => {
      localStorage.setItem('proposal_onboarding_seen', 'true');
      localStorage.setItem(`requirements_onboarding_seen_${_uuid}`, 'true');
    }, MOCK_UUID);
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === `proposals/${MOCK_UUID}/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposalWithTech) };
      }
      return null;
    });
  });

  test('opens the technical detail of a linked requirement', {
    tag: [...PROPOSAL_FUNCTIONAL_REQUIREMENTS_MODAL, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    // Bug caught: the item projection used to discard configuration and usage flow.
    await navigateToRequirements(page);
    await page.getByText('Vistas').first().click();
    await page.getByTestId('view-requirements-link').first().click();

    const first = page.getByTestId('linked-requirement').first();
    await expect(first.getByTestId('linked-requirement-configuration')).toContainText('Secciones persistidas con permisos de edición en el servidor.');
    await expect(first.getByTestId('linked-requirement-usage-flow')).toContainText('Editar una sección → guardar → consultar la portada actualizada.');
  });

  test('item with linked requirements shows link that opens the nested modal', {
    tag: [...PROPOSAL_FUNCTIONAL_REQUIREMENTS_MODAL, '@role:guest'],
  }, async ({ page }) => {
    await navigateToRequirements(page);

    await page.getByText('Vistas').first().click();
    await expect(page.getByText('Página principal con hero y servicios')).toBeVisible({ timeout: 3000 });

    // Each linked item shows its own count — variable per item, not uniform
    const links = page.getByTestId('view-requirements-link');
    await expect(links).toHaveCount(2);
    await expect(links.first()).toContainText('Ver requerimientos (3)');
    await expect(links.nth(1)).toContainText('Ver requerimientos (1)');

    await links.first().click();

    // Nested modal: one row per linked requirement, each with title +
    // priority badge + description
    const nested = page.getByTestId('linked-requirement');
    await expect(nested).toHaveCount(3);
    await expect(nested.first()).toContainText('Home dinámico con secciones administrables');
    await expect(nested.first()).toContainText('Alta');
    await expect(nested.first()).toContainText('Hero, servicios y testimonios editables desde el panel.');
    await expect(nested.nth(1)).toContainText('SEO técnico y metadatos del Home');
    await expect(nested.nth(1)).toContainText('Media');
    await expect(nested.nth(2)).toContainText('Estados vacío y de error del Home');
  });

  test('closing the nested modal keeps the group modal open', {
    tag: [...PROPOSAL_FUNCTIONAL_REQUIREMENTS_MODAL, '@role:guest'],
  }, async ({ page }) => {
    await navigateToRequirements(page);

    await page.getByText('Vistas').first().click();
    await page.getByTestId('view-requirements-link').first().click();
    await expect(page.getByTestId('linked-requirement').first()).toBeVisible({ timeout: 3000 });

    await page.getByRole('button', { name: 'Cerrar requerimientos vinculados' }).click();

    await expect(page.getByTestId('linked-requirement')).toHaveCount(0);
    await expect(page.getByText('Página principal con hero y servicios')).toBeVisible();
  });

  test('nested requirements link also works in executive mode', {
    tag: [...PROPOSAL_FUNCTIONAL_REQUIREMENTS_MODAL, '@role:guest'],
  }, async ({ page }) => {
    await page.goto(`/proposal/${MOCK_UUID}?mode=executive`);

    const nextBtn = page.getByTestId('nav-next');
    await expect(nextBtn).toBeVisible({ timeout: 15000 });
    await nextBtn.click();
    await expect(page.getByText('Requerimientos funcionales')).toBeVisible({ timeout: 5000 });

    await page.getByText('Vistas').first().click();
    await page.getByTestId('view-requirements-link').first().click();
    await expect(page.getByTestId('linked-requirement').first()).toContainText(
      'Home dinámico con secciones administrables', { timeout: 3000 },
    );
  });

  test('legacy proposal without item ids shows no requirements link', {
    tag: [...PROPOSAL_FUNCTIONAL_REQUIREMENTS_MODAL, '@role:guest'],
  }, async ({ page }) => {
    // Override with the legacy mock (items without ids, no technical doc)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === `proposals/${MOCK_UUID}/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposal) };
      }
      return null;
    });

    await navigateToRequirements(page);

    await page.getByText('Vistas').first().click();
    await expect(page.getByText('Página principal con hero y servicios')).toBeVisible({ timeout: 3000 });
    await expect(page.getByTestId('view-requirements-link')).toHaveCount(0);
  });
});
