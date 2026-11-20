import { computed, unref } from 'vue';

/**
 * Dirección para un detalle que vive en un modal.
 *
 * Varios listados de contabilidad abren su detalle en una capa sin URL: no se
 * puede compartir, ni recargar en él, ni — el motivo por el que existe este
 * composable — publicarlo en el `<a href>` de la fila. Sin dirección no hay
 * enlace posible, y sin enlace la fila no responde a ninguno de los gestos del
 * navegador.
 *
 * Se elige un parámetro sobre la vista actual (`?income=123`) antes que una
 * ruta propia porque es lo que dice la verdad: el detalle ES una capa sobre el
 * listado. Además el contexto (pestaña, filtros, que ya viven en el query)
 * sobrevive gratis, y atrás/adelante cierran y abren el modal solos.
 *
 * OJO: el parámetro NO puede ser un `ephemeralParam` de useAccountingFilters —
 * esos se capturan y se borran en el setup, que es justamente por qué el
 * `?focus=` de hoy no sobrevive a una recarga.
 *
 * @param {string} name Nombre del parámetro (`income`, `account`, `hosting`…).
 * @param {{ rows?, key?: string, resolve?: (id: number) => object|null, buildQuery?: Function }} [options]
 *   `rows` (array, ref o getter) o `resolve` sólo hacen falta para los modales
 *   que reciben el objeto de la fila y no un id. El que se lo trae solo del
 *   backend no necesita ninguno. `buildQuery` incorpora filtros ya aplicados
 *   aunque la navegación que los escribe en la URL siga pendiente.
 */
export function useDetailQueryParam(name, { rows, key = 'id', resolve, buildQuery } = {}) {
  const route = useRoute();
  const router = useRouter();

  const openId = computed(() => {
    const raw = Array.isArray(route.query[name]) ? route.query[name][0] : route.query[name];
    const n = Number(raw);
    return Number.isInteger(n) && n > 0 ? n : null;
  });

  const isOpen = computed(() => openId.value != null);

  /**
   * La fila abierta, para los modales que reciben el objeto. `null` con el
   * parámetro puesto significa «esa fila no está en la lista» — filtrada,
   * borrada o de otra página: la página decide si la trae o limpia el
   * parámetro, pero no debe dejar una capa abierta sobre la nada.
   */
  const openRow = computed(() => {
    if (openId.value == null) return null;
    // `resolve` para las listas que ya saben buscarse solas (el store de tareas
    // reparte sus filas en varios tableros y expone getTaskById).
    if (resolve) return resolve(openId.value) || null;
    // Getter además de ref: el estado de Pinia se REEMPLAZA al recargar la
    // lista, así que capturar el array de una vez lo dejaría viejo.
    const list = (typeof rows === 'function' ? rows() : unref(rows)) || [];
    return list.find((row) => row[key] === openId.value) || null;
  });

  /** Destino del `<a href>` de la fila: el detalle al lado de los filtros vigentes. */
  function toFor(id) {
    const query = buildQuery?.(route.query) ?? { ...route.query };
    return { path: route.path, query: { ...query, [name]: String(id) } };
  }

  /** Push, no replace: el detalle es un paso, y atrás tiene que cerrarlo. */
  function open(id) {
    router.push(toFor(id));
  }

  /** Replace: cerrar no es un paso nuevo, es deshacer el que abrió. */
  function close() {
    const query = buildQuery?.(route.query) ?? { ...route.query };
    delete query[name];
    router.replace({ path: route.path, query });
  }

  return { openId, openRow, isOpen, toFor, open, close };
}
