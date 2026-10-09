import { PANEL_VIEWPORTS } from '../../config/responsive';
import {
  RESPONSIVE_MODULE_NAMES,
  modulesForChangedFiles,
  responsiveOwnerForView,
} from '../../config/responsiveAcceptance';
import { VIEWPORTS, viewportUse } from '../../e2e/helpers/viewports';

describe('responsive acceptance registry', () => {
  it('keeps the five canonical viewport widths', () => {
    expect(Object.values(PANEL_VIEWPORTS).map(({ width }) => width)).toEqual([
      412,
      835,
      1195,
      1440,
      2560,
    ]);
  });

  it('exposes the project matrix through the E2E viewport helper', () => {
    expect(VIEWPORTS).toBe(PANEL_VIEWPORTS);
    expect(viewportUse('portrait')).toEqual({
      viewport: { width: 835, height: 1195 },
      hasTouch: true,
    });
  });

  it('rejects an unknown E2E viewport alias', () => {
    expect(() => viewportUse('tablet')).toThrow('Viewport responsivo desconocido: tablet');
  });

  it('runs only the owning module for a scoped page', () => {
    expect(modulesForChangedFiles(['frontend/pages/panel/mcps/index.vue'])).toEqual(['mcp']);
  });

  it.each([
    'frontend/pages/building-with-us/index.vue',
    'frontend/components/BuildingWithUs/ProgramView.vue',
    'frontend/components/BuildingWithUs/Onboarding.vue',
    'frontend/components/BuildingWithUs/ProgramSkeleton.vue',
    'frontend/composables/useBuildingWithUsTheme.js',
    'frontend/utils/buildingWithUs.js',
  ])('selects public acceptance for %s', (file) => {
    expect(modulesForChangedFiles([file])).toEqual(['public']);
  });

  it.each([
    'frontend/pages/panel/building-with-us/index.vue',
    'frontend/components/BuildingWithUs/admin/ContractPanel.vue',
  ])('selects commercial acceptance for %s', (file) => {
    expect(modulesForChangedFiles([file])).toEqual(['commercial']);
  });

  it('assigns the Building with Us panel to commercial acceptance', () => {
    expect(responsiveOwnerForView('admin-panel', {
      file: 'frontend/pages/panel/building-with-us/index.vue',
      url: '/panel/building-with-us',
      audience: 'admin',
    })).toBe('commercial');
  });

  it('assigns the communications page to its focused responsive module', () => {
    const view = {
      file: 'frontend/pages/panel/communications/index.vue',
      url: '/panel/communications',
      audience: 'admin',
    };

    expect(modulesForChangedFiles([view.file])).toEqual(['communications']);
    expect(responsiveOwnerForView('admin-panel', view)).toBe('communications');
  });

  it('assigns the project state catalog to the projects module', () => {
    const view = {
      file: 'frontend/pages/panel/projects/statuses.vue',
      url: '/panel/projects/statuses',
      audience: 'admin',
    };

    expect(modulesForChangedFiles([view.file])).toEqual(['projects']);
    expect(responsiveOwnerForView('admin-panel', view)).toBe('projects');
  });

  it('runs every module for a shared primitive', () => {
    expect(modulesForChangedFiles(['frontend/components/base/BaseModal.vue'])).toEqual(
      RESPONSIVE_MODULE_NAMES,
    );
  });

  it('runs every module for an unregistered UI directory', () => {
    expect(modulesForChangedFiles(['frontend/components/new-area/Widget.vue'])).toEqual(
      RESPONSIVE_MODULE_NAMES,
    );
  });

  it('assigns document editors to canvas', () => {
    expect(responsiveOwnerForView('admin-panel', {
      file: 'frontend/pages/panel/documents/[id]/edit.vue',
      url: '/panel/documents/:id/edit',
      audience: 'admin',
    })).toBe('canvas');
  });
});
