import { Node, mergeAttributes } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import { Table, TableRow, TableCell, TableHeader } from '@tiptap/extension-table';
import { TextStyle, Color } from '@tiptap/extension-text-style';
import TextAlign from '@tiptap/extension-text-align';
import Highlight from '@tiptap/extension-highlight';
import Placeholder from '@tiptap/extension-placeholder';
import { normalizeEditorialColor } from './editorialFormat';

// Browsers serialize CSS hex colors as rgb(). Normalize both imported markup
// and toolbar commands so mode switches do not change the document attributes.
const EditorialColor = Color.extend({
  addGlobalAttributes() {
    return [{ types: this.options.types, attributes: { color: {
      default: null,
      parseHTML: (element) => normalizeEditorialColor(element.style.color),
      renderHTML: (attributes) => attributes.color ? { style: `color: ${normalizeEditorialColor(attributes.color)}` } : {},
    } } }];
  },
  addCommands() {
    return {
      ...this.parent?.(),
      setColor: (color) => ({ chain }) => {
        const normalized = normalizeEditorialColor(color);
        return normalized ? chain().setMark('textStyle', { color: normalized }).run() : false;
      },
    };
  },
});

// The standard extension adds data-color and color:inherit. The persisted
// vocabulary deliberately uses only the presentation property it represents.
const EditorialHighlight = Highlight.extend({
  addAttributes() {
    return { color: {
      default: null,
      parseHTML: (element) => normalizeEditorialColor(element.style.backgroundColor),
      renderHTML: (attributes) => attributes.color ? { style: `background-color: ${normalizeEditorialColor(attributes.color)}` } : {},
    } };
  },
  addCommands() {
    return {
      ...this.parent?.(),
      setHighlight: (attributes = {}) => ({ commands }) => commands.setMark(this.name, { color: normalizeEditorialColor(attributes.color) }),
      toggleHighlight: (attributes = {}) => ({ commands }) => commands.toggleMark(this.name, { color: normalizeEditorialColor(attributes.color) }),
    };
  },
});

const cellAttributes = function () {
  const attributes = { ...this.parent?.() };
  // TextAlign owns cell alignment as well as paragraph alignment. Keeping the
  // table package's second, independent align attribute would diverge on edits.
  delete attributes.align;
  return attributes;
};
const EditorialTableCell = TableCell.extend({ addAttributes: cellAttributes });
const EditorialTableHeader = TableHeader.extend({ addAttributes: cellAttributes });
const EditorialStarterKit = StarterKit.extend({
  addExtensions() {
    return this.parent().map((extension) => ['paragraph', 'heading', 'code'].includes(extension.name) ? extension.extend({
      parseHTML() { return this.parent().map((rule) => ({ ...rule, preserveWhitespace: 'full' })); },
    }) : extension);
  },
});

const TableOfContents = Node.create({
  name: 'editorialToc', group: 'block', atom: true,
  parseHTML: () => [{ tag: 'div[data-editor-block="toc"]' }],
  renderHTML: () => ['div', { 'data-editor-block': 'toc' }, '[TOC]'],
});

const Callout = Node.create({
  name: 'editorialCallout', group: 'block', content: 'block+', defining: true,
  addAttributes: () => ({ kind: { default: 'NOTE', parseHTML: (el) => el.dataset.callout, renderHTML: (attrs) => ({ 'data-callout': attrs.kind }) } }),
  parseHTML: () => [{ tag: 'blockquote[data-callout]', priority: 100 }],
  renderHTML: ({ HTMLAttributes }) => ['blockquote', mergeAttributes(HTMLAttributes), 0],
});

/** A single schema owns both visual editing and source conversion. */
export function editorialExtensions(profile = 'document', placeholder = '') {
  const whatsapp = profile === 'whatsapp';
  const extensions = [EditorialStarterKit.configure({
    heading: whatsapp ? false : { levels: [1, 2, 3, 4, 5, 6] },
    underline: !whatsapp,
    link: whatsapp ? false : { openOnClick: false, autolink: false, HTMLAttributes: { target: null, rel: null } },
    horizontalRule: !whatsapp,
    undoRedo: false,
    trailingNode: false,
  }), Placeholder.configure({ placeholder })];
  if (!whatsapp) extensions.push(
    Table.extend({ renderHTML: ({ HTMLAttributes }) => ['table', HTMLAttributes, ['tbody', 0]] }).configure({ resizable: false }),
    TableRow, EditorialTableCell, EditorialTableHeader, TextStyle, EditorialColor,
    TextAlign.configure({ types: ['heading', 'paragraph', 'tableCell', 'tableHeader'] }),
    EditorialHighlight.configure({ multicolor: true }), TableOfContents, Callout,
  );
  return extensions;
}
