import assert from 'assert'
import { expect } from 'chai'
import sinon from 'sinon'
import undici from 'undici'

import HexToCssFilterLibrary from '../index.js'
import DEFAULTS from '../util/defaults.js'

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
    beforeEach(() => {
      hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey)
    })

    describe('parameters', () => {
      describe('hexColor', () => {
        describe('when null', () => {
          const hexColor = null

          it('should throw error', async () => {
            try {
              hexToCssFilterLibrary.fetchColorRecord(hexColor)
            } catch (e) {
              expect(e).to.be.instanceOf(Error)
            }
          })
        })

        describe('when undefined', () => {
          const hexColor = undefined

          it('should throw error', async () => {
            try {
              hexToCssFilterLibrary.fetchColorRecord(hexColor)
            } catch (e) {
              expect(e).to.be.instanceOf(Error)
            }
          })
        })

        describe('when defined', () => {
          describe('when queryDb() response is null', () => {
            const hexColor = '#333'
            const stubbedResponse = null

            beforeEach(() => {
              sinon.stub(hexToCssFilterLibrary, 'queryDb').resolves(stubbedResponse)
            })

            it('should throw error', async () => {
              try {
                hexToCssFilterLibrary.fetchColorRecord(hexColor)
              } catch (e) {
                expect(e).to.be.instanceOf(Error)
              }
            })
          })

          describe('when queryDb() response is not null', () => {
            describe('when error attribute is present', () => {
              const hexColor = '#333'
              const stubbedResponse = { error: 'stubbedError' }

              beforeEach(() => {
                sinon.stub(hexToCssFilterLibrary, 'queryDb').resolves(stubbedResponse)
              })

              it('should throw error', async () => {
                try {
                  hexToCssFilterLibrary.fetchColorRecord(hexColor)
                } catch (e) {
                  expect(e).to.be.instanceOf(Error)
                }
              })
            })

            const stubbedResponse = [
              [
                { Name: 'id', Type: 4, Value: '4382381' },
                { Name: 'invert', Type: 4, Value: '66' },
                { Name: 'sepia', Type: 4, Value: '56' },
                { Name: 'saturate', Type: 4, Value: '416' },
                { Name: 'hue-rotate', Type: 4, Value: '110' },
                { Name: 'brightness', Type: 4, Value: '98' },
                { Name: 'contrast', Type: 4, Value: '100' },
                { Name: 'loss', Type: 5, Value: '0.2578769732' }
              ]
            ]

            describe('when hex digit amount is not 3 or 6', () => {
              describe('with hash', () => {
                const hexColor = '#3333'

                it('should throw error', async () => {
                  try {
                    hexToCssFilterLibrary.fetchColorRecord(hexColor)
                  } catch (e) {
                    expect(e).to.be.instanceOf(Error)
                  }
                })
              })

              describe('without hash', () => {
                const hexColor = '3333'

                it('should throw error', async () => {
                  try {
                    hexToCssFilterLibrary.fetchColorRecord(hexColor)
                  } catch (e) {
                    expect(e).to.be.instanceOf(Error)
                  }
                })
              })
            })

            describe('when hex digit amount is 3 or 6', () => {
              const supportedHexLengths = [3, 6]
              const supportedHexPrefixes = [
                { name: 'with hash', value: '#' },
                { name: 'without hash', value: '' }
              ]
              const expectedResponse = {
                id: 4382381,
                invert: 66,
                sepia: 56,
                saturate: 416,
                'hue-rotate': 110,
                brightness: 98,
                contrast: 100,
                loss: 0.2578769732
              }

              beforeEach(() => {
                sinon.stub(hexToCssFilterLibrary, 'queryDb').resolves(stubbedResponse)
              })

              supportedHexLengths.forEach((hexLength) => {
                describe(`when ${hexLength}-digit hex`, () => {
                  supportedHexPrefixes.forEach((hexPrefix) => {
                    describe(hexPrefix.name, () => {
                      const hexColor = `${hexPrefix.value}${'3'.repeat(hexLength)}`

                      it('should make a call to the database and return record as object', async () => {
                        assert.deepEqual(
                          await hexToCssFilterLibrary.fetchColorRecord(hexColor),
                          expectedResponse
                        )
                      })
                    })
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
        const hexColor = '#333'
        const stubbedResponse = [
          [
            { Name: 'id', Type: 4, Value: '4382381' },
            { Name: 'invert', Type: 4, Value: '66' },
            { Name: 'sepia', Type: 4, Value: '56' },
            { Name: 'saturate', Type: 4, Value: '416' },
            { Name: 'hue-rotate', Type: 4, Value: '110' },
            { Name: 'brightness', Type: 4, Value: '98' },
            { Name: 'contrast', Type: 4, Value: '100' },
            { Name: 'loss', Type: 5, Value: '0.2578769732' }
          ]
        ]

        beforeEach(() => {
          sinon.stub(hexToCssFilterLibrary, 'queryDb').resolves(stubbedResponse)
        })

        describe('when null', () => {
          const options = { raw: null }

          it('should not return the output from queryDb()', async () => {
            assert.notEqual(
              await hexToCssFilterLibrary.fetchColorRecord(hexColor, options),
              stubbedResponse
            )
          })
        })

        describe('when undefined', () => {
          const options = { raw: undefined }

          it('should not return the output from queryDb()', async () => {
            assert.notEqual(
              await hexToCssFilterLibrary.fetchColorRecord(hexColor, options),
              stubbedResponse
            )
          })
        })

        describe('when true', () => {
          const options = { raw: true }

          it('should return the output from queryDb()', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchColorRecord(hexColor, options),
              stubbedResponse
            )
          })
        })
      })
    })
  })

  describe('fetchFilter()', () => {
    beforeEach(() => {
      hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey)
    })

    describe('parameters', () => {
      describe('hexColor', () => {
        describe('when filter has no values that are 0', () => {
          const hexColor = '333'
          const stubbedResponse = {
            id: 4382381,
            invert: 66,
            sepia: 56,
            saturate: 416,
            'hue-rotate': 110,
            brightness: 98,
            contrast: 100,
            loss: 0.2578769732
          }
          const expectedResponse = 'invert(66%) sepia(56%) saturate(416%) hue-rotate(110deg) brightness(98%) contrast(100%)'

          beforeEach(() => {
            sinon.stub(hexToCssFilterLibrary, 'fetchColorRecord').resolves(stubbedResponse)
          })

          it('should exclude value from filter', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter(hexColor),
              expectedResponse
            )
          })
        })

        describe('when filter has a value that is 0', () => {
          const hexColor = '333'
          const stubbedResponse = {
            id: 4382381,
            invert: 66,
            sepia: 56,
            saturate: 416,
            'hue-rotate': 110,
            brightness: 0,
            contrast: 100,
            loss: 0.2578769732
          }
          const expectedResponse = 'invert(66%) sepia(56%) saturate(416%) hue-rotate(110deg) contrast(100%)'

          beforeEach(() => {
            sinon.stub(hexToCssFilterLibrary, 'fetchColorRecord').resolves(stubbedResponse)
          })

          it('should exclude value from filter', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter(hexColor),
              expectedResponse
            )
          })
        })
      })
    })

    describe('options', () => {
      const hexColor = '#333333'
      const stubbedResponse = {
        id: 4382381,
        invert: 66,
        sepia: 56,
        saturate: 416,
        'hue-rotate': 110,
        brightness: 98,
        contrast: 100,
        loss: 0.2578769732
      }

      beforeEach(() => {
        sinon.stub(hexToCssFilterLibrary, 'fetchColorRecord').resolves(stubbedResponse)
      })

      describe('filterPrefix', () => {
        const expectedResponse = 'invert(66%) sepia(56%) saturate(416%) hue-rotate(110deg) brightness(98%) contrast(100%)'

        describe('when null', () => {
          const options = {
            filterPrefix: null
          }

          it('should return the filter without prefix', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter(hexColor, options),
              expectedResponse
            )
          })
        })

        describe('when undefined', () => {
          const options = {
            filterPrefix: undefined
          }

          it('should return the filter without prefix', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter(hexColor, options),
              expectedResponse
            )
          })
        })

        describe('when true', () => {
          const options = {
            filterPrefix: true
          }
          const expectedResponse = 'filter: invert(66%) sepia(56%) saturate(416%) hue-rotate(110deg) brightness(98%) contrast(100%)'

          it('should prefix filter with \'filter:\'', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter(hexColor, options),
              expectedResponse
            )
          })
        })
      })

      describe('preBlacken', () => {
        const hexColor = '#333333'
        const expectedResponse = 'invert(66%) sepia(56%) saturate(416%) hue-rotate(110deg) brightness(98%) contrast(100%)'

        describe('when null', () => {
          const options = {
            preBlacken: null
          }

          it('should return the filter without prefix', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter(hexColor, options),
              expectedResponse
            )
          })
        })

        describe('when undefined', () => {
          const options = {
            preBlacken: undefined
          }

          it('should return the filter without prefix', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter(hexColor, options),
              expectedResponse
            )
          })
        })

        describe('when true', () => {
          const options = {
            preBlacken: true
          }
          const expectedResponse = 'brightness(0) saturate(1) invert(66%) sepia(56%) saturate(416%) hue-rotate(110deg) brightness(98%) contrast(100%)'

          it('should prefix filter with brightness(0) saturate(1)', async () => {
            assert.equal(
              await hexToCssFilterLibrary.fetchFilter(hexColor, options),
              expectedResponse
            )
          })
        })
      })
    })
  })
})
