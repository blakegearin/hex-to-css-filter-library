import assert from 'assert'
import undici from 'undici'

import { buildRowsUrl, remoteLookupFilter, remoteLookupColorRecord } from '../util/remote-dataset.js'
import DEFAULTS from '../util/defaults.js'
import { findRowByHex, rowsApiResponse } from './fixtures/new-schema-db.js'

const mockAgent = new undici.MockAgent()
mockAgent.disableNetConnect()

const ORIGIN = 'https://datasets-server.huggingface.co'

describe('remote-dataset', () => {
  before(() => undici.setGlobalDispatcher(mockAgent))

  const remote = DEFAULTS.remote
  const row = findRowByHex('#42dead')

  const mockRows = (payload, status = 200) => {
    const expectedUrl = new URL(buildRowsUrl(remote, row.id))
    mockAgent
      .get(ORIGIN)
      .intercept({ method: 'GET', path: `${expectedUrl.pathname}${expectedUrl.search}` })
      .reply(status, payload)
  }

  describe('buildRowsUrl()', () => {
    it('turns the color id into a single-row offset request', () => {
      assert.equal(
        buildRowsUrl(remote, 4382381),
        'https://datasets-server.huggingface.co/rows' +
          '?dataset=blakegearin%2Fhex-to-css-filter-covering-dataset' +
          '&config=default&split=train&offset=4382381&length=1'
      )
    })
  })

  describe('remoteLookupFilter()', () => {
    it('returns the stored chain for the id', async () => {
      mockRows(rowsApiResponse(row))
      assert.equal(await remoteLookupFilter(remote, row.id, fetch), row.filter)
      mockAgent.assertNoPendingInterceptors()
    })

    it('returns undefined when the server has no such row', async () => {
      const empty = { ...rowsApiResponse(row), rows: [] }
      mockRows(empty)
      assert.equal(await remoteLookupFilter(remote, row.id, fetch), undefined)
      mockAgent.assertNoPendingInterceptors()
    })

    it('refuses a row whose id does not match the requested one', async () => {
      const wrong = rowsApiResponse(row)
      wrong.rows[0].row.id = 999
      mockRows(wrong)
      await assert.rejects(
        remoteLookupFilter(remote, row.id, fetch),
        /row-order assumption is broken/
      )
      mockAgent.assertNoPendingInterceptors()
    })

    it('throws on a non-OK response', async () => {
      mockRows({ error: 'boom' }, 500)
      await assert.rejects(
        remoteLookupFilter(remote, row.id, fetch),
        /Dataset server returned HTTP 500/
      )
      mockAgent.assertNoPendingInterceptors()
    })

    it('throws on a malformed response', async () => {
      mockRows({ unexpected: true })
      await assert.rejects(
        remoteLookupFilter(remote, row.id, fetch),
        /Unexpected dataset server response/
      )
      mockAgent.assertNoPendingInterceptors()
    })
  })

  describe('remoteLookupColorRecord()', () => {
    it('maps the row to canonical Name/Type/Value records', async () => {
      mockRows(rowsApiResponse(row))
      assert.deepEqual(await remoteLookupColorRecord(remote, row.id, fetch), [[
        { Name: 'id', Type: 'integer', Value: String(row.id) },
        { Name: 'filter', Type: 'text', Value: row.filter },
        { Name: 'loss', Type: 'real', Value: String(row.loss) }
      ]])
      mockAgent.assertNoPendingInterceptors()
    })

    it('returns an empty array when the server has no such row', async () => {
      mockRows({ ...rowsApiResponse(row), rows: [] })
      assert.deepEqual(await remoteLookupColorRecord(remote, row.id, fetch), [])
      mockAgent.assertNoPendingInterceptors()
    })

    it('keeps null values as empty strings and unknown dtypes verbatim', async () => {
      const payload = rowsApiResponse(row)
      payload.rows[0].row.loss = null
      payload.features[2].type.dtype = 'bool'
      mockRows(payload)
      const canonical = await remoteLookupColorRecord(remote, row.id, fetch)
      assert.deepEqual(canonical[0][2], { Name: 'loss', Type: 'bool', Value: '' })
      mockAgent.assertNoPendingInterceptors()
    })
  })
})
