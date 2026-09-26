/** Fixtures shared by the secure-link E2E specs (panel, public and responsive). */

export const SECURE_LINK_TOKEN = 'e2eTokenAbCdEfGhIjKlMnOpQrStUvWxYz0123456789';

export const secureLinkTypes = [
  {
    key: 'credentials',
    label_es: 'Credenciales de acceso',
    label_en: 'Access credentials',
    fields: [
      { key: 'service', label_es: 'Servicio o sitio', label_en: 'Service or site', kind: 'text', required: false, max_length: 200 },
      { key: 'username', label_es: 'Usuario o correo', label_en: 'Username or email', kind: 'text', required: false, max_length: 200 },
      { key: 'password', label_es: 'Contraseña', label_en: 'Password', kind: 'secret', required: true, max_length: 2000 },
      { key: 'note', label_es: 'Nota', label_en: 'Note', kind: 'textarea', required: false, max_length: 2000 },
    ],
  },
  {
    key: 'confidential_message',
    label_es: 'Mensaje o comunicado confidencial',
    label_en: 'Confidential message',
    fields: [
      { key: 'subject', label_es: 'Asunto', label_en: 'Subject', kind: 'text', required: false, max_length: 200 },
      { key: 'message', label_es: 'Mensaje', label_en: 'Message', kind: 'textarea', required: true, max_length: 15000 },
    ],
  },
];

export function secureLinkRow(overrides = {}) {
  return {
    id: 7,
    title: 'Admin Django producción',
    secret_type: 'credentials',
    type_label: 'Credenciales de acceso',
    language: 'es',
    origin: 'panel',
    origin_label: 'Equipo (panel)',
    sender: 'ProjectApp',
    team_only: false,
    status: 'active',
    client: null,
    client_name: 'Ana Cliente',
    project: null,
    project_name: 'Portal Demo',
    created_by_name: 'Admin',
    creator_name: '',
    creator_email: '',
    validity_days: 7,
    expires_at: '2026-10-03T15:00:00Z',
    consumed_at: null,
    revoked_at: null,
    activation_count: 1,
    created_at: '2026-09-26T15:00:00Z',
    updated_at: '2026-09-26T15:00:00Z',
    ...overrides,
  };
}

export const revealedContent = {
  secret_type: 'credentials',
  type_label: 'Credenciales de acceso',
  title: 'Admin Django producción',
  fields: [
    { key: 'service', label: 'Servicio o sitio', kind: 'text', value: 'Django admin' },
    { key: 'password', label: 'Contraseña', kind: 'secret', value: 'S3cr3t-E2E!' },
  ],
};

export function publicStatus(overrides = {}) {
  return {
    status: 'active',
    secret_type: 'credentials',
    type_label: 'Credenciales de acceso',
    sender: 'ProjectApp',
    language: 'es',
    expires_at: '2026-10-03T15:00:00Z',
    team_only: false,
    can_reveal: true,
    ...overrides,
  };
}

export const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });
