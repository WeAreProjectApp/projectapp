import { folderPath } from './folderHierarchy';
export { folderPath } from './folderHierarchy';

export function folderOptions(folders, { client, project, exclude } = {}) {
  return folders.filter((folder) => (
    (!client || Number(folder.client) === Number(client))
    && (!folder.project || Number(folder.project) === Number(project))
    && !folderPath(folder, folders).some((node) => Number(node.id) === Number(exclude))
  )).map((folder) => ({
    value: String(folder.id),
    label: folderPath(folder, folders).map((node) => node.name).join(' / '),
  }));
}
