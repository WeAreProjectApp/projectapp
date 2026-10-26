/** Shared cycle-safe root-to-folder path. */
export function folderPath(folder, folders) {
  const byId = new Map(folders.map((item) => [Number(item.id), item]));
  const segments = [];
  const seen = new Set();
  let node = folder;
  while (node && !seen.has(node.id)) {
    seen.add(node.id);
    segments.unshift(node);
    node = byId.get(Number(node.parent));
  }
  return segments;
}
