#!/usr/bin/env node

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const catalogPath = path.join(frontendRoot, 'config/panelActions.js')
const scopedPaths = [
  'layouts/admin.vue',
  'pages/panel',
  'components/panel',
  'components/accounting',
  'components/BusinessProposal/admin',
  'components/WebAppDiagnostic/admin',
  'components/WebAppDiagnostic/DiagnosticActionsModal.vue',
  'components/WebAppDiagnostic/DiagnosticDocumentsTab.vue',
  'components/WebAppDiagnostic/DiagnosticEmailsTab.vue',
  'components/WebAppDiagnostic/DiagnosticFilterPanel.vue',
  'components/WebAppDiagnostic/ConfidentialityParamsModal.vue',
  'components/Tasks',
  'components/proposals',
  'components/views',
  'components/clients',
  'components/emails',
  'components/hour-packages',
  'components/Linktree',
  'components/ConfirmModal.vue',
  'components/ComposedEmailPreview.vue',
  'components/EmailHistoryList.vue',
  'components/AttachFromDocumentsModal.vue',
  'components/MarkdownAttachmentModal.vue',
  'components/ui/FilterToggleButton.vue',
  'components/ui/ClientAutocomplete.vue',
  'components/base/BaseActionIcon.vue',
  'components/base/BaseActionButton.vue',
  'components/base/BaseActionMenu.vue',
  'components/base/BaseDropdown.vue',
  'components/base/BaseResponsiveTable.vue',
  'components/base/BaseRowActionsModal.vue',
  'components/base/BasePagination.vue',
  'components/base/BaseFilterTabs.vue',
  'components/base/BaseAlert.vue',
  'components/base/BaseDrawer.vue',
]

const actionTagPattern = /<(button|BaseButton|BaseActionButton|NuxtLink|a|label|summary)\b[\s\S]*?<\/\1>/g
const pictographicPattern = /\p{Extended_Pictographic}|[✕×↻▾▸↑↓→←＋−▲▼▶◀]/gu
const leadingPlusPattern = />\s*\+\s+\p{L}/gu
const rawSvgPattern = /<svg\b/g
const directIconPattern = /<((?!BaseAction)[A-Z][A-Za-z0-9]*Icon)\b/g
const allowCommentPattern = /panel-action-icons:\s*allow-[a-z-]+/

function walk(targetPath) {
  if (!fs.existsSync(targetPath)) return []
  const stat = fs.statSync(targetPath)
  if (stat.isFile()) return targetPath.endsWith('.vue') ? [targetPath] : []
  return fs.readdirSync(targetPath).flatMap((entry) => walk(path.join(targetPath, entry)))
}

function lineNumber(source, offset) {
  return source.slice(0, offset).split('\n').length
}

function hasAllowComment(source, offset) {
  return allowCommentPattern.test(source.slice(Math.max(0, offset - 260), offset))
}

function isInsideTooltip(source, offset) {
  const before = source.slice(0, offset)
  return before.lastIndexOf('<BaseTooltip') > before.lastIndexOf('</BaseTooltip>')
}

function hasVisibleActionText(block) {
  const body = block
    .slice(block.indexOf('>') + 1, block.lastIndexOf('</'))
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/<svg\b[\s\S]*?<\/svg>/g, '')
    .replace(/<BaseActionIcon\b[^>]*\/?\s*>/g, '')
    .replace(/<[A-Z][A-Za-z0-9]*Icon\b[^>]*\/?\s*>/g, '')
    .replace(/<[^>]+>/g, '')
    .trim()
  return Boolean(body)
}

function collectCatalogKeys(source) {
  const keys = new Set()
  const definitionPattern = /^\s*(?:'([^']+)'|([a-z][a-z0-9-]*)):\s*defineAction\(/gm
  for (const match of source.matchAll(definitionPattern)) keys.add(match[1] || match[2])
  return keys
}

const catalogSource = fs.readFileSync(catalogPath, 'utf8')
const catalogKeys = collectCatalogKeys(catalogSource)
const files = [...new Set(scopedPaths.flatMap((entry) => walk(path.join(frontendRoot, entry))))].sort()
const errors = []

const iconSources = [...catalogSource.matchAll(/from\s+['"](@heroicons\/vue\/[^'"]+)['"]/g)]
  .map((match) => match[1])
if (iconSources.length !== 1 || iconSources[0] !== '@heroicons/vue/24/outline') {
  errors.push('config/panelActions.js must source every canonical icon from @heroicons/vue/24/outline')
}

const catalogIconNames = [...catalogSource.matchAll(/defineAction\([^,]+,\s*['"]([^'"]+)['"]/g)]
  .map((match) => match[1])
for (const iconName of new Set(catalogIconNames)) {
  const owners = catalogIconNames.filter((candidate) => candidate === iconName)
  if (owners.length > 1) errors.push(`config/panelActions.js assigns ${iconName} to ${owners.length} actions`)
}

for (const file of files) {
  const source = fs.readFileSync(file, 'utf8')
  const relativePath = path.relative(frontendRoot, file)

  for (const match of source.matchAll(actionTagPattern)) {
    const block = match[0]
    const line = lineNumber(source, match.index)
    const allowed = hasAllowComment(source, match.index)

    for (const rawSvg of block.matchAll(rawSvgPattern)) {
      const svgOffset = match.index + rawSvg.index
      if (!allowed && !hasAllowComment(source, svgOffset)) {
        errors.push(`${relativePath}:${lineNumber(source, svgOffset)} embeds raw SVG inside an action control`)
      }
    }

    for (const textIcon of block.matchAll(pictographicPattern)) {
      const iconOffset = match.index + textIcon.index
      if (!allowed && !hasAllowComment(source, iconOffset)) {
        errors.push(`${relativePath}:${lineNumber(source, iconOffset)} embeds an emoji or text glyph inside an action control`)
      }
    }

    for (const textIcon of block.matchAll(leadingPlusPattern)) {
      const iconOffset = match.index + textIcon.index
      if (!allowed && !hasAllowComment(source, iconOffset)) {
        errors.push(`${relativePath}:${lineNumber(source, iconOffset)} embeds an emoji or text glyph inside an action control`)
      }
    }

    for (const directIcon of block.matchAll(directIconPattern)) {
      const iconOffset = match.index + directIcon.index
      if (!allowed && !hasAllowComment(source, iconOffset) && !isInsideTooltip(source, iconOffset)) {
        errors.push(`${relativePath}:${lineNumber(source, iconOffset)} renders ${directIcon[1]} directly inside an action control`)
      }
    }

    if (match[1] === 'BaseButton' && /\bicon-only\b/.test(block)) {
      const hasAccessibleName = /(?:aria-label|aria-labelledby)=/.test(block)
      const hasTooltip = /\btitle=/.test(block) || isInsideTooltip(source, match.index)
      if (!hasAccessibleName) errors.push(`${relativePath}:${line} icon-only BaseButton has no accessible name`)
      if (!hasTooltip) errors.push(`${relativePath}:${line} icon-only BaseButton has no hover/focus label`)
    }

    if (
      ['button', 'NuxtLink', 'a'].includes(match[1])
      && block.includes('<BaseActionIcon')
      && !hasVisibleActionText(block)
    ) {
      const hasAccessibleName = /(?:aria-label|aria-labelledby)=/.test(block)
      const hasTooltip = /\btitle=/.test(block) || isInsideTooltip(source, match.index)
      if (!hasAccessibleName) errors.push(`${relativePath}:${line} icon-only action control has no accessible name`)
      if (!hasTooltip) errors.push(`${relativePath}:${line} icon-only action control has no hover/focus label`)
    }
  }

  const templateActionPattern = /<BaseAction(?:Icon|Button)\b[^>]*\saction="([^"]+)"/g
  const itemFactoryActionPattern = /createPanelActionItem\(\s*['"]([^'"]+)['"]/g
  for (const pattern of [templateActionPattern, itemFactoryActionPattern]) {
    for (const match of source.matchAll(pattern)) {
      const action = match[1]
      if (!catalogKeys.has(action)) {
        errors.push(`${relativePath}:${lineNumber(source, match.index)} references unknown action "${action}"`)
      }
    }
  }
}

if (errors.length) {
  console.error('Panel action icon guard failed:')
  for (const error of errors) console.error(`  - ${error}`)
  console.error('\nUse BaseActionIcon/BaseActionButton with a key from config/panelActions.js.')
  process.exit(1)
}

console.log(`Panel action icon guard passed (${files.length} files, ${catalogKeys.size} canonical actions).`)
