/**
 * Tests for DocumentActionsSheet.vue.
 *
 * Covers: visibility (modelValue / document), header (title + client),
 * actions list rendering with "Editar contenido" first, per-action emits
 * plus auto-close, danger styling for delete, and the Cancelar close.
 */

import { mount } from '@vue/test-utils';
import DocumentActionsSheet from '../../components/panel/documents/DocumentActionsSheet.vue';
import BaseActionIcon from '../../components/base/BaseActionIcon.vue';

const baseDocument = { id: 7, title: 'Contrato de Servicios', client_name: 'ACME Corp' };

function mountSheet(props = {}) {
  return mount(DocumentActionsSheet, {
    props: { modelValue: true, document: baseDocument, ...props },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        // BaseButton se registra global en jest.setup y declara NuxtLink como
        // variante; sin este stub Vue avisa que no la resuelve.
        NuxtLink: { template: '<a :href="to" v-bind="$attrs"><slot /></a>', props: ['to'] },
      },
    },
  });
}

// Los botones de acción son los que viven en la lista `.p-2` (excluye la X y "Cancelar").
function actionButtons(wrapper) {
  return wrapper.findAll('.p-2 button');
}

function actionByLabel(wrapper, label) {
  return actionButtons(wrapper).find((btn) => btn.text().includes(label));
}

describe('DocumentActionsSheet', () => {
  describe('visibility', () => {
    it('does not render content when modelValue is false', () => {
      // quality: allow-negation-only (a closed teleported sheet intentionally renders no content)
      const wrapper = mountSheet({ modelValue: false });

      expect(wrapper.text()).not.toContain('Contrato de Servicios');
    });

    it('does not render content when document is null', () => {
      // quality: allow-negation-only (a sheet without a target intentionally renders no content)
      const wrapper = mountSheet({ document: null });

      expect(wrapper.text()).not.toContain('Renombrar');
    });
  });

  describe('header', () => {
    it('renders the document title', () => {
      const wrapper = mountSheet();

      expect(wrapper.text()).toContain('Contrato de Servicios');
    });

    it('renders the client name when present', () => {
      const wrapper = mountSheet();

      expect(wrapper.text()).toContain('ACME Corp');
    });
  });

  describe('actions list', () => {
    it('renders every action label', () => {
      const wrapper = mountSheet();
      const labels = [
        'Editar contenido', 'Hilo de documentos', 'Renombrar', 'Mover a carpeta', 'Enviar por correo',
        'Descargar PDF', 'Copiar markdown', 'Duplicar', 'Eliminar',
      ];

      const rendered = actionButtons(wrapper).map(button => button.text());
      expect(rendered).toEqual(expect.arrayContaining(
        labels.map(label => expect.stringContaining(label)),
      ));
    });

    it('lists "Editar contenido" as the first action', () => {
      const wrapper = mountSheet();

      expect(actionButtons(wrapper).at(0).text()).toContain('Editar contenido');
    });

    it('renders copy and duplicate with distinct catalog actions', () => {
      const wrapper = mountSheet();

      expect(actionByLabel(wrapper, 'Copiar markdown').findComponent(BaseActionIcon).props('action')).toBe('copy');
      expect(actionByLabel(wrapper, 'Duplicar').findComponent(BaseActionIcon).props('action')).toBe('duplicate');
    });
  });

  describe('action emits', () => {
    it('emits edit when "Editar contenido" is clicked', async () => {
      const wrapper = mountSheet();
      await actionByLabel(wrapper, 'Editar contenido').trigger('click');

      expect(wrapper.emitted('edit')).toHaveLength(1);
    });

    it('closes after an action is triggered', async () => {
      const wrapper = mountSheet();
      await actionByLabel(wrapper, 'Editar contenido').trigger('click');

      expect(wrapper.emitted('update:modelValue')).toEqual([[false]]);
    });

    it('emits rename when "Renombrar" is clicked', async () => {
      const wrapper = mountSheet();
      await actionByLabel(wrapper, 'Renombrar').trigger('click');

      expect(wrapper.emitted('rename')).toHaveLength(1);
    });

    it('emits thread when "Hilo de documentos" is clicked', async () => {
      const wrapper = mountSheet();
      await actionByLabel(wrapper, 'Hilo de documentos').trigger('click');

      expect(wrapper.emitted('thread')).toHaveLength(1);
    });

    it('emits duplicate when "Duplicar" is clicked', async () => {
      const wrapper = mountSheet();
      await actionByLabel(wrapper, 'Duplicar').trigger('click');

      expect(wrapper.emitted('duplicate')).toHaveLength(1);
    });

    it('emits delete when "Eliminar" is clicked', async () => {
      const wrapper = mountSheet();
      await actionByLabel(wrapper, 'Eliminar').trigger('click');

      expect(wrapper.emitted('delete')).toHaveLength(1);
    });
  });

  describe('danger styling', () => {
    it('styles the delete action as danger', () => {
      const wrapper = mountSheet();

      expect(actionByLabel(wrapper, 'Eliminar').classes().join(' ')).toContain('text-danger-strong');
    });
  });

  describe('close', () => {
    it('emits update:modelValue false when Cancelar is clicked', async () => {
      const wrapper = mountSheet();
      const cancel = wrapper.findAll('button').find((btn) => btn.text() === 'Cancelar');
      await cancel.trigger('click');

      expect(wrapper.emitted('update:modelValue')).toEqual([[false]]);
    });
  });

  describe('archive actions', () => {
    it('offers Archivar between Duplicar and Eliminar for an active document', () => {
      const wrapper = mountSheet();
      const labels = actionButtons(wrapper).map((b) => b.text());

      const archiveAt = labels.findIndex((t) => t.includes('Archivar'));
      const duplicateAt = labels.findIndex((t) => t.includes('Duplicar'));
      const deleteAt = labels.findIndex((t) => t.includes('Eliminar'));

      expect(archiveAt).toBeGreaterThan(duplicateAt);
      expect(archiveAt).toBeLessThan(deleteAt);
    });

    it('emits archive and closes when Archivar is clicked', async () => {
      const wrapper = mountSheet();

      await actionByLabel(wrapper, 'Archivar').trigger('click');

      expect(wrapper.emitted('archive')).toEqual([[]]);
      expect(wrapper.emitted('update:modelValue')).toEqual([[false]]);
    });

    it('swaps Archivar for Restaurar on an archived document', () => {
      const wrapper = mountSheet({ archived: true });
      const labels = actionButtons(wrapper).map((b) => b.text());

      expect(labels.some((t) => t.includes('Restaurar'))).toBe(true);
      expect(labels.some((t) => t.includes('Archivar'))).toBe(false);
    });

    it('hides the actions that make no sense on something out of circulation', () => {
      const wrapper = mountSheet({ archived: true });
      const labels = actionButtons(wrapper).map((b) => b.text()).join(' | ');

      expect(labels).not.toContain('Editar contenido');
      expect(labels).not.toContain('Mover a carpeta');
      expect(labels).not.toContain('Enviar por correo');
      // Consultarlo y borrarlo sí siguen teniendo sentido.
      expect(labels).toContain('Descargar PDF');
      expect(labels).toContain('Eliminar');
    });

    it('reads is_archived off the document when the scope prop is not set', () => {
      const wrapper = mountSheet({ document: { ...baseDocument, is_archived: true } });
      const labels = actionButtons(wrapper).map((b) => b.text());

      expect(labels.some((t) => t.includes('Restaurar'))).toBe(true);
    });

    it('emits unarchive when Restaurar is clicked', async () => {
      const wrapper = mountSheet({ archived: true });

      await actionByLabel(wrapper, 'Restaurar').trigger('click');

      expect(wrapper.emitted('unarchive')).toEqual([[]]);
    });
  });
});

describe('DocumentActionsSheet — abrir en pestaña nueva', () => {
  // El enlace es lo que hace la acción alcanzable en pantallas táctiles, donde
  // ctrl+clic no existe. Por eso es un <a> de verdad y no un botón que llame a
  // window.open: así también se puede copiar y abrir con el menú contextual.
  function newTabLink(wrapper) {
    return wrapper.find('[data-testid="document-open-new-tab"]');
  }

  it('offers the editor in another tab as a real link', () => {
    const wrapper = mountSheet({ editTo: '/es-co/panel/documents/7/edit' });

    const link = newTabLink(wrapper);
    expect(link.attributes('href')).toBe('/es-co/panel/documents/7/edit');
    expect(link.attributes('target')).toBe('_blank');
    expect(link.attributes('rel')).toBe('noopener noreferrer');
    expect(link.text()).toContain('Abrir en pestaña nueva');
  });

  it('places it right after Editar contenido', () => {
    const wrapper = mountSheet({ editTo: '/es-co/panel/documents/7/edit' });

    const labels = wrapper.findAll('[data-testid="document-actions-list"] > *').map((el) => el.text());
    expect(labels[0]).toContain('Editar contenido');
    expect(labels[1]).toContain('Abrir en pestaña nueva');
  });

  it('closes the sheet once the other tab is on its way', async () => {
    const wrapper = mountSheet({ editTo: '/es-co/panel/documents/7/edit' });

    await newTabLink(wrapper).trigger('click');

    expect(wrapper.emitted('update:modelValue')).toEqual([[false]]);
  });

  it('leaves it out when the sheet was given no address', () => {
    const wrapper = mountSheet();

    expect(newTabLink(wrapper).exists()).toBe(false);
    expect(actionByLabel(wrapper, 'Editar contenido')).toBeDefined();
  });

  it('leaves it out for an archived document, which has no editor', () => {
    const wrapper = mountSheet({ archived: true, editTo: '/es-co/panel/documents/7/edit' });

    expect(newTabLink(wrapper).exists()).toBe(false);
    expect(actionByLabel(wrapper, 'Restaurar')).toBeDefined();
  });
});

describe('DocumentActionsSheet — contract window', () => {
  it('offers only consulting, sharing and export for the live contract', () => {
    const wrapper = mountSheet({
      document: { ...baseDocument, is_contract_mirror: true },
      editTo: '/es-co/panel/documents/7/edit',
    });
    const labels = wrapper.findAll('[data-testid="document-actions-list"] > *')
      .map((element) => element.text().replace(/\s+/g, ' ').trim());

    expect(labels).toEqual([
      expect.stringContaining('Ver contrato vigente'),
      expect.stringContaining('Abrir en pestaña nueva'),
      expect.stringContaining('Hilo de documentos'),
      expect.stringContaining('Enviar por correo'),
      expect.stringContaining('Descargar PDF'),
      expect.stringContaining('Copiar markdown'),
    ]);
    expect(labels.join(' | ')).not.toMatch(/Renombrar|Mover|Duplicar|Archivar|Eliminar|Editar contenido/);
  });
});

describe('DocumentActionsSheet — generated snapshots', () => {
  it('offers only read-only navigation, one stored download and archive', () => {
    const wrapper = mountSheet({
      document: { ...baseDocument, is_generated_snapshot: true },
      editTo: '/es-co/panel/documents/7/edit',
    });
    const labels = wrapper.findAll('[data-testid="document-actions-list"] > *')
      .map((element) => element.text().replace(/\s+/g, ' ').trim());

    expect(labels).toEqual([
      expect.stringContaining('Ver versión archivada'),
      expect.stringContaining('Abrir en pestaña nueva'),
      expect.stringContaining('Hilo de documentos'),
      expect.stringContaining('Descargar versión archivada'),
      expect.stringContaining('Archivar'),
    ]);
    expect(labels.join(' | ')).not.toMatch(/Renombrar|Mover|Enviar|Duplicar|Eliminar/);
    expect(labels.filter((label) => label.includes('Descargar'))).toHaveLength(1);
  });

  it('limits an archived generated snapshot to restore and stored download', () => {
    const wrapper = mountSheet({
      document: { ...baseDocument, is_generated_snapshot: true, is_archived: true },
      editTo: '/es-co/panel/documents/7/edit',
    });
    const labels = actionButtons(wrapper).map((button) => button.text());

    expect(labels).toHaveLength(3);
    expect(labels[0]).toContain('Restaurar');
    expect(labels[1]).toContain('Hilo de documentos');
    expect(labels[2]).toContain('Descargar versión archivada');
  });
});

describe('DocumentActionsSheet — issued collection accounts', () => {
  it('offers only account viewing, one account PDF and archive', () => {
    const wrapper = mountSheet({
      document: {
        ...baseDocument,
        document_type_code: 'collection_account',
        commercial_status: 'issued',
        is_generated_snapshot: true,
      },
      editTo: '/es-co/panel/documents/7/edit',
    });
    const labels = wrapper.findAll('[data-testid="document-actions-list"] > *')
      .map((element) => element.text().replace(/\s+/g, ' ').trim());

    expect(labels).toHaveLength(5);
    expect(labels[0]).toContain('Ver cuenta de cobro');
    expect(labels[1]).toContain('Abrir en pestaña nueva');
    expect(labels[2]).toContain('Hilo de documentos');
    expect(labels[3]).toContain('Descargar cuenta de cobro');
    expect(labels[4]).toContain('Archivar');
    expect(labels.join(' | ')).not.toMatch(/Renombrar|Mover|Enviar|Duplicar|Eliminar/);
  });
});
