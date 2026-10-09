[![npm version](https://badge.fury.io/js/hex-to-css-filter-library.svg)](http://badge.fury.io/js/hex-to-css-filter-library)
![Tests](https://img.shields.io/badge/tests-mocha-8d6748)
![Statements](https://img.shields.io/badge/statements-100%25-brightgreen.svg?style=flat)
![Branches](https://img.shields.io/badge/branches-100%25-brightgreen.svg?style=flat)
![Functions](https://img.shields.io/badge/functions-100%25-brightgreen.svg?style=flat)
![Lines](https://img.shields.io/badge/lines-100%25-brightgreen.svg?style=flat)
[![Javascript Style Guide](https://img.shields.io/badge/code_style-standard-f3df49)](https://standardjs.com)
[![MIT License](https://img.shields.io/badge/license-MIT%20License-blue)](LICENSE)

# hex-to-css-filter-library

A JavaScript library backed by a covering dataset of CSS filters for sRGB:
for **every one of the 16,777,216 hex colors**, the dataset stores a
six-function filter chain that — applied to black — renders the target color
with a *rendered loss* under 1%.

Rendered loss is computed from the stored chain itself: black is rendered
through `invert() sepia() saturate() hue-rotate() brightness() contrast()` at
floating-point precision, and the absolute per-channel deltas to the target —
red, green, blue (0–255) plus hue, saturation, lightness (0–100) — are summed;
"under 1%" means that sum is under 1. The metric definition, the statistics,
and the dataset schema are documented in
**[docs/dataset.md](docs/dataset.md)**.

**Try it live:** the [demo page](https://blakegearin.github.io/hex-to-css-filter-library/)
turns any hex color into the stored filter chain in the browser.

## Usage

1. Install the dependency

   - NPM: `npm install hex-to-css-filter-library`
   - Yarn: `yarn add hex-to-css-filter-library`

   Node.js 24 or newer is required for the local dataset (it uses the built-in
   `node:sqlite` driver — no native install steps). Browser builds talk to the
   dataset over the network instead.

1. Add the dependency into your file

    ```js
    import HexToCssFilterLibrary from 'hex-to-css-filter-library'
    ```

1. Create an instance and fetch a filter — no account, API key, or manual data
   setup:

    ```js
    const hexToCssFilterLibrary = new HexToCssFilterLibrary()
    const filter = await hexToCssFilterLibrary.fetchFilter('#42dead')
    // BEGIN:example-filter
    // invert(95%) sepia(18%) saturate(20940%) hue-rotate(66deg) brightness(157%) contrast(74%)
    // END:example-filter
    ```

On Node, the first lookup downloads the dataset artifact (~460 MB gzipped) from
the release mirror, verifies it against a SHA-256 checksum pinned in the
library, and caches it under a per-user data directory keyed by dataset
snapshot. Every lookup after that is a local database read with zero network
access. In the browser the same lookup is served from the public dataset
mirror over HTTPS (the Hugging Face Dataset Viewer API), so there is nothing
to cache.

### Options

```js
// Defaults are shown; all options are optional.
const hexToCssFilterLibrary = new HexToCssFilterLibrary({
  source: 'local',      // 'local' (Node default) | 'remote' (browser default)
  dbPath: null,         // your own copy of the database; skips the cache
  cacheDir: null,       // override the per-user cache root
  fetchFunction: fetch  // inject a fetch implementation if you like
})
```

| Name            |   Type   | Default            | Description                                                                                                          |
| --------------- | :------: | ------------------ | -------------------------------------------------------------------------------------------------------------------- |
| `source`        |  String  | `local` on Node, `remote` in browsers | `local`: download-and-cache SQLite dataset (Node only). `remote`: read-only lookups over the public dataset mirror. |
| `dbPath`        |  String  | cache location     | Path to a copy of the dataset you downloaded yourself — the escape hatch for air-gapped machines. (If no usable file is found there, the library downloads to that path.) |
| `cacheDir`      |  String  | per-user cache dir | Root under which the dataset snapshot is cached (defaults to macOS `~/Library/Caches`, Linux `$XDG_CACHE_HOME`/`~/.cache`, Windows `%LOCALAPPDATA`). |
| `fetchFunction` | Function | `fetch`            | Used for the dataset download (and for `remote` lookups).                                                            |

The v2 constructor form `new HexToCssFilterLibrary(apiKey, options)` is still
accepted — the string is ignored, since no account or API key is needed
anymore (DBHub.io hosting is retired).

### Cache location

The cache lives at
`datasets/<snapshot>/hex-to-css-filter-covering-dataset-<snapshot>.sqlite3`.
It is keyed by dataset snapshot (never library version), so upgrades reuse it.
A corrupt or missing cache is re-downloaded automatically; a checksum failure
rejects the file and tries the next mirror rather than trusting it. If every
mirror fails, the error names each URL and includes copy-pasteable
`curl` + `shasum` instructions plus the `dbPath` hint.

## Documentation

### Hex Color Input

Hex color codes can be passed in with 3 or 6 digits, [case insensitive](https://en.wikipedia.org/wiki/Case_sensitivity), and [hash](https://en.wikipedia.org/wiki/Number_sign) insensitive.

For example, all of these are valid and accepted representations:

- `333`
- `#333`
- `333333`
- `#333333`

### Fetch Filter

```js
const filter = await hexToCssFilterLibrary.fetchFilter('#42dead')
// BEGIN:example-filter
// invert(95%) sepia(18%) saturate(20940%) hue-rotate(66deg) brightness(157%) contrast(74%)
// END:example-filter

const options = {
  filterPrefix: true,
  preBlacken: true
}
const filter = await hexToCssFilterLibrary.fetchFilter('#42dead', options)
// BEGIN:example-filter-prefix
// filter: brightness(0) saturate(1) invert(95%) sepia(18%) saturate(20940%) hue-rotate(66deg) brightness(157%) contrast(74%)
// END:example-filter-prefix
```

| Parameter  |  Type  | Description                             |
| ---------- | :----: | --------------------------------------- |
| `hexColor` | String | see [Hex Color Input](#hex-color-input) |

#### Options

| Name           |  Type   | Default | Description                                    |
| -------------- | :-----: | ------- | ---------------------------------------------- |
| `filterPrefix` | Boolean | `false` | flag for `filter:` inclusion                   |
| `preBlacken`   | Boolean | `false` | flag for `brightness(0) saturate(1)` inclusion |

The chain is returned verbatim from the dataset — stored witnesses, not
re-derived guesses.

### Fetch Color Record

```js
const colorRecord = await hexToCssFilterLibrary.fetchColorRecord('#42dead')
// BEGIN:example-record
// {
//   id: 4382381,
//   filter: 'invert(95%) sepia(18%) saturate(20940%) hue-rotate(66deg) brightness(157%) contrast(74%)',
//   loss: 0.8793432176
// }
// END:example-record

const options = { raw: true }
const rawColorRecord = await hexToCssFilterLibrary.fetchColorRecord('#42dead', options)
// BEGIN:example-record-raw
// [
//   [
//     { Name: 'id', Type: 'integer', Value: '4382381' },
//     { Name: 'filter', Type: 'text', Value: 'invert(95%) sepia(18%) saturate(20940%) hue-rotate(66deg) brightness(157%) contrast(74%)' },
//     { Name: 'loss', Type: 'real', Value: '0.8793432176' }
//   ]
// ]
// END:example-record-raw
```

| Parameter  |  Type  | Description                             |
| ---------- | :----: | --------------------------------------- |
| `hexColor` | String | see [Hex Color Input](#hex-color-input) |

#### Options

| Name  |  Type   | Default | Description                                       |
| ----- | :-----: | ------- | ------------------------------------------------- |
| `raw` | Boolean | `false` | flag for the column-by-column Name/Type/Value map |

`loss` in the record is the dataset's rendered loss (see
[docs/dataset.md](docs/dataset.md#the-metric-rendered-loss)) — lower is
better, and every row is under 1.

### Query DB

`queryDb()` runs read-only SQL against the local dataset (it requires
`source: 'local'`, i.e. Node):

```js
const sql = 'SELECT COUNT(*) AS colors FROM color'
const response = await hexToCssFilterLibrary.queryDb(sql)
// [ [ { Name: 'colors', Type: null, Value: '16777216' } ] ]

const options = { getFirstValue: true }
const count = await hexToCssFilterLibrary.queryDb(sql, options)
// '16777216' (the expression column has no declared type; for table columns
// Type is 'integer' | 'text' | 'real')
```

| Parameter |  Type  | Description  |
| --------- | :----: | ------------ |
| `sql`     | String | query to run |

#### Options

| Name            |  Type   | Default | Description                                                    |
| --------------- | :-----: | ------- | -------------------------------------------------------------- |
| `getFirstValue` | Boolean | `false` | flag for getting the value of the first record in the response |

## Dataset

<!-- BEGIN:claim-summary -->
The dataset is a covering certificate: every one of the **16,777,216 sRGB colors** has a stored
filter chain whose rendered loss (see the metric definition in
[docs/dataset.md](docs/dataset.md#the-metric-rendered-loss)) is under 1%. Snapshot `2026.10.07`
is the build pinned in this library: it ships checksummed, is verified on every
download, and this summary regenerates from it — refusing to render unless
every row passes.

- Max rendered loss: `0.9999991215` (0 rows at or above 1)
- Average rendered loss: 0.78803
- 16,777,211 rows use integer parameters; 5 extreme-saturation colors use 0.1-granularity fractional parameters

Full loss statistics, the distribution chart, the schema, and the artifact
checksums live in **[docs/dataset.md](docs/dataset.md)**.
<!-- END:claim-summary -->

## FAQ

- A filter isn't working/accurate, what's going on?

  - The filters in the dataset assume a starting color of black (`#000000`). If
    your HTML element isn't black, you'll need to use the
    [`preBlacken` option](#options-1).

- What if I'm not using JavaScript?

  - The dataset is a plain SQLite file (and a Parquet mirror) under
    [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) — download it,
    verify the pinned checksum, and read it with any SQLite client. The
    artifact URLs and the one-command verification are in
    [docs/dataset.md](docs/dataset.md#the-artifact).

- Can I use this on an air-gapped machine?

  - Yes: download the dataset anywhere you have network, then construct with
    `{ dbPath: '/path/to/hex-to-css-filter-covering-dataset-<snapshot>.sqlite3' }`.
    The library uses that file directly and never touches the network.

- What happened to DBHub.io and the `apiKey`?

  - Retired. The dataset is published as a plain release artifact on mirrors
    with no account, token, or rate limit in the loop, and integrity is
    established by the pinned SHA-256 instead of by trusting a host.

## About Problem Domain

The leading method to convert a hex color to a CSS filter is trial-and-error
loss minimization at runtime:

- Search using [SPSA](https://en.wikipedia.org/wiki/Simultaneous_perturbation_stochastic_approximation) by [MultiplyByZer0 on Stack Overflow](https://stackoverflow.com/a/43960991/5988852)

- NPM package: [hex-to-css-filter](https://github.com/willmendesneto/hex-to-css-filter)

- Brute force with partial color coverage by [Dave on Stack Overflow](https://stackoverflow.com/a/43959856/5988852)

This library replaces search with lookup. The dataset is an exhaustive
constructive certificate for the covering claim "every sRGB color has a stored
filter chain that renders under 1% loss": one witness per color, checkable row
by row from the artifact alone. The witnesses are integer-parameter chains,
with five extreme-saturation exceptions noted in
[docs/dataset.md](docs/dataset.md#fractional-parameter-exceptions).

## License

- Library code: [MIT](LICENSE)
- Dataset: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
