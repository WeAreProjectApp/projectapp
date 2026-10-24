/**
 * Tests for sectionEditorUtils — value_added conditions + commercial_conditions
 * roundtrip (Req 3 + Req 1/2 panel editing).
 */
import {
  buildFormFromJson,
  formToJson,
} from '../../components/BusinessProposal/admin/sectionEditorUtils.js';

describe('value_added_modules conditions roundtrip', () => {
  const json = {
    index: '11',
    title: 'Incluido',
    intro: 'intro',
    module_ids: ['ai_automation_module'],
    justifications: { ai_automation_module: 'j' },
    conditions: {
      ai_automation_module: {
        min_price_usd: 2900,
        min_price_cop: 10400000,
        duration_months: 6,
        discretionary_note: 'si aplica',
        terms: 'Depende del asistente.',
      },
    },
    footer_note: 'nota',
  };

  it('buildFormFromJson keeps conditions for referenced ids', () => {
    const form = buildFormFromJson(json, 'value_added_modules', {});
    expect(form.conditions.ai_automation_module.duration_months).toBe(6);
    expect(form.conditions.ai_automation_module.terms).toBe('Depende del asistente.');
  });

  it('formToJson serializes non-empty conditions and prunes empty ones', () => {
    const form = buildFormFromJson(json, 'value_added_modules', {});
    // Add an empty condition for a second id → should be pruned.
    form.module_ids.push('admin_module');
    form.conditions.admin_module = {
      min_price_usd: null, min_price_cop: null, duration_months: null,
      discretionary_note: '', terms: '',
    };
    const out = formToJson(form, 'value_added_modules');
    expect(out.conditions.ai_automation_module.min_price_cop).toBe(10400000);
    expect(out.conditions.admin_module).toBeUndefined();
  });
});

describe('commercial_conditions roundtrip', () => {
  const json = {
    index: '17',
    title: 'Condiciones comerciales',
    packagesTitle: 'Paquetes',
    packagesIntro: 'intro',
    hourlyRate: 90000,
    currency: 'COP',
    packages: [
      { name: 'Ágil', hours: 20, discountPercent: 0, note: 'x' },
      { name: 'Pro', hours: 60, discountPercent: 10, note: 'y' },
    ],
    effortBadge: 'Esfuerzo medio aparte',
    scopeTitle: 'Alcance',
    scopeParagraphs: ['p1', 'p2'],
  };

  it('builds a form with textarea-joined scope paragraphs', () => {
    const form = buildFormFromJson(json, 'commercial_conditions', { currency: 'COP' });
    expect(form.packages).toHaveLength(2);
    expect(form.hourlyRate).toBe(90000);
    expect(form.scopeParagraphs).toContain('p1');
    expect(form.scopeParagraphs).toContain('p2');
  });

  it('formToJson coerces numerics and splits scope paragraphs back to an array', () => {
    const form = buildFormFromJson(json, 'commercial_conditions', { currency: 'COP' });
    // Simulate admin text edits (strings from inputs).
    form.hourlyRate = '80000';
    form.packages[0].hours = '25';
    const out = formToJson(form, 'commercial_conditions');
    expect(out.hourlyRate).toBe(80000);
    expect(out.packages[0].hours).toBe(25);
    expect(Array.isArray(out.scopeParagraphs)).toBe(true);
    expect(out.scopeParagraphs).toEqual(['p1', 'p2']);
  });

  it('defaults hourPackagesMode to auto and always writes it back explicitly', () => {
    const form = buildFormFromJson(json, 'commercial_conditions', { currency: 'COP' });
    expect(form.hourPackagesMode).toBe('auto');
    const out = formToJson(form, 'commercial_conditions');
    expect(out.hourPackagesMode).toBe('auto');
  });

  it('preserves manual mode through the roundtrip', () => {
    const form = buildFormFromJson(
      { ...json, hourPackagesMode: 'manual' }, 'commercial_conditions', { currency: 'COP' },
    );
    expect(form.hourPackagesMode).toBe('manual');
    expect(formToJson(form, 'commercial_conditions').hourPackagesMode).toBe('manual');
  });

  it('normalizes unknown mode values to auto', () => {
    const form = buildFormFromJson(
      { ...json, hourPackagesMode: 'catalog' }, 'commercial_conditions', { currency: 'COP' },
    );
    expect(form.hourPackagesMode).toBe('auto');
    expect(formToJson(form, 'commercial_conditions').hourPackagesMode).toBe('auto');
  });

  it('carries the manual rate keys and package ids through untouched', () => {
    const form = buildFormFromJson({
      ...json,
      hourPackagesMode: 'manual',
      manualHourlyRate: 45000,
      manualCurrency: 'COP',
      manualPackageRates: [{ packageId: 7, hourlyRate: 52000 }],
      packages: [{ id: 7, name: 'Ágil', hours: 20, discountPercent: 0, note: '' }],
    }, 'commercial_conditions', { currency: 'COP' });

    const out = formToJson(form, 'commercial_conditions');
    expect(out.manualHourlyRate).toBe(45000);
    expect(out.manualCurrency).toBe('COP');
    expect(out.manualPackageRates).toEqual([{ packageId: 7, hourlyRate: 52000 }]);
    expect(out.packages[0].id).toBe(7);
  });

  it('omits an empty manual rate instead of writing a zero that would print $0', () => {
    const form = buildFormFromJson(json, 'commercial_conditions', { currency: 'COP' });
    expect(form.manualHourlyRate).toBe('');

    const out = formToJson(form, 'commercial_conditions');
    expect('manualHourlyRate' in out).toBe(false);
    expect('manualPackageRates' in out).toBe(false);
  });

  // Falla si editar el texto comercial borra el snapshot congelado de requerimientos.
  it('keeps frozen requirement packages while the editor changes commercial copy', () => {
    const form = buildFormFromJson({
      ...json,
      pricingModel: 'requirements', packagesFrozen: true, hourPackagesEnabled: false,
      packages: [{
        id: 8, name: 'Premium', xsCount: 30, sCount: 20, mCount: 10,
        referencePrice: 7600000, totalPrice: 5700000, discountPercent: 25,
        validityMonths: 12, note: 'Uso único', hours: 40, hourlyRate: 50000,
      }],
    }, 'commercial_conditions', { currency: 'COP' });
    form.scopeTitle = 'Alcance actualizado';
    form.packagesIntro = 'Los cupos se validan antes de programar.';

    const out = formToJson(form, 'commercial_conditions');
    expect(out).toMatchObject({
      pricingModel: 'requirements', packagesFrozen: true, hourPackagesEnabled: false,
      scopeTitle: 'Alcance actualizado', packagesIntro: 'Los cupos se validan antes de programar.',
      packages: [expect.objectContaining({
        xsCount: 30, sCount: 20, mCount: 10, referencePrice: 7600000, totalPrice: 5700000,
      })],
    });
    expect(out.packages[0].hours).toBeUndefined();
    expect(out.packages[0].hourlyRate).toBeUndefined();
  });
});
