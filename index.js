import base64 from 'base-64'
import utf8 from 'utf8'

import DEFAULTS from './util/defaults.js'

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
  constructor (apiKey, options = {}) {
    if (apiKey == null) throw new Error('Required parameter apiKey is not present')
    this.apiKey = apiKey

    this.apiUrl = options.apiUrl || DEFAULTS.apiUrl
    this.apiEndpoint = options.apiEndpoint || DEFAULTS.apiEndpoint
    this.dbOwner = options.dbOwner || DEFAULTS.dbOwner
    this.dbName = options.dbName || DEFAULTS.dbName

    // Check if running in Node
    // `global` is not defined when running on web
    if ((typeof process !== 'undefined') && (process.release.name === 'node')) {
      this.headersClass = global.Headers = options.headersClass || DEFAULTS.headersClass
      this.formDataClass = global.FormData = options.formDataClass || DEFAULTS.formDataClass
      this.requestClass = global.Request = options.requestClass || DEFAULTS.requestClass
      this.fetchFunction = global.fetch = options.fetchFunction || DEFAULTS.fetchFunction
    }
  }

  async queryDb (sql, options = {}) {
    if (sql == null) throw new Error('Required parameter sql is not present')

    const getFirstValue = options.getFirstValue || DEFAULTS.getFirstValue

    const requestBody = new FormData()

    if (this.apiKey) requestBody.append('apikey', this.apiKey)
    if (this.dbOwner) requestBody.append('dbowner', this.dbOwner)
    if (this.dbName) requestBody.append('dbname', this.dbName)

    const requestSql = base64.encode(utf8.encode(sql))
    requestBody.append('sql', requestSql)

    const requestOptions = {
      method: 'POST',
      headers: new Headers(),
      mode: 'cors',
      type: 'json',
      cache: 'default',
      body: requestBody
    }

    const requestUrl = `${this.apiUrl}${this.apiEndpoint}`
    const request = new Request(requestUrl, requestOptions)
    const response = await fetch(request, requestOptions).then((response) => response.json())

    if (getFirstValue) {
      const responseFirstElement = response[0]
      if (responseFirstElement) return responseFirstElement[0].Value
    }

    return response
  }

  async fetchColorRecord (hexColor, options = {}) {
    const raw = options.raw || false

    const hexColorInt = hexColorToInt(hexColor)

    const response = await this.queryDb(`SELECT * FROM 'color' WHERE id = ${hexColorInt}`)

    if (response === null || (Array.isArray(response) && response.length === 0)) {
      throw colorNotFound(hexColor, hexColorInt)
    } else if (response.error) {
      throw new Error(response.error)
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

    const filter = await this.queryDb(
      `SELECT filter FROM 'color' WHERE id = ${hexColorInt}`,
      { getFirstValue: true }
    )

    if (typeof filter !== 'string') {
      if (filter && filter.error) throw new Error(filter.error)
      throw colorNotFound(hexColor, hexColorInt)
    }

    const filterArray = []
    if (filterPrefix) filterArray.push('filter:')
    if (preBlacken) filterArray.push('brightness(0) saturate(1)')
    if (filter) filterArray.push(filter)

    this.filter = filterArray.join(' ')
    return this.filter
  }
}
