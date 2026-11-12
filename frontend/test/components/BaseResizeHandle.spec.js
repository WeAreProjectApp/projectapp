import { mount } from '@vue/test-utils'

import BaseResizeHandle from '../../components/base/BaseResizeHandle.vue'

function mountHandle(props = {}) {
  return mount(BaseResizeHandle, {
    props: {
      value: 320,
      min: 240,
      max: 520,
      label: 'Ajustar el ancho de la columna Título',
      testId: 'title-resize',
      ...props,
    },
  })
}

describe('BaseResizeHandle', () => {
  it('publishes the separator value contract', () => {
    const handle = mountHandle().get('[data-testid="title-resize"]')

    expect(handle.attributes('role')).toBe('separator')
    expect(handle.attributes('aria-valuenow')).toBe('320')
    expect(handle.attributes('aria-valuemin')).toBe('240')
    expect(handle.attributes('aria-valuemax')).toBe('520')
    expect(handle.attributes('title')).toBe('Ajustar el ancho de la columna Título')
  })

  it('captures the pointer during a drag', async () => {
    const wrapper = mountHandle()
    const handle = wrapper.get('[data-testid="title-resize"]')
    handle.element.setPointerCapture = jest.fn()
    handle.element.releasePointerCapture = jest.fn()

    await handle.trigger('pointerdown', { pointerId: 7, clientX: 100 })
    await handle.trigger('pointermove', { pointerId: 7, clientX: 140 })
    await handle.trigger('pointerup', { pointerId: 7, clientX: 140 })

    expect(handle.element.setPointerCapture).toHaveBeenCalledWith(7)
    expect(handle.element.releasePointerCapture).toHaveBeenCalledWith(7)
    expect(wrapper.emitted('pointer-start')[0][0].defaultPrevented).toBe(true)
    expect(wrapper.emitted('pointer-move')).toHaveLength(1)
  })

  it.each([
    ['ArrowLeft', 304],
    ['ArrowRight', 336],
    ['Home', 240],
    ['End', 520],
  ])('emits the width for %s', async (key, expected) => {
    const wrapper = mountHandle()

    await wrapper.get('[data-testid="title-resize"]').trigger('keydown', { key })

    expect(wrapper.emitted('resize')).toEqual([[expected]])
  })

  it('clamps a keyboard step at the maximum', async () => {
    const wrapper = mountHandle({ value: 516 })

    await wrapper.get('[data-testid="title-resize"]').trigger('keydown', { key: 'ArrowRight' })

    expect(wrapper.emitted('resize')).toEqual([[520]])
  })

  it('requests the default on double click', async () => {
    const wrapper = mountHandle()

    await wrapper.get('[data-testid="title-resize"]').trigger('dblclick')

    expect(wrapper.emitted('reset')).toHaveLength(1)
  })
})
