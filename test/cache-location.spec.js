import assert from 'assert'

import { defaultCacheDir, cachedDbPath, APP_DIR_NAME } from '../util/cache-location.js'

describe('cache-location', () => {
  describe('defaultCacheDir()', () => {
    it('uses Library/Caches on macOS', () => {
      assert.equal(
        defaultCacheDir({ platform: 'darwin', env: {}, homedir: '/Users/blake' }),
        `/Users/blake/Library/Caches/${APP_DIR_NAME}/datasets`
      )
    })

    it('prefers LOCALAPPDATA on Windows', () => {
      assert.equal(
        defaultCacheDir({ platform: 'win32', env: { LOCALAPPDATA: 'C:\\Users\\blake\\AppData\\Local' }, homedir: 'C:\\Users\\blake' }),
        `C:\\Users\\blake\\AppData\\Local/${APP_DIR_NAME}/datasets`
      )
    })

    it('falls back to AppData on Windows without LOCALAPPDATA', () => {
      assert.equal(
        defaultCacheDir({ platform: 'win32', env: {}, homedir: 'C:\\Users\\blake' }),
        `C:\\Users\\blake/AppData/Local/${APP_DIR_NAME}/datasets`
      )
    })

    it('prefers XDG_CACHE_HOME on Linux', () => {
      assert.equal(
        defaultCacheDir({ platform: 'linux', env: { XDG_CACHE_HOME: '/ramdisk/cache' }, homedir: '/home/blake' }),
        `/ramdisk/cache/${APP_DIR_NAME}/datasets`
      )
    })

    it('falls back to ~/.cache on Linux', () => {
      assert.equal(
        defaultCacheDir({ platform: 'linux', env: {}, homedir: '/home/blake' }),
        `/home/blake/.cache/${APP_DIR_NAME}/datasets`
      )
    })

    it('falls back to ~/.cache on anything else', () => {
      assert.equal(
        defaultCacheDir({ platform: 'unknown99', env: {}, homedir: '/nobody' }),
        `/nobody/.cache/${APP_DIR_NAME}/datasets`
      )
    })
  })

  describe('cachedDbPath()', () => {
    it('is keyed by dataset snapshot, so library upgrades reuse it', () => {
      const release = { snapshot: '2026.10.07', dbFile: 'covering-dataset.sqlite3' }
      assert.equal(
        cachedDbPath('/user/cache/datasets', release),
        '/user/cache/datasets/2026.10.07/covering-dataset.sqlite3'
      )
    })

    it('separates datasets from different snapshots', () => {
      const a = cachedDbPath('/c', { snapshot: '2026.10.07', dbFile: 'd.sqlite3' })
      const b = cachedDbPath('/c', { snapshot: '2027.01.01', dbFile: 'd.sqlite3' })
      assert.notEqual(a, b)
    })
  })
})
