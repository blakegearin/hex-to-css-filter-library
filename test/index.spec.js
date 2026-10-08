import assert from 'assert'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import sinon from 'sinon'
import undici from 'undici'

import HexToCssFilterLibrary, { resolveSource, validateSource } from '../index.js'
import DEFAULTS from '../util/defaults.js'
import {
  buildFixtureRelease,
  findRowByHex,
  rowsApiResponse
} from './fixtures/new-schema-db.js'

const mockAgent = new undici.MockAgent()
mockAgent.disableNetConnect()

describe('HexToCssFilterLibrary', () => {
  const testValue = 'testValue'

  let tmpDir
  let fixture
  before(() => {
    undici.setGlobalDispatcher(mockAgent)
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'htcf-lib-'))
    fixture = buildFixtureRelease(tmpDir)
  })
  after(() => fs.rmSync(tmpDir, { recursive: true, force: true }))

  // Local mode backed by the already-built fixture file: correct dbSize makes
  // the cache valid, so these instances never touch the mock network.
  const localLibrary = (extraOptions = {}) => new HexToCssFilterLibrary({
    dbPath: path.join(tmpDir, fixture.release.dbFile),
    datasetRelease: fixture.release,
    ...extraOptions
  })

  describe('constructor()', () => {
    describe('v2 compatibility', () => {
      describe('when an API key string is passed first', () => {
        it('should accept and ignore it and read options from the second argument', () => {
          const library = new HexToCssFilterLibrary('oldApiKey', { dbPath: testValue })
          assert.equal(library.dbPath, testValue)
          assert.equal(library.source, 'local')
        })
      })

      describe('when null is passed first', () => {
        it('should read options from the second argument', () => {
          const library = new HexToCssFilterLibrary(null, { dbPath: testValue })
          assert.equal(library.dbPath, testValue)
        })
      })
    })

    describe('options', () => {
      const optionParameters = ['dbPath', 'cacheDir', 'datasetRelease', 'remote', 'fetchFunction']
      optionParameters.forEach((parameterName) => {
        describe(parameterName, () => {
          describe('when null', () => {
            const options = {}
            options[parameterName] = null

            it('should be set to default value', () => {
              const library = new HexToCssFilterLibrary(options)
              assert.equal(library[parameterName], DEFAULTS[parameterName])
            })
          })

          describe('when undefined', () => {
            const options = {}
            options[parameterName] = undefined

            it('should be set to default value', () => {
              const library = new HexToCssFilterLibrary(options)
              assert.equal(library[parameterName], DEFAULTS[parameterName])
            })
          })

          describe('when defined', () => {
            const options = {}
            options[parameterName] = testValue

            it(`should be set to options.${parameterName}`, () => {
              const library = new HexToCssFilterLibrary(options)
              assert.equal(library[parameterName], testValue)
            })
          })
        })
      })
    })
  })

  describe('resolveSource()', () => {
    describe('when a source is requested', () => {
      it('should return it unchanged', () => {
        assert.equal(resolveSource('remote', true), 'remote')
      })
    })

    describe('when no source is requested on Node', () => {
      it('should default to local', () => {
        assert.equal(resolveSource(undefined, true), 'local')
      })
    })

    describe('when no source is requested off Node', () => {
      it('should default to remote', () => {
        assert.equal(resolveSource(undefined, false), 'remote')
      })
    })
  })

  describe('validateSource()', () => {
    it('should return valid sources', () => {
      assert.equal(validateSource('local', true), 'local')
      assert.equal(validateSource('remote', false), 'remote')
    })

    it('should throw on an unknown source', () => {
      assert.throws(() => validateSource('carrier-pigeon', true), /Unknown source/)
    })

    it('should throw when local is requested off Node', () => {
      assert.throws(() => validateSource('local', false), /needs Node\.js/)
    })
  })

  describe('queryDb()', () => {
    describe('when the local database is available', () => {
      let library

      beforeEach(() => {
        library = localLibrary()
      })

      afterEach(() => library.close())

      it('should throw when sql is null', async () => {
        await assert.rejects(library.queryDb(null), /Required parameter sql is not present/)
      })

      it('should throw when sql is undefined', async () => {
        await assert.rejects(library.queryDb(undefined), /Required parameter sql is not present/)
      })

      it('should return canonical rows', async () => {
        const response = await library.queryDb('SELECT COUNT() FROM color')
        assert.deepEqual(response, [
          [{ Name: 'COUNT()', Type: null, Value: '4' }]
        ])
      })

      it('should return the first value with getFirstValue', async () => {
        const response = await library.queryDb(
          "SELECT filter FROM 'color' WHERE id = 4382381",
          { getFirstValue: true }
        )
        assert.equal(response, findRowByHex('#42dead').filter)
      })

      it('should return the original response when getFirstValue is falsy', async () => {
        const options = { getFirstValue: null }
        const response = await library.queryDb(
          "SELECT filter FROM 'color' WHERE id = 4382381", options
        )
        assert.deepEqual(response, [[
          { Name: 'filter', Type: 'text', Value: findRowByHex('#42dead').filter }
        ]])
      })

      it('should return the untouched response when there are no rows', async () => {
        const response = await library.queryDb(
          "SELECT filter FROM 'color' WHERE id = 99999999", { getFirstValue: true }
        )
        assert.deepEqual(response, [])
      })
    })

    describe('when source is remote', () => {
      it('should throw an error that names the supported lookups', async () => {
        const library = new HexToCssFilterLibrary({ source: 'remote' })
        await assert.rejects(
          library.queryDb('SELECT COUNT() FROM color'),
          /queryDb\(\) runs arbitrary SQL against the local dataset/
        )
      })
    })
  })

  describe('remote mode over the mocked dataset server', () => {
    const row = findRowByHex('#42dead')
    const rowsUrl = `/rows?dataset=${encodeURIComponent(DEFAULTS.remote.dataset)}&config=default&split=train&offset=4382381&length=1`
    let library

    beforeEach(() => {
      library = new HexToCssFilterLibrary({ source: 'remote' })
      mockAgent
        .get('https://datasets-server.huggingface.co')
        .intercept({ method: 'GET', path: rowsUrl })
        .reply(200, rowsApiResponse(row))
    })

    it('fetchFilter() should return the chain verbatim without any local files', async () => {
      assert.equal(await library.fetchFilter('#42dead'), row.filter)
      mockAgent.assertNoPendingInterceptors()
    })

    it('fetchColorRecord() should map the row to { id, filter, loss }', async () => {
      assert.deepEqual(await library.fetchColorRecord('#42dead'), row)
      mockAgent.assertNoPendingInterceptors()
    })
  })

  describe('fetchFilter()', () => {
    let library

    afterEach(() => {
      sinon.restore()
    })

    describe('parameters', () => {
      describe('hexColor', () => {
        describe('when null', () => {
          it('should throw error', async () => {
            library = localLibrary()
            await assert.rejects(library.fetchFilter(null))
          })
        })

        describe('when undefined', () => {
          it('should throw error', async () => {
            library = localLibrary()
            await assert.rejects(library.fetchFilter(undefined))
          })
        })

        describe('when the hex digit amount is not 3 or 6', () => {
          it('should throw error', async () => {
            library = localLibrary()
            await assert.rejects(
              library.fetchFilter('#3333'),
              /Hex color is not valid/
            )
          })
        })

        describe('when the color is not in the database', () => {
          it('should throw a color not found error', async () => {
            library = localLibrary()
            await assert.rejects(
              library.fetchFilter('#abcdef'),
              /Color not found in database/
            )
          })
        })

        describe('when the lookup rejects', () => {
          it('should propagate the error', async () => {
            library = localLibrary()
            sinon.stub(library, 'lookupFilter').rejects(new Error('stubbedError'))
            await assert.rejects(library.fetchFilter('#333'), /stubbedError/)
          })
        })

        describe('when the stored chain is empty', () => {
          it('should return the empty chain verbatim', async () => {
            library = localLibrary()
            sinon.stub(library, 'lookupFilter').resolves('')
            assert.equal(await library.fetchFilter('#000000'), '')
          })

          it('should only add the requested prefix', async () => {
            library = localLibrary()
            sinon.stub(library, 'lookupFilter').resolves('')
            assert.equal(
              await library.fetchFilter('#000000', { filterPrefix: true }),
              'filter:'
            )
          })
        })

        describe('when the filter chain contains a 0% value', () => {
          it('should still return the chain verbatim', async () => {
            library = localLibrary()
            assert.equal(
              await library.fetchFilter('#333'),
              findRowByHex('#333333').filter
            )
          })
        })
      })
    })

    describe('options', () => {
      const row = findRowByHex('#42dead')

      beforeEach(() => {
        library = localLibrary()
        sinon.stub(library, 'lookupFilter').resolves(row.filter)
      })

      describe('filterPrefix', () => {
        describe('when null', () => {
          const options = { filterPrefix: null }

          it('should return the filter without prefix', async () => {
            assert.equal(await library.fetchFilter('#42dead', options), row.filter)
          })
        })

        describe('when undefined', () => {
          const options = { filterPrefix: undefined }

          it('should return the filter without prefix', async () => {
            assert.equal(await library.fetchFilter('#42dead', options), row.filter)
          })
        })

        describe('when true', () => {
          const options = { filterPrefix: true }

          it('should prefix filter with \'filter:\'', async () => {
            assert.equal(
              await library.fetchFilter('#42dead', options),
              `filter: ${row.filter}`
            )
          })
        })
      })

      describe('preBlacken', () => {
        describe('when null', () => {
          const options = { preBlacken: null }

          it('should return the filter without the blacken step', async () => {
            assert.equal(await library.fetchFilter('#42dead', options), row.filter)
          })
        })

        describe('when undefined', () => {
          const options = { preBlacken: undefined }

          it('should return the filter without the blacken step', async () => {
            assert.equal(await library.fetchFilter('#42dead', options), row.filter)
          })
        })

        describe('when true', () => {
          const options = { preBlacken: true }

          it('should prefix filter with brightness(0) saturate(1)', async () => {
            assert.equal(
              await library.fetchFilter('#42dead', options),
              `brightness(0) saturate(1) ${row.filter}`
            )
          })
        })

        describe('when true alongside filterPrefix', () => {
          const options = { filterPrefix: true, preBlacken: true }

          it('should compose both prefixes in documented order', async () => {
            assert.equal(
              await library.fetchFilter('#42dead', options),
              `filter: brightness(0) saturate(1) ${row.filter}`
            )
          })
        })
      })
    })

    describe('hex input normalization', () => {
      const normalizationCases = [
        { row: findRowByHex('#333333'), inputs: ['333', '#333', '333333', '#333333'] },
        { row: findRowByHex('#42dead'), inputs: ['42dead', '#42dead', '42DEAD', '#42DeAd'] },
        { row: findRowByHex('#000000'), inputs: ['000', '#000', '000000', '#000000'] },
        { row: findRowByHex('#ffffff'), inputs: ['fff', '#fff', 'ffffff', '#FFFFFF'] }
      ]

      normalizationCases.forEach(({ row, inputs }) => {
        describe(`when querying ${row.filter.slice(0, 11)}...`, () => {
          beforeEach(() => {
            library = localLibrary()
          })

          inputs.forEach((hexColor) => {
            it(`normalizes '${hexColor}' to id ${row.id}`, async () => {
              assert.equal(await library.fetchFilter(hexColor), row.filter)
            })
          })
        })
      })
    })
  })

  describe('fetchColorRecord()', () => {
    let library

    afterEach(() => {
      sinon.restore()
    })

    describe('parameters', () => {
      describe('hexColor', () => {
        describe('when null', () => {
          it('should throw error', async () => {
            library = localLibrary()
            await assert.rejects(library.fetchColorRecord(null))
          })
        })

        describe('when undefined', () => {
          it('should throw error', async () => {
            library = localLibrary()
            await assert.rejects(library.fetchColorRecord(undefined))
          })
        })

        describe('when the hex digit amount is not 3 or 6', () => {
          it('should throw error', async () => {
            library = localLibrary()
            await assert.rejects(
              library.fetchColorRecord('#3333'),
              /Hex color is not valid/
            )
          })
        })

        describe('when the color is not in the fixture database', () => {
          it('should throw a color not found error', async () => {
            library = localLibrary()
            await assert.rejects(
              library.fetchColorRecord('#abcdef'),
              /Color not found in database/
            )
          })
        })

        describe('when the lookup rejects', () => {
          it('should propagate the error', async () => {
            library = localLibrary()
            sinon.stub(library, 'lookupColorRecord').rejects(new Error('stubbedError'))
            await assert.rejects(library.fetchColorRecord('#333'), /stubbedError/)
          })
        })

        describe('when the stored chain is empty', () => {
          it('should keep the empty chain as a string', async () => {
            library = localLibrary()
            sinon.stub(library, 'lookupColorRecord').resolves([[
              { Name: 'id', Type: 'integer', Value: '0' },
              { Name: 'filter', Type: 'text', Value: '' },
              { Name: 'loss', Type: 'real', Value: '0' }
            ]])
            assert.deepEqual(
              await library.fetchColorRecord('#000000'),
              { id: 0, filter: '', loss: 0 }
            )
          })
        })
      })
    })

    describe('hex input normalization', () => {
      const normalizationCases = [
        { row: findRowByHex('#333333'), inputs: ['333', '#333', '333333', '#333333'] },
        { row: findRowByHex('#42dead'), inputs: ['42dead', '#42dead', '42DEAD', '#42DeAd'] }
      ]

      normalizationCases.forEach(({ row, inputs }) => {
        inputs.forEach((hexColor) => {
          it(`normalizes '${hexColor}' to id ${row.id} and returns the record`, async () => {
            library = localLibrary()
            assert.deepEqual(await library.fetchColorRecord(hexColor), row)
          })
        })
      })
    })

    describe('options', () => {
      describe('raw', () => {
        const row = findRowByHex('#42dead')

        beforeEach(() => {
          library = localLibrary()
        })

        describe('when null', () => {
          const options = { raw: null }

          it('should not return the canonical rows', async () => {
            assert.notDeepEqual(
              await library.fetchColorRecord('#42dead', options),
              [[
                { Name: 'id', Type: 'integer', Value: String(row.id) },
                { Name: 'filter', Type: 'text', Value: row.filter },
                { Name: 'loss', Type: 'real', Value: String(row.loss) }
              ]]
            )
          })
        })

        describe('when undefined', () => {
          const options = { raw: undefined }

          it('should not return the canonical rows', async () => {
            assert.notDeepEqual(
              await library.fetchColorRecord('#42dead', options),
              [[
                { Name: 'id', Type: 'integer', Value: String(row.id) },
                { Name: 'filter', Type: 'text', Value: row.filter },
                { Name: 'loss', Type: 'real', Value: String(row.loss) }
              ]]
            )
          })
        })

        describe('when true', () => {
          const options = { raw: true }

          it('should return the canonical rows', async () => {
            assert.deepEqual(
              await library.fetchColorRecord('#42dead', options),
              [[
                { Name: 'id', Type: 'integer', Value: String(row.id) },
                { Name: 'filter', Type: 'text', Value: row.filter },
                { Name: 'loss', Type: 'real', Value: String(row.loss) }
              ]]
            )
          })
        })
      })
    })
  })

  describe('close()', () => {
    it('should be a no-op before the database is opened', () => {
      const library = localLibrary()
      library.close()
      assert.equal(library.localDataset, null)
    })

    it('should release the local dataset after use', async () => {
      const library = localLibrary()
      await library.fetchFilter('#42dead')
      library.close()
      assert.equal(library.localDataset, null)
    })
  })
})
