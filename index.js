import base64 from 'base-64'
import utf8 from 'utf8'

import DEFAULTS from './util/defaults.js'

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
    const response = await fetch(request, requestOptions)
      .then(function (response) { return response.json() })

    if (getFirstValue) {
      const responseFirstElement = response[0]
      if (responseFirstElement) {
        return responseFirstElement[0].Value
      }
    }

    return response
  }

  async fetchColorRecord (hexColor, options = {}) {
    if (hexColor == null) throw new Error('Required parameter hexColor is not present')

    const raw = options.raw || false

    if (
      (hexColor.length === 3 && hexColor.charAt(0) !== '#') ||
      (hexColor.length === 4 && hexColor.charAt(0) === '#')
    ) {
      hexColor = hexColor.replace(/(\w)(\w)(\w)/g, '$1$1$2$2$3$3')
    }

    const validHexColor = /^#?[0-9a-f]{6}$/i.test(hexColor)
    if (!validHexColor) throw new Error(`Hex color is not valid: ${hexColor}`)

    const hexColorInt = parseInt(hexColor.replace('#', ''), 16)

    const response = await this.queryDb(`SELECT * FROM 'color' WHERE ID = ${hexColorInt}`)

    if (response === null) {
      const error =
        `Color not found in database | hex: ${this.hexColor} | integer: ${hexColorInt}`
      throw new Error(error)
    } else if (response.error) {
      throw new Error(response.error)
    } else if (raw) {
      return response
    }

    // Convert from { Name: "invert", Type: "4", Value: "50" } to { invert: "50" }
    const record = response[0].reduce(
      (acc, cur) => {
        acc[cur.Name] = (cur.Name === 'loss') ? parseFloat(cur.Value) : parseInt(cur.Value)
        return acc
      },
      {}
    )

    return record
  }

  async fetchFilter (hexColor, options = {}) {
    const colorRecord = await this.fetchColorRecord(hexColor, options)

    const filterPrefix = options.filterPrefix || false
    const preBlacken = options.preBlacken || false

    const filterArray = []
    if (filterPrefix) filterArray.push('filter:')
    if (preBlacken) filterArray.push('brightness(0) saturate(1)')

    for (const [key, value] of Object.entries(colorRecord)) {
      if (value === 0) continue

      let valueUnit

      switch (key) {
        case 'id':
        case 'loss':
          continue
        case 'hue-rotate':
          valueUnit = 'deg'
          break
        default:
          valueUnit = '%'
      }

      // Convert from { invert: "50" } to "invert(50%)"
      filterArray.push(`${key}(${value}${valueUnit})`)
    }

    this.filter = filterArray.join(' ')
    return this.filter
  }
}
