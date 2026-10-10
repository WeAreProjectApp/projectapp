import { useBuildingWithUsTheme } from '../../composables/useBuildingWithUsTheme'

describe('useBuildingWithUsTheme', () => {
  beforeEach(() => window.localStorage.clear())
  afterEach(() => window.localStorage.clear())

  it('starts with the light theme', () => {
    const { theme } = useBuildingWithUsTheme()

    expect(theme.value).toBe('light')
  })

  it('loads its own saved theme', () => {
    window.localStorage.setItem('projectapp-building-with-us-theme', 'dark')
    window.localStorage.setItem('projectapp-financing-theme', 'light')

    const { isDark } = useBuildingWithUsTheme()

    expect(isDark.value).toBe(true)
  })

  it('saves a dark theme after toggling', () => {
    const { isDark, toggle } = useBuildingWithUsTheme()

    toggle()

    expect(isDark.value).toBe(true)
    expect(window.localStorage.getItem('projectapp-building-with-us-theme')).toBe('dark')
  })

  it('restores the light theme after a second toggle', () => {
    const { theme, toggle } = useBuildingWithUsTheme()

    toggle()
    toggle()

    expect(theme.value).toBe('light')
    expect(window.localStorage.getItem('projectapp-building-with-us-theme')).toBe('light')
  })
})
