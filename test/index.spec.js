import assert from 'assert'
import { expect } from 'chai'
import nock from 'nock'

import HexToCssFilterLibrary from '../index.js'
import DEFAULTS from '../util/defaults.js'

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
          'dbName'
        ]
        optionParameters.forEach((parameterName) => {
          describe(parameterName, () => {
            describe('when null', () => {
              it('should be set to default value', () => {
                const options = {}
                options[parameterName] = null
                const hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey, options)
                assert.equal(hexToCssFilterLibrary[parameterName], DEFAULTS[parameterName])
              })
            })

            describe('when undefined', () => {
              it('should be set to default value', () => {
                const options = {}
                options[parameterName] = undefined
                const hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey, options)
                assert.equal(hexToCssFilterLibrary[parameterName], DEFAULTS[parameterName])
              })
            })

            describe('when defined', () => {
              it(`should be set to options.${parameterName}`, () => {
                const options = {}
                options[parameterName] = testValue
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
          const dbCall = nock(DEFAULTS.apiUrl)
            .post(DEFAULTS.apiEndpoint)
            .reply(200, { data: responseData })

          it('should make a call to the defaults apiUrl and apiEndpoint', () => {
            return hexToCssFilterLibrary.queryDb(sql).then(response => {
              assert.equal(response.data, responseData)
              dbCall.done()
            })
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
          const dbCall = nock(DEFAULTS.apiUrl)
            .post(DEFAULTS.apiEndpoint)
            .reply(200, { data: responseData })

          it('should be set to default value', () => {
            return hexToCssFilterLibrary.queryDb(sql, options).then(response => {
              assert.equal(response.data, responseData)
              dbCall.done()
            })
          })
        })

        describe('when undefined', () => {
          const dbCall = nock(DEFAULTS.apiUrl)
            .post(DEFAULTS.apiEndpoint)
            .reply(200, { data: responseData })

          it('should be set to default value', () => {
            const options = {
              getFirstValue: undefined
            }
            return hexToCssFilterLibrary.queryDb(sql, options).then(response => {
              assert.equal(response.data, responseData)
              dbCall.done()
            })
          })
        })

        describe('when true', () => {
          describe('when the call\'s returns a nested array with an object containing Value', () => {
            const dbCall = nock(DEFAULTS.apiUrl)
              .post(DEFAULTS.apiEndpoint)
              .reply(
                200,
                [[{ Value: responseData }]]
              )

            it('returns first value inside the nested array', () => {
              const options = {
                getFirstValue: true
              }
              return hexToCssFilterLibrary.queryDb(sql, options).then(response => {
                assert.equal(response, responseData)
                dbCall.done()
              })
            })
          })

          describe('when the call\'s does not return a nested array with an object containing Value', () => {
            const dbCall = nock(DEFAULTS.apiUrl)
              .post(DEFAULTS.apiEndpoint)
              .reply(200, { data: responseData })

            it('returns the original call\'s return value', () => {
              const options = {
                getFirstValue: true
              }
              return hexToCssFilterLibrary.queryDb(sql, options).then(response => {
                assert.equal(response.data, responseData)
                dbCall.done()
              })
            })
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
        describe('when null', () => {
          const hexColor = null

          it('should throw error', async () => {
            try {
              hexToCssFilterLibrary.fetchFilter(hexColor)
            } catch (e) {
              expect(e).to.be.instanceOf(Error)
            }
          })
        })

        describe('when undefined', () => {
          const hexColor = undefined

          it('should throw error', async () => {
            try {
              hexToCssFilterLibrary.fetchFilter(hexColor)
            } catch (e) {
              expect(e).to.be.instanceOf(Error)
            }
          })
        })

        describe('when defined', () => {
          describe('when queryDb() response is null', () => {
            const hexColor = '#333'

            beforeEach(() => {
              nock(DEFAULTS.apiUrl)
                .post(DEFAULTS.apiEndpoint)
                .reply(200, null)
            })

            it('should throw error', async () => {
              try {
                hexToCssFilterLibrary.fetchFilter(hexColor)
              } catch (e) {
                expect(e).to.be.instanceOf(Error)
              }
            })
          })

          describe('when queryDb() response is not null', () => {
            describe('when hex digit amount is not 3 or 6', () => {
              describe('with hash', () => {
                const hexColor = '#3333'

                it('should throw error', async () => {
                  try {
                    hexToCssFilterLibrary.fetchFilter(hexColor)
                  } catch (e) {
                    expect(e).to.be.instanceOf(Error)
                  }
                })
              })

              describe('without hash', () => {
                const hexColor = '3333'

                it('should throw error', async () => {
                  try {
                    hexToCssFilterLibrary.fetchFilter(hexColor)
                  } catch (e) {
                    expect(e).to.be.instanceOf(Error)
                  }
                })
              })
            })

            describe('when hex digit amount is 3 or 6', () => {
              describe('when filter has no values that are 0', () => {
                let dbCall
                const response = [
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
                const filter = 'invert(66%) sepia(56%) saturate(416%) hue-rotate(110deg) brightness(98%) contrast(100%)'

                beforeEach(() => {
                  dbCall = nock(DEFAULTS.apiUrl)
                    .post(DEFAULTS.apiEndpoint)
                    .reply(200, response)
                })

                describe('when 3-digit hex', () => {
                  describe('with hash', () => {
                    const hexColor = '#333'

                    it('should make a call to the database and return filter', () => {
                      return hexToCssFilterLibrary.fetchFilter(hexColor).then(response => {
                        assert.equal(response, filter)
                        dbCall.done()
                      })
                    })
                  })

                  describe('without hash', () => {
                    const hexColor = '333'

                    it('should make a call to the database and return filter', () => {
                      return hexToCssFilterLibrary.fetchFilter(hexColor).then(response => {
                        assert.equal(response, filter)
                        dbCall.done()
                      })
                    })
                  })
                })

                describe('when 6-digit hex', () => {
                  describe('with hash', () => {
                    const hexColor = '#333333'

                    it('should make a call to the database and return filter', () => {
                      return hexToCssFilterLibrary.fetchFilter(hexColor).then(response => {
                        assert.equal(response, filter)
                        dbCall.done()
                      })
                    })
                  })

                  describe('without hash', () => {
                    const hexColor = '333333'

                    it('should make a call to the database and return filter', () => {
                      return hexToCssFilterLibrary.fetchFilter(hexColor).then(response => {
                        assert.equal(response, filter)
                        dbCall.done()
                      })
                    })
                  })
                })
              })

              describe('when filter has a value that is 0', () => {
                let dbCall
                const hexColor = '333'
                const response = [
                  [
                    { Name: 'id', Type: 4, Value: '4382381' },
                    { Name: 'invert', Type: 4, Value: '66' },
                    { Name: 'sepia', Type: 4, Value: '56' },
                    { Name: 'saturate', Type: 4, Value: '416' },
                    { Name: 'hue-rotate', Type: 4, Value: '110' },
                    { Name: 'brightness', Type: 4, Value: '0' },
                    { Name: 'contrast', Type: 4, Value: '100' },
                    { Name: 'loss', Type: 5, Value: '0.2578769732' }
                  ]
                ]
                const filter = 'invert(66%) sepia(56%) saturate(416%) hue-rotate(110deg) contrast(100%)'

                beforeEach(() => {
                  dbCall = nock(DEFAULTS.apiUrl)
                    .post(DEFAULTS.apiEndpoint)
                    .reply(200, response)
                })

                it('should exclude value from filter', () => {
                  return hexToCssFilterLibrary.fetchFilter(hexColor).then(response => {
                    assert.equal(response, filter)
                    dbCall.done()
                  })
                })
              })
            })
          })
        })
      })
    })

    describe('options', () => {
      describe('filterPrefix', () => {
        let dbCall
        const hexColor = '#333333'
        const response = [
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
        const filter = 'invert(66%) sepia(56%) saturate(416%) hue-rotate(110deg) brightness(98%) contrast(100%)'

        beforeEach(() => {
          dbCall = nock(DEFAULTS.apiUrl)
            .post(DEFAULTS.apiEndpoint)
            .reply(200, response)
        })

        describe('when null', () => {
          it('should return the filter without prefix', () => {
            const options = {
              filterPrefix: null
            }
            return hexToCssFilterLibrary.fetchFilter(hexColor, options).then(response => {
              assert.equal(response, filter)
              dbCall.done()
            })
          })
        })

        describe('when undefined', () => {
          it('should return the filter without prefix', () => {
            const options = {
              filterPrefix: undefined
            }
            return hexToCssFilterLibrary.fetchFilter(hexColor, options).then(response => {
              assert.equal(response, filter)
              dbCall.done()
            })
          })
        })

        describe('when true', () => {
          const filter = 'filter: invert(66%) sepia(56%) saturate(416%) hue-rotate(110deg) brightness(98%) contrast(100%)'

          it('should prefix filter with \'filter:\'', () => {
            const options = {
              filterPrefix: true
            }
            return hexToCssFilterLibrary.fetchFilter(hexColor, options).then(response => {
              assert.equal(response, filter)
              dbCall.done()
            })
          })
        })
      })

      describe('preBlacken', () => {
        let dbCall
        const hexColor = '#333333'
        const response = [
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
        const filter = 'invert(66%) sepia(56%) saturate(416%) hue-rotate(110deg) brightness(98%) contrast(100%)'

        beforeEach(() => {
          dbCall = nock(DEFAULTS.apiUrl)
            .post(DEFAULTS.apiEndpoint)
            .reply(200, response)
        })

        describe('when null', () => {
          it('should return the filter without prefix', () => {
            const options = {
              preBlacken: null
            }
            return hexToCssFilterLibrary.fetchFilter(hexColor, options).then(response => {
              assert.equal(response, filter)
              dbCall.done()
            })
          })
        })

        describe('when undefined', () => {
          it('should return the filter without prefix', () => {
            const options = {
              preBlacken: undefined
            }
            return hexToCssFilterLibrary.fetchFilter(hexColor, options).then(response => {
              assert.equal(response, filter)
              dbCall.done()
            })
          })
        })

        describe('when true', () => {
          const filter = 'brightness(0) saturate(1) invert(66%) sepia(56%) saturate(416%) hue-rotate(110deg) brightness(98%) contrast(100%)'

          it('should prefix filter with brightness(0) saturate(1)', () => {
            const options = {
              preBlacken: true
            }
            return hexToCssFilterLibrary.fetchFilter(hexColor, options).then(response => {
              assert.equal(response, filter)
              dbCall.done()
            })
          })
        })
      })
    })
  })
})
