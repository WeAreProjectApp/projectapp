export function queryId(raw) {
  if (typeof raw !== 'string' || !/^\d+$/.test(raw)) return undefined;
  const id = Number(raw);
  return Number.isSafeInteger(id) && id > 0 ? id : undefined;
}

function idListCodec(allowNone) {
  return {
    read(raw) {
      if (typeof raw !== 'string') return undefined;
      const values = raw.split(',').map((value) => (
        allowNone && value === 'none' ? value : queryId(value)
      ));
      return values.every((value) => value !== undefined) ? values : undefined;
    },
    write: (values) => values.join(','),
  };
}

export const numericFilterIds = idListCodec(false);
export const optionalFilterIds = idListCodec(true);

export const repeatedFilterText = {
  read(raw) {
    const values = Array.isArray(raw) ? raw : [raw];
    return values.every((value) => typeof value === 'string' && value !== '') ? values : undefined;
  },
  write: (values) => (values.length === 1 ? values[0] : [...values]),
};

export const collectionProjectFilter = {
  read(raw) {
    if (typeof raw !== 'string') return undefined;
    try {
      const values = JSON.parse(raw);
      if (Array.isArray(values) && values.every((value) => (
        typeof value === 'string' ? value !== '' : Number.isSafeInteger(value) && value > 0
      ))) return values;
    } catch {
      // A malformed key leaves the preset (or the page default) in effect.
    }
    return undefined;
  },
  write: (values) => JSON.stringify(values),
};
