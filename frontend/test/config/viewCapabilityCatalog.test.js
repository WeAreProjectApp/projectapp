import {
  EXPLORER_SPACE_IDS,
  capabilityCatalogFindings,
  capabilityNodePath,
  capabilityViewRecords,
  descendantCapabilityViewUrls,
  explorerTourSteps,
  findCapabilityNode,
  flattenCapabilityCatalog,
  viewCapabilityCatalog,
} from '../../config/viewCapabilityCatalog'
import { countCatalogViews, viewCatalogSections } from '../../config/viewCatalog'

describe('viewCapabilityCatalog', () => {
  it('starts with the three product spaces', () => {
    expect(EXPLORER_SPACE_IDS).toEqual([
      'panel-internal',
      'client-platform',
      'public-experiences',
    ])
    expect(viewCapabilityCatalog.children.map((node) => node.label)).toEqual([
      'Panel interno',
      'Plataforma de clientes',
      'Experiencias públicas',
    ])
  })

  it('classifies every canonical view exactly once', () => {
    expect(capabilityCatalogFindings()).toEqual([])
    expect(descendantCapabilityViewUrls(viewCapabilityCatalog)).toHaveLength(
      countCatalogViews(viewCatalogSections),
    )
  })

  it('organizes the Panel into its main operational modules', () => {
    const panel = findCapabilityNode('panel-internal')

    expect(panel.children.map((node) => node.label)).toEqual([
      'Panorama y tareas',
      'Comercial',
      'Contenido',
      'Documentos y comunicaciones',
      'Proyectos',
      'Control financiero',
      'Integraciones',
      'Gobierno del sistema',
    ])
  })

  it('organizes the Platform into business capabilities', () => {
    const platform = findCapabilityNode('client-platform')

    expect(platform.children.map((node) => node.label)).toEqual([
      'Acceso y cuenta',
      'Clientes y proyectos',
      'Seguimiento del trabajo',
      'Entregables y recursos',
      'Documentos y aprobaciones',
      'Pagos, hosting y cobros',
      'Comunicación y notificaciones',
      'Administración de accesos',
    ])
  })

  it('organizes public content and commercial experiences', () => {
    const publicExperiences = findCapabilityNode('public-experiences')

    expect(publicExperiences.children.map((node) => node.label)).toEqual([
      'Marca y captación',
      'Contenido y prueba social',
      'Módulos adicionales',
      'Programa de Alianza',
      'Propuesta comercial',
      'Diagnóstico',
      'Enlaces seguros',
    ])
  })

  it('builds one guided step per main module', () => {
    expect(explorerTourSteps('panel-internal').map((node) => node.id)).toEqual([
      'panel-overview-work',
      'panel-commercial',
      'panel-content',
      'panel-documents-communications',
      'panel-projects',
      'panel-finance',
      'panel-integrations',
      'panel-governance',
    ])
  })

  it('resolves the breadcrumb path for a Panel submodule', () => {
    expect(capabilityNodePath('panel-editorial-content').map((node) => node.id)).toEqual([
      'projectapp',
      'panel-internal',
      'panel-content',
      'panel-editorial-content',
    ])
  })

  it('resolves technical references only from the canonical catalog', () => {
    const node = findCapabilityNode('platform-document-portal')

    expect(capabilityViewRecords(node)).toEqual([
      expect.objectContaining({
        label: 'Documentos del cliente',
        url: '/platform/documents',
      }),
    ])
  })

  it('gives every node a unique identifier', () => {
    const ids = flattenCapabilityCatalog().map((node) => node.id)

    expect(new Set(ids).size).toBe(ids.length)
  })
})
