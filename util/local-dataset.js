import os from 'node:os'
import path from 'node:path'
import fs from 'node:fs'
import { createHash } from 'node:crypto'
import { Readable, Transform } from 'node:stream'
import { pipeline } from 'node:stream/promises'
import { createGunzip } from 'node:zlib'
import { DatabaseSync } from 'node:sqlite'

import { defaultCacheDir, cachedDbPath } from './cache-location.js'

const hashTap = (state) =>
  new Transform({
    transform (chunk, encoding, callback) {
      state.hash.update(chunk)
      state.bytes += chunk.length
      callback(null, chunk)
    }
  })

const datasetDownloadError = (release, failures, targetPath) => new Error(
  [
    `Unable to download the hex-to-css filter dataset (snapshot ${release.snapshot}) from any known location:`,
    ...failures.map((failure) => `  - ${failure}`),
    '',
    'Manual escape hatch:',
    ...release.manualInstructions.map((line) => `  ${line}`),
    '',
    `After placing a verified copy yourself, point the library at it with { dbPath: '${targetPath}' } (expected location).`
  ].join('\n')
)

const checksumError = (label, url, expected, actual) => new Error(
  `${label} checksum verification failed for ${url}: expected sha256 ${expected}, received ${actual}. The file was rejected; nothing was cached.`
)

export default class LocalDataset {
  constructor (options = {}) {
    this.release = options.datasetRelease
    this.fetchFunction = options.fetchFunction || fetch
    this.dbPath = options.dbPath ||
      cachedDbPath(
        options.cacheDir ||
          defaultCacheDir({
            platform: process.platform,
            env: process.env,
            homedir: os.homedir()
          }),
        this.release
      )
    this.db = null
    this.ready = null
  }

  ensure () {
    if (this.ready === null) this.ready = this.#prepare()
    return this.ready
  }

  async #prepare () {
    if (await this.#usable()) return this.dbPath

    await this.#wipe()
    await this.#download()

    if (!await this.#usable()) {
      throw new Error(
        `The downloaded dataset at ${this.dbPath} passed checksum verification but could not be opened as the expected SQLite database. Delete the file and retry, or report this with the dataset snapshot ${this.release.snapshot}.`
      )
    }
    return this.dbPath
  }

  async #usable () {
    try {
      const stat = await fs.promises.stat(this.dbPath)
      if (stat.size !== this.release.dbSize) return false
      this.db = new DatabaseSync(this.dbPath, { readOnly: true })
      const probe = this.db.prepare("SELECT filter FROM 'color' WHERE id = 0").get()
      if (probe === undefined) {
        this.db.close()
        this.db = null
        return false
      }
      return true
    } catch (e) {
      if (this.db !== null) {
        this.db.close()
        this.db = null
      }
      return false
    }
  }

  async #wipe () {
    await fs.promises.rm(this.dbPath, { force: true })
  }

  async #download () {
    const dir = path.dirname(this.dbPath)
    await fs.promises.mkdir(dir, { recursive: true })
    const tmpGz = path.join(dir, `${path.basename(this.dbPath)}.download.gz.part`)
    const tmpDb = path.join(dir, `${path.basename(this.dbPath)}.download.part`)
    const failures = []

    for (const url of this.release.urls) {
      try {
        await this.#fetchToGz(url, tmpGz)
        await this.#gunzipTo(tmpGz, tmpDb)
        await fs.promises.rename(tmpDb, this.dbPath)
        return
      } catch (e) {
        failures.push(`${url}: ${e.message}`)
      } finally {
        await fs.promises.rm(tmpGz, { force: true })
        await fs.promises.rm(tmpDb, { force: true })
      }
    }

    throw datasetDownloadError(this.release, failures, this.dbPath)
  }

  async #fetchToGz (url, dest) {
    const response = await this.fetchFunction(url)
    if (!response.ok) {
      throw new Error(`artifact host returned HTTP ${response.status}`)
    }
    const state = { hash: createHash('sha256'), bytes: 0 }
    await pipeline(
      Readable.fromWeb(response.body),
      hashTap(state),
      fs.createWriteStream(dest)
    )
    if (state.bytes !== this.release.gzSize) {
      throw new Error(`unexpected download size: expected ${this.release.gzSize} bytes, received ${state.bytes}`)
    }
    const actual = state.hash.digest('hex')
    if (actual !== this.release.gzSha256) {
      throw checksumError('gzipped dataset artifact', url, this.release.gzSha256, actual)
    }
  }

  async #gunzipTo (src, dest) {
    const state = { hash: createHash('sha256'), bytes: 0 }
    await pipeline(
      fs.createReadStream(src),
      createGunzip(),
      hashTap(state),
      fs.createWriteStream(dest)
    )
    if (state.bytes !== this.release.dbSize) {
      throw new Error(`decompressed size mismatch: expected ${this.release.dbSize} bytes, received ${state.bytes}`)
    }
    const actual = state.hash.digest('hex')
    if (actual !== this.release.dbSha256) {
      throw checksumError('decompressed dataset artifact', src, this.release.dbSha256, actual)
    }
  }

  #statement (sql) {
    return this.db.prepare(sql)
  }

  async lookupFilter (hexColorInt) {
    await this.ensure()
    const row = this.#statement("SELECT filter FROM 'color' WHERE id = ?").get(hexColorInt)
    return row === undefined ? undefined : row.filter
  }

  async lookupColorRecord (hexColorInt) {
    await this.ensure()
    const statement = this.#statement("SELECT * FROM 'color' WHERE id = ?")
    return rowsToCanonical(statement, [statement.get(hexColorInt)].filter((row) => row !== undefined))
  }

  async queryDb (sql) {
    await this.ensure()
    const statement = this.#statement(sql)
    return rowsToCanonical(statement, statement.all())
  }

  close () {
    if (this.db !== null) {
      this.db.close()
      this.db = null
    }
    this.ready = null
  }
}

const rowsToCanonical = (statement, rows) => {
  const columns = statement.columns()
  return rows.map(
    (row) => columns.map(
      (column) => ({
        Name: column.name,
        Type: column.type === null ? null : String(column.type).toLowerCase(),
        Value: row[column.name] == null ? '' : String(row[column.name])
      })
    )
  )
}
