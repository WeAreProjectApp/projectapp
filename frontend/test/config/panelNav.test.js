/**
 * Tests for the panel navigation config.
 *
 * Covers: the "Contenido ProjectApp" section (renamed from "Website content")
 * and its LinkedIn module entry. Sidebar labels are Spanish by convention.
 */
import { getPanelNavSections } from '../../config/panelNav';

const identityLocalePath = (path) => path;

describe('getPanelNavSections', () => {
  it('shows a writing icon for the proposals module', () => {
    const sections = getPanelNavSections(identityLocalePath);
    const proposals = sections.find(section => section.id === 'commercial').items.find(item => item.href === '/panel/proposals');
    expect(proposals.icon).toBe('writing');
  });

  it('names the site section Contenido ProjectApp', () => {
    const sections = getPanelNavSections(identityLocalePath);
    const site = sections.find((s) => s.id === 'site');

    expect(site).toBeDefined();
    expect(site.label).toBe('Contenido ProjectApp');
  });

  it('includes the LinkedIn module in the site section', () => {
    const sections = getPanelNavSections(identityLocalePath);
    const site = sections.find((s) => s.id === 'site');
    const linkedin = site.items.find((i) => i.label === 'LinkedIn');

    expect(linkedin).toBeDefined();
    expect(linkedin.href).toBe('/panel/linkedin');
    expect(linkedin.icon).toBe('linkedin');
  });

  it('no section uses the old Website content label', () => {
    const sections = getPanelNavSections(identityLocalePath);

    expect(sections.map((s) => s.label)).not.toContain('Website content');
    expect(sections.map((s) => s.label)).toContain('Contenido ProjectApp');
  });

  it('groups customer communication tools under Comunicaciones', () => {
    const sections = getPanelNavSections(identityLocalePath);
    const communications = sections.find((s) => s.id === 'communications');

    expect(communications.label).toBe('Comunicaciones');
    expect(communications.items).toEqual(expect.arrayContaining([
      expect.objectContaining({ label: 'Hilos con clientes', href: '/panel/communications' }),
      expect.objectContaining({ label: 'Enviar emails', href: '/panel/emails' }),
    ]));
  });

  it('offers collection accounts instead of ads in accounting quick access', () => {
    const accounting = getPanelNavSections(identityLocalePath)
      .find((section) => section.id === 'accounting');
    const links = accounting.items.filter((item) => !item.divider);

    expect(links).toEqual(expect.arrayContaining([
      expect.objectContaining({
        label: 'Cuentas de cobro',
        href: '/panel/accounting/collections',
        icon: 'file',
      }),
    ]));
    expect(links.map((item) => item.label)).not.toContain('Ads');
  });

  it('splits commercial work, offerings, and programs into ordered menu sections', () => {
    // Fails if a new commercial item is put back into the wrong menu section or a visual grouping is lost.
    const sections = getPanelNavSections(identityLocalePath);
    const [commercial, offerings, programs] = ['commercial', 'offerings', 'programs']
      .map((id) => sections.find((section) => section.id === id));

    expect(sections.slice(
      sections.indexOf(commercial),
      sections.indexOf(programs) + 1,
    ).map((section) => section.id)).toEqual(['commercial', 'offerings', 'programs']);
    expect(commercial.items).toEqual([
      { label: 'Clientes', href: '/panel/clients', icon: 'users' },
      { divider: true },
      { label: 'Propuestas', href: '/panel/proposals', icon: 'writing' },
      { label: 'Nueva propuesta', href: '/panel/proposals/create', icon: 'plus' },
      { label: 'Diagnósticos', href: '/panel/diagnostics', icon: 'file' },
      { label: 'Nuevo diagnóstico', href: '/panel/diagnostics/create', icon: 'plus' },
      { label: 'Consultoría y asesoría', href: '/panel/consulting', icon: 'search' },
      { divider: true },
      { label: 'Defaults', href: '/panel/defaults', icon: 'settings' },
      { label: 'Entregabilidad email', href: '/panel/proposals/email-deliverability', icon: 'mail' },
    ]);
    expect(offerings.items).toEqual([
      { label: 'Paquetes de requerimientos', href: '/panel/hour-packages', icon: 'package' },
      { label: 'Módulos adicionales', href: '/panel/additional-modules', icon: 'puzzle' },
    ]);
    expect(programs.items).toEqual([
      { label: 'Programa de Alianza', href: '/panel/partnership-program', icon: 'credit-card' },
      { label: 'Building with Us', href: '/panel/building-with-us', icon: 'handshake' },
      { divider: true },
      { label: 'Células', href: '/panel/cells', icon: 'team' },
    ]);
  });

  it('preserves locale-prefixed links in every segmented commercial section', () => {
    // Fails if moving an item into its new section bypasses the localized panel URL.
    const sections = getPanelNavSections(
      (path) => `/en-us${path}`,
      { includeSuperuserOnly: false },
    );

    expect(['commercial', 'offerings', 'programs'].map((id) => {
      const section = sections.find((candidate) => candidate.id === id);
      return section.items.filter((item) => !item.divider).map((item) => item.href);
    })).toEqual([
      [
        '/en-us/panel/clients',
        '/en-us/panel/proposals',
        '/en-us/panel/proposals/create',
        '/en-us/panel/diagnostics',
        '/en-us/panel/diagnostics/create',
        '/en-us/panel/consulting',
        '/en-us/panel/defaults',
        '/en-us/panel/proposals/email-deliverability',
      ],
      ['/en-us/panel/hour-packages', '/en-us/panel/additional-modules'],
      [
        '/en-us/panel/partnership-program',
        '/en-us/panel/building-with-us',
        '/en-us/panel/cells',
      ],
    ]);
  });

  describe('Plataforma section', () => {
    it('lives after Contabilidad so the hostings breadcrumb keeps resolving there', () => {
      const sections = getPanelNavSections(identityLocalePath);
      const ids = sections.map((s) => s.id);

      expect(ids.indexOf('platform')).toBeGreaterThan(ids.indexOf('accounting'));
    });

    it('offers Proyectos to every admin', () => {
      const sections = getPanelNavSections(
        identityLocalePath, { includeSuperuserOnly: false },
      );
      const platform = sections.find((s) => s.id === 'platform');
      const projects = platform.items.find((i) => i.label === 'Proyectos');

      expect(projects).toBeDefined();
      expect(projects.href).toBe('/panel/projects');
      expect(projects.icon).toBe('folder');
    });

    it('shows the doubled Hostings entry only to superusers', () => {
      const withSuperuser = getPanelNavSections(identityLocalePath)
        .find((s) => s.id === 'platform');
      const withoutSuperuser = getPanelNavSections(
        identityLocalePath, { includeSuperuserOnly: false },
      ).find((s) => s.id === 'platform');

      expect(withSuperuser.items.map((i) => i.label)).toContain('Hostings');
      expect(withoutSuperuser.items.map((i) => i.label)).not.toContain('Hostings');
    });
  });
});
