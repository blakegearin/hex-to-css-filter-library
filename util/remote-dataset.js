// Remote lookups via the Hugging Face Dataset Viewer API. The Parquet mirror
// is id-sorted, so the row offset is the color id; responses are validated by
// re-checking that id.

const DTYPE_TO_SQLITE_TYPE = {
  int64: 'integer',
  int32: 'integer',
  string: 'text',
  float64: 'real',
  float32: 'real'
}

export const buildRowsUrl = (remote, hexColorInt) => {
  const url = new URL(remote.rowsEndpoint)
  url.searchParams.set('dataset', remote.dataset)
  url.searchParams.set('config', remote.config)
  url.searchParams.set('split', remote.split)
  url.searchParams.set('offset', String(hexColorInt))
  url.searchParams.set('length', '1')
  return url.toString()
}

const fetchRow = async (remote, hexColorInt, fetchFunction) => {
  const url = buildRowsUrl(remote, hexColorInt)
  const response = await fetchFunction(url)
  if (!response.ok) {
    throw new Error(`Dataset server returned HTTP ${response.status} for ${url}`)
  }
  const payload = await response.json()
  if (!Array.isArray(payload.rows)) {
    throw new Error(`Unexpected dataset server response for ${url}`)
  }
  if (payload.rows.length === 0) return null
  const row = payload.rows[0].row
  if (Number(row.id) !== hexColorInt) {
    throw new Error(
      `Dataset server returned id ${row.id} when querying ${hexColorInt}; the row-order assumption is broken, refusing to return a wrong filter.`
    )
  }
  return { row, features: payload.features }
}

export const remoteLookupFilter = async (remote, hexColorInt, fetchFunction) => {
  const result = await fetchRow(remote, hexColorInt, fetchFunction)
  return result === null ? undefined : result.row.filter
}

export const remoteLookupColorRecord = async (remote, hexColorInt, fetchFunction) => {
  const result = await fetchRow(remote, hexColorInt, fetchFunction)
  if (result === null) return []
  const { row, features } = result
  const canonical = features.map((feature) => ({
    Name: feature.name,
    Type: DTYPE_TO_SQLITE_TYPE[feature.type.dtype] || feature.type.dtype,
    Value: row[feature.name] == null ? '' : String(row[feature.name])
  }))
  return [canonical]
}
