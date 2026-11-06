import { documentEditorialPreview } from '~/utils/documentEditorialPreview';

function preview(html, labels = {}) {
  const host = document.createElement('div');
  host.innerHTML = documentEditorialPreview(html, 'document-preview', {
    toc: 'Índice', emptyToc: 'Añade encabezados.', ...labels,
  });
  return host;
}

describe('documentEditorialPreview', () => {
  // Catches duplicate heading labels making every table-of-contents entry jump to one destination.
  it('creates distinct table-of-contents anchors for duplicate headings', () => {
    // quality: allow-fragile-selector (Heading IDs and links are the preview utility's public HTML contract.)
    const host = preview('<div data-editor-block="toc">[TOC]</div><h2>Resumen</h2><h2>Resumen</h2>');

    expect([...host.querySelectorAll('h2')].map((heading) => heading.id)).toEqual(['document-preview-heading-1', 'document-preview-heading-2']);
    expect([...host.querySelectorAll('a')].map((link) => link.getAttribute('href'))).toEqual(['#document-preview-heading-1', '#document-preview-heading-2']);
  });

  // Catches a table of contents concealing the reason it has no navigable entries.
  it('explains an empty table of contents', () => {
    // quality: allow-fragile-selector (The empty-index projection is the utility's public HTML contract.)
    const host = preview('<div data-editor-block="toc">[TOC]</div>');

    expect(host.textContent).toBe('ÍndiceAñade encabezados.');
  });

  // Catches translated preview labels being appended as executable markup.
  it('renders preview labels as literal text', () => {
    // quality: allow-fragile-selector (The utility owns the preview's parsed label output.)
    const host = preview('<div data-editor-block="toc">[TOC]</div>', { toc: '<img src=x>', emptyToc: 'Sin secciones' });

    expect(host.querySelector('img')).toBeNull();
    expect(host.textContent).toBe('<img src=x>Sin secciones');
  });

  // Catches the callout decorator dropping its rich body while it adds its reading label.
  it('preserves the callout body markup', () => {
    // quality: allow-fragile-selector (Callout elements are the documented reading projection.)
    const host = preview('<blockquote data-callout="TIP"><p>Conserva <strong>esto</strong></p></blockquote>', { TIP: 'Consejo' });
    const callout = host.querySelector('blockquote');

    expect(callout.getAttribute('data-callout')).toBe('TIP');
    expect(callout.textContent).toBe('ConsejoConserva esto');
    expect(callout.querySelector('strong').textContent).toBe('esto');
  });
});
