/** Measure rendered sRGB text over its composed, solid ancestor backgrounds. */
export async function textContrast(locator, { placeholder = false } = {}) {
  await locator.evaluate(async (element) => {
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const animations = new Set();
    for (let ancestor = element; ancestor; ancestor = ancestor.parentElement) {
      ancestor.getAnimations().filter((animation) => (
        animation.effect?.getTiming().iterations !== Infinity
      )).forEach((animation) => animations.add(animation));
    }
    await Promise.allSettled([...animations].map((animation) => animation.finished));
  });
  return locator.evaluate((element, usePlaceholder) => {
    const rgba = (value) => {
      const channels = value.match(/[\d.]+/g).map(Number);
      return [...channels.slice(0, 3), channels[3] ?? 1];
    };
    const composite = (foreground, background) => {
      const alpha = foreground[3] + background[3] * (1 - foreground[3]);
      return [0, 1, 2].map((index) => (
        foreground[index] * foreground[3]
        + background[index] * background[3] * (1 - foreground[3])
      ) / alpha).concat(alpha);
    };
    const luminance = (color) => color.slice(0, 3)
      .map((channel) => channel / 255)
      .map((channel) => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4)
      .reduce((sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index], 0);
    const layers = [];
    let opacity = 1;
    for (let ancestor = element; ancestor; ancestor = ancestor.parentElement) {
      const style = getComputedStyle(ancestor);
      if (style.backgroundImage !== 'none') {
        throw new Error('Use a solid fixture surface to measure text contrast.');
      }
      layers.unshift(rgba(style.backgroundColor));
      opacity *= Number(style.opacity);
    }
    const background = layers.reduce((color, layer) => composite(layer, color), [255, 255, 255, 1]);
    const foreground = rgba(getComputedStyle(element, usePlaceholder ? '::placeholder' : null).color);
    foreground[3] *= opacity;
    const ink = luminance(composite(foreground, background));
    const canvas = luminance(background);
    return (Math.max(ink, canvas) + 0.05) / (Math.min(ink, canvas) + 0.05);
  }, placeholder);
}
