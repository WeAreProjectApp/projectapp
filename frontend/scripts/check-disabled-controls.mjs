#!/usr/bin/env node
/**
 * Panel disabled-control guard.
 *
 * A disabled interactive element must name why it is unavailable. The guard
 * is deliberately syntactic: callers declare the contract with one of
 * `disabled-reason`, `aria-describedby`, `title`, `loading`, or the explicit
 * `data-disabled-explained` marker when adjacent copy owns the explanation.
 * BaseControlGate is the preferred visible pattern for resolvable blockers
 * that no field owns; a missing form field keeps submit enabled and is named
 * beside its field by BaseFormField after the attempt.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const FRONTEND_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const strict = process.argv.includes('--strict')
const quiet = process.argv.includes('--quiet')

const DIRECTORY_SCOPES = [
  'pages/panel',
  'components/base',
  'components/Linktree',
  'components/Panel',
  'components/panel',
  'components/accounting',
  'components/blog',
  'components/clients',
  'components/emails',
  'components/hour-packages',
  'components/proposals',
  'components/stats',
  'components/Tasks',
  'components/views',
  'components/ui',
  'components/WebAppDiagnostic',
  'components/BusinessProposal/admin',
]

const SHARED_PANEL_FILES = [
  'components/AttachFromDocumentsModal.vue',
  'components/ComposedEmailPreview.vue',
  'components/ConfirmModal.vue',
  'components/EmailHistoryList.vue',
  'components/LocaleSwitcher.vue',
  'components/MarkdownAttachmentModal.vue',
]

const EXCLUDED_PARTS = [
  `${path.sep}WebAppDiagnostic${path.sep}public${path.sep}`,
]

const CONTROL_TAGS = [
  'BaseActionButton',
  'BaseActionMenu',
  'BaseButton',
  'BaseCheckbox',
  'BaseCurrencyInput',
  'BaseInput',
  'BaseMobileTabSelect',
  'BaseResponsiveTabs',
  'BaseSegmented',
  'BaseSegmentedMulti',
  'BaseSelect',
  'BaseTextarea',
  'BaseToggle',
  'button',
  'input',
  'select',
  'textarea',
]

const CONTROL_OPEN_RE = new RegExp(`<(${CONTROL_TAGS.join('|')})\\b`, 'g')
const DISABLED_RE = /(?:^|\s):?disabled(?:\s|=|$)/
const EXPLANATION_RE = /(?:disabled-reason|aria-describedby|(?:^|\s):?title(?:\s|=)|(?:^|\s):?loading(?:\s|=)|data-disabled-explained)/m
const BUSY_RE = /(?:saving|loading|busy|updating|uploading|downloading|generating|submitting|sending|retrying|creating|deleting|applying|resetting|refreshing|publishing|exporting|bridging|toggling|previewing|scheduling|completing|moving|adding|loggingIn|resending|isUpdating|templateBusy)/i

function startTags(source) {
  const tags = []
  CONTROL_OPEN_RE.lastIndex = 0
  let match
  while ((match = CONTROL_OPEN_RE.exec(source)) !== null) {
    let quote = ''
    let cursor = CONTROL_OPEN_RE.lastIndex
    for (; cursor < source.length; cursor += 1) {
      const char = source[cursor]
      if (quote) {
        if (char === quote && source[cursor - 1] !== '\\') quote = ''
        continue
      }
      if (char === '"' || char === "'" || char === '`') {
        quote = char
        continue
      }
      if (char === '>') break
    }
    if (cursor >= source.length) break
    tags.push({
      tag: match[1],
      attributes: source.slice(CONTROL_OPEN_RE.lastIndex, cursor),
      index: match.index,
    })
    CONTROL_OPEN_RE.lastIndex = cursor + 1
  }
  return tags
}

function disabledExpression(attributes) {
  const match = attributes.match(/:?disabled(?:\s*=\s*(?:"([^"]*)"|'([^']*)'))?/)
  return match?.[1] ?? match?.[2] ?? 'disabled'
}

function isBusyOnly(expression) {
  const withoutLookupKeys = expression.replace(/\[[^\]]*\]/g, '')
  const comparison = withoutLookupKeys.match(
    /^\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*(?:===|==|!==|!=)\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*|null|undefined)\s*$/,
  )
  if (comparison) {
    return [comparison[1], comparison[2]].some((identifier) => (
      BUSY_RE.test(identifier.split('.').at(-1))
    ))
  }

  const identifiers = withoutLookupKeys.match(/[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*/g) || []
  if (!identifiers.length) return false
  return identifiers.every((identifier) => {
    if (['Boolean', 'true', 'false', 'undefined', 'null'].includes(identifier)) return true
    const name = identifier.split('.').at(-1)
    return BUSY_RE.test(name)
  })
}

function walk(directory) {
  if (!fs.existsSync(directory)) return []
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const target = path.join(directory, entry.name)
    if (EXCLUDED_PARTS.some(part => target.includes(part))) return []
    if (entry.isDirectory()) return walk(target)
    return entry.isFile() && entry.name.endsWith('.vue') ? [target] : []
  })
}

const files = [
  ...DIRECTORY_SCOPES.flatMap(scope => walk(path.join(FRONTEND_ROOT, scope))),
  ...SHARED_PANEL_FILES.map(file => path.join(FRONTEND_ROOT, file)).filter(fs.existsSync),
]

const findings = []
for (const file of [...new Set(files)].sort()) {
  const source = fs.readFileSync(file, 'utf8')
  for (const control of startTags(source)) {
    const { attributes } = control
    if (!DISABLED_RE.test(attributes)) continue
    if (/\b:?disabled\s*=\s*["']false["']/.test(attributes)) continue
    if (EXPLANATION_RE.test(attributes)) continue

    const expression = disabledExpression(attributes)
    // Busy-only locks are explained by BaseButton's standard operation-in-
    // progress title/tooltip or by the control's changing status label. Any
    // simultaneous validation/lifecycle condition still needs explicit copy.
    if (isBusyOnly(expression)) continue

    const line = source.slice(0, control.index).split('\n').length
    findings.push({
      file: path.relative(FRONTEND_ROOT, file),
      line,
      tag: control.tag,
      expression,
    })
  }
}

if (!quiet) {
  if (findings.length === 0) {
    console.log('disabled-controls: PASS — 0 silent panel controls')
  } else {
    console.log(`disabled-controls: ${findings.length} silent panel control(s)`)
    for (const finding of findings) {
      console.log(`  ${finding.file}:${finding.line} <${finding.tag}> disabled=${finding.expression}`)
    }
    console.log('\nAdd disabled-reason, aria-describedby, title, loading, or data-disabled-explained.')
  }
}

if (strict && findings.length > 0) process.exit(1)
