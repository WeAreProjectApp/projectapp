import { mount, flushPromises } from '@vue/test-utils'
import DocumentMarkdownBody from '../../components/panel/documents/DocumentMarkdownBody.vue'

async function mountBody(props = {}) {
  const wrapper = mount(DocumentMarkdownBody, { props })
  // DOMPurify loads via dynamic import in onMounted
  await flushPromises()
  return wrapper
}

describe('DocumentMarkdownBody', () => {
  it('renders parsed markdown with md-* classes', async () => {
    const wrapper = await mountBody({ markdown: '# Título\n\nHola **mundo**' })
    expect(wrapper.html()).toContain('md-h1')
    expect(wrapper.html()).toContain('<strong>mundo</strong>')
  })

  it('renders nothing for empty markdown', async () => {
    const wrapper = await mountBody({ markdown: '   ' })
    expect(wrapper.element.innerHTML).toBe('')
  })

  // Catches plain legacy documents gaining rich formatting or interpreting stored HTML as markup.
  it('renders plain source syntax literally', async () => {
    const wrapper = await mountBody({ markdown: '**literal** <u>visible</u>', format: 'plain' })

    expect(wrapper.text()).toBe('**literal** <u>visible</u>')
    expect(wrapper.html()).toContain('&lt;u&gt;visible&lt;/u&gt;')
    expect(wrapper.html()).not.toContain('<strong>literal</strong>')
  })

  it('strips script tags injected through markdown', async () => {
    const wrapper = await mountBody({ markdown: 'hola\n\n<script>window.hacked = true<\/script>' })
    expect(wrapper.html()).not.toContain('<script')
    expect(window.hacked).toBeUndefined()
  })

  it('strips event handler attributes', async () => {
    const wrapper = await mountBody({ markdown: 'x <img src="x" onerror="window.hacked=1"> y' })
    expect(wrapper.html()).not.toContain('onerror')
  })

  it('neutralizes javascript: links', async () => {
    const wrapper = await mountBody({ markdown: '[mal](javascript:alert(1))' })
    expect(wrapper.html()).not.toContain('javascript:')
  })

  it('keeps target and rel on parser-generated links', async () => {
    const wrapper = await mountBody({ markdown: '[ok](https://example.com)' })
    const link = wrapper.find('a.md-link')
    expect(link.exists()).toBe(true)
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('href')).toBe('https://example.com')
  })

  it('converts emoji shortcodes in the rendered output', async () => {
    const wrapper = await mountBody({ markdown: 'Deploy :rocket:' })
    expect(wrapper.text()).toContain('Deploy 🚀')
  })

  it('applies variant modifier classes', async () => {
    const full = await mountBody({ markdown: '# T', variant: 'full' })
    expect(full.classes()).toContain('markdown-preview--full')
    const mini = await mountBody({ markdown: '# T', variant: 'mini' })
    expect(mini.classes()).toContain('markdown-preview--mini')
  })
})
