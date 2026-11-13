import { flushPromises, mount } from '@vue/test-utils';
import { ref } from 'vue';

import Workspace from '../../components/RequirementPackages/Workspace.vue';

const translations = {
  'requirementPackages.title': 'Paquetes de requerimientos',
  'requirementPackages.intro': 'Describe el resultado que necesitas.',
  'requirementPackages.refresh': 'Actualizar',
  'requirementPackages.balances': 'Tus cupos disponibles',
  'requirementPackages.sizes': 'Qué significa cada talla',
  'requirementPackages.projectExample': 'Ejemplo de tu proyecto',
  'requirementPackages.genericExample': 'Ejemplo general',
  'requirementPackages.outside': 'L, XL y Proyecto requieren una cotización independiente.',
  'requirementPackages.catalog': 'Comprar un paquete',
  'requirementPackages.emptyCatalog': 'No hay paquetes disponibles para este proyecto.',
  'requirementPackages.newRequest': 'Solicitar un cambio',
  'requirementPackages.requestTitle': 'Título del cambio',
  'requirementPackages.description': 'Qué resultado necesitas y en qué contexto',
  'requirementPackages.send': 'Enviar a evaluación',
  'requirementPackages.requests': 'Solicitudes',
  'requirementPackages.emptyRequests': 'Todavía no hay solicitudes.',
  'requirementPackages.orders': 'Compras',
  'requirementPackages.none': 'Sin registros',
  'requirementPackages.movements': 'Historial de cupos',
  'requirementPackages.noMovements': 'Todavía no hay movimientos.',
};
const originalUseI18n = global.useI18n;
const originalUseRoute = global.useRoute;

function overview() {
  return {
    is_admin: false,
    balances: { XS: 2, S: 1, M: 0 },
    examples: {
      sizes: [
        {
          size: 'XS',
          source: 'project',
          examples: ['Cambiar el saludo específico de este proyecto.'],
        },
        {
          size: 'S',
          source: 'generic',
          examples: ['Agregar una confirmación a una acción existente.'],
        },
      ],
    },
    catalog: [],
    requests: { count: 0, results: [] },
    orders: { count: 0, results: [] },
    movements: { count: 0, results: [] },
  };
}

describe('RequirementPackages Workspace examples', () => {
  let wrapper;

  beforeEach(() => {
    global.useI18n = () => ({
      t: (key) => translations[key] || key,
      locale: ref('es-CO'),
    });
    global.useRoute = () => ({ query: {} });
  });

  afterEach(() => {
    wrapper?.unmount();
    wrapper = null;
    global.useI18n = originalUseI18n;
    global.useRoute = originalUseRoute;
  });

  // Falla si personalizar XS oculta o etiqueta mal el ejemplo genérico que todavía debe aparecer en S.
  it('labels each rendered size with the source of its effective examples', async () => {
    const api = {
      overview: jest.fn().mockResolvedValue(overview()),
    };
    wrapper = mount(Workspace, {
      props: { api },
      global: {
        stubs: {
          BaseButton: {
            props: ['disabled'],
            emits: ['click'],
            template: '<button v-bind="$attrs" :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
          },
          ExampleEditor: true,
          RequestDetail: true,
        },
      },
    });
    await flushPromises();

    expect(api.overview).toHaveBeenCalledWith('es', {
      order_offset: 0,
      request_offset: 0,
      movement_offset: 0,
    });
    expect(wrapper.get('[data-testid="package-size-XS"]').text()).toContain(
      'Ejemplo de tu proyecto',
    );
    expect(wrapper.get('[data-testid="package-size-XS"]').text()).toContain(
      'Cambiar el saludo específico de este proyecto.',
    );
    expect(wrapper.get('[data-testid="package-size-S"]').text()).toContain(
      'Ejemplo general',
    );
    expect(wrapper.get('[data-testid="package-size-S"]').text()).toContain(
      'Agregar una confirmación a una acción existente.',
    );
  });

  // Falla si una segunda notificación del proyecto conserva abierta la solicitud anterior.
  it('replaces the visible request detail when the initial request changes', async () => {
    const api = {
      overview: jest.fn().mockResolvedValue(overview()),
      request: jest
        .fn()
        .mockResolvedValueOnce({
          id: 701,
          title: 'Solicitud inicial',
          description: 'Detalle de la primera notificación.',
        })
        .mockResolvedValueOnce({
          id: 702,
          title: 'Solicitud más reciente',
          description: 'Detalle de la segunda notificación.',
        }),
    };
    wrapper = mount(Workspace, {
      props: { api, initialRequest: 701 },
      global: {
        stubs: {
          BaseButton: {
            props: ['disabled'],
            emits: ['click'],
            template: '<button v-bind="$attrs" :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
          },
          ExampleEditor: true,
          RequestDetail: {
            props: ['row'],
            template: '<section :data-testid="`selected-request-${row.id}`">{{ row.title }} · {{ row.description }}</section>',
          },
        },
      },
    });
    await flushPromises();

    expect(wrapper.get('[data-testid="selected-request-701"]').text()).toBe(
      'Solicitud inicial · Detalle de la primera notificación.',
    );

    await wrapper.setProps({ initialRequest: 702 });
    await flushPromises();

    expect(wrapper.get('[data-testid="selected-request-702"]').text()).toBe(
      'Solicitud más reciente · Detalle de la segunda notificación.',
    );
    expect(wrapper.findAll('[data-testid="selected-request-701"]')).toHaveLength(0);
  });
});
