import assert from 'assert'
import { expect } from 'chai'
import sinon from 'sinon'
import undici from 'undici'

import HexToCssFilterLibrary from '../index.js'
import DEFAULTS from '../util/defaults.js'
import {
  findRowByHex,
  fixtureQueryDb,
  selectAllResponse,
  selectFilterResponse
} from './fixtures/new-schema-db.js'

const mockAgent = new undici.MockAgent()
mockAgent.disableNetConnect()
undici.setGlobalDispatcher(mockAgent)

describe('HexToCssFilterLibrary', () => {
  const apiKey = 'testApiKey'
  const responseData = 'stubbedResponse'
  const testValue = 'testValue'

  let hexToCssFilterLibrary

  describe('constructor()', () => {
    describe('parameters', () => {
      describe('apiKey', () => {
        describe('when null', () => {
          it('should throw error', () => {
            assert.throws(() => new HexToCssFilterLibrary(null))
          })
        })

        describe('when undefined', () => {
          it('should throw error', () => {
            assert.throws(() => new HexToCssFilterLibrary(undefined))
          })
        })
      })

      describe('options', () => {
        const optionParameters = [
          'apiUrl',
          'apiEndpoint',
          'dbOwner',
          'dbName',
          'headersClass',
          'formDataClass',
          'requestClass',
          'fetchFunction'
        ]
        optionParameters.forEach((parameterName) => {
          describe(parameterName, () => {
            describe('when null', () => {
              const options = {}
              options[parameterName] = null

              it('should be set to default value', () => {
                const hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey, options)
                assert.equal(hexToCssFilterLibrary[parameterName], DEFAULTS[parameterName])
              })
            })

            describe('when undefined', () => {
              const options = {}
              options[parameterName] = undefined

              it('should be set to default value', () => {
                const hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey, options)
                assert.equal(hexToCssFilterLibrary[parameterName], DEFAULTS[parameterName])
              })
            })

            describe('when defined', () => {
              const options = {}
              options[parameterName] = testValue

              it(`should be set to options.${parameterName}`, () => {
                const hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey, options)
                assert.equal(hexToCssFilterLibrary[parameterName], testValue)
              })
            })
          })
        })
      })
    })
  })

  describe('queryDb()', () => {
    beforeEach(() => {
      hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey)
    })

    describe('parameters', () => {
      describe('sql', () => {
        describe('when null', () => {
          const sql = null

          it('should throw error', async () => {
            try {
              hexToCssFilterLibrary.queryDb(sql)
            } catch (e) {
              expect(e).to.be.instanceOf(Error)
            }
          })
        })

        describe('when undefined', () => {
          const sql = undefined

          it('should throw error', async () => {
            try {
              hexToCssFilterLibrary.queryDb(sql)
            } catch (e) {
              expect(e).to.be.instanceOf(Error)
            }
          })
        })

        describe('when defined', () => {
          const sql = 'SELECT COUNT() FROM color'

          beforeEach(() => {
            mockAgent.get(DEFAULTS.apiUrl)
              .intercept({ method: 'POST', path: DEFAULTS.apiEndpoint })
              .reply(200, { data: responseData })
          })

          it('should make a call to the defaults apiUrl and apiEndpoint', async () => {
            assert.equal(
              (await hexToCssFilterLibrary.queryDb(sql)).data,
              responseData
            )
            mockAgent.assertNoPendingInterceptors()
          })
        })
      })
    })

    describe('options', () => {
      const sql = 'SELECT COUNT() FROM color'

      describe('getFirstValue', () => {
        describe('when null', () => {
          const options = {
            getFirstValue: null
          }

          beforeEach(() => {
            mockAgent.get(DEFAULTS.apiUrl)
              .intercept({ method: 'POST', path: DEFAULTS.apiEndpoint })
              .reply(200, { data: responseData })
          })

          it('should be set to default value', async () => {
            assert.equal(
              (await hexToCssFilterLibrary.queryDb(sql, options)).data,
              responseData
            )
            mockAgent.assertNoPendingInterceptors()
          })
        })

        describe('when undefined', () => {
          const options = {
            getFirstValue: undefined
          }

          beforeEach(() => {
            mockAgent.get(DEFAULTS.apiUrl)
              .intercept({ method: 'POST', path: DEFAULTS.apiEndpoint })
              .reply(200, { data: responseData })
          })

          it('should be set to default value', async () => {
            assert.equal(
              (await hexToCssFilterLibrary.queryDb(sql, options)).data,
              responseData
            )
            mockAgent.assertNoPendingInterceptors()
          })
        })

        describe('when true', () => {
          const options = {
            getFirstValue: true
          }

          describe('when the call\'s returns a nested array with an object containing Value', () => {
            beforeEach(() => {
              mockAgent.get(DEFAULTS.apiUrl)
                .intercept({ method: 'POST', path: DEFAULTS.apiEndpoint })
                .reply(
                  200,
                  [[{ Value: responseData }]]
                )
            })

            it('returns first value inside the nested array', async () => {
              assert.equal(
                await hexToCssFilterLibrary.queryDb(sql, options),
                responseData
              )
              mockAgent.assertNoPendingInterceptors()
            })
          })

          describe('when the response is a new-schema filter row', () => {
            const row = findRowByHex('#42dead')

            beforeEach(() => {
              mockAgent.get(DEFAULTS.apiUrl)
                .intercept({ method: 'POST', path: DEFAULTS.apiEndpoint })
                .reply(200, selectFilterResponse(row))
            })

            it('returns the stored filter chain verbatim', async () => {
              assert.equal(
                await hexToCssFilterLibrary.queryDb(
                  `SELECT filter FROM 'color' WHERE id = ${row.id}`, options
                ),
                row.filter
              )
              mockAgent.assertNoPendingInterceptors()
            })
          })

          describe('when the call\'s does not return a nested array with an object containing Value', () => {
            beforeEach(() => {
              mockAgent.get(DEFAULTS.apiUrl)
                .intercept({ method: 'POST', path: DEFAULTS.apiEndpoint })
                .reply(200, { data: responseData })
            })

            it('returns the original call\'s return value', async () => {
              assert.equal(
                (await hexToCssFilterLibrary.queryDb(sql, options)).data,
                responseData
              )
              mockAgent.assertNoPendingInterceptors()
            })
          })
        })
      })
    })
  })

  describe('fetchColorRecord()', () => {
    describe('parameters', () => {
      describe('hexColor', () => {
        describe('when null', () => {
          beforeEach(() => {
            hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey)
          })

          const hexColor = null

          it('should throw error', async () => {
            try {
              await hexToCssFilterLibrary.fetchColorRecord(hexColor)
            } catch (e) {
              expect(e).to.be.instanceOf(Error)
            }
          })
        })

        describe('when undefined', () => {
          beforeEach(() => {
            hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey)
          })

          const hexColor = undefined

          it('should throw error', async () => {
            try {
              await hexToCssFilterLibrary.fetchColorRecord(hexColor)
            } catch (e) {
              expect(e).to.be.instanceOf(Error)
            }
          })
        })

        describe('when defined', () => {
          describe('when the hex digit amount is not 3 or 6', () => {
            beforeEach(() => {
              hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey)
              sinon.stub(hexToCssFilterLibrary, 'queryDb').callsFake(
                async (sql, options) => fixtureQueryDb(sql, options)
              )
            })

            describe('with hash', () => {
              const hexColor = '#3333'

              it('should throw error', async () => {
                await assert.rejects(
                  hexToCssFilterLibrary.fetchColorRecord(hexColor),
                  /Hex color is not valid/
                )
              })
            })

            describe('without hash', () => {
              const hexColor = '3333'

              it('should throw error', async () => {
                await assert.rejects(
                  hexToCssFilterLibrary.fetchColorRecord(hexColor),
                  /Hex color is not valid/
                )
              })
            })
          })

          describe('when the color is not in the fixture database', () => {
            beforeEach(() => {
              hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey)
              sinon.stub(hexToCssFilterLibrary, 'queryDb').callsFake(
                async (sql, options) => fixtureQueryDb(sql, options)
              )
            })

            it('should throw a color not found error', async () => {
              await assert.rejects(
                hexToCssFilterLibrary.fetchColorRecord('#abcdef'),
                /Color not found in database/
              )
            })
          })

          describe('when queryDb() returns an API error', () => {
            beforeEach(() => {
              hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey)
              sinon.stub(hexToCssFilterLibrary, 'queryDb').resolves({ error: 'stubbedError' })
            })

            it('should throw error', async () => {
              await assert.rejects(
                hexToCssFilterLibrary.fetchColorRecord('#333'),
                /stubbedError/
              )
            })
          })

          describe('when queryDb() response is null', () => {
            beforeEach(() => {
              hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey)
              sinon.stub(hexToCssFilterLibrary, 'queryDb').resolves(null)
            })

            it('should throw a color not found error', async () => {
              await assert.rejects(
                hexToCssFilterLibrary.fetchColorRecord('#333'),
                /Color not found in database/
              )
            })
          })

          describe('when the stored chain is empty', () => {
            beforeEach(() => {
              hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey)
              sinon.stub(hexToCssFilterLibrary, 'queryDb').resolves([[
                { Name: 'id', Type: 'integer', Value: '0' },
                { Name: 'filter', Type: 'text', Value: '' },
                { Name: 'loss', Type: 'real', Value: '0' }
              ]])
            })

            it('should keep the empty chain as a string', async () => {
              assert.deepEqual(
                await hexToCssFilterLibrary.fetchColorRecord('#000000'),
                { id: 0, filter: '', loss: 0 }
              )
            })
          })

          describe('when hex digit amount is 3 or 6', () => {
            const normalizationCases = [
              { row: findRowByHex('#333333'), inputs: ['333', '#333', '333333', '#333333'] },
              { row: findRowByHex('#42dead'), inputs: ['42dead', '#42dead', '42DEAD', '#42DeAd'] },
              { row: findRowByHex('#000000'), inputs: ['000', '#000', '000000', '#000000'] },
              { row: findRowByHex('#ffffff'), inputs: ['fff', '#fff', 'ffffff', '#FFFFFF'] }
            ]

            normalizationCases.forEach(({ row, inputs }) => {
              describe(`when querying ${row.filter.slice(0, 11)}...`, () => {
                let queryDbStub

                beforeEach(() => {
                  hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey)
                  queryDbStub = sinon.stub(hexToCssFilterLibrary, 'queryDb').callsFake(
                    async (sql, options) => fixtureQueryDb(sql, options)
                  )
                })

                inputs.forEach((hexColor) => {
                  it(`normalizes '${hexColor}' to id ${row.id} and returns the record`, async () => {
                    const record = await hexToCssFilterLibrary.fetchColorRecord(hexColor)

                    assert.deepEqual(record, row)
                    assert.equal(
                      queryDbStub.lastCall.args[0],
                      `SELECT * FROM 'color' WHERE id = ${row.id}`
                    )
                  })
                })
              })
            })
          })
        })
      })
    })

    describe('options', () => {
      describe('raw', () => {
        const row = findRowByHex('#42dead')

        beforeEach(() => {
          hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey)
          sinon.stub(hexToCssFilterLibrary, 'queryDb').callsFake(
            async (sql, options) => fixtureQueryDb(sql, options)
          )
        })

        describe('when null', () => {
          const options = { raw: null }

          it('should not return the output from queryDb()', async () => {
            assert.notDeepEqual(
              await hexToCssFilterLibrary.fetchColorRecord('#42dead', options),
              selectAllResponse(row)
            )
          })
        })

        describe('when undefined', () => {
          const options = { raw: undefined }

          it('should not return the output from queryDb()', async () => {
            assert.notDeepEqual(
              await hexToCssFilterLibrary.fetchColorRecord('#42dead', options),
              selectAllResponse(row)
            )
          })
        })

        describe('when true', () => {
          const options = { raw: true }

          it('should return the output from queryDb()', async () => {
            assert.deepEqual(
              await hexToCssFilterLibrary.fetchColorRecord('#42dead', options),
              selectAllResponse(row)
            )
          })
        })
      })
    })
  })

  describe('fetchFilter()', () => {
    beforeEach(() => {
      hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey)
      sinon.stub(hexToCssFilterLibrary, 'queryDb').callsFake(
        async (sql, options) => fixtureQueryDb(sql, options)
      )
    })

    afterEach(() => {
      sinon.restore()
    })

    describe('parameters', () => {
      describe('hexColor', () => {
        describe('when null', () => {
          const hexColor = null

          it('should throw error', async () => {
            await assert.rejects(hexToCssFilterLibrary.fetchFilter(hexColor))
          })
        })

        describe('when undefined', () => {
          const hexColor = undefined

          it('should throw error', async () => {
            await assert.rejects(hexToCssFilterLibrary.fetchFilter(hexColor))
          })
        })

        describe('when the hex digit amount is not 3 or 6', () => {
          const hexColor = '#3333'

          it('should throw error', async () => {
            await assert.rejects(
              hexToCssFilterLibrary.fetchFilter(hexColor),
              /Hex color is not valid/
            )
          })
        })

        describe('when the color is not in the fixture database', () => {
          const hexColor = '#abcdef'

          it('should throw a color not found error', async () => {
            await assert.rejects(
              hexToCssFilterLibrary.fetchFilter(hexColor),
              /Color not found in database/
            )
          })
        })

        describe('when queryDb() returns an API error', () => {
          beforeEach(() => {
            hexToCssFilterLibrary.queryDb.resolves({ error: 'stubbedError' })
          })

          it('should throw error', async () => {
            await assert.rejects(
              hexToCssFilterLibrary.fetchFilter('#333'),
              /stubbedError/
            )
          })
        })

        describe('when queryDb() response is null', () => {
          beforeEach(() => {
            hexToCssFilterLibrary.queryDb.resolves(null)
          })

          it('should throw a color not found error', async () => {
            await assert.rejects(
              hexToCssFilterLibrary.fetchFilter('#333'),
              /Color not found in database/
            )
          })
        })

        describe('when the stored chain is empty', () => {
          beforeEach(() => {
            hexToCssFilterLibrary.queryDb.resolves('')
          })

          it('should return the empty chain verbatim', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter('#000000'),
              ''
            )
          })

          it('should only add the requested prefix', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter('#000000', { filterPrefix: true }),
              'filter:'
            )
          })
        })

        describe('when the filter chain contains a 0% value', () => {
          const row = findRowByHex('#333333')

          it('should still return the chain verbatim', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter('#333'),
              row.filter
            )
          })
        })
      })
    })

    describe('options', () => {
      const row = findRowByHex('#42dead')

      describe('filterPrefix', () => {
        describe('when null', () => {
          const options = { filterPrefix: null }

          it('should return the filter without prefix', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter('#42dead', options),
              row.filter
            )
          })
        })

        describe('when undefined', () => {
          const options = { filterPrefix: undefined }

          it('should return the filter without prefix', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter('#42dead', options),
              row.filter
            )
          })
        })

        describe('when true', () => {
          const options = { filterPrefix: true }

          it('should prefix filter with \'filter:\'', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter('#42dead', options),
              `filter: ${row.filter}`
            )
          })
        })
      })

      describe('preBlacken', () => {
        describe('when null', () => {
          const options = { preBlacken: null }

          it('should return the filter without the blacken step', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter('#42dead', options),
              row.filter
            )
          })
        })

        describe('when undefined', () => {
          const options = { preBlacken: undefined }

          it('should return the filter without the blacken step', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter('#42dead', options),
              row.filter
            )
          })
        })

        describe('when true', () => {
          const options = { preBlacken: true }

          it('should prefix filter with brightness(0) saturate(1)', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter('#42dead', options),
              `brightness(0) saturate(1) ${row.filter}`
            )
          })
        })

        describe('when true alongside filterPrefix', () => {
          const options = { filterPrefix: true, preBlacken: true }

          it('should compose both prefixes in documented order', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter('#42dead', options),
              `filter: brightness(0) saturate(1) ${row.filter}`
            )
          })
        })
      })

      describe('end-to-end over the mocked HTTP API', () => {
        beforeEach(() => {
          sinon.restore()
          hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey)
          mockAgent.get(DEFAULTS.apiUrl)
            .intercept({ method: 'POST', path: DEFAULTS.apiEndpoint })
            .reply(200, selectFilterResponse(row))
        })

        it('should request the filter column with getFirstValue and return it verbatim', async () => {
          assert.equal(
            await hexToCssFilterLibrary.fetchFilter('#42dead'),
            row.filter
          )
          mockAgent.assertNoPendingInterceptors()
        })
      })
    })
  })
})
