/**
 * Tests for usePlatformCustomTheme composable.
 */

const mockAuthStore = {
  user: null,
  updateProfile: jest.fn().mockResolvedValue({ success: true }),
}

jest.mock('../../stores/platform-auth', () => ({
  usePlatformAuthStore: () => mockAuthStore,
}))

const mockRequest = jest.fn()

jest.mock('../../composables/usePlatformApi', () => ({
  usePlatformApi: () => ({ request: mockRequest }),
}))

describe('usePlatformCustomTheme', () => {
  let usePlatformCustomTheme
  const originalImage = global.Image

  beforeEach(() => {
    jest.resetModules()
    mockAuthStore.user = null
    mockAuthStore.updateProfile.mockClear().mockResolvedValue({ success: true })
    mockRequest.mockReset()
    document.documentElement.removeAttribute('style')
    usePlatformCustomTheme = require('../../composables/usePlatformCustomTheme').usePlatformCustomTheme
  })

  afterEach(() => {
    global.Image = originalImage
  })

  it('hydrate copies user theme fields once', () => {
    mockAuthStore.user = {
      theme_color: '#2874f3',
      cover_image: 'x.jpg',
      custom_cover_image: '',
    }
    const theme = usePlatformCustomTheme()
    theme.hydrate()
    expect(theme.themeColor.value).toBe('#2874f3')
    expect(theme.coverImage.value).toBe('x.jpg')
  })

  it('hydrate skips re-run when already initialized', () => {
    mockAuthStore.user = { theme_color: '#2874f3', cover_image: '', custom_cover_image: '' }
    const theme = usePlatformCustomTheme()
    theme.hydrate()
    mockAuthStore.user = { theme_color: '#000000', cover_image: '', custom_cover_image: '' }
    theme.hydrate()
    expect(theme.themeColor.value).toBe('#2874f3')
  })

  it('applyTheme sets CSS variables for palette color', () => {
    const theme = usePlatformCustomTheme()
    theme.themeColor.value = '#2874f3'
    theme.applyTheme()
    expect(document.documentElement.style.getPropertyValue('--theme-color')).toBe('#2874f3')
  })

  it('applyTheme uses fallback rgba when hex not in palette', () => {
    const theme = usePlatformCustomTheme()
    theme.themeColor.value = '#aabbcc'
    theme.applyTheme()
    expect(document.documentElement.style.getPropertyValue('--theme-surface')).toContain('rgba')
  })

  it('applyTheme removes vars when color cleared', () => {
    const theme = usePlatformCustomTheme()
    theme.themeColor.value = '#2874f3'
    theme.applyTheme()
    theme.themeColor.value = ''
    theme.applyTheme()
    expect(document.documentElement.style.getPropertyValue('--theme-color')).toBe('')
  })

  it('setThemeColor updates profile', async () => {
    const theme = usePlatformCustomTheme()
    await theme.setThemeColor('#2874f3')
    expect(mockAuthStore.updateProfile).toHaveBeenCalledWith({ theme_color: '#2874f3' })
  })

  it('setCoverImage replaces the uploaded cover', async () => {
    const theme = usePlatformCustomTheme()
    theme.customCoverImageUrl.value = 'https://old'
    await theme.setCoverImage('n.jpg')
    expect(theme.coverImage.value).toBe('n.jpg')
    expect(theme.customCoverImageUrl.value).toBe('')
    expect(mockAuthStore.updateProfile).toHaveBeenCalledWith({ cover_image: 'n.jpg', custom_cover_image: null })
  })

  it('setCustomCoverImage updates user from response', async () => {
    mockRequest.mockResolvedValueOnce({
      data: { id: 1, custom_cover_image: 'https://cdn/x.png', cover_image: '' },
    })
    const theme = usePlatformCustomTheme()
    const file = new File(['b'], 'c.png', { type: 'image/png' })
    await theme.setCustomCoverImage(file)
    expect(mockRequest).toHaveBeenCalled()
    expect(theme.customCoverImageUrl.value).toBe('https://cdn/x.png')
    expect(mockAuthStore.user.custom_cover_image).toBe('https://cdn/x.png')
  })

  it('clearCover removes both saved cover sources', async () => {
    const theme = usePlatformCustomTheme()
    theme.coverImage.value = 'a.jpg'
    theme.customCoverImageUrl.value = 'https://u'
    await theme.clearCover()
    expect(mockAuthStore.updateProfile).toHaveBeenCalledWith({ cover_image: '', custom_cover_image: null })
    expect(theme.coverImage.value).toBe('')
    expect(theme.customCoverImageUrl.value).toBe('')
    expect(theme.isCoverDark.value).toBe(false)
  })

  it('clearAll resets theme and cover', async () => {
    const theme = usePlatformCustomTheme()
    theme.themeColor.value = '#2874f3'
    theme.coverImage.value = 'x.jpg'
    await theme.clearAll()
    expect(theme.themeColor.value).toBe('')
    expect(theme.coverImage.value).toBe('')
  })

  it('computed hasTheme reflects themeColor', () => {
    const theme = usePlatformCustomTheme()
    expect(theme.hasTheme.value).toBe(false)
    theme.themeColor.value = '#2874f3'
    expect(theme.hasTheme.value).toBe(true)
  })

  it('computed hasCover reflects cover fields', () => {
    const theme = usePlatformCustomTheme()
    theme.coverImage.value = 'a.jpg'
    expect(theme.hasCover.value).toBe(true)
  })

  it('setCoverImage marks cover dark when sampled brightness is low', async () => {
    const origImage = global.Image
    global.Image = class {
      set onload(fn) {
        this._on = fn
      }

      set onerror(_fn) {}

      set src(_v) {
        queueMicrotask(() => this._on())
      }
    }
    const origCreate = document.createElement.bind(document)
    jest.spyOn(document, 'createElement').mockImplementation((tag) => {
      if (tag === 'canvas') {
        return {
          width: 64,
          height: 64,
          getContext: () => ({
            drawImage: jest.fn(),
            getImageData: () => ({ data: new Uint8ClampedArray(64 * 64 * 4).fill(5) }),
          }),
        }
      }
      return origCreate(tag)
    })
    const theme = usePlatformCustomTheme()
    await theme.setCoverImage('dark.jpg')
    await Promise.resolve()
    await Promise.resolve()
    expect(theme.isCoverDark.value).toBe(true)
    document.createElement.mockRestore()
    global.Image = origImage
  })

  it('setThemeColor ignores updateProfile rejection', async () => {
    mockAuthStore.updateProfile.mockRejectedValueOnce(new Error('net'))
    const theme = usePlatformCustomTheme()
    await expect(theme.setThemeColor('#2874f3')).resolves.toBeUndefined()
  })

  it('hydrate skips copying theme fields when user is null', () => {
    mockAuthStore.user = null
    const theme = usePlatformCustomTheme()
    theme.hydrate()
    expect(theme.themeColor.value).toBe('')
    expect(theme.coverImage.value).toBe('')
  })

  it('hydrate uses empty string when user theme_color is undefined', () => {
    mockAuthStore.user = { cover_image: 'x.jpg', custom_cover_image: '' }
    const theme = usePlatformCustomTheme()
    theme.hydrate()
    expect(theme.themeColor.value).toBe('')
  })

  it('hydrate sets customCoverImageUrl when user custom_cover_image is truthy', () => {
    mockAuthStore.user = {
      theme_color: '',
      cover_image: '',
      custom_cover_image: 'https://cdn/img.png',
    }
    const theme = usePlatformCustomTheme()
    theme.hydrate()
    expect(theme.customCoverImageUrl.value).toBe('https://cdn/img.png')
  })

  it('applyTheme clears vars when color string has wrong length', () => {
    const theme = usePlatformCustomTheme()
    theme.themeColor.value = '#abc'
    theme.applyTheme()
    expect(document.documentElement.style.getPropertyValue('--theme-color')).toBe('')
  })

  it('measureBrightness resolves to 128 when image fails to load', async () => {
    global.Image = class {
      set onload(_fn) {}

      set onerror(fn) {
        this._err = fn
      }

      set src(_v) {
        queueMicrotask(() => this._err())
      }
    }
    const theme = usePlatformCustomTheme()
    await theme.setCoverImage('broken.jpg')
    await Promise.resolve()
    await Promise.resolve()
    expect(theme.isCoverDark.value).toBe(false)
  })

  it('applyTheme uses dark button text for light primary color', () => {
    const theme = usePlatformCustomTheme()
    theme.themeColor.value = '#ffffff'
    theme.applyTheme()
    expect(document.documentElement.style.getPropertyValue('--theme-btn-text')).toBe('#000000')
  })

  it('setCustomCoverImage does not update state when response has no data', async () => {
    mockRequest.mockResolvedValueOnce({ data: null })
    const theme = usePlatformCustomTheme()
    theme.customCoverImageUrl.value = 'https://old'
    await theme.setCustomCoverImage(new File(['b'], 'c.png', { type: 'image/png' }))
    expect(theme.customCoverImageUrl.value).toBe('https://old')
  })

  it('setCustomCoverImage sets empty string when custom_cover_image is missing in response', async () => {
    mockRequest.mockResolvedValueOnce({
      data: { id: 1, cover_image: '' },
    })
    const theme = usePlatformCustomTheme()
    await theme.setCustomCoverImage(new File(['b'], 'c.png', { type: 'image/png' }))
    expect(theme.customCoverImageUrl.value).toBe('')
  })

  it('setCustomCoverImage silently ignores request failure', async () => {
    mockRequest.mockRejectedValueOnce(new Error('upload failed'))
    const theme = usePlatformCustomTheme()
    theme.customCoverImageUrl.value = 'https://old'
    await expect(theme.setCustomCoverImage(new File(['b'], 'c.png', { type: 'image/png' }))).resolves.toBeUndefined()
    expect(theme.customCoverImageUrl.value).toBe('https://old')
  })

  it('setCustomCoverImage skips state update when response has no data', async () => {
    mockRequest.mockResolvedValueOnce({})
    const theme = usePlatformCustomTheme()
    theme.customCoverImageUrl.value = 'previous'
    const file = new File(['b'], 'c.png', { type: 'image/png' })
    await theme.setCustomCoverImage(file)
    expect(theme.customCoverImageUrl.value).toBe('previous')
  })

  it('hydrate calls detectCoverBrightness with empty url when no cover set', () => {
    mockAuthStore.user = null
    const theme = usePlatformCustomTheme()
    theme.hydrate()
    expect(theme.isCoverDark.value).toBe(false)
  })

  it('setCoverImage ignores updateProfile rejection', async () => {
    mockAuthStore.updateProfile.mockRejectedValueOnce(new Error('net'))
    const theme = usePlatformCustomTheme()
    await expect(theme.setCoverImage('x.jpg')).resolves.toBeUndefined()
  })

  it('clearCover preserves the cover on request failure', async () => {
    mockAuthStore.updateProfile.mockRejectedValueOnce(new Error('net'))
    const theme = usePlatformCustomTheme()
    theme.customCoverImageUrl.value = 'https://cdn/saved.png'

    await expect(theme.clearCover()).resolves.toBeUndefined()

    expect(theme.customCoverImageUrl.value).toBe('https://cdn/saved.png')
  })

  it.each([
    ['clearCover', (theme) => theme.clearCover()],
    ['setCoverImage', (theme) => theme.setCoverImage('gallery.jpg')],
  ])('%s preserves the cover when the profile store rejects the update', async (_name, action) => {
    mockAuthStore.updateProfile.mockResolvedValueOnce({ success: false, message: 'No pudimos actualizar tu perfil.' })
    const theme = usePlatformCustomTheme()
    theme.customCoverImageUrl.value = 'https://cdn/saved.png'

    await action(theme)

    expect(theme.customCoverImageUrl.value).toBe('https://cdn/saved.png')
    expect(theme.hasCover.value).toBe(true)
  })

  it('clearAll ignores updateProfile rejection', async () => {
    mockAuthStore.updateProfile.mockRejectedValueOnce(new Error('net'))
    const theme = usePlatformCustomTheme()
    theme.themeColor.value = '#ff0000'
    await expect(theme.clearAll()).resolves.toBeUndefined()
    expect(theme.themeColor.value).toBe('')
  })

  it('hasCover reflects customCoverImageUrl when coverImage is empty', () => {
    const theme = usePlatformCustomTheme()
    theme.coverImage.value = ''
    theme.customCoverImageUrl.value = 'https://cdn/custom.jpg'
    expect(theme.hasCover.value).toBe(true)
  })

  it('isCustomized is false when neither theme nor cover is set', () => {
    const theme = usePlatformCustomTheme()
    expect(theme.isCustomized.value).toBe(false)
  })

  it('isCustomized is true when only hasCover is set', () => {
    const theme = usePlatformCustomTheme()
    theme.themeColor.value = ''
    theme.coverImage.value = 'a.jpg'
    expect(theme.isCustomized.value).toBe(true)
  })

  it('isCustomized becomes true when themeColor is set', () => {
    const theme = usePlatformCustomTheme()
    theme.themeColor.value = '#2874f3'
    expect(theme.isCustomized.value).toBe(true)
  })
})
