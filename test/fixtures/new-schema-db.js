// Hand-built fixture for the rebuilt schema: color (id INTEGER PRIMARY KEY, filter TEXT, loss REAL)
// Rows copied from the final monolith; the suite never touches the 1.7 GB artifact.
import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'
import { createHash } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'

export const COLOR_ROWS = [
  {
    id: 0,
    filter: 'invert(47%) sepia(7%) saturate(2949%) hue-rotate(60deg) brightness(39%) contrast(177%)',
    loss: 0
  },
  {
    id: 3355443,
    filter: 'invert(0%) sepia(8%) saturate(23908%) hue-rotate(288deg) brightness(114%) contrast(60%)',
    loss: 0
  },
  {
    id: 4382381,
    filter: 'invert(95%) sepia(18%) saturate(20940%) hue-rotate(66deg) brightness(157%) contrast(74%)',
    loss: 0.8793432176
  },
  {
    id: 16777215,
    filter: 'invert(99%) sepia(4%) saturate(72%) hue-rotate(352deg) brightness(116%) contrast(100%)',
    loss: 0
  }
]

export const findRowByHex = (hexColor) => {
  const hexColorInt = parseInt(hexColor.replace('#', ''), 16)
  return COLOR_ROWS.find((row) => row.id === hexColorInt)
}

export const buildFixtureDbFile = (dbPath) => {
  const db = new DatabaseSync(dbPath)
  db.exec('CREATE TABLE color (id INTEGER PRIMARY KEY, filter TEXT, loss REAL)')
  const insert = db.prepare('INSERT INTO color VALUES (?, ?, ?)')
  COLOR_ROWS.forEach((row) => insert.run(row.id, row.filter, row.loss))
  db.close()
  return dbPath
}

export const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex')

// A miniature, fully real "release": a fixture SQLite file gzipped, with the
// sizes/hashes a pinned manifest would carry, served from the mock origin.
export const buildFixtureRelease = (dir) => {
  const dbPath = buildFixtureDbFile(path.join(dir, 'fixture-dataset.sqlite3'))
  const dbBytes = fs.readFileSync(dbPath)
  const gzBytes = zlib.gzipSync(dbBytes)
  return {
    gzBytes,
    dbSize: dbBytes.length,
    release: {
      snapshot: '2099.01.01',
      dbFile: 'fixture-dataset.sqlite3',
      gzFile: 'fixture-dataset.sqlite3.gz',
      gzSize: gzBytes.length,
      gzSha256: sha256(gzBytes),
      dbSize: dbBytes.length,
      dbSha256: sha256(dbBytes),
      urls: ['https://dataset.test/2099.01.01/fixture-dataset.sqlite3.gz'],
      manualInstructions: ['manual escape hatch fixture line']
    }
  }
}

export const rowsApiResponse = (row) => ({
  features: [
    { feature_idx: 0, name: 'id', type: { dtype: 'int64', _type: 'Value' } },
    { feature_idx: 1, name: 'filter', type: { dtype: 'string', _type: 'Value' } },
    { feature_idx: 2, name: 'loss', type: { dtype: 'float64', _type: 'Value' } }
  ],
  rows: [{ row_idx: row.id, row: { id: row.id, filter: row.filter, loss: row.loss } }],
  num_rows_total: 16777216,
  num_rows_per_page: 100
})
