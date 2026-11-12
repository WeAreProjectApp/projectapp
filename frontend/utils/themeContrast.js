import { hexToRgb } from './colorUtils'

const relativeLuminance = (hex) => {
  const { r, g, b } = hexToRgb(hex)
  return [r, g, b]
    .map((channel) => channel / 255)
    .map((channel) => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4)
    .reduce((sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index], 0)
}

export const contrastRatio = (foreground, background) => {
  const first = relativeLuminance(foreground)
  const second = relativeLuminance(background)
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05)
}

export const readableForeground = (background) => (
  contrastRatio('#000000', background) > contrastRatio('#ffffff', background) ? '#000000' : '#ffffff'
)

export const readableBrand = (color, shades, backgrounds, dark) => {
  const surfaces = Array.isArray(backgrounds) ? backgrounds : [backgrounds]
  const readable = (candidate) => surfaces.every((background) => contrastRatio(candidate, background) >= 4.5)
  if (readable(color)) return color
  const candidates = dark ? [...(shades || [])].reverse() : (shades || [])
  return candidates.find(readable) || readableForeground(surfaces[0])
}
