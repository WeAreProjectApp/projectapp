import messages from '../../locales/documentFolders/es';

export const documentFolderI18n = () => ({
  t: (key, values = {}) => (messages[key.replace('documentFolders.', '')] || key)
    .replace(/\{(\w+)\}/g, (_, name) => values[name] ?? ''),
});
