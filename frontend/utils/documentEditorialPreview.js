/** Decorate a disposable reading projection; never serialize it as source. */
/** @param {string} html @param {string} prefix @param {Record<string, string>} labels */
export function documentEditorialPreview(html, prefix, labels) {
  const host = document.createElement('div');
  host.innerHTML = html;
  host.querySelectorAll('h1,h2,h3,h4,h5,h6,p,ul,ol,li,blockquote,table,thead,tr,th,td,a,hr,pre').forEach((element) => {
    const tag = element.localName;
    element.classList.add(({ pre: 'md-code-block', a: 'md-link' })[tag] || `md-${tag}`);
  });
  for (const quote of host.querySelectorAll('blockquote[data-callout]')) {
    const kind = quote.dataset.callout || 'NOTE';
    const label = document.createElement('span');
    label.className = 'callout-label';
    label.textContent = labels[kind] || kind;
    const body = document.createElement('div');
    body.className = 'callout-body';
    body.append(...quote.childNodes);
    quote.classList.add('callout', `callout-${kind.toLowerCase()}`);
    quote.append(label, body);
  }
  const headings = [...host.querySelectorAll('h1,h2,h3,h4,h5,h6')];
  const indexes = host.querySelectorAll('[data-editor-block="toc"]');
  if (indexes.length) headings.forEach((heading, index) => { heading.id = `${prefix}-heading-${index + 1}`; });
  for (const index of indexes) {
    index.replaceChildren();
    const title = document.createElement('p');
    title.textContent = labels.toc;
    title.className = 'font-semibold';
    index.append(title);
    if (!headings.length) {
      const empty = document.createElement('p');
      empty.textContent = labels.emptyToc;
      index.append(empty);
      continue;
    }
    const list = document.createElement('ul');
    list.className = 'md-ul';
    for (const heading of headings) {
      const item = document.createElement('li');
      const link = document.createElement('a');
      link.setAttribute('href', `#${heading.id}`);
      link.textContent = heading.textContent;
      link.className = 'md-link';
      item.append(link);
      list.append(item);
    }
    index.append(list);
  }
  return host.innerHTML;
}
