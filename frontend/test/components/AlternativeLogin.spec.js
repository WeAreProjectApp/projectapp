const { flushPromises, mount } = require('@vue/test-utils')
const BaseInput = require('../../components/base/BaseInput.vue').default
const BaseSegmented = require('../../components/base/BaseSegmented.vue').default

const mockConfig = jest.fn()
const mockPost = jest.fn()
const mockUseAccessLogin = jest.fn(() => ({ config: mockConfig, post: mockPost }))

jest.mock('../../composables/useAccessLogin', () => ({
  useAccessLogin: mockUseAccessLogin,
}))

const AlternativeLogin = require('../../components/auth/AlternativeLogin.vue').default

const BaseButtonStub = {
  props: ['disabled', 'disabledReason', 'loading', 'type', 'variant'],
  emits: ['click'],
  template: '<button role="button" :type="type || \'button\'" :disabled="disabled || loading" @click="$emit(\'click\', $event)"><slot /></button>',
}

const LoginCaptchaStub = {
  emits: ['update:token'],
  template: '<button type="button" data-testid="captcha-pass" @click="$emit(\'update:token\', \'captcha-token\')">Completar captcha</button>',
}

const globalStubs = {
  BaseAlert: { template: '<p role="alert"><slot /></p>' },
  BaseButton: BaseButtonStub,
  BaseFormField: { template: '<label><slot /></label>' },
  LoginCaptcha: LoginCaptchaStub,
}

const mounted = []

function mountLogin(props = {}) {
  const wrapper = mount(AlternativeLogin, {
    props: { surface: 'panel', next: '/panel/inicio', ...props },
    global: {
      components: { BaseInput, BaseSegmented },
      stubs: globalStubs,
    },
  })
  mounted.push(wrapper)
  return wrapper
}

async function requestCode(wrapper) {
  await wrapper.get('[data-testid="access-email"]').setValue('ana@example.com')
  await wrapper.get('[data-testid="captcha-pass"]').trigger('click')
  await wrapper.find('form').trigger('submit')
  await flushPromises()
}

describe('AlternativeLogin', () => {
  beforeEach(() => {
    mockConfig.mockResolvedValue({ google_client_id: 'google-client-id' })
    mockPost.mockReset()
    mockUseAccessLogin.mockClear()
    global.useRuntimeConfig = () => ({
      public: { recaptchaEnabled: true, recaptchaSiteKey: 'captcha-site-key' },
    })
  })

  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
    jest.useRealTimers()
    delete global.useRuntimeConfig
    delete window.google
  })

  it('sends the entered email with the captcha token', async () => {
    // Falla si solicitar un código deja de enviar el correo o el captcha que exige el servidor.
    jest.useFakeTimers()
    mockPost.mockResolvedValueOnce({
      challenge_id: 'challenge-email-1', detail: 'Código enviado.', retry_after: 30,
    })
    const wrapper = mountLogin()
    await flushPromises()

    await requestCode(wrapper)

    expect(mockPost).toHaveBeenCalledWith('email-request', {
      email: 'ana@example.com', recaptcha_token: 'captcha-token',
    })
  })

  it('blocks verification for a five-digit code', async () => {
    // Falla si un código incompleto puede iniciar una verificación de acceso.
    jest.useFakeTimers()
    mockPost.mockResolvedValueOnce({
      challenge_id: 'challenge-email-2', detail: 'Código enviado.', retry_after: 30,
    })
    const wrapper = mountLogin()
    await flushPromises()

    await requestCode(wrapper)
    await wrapper.get('[data-testid="access-code"]').setValue('12345')
    const verifyButton = wrapper.get('[role="button"][type="submit"]')
    await verifyButton.trigger('click')

    expect(verifyButton.element.disabled).toBe(true)
    expect(mockPost).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('authenticated')).toBeUndefined()
  })

  it('emits the verified access session', async () => {
    // Falla si la sesión verificada no llega al contenedor que completa el inicio de sesión.
    jest.useFakeTimers()
    const session = { session_id: 'panel-session-9', user: { id: 19, email: 'ana@example.com' } }
    mockPost
      .mockResolvedValueOnce({ challenge_id: 'challenge-email-3', detail: 'Código enviado.', retry_after: 30 })
      .mockResolvedValueOnce(session)
    const wrapper = mountLogin()
    await flushPromises()

    await requestCode(wrapper)
    await wrapper.get('[data-testid="access-code"]').setValue('123456')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(mockPost).toHaveBeenNthCalledWith(2, 'email-verify', {
      challenge_id: 'challenge-email-3', code: '123456', next: '/panel/inicio',
    })
    expect(wrapper.emitted('authenticated')).toEqual([[session]])
  })

  it('prepares Google with captcha nonce before verifying its credential', async () => {
    // Falla si Google se inicializa sin desafío captcha o verifica en otra operación.
    const initialize = jest.fn()
    const renderButton = jest.fn()
    window.google = { accounts: { id: { initialize, renderButton } } }
    const session = { session_id: 'google-session-2', user: { id: 22, email: 'ana@example.com' } }
    mockPost
      .mockResolvedValueOnce({ nonce: 'nonce-from-server' })
      .mockResolvedValueOnce(session)
    const wrapper = mountLogin()
    await flushPromises()

    await wrapper.get('[role="tab"][aria-selected="false"]').trigger('click')
    await wrapper.get('[data-testid="captcha-pass"]').trigger('click')
    await wrapper.get('[role="button"][type="button"]').trigger('click')
    await flushPromises()

    expect(mockPost).toHaveBeenNthCalledWith(1, 'google-challenge', { recaptcha_token: 'captcha-token' })
    expect(initialize).toHaveBeenCalledWith(expect.objectContaining({
      client_id: 'google-client-id', nonce: 'nonce-from-server', auto_select: false,
    }))

    const callback = initialize.mock.calls[0][0].callback
    await callback({ credential: 'credential-from-google' })
    await flushPromises()

    expect(mockPost).toHaveBeenNthCalledWith(2, 'google-verify', {
      credential: 'credential-from-google', next: '/panel/inicio',
    })
    expect(renderButton).toHaveBeenCalledTimes(1)
  })

  it('ignores a Google credential after switching methods', async () => {
    // Falla si un callback viejo de Google inicia sesión cuando la persona ya escogió código.
    const initialize = jest.fn()
    window.google = { accounts: { id: { initialize, renderButton: jest.fn() } } }
    mockPost.mockResolvedValueOnce({ nonce: 'nonce-for-stale-callback' })
    const wrapper = mountLogin()
    await flushPromises()

    await wrapper.get('[role="tab"][aria-selected="false"]').trigger('click')
    await wrapper.get('[data-testid="captcha-pass"]').trigger('click')
    await wrapper.get('[role="button"][type="button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[role="tab"][aria-selected="false"]').trigger('click')
    await initialize.mock.calls[0][0].callback({ credential: 'stale-credential' })
    await flushPromises()

    expect(mockPost).toHaveBeenCalledWith('google-challenge', { recaptcha_token: 'captcha-token' })
    expect(mockPost).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('authenticated')).toBeUndefined()
  })
})
