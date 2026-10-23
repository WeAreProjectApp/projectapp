<script setup>
import { computed, ref, onMounted } from 'vue'
import { useMarkdownPreview } from '~/composables/useMarkdownPreview'
import { oneOf } from '~/components/base/propValidators'
import { sourceToHtml } from '~/utils/editorialFormat'

/**
 * Renders document markdown as sanitized HTML. Single owner of the
 * `.markdown-preview` styles (previously duplicated in create.vue/edit.vue).
 *
 * The parser output goes through DOMPurify before hitting v-html — documents
 * can be written by the MCP connector without passing through this panel, so
 * the markdown is not trusted input. DOMPurify only runs in the browser; until
 * it loads (or during SSR) nothing is rendered, never unsanitized HTML.
 *
 * variant: default → editor split preview; full → full-page preview modal;
 * mini → card thumbnail (non-interactive).
 * theme: friendly (default) → current look; professional → mirrors the
 * ReportLab brand PDF palette (dark esmerald headings, lemon accent).
 * standardMarkdown: GFM parser for extracted Office documents, including
 * escaped table delimiters and literal punctuation.
 */
const props = defineProps({
  markdown: { type: String, default: '' },
  variant: { type: String, default: 'default', validator: oneOf(['default', 'full', 'mini']) },
  theme: { type: String, default: 'friendly', validator: oneOf(['friendly', 'professional']) },
  standardMarkdown: { type: Boolean, default: false },
  format: { type: String, default: 'markdown' },
})

const { parseMarkdown } = useMarkdownPreview()

const purify = ref(null)
const standardParser = ref(null)
onMounted(async () => {
  const [mod, markdown] = await Promise.all([
    import('dompurify'),
    props.standardMarkdown ? import('marked') : Promise.resolve(null),
  ])
  purify.value = mod.default || mod
  standardParser.value = markdown?.marked || null
})

const safeHtml = computed(() => {
  if (!props.markdown?.trim() || !purify.value) return ''
  const extended = props.format === 'markdown_html_v1' || /<(?:p|h[1-6]|span|mark|u|table|ul|ol|blockquote)\b/i.test(props.markdown)
  let html = extended ? sourceToHtml(props.markdown, 'document', { strict: false }) : props.standardMarkdown
    ? standardParser.value?.parse(props.markdown, { gfm: true }).replace(
      /<(h[1-6]|p|ul|ol|li|blockquote|table|thead|tr|th|td|a|hr|pre)(?=[\s>])/g,
      (_tag, name) => `<${name} class="${{ pre: 'md-code-block', a: 'md-link' }[name] || `md-${name}`}"`,
    ) || ''
    : parseMarkdown(props.markdown)
  if (extended) {
    const host = document.createElement('div'); host.innerHTML = html;
    host.querySelectorAll('h1,h2,h3,h4,h5,h6,p,ul,ol,li,blockquote,table,thead,tr,th,td,a,hr,pre').forEach((el) => {
      el.classList.add({ pre: 'md-code-block', a: 'md-link' }[el.localName] || `md-${el.localName}`);
    });
    html = host.innerHTML;
  }
  return purify.value.sanitize(html, { ADD_ATTR: ['target'] })
})
</script>

<template>
  <div
    class="markdown-preview"
    :class="{
      'markdown-preview--full': variant === 'full',
      'markdown-preview--mini': variant === 'mini',
      'markdown-preview--professional': theme === 'professional',
    }"
    v-html="safeHtml"
  />
</template>

<style scoped>
.markdown-preview :deep(.md-h1) {
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1.3;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #d1d5db;
  color: #047857;
}
.markdown-preview :deep(.md-h2) {
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1.35;
  margin-top: 1.25rem;
  margin-bottom: 0.5rem;
  color: #047857;
}
.markdown-preview :deep(.md-h3) {
  font-size: 1.1rem;
  font-weight: 600;
  line-height: 1.4;
  margin-top: 1rem;
  margin-bottom: 0.4rem;
  color: #059669;
}
.markdown-preview :deep(.md-h4),
.markdown-preview :deep(.md-h5),
.markdown-preview :deep(.md-h6) {
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.4;
  margin-top: 0.85rem;
  margin-bottom: 0.35rem;
  color: #059669;
}
.markdown-preview :deep(.md-p) {
  margin-bottom: 0.75rem;
  line-height: 1.7;
  font-size: 0.875rem;
  color: #374151;
}
.markdown-preview :deep(.md-ul),
.markdown-preview :deep(.md-ol) {
  margin-bottom: 0.75rem;
  padding-left: 1.5rem;
  font-size: 0.875rem;
  color: #374151;
}
.markdown-preview :deep(.md-ul) { list-style-type: disc; }
.markdown-preview :deep(.md-ol) { list-style-type: decimal; }
.markdown-preview :deep(.md-ul li),
.markdown-preview :deep(.md-ol li) {
  margin-bottom: 0.25rem;
  line-height: 1.6;
}
.markdown-preview :deep(.md-blockquote) {
  border-left: 3px solid #10b981;
  background-color: #f0fdf4;
  padding: 0.75rem 1rem;
  margin-bottom: 0.75rem;
  font-style: italic;
  font-size: 0.875rem;
  color: #4b5563;
  border-radius: 0 0.5rem 0.5rem 0;
}
.markdown-preview :deep(.md-code-block) {
  background-color: #f3f4f6;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
  margin-bottom: 0.75rem;
  overflow-x: auto;
  font-size: 0.8rem;
  line-height: 1.6;
}
.markdown-preview :deep(.md-code-block code) {
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
  color: #1f2937;
}
.markdown-preview :deep(.md-table) {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 0.75rem;
  font-size: 0.8rem;
}
.markdown-preview :deep(.md-table th) {
  background-color: #f9fafb;
  border: 1px solid #e5e7eb;
  padding: 0.5rem 0.75rem;
  text-align: left;
  font-weight: 600;
  color: #374151;
}
.markdown-preview :deep(.md-table td) {
  border: 1px solid #e5e7eb;
  padding: 0.5rem 0.75rem;
  color: #4b5563;
}
.markdown-preview :deep(.md-table tbody tr:nth-child(even)) {
  background-color: #f9fafb;
}
.markdown-preview :deep(.md-hr) {
  border: none;
  border-top: 1px solid #d1d5db;
  margin: 1.25rem 0;
}
.markdown-preview :deep(.md-link) {
  color: #059669;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.markdown-preview :deep(.md-link:hover) { color: #047857; }
.markdown-preview :deep(strong) { font-weight: 600; }
.markdown-preview :deep(em) { font-style: italic; }
.markdown-preview :deep(del) { text-decoration: line-through; color: #6b7280; }
.markdown-preview :deep(code) {
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.85em;
  background-color: #f3f4f6;
  color: #374151;
  padding: 1px 4px;
  border-radius: 3px;
  border: 1px solid #e5e7eb;
}
.markdown-preview :deep(ul ul),
.markdown-preview :deep(ol ol),
.markdown-preview :deep(ul ol),
.markdown-preview :deep(ol ul) {
  margin-top: 4px;
  margin-bottom: 4px;
  margin-left: 20px;
}
.markdown-preview :deep(.callout) {
  border-radius: 6px;
  padding: 10px 14px;
  margin: 12px 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.markdown-preview :deep(.callout-label) { font-size: 11px; font-weight: 700; letter-spacing: 0.05em; }
.markdown-preview :deep(.callout-body) { font-size: 13px; line-height: 1.5; }
.markdown-preview :deep(.callout-note) { background-color: #e6efef; border-left: 3px solid #002921; }
.markdown-preview :deep(.callout-note .callout-label) { color: #002921; }
.markdown-preview :deep(.callout-tip) { background-color: #f0fff4; border-left: 3px solid #809490; }
.markdown-preview :deep(.callout-tip .callout-label) { color: #809490; }
.markdown-preview :deep(.callout-important) { background-color: #eef2ff; border-left: 3px solid #6366f1; }
.markdown-preview :deep(.callout-important .callout-label) { color: #6366f1; }
.markdown-preview :deep(.callout-warning) { background-color: #fffbeb; border-left: 3px solid #d97706; }
.markdown-preview :deep(.callout-warning .callout-label) { color: #d97706; }
.markdown-preview :deep(.callout-caution) { background-color: #fff1f2; border-left: 3px solid #f43f5e; }
.markdown-preview :deep(.callout-caution .callout-label) { color: #f43f5e; }

/* Dark mode */
:global(.dark) .markdown-preview :deep(.md-h1) { color: #6ee7b7; border-bottom-color: #374151; }
:global(.dark) .markdown-preview :deep(.md-h2) { color: #6ee7b7; }
:global(.dark) .markdown-preview :deep(.md-h3) { color: #a7f3d0; }
:global(.dark) .markdown-preview :deep(.md-h4),
:global(.dark) .markdown-preview :deep(.md-h5),
:global(.dark) .markdown-preview :deep(.md-h6) { color: #a7f3d0; }
:global(.dark) .markdown-preview :deep(.md-p),
:global(.dark) .markdown-preview :deep(.md-ul),
:global(.dark) .markdown-preview :deep(.md-ol) { color: #d1d5db; }
:global(.dark) .markdown-preview :deep(.md-ul li),
:global(.dark) .markdown-preview :deep(.md-ol li) { color: #d1d5db; }
:global(.dark) .markdown-preview :deep(.md-blockquote) {
  background-color: rgba(16, 185, 129, 0.1);
  border-left-color: #10b981;
  color: #9ca3af;
}
:global(.dark) .markdown-preview :deep(.md-code-block) { background-color: #1f2937; border-color: #374151; }
:global(.dark) .markdown-preview :deep(.md-code-block code) { color: #e5e7eb; }
:global(.dark) .markdown-preview :deep(.md-table th) { background-color: #1f2937; border-color: #374151; color: #d1d5db; }
:global(.dark) .markdown-preview :deep(.md-table td) { border-color: #374151; color: #9ca3af; }
:global(.dark) .markdown-preview :deep(.md-table tbody tr:nth-child(even)) { background-color: rgba(31, 41, 55, 0.5); }
:global(.dark) .markdown-preview :deep(.md-hr) { border-top-color: #374151; }
:global(.dark) .markdown-preview :deep(.md-link) { color: #6ee7b7; }
:global(.dark) .markdown-preview :deep(.md-link:hover) { color: #a7f3d0; }
:global(.dark) .markdown-preview :deep(del) { color: #9ca3af; }
:global(.dark) .markdown-preview :deep(code) { background-color: #374151; color: #d1d5db; border-color: #4b5563; }
:global(.dark) .markdown-preview :deep(.callout-note) { background-color: #0d2b24; border-color: #809490; }
:global(.dark) .markdown-preview :deep(.callout-tip) { background-color: #052e16; border-color: #4ade80; }
:global(.dark) .markdown-preview :deep(.callout-tip .callout-label) { color: #4ade80; }
:global(.dark) .markdown-preview :deep(.callout-important) { background-color: #1e1b4b; border-color: #818cf8; }
:global(.dark) .markdown-preview :deep(.callout-important .callout-label) { color: #818cf8; }
:global(.dark) .markdown-preview :deep(.callout-warning) { background-color: #1c1400; border-color: #fbbf24; }
:global(.dark) .markdown-preview :deep(.callout-warning .callout-label) { color: #fbbf24; }
:global(.dark) .markdown-preview :deep(.callout-caution) { background-color: #200a0e; border-color: #fb7185; }
:global(.dark) .markdown-preview :deep(.callout-caution .callout-label) { color: #fb7185; }

/* Card thumbnail (gallery mini-preview) */
.markdown-preview--mini { font-size: 0.65rem; }
.markdown-preview--mini :deep(.md-h1) {
  font-size: 0.9rem;
  margin-bottom: 0.35rem;
  padding-bottom: 0.25rem;
}
.markdown-preview--mini :deep(.md-h2) {
  font-size: 0.8rem;
  margin-top: 0.5rem;
  margin-bottom: 0.25rem;
}
.markdown-preview--mini :deep(.md-h3),
.markdown-preview--mini :deep(.md-h4),
.markdown-preview--mini :deep(.md-h5),
.markdown-preview--mini :deep(.md-h6) {
  font-size: 0.72rem;
  margin-top: 0.4rem;
  margin-bottom: 0.2rem;
}
.markdown-preview--mini :deep(.md-p),
.markdown-preview--mini :deep(.md-ul),
.markdown-preview--mini :deep(.md-ol),
.markdown-preview--mini :deep(.md-blockquote) {
  font-size: 0.65rem;
  line-height: 1.5;
  margin-bottom: 0.35rem;
}
.markdown-preview--mini :deep(.md-ul),
.markdown-preview--mini :deep(.md-ol) { padding-left: 1rem; }
.markdown-preview--mini :deep(.md-table) { font-size: 0.55rem; }
.markdown-preview--mini :deep(.md-table th),
.markdown-preview--mini :deep(.md-table td) { padding: 0.2rem 0.35rem; }
.markdown-preview--mini :deep(.md-code-block) {
  font-size: 0.55rem;
  padding: 0.35rem 0.5rem;
  margin-bottom: 0.35rem;
}
.markdown-preview--mini :deep(.callout) { padding: 5px 7px; margin: 6px 0; gap: 2px; }
.markdown-preview--mini :deep(.callout-label) { font-size: 8px; }
.markdown-preview--mini :deep(.callout-body) { font-size: 9px; line-height: 1.4; }
.markdown-preview--mini :deep(.md-hr) { margin: 0.5rem 0; }

/* Full-page preview (modal) */
.markdown-preview--full :deep(.md-h1) { font-size: 2rem; }
.markdown-preview--full :deep(.md-h2) { font-size: 1.5rem; }
.markdown-preview--full :deep(.md-h3) { font-size: 1.25rem; }
.markdown-preview--full :deep(.md-p),
.markdown-preview--full :deep(.md-ul),
.markdown-preview--full :deep(.md-ol),
.markdown-preview--full :deep(.md-blockquote) {
  font-size: 1rem;
  line-height: 1.75;
}
.markdown-preview--full :deep(.md-table) { font-size: 0.95rem; }
.markdown-preview--full :deep(.md-code-block) { font-size: 0.9rem; }

/* Professional theme — mirrors the ReportLab brand PDF */
.markdown-preview--professional :deep(.md-h1),
.markdown-preview--professional :deep(.md-h2) {
  color: #002921;
  border-bottom-color: #f0ff3d;
}
.markdown-preview--professional :deep(.md-h3),
.markdown-preview--professional :deep(.md-h4),
.markdown-preview--professional :deep(.md-h5),
.markdown-preview--professional :deep(.md-h6) { color: #335550; }
.markdown-preview--professional :deep(.md-p),
.markdown-preview--professional :deep(.md-ul),
.markdown-preview--professional :deep(.md-ol) { color: #335550; }
.markdown-preview--professional :deep(.md-blockquote) {
  background-color: #faf3e0;
  border-left-color: #f0ff3d;
  color: #002921;
  font-style: normal;
}
.markdown-preview--professional :deep(.md-table th) {
  background-color: #002921;
  color: #ffffff;
  border-color: #002921;
}
.markdown-preview--professional :deep(.md-table td) { border-color: #d1d5db; }
.markdown-preview--professional :deep(.md-table tbody tr:nth-child(even)) {
  background-color: #e6efef;
}
.markdown-preview--professional :deep(.md-link) { color: #059669; }
.markdown-preview--professional :deep(.md-code-block) {
  background-color: #e5e7eb;
  border-color: #d1d5db;
}
:global(.dark) .markdown-preview--professional :deep(.md-h1),
:global(.dark) .markdown-preview--professional :deep(.md-h2),
:global(.dark) .markdown-preview--professional :deep(.md-h3) { color: #a7f3d0; }
:global(.dark) .markdown-preview--professional :deep(.md-p),
:global(.dark) .markdown-preview--professional :deep(.md-ul),
:global(.dark) .markdown-preview--professional :deep(.md-ol) { color: #d1d5db; }
:global(.dark) .markdown-preview--professional :deep(.md-blockquote) {
  background-color: rgba(250, 243, 224, 0.08);
  color: #e5e7eb;
}
</style>
