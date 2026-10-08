// Regenerates docs/dataset.md and the generated regions of README.md directly
// from the verified dataset artifact. Every number in those documents comes
// from a full scan of the database; nothing is hand-typed.
//
// Usage: node docs/generate_dataset_doc.js [--db <path-to-sqlite3>]
// Default --db is the library's own download-and-cache location, so the docs
// are generated from the same file the library serves.

import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { createHash } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { DatabaseSync } from 'node:sqlite'

import DEFAULTS from '../util/defaults.js'
import { defaultCacheDir, cachedDbPath } from '../util/cache-location.js'

const RELEASE = DEFAULTS.datasetRelease
const EXPECTED_ROWS = 256 ** 3
const EXAMPLE_ID = 0x42dead

const repoRoot = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')

const parseArgs = (argv) => {
  const args = { dbPath: null }
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--db') {
      args.dbPath = argv[++i]
      if (!args.dbPath) throw new Error('--db needs a path')
    } else {
      throw new Error(`Unknown argument: ${argv[i]}`)
    }
  }
  if (!args.dbPath) {
    args.dbPath = cachedDbPath(
      defaultCacheDir({ platform: process.platform, env: process.env, homedir: os.homedir() }),
      RELEASE
    )
  }
  return args
}

// The documents must describe the published artifact, not any arbitrary copy,
// so refuse to generate unless the file's sha256 matches the pinned release.
const verifyArtifact = async (dbPath) => {
  const stat = await fs.promises.stat(dbPath)
  if (stat.size !== RELEASE.dbSize) {
    throw new Error(`${dbPath}: expected ${RELEASE.dbSize} bytes, found ${stat.size}`)
  }
  const hash = createHash('sha256')
  await new Promise((resolve, reject) => {
    const stream = fs.createReadStream(dbPath)
    stream.on('error', reject)
    stream.on('data', (chunk) => hash.update(chunk))
    stream.on('end', resolve)
  })
  const actual = hash.digest('hex')
  if (actual !== RELEASE.dbSha256) {
    throw new Error(`${dbPath}: expected sha256 ${RELEASE.dbSha256}, found ${actual}`)
  }
  return actual
}

const collectStats = (db) => {
  const schema = db.prepare("SELECT sql FROM sqlite_master WHERE name = 'color'").get()
  const expected = 'CREATE TABLE color (id INTEGER PRIMARY KEY, filter TEXT, loss REAL)'
  if (!schema || schema.sql.replace(/\s+/g, ' ').trim() !== expected) {
    throw new Error(`Unexpected schema: ${schema === undefined ? 'no color table' : schema.sql}`)
  }

  const probe = db.prepare('SELECT COUNT(*) AS c FROM color').get()
  if (probe.c !== EXPECTED_ROWS) {
    throw new Error(`Expected ${EXPECTED_ROWS} rows, found ${probe.c}`)
  }

  const stats = db.prepare(`
    SELECT
      COUNT(*) AS total,
      AVG(loss) AS avg,
      MAX(loss) AS max,
      MIN(loss) AS min,
      SUM(loss = 0) AS eq0,
      SUM(loss > 0 AND loss < 0.1) AS b0,
      SUM(loss >= 0.1 AND loss < 0.2) AS b1,
      SUM(loss >= 0.2 AND loss < 0.3) AS b2,
      SUM(loss >= 0.3 AND loss < 0.4) AS b3,
      SUM(loss >= 0.4 AND loss < 0.5) AS b4,
      SUM(loss >= 0.5 AND loss < 0.6) AS b5,
      SUM(loss >= 0.6 AND loss < 0.7) AS b6,
      SUM(loss >= 0.7 AND loss < 0.8) AS b7,
      SUM(loss >= 0.8 AND loss < 0.9) AS b8,
      SUM(loss >= 0.9 AND loss < 1) AS b9,
      SUM(loss >= 1) AS fails
    FROM color
  `).get()

  const buckets = [stats.eq0, stats.b0, stats.b1, stats.b2, stats.b3, stats.b4, stats.b5, stats.b6, stats.b7, stats.b8, stats.b9]
  const bucketSum = buckets.reduce((a, b) => a + b, 0)
  if (bucketSum !== stats.total) {
    throw new Error(`Bucket sum ${bucketSum} does not match row count ${stats.total}`)
  }
  if (stats.fails !== 0) {
    throw new Error(`Covering claim violated: ${stats.fails} rows render with loss >= 1`)
  }

  const example = db.prepare('SELECT id, filter, loss FROM color WHERE id = ?').get(EXAMPLE_ID)
  if (example === undefined) throw new Error(`Example color ${EXAMPLE_ID} not found`)

  const fractional = db.prepare("SELECT id, filter, loss FROM color WHERE instr(filter, '.') > 0 ORDER BY id").all()

  return { stats, buckets, example, fractional }
}

// Truncates to a fixed number of decimals (never rounds up): the legacy stats
// table used this convention and the max must not render as 1.00000.
const truncFixed = (num, digits) => {
  const match = num.toString().match(new RegExp('^-?\\d+(?:\\.\\d{0,' + digits + '})?'))
  return match[0]
}

const group = (n) => n.toLocaleString('en-US')

const toHex = (id) => `#${id.toString(16).padStart(6, '0')}`

const BAND_LABELS = ['0%', '0.0%', '0.1%', '0.2%', '0.3%', '0.4%', '0.5%', '0.6%', '0.7%', '0.8%', '0.9%']

const statsTable = ({ stats, buckets }) => {
  const header = `Average|Max|Min|${BAND_LABELS.join('|')}|Total`
  const rule = `-------|---|---|${BAND_LABELS.map((l) => '-'.repeat(Math.max(2, l.length))).join('|')}|-----`
  const row = [
    truncFixed(stats.avg, 5),
    truncFixed(stats.max, 5),
    truncFixed(stats.min, 5),
    ...buckets.map((b) => group(b)),
    group(stats.total)
  ].join('|')
  return `${header}\n${rule}\n${row}`
}

const pieChart = ({ buckets }) => [
  '```mermaid',
  'pie showData',
  ...BAND_LABELS.map((label, i) => `  "${label} loss" : ${buckets[i]}`),
  '```'
].join('\n')

const fractionalTable = ({ fractional }) => {
  const rows = fractional.map(
    (r) => `\`${toHex(r.id)}\`|\`${r.filter}\`|${truncFixed(r.loss, 5)}`
  )
  return ['Color|Filter chain|Loss', '-----|-----------|----', ...rows].join('\n')
}

const buildDatasetDoc = ({ stats, buckets, example, fractional }) => `# The CSS Filter Covering Dataset

<!-- This document is generated. Do not edit numbers by hand: run
     \`node docs/generate_dataset_doc.js\` (from the library repo root) to
     regenerate it directly from the verified dataset artifact. -->

The dataset behind [hex-to-css-filter-library](../README.md) is a covering
certificate for sRGB: for **every one of the ${group(stats.total)} colors** it
stores a six-function CSS filter chain whose rendered loss is under 1%.

## The artifact

- Snapshot: \`${RELEASE.snapshot}\`
- Database: \`${RELEASE.dbFile}\` (${group(RELEASE.dbSize)} bytes, uncompressed)
- Download: \`${RELEASE.gzFile}\` (${group(RELEASE.gzSize)} bytes)

| Checksum (SHA-256) | File |
| ------------------ | ---- |
| \`${RELEASE.dbSha256}\` | \`${RELEASE.dbFile}\` |
| \`${RELEASE.gzSha256}\` | \`${RELEASE.gzFile}\` |

Mirrors (same bytes, same checksums, verified on download by the library):

${RELEASE.urls.map((url) => `- ${url}`).join('\n')}

One-command verification from an empty directory (macOS: \`shasum -a 256 -c\`):

\`\`\`sh
curl -sSfL -O ${RELEASE.urls[0].replace(/[^/]+$/, 'CHECKSUMS.txt')} \\
  -O ${RELEASE.urls[0]}
sha256sum -c CHECKSUMS.txt
\`\`\`

Licenses: the dataset is [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/),
the library code is [MIT](../LICENSE). A browsable copy of the data lives at
the Hugging Face dataset
[${RELEASE.urls[1].match(/datasets\/([^/]+\/[^/]+)/)[1]}](https://huggingface.co/datasets/${RELEASE.urls[1].match(/datasets\/([^/]+\/[^/]+)/)[1]}),
which is also what browser builds query over the network.

## The metric: rendered loss

\`loss\` is the **rendered loss** of the stored witness — *not* the legacy
continuous metric that older releases published. It is defined in words as
follows:

1. Start from black (\`#000000\`) and apply the stored chain — \`invert\`,
   \`sepia\`, \`saturate\`, \`hue-rotate\`, \`brightness\`, \`contrast\` — in that
   order, using the filter functions' color-matrix math at full floating-point
   precision, without rounding the result to 8-bit channels.
2. Take the absolute difference per channel between the rendered color and the
   target color: red, green and blue on the 0–255 scale, plus hue, saturation
   and lightness (computed with the classic RGB→HSL conversion, hue folded into
   the 0–100 scale, achromatic colors read as \`h = 0, s = 0\`).
3. Sum those six deltas. That sum is the rendered loss.

The metric is deliberately kept as the historical definition so the long-standing
"under 1% loss" claim remains comparable; it is a non-standard, mixed RGB+HSL
measure — the threshold "1" is written "1% loss", not a true percentage. A
standard colorimetric recomputation (CIEDE2000) is planned as an additional
column, tracked separately.

Because the metric re-renders from the stored \`filter\` text, every row can be
re-checked from the artifact alone: the script that generated this document
re-scanned all ${group(stats.total)} rows and refuses to (re)generate unless
every row lands under 1.

## The claim, checked

- Rows: ${group(stats.total)} (every sRGB color, \`id\` packed as 0xRRGGBB)
- Rows with rendered loss ≥ 1: **${stats.fails === 0 ? '0' : stats.fails}**
- Maximum rendered loss: \`${stats.max}\` (under 1)
- Average rendered loss: ${truncFixed(stats.avg, 5)}
- Exact matches (loss = 0): ${group(stats.eq0)} colors
- ${group(EXPECTED_ROWS - fractional.length)} of ${group(stats.total)} rows use
  integer percent/degree parameters; ${fractional.length} colors are stored with
  0.1-granularity fractional parameters (see below).

## Loss statistics

${statsTable({ stats, buckets, example, fractional })}

${pieChart({ stats, buckets, example, fractional })}

Bands: \`0%\` is loss exactly 0; \`0.0%\` is 0 < loss < 0.1; each further band is
the half-open interval [band, band + 0.1).

## Schema

\`CREATE TABLE color (id INTEGER PRIMARY KEY, filter TEXT, loss REAL)\`

Field|Type|Description
-----|----|-----------
\`id\`|\`INTEGER\`|Primary key: the target color packed as 0xRRGGBB (red in the high byte). It is also the row offset in the Parquet mirror.
\`filter\`|\`TEXT\`|The witness chain verbatim: six CSS filter functions applied to black — \`invert() sepia() saturate() hue-rotate() brightness() contrast()\`.
\`loss\`|\`REAL\`|Rendered loss of the stored chain, defined above; under 1 for every row. Legacy databases published the pre-rounding continuous metric here instead — do not compare the two.

## Fractional-parameter exceptions

Searches optimize over integers, but ${fractional.length} extreme-saturation
colors could only be certified with 0.1-granularity fractional parameters. They
are stored as-is and served verbatim; every other row is integer:

${fractionalTable({ stats, buckets, example, fractional })}

## Example record

\`\`\`js
// ${toHex(example.id)}
'${example.filter}' // loss: ${example.loss}
\`\`\`

## Regenerating this document

With the cached artifact in place (\`node docs/generate_dataset_doc.js\`), the
script verifies the file's size and pinned SHA-256, then re-runs the full scan
and rewrites this file plus the generated regions of \`README.md\`. Against a
manual copy: \`node docs/generate_dataset_doc.js --db /path/to/${RELEASE.dbFile}\`.
`

const regionBodies = ({ stats, example, fractional }) => ({
  'claim-summary': [
    `The dataset is a covering certificate: every one of the **${group(stats.total)} sRGB colors** has a stored`,
    'filter chain whose rendered loss (see the metric definition in',
    `[docs/dataset.md](docs/dataset.md#the-metric-rendered-loss)) is under 1%. Snapshot \`${RELEASE.snapshot}\``,
    'is the build pinned in this library: it ships checksummed, is verified on every',
    'download, and this summary regenerates from it — refusing to render unless',
    'every row passes.',
    '',
    `- Max rendered loss: \`${stats.max}\` (0 rows at or above 1)`,
    `- Average rendered loss: ${truncFixed(stats.avg, 5)}`,
    `- ${group(EXPECTED_ROWS - fractional.length)} rows use integer parameters; ${fractional.length} extreme-saturation colors use 0.1-granularity fractional parameters`,
    '',
    'Full loss statistics, the distribution chart, the schema, and the artifact',
    'checksums live in **[docs/dataset.md](docs/dataset.md)**.'
  ].join('\n'),
  'example-filter': `// ${example.filter}`,
  'example-filter-prefix': `// filter: brightness(0) saturate(1) ${example.filter}`,
  'example-record': [
    '// {',
    `//   id: ${example.id},`,
    `//   filter: '${example.filter}',`,
    `//   loss: ${example.loss}`,
    '// }'
  ].join('\n'),
  'example-record-raw': [
    '// [',
    '//   [',
    `//     { Name: 'id', Type: 'integer', Value: '${example.id}' },`,
    `//     { Name: 'filter', Type: 'text', Value: '${example.filter}' },`,
    `//     { Name: 'loss', Type: 'real', Value: '${example.loss}' }`,
    '//   ]',
    '// ]'
  ].join('\n')
})

const REGION_NAMES = Object.keys(regionBodies({
  stats: { total: 0, max: 0, avg: 0 },
  example: { id: 0, filter: '', loss: 0 },
  fractional: []
}))

const tagPattern = (kind) => new RegExp(`^(\\s*)(?:<!--|//) ${kind}:([a-z-]+?)(?: -->)?$`)

const indentBody = (body, indent) =>
  body.split('\n').map((line) => (line === '' ? line : indent + line)).join('\n')

const spliceReadme = (readme, bodies) => {
  const lines = readme.split('\n')
  const out = []
  const found = new Set()
  let active = null

  for (const line of lines) {
    const begin = tagPattern('BEGIN').exec(line)
    const end = tagPattern('END').exec(line)
    if (begin) {
      if (active !== null) throw new Error(`Nested BEGIN:${begin[2]} in README.md`)
      if (!bodies[begin[2]]) throw new Error(`Unknown generated region: ${begin[2]}`)
      active = begin[2]
      found.add(active)
      out.push(line, indentBody(bodies[active], begin[1]))
      continue
    }
    if (end) {
      if (active !== end[2]) throw new Error(`Unmatched END:${end[2]} in README.md`)
      active = null
      out.push(line)
      continue
    }
    if (active === null) out.push(line)
  }
  if (active !== null) throw new Error(`Unterminated region ${active} in README.md`)

  const missing = REGION_NAMES.filter((name) => !found.has(name))
  if (missing.length > 0) {
    throw new Error(`README.md is missing generated-region markers: ${missing.join(', ')}`)
  }
  return out.join('\n')
}

const main = async () => {
  const { dbPath } = parseArgs(process.argv.slice(2))
  console.log(`Verifying ${dbPath} against pinned sha256…`)
  await verifyArtifact(dbPath)

  const db = new DatabaseSync(dbPath, { readOnly: true })
  let data
  try {
    console.log('Scanning all rows (direct SQL over the database, ~10 s)…')
    data = collectStats(db)
  } finally {
    db.close()
  }

  const docPath = path.join(repoRoot, 'docs', 'dataset.md')
  fs.writeFileSync(docPath, buildDatasetDoc(data))
  console.log(`Wrote ${docPath}`)

  const readmePath = path.join(repoRoot, 'README.md')
  const readme = fs.readFileSync(readmePath, 'utf8')
  fs.writeFileSync(readmePath, spliceReadme(readme, regionBodies(data)))
  console.log(`Spliced generated regions into ${readmePath}`)

  console.log(`Covering claim re-verified: ${group(data.stats.total)} rows, 0 at loss >= 1, max ${data.stats.max}`)
}

main().catch((err) => {
  console.error(err.message)
  process.exitCode = 1
})
