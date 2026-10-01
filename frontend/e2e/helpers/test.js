import { test as base, expect } from "@playwright/test";
import { PANEL_CONTENT_MAX_PX } from "../../config/responsive.js";
import { getResponsiveScenario } from "../responsive/catalog-scenarios.js";

const shouldLogErrors = process.env.E2E_LOG_ERRORS === "1";
const shouldValidateResponsive = process.env.E2E_RESPONSIVE === "1";

function responsiveProfileFromTags(testInfo) {
  const tag = testInfo.tags.find((value) => value.startsWith('@viewport:'));
  return tag?.slice('@viewport:'.length) ?? null;
}

function responsiveScenarioFromTags(testInfo) {
  const tag = testInfo.tags.find((value) => value.startsWith('@responsive-scenario:'));
  return tag ? getResponsiveScenario(tag.slice('@responsive-scenario:'.length)) : null;
}

async function assertResponsiveContract(page, testInfo, { scenario, profile } = {}) {
  const geometry = await page.evaluate(() => {
    const root = document.documentElement;
    const body = document.body;
    const rootScrollWidth = root.scrollWidth;
    const bodyScrollWidth = body?.scrollWidth || 0;
    const clientWidth = root.clientWidth;
    const offenders = [...document.querySelectorAll('body *')]
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          element,
          rect,
          overhang: Math.max(0, rect.right - clientWidth, -rect.left),
        };
      })
      .filter(({ rect, overhang }) => overhang > 1 && rect.width > 0 && rect.height > 0)
      .sort((left, right) => right.overhang - left.overhang)
      .slice(0, 8)
      .map(({ element, rect, overhang }) => ({
        tag: element.tagName.toLowerCase(),
        id: element.id || null,
        testid: element.getAttribute('data-testid'),
        class: element.className?.toString().slice(0, 160) || null,
        left: Math.round(rect.left),
        right: Math.round(rect.right),
        width: Math.round(rect.width),
        overhang: Math.round(overhang),
      }));
    return {
      overflow: Math.max(rootScrollWidth, bodyScrollWidth) - clientWidth,
      rootScrollWidth,
      bodyScrollWidth,
      clientWidth,
      innerWidth: window.innerWidth,
      offenders,
    };
  });
  const evidence = [
    scenario?.catalogKey && `scenario=${scenario.catalogKey}`,
    scenario?.owner && `owner=${scenario.owner}`,
    profile && `profile=${profile}`,
  ].filter(Boolean).join(' · ');
  expect(
    geometry.overflow,
    `La página desborda horizontalmente ${geometry.overflow}px${evidence ? ` (${evidence})` : ` en ${testInfo.project.name}`} · geometry=${JSON.stringify(geometry)}`,
  ).toBeLessThanOrEqual(1);

  const pathname = new URL(page.url()).pathname;
  const viewport = page.viewportSize();
  const requiresPanelShell = scenario
    ? scenario.capabilities.panelShell
    : pathname.includes('/panel');
  if (requiresPanelShell && viewport?.width >= 1920) {
    const contentWidths = await page.getByTestId('panel-content-shell').evaluateAll((elements) => (
      elements
        .map((element) => element.getBoundingClientRect().width)
        .filter((width) => width > 0)
    ));
    expect(contentWidths.length, 'No hay un shell visible que limite el panel').toBeGreaterThan(0);
    expect(
      Math.max(...contentWidths),
      `El contenido del panel supera ${PANEL_CONTENT_MAX_PX}px en monitor wide`,
    ).toBeLessThanOrEqual(PANEL_CONTENT_MAX_PX + 1);
  }

  const hasTouch = ['compact', 'portrait', 'landscape'].includes(profile) || testInfo.project.use.hasTouch;
  if (hasTouch) {
    const undersizedTargets = await page.locator('[data-responsive-touch-target]').evaluateAll((elements) => (
      elements
        .filter((element) => {
          const style = getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
        })
        .map((element) => {
          const rect = element.getBoundingClientRect();
          return { label: element.getAttribute('aria-label') || element.textContent?.trim(), width: rect.width, height: rect.height };
        })
        .filter(({ width, height }) => width < 43.5 || height < 43.5)
    ));
    expect(undersizedTargets, 'Hay targets táctiles declarados por debajo de 44px').toEqual([]);
  }
}

/**
 * Run responsive geometry only after the scenario's user assertion has passed.
 * Keeping this explicit prevents a generic post-test hook from accrediting a
 * route whose declared table/modal/target surface was never actually opened.
 */
export async function assertResponsiveScenario(page, testInfo, scenario, options = {}) {
  const profile = options.profile ?? responsiveProfileFromTags(testInfo);
  await assertResponsiveContract(page, testInfo, { scenario, profile });

  if (scenario?.capabilities?.table && options.priorityLocator) {
    await expect(options.priorityLocator, `La columna o dato prioritario no quedó alcanzable (${scenario.catalogKey})`).toBeVisible();
  }

  if (scenario?.capabilities?.modal && options.modalLocator) {
    await expect(options.modalLocator, `El modal declarado no quedó abierto (${scenario.catalogKey})`).toBeVisible();
    if (options.finalActionLocator) {
      const box = await options.finalActionLocator.boundingBox();
      const currentViewport = page.viewportSize();
      expect(box, `No se pudo medir la acción final del modal (${scenario.catalogKey})`).not.toBeNull();
      expect(box.y + box.height, `La acción final del modal quedó fuera del viewport (${scenario.catalogKey})`).toBeLessThanOrEqual(currentViewport.height + 1);
    }
  }
}

export const test = base.extend({
  page: async ({ page }, use, testInfo) => {
    // The gateway guide is intentionally shown once per browser for real
    // visitors. Existing gateway specs exercise their own target, so keep the
    // one-time guide out of their way unless a guide-specific test removes it.
    await page.addInitScript(() => {
      localStorage.setItem('projectapp-proposal-gateway-guide-v1', 'true');
    });
    if (shouldLogErrors) {
      page.on("pageerror", (err) => {
        console.error("[e2e:pageerror]", err);
      });
      page.on("console", (msg) => {
        if (msg.type() === "error") {
          console.error("[e2e:console:error]", msg.text());
        }
      });
    }
    await use(page);
    const isResponsiveTest = testInfo.tags.some((tag) => tag.startsWith('@responsive:'));
    const isRedirectCompatibility = testInfo.tags.includes('@responsive-redirect');
    if (shouldValidateResponsive && isResponsiveTest && !isRedirectCompatibility && !page.isClosed() && testInfo.errors.length === 0) {
      await assertResponsiveContract(page, testInfo, {
        profile: responsiveProfileFromTags(testInfo),
        scenario: responsiveScenarioFromTags(testInfo),
      });
    }
  },
});

export { expect };
