() => {
  const issues = [];
  const texts = [];
  const nodes = [document.body, ...document.body.querySelectorAll('*')];
  const add = (code, message, element) => issues.push({ severity: 'error', code, message, file: 'template.html', line: Number(element?.dataset.templateLine || 1), node: element?.dataset.templateNode || null });
  const visible = (el) => {
    const css = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return css.display !== 'none' && css.visibility === 'visible' && rect.width > 0 && rect.height > 0 && !el.closest('[hidden]');
  };
  if (nodes.length > 2000) add('complexity', 'La plantilla supera 2000 elementos.', document.body);
  if (document.documentElement.scrollHeight > 12000) add('page_height', 'La página supera 12000 px de alto.', document.body);
  if (innerWidth === 320 && document.documentElement.scrollWidth > 321) add('overflow', 'Hay desbordamiento horizontal a 320 px.', document.body);
  for (const el of nodes) {
    if (!visible(el)) continue;
    const rect = el.getBoundingClientRect();
    const css = getComputedStyle(el);
    if (el.matches('a[data-link], [data-action]') && (rect.width < 44 || rect.height < 44)) add('touch_target', 'El área tocable debe medir al menos 44 × 44 px.', el);
    for (const pseudo of ['::before', '::after']) {
      const content = getComputedStyle(el, pseudo).content;
      if (content && !['none', 'normal', '""', "''"].includes(content)) add('generated_text', 'Usa texto HTML para que se pueda comprobar su contraste; no generes texto con CSS.', el);
    }
    // Transparent text, hidden text and filters cannot buy a false contrast pass.
    for (const node of [...el.childNodes]) {
      if (node.nodeType !== Node.TEXT_NODE || !node.textContent.trim()) continue;
      const range = document.createRange(); range.selectNodeContents(node);
      const rects = [...range.getClientRects()].map((r) => ({ x: r.x, y: r.y + scrollY, width: r.width, height: r.height }));
      if (!rects.some((r) => r.width && r.height)) continue;
      let opacity = 1;
      let ambiguous = false;
      for (let ancestor = el; ancestor; ancestor = ancestor.parentElement) {
        const style = getComputedStyle(ancestor);
        opacity *= Number(style.opacity);
        if (style.mixBlendMode !== 'normal' || style.filter !== 'none' || style.backdropFilter !== 'none') ambiguous = true;
      }
      const foreground = css.webkitTextFillColor || css.color;
      const color = foreground.match(/[\d.]+/g)?.map(Number);
      if (!foreground.startsWith('rgb') || ambiguous) add('contrast_unverifiable', 'No se puede certificar el contraste de este texto con filtros, mezcla o colores no RGB.', el);
      else texts.push({ rects, color, opacity, threshold: /^H[1-6]$/.test(el.tagName) && parseFloat(css.fontSize) >= 24 ? 3 : 4.5, node: el.dataset.templateNode, line: Number(el.dataset.templateLine || 1) });
      // The wrapper hides only glyphs for background sampling; parent colors and
      // backgrounds (including gradients/textures/currentColor) stay unchanged.
      const span = document.createElement('span');
      span.setAttribute('data-contrast-glyph', '');
      span.style.setProperty('display', 'contents', 'important');
      node.replaceWith(span); span.append(node);
    }
  }
  const animations = document.getAnimations().filter((a) => a.effect?.target && visible(a.effect.target));
  const animated = new Set(animations.map((a) => a.effect.target));
  if (animated.size > 6) add('animation_count', 'Hay más de 6 elementos animados simultáneamente.', document.body);
  for (const animation of animations) {
    const el = animation.effect.target;
    const timing = animation.effect.getTiming();
    const frames = animation.effect.getKeyframes();
    const properties = new Set(frames.flatMap((f) => Object.keys(f)).filter((k) => !['offset', 'computedOffset', 'easing', 'composite'].includes(k)));
    if ([...properties].some((p) => !['transform', 'opacity'].includes(p))) add('animation_property', 'Sólo se pueden animar transform y opacity.', el);
    if ((timing.iterations === Infinity || timing.iterations > 1) && (el.textContent.trim() || el.matches('a,button') || el.querySelector('a,button'))) add('continuous_text', 'No se permite animación continua en textos o botones.', el);
    // Conservative cycle bound also covers transform-based flashing; easing
    // steps cannot turn a permitted duration into >3 changes per second.
    const steps = Math.max(2, frames.length - 1, ...frames.map((f) => Number(/steps\((\d+)/.exec(f.easing)?.[1] || 0)));
    const timingSteps = Number(/steps\((\d+)/.exec(timing.easing)?.[1] || 0);
    if (!Number.isFinite(Number(timing.duration)) || Number(timing.duration) < Math.max(steps, timingSteps) * 1000 / 3) add('flash_rate', 'La animación cambia más de 3 veces por segundo.', el);
  }
  return { issues, texts, animated: animated.size };
}
