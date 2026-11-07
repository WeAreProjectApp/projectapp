import { emailStatusLabel } from '../../utils/emailStatus';

describe('emailStatusLabel', () => {
  test.each([
    ['sent', 'Enviado'],
    ['delivered', 'Entregado'],
    ['bounced', 'Rebotado'],
    ['failed', 'Fallido'],
    ['skipped', 'Omitida'],
  ])('renders the Spanish label for %s', (status, label) => {
    // Falla si el panel vuelve a mostrar la etiqueta inglesa que entrega el backend.
    expect(emailStatusLabel(status, 'English backend label')).toBe(label);
  });

  it('keeps the supplied label for an unknown transport state', () => {
    // Falla si un estado nuevo pierde la explicación que el backend sí proporcionó.
    expect(emailStatusLabel('queued', 'En cola')).toBe('En cola');
  });
});
