import catalog from '../../contracts/platform-features.json'

export { catalog as platformFeatureCatalog }

export function platformPath(path) {
  return path.split(/[?#]/)[0].replace(/^\/[a-z]{2}(?:-[a-z]{2})?(?=\/)/i, '').replace(/\/$/, '')
}

export function matchesFeatureRoute(pattern, path) {
  const expression = pattern.split('/').map(part => part.startsWith(':') ? '[^/]+' : part).join('/')
  return new RegExp(`^${expression}$`).test(platformPath(path))
}

export function featureForRoute(path) {
  return catalog.features.find(item => item.routes.some(pattern => matchesFeatureRoute(pattern, path)))?.key
}

export function featureForTarget(target) {
  return catalog.features.find(item => item.targets.includes(target))?.key
}

