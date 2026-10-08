// Legal identity shown in the Waiter legal pages, the footer and /contact.
// Must match the RUT and the business portfolio verified in Meta exactly:
// Meta rejects the WhatsApp app review when they differ.
export const LEGAL_ENTITY = Object.freeze({
  brand: 'ProjectApp',
  tradeName: 'SOFTPROJECTAPPCO',
  owner: 'GUSTAVO ADOLFO PEREZ PEREZ',
  nit: '1021513348-7',
  nationalId: '1021513348',
  address: 'Calle 30A #79-42',
  city: 'Medellín',
  country: 'Colombia',
  phone: '+57 323 812 2373',
  phoneHref: 'tel:+573238122373',
  whatsappHref: 'https://wa.me/573238122373',
  email: 'team@projectapp.co',
})

export const WAITER_LEGAL_ROUTES = Object.freeze({
  product: '/waiter',
  privacy: '/waiter/privacy',
  terms: '/waiter/terms',
  dataDeletion: '/waiter/data-deletion',
})
