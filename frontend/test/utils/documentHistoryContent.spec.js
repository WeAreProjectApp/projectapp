import { documentContentDiff, historicalContent } from '~/utils/documentHistoryContent';

const snapshot = (content_markdown, text_formats = {}) => ({ content_markdown, text_formats });
const changed = (diff, kind) => diff.hunks.flatMap((hunk) => hunk.blocks).filter((block) => block.kind === kind);

describe('document history content', () => {
  it('renders historical headings as headings', () => {
    expect(historicalContent(snapshot('# Acuerdo')).html).toContain('<h1>Acuerdo</h1>');
  });

  it('keeps literal Markdown in a plain historical version', () => {
    expect(historicalContent(snapshot('**Literal**', { '/content_markdown': 'plain' })).html).toBe('<p>**Literal**</p>');
  });

  it('ignores equivalent emphasis serialization', () => {
    expect(documentContentDiff(snapshot('**Acuerdo**'), snapshot('<p><b>Acuerdo</b></p>')).hunks).toEqual([]);
  });

  it('ignores equivalent table wrappers', () => {
    const old = snapshot('| Nombre |\n| --- |\n| Ana |');
    const next = snapshot('<table><tr><th><p>Nombre</p></th></tr><tr><td><p>Ana</p></td></tr></table>');

    expect(documentContentDiff(old, next).hunks).toEqual([]);
  });

  it('preserves spaces between inline elements', () => {
    const diff = documentContentDiff(snapshot('<p><b>Uno</b> <i>dos</i></p>'), snapshot('<p><b>Uno</b><i>dos</i></p>'));

    expect(diff.hunks).toHaveLength(1);
  });

  it('identifies a formatting-only change', () => {
    const diff = documentContentDiff(snapshot('Acuerdo'), snapshot('**Acuerdo**'));

    expect(diff.hunks[0].formatOnly).toBe(true);
    expect(changed(diff, 'removed')[0].item.html).toContain('<p>Acuerdo</p>');
    expect(changed(diff, 'added')[0].item.html).toContain('<strong>Acuerdo</strong>');
  });

  it('retains removed list entries', () => {
    const diff = documentContentDiff(snapshot('- Diseño\n- Desarrollo'), snapshot('- Diseño'));

    expect(changed(diff, 'removed')[0].item.html).toContain('<li>Desarrollo</li>');
  });

  it('renders added table cells', () => {
    const diff = documentContentDiff(snapshot('Anterior'), snapshot('| Fase | Estado |\n| --- | --- |\n| Diseño | Listo |'));

    expect(changed(diff, 'added').map((block) => block.item.html).join('')).toContain('<td>Listo</td>');
  });

  it('retains one neighbouring block of context', () => {
    const diff = documentContentDiff(snapshot('# Título\n\nAnterior\n\nCierre'), snapshot('# Título\n\nNuevo\n\nCierre'));

    expect(diff.hunks[0].blocks.filter((block) => block.kind === 'context').map((block) => block.item.text)).toEqual(['Título', 'Cierre']);
  });

  it('reads legacy structured lists', () => {
    const result = historicalContent({ content_json: { blocks: [{ type: 'list', ordered: true, items: [{ text: 'Primero', children: [{ text: 'Detalle', children: [] }] }] }] } });

    expect(result.html).toContain('<ol><li>');
    expect(result.html).toContain('Detalle');
  });

  it('preserves unknown historical blocks as escaped text', () => {
    const result = historicalContent({ content_json: { blocks: [{ type: 'future', text: '<script>legacy()</script>' }] } });

    expect(result.unsupported).toBe(true);
    expect(result.html).toContain('&lt;script&gt;');
    expect(result.html).not.toContain('<script>');
  });

  it('removes executable historical markup', () => {
    const result = historicalContent(snapshot('<p onclick="attack()">Texto</p><script>attack()</script>'));

    expect(result.html).toContain('Texto');
    expect(result.html).not.toContain('onclick');
    expect(result.html).not.toContain('<script');
  });

  it('preserves a change in a link destination', () => {
    const diff = documentContentDiff(snapshot('[Contrato](https://old.example.test)'), snapshot('[Contrato](https://new.example.test)'));

    expect(changed(diff, 'added')[0].item.html).toContain('https://new.example.test');
  });

  it('keeps code whitespace significant', () => {
    const diff = documentContentDiff(snapshot('```\n  valor\n```'), snapshot('```\nvalor\n```'));

    expect(diff.hunks).toHaveLength(1);
  });

  it('leaves both historical snapshots unchanged', () => {
    const old = snapshot('# Antes');
    const next = snapshot('# Después');
    const original = JSON.stringify([old, next]);

    documentContentDiff(old, next);

    expect(JSON.stringify([old, next])).toBe(original);
  });

  it('isolates a modified table row from distant unchanged rows', () => {
    const old = snapshot('| Fase | Estado |\n| --- | --- |\n| A | Lista |\n| B | Lista |\n| C | Pendiente |\n| D | Lista |\n| E | Lista |');
    const next = snapshot(old.content_markdown.replace('C | Pendiente', 'C | Terminada'));

    const diff = documentContentDiff(old, next);

    expect(changed(diff, 'added')).toHaveLength(1);
    expect(changed(diff, 'added')[0].item.html).toContain('<td>Terminada</td>');
    expect(diff.hunks[0].blocks.map((block) => block.item.html).join('')).not.toContain('<td>E</td>');
  });

  it('keeps unchanged list items out of the changed blocks', () => {
    const diff = documentContentDiff(snapshot('- Uno\n- Antes\n- Tres'), snapshot('- Uno\n- Nuevo\n- Tres'));

    expect(changed(diff, 'added')).toHaveLength(1);
    expect(changed(diff, 'added')[0].item.html).not.toContain('<li>Uno</li>');
  });

  it('identifies the persisted PDF format without an available file', () => {
    expect(historicalContent({ content_format: 'pdf' }).pdf).toBe(true);
  });
});
