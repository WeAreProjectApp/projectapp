import { normalizeName } from './clientMatch';

/**
 * Lista plana e indentada de carpetas para los `<select>` de carpeta padre.
 *
 * `excludeId` saca del listado a la carpeta y a toda su descendencia: una
 * carpeta no puede colgar de sí misma ni de una hija suya (el serializer del
 * backend rechaza exactamente eso), y ofrecerlo sólo sirve para provocar el
 * error.
 */
export function buildFolderOptions(folderStore, excludeId = null) {
  const exclude = new Set();
  if (excludeId != null) {
    exclude.add(excludeId);
    folderStore.descendantIdsOf(excludeId).forEach((id) => exclude.add(id));
  }
  const options = [];
  const walk = (parentId, depth) => {
    folderStore.childrenOf(parentId)
      .filter((folder) => !exclude.has(folder.id))
      .forEach((folder) => {
        options.push({ id: folder.id, label: `${'   '.repeat(depth)}${folder.name}` });
        walk(folder.id, depth + 1);
      });
  };
  walk(null, 0);
  return options;
}

/*
 * Opciones del selector de carpeta de un documento (`DocumentFolderSelect`).
 *
 * Trabajan sobre la lista cruda del store (activas y archivadas juntas) y no
 * sobre sus getters: una fila sin `parent` o una respuesta que no es una lista
 * no pueden tumbar el formulario que las muestra.
 */

const TOP_LEVEL_LOCATION = {
  project: 'Carpeta del proyecto',
  client: 'Carpeta del cliente',
};

function asList(folders) {
  return Array.isArray(folders) ? folders : [];
}

function toFolderId(value) {
  if (value == null || value === '') return null;
  const id = Number(value);
  return Number.isInteger(id) ? id : null;
}

function indexById(folders) {
  const byId = new Map();
  asList(folders).forEach((folder) => {
    const id = toFolderId(folder?.id);
    if (id != null) byId.set(id, folder);
  });
  return byId;
}

// Cadena raíz → carpeta. Un dato cíclico se corta en la primera repetición.
function chainOf(byId, id) {
  const chain = [];
  const seen = new Set();
  let current = byId.get(id) || null;
  while (current && !seen.has(toFolderId(current.id))) {
    seen.add(toFolderId(current.id));
    chain.unshift(current);
    current = byId.get(toFolderId(current.parent)) || null;
  }
  return chain;
}

/**
 * Destino válido para un documento hecho a mano: activa y fuera del archivado
 * automático, que el backend rechaza con 409 `system_managed_folder`.
 */
export function isPickableFolder(folder) {
  return Boolean(folder) && !folder.is_archived && !folder.is_system_managed;
}

/** Ruta legible de cualquier carpeta de la lista, archivada o automática incluida. */
export function folderPathLabel(folders, id) {
  const folderId = toFolderId(id);
  if (folderId == null) return '';
  return chainOf(indexById(folders), folderId).map((folder) => folder.name).join(' / ');
}

function topLevelLocation(folder) {
  if (TOP_LEVEL_LOCATION[folder.folder_kind]) return TOP_LEVEL_LOCATION[folder.folder_kind];
  const hasOwner = folder.project != null || folder.client != null
    || Boolean(folder.project_name || folder.client_display_name);
  return hasOwner ? 'Carpeta principal' : 'Carpetas propias';
}

// El estado sólo viaja en la raíz del proyecto; como en el selector de
// proyectos, se nombra cuando no es el operativo normal.
function projectStateOf(chain) {
  const state = chain.find((node) => node.managed_project_state)?.managed_project_state;
  if (!state || state.system_key === 'active') return '';
  return state.name || '';
}

// Ubicación · dueños · estado. Un dueño que ya se lee en la ruta no se repite.
function detailOf(folder, chain) {
  const ancestors = chain.slice(0, -1);
  const location = ancestors.length
    ? ancestors.map((node) => node.name).join(' / ')
    : topLevelLocation(folder);
  const seen = new Set(chain.map((node) => normalizeName(node.name)));
  const owners = [];
  [folder.project_name, folder.client_display_name].forEach((name) => {
    const key = normalizeName(name);
    if (!key || seen.has(key)) return;
    seen.add(key);
    owners.push(name);
  });
  return [location, ...owners, projectStateOf(chain)].filter(Boolean).join(' · ');
}

function pickerOptionOf(folder, chain) {
  const names = chain.map((node) => node.name);
  return {
    id: toFolderId(folder.id),
    name: folder.name,
    pathLabel: names.join(' / '),
    detail: detailOf(folder, chain),
    nameKey: normalizeName(folder.name),
    haystack: normalizeName(
      [...names, folder.project_name, folder.client_display_name].filter(Boolean).join(' '),
    ),
  };
}

/**
 * Carpetas elegibles en el orden del panel lateral: cada padre antes que sus
 * hijas, hermanas en el orden en que llegan del store.
 *
 * Una carpeta activa cuyo padre no lo está se trata como raíz. Una automática
 * no se ofrece, pero se sigue bajando por ella: el backend sólo mira el
 * destino, así que un hijo manual sigue siendo elegible.
 */
export function buildFolderPickerOptions(folders) {
  const list = asList(folders);
  const byId = indexById(list);
  const isActive = (folder) => Boolean(folder) && !folder.is_archived;
  const children = new Map();
  const roots = [];
  list.forEach((folder) => {
    const id = toFolderId(folder?.id);
    if (id == null || !isActive(folder)) return;
    const parentId = toFolderId(folder.parent);
    if (parentId != null && parentId !== id && isActive(byId.get(parentId))) {
      if (!children.has(parentId)) children.set(parentId, []);
      children.get(parentId).push(folder);
    } else {
      roots.push(folder);
    }
  });

  const options = [];
  const visited = new Set();
  const walk = (folder) => {
    const id = toFolderId(folder.id);
    if (visited.has(id)) return;
    visited.add(id);
    if (isPickableFolder(folder)) options.push(pickerOptionOf(folder, chainOf(byId, id)));
    (children.get(id) || []).forEach(walk);
  };
  roots.forEach(walk);
  return options;
}

/**
 * Filtra por cada palabra escrita contra ruta, cliente y proyecto, sin tildes
 * ni mayúsculas. Primero las que la tienen en su propio nombre; después las que
 * coinciden sólo por su ubicación o su dueño. Cada grupo conserva el orden.
 */
export function filterFolderPickerOptions(options, term) {
  const tokens = normalizeName(term).split(' ').filter(Boolean);
  if (!tokens.length) return options;
  const byName = [];
  const byContext = [];
  options.forEach((option) => {
    if (!tokens.every((token) => option.haystack.includes(token))) return;
    const target = tokens.some((token) => option.nameKey.includes(token)) ? byName : byContext;
    target.push(option);
  });
  return [...byName, ...byContext];
}

/**
 * Carpeta a proponer cuando un enlace trae `?folder=`: la pedida si es
 * elegible y, si no (automática o archivada), la elegible más cercana hacia
 * arriba. `requested` es la fila pedida, para poder explicar el ajuste.
 */
export function resolveFolderPreselection(folders, raw) {
  const id = toFolderId(raw);
  const byId = indexById(folders);
  const requested = id == null ? null : byId.get(id) || null;
  if (!requested) return { folderId: null, requested: null };
  const target = chainOf(byId, id).reverse().find(isPickableFolder) || null;
  return { folderId: target ? toFolderId(target.id) : null, requested };
}
