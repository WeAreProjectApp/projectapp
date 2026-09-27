#!/usr/bin/env node
/**
 * Materializa los recursos compartidos dentro de cada proyecto HyperFrames.
 * HyperFrames resuelve rutas desde la raíz del proyecto y exige que los recursos
 * vivan dentro de él, así que shared/ y las fuentes del frontend se copian a
 * <video>/assets/ (gitignored) antes de previsualizar, chequear o renderizar.
 *
 *   node scripts/sync-assets.mjs [--video additional-modules|financing]
 */
import { copyFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

import { EDITION, EDITION_ROOT, EXPLAINERS_ROOT, FRONTEND_ROOT, SHARED_DIR, VIDEOS, assertExists, parseArgs, videoDir } from './lib/paths.mjs'

const FONT_FILES = ['Ubuntu-Light.ttf', 'Ubuntu-Regular.ttf', 'Ubuntu-Medium.ttf', 'Ubuntu-Bold.ttf', 'NotoEmoji-Regular.ttf']
const SHARED_FILES = ['brand.css', 'layout.css', 'engine.js']
const LOGO_SOURCE = resolve(FRONTEND_ROOT, 'assets', 'images', 'preloadingAnimation', 'Logo-White-ProjectApp.png')
const GSAP_SOURCE = resolve(EXPLAINERS_ROOT, 'node_modules', 'gsap', 'dist', 'gsap.min.js')

const options = parseArgs(process.argv.slice(2))
const targets = options.video ? [options.video] : VIDEOS.filter(video => EDITION === 'brag-v2' || video !== 'proposal')

for (const video of targets) {
  const assetsDir = resolve(videoDir(video), 'assets')
  const fontsDir = resolve(assetsDir, 'fonts')
  mkdirSync(fontsDir, { recursive: true })

  for (const file of SHARED_FILES) {
    copyFileSync(assertExists(resolve(SHARED_DIR, file)), resolve(assetsDir, file))
  }
  for (const font of FONT_FILES) {
    copyFileSync(assertExists(resolve(FRONTEND_ROOT, 'assets', 'fonts', font)), resolve(fontsDir, font))
  }
  copyFileSync(assertExists(GSAP_SOURCE, 'Corré npm install en explainers/.'), resolve(assetsDir, 'gsap.min.js'))
  copyFileSync(assertExists(LOGO_SOURCE), resolve(assetsDir, 'logo-white.png'))

  if (EDITION === 'brag-v2') {
    for (const file of ['motion.js', 'layout.css']) {
      copyFileSync(resolve(EDITION_ROOT, 'shared', file), resolve(assetsDir, file))
    }
  }

  if (video === 'proposal') {
    copyFileSync(resolve(videoDir(video), 'layout.css'), resolve(assetsDir, 'proposal-layout.css'))
    copyFileSync(resolve(videoDir(video), 'motion.js'), resolve(assetsDir, 'motion.js'))
  }

  console.log(`${video}/assets/ sincronizado (${SHARED_FILES.length} hojas, ${FONT_FILES.length} fuentes, gsap, logo)`)
}
