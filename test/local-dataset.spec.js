import assert from 'assert'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import zlib from 'node:zlib'
import { createHash } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'
import undici from 'undici'

import LocalDataset from '../util/local-dataset.js'
import { APP_DIR_NAME } from '../util/cache-location.js'
import {
  buildFixtureRelease,
  buildFixtureDbFile,
  findRowByHex
} from './fixtures/new-schema-db.js'

const mockAgent = new undici.MockAgent()
mockAgent.disableNetConnect()

const FIXTURE_ORIGIN = 'https://dataset.test'
const FIXTURE_PATH = '/2099.01.01/fixture-dataset.sqlite3.gz'

describe('LocalDataset', () => {
  const row = findRowByHex('#42dead')
  let tmpRoot
  let fixture

  before(() => {
    undici.setGlobalDispatcher(mockAgent)
    tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'htcf-local-'))
    fixture = buildFixtureRelease(tmpRoot)
  })

  after(() => fs.rmSync(tmpRoot, { recursive: true, force: true }))

  const mockGz = (body, origin = FIXTURE_ORIGIN, requestPath = FIXTURE_PATH) =>
    mockAgent.get(origin)
      .intercept({ method: 'GET', path: requestPath })
      .reply(200, body)

  const mockStatus = (status, origin = FIXTURE_ORIGIN, requestPath = FIXTURE_PATH) =>
    mockAgent.get(origin)
      .intercept({ method: 'GET', path: requestPath })
      .reply(status, { message: 'nope' })

  const freshCacheDir = () => fs.mkdtempSync(path.join(tmpRoot, 'cache-'))

  const datasetFor = (release, options = {}) => new LocalDataset({
    datasetRelease: release,
    ...options
  })

  describe('download-and-cache install story', () => {
    it('fetches from the release URL, verifies, and caches in the snapshot directory', async () => {
      const cacheDir = freshCacheDir()
      mockGz(fixture.gzBytes)
      const dataset = datasetFor(fixture.release, { cacheDir })

      await dataset.ensure()

      const cached = path.join(
        cacheDir, fixture.release.snapshot, fixture.release.dbFile
      )
      assert.equal(dataset.dbPath, cached)
      assert.ok(fs.existsSync(cached))
      assert.equal(fs.statSync(cached).size, fixture.dbSize)

      assert.equal(await dataset.lookupFilter(4382381), row.filter)
      dataset.close()
      mockAgent.assertNoPendingInterceptors()
    })

    it('never touches the network again once cached', async () => {
      const cacheDir = freshCacheDir()
      mockGz(fixture.gzBytes)
      const first = datasetFor(fixture.release, { cacheDir })
      await first.ensure()
      assert.equal(await first.lookupFilter(0), findRowByHex('#000000').filter)
      first.close()

      const second = datasetFor(fixture.release, { cacheDir })
      assert.equal(await second.lookupFilter(16777215), findRowByHex('#ffffff').filter)
      second.close()
      mockAgent.assertNoPendingInterceptors()
    })

    it('stores the snapshot (not the library version) in the cache path', () => {
      const dataset = datasetFor(fixture.release, { cacheDir: '/tmp/x' })
      assert.match(dataset.dbPath, /\/x\/2099\.01\.01\/fixture-dataset\.sqlite3$/)
    })

    it('derives the per-user cache location when neither dbPath nor cacheDir is set', () => {
      const dataset = new LocalDataset({ datasetRelease: fixture.release })
      assert.match(dataset.dbPath, new RegExp(
        `${APP_DIR_NAME}/datasets/2099\\.01\\.01/fixture-dataset\\.sqlite3$`
      ))
    })
  })

  describe('checksum verification', () => {
    it('rejects a downloaded artifact whose checksum does not match', async () => {
      const cacheDir = freshCacheDir()
      const mutated = Uint8Array.from(fixture.gzBytes)
      mutated[0] ^= 0xff
      mockGz(Buffer.from(mutated))

      const dataset = datasetFor(fixture.release, { cacheDir })
      await assert.rejects(
        dataset.ensure(),
        (error) => {
          assert.match(error.message, /checksum verification failed/)
          assert.match(error.message, new RegExp(fixture.release.gzSha256))
          assert.match(error.message, /nothing was cached/)
          return true
        }
      )

      const cached = path.join(cacheDir, fixture.release.snapshot, fixture.release.dbFile)
      assert.equal(fs.existsSync(cached), false)
      assert.deepEqual(fs.readdirSync(path.dirname(cached)), [])
      mockAgent.assertNoPendingInterceptors()
    })

    it('rejects a download whose size does not match the manifest', async () => {
      const cacheDir = freshCacheDir()
      const release = { ...fixture.release, gzSize: fixture.gzBytes.length - 64 }
      mockGz(fixture.gzBytes)

      const dataset = datasetFor(release, { cacheDir })
      await assert.rejects(dataset.ensure(), /unexpected download size/)
      mockAgent.assertNoPendingInterceptors()
    })

    it('rejects a gz stream that decompresses to a size mismatch', async () => {
      const cacheDir = freshCacheDir()
      const release = { ...fixture.release, dbSize: fixture.dbSize + 1 }
      mockGz(fixture.gzBytes)

      const dataset = datasetFor(release, { cacheDir })
      await assert.rejects(dataset.ensure(), /decompressed size mismatch/)
      mockAgent.assertNoPendingInterceptors()
    })

    it('rejects a decompressed artifact whose checksum does not match', async () => {
      const cacheDir = freshCacheDir()
      const release = {
        ...fixture.release,
        dbSha256: '0'.repeat(64)
      }
      mockGz(fixture.gzBytes)

      const dataset = datasetFor(release, { cacheDir })
      await assert.rejects(
        dataset.ensure(),
        /decompressed dataset artifact checksum verification failed/
      )
      mockAgent.assertNoPendingInterceptors()
    })

    it('falls back to the next mirror when one serves unverified bytes', async () => {
      const cacheDir = freshCacheDir()
      const mutated = Uint8Array.from(fixture.gzBytes)
      mutated[0] ^= 0xff
      const urls = [
        'https://mirror-a.test/2099.01.01/fixture-dataset.sqlite3.gz',
        'https://mirror-b.test/2099.01.01/fixture-dataset.sqlite3.gz'
      ]
      mockGz(Buffer.from(mutated), 'https://mirror-a.test', '/2099.01.01/fixture-dataset.sqlite3.gz')
      mockGz(fixture.gzBytes, 'https://mirror-b.test', '/2099.01.01/fixture-dataset.sqlite3.gz')

      const dataset = datasetFor({ ...fixture.release, urls }, { cacheDir })
      assert.equal(await dataset.lookupFilter(4382381), row.filter)
      dataset.close()
      mockAgent.assertNoPendingInterceptors()
    })
  })

  describe('artifact host failure', () => {
    it('produces an actionable error naming the URL and the manual escape hatch', async () => {
      const cacheDir = freshCacheDir()
      mockStatus(500)

      const dataset = datasetFor(fixture.release, { cacheDir })
      await assert.rejects(dataset.ensure(), (error) => {
        assert.match(error.message, /Unable to download the hex-to-css filter dataset/)
        assert.match(error.message, /snapshot 2099\.01\.01/)
        assert.match(error.message, new RegExp(`${FIXTURE_ORIGIN}${FIXTURE_PATH}`))
        assert.match(error.message, /HTTP 500/)
        assert.match(error.message, /Manual escape hatch:/)
        assert.match(error.message, /manual escape hatch fixture line/)
        assert.match(error.message, /dbPath/)
        return true
      })

      const cached = path.join(cacheDir, fixture.release.snapshot, fixture.release.dbFile)
      assert.equal(fs.existsSync(cached), false)
      mockAgent.assertNoPendingInterceptors()
    })
  })

  describe('cache recovery', () => {
    const cachedPathFor = (cacheDir) =>
      path.join(cacheDir, fixture.release.snapshot, fixture.release.dbFile)

    it('re-downloads a corrupt cache transparently', async () => {
      const cacheDir = freshCacheDir()
      mockGz(fixture.gzBytes)
      const dataset = datasetFor(fixture.release, { cacheDir })
      await dataset.ensure()
      dataset.close()

      const cached = cachedPathFor(cacheDir)
      fs.writeFileSync(cached, Buffer.alloc(fixture.dbSize, 0xab))

      mockGz(fixture.gzBytes)
      const revived = datasetFor(fixture.release, { cacheDir })
      assert.equal(await revived.lookupFilter(4382381), row.filter)
      revived.close()
      mockAgent.assertNoPendingInterceptors()
    })

    it('re-downloads a truncated cache', async () => {
      const cacheDir = freshCacheDir()
      mockGz(fixture.gzBytes)
      const dataset = datasetFor(fixture.release, { cacheDir })
      await dataset.ensure()
      dataset.close()

      fs.writeFileSync(cachedPathFor(cacheDir), 'too small')

      mockGz(fixture.gzBytes)
      const revived = datasetFor(fixture.release, { cacheDir })
      assert.equal(await revived.lookupFilter(4382381), row.filter)
      revived.close()
      mockAgent.assertNoPendingInterceptors()
    })

    it('re-downloads a valid database that lacks the color rows', async () => {
      const cacheDir = freshCacheDir()
      const cached = cachedPathFor(cacheDir)
      fs.mkdirSync(path.dirname(cached), { recursive: true })
      const db = new DatabaseSync(cached)
      db.exec('CREATE TABLE color (id INTEGER PRIMARY KEY, filter TEXT, loss REAL)')
      db.prepare('INSERT INTO color VALUES (?, ?, ?)').run(1, 'invert(1%)', 0)
      db.close()
      fs.truncateSync(cached, fixture.dbSize)

      mockGz(fixture.gzBytes)
      const dataset = datasetFor(fixture.release, { cacheDir })
      assert.equal(await dataset.lookupFilter(4382381), row.filter)
      dataset.close()
      mockAgent.assertNoPendingInterceptors()
    })

    it('throws when a checksum-verified download still cannot be opened', async () => {
      const cacheDir = freshCacheDir()
      const payload = Buffer.from('not a database but honestly hashed')
      const gzBytes = zlib.gzipSync(payload)
      const sha = (bytes) => createHash('sha256').update(bytes).digest('hex')
      const release = {
        ...fixture.release,
        gzSize: gzBytes.length,
        gzSha256: sha(gzBytes),
        dbSize: payload.length,
        dbSha256: sha(payload)
      }
      mockGz(gzBytes)

      const dataset = datasetFor(release, { cacheDir })
      await assert.rejects(
        dataset.ensure(),
        /passed checksum verification but could not be opened/
      )
    })
  })

  describe('dbPath option', () => {
    it('uses the provided path instead of the cache directory', async () => {
      const dbPath = path.join(freshCacheDir(), 'air-gapped-copy', 'custom.sqlite3')
      mockGz(fixture.gzBytes)
      const dataset = datasetFor(fixture.release, { dbPath })

      await dataset.ensure()
      assert.ok(fs.existsSync(dbPath))
      assert.equal(await dataset.lookupFilter(4382381), row.filter)
      dataset.close()
      mockAgent.assertNoPendingInterceptors()
    })

    it('works fully offline against a pre-placed verified database', async () => {
      const dbPath = buildFixtureDbFile(path.join(freshCacheDir(), 'preplaced.sqlite3'))
      const dataset = datasetFor(fixture.release, { dbPath })

      assert.equal(await dataset.lookupFilter(4382381), row.filter)
      dataset.close()
      mockAgent.assertNoPendingInterceptors()
    })
  })

  describe('queryDb()', () => {
    it('maps rows to canonical Name/Type/Value records', async () => {
      const dbPath = buildFixtureDbFile(path.join(freshCacheDir(), 'canonical.sqlite3'))
      const dataset = datasetFor(fixture.release, { dbPath })

      assert.deepEqual(await dataset.queryDb('SELECT NULL AS x'), [
        [{ Name: 'x', Type: null, Value: '' }]
      ])
      assert.deepEqual(await dataset.lookupColorRecord(4382381), [[
        { Name: 'id', Type: 'integer', Value: '4382381' },
        { Name: 'filter', Type: 'text', Value: row.filter },
        { Name: 'loss', Type: 'real', Value: '0.8793432176' }
      ]])
      assert.deepEqual(await dataset.lookupColorRecord(99999999), [])
      assert.equal(await dataset.lookupFilter(99999999), undefined)
      dataset.close()
    })
  })

  describe('close()', () => {
    it('is a no-op before the database is opened', () => {
      const dataset = datasetFor(fixture.release, { cacheDir: freshCacheDir() })
      dataset.close()
    })

    it('allows a fresh ensure after closing', async () => {
      const cacheDir = freshCacheDir()
      mockGz(fixture.gzBytes)
      const dataset = datasetFor(fixture.release, { cacheDir })
      await dataset.ensure()
      dataset.close()
      await dataset.ensure()
      assert.equal(await dataset.lookupFilter(4382381), row.filter)
      dataset.close()
      mockAgent.assertNoPendingInterceptors()
    })
  })
})
