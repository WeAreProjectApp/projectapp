import { flushPromises, mount } from '@vue/test-utils'
import ProjectClientCredential from '../../../components/projects/client-access/ProjectClientCredential.vue'

global.useI18n = () => ({ t: (key) => key })

function mountCredential(api) {
  return mount(ProjectClientCredential, {
    props: { api, projectId: 42, environment: 'production', field: 'admin_password' },
  })
}

describe('ProjectClientCredential', () => {
  beforeEach(() => {
    jest.useFakeTimers()
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: jest.fn().mockResolvedValue(undefined) },
    })
    Object.defineProperty(document, 'hidden', { configurable: true, value: false })
  })

  afterEach(() => {
    jest.useRealTimers()
    Object.defineProperty(document, 'hidden', { configurable: true, value: false })
  })

  it('clears a revealed credential when the tab becomes hidden', async () => {
    // Falla si una contraseña queda expuesta después de abandonar la pestaña.
    const api = { reveal: jest.fn().mockResolvedValue({ secret: 'clave-visible' }) }
    const wrapper = mountCredential(api)

    await wrapper.get('[data-testid="client-credential-toggle"]').trigger('click')
    await flushPromises()
    Object.defineProperty(document, 'hidden', { configurable: true, value: true })
    document.dispatchEvent(new Event('visibilitychange'))
    await flushPromises()

    expect(wrapper.find('[data-testid="client-credential-value"]').exists()).toBe(false)
    expect(api.reveal).toHaveBeenCalledWith('production', 'admin_password')
    wrapper.unmount()
  })

  it('clears a revealed credential after thirty seconds', async () => {
    // Falla si una revelación permanece en memoria más tiempo que el límite visible prometido.
    const api = { reveal: jest.fn().mockResolvedValue({ secret: 'clave-temporal' }) }
    const wrapper = mountCredential(api)

    await wrapper.get('[data-testid="client-credential-toggle"]').trigger('click')
    await flushPromises()
    jest.advanceTimersByTime(30000)
    await flushPromises()

    expect(wrapper.find('[data-testid="client-credential-value"]').exists()).toBe(false)
    expect(api.reveal).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('requests a fresh credential before copying it', async () => {
    // Falla si Copiar reutiliza una contraseña mostrada antes de que el servidor pueda revocar el grant.
    const api = {
      reveal: jest.fn()
        .mockResolvedValueOnce({ secret: 'clave-anterior' })
        .mockResolvedValueOnce({ secret: 'clave-nueva' }),
    }
    const wrapper = mountCredential(api)

    await wrapper.get('[data-testid="client-credential-toggle"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="client-credential-copy"]').trigger('click')
    await flushPromises()

    expect(api.reveal).toHaveBeenCalledTimes(2)
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('clave-nueva')
    expect(wrapper.get('[role="status"]').text()).toBe('projectClientAccess.copied')
    wrapper.unmount()
  })

  it('removes a previous credential when a new reveal is denied', async () => {
    // Falla si una revocación deja en pantalla la contraseña que fue revelada antes.
    const api = {
      reveal: jest.fn()
        .mockResolvedValueOnce({ secret: 'clave-anterior' })
        .mockRejectedValueOnce({ response: { status: 403, data: { detail: 'Acceso revocado' } } }),
    }
    const wrapper = mountCredential(api)

    await wrapper.get('[data-testid="client-credential-toggle"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="client-credential-copy"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="client-credential-value"]').exists()).toBe(false)
    expect(wrapper.get('[role="alert"]').text()).toBe('Acceso revocado')
    expect(wrapper.emitted('denied')).toEqual([[]])
    wrapper.unmount()
  })
})
