// Hand-built fixture for the rebuilt schema: color (id INTEGER PRIMARY KEY, filter TEXT, loss REAL)
// Rows copied from the final monolith; the suite never touches the 1.7 GB artifact.
const COLOR_ROWS = [
  {
    id: 0,
    filter: 'invert(47%) sepia(7%) saturate(2949%) hue-rotate(60deg) brightness(39%) contrast(177%)',
    loss: 0
  },
  {
    id: 3355443,
    filter: 'invert(0%) sepia(8%) saturate(23908%) hue-rotate(288deg) brightness(114%) contrast(60%)',
    loss: 0
  },
  {
    id: 4382381,
    filter: 'invert(95%) sepia(18%) saturate(20940%) hue-rotate(66deg) brightness(157%) contrast(74%)',
    loss: 0.8793432176
  },
  {
    id: 16777215,
    filter: 'invert(99%) sepia(4%) saturate(72%) hue-rotate(352deg) brightness(116%) contrast(100%)',
    loss: 0
  }
]

export const findRowByHex = (hexColor) => {
  const hexColorInt = parseInt(hexColor.replace('#', ''), 16)
  return COLOR_ROWS.find((row) => row.id === hexColorInt)
}

export const selectAllResponse = (row) => [[
  { Name: 'id', Type: 'integer', Value: String(row.id) },
  { Name: 'filter', Type: 'text', Value: row.filter },
  { Name: 'loss', Type: 'real', Value: String(row.loss) }
]]

export const selectFilterResponse = (row) => [[
  { Name: 'filter', Type: 'text', Value: row.filter }
]]

export const fixtureQueryDb = (sql, options = {}) => {
  const match = /WHERE id = (\d+)/i.exec(sql)
  const row = match ? COLOR_ROWS.find((r) => String(r.id) === match[1]) : null
  if (!row) return []
  return options.getFirstValue ? selectFilterResponse(row)[0][0].Value : selectAllResponse(row)
}
