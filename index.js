import DEFAULTS from './util/defaults.js'
import { remoteLookupFilter, remoteLookupColorRecord } from './util/remote-dataset.js'

const nodeRuntime = () =>
  typeof process !== 'undefined' && process.release && process.release.name === 'node'

export const resolveSource = (source, isNode) => {
  if (source) return source
  if (isNode) return 'local'
  return 'remote'
}

export const validateSource = (source, isNode) => {
  if (source !== 'local' && source !== 'remote') {
    throw new Error(`Unknown source: ${source}; expected 'local' or 'remote'`)
  }
  if (source === 'local' && !isNode) {
    throw new Error('The local dataset needs Node.js (there is no file system here); construct with { source: \'remote\' } to query over the network.')
  }
  return source
}

const hexColorToInt = (hexColor) => {
  if (hexColor == null) throw new Error('Required parameter hexColor is not present')

  if (
    (hexColor.length === 3 && hexColor.charAt(0) !== '#') ||
    (hexColor.length === 4 && hexColor.charAt(0) === '#')
  ) {
    hexColor = hexColor.replace(/(\w)(\w)(\w)/g, '$1$1$2$2$3$3')
  }

  const validHexColor = /^#?[0-9a-f]{6}$/i.test(hexColor)
  if (!validHexColor) throw new Error(`Hex color is not valid: ${hexColor}`)

  return parseInt(hexColor.replace('#', ''), 16)
}

const colorNotFound = (hexColor, hexColorInt) => new Error(
  `Color not found in database | hex: ${hexColor} | integer: ${hexColorInt}`
)

export default class HexToCssFilterLibrary {
  // v2 called the constructor (apiKey, options); a string apiKey is accepted
  // and ignored so existing call sites keep working.
  constructor (first = {}, second = {}) {
    const options = (typeof first === 'string' || first === null || first === undefined)
      ? second
      : first

    const isNode = nodeRuntime()
    this.source = validateSource(resolveSource(options.source, isNode), isNode)

    this.dbPath = options.dbPath || DEFAULTS.dbPath
    this.cacheDir = options.cacheDir || DEFAULTS.cacheDir
    this.datasetRelease = options.datasetRelease || DEFAULTS.datasetRelease
    this.remote = options.remote || DEFAULTS.remote
    this.fetchFunction = options.fetchFunction || DEFAULTS.fetchFunction

    this.localDataset = null
  }

  async #local () {
    if (this.localDataset === null) {
      const { default: LocalDataset } = await import('./util/local-dataset.js')
      this.localDataset = new LocalDataset({
        datasetRelease: this.datasetRelease,
        dbPath: this.dbPath,
        cacheDir: this.cacheDir,
        fetchFunction: this.fetchFunction
      })
    }
    return this.localDataset
  }

  async lookupFilter (hexColorInt) {
    if (this.source === 'local') {
      return (await this.#local()).lookupFilter(hexColorInt)
    }
    return remoteLookupFilter(this.remote, hexColorInt, this.fetchFunction)
  }

  async lookupColorRecord (hexColorInt) {
    if (this.source === 'local') {
      return (await this.#local()).lookupColorRecord(hexColorInt)
    }
    return remoteLookupColorRecord(this.remote, hexColorInt, this.fetchFunction)
  }

  async queryDb (sql, options = {}) {
    if (sql == null) throw new Error('Required parameter sql is not present')

    if (this.source !== 'local') {
      throw new Error('queryDb() runs arbitrary SQL against the local dataset. Remote (browser) builds only support lookupFilter/fetchColorRecord; construct with { source: \'local\' } on Node.')
    }

    const getFirstValue = options.getFirstValue || DEFAULTS.getFirstValue

    const dataset = await this.#local()
    const response = await dataset.queryDb(sql)

    if (getFirstValue) {
      const responseFirstElement = response[0]
      if (responseFirstElement) return responseFirstElement[0].Value
    }

    return response
  }

  async fetchColorRecord (hexColor, options = {}) {
    const raw = options.raw || false

    const hexColorInt = hexColorToInt(hexColor)

    const response = await this.lookupColorRecord(hexColorInt)

    if (Array.isArray(response) && response.length === 0) {
      throw colorNotFound(hexColor, hexColorInt)
    } else if (raw) {
      return response
    }

    return response[0].reduce(
      (acc, cur) => {
        const asNumber = Number(cur.Value)
        acc[cur.Name] = cur.Value !== '' && Number.isFinite(asNumber) ? asNumber : cur.Value
        return acc
      },
      {}
    )
  }

  async fetchFilter (hexColor, options = {}) {
    const hexColorInt = hexColorToInt(hexColor)

    const filterPrefix = options.filterPrefix || false
    const preBlacken = options.preBlacken || false

    const filter = await this.lookupFilter(hexColorInt)

    if (typeof filter !== 'string') {
      throw colorNotFound(hexColor, hexColorInt)
    }

    const filterArray = []
    if (filterPrefix) filterArray.push('filter:')
    if (preBlacken) filterArray.push('brightness(0) saturate(1)')
    if (filter) filterArray.push(filter)

    this.filter = filterArray.join(' ')
    return this.filter
  }

  close () {
    if (this.localDataset === null) return
    this.localDataset.close()
    this.localDataset = null
  }
}
