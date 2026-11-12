import {
  expiryFromDays,
  getExpiryDays,
  toLocalDatetime,
} from '../../utils/proposalExpiry';

describe('proposalExpiry', () => {
  const novemberSeventh = new Date(2026, 10, 7, 4, 41, 0);

  it('keeps seven calendar days when the expiry hour is later', () => {
    // Falla si calcular desde milisegundos vuelve a sustituir siete días por ocho.
    const now = new Date(novemberSeventh);
    const days = getExpiryDays('2026-11-14T19:30', now);

    expect(days).toBe(7);
    expect(now.getTime()).toBe(new Date(2026, 10, 7, 4, 41, 0).getTime());
  });

  it('floors an overdue expiry to one day', () => {
    // Falla si una propuesta vencida vuelve a mostrar cero o un valor negativo.
    expect(getExpiryDays('2026-11-06T19:30', novemberSeventh)).toBe(1);
  });

  it('floors an expiry later on the current calendar day to one day', () => {
    // Falla si las horas restantes hacen que una fecha de hoy se presente como cero días.
    expect(getExpiryDays('2026-11-07T23:59', novemberSeventh)).toBe(1);
  });

  it('uses the default when expiry is missing', () => {
    // Falla si una propuesta sin vencimiento deja el control sin su valor inicial de 21 días.
    expect(getExpiryDays('', novemberSeventh)).toBe(21);
  });

  it('preserves the current expiry time when seven days cross a month boundary', () => {
    // Falla si el ajuste de días reemplaza la hora guardada o trata siete días como 168 horas.
    const now = new Date(2026, 11, 28, 23, 45, 0);

    expect(expiryFromDays(7, '2026-12-20T08:15', now)).toBe('2027-01-04T08:15');
  });

  it('roundtrips seven days for a future proposal', () => {
    // Falla si editar el número de días deja de corresponder con la fecha que el formulario muestra.
    const expiry = expiryFromDays(7, '2026-11-14T19:30', novemberSeventh);

    expect(getExpiryDays(expiry, novemberSeventh)).toBe(7);
  });

  it('uses the current clock time when no expiry exists', () => {
    // Falla si el vencimiento nuevo pierde la hora local de la edición.
    expect(expiryFromDays(7, '', novemberSeventh)).toBe('2026-11-14T04:41');
  });

  test.each([0, -2, 7.5, '7'])('defaults invalid day input %p to 21 days', (days) => {
    // Falla si una entrada no válida vuelve a producir una fecha incoherente en vez del plazo seguro.
    expect(expiryFromDays(days, '2026-10-15T19:30', novemberSeventh)).toBe('2026-11-28T19:30');
  });

  it('converts an ISO instant to the browser-local datetime control value', () => {
    // Falla si una recarga conserva UTC y desplaza la fecha u hora que el operador editó.
    const local = new Date('2026-11-07T00:30:00Z');
    const expected = `${local.getFullYear()}-${String(local.getMonth() + 1).padStart(2, '0')}`
      + `-${String(local.getDate()).padStart(2, '0')}T${String(local.getHours()).padStart(2, '0')}`
      + `:${String(local.getMinutes()).padStart(2, '0')}`;

    expect(toLocalDatetime('2026-11-07T00:30:00Z')).toBe(expected);
  });

  it('returns an empty local datetime for invalid input', () => {
    // Falla si una fecha corrupta termina como NaN en el control de vencimiento.
    expect(toLocalDatetime('no es una fecha')).toBe('');
  });
});
