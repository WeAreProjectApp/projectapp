import { mount } from '@vue/test-utils';

jest.mock('../../composables/useMessages', () => ({
  useMessages: jest.fn(() => ({ messages: require('vue').ref({ company: require('../../locales/waiter/es.js').default.company }) })),
}));

import CompanyDetails from '../../components/legal/CompanyDetails.vue';
import { LEGAL_ENTITY } from '../../config/legalEntity.js';

describe('CompanyDetails', () => {
  it('lists the company identity, address and business hours', () => {
    const text = mount(CompanyDetails).text();

    expect(text).toContain('Datos de la empresa');
    expect(text).toContain(`ProjectApp — ${LEGAL_ENTITY.tradeName}`);
    expect(text).toContain(LEGAL_ENTITY.owner);
    expect(text).toContain(LEGAL_ENTITY.nit);
    expect(text).toContain(`${LEGAL_ENTITY.address}, ${LEGAL_ENTITY.city}, ${LEGAL_ENTITY.country}`);
    expect(text).toContain('Lunes a viernes, 8:00 a. m. a 6:00 p. m.');
  });

  it('links the phone to WhatsApp in a new tab and the email to mailto', () => {
    const wrapper = mount(CompanyDetails);

    const phone = wrapper.get(`a[href="${LEGAL_ENTITY.whatsappHref}"]`);
    expect(phone.text()).toBe(LEGAL_ENTITY.phone);
    expect(phone.attributes('target')).toBe('_blank');
    expect(wrapper.get(`a[href="mailto:${LEGAL_ENTITY.email}"]`).text()).toBe(LEGAL_ENTITY.email);
  });
});
