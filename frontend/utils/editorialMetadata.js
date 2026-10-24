/** Keep annotations attached to their owning object across form projections. */
export function withEditorialFormats(source, target) {
  if (!source || !target || typeof source !== 'object' || typeof target !== 'object') return target;
  if (!Array.isArray(target) && source.text_formats && Object.keys(source.text_formats).length) target.text_formats = { ...source.text_formats };
  for (const key of Object.keys(target)) {
    if (key !== 'text_formats' && source[key] && target[key] && typeof target[key] === 'object') withEditorialFormats(source[key], target[key]);
  }
  return target;
}

export const fieldFormat = (owner, path, fallback = 'plain') => owner?.text_formats?.[path] || fallback;
export function setFieldFormat(owner, path, format) {
  owner.text_formats = { ...owner.text_formats, [path]: format };
}

/** Remove one JSON root's annotations after its clone has local owners. */
export function withoutEditorialPrefix(formats, prefix) {
  return Object.fromEntries(Object.entries(formats || {}).filter(([path]) => path !== prefix && !path.startsWith(prefix + '/')));
}


export function remapEditorialArrayFormats(formats, prefix, retainedIndices) {
  const result = {};
  for (const [path, format] of Object.entries(formats || {})) {
    if (!path.startsWith(prefix + '/')) { result[path] = format; continue; }
    const [oldIndex, ...rest] = path.slice(prefix.length + 1).split('/');
    const index = retainedIndices.indexOf(Number(oldIndex));
    if (index >= 0) result[prefix + '/' + index + (rest.length ? '/' + rest.join('/') : '')] = format;
  }
  return result;
}

export function normalizeEditorialFeatures(payload) {
  const features = payload.email_features || [];
  const indices = features.map((_, index) => index).filter(index => typeof features[index] === 'string' && features[index].trim());
  payload.text_formats = remapEditorialArrayFormats(payload.text_formats, '/email_features', indices);
  payload.email_features = indices.map(index => features[index].trim());
  return payload;
}

/** Move resolved annotations to their closest object owner in an isolated clone. */
export function resolveEditorialContent(source, formats = {}, prefix = '') {
  const annotate = (result, annotations, base = '') => {
    for (const [path, format] of Object.entries(annotations || {})) {
      if (!path.startsWith(base + '/')) continue;
      const tokens = path.slice(base.length + 1).split('/').map(key => key.replace(/~1/g, '/').replace(/~0/g, '~'));
      const localPath = '/' + tokens.map(key => key.replace(/~/g, '~0').replace(/\//g, '~1')).join('/');
      let node = result;
      let owner = result;
      let relative = [];
      for (const [index, token] of tokens.entries()) {
        if (!node || typeof node !== 'object' || !Object.hasOwn(node, token)) break;
        relative.push(token.replace(/~/g, '~0').replace(/\//g, '~1'));
        const child = node[token];
        if (typeof child === 'string') {
          if (index !== tokens.length - 1) break;
          const ownerPath = '/' + relative.join('/');
          const existing = owner.text_formats?.[ownerPath];
          if (existing && existing !== format) {
            // Keep genuinely conflicting declarations available to server validation.
            if (owner !== result && !Object.hasOwn(result.text_formats || {}, localPath)) {
              result.text_formats = { ...result.text_formats, [localPath]: format };
            }
            break;
          }
          owner.text_formats = { ...owner.text_formats, [ownerPath]: format };
          if (owner !== result && Object.hasOwn(result.text_formats || {}, localPath)) {
            delete result.text_formats[localPath];
            if (!Object.keys(result.text_formats).length) delete result.text_formats;
          }
          break;
        }
        node = child;
        if (node && typeof node === 'object' && !Array.isArray(node)) { owner = node; relative = []; }
      }
    }
    return result;
  };
  const copy = value => {
    if (Array.isArray(value)) return value.map(copy);
    if (!value || typeof value !== 'object') return value;
    const result = Object.fromEntries(Object.entries(value).map(([key, item]) => [key, copy(item)]));
    return annotate(result, value.text_formats);
  };
  return annotate(copy(source || {}), formats, prefix);
}
