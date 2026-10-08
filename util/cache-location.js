// Per-user cache location, versioned by dataset snapshot (never library
// version), so it is stable across upgrades.

export const APP_DIR_NAME = 'hex-to-css-filter-library'

const platformCacheRoot = (platform, env, homedir) => {
  if (platform === 'darwin') {
    return `${homedir}/Library/Caches`
  }
  if (platform === 'win32') {
    return env.LOCALAPPDATA || `${homedir}/AppData/Local`
  }
  return env.XDG_CACHE_HOME || `${homedir}/.cache`
}

export const defaultCacheDir = ({ platform, env, homedir }) => {
  const root = platformCacheRoot(platform, env, homedir)
  return `${root}/${APP_DIR_NAME}/datasets`
}

export const cachedDbPath = (cacheDir, release) =>
  `${cacheDir}/${release.snapshot}/${release.dbFile}`
