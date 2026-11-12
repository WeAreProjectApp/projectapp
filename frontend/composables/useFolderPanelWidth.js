import { computed, ref } from 'vue';

import { usePersistedRef } from '~/composables/usePersistedRef';

// A 240px el panel dejaba ~70px de nombre y 7 de las 16 carpetas raíz reales
// se truncaban. El default garantiza el inventario vigente al 16-ago-2026
// (nombre más largo: «Futuros Requerimientos», 22 caracteres) con la fila
// activa en font-medium como peor caso; el árbitro de la cifra es el E2E de
// garantía (admin-document-folder-panel-resize), no el ojo en una pantalla.
export const FOLDER_PANEL_MIN = 240; // el ancho histórico: nunca más angosto que hoy
export const FOLDER_PANEL_MAX = 480; // tope para no comerse la vista de documentos
export const FOLDER_PANEL_DEFAULT = 384; // 24rem; 336 truncaba el nombre de 22 chars y 352 quedó corto al sumar la fila el ícono de editar (#196) — medido por el E2E
export const FOLDER_PANEL_KEY = 'projectapp-documents-folder-width';
const KEYBOARD_STEP = 16;

function clampWidth(value, fallback = FOLDER_PANEL_DEFAULT) {
  const px = Number(value);
  if (!Number.isFinite(px)) return fallback;
  return Math.min(FOLDER_PANEL_MAX, Math.max(FOLDER_PANEL_MIN, px));
}

/**
 * Ancho arrastrable y persistido del panel de carpetas de /panel/documents.
 * Port px-based del splitter de CollectionAccountFormModal; `containerRef`
 * es el div del grid, cuyo borde izquierdo coincide con el del panel, así
 * que `clientX - rect.left` ES el ancho pedido.
 */
export function useFolderPanelWidth(containerRef, options = {}) {
  const defaultWidth = clampWidth(options.defaultWidth ?? FOLDER_PANEL_DEFAULT);
  const clamp = value => clampWidth(value, defaultWidth);
  const { ref: width, write, remove } = usePersistedRef(options.storageKey || FOLDER_PANEL_KEY, defaultWidth);
  // Re-clamp de lo hidratado: un storage viejo, manipulado o de otra versión
  // no puede producir un layout inservible.
  width.value = clamp(width.value);

  const dragging = ref(false);

  // Sólo la variable CSS, nunca gridTemplateColumns inline: la clase `lg:` del
  // grid es la única que la consume, y así el ancho guardado queda inerte bajo
  // lg, donde el panel apila a ancho completo.
  const gridStyle = computed(() => ({ '--folders-panel-w': `${width.value}px` }));

  function onHandleDown(e) {
    dragging.value = true;
  }

  function onHandleMove(e) {
    if (!dragging.value || !containerRef.value) return;
    const rect = containerRef.value.getBoundingClientRect();
    if (!rect.width) return;
    width.value = clamp(e.clientX - rect.left);
  }

  function onHandleUp(e) {
    if (!dragging.value) return;
    dragging.value = false;
    // Persistir al soltar y no por move: un drag son decenas de writes menos.
    write(width.value);
  }

  function resizeWidth(value) {
    width.value = clamp(value);
    write(width.value);
  }

  function onHandleKey(e) {
    let next = null;
    if (e.key === 'ArrowLeft') next = width.value - KEYBOARD_STEP;
    else if (e.key === 'ArrowRight') next = width.value + KEYBOARD_STEP;
    else if (e.key === 'Home') next = FOLDER_PANEL_MIN;
    else if (e.key === 'End') next = FOLDER_PANEL_MAX;
    if (next === null) return;
    e.preventDefault();
    resizeWidth(next);
  }

  // El doble clic vuelve al default Y olvida la preferencia: si el default
  // cambia en el futuro, un valor viejo guardado no lo deja pisado.
  function resetWidth() {
    width.value = defaultWidth;
    remove();
  }

  return {
    width, dragging, gridStyle, onHandleDown, onHandleMove, onHandleUp,
    onHandleKey, resizeWidth, resetWidth,
  };
}
