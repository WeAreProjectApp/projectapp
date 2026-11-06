import {
  PANEL_BREAKPOINTS,
  PANEL_CONTENT_MAX_PX,
  PANEL_SCREENS,
} from './config/responsive.js'

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./components/**/*.{vue,js,ts,jsx,tsx}",
    "./layouts/**/*.{vue,js,ts,jsx,tsx}",
    "./pages/**/*.{vue,js,ts,jsx,tsx}",
    "./plugins/**/*.{js,ts}",
    // utils/ holds shared class literals (see utils/tableLayout.js); without
    // this glob the JIT purges them and the tables lose their padding.
    "./utils/**/*.{js,ts}",
    "./app.vue",
  ],
  theme: {
    extend: {
      // Panel-specific aliases derived from the five real PA-75 devices.
      // Existing sm/md/lg classes remain available for legacy/public UI.
      screens: {
        [PANEL_SCREENS.portrait]: `${PANEL_BREAKPOINTS.portrait}px`,
        [PANEL_SCREENS.landscape]: `${PANEL_BREAKPOINTS.landscape}px`,
        [PANEL_SCREENS.desktop]: `${PANEL_BREAKPOINTS.desktop}px`,
        [PANEL_SCREENS.wide]: `${PANEL_BREAKPOINTS.wide}px`,
      },
      maxWidth: {
        panel: `${PANEL_CONTENT_MAX_PX}px`,
      },
      fontFamily: {
        'bold': ['Ubuntu-Bold', 'sans-serif'],
        'medium': ['Ubuntu-Medium', 'sans-serif'],
        'regular': ['Ubuntu-Regular', 'sans-serif'],
        'light': ['Ubuntu-Light', 'sans-serif'],
        'bolditalic': ['Ubuntu-BoldItalic', 'sans-serif'],
        'mediumitalic': ['Ubuntu-MediumItalic', 'sans-serif'],
        'italic': ['Ubuntu-Italic', 'sans-serif'],
        'lightitalic': ['Ubuntu-LightItalic', 'sans-serif'],
        'caveat-regular': ['Caveat-Regular', 'cursive'],
        'caveat-medium': ['Caveat-Medium', 'cursive'],
        'caveat-semibold': ['Caveat-SemiBold', 'cursive'],
        'caveat-bold': ['Caveat-Bold', 'cursive'],
      },
      colors: {
        // -----------------------------------------------------------------
        // Legacy hex tokens — DEPRECATED for new code.
        // Kept because of ~3000 usages across the public site (proposal,
        // blog, portfolio, landings) and ~360 in the panel that still use
        // opacity modifiers like `bg-esmerald/40`. Removing them would
        // require migrating every single one in lockstep — too risky.
        //
        // For new code: use the semantic tokens below (`primary`, `accent`,
        // `surface`, `text-default`, etc.). The lint guard at
        // `scripts/check-design-tokens.mjs` flags new usage of these.
        //
        // Future cleanup path: redefine these as
        // `rgb(var(--color-X-rgb) / <alpha-value>)` once the panel's offense
        // count drops enough to coordinate the migration.
        // -----------------------------------------------------------------
        'window-black': '#191919',
        'esmerald-light': '#E6EFEF',
        'esmerald': '#002921',
        'esmerald-dark': '#001713',
        'green-light' : '#809490',
        'lemon': '#F0FF3D',
        'bone': '#FAF3E0',
        'brown': '#623721',
        'black': '#121212',
        'dark' : '#000000',

        // Semantic tokens — bound to CSS vars in assets/styles/theme.css.
        // These auto-resolve light/dark, so prefer `bg-surface` over
        // `bg-white dark:bg-gray-800`. Legacy hex tokens above stay for
        // backwards-compat while views migrate incrementally.
        //
        // Tokens use the `rgb(var(--color-X-rgb) / <alpha-value>)` bridge
        // so Tailwind opacity modifiers work on every semantic token:
        //   bg-primary/40, text-text-brand/60, ring-focus-ring/30, etc.
        //
        // Solid tokens use the RGB triplet bridge so Tailwind opacity
        // modifiers compose correctly (`bg-primary/40`, `text-text-brand/60`).
        //
        // Alpha-baked tokens (surface-raised, border-default, border-muted,
        // input-border, primary-soft, *-soft status variants) are
        // intrinsically `rgba()` in dark mode — see theme.css. They route
        // through `var(--color-X)` directly to preserve the baked alpha;
        // the `/N` modifier syntax is intentionally NOT supported on these.
        'primary': 'rgb(var(--color-primary-rgb) / <alpha-value>)',
        'primary-strong': 'rgb(var(--color-primary-strong-rgb) / <alpha-value>)',
        'primary-soft': 'var(--color-primary-soft)',
        'accent': 'rgb(var(--color-accent-rgb) / <alpha-value>)',
        'accent-mid': 'rgb(var(--color-accent-mid-rgb) / <alpha-value>)',
        'accent-soft': 'rgb(var(--color-accent-soft-rgb) / <alpha-value>)',
        'surface': 'rgb(var(--color-surface-rgb) / <alpha-value>)',
        'surface-muted': 'rgb(var(--color-surface-muted-rgb) / <alpha-value>)',
        'surface-raised': 'var(--color-surface-raised)',
        'border-default': 'var(--color-border)',
        'border-muted': 'var(--color-border-muted)',
        'text-default': 'rgb(var(--color-text-rgb) / <alpha-value>)',
        'text-muted': 'rgb(var(--color-text-muted-rgb) / <alpha-value>)',
        'text-subtle': 'rgb(var(--color-text-subtle-rgb) / <alpha-value>)',
        'text-brand': 'rgb(var(--color-text-brand-rgb) / <alpha-value>)',
        'input-bg': 'rgb(var(--color-input-bg-rgb) / <alpha-value>)',
        'input-border': 'var(--color-input-border)',
        'input-text': 'rgb(var(--color-input-text-rgb) / <alpha-value>)',
        'input-placeholder': 'rgb(var(--color-input-placeholder-rgb) / <alpha-value>)',
        'focus-ring': 'rgb(var(--color-focus-ring-rgb) / <alpha-value>)',
        // "on-X" tokens: foreground color intended to sit on top of `bg-X`.
        // Useful for buttons / pills where the content needs guaranteed
        // contrast against the brand or status surface.
        'on-primary': 'rgb(var(--color-on-primary-rgb) / <alpha-value>)',
        'on-accent': 'rgb(var(--color-on-accent-rgb) / <alpha-value>)',
        'on-danger': 'rgb(var(--color-on-danger-rgb) / <alpha-value>)',
        'success-soft': 'var(--color-success-soft)',
        'success-strong': 'rgb(var(--color-success-strong-rgb) / <alpha-value>)',
        'warning-soft': 'var(--color-warning-soft)',
        'warning-strong': 'rgb(var(--color-warning-strong-rgb) / <alpha-value>)',
        'danger-soft': 'var(--color-danger-soft)',
        'danger-strong': 'rgb(var(--color-danger-strong-rgb) / <alpha-value>)',
        'info-soft': 'var(--color-info-soft)',
        'info-strong': 'rgb(var(--color-info-strong-rgb) / <alpha-value>)',
      },
      // Elevation scale bound to theme.css vars (adjusted per mode).
      // card → cards/panels; raised → dropdowns/popovers/floating; overlay →
      // modals/drawers. Pair shadow-reliant surfaces with border-border-default.
      boxShadow: {
        'card': 'var(--shadow-card)',
        'raised': 'var(--shadow-raised)',
        'overlay': 'var(--shadow-overlay)',
      },
      // Meta text one step below text-xs (replaces ad-hoc text-[10px]/[11px]).
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
        'panel-meta': ['0.75rem', { lineHeight: '1rem' }],
        'panel-control': ['0.875rem', { lineHeight: '1.25rem' }],
        'panel-body': ['1rem', { lineHeight: '1.5rem' }],
        'panel-section': ['clamp(1.125rem, 1.05rem + 0.2vw, 1.25rem)', { lineHeight: '1.75rem' }],
        'panel-title': ['clamp(1.5rem, 1.35rem + 0.4vw, 1.875rem)', { lineHeight: '2.25rem' }],
      },
      // Motion scale: fast → hovers/toggles; base → collapses/tab panels;
      // slow → progress bars/large reveals. Pair with motion-safe: variants.
      transitionDuration: {
        fast: '150ms',
        base: '250ms',
        slow: '400ms',
      },
      transitionTimingFunction: {
        'out-soft': 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
      animation: {
        first: "moveVertical 30s ease infinite",
        second: "moveInCircle 20s reverse infinite",
        third: "moveInCircle 40s linear infinite",
        fourth: "moveHorizontal 40s ease infinite",
        fifth: "moveInCircle 20s ease infinite",
      },
      keyframes: {
        moveHorizontal: {
          "0%": {
            transform: "translateX(-50%) translateY(-10%)",
          },
          "50%": {
            transform: "translateX(50%) translateY(10%)",
          },
          "100%": {
            transform: "translateX(-50%) translateY(-10%)",
          },
        },
        moveInCircle: {
          "0%": {
            transform: "rotate(0deg)",
          },
          "50%": {
            transform: "rotate(180deg)",
          },
          "100%": {
            transform: "rotate(360deg)",
          },
        },
        moveVertical: {
          "0%": {
            transform: "translateY(-50%)",
          },
          "50%": {
            transform: "translateY(50%)",
          },
          "100%": {
            transform: "translateY(-50%)",
          },
        },
      },
    },
  },
  plugins: [],
}
