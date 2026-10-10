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

  it('gives additional modules a dedicated puzzle icon', () => {
    const commercial = getPanelNavSections(identityLocalePath)
      .find((section) => section.id === 'commercial');
    const modules = commercial.items.find((item) => item.label === 'Módulos adicionales');

    expect(modules.icon).toBe('puzzle');
  });

  it('places the partnership program immediately after additional modules', () => {
    const commercial = getPanelNavSections(identityLocalePath)
      .find((section) => section.id === 'commercial');
    const labels = commercial.items.filter((item) => !item.divider).map((item) => item.label);

    expect(labels.indexOf('Programa de Alianza')).toBe(labels.indexOf('Módulos adicionales') + 1);
  });

  it('places Building with Us immediately after the partnership program', () => {
    const commercial = getPanelNavSections(identityLocalePath)
      .find((section) => section.id === 'commercial');
    const partnershipIndex = commercial.items.findIndex((item) => item.label === 'Programa de Alianza');

    expect(commercial.items[partnershipIndex + 1]).toEqual({
      label: 'Building with Us', href: '/panel/building-with-us', icon: 'handshake',
    });
    expect(commercial.items[partnershipIndex + 2]).toEqual({ divider: true });
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
