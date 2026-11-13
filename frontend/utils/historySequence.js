// Bound the dynamic-programming matrix, including for documents with thousands
// of paragraphs. The fallback retains every block; it only loses fine alignment.
const MAX_CELLS = 250_000;

export function historySequence(before, after, key = (item) => item.key) {
  let start = 0;
  while (start < before.length && start < after.length && key(before[start]) === key(after[start])) start++;
  let leftEnd = before.length;
  let rightEnd = after.length;
  while (leftEnd > start && rightEnd > start && key(before[leftEnd - 1]) === key(after[rightEnd - 1])) { leftEnd--; rightEnd--; }
  const rows = leftEnd - start;
  const columns = rightEnd - start;
  const simplified = rows * columns > MAX_CELLS;
  const result = before.slice(0, start).map((item) => ({ kind: 'context', item }));
  if (simplified) {
    result.push(...before.slice(start, leftEnd).map((item) => ({ kind: 'removed', item })));
    result.push(...after.slice(start, rightEnd).map((item) => ({ kind: 'added', item })));
  } else {
    const width = columns + 1;
    const matrix = new Uint32Array((rows + 1) * width);
    for (let i = rows - 1; i >= 0; i--) {
      for (let j = columns - 1; j >= 0; j--) {
        matrix[i * width + j] = key(before[start + i]) === key(after[start + j])
          ? 1 + matrix[(i + 1) * width + j + 1]
          : Math.max(matrix[(i + 1) * width + j], matrix[i * width + j + 1]);
      }
    }
    let i = 0;
    let j = 0;
    while (i < rows || j < columns) {
      if (i < rows && j < columns && key(before[start + i]) === key(after[start + j])) {
        result.push({ kind: 'context', item: after[start + j] }); i++; j++;
      } else if (i < rows && (j === columns || matrix[(i + 1) * width + j] >= matrix[i * width + j + 1])) {
        result.push({ kind: 'removed', item: before[start + i++] });
      } else {
        result.push({ kind: 'added', item: after[start + j++] });
      }
    }
  }
  result.push(...after.slice(rightEnd).map((item) => ({ kind: 'context', item })));
  return { operations: result, simplified };
}

/** One neighbouring unchanged block on each side of every change. */
export function historyHunks(operations) {
  const ranges = [];
  operations.forEach((operation, index) => {
    if (operation.kind === 'context') return;
    const from = Math.max(0, index - 1);
    const to = Math.min(operations.length, index + 2);
    const last = ranges[ranges.length - 1];
    if (last && from <= last.to) last.to = to;
    else ranges.push({ from, to });
  });
  return ranges.map(({ from, to }) => {
    const blocks = operations.slice(from, to);
    const removed = blocks.filter((block) => block.kind === 'removed').map((block) => block.item.text).join('\n');
    const added = blocks.filter((block) => block.kind === 'added').map((block) => block.item.text).join('\n');
    return { blocks, formatOnly: removed === added && blocks.some((block) => block.kind === 'removed') && blocks.some((block) => block.kind === 'added') };
  });
}
