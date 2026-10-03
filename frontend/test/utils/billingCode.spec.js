import { clientCustomerSnapshot, clientFormPayload } from '~/utils/billingCode';

describe('billingCode', () => {
  it('sends a C.C. customer without a residual NIT', () => {
    // Fails if a natural person's prior NIT leaks into the client update payload.
    expect(clientFormPayload({
      name: ' Ana ',
      email: ' ana@example.com ',
      phone: ' 300 123 ',
      company: ' Independiente ',
      identification_type: 'CC',
      nit: '901234567',
      cedula: ' 10203040 ',
      address: ' Calle 10 # 3 - 20 ',
      billing_code: ' ana  co ',
    })).toEqual({
      name: 'Ana',
      email: 'ana@example.com',
      phone: '300 123',
      company: 'Independiente',
      nit: '',
      cedula: '10203040',
      address: 'Calle 10 # 3 - 20',
      billing_code: 'ANA CO',
    });
  });

  it('uses the billing customer projection from the server verbatim', () => {
    // Fails if the account modal rebuilds the PDF customer instead of using the server projection.
    const billingCustomer = {
      name: 'Acme Soluciones SAS',
      identification_type: 'NIT',
      identification: '901234567-8',
      email: 'facturacion@acme.co',
      contact_name: 'Ana Pérez',
      address: 'Calle 93 # 18-28',
    };

    expect(clientCustomerSnapshot({ name: 'Ana', billing_customer: billingCustomer }))
      .toEqual(billingCustomer);
  });

  it('derives a compatible customer only for an older cached row', () => {
    // Fails if cached picker rows without billing_customer no longer populate a usable document recipient.
    expect(clientCustomerSnapshot({
      name: 'Ana Pérez', company: 'Acme Soluciones', nit: '', cedula: '10203040',
      email: 'ana@acme.co', address: 'Carrera 7 # 72-41', is_email_placeholder: false,
    })).toEqual({
      name: 'Ana Pérez',
      identification_type: 'CC',
      identification: '10203040',
      email: 'ana@acme.co',
      contact_name: 'Ana Pérez',
      address: 'Carrera 7 # 72-41',
    });
  });
});
