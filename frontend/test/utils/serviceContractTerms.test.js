import {
  formatServiceTerm,
  savedServiceTermNumber,
  serviceTermNumber,
  validServiceContractSettings,
} from '../../utils/serviceContractTerms';

describe('serviceContractTerms', () => {
  test.each([
    [1, false, 'un (1)'],
    [21, false, 'veintiún (21)'],
    [1, true, 'un (1) mes'],
    [21, true, 'veintiún (21) meses'],
  ])('formats %p with duration %p', (value, duration, expected) => {
    // Falla si la vista previa deja de coincidir con el texto contractual guardado.
    expect(formatServiceTerm(value, duration)).toBe(expected);
  });

  test.each([
    [1, 1],
    ['999', 999],
    [0, null],
    [1000, null],
    ['2.5', null],
    [-1, null],
  ])('parses %p as %p', (value, expected) => {
    // Falla si el formulario acepta un número que el contrato no puede representar.
    expect(serviceTermNumber(value)).toBe(expected);
  });

  test.each([
    ['doce (12) meses', true, 12],
    ['veintiún (21)', false, 21],
    ['doce (12)', true, null],
    ['veintiuno (21)', false, null],
  ])('recognizes %p with duration %p', (value, duration, expected) => {
    // Falla si abrir un contrato histórico reemplaza una cláusula que no coincide exactamente.
    expect(savedServiceTermNumber(value, duration)).toBe(expected);
  });

  it('requires each configured default to belong to its catalog', () => {
    // Falla si el modal habilita una configuración cuyo valor inicial no se puede seleccionar.
    expect(validServiceContractSettings({
      duration_options: [3, 6, 9],
      notice_options: [30, 60, 90],
      default_duration: 9,
      default_renewal_notice: 60,
      default_termination_notice: 60,
    })).toBe(true);
    expect(validServiceContractSettings({
      duration_options: [3, 6, 9],
      notice_options: [30, 60, 90],
      default_duration: 12,
      default_renewal_notice: 60,
      default_termination_notice: 60,
    })).toBe(false);
  });
});
