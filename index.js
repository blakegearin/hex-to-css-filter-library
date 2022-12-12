import base64 from 'base-64'
import fetch, { FormData, Headers, Request } from 'node-fetch'
import utf8 from 'utf8'

export default class HexToCssFilterLibrary {
  constructor (apiKey, options = {}) {
    const debug = options.debug || false

    this.apiKey = apiKey
    if (debug) console.log(`apiKey: ${this.apiKey}`)

    if (debug) {
      console.log('options')
      console.dir(options)
    }

    this.dbUrl = options.dbUrl || 'https://api.dbhub.io/v1/query'
    if (debug) console.log(`dbUrl: ${this.dbUrl}`)

    this.dbOwner = options.dbOwner || 'blakegearin'
    if (debug) console.log(`dbOwner: ${this.dbOwner}`)

    this.dbName = options.dbName || 'hex-to-css-filter-db.sqlite3'
    if (debug) console.log(`dbName: ${this.dbName}`)

    this.base64EncodeSql = options.base64EncodeSql || true
    if (debug) console.log(`base64EncodeSql: ${this.base64EncodeSql}`)
  }

  async queryDb (sql, options = {}) {
    const debug = options.debug || false
    const getFirstValue = options.getFirstValue || false
    const requestBody = options.requestBody || new FormData()

    if (debug) console.log(`requestBody: ${requestBody}`)

    if (this.apiKey) requestBody.append('apikey', this.apiKey)
    if (this.dbOwner) requestBody.append('dbowner', this.dbOwner)
    if (this.dbName) requestBody.append('dbname', this.dbName)

    const requestSql = this.base64EncodeSql ? base64.encode(utf8.encode(sql)) : sql
    if (debug) console.log(`requestSql: ${requestSql}`)

    requestBody.append('sql', requestSql)

    if (debug) {
      console.log('[...requestBody.entries()')
      console.dir([...requestBody.entries()])
    }

    const requestOptions = {
      method: 'POST',
      headers: new Headers(),
      mode: 'cors',
      type: 'json',
      cache: 'default',
      body: requestBody
    }

    if (debug) {
      console.log('requestOptions')
      console.dir(requestOptions)
    }

    const request = new Request(this.dbUrl, requestOptions)
    const response = await fetch(request, requestOptions)
      .then(function (response) { return response.json() })

    if (debug) {
      console.log('response')
      console.dir(response)
    }

    if (getFirstValue) {
      const responseFirstElement = response[0]
      if (responseFirstElement) return responseFirstElement[0].Value
    }

    return response
  }

  async fetchFilter (hexColor, options = {}) {
    const debug = options.debug || false
    const filterPrefix = options.filterPrefix || false
    const preBlacken = options.preBlacken || false

    if (debug) console.log(`hexColor: ${hexColor}`)

    if (
      (hexColor.length === 3 && hexColor.charAt(0) !== '#') ||
      (hexColor.length === 4 && hexColor.charAt(0) === '#')
    ) {
      hexColor = hexColor.replace(/(\w)(\w)(\w)/g, '$1$1$2$2$3$3')
    }

    if (debug) console.log(`hexColor: ${hexColor}`)

    const validHexColor = /^#?[0-9a-f]{6}$/i.test(hexColor)

    if (!validHexColor) return `Hex color is not valid: ${hexColor}`

    const hexColorInt = parseInt(hexColor.replace('#', ''), 16)
    if (debug) console.log(`hexColorInt: ${hexColorInt}`)

    const response = await this.queryDb(
      `SELECT * FROM 'color' WHERE ID = ${hexColorInt}`
    )

    if (response === null) {
      return `Color not found in database | hex: ${this.fullHexColor} | integer: ${hexColorInt}`
    }

    // Convert from { Name: "invert", Type: "4", Value: "50" } to { invert: "50" }
    const record = response[0].reduce(
      function (acc, cur) {
        acc[cur.Name] = cur.Value
        return acc
      },
      {}
    )

    if (debug) {
      console.log('record')
      console.dir(record)
    }

    const filterArray = []
    if (filterPrefix) filterArray.push('filter:')
    if (preBlacken) filterArray.push('brightness(0) saturate(1)')

    for (const [key, value] of Object.entries(record)) {
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

    if (debug) {
      console.log('filterArray')
      console.dir(filterArray)
    }

    this.filter = filterArray.join(' ')
    return this.filter
  }
}
