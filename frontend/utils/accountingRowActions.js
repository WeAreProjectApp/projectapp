/**
 * Shared vocabulary for the accounting row menus.
 *
 * Every three-dot menu of the module opens with the same read-only entries —
 * the record's detail and change history, then its note when it has one — so
 * the kebab reads the same on every tab before the entity's own actions.
 */

/** True when the record carries a note worth opening; whitespace is not one. */
export function hasNote(record) {
  return typeof record?.notes === 'string' && record.notes.trim() !== '';
}

export const HISTORY_ROW_ACTION = Object.freeze({
  id: 'history', action: 'view', label: 'Detalle e historial',
});

export const NOTE_ROW_ACTION = Object.freeze({
  id: 'notes', action: 'notes', label: 'Ver nota',
});

/** Detail and history first, then the note when the record has one. */
export function leadingRowActions(record) {
  return hasNote(record) ? [HISTORY_ROW_ACTION, NOTE_ROW_ACTION] : [HISTORY_ROW_ACTION];
}
