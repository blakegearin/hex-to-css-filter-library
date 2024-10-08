[![npm version](https://badge.fury.io/js/hex-to-css-filter-library.svg)](http://badge.fury.io/js/hex-to-css-filter-library)
![Tests](https://img.shields.io/badge/tests-mocha-8d6748)
![Statements](https://img.shields.io/badge/statements-100%25-brightgreen.svg?style=flat)
![Branches](https://img.shields.io/badge/branches-100%25-brightgreen.svg?style=flat)
![Functions](https://img.shields.io/badge/functions-100%25-brightgreen.svg?style=flat)
![Lines](https://img.shields.io/badge/lines-100%25-brightgreen.svg?style=flat)
[![Javascript Style Guide](https://img.shields.io/badge/code_style-standard-f3df49)](https://standardjs.com)
[![MIT License](https://img.shields.io/badge/license-MIT%20License-blue)](LICENSE)

# hex-to-css-filter-library

A JavaScript library to access a [remote database](https://dbhub.io/blakegearin/hex-to-css-filter-db.sqlite3) of CSS filters to change HTML elements to any hex color code.

## Usage

1. Install the dependency

   - NPM: `npm install hex-to-css-filter-library`
   - Yarn: `yarn add hex-to-css-filter-library`

1. Add the dependency into your file

    ```js
    import HexToCssFilterLibrary from 'hex-to-css-filter-library'
    ```

1. Create an account with [DBHub.io](https://dbhub.io/)

1. Generate a new API key on your [Settings page](https://dbhub.io/pref)

1. Use your API key to fetch a CSS filter or query the database

    ```js
    const filter = await new HexToCssFilterLibrary(apiKey).fetchFilter('#42dead')
    ```

## Documentation

### Hex Color Input

Hex color codes can be passed in with 3 or 6 digits, [case insensitive](https://en.wikipedia.org/wiki/Case_sensitivity), and [hash](https://en.wikipedia.org/wiki/Number_sign) insensitive.

For example, all of these are valid and accepted representations:

- `333`
- `#333`
- `333333`
- `#333333`

### Constructor

```js
// This is hardcoded but it's standard to set this as an environment variable
// Your key should be kept secret and not committed or made public
const apiKey = '...'
const hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey)

const options = {...}
const hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey, options)
```

| Parameter |  Type  | Description           |
| --------- | :----: | --------------------- |
| `apiKey`  | String | generated by DBHub.io |

#### Options

Starting with [2.0.0](https://github.com/blakegearin/hex-to-css-filter-library/releases/tag/2.0.0), this package relies on [Node's fetch API](https://nodejs.org/dist/latest/docs/api/globals.html#fetch) instead of [`node-fetch`](https://www.npmjs.com/package/node-fetch). This makes the package work in the browser and Node.

If not on Node 16.15 or above, feel free to import `node-fetch` or another dependency and pass in the relevant options.

```js
import fetch, { FormData, Headers, Request } from 'node-fetch'

const options = {
  formDataClass: FormData,
  headersClass: Headers,
  requestClass: Request,
  fetchFunction: fetch,
}
const hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey, options)
```

| Name            |   Type   | Default                                                                                                                                          | Description                                                   |
| --------------- | :------: | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| `apiUrl`        |  String  | `https://api.dbhub.io`                                                                                                                           | URL for the DBHub.io API                                      |
| `apiEndpoint`   |  String  | `/v1/query`                                                                                                                                      | query endpoint for the DBHub.io API                           |
| `dbOwner`       |  String  | `blakegearin`                                                                                                                                    | owner of the database on DBHub.io                             |
| `dbName`        |  String  | `hex-to-css-filter-db.sqlite3`                                                                                                                   | name of the database on DBHub.io                              |
| `formDataClass` |  Class   | `FormData` of [Web API](https://developer.mozilla.org/en-US/docs/Web/API/FormData) or [Node](https://nodejs.org/api/globals.html#class-formdata) | class used to form the body of the request to the database    |
| `headersClass`  |  Class   | `Headers` of [Web API](https://developer.mozilla.org/en-US/docs/Web/API/Headers) or [Node](https://nodejs.org/api/globals.html#class-headers)    | class used to form the headers of the request to the database |
| `requestClass`  |  Class   | `Request` of [Web API](https://developer.mozilla.org/en-US/docs/Web/API/Request) or [Node](https://nodejs.org/api/globals.html#request)          | class used to form the request to the database                |
| `fetchFunction` | Function | `fetch` of [Web API](https://developer.mozilla.org/en-US/docs/Web/API/fetch) or [Node](https://nodejs.org/api/globals.html#fetch)                | function used to execute the request to the database          |

### Fetch Filter

```js
const filter = await hexToCssFilterLibrary.fetchFilter('#42dead')
// invert(66%) sepia(56%) saturate(416%) hue-rotate(110deg) brightness(98%) contrast(100%)

const options = {
  filterPrefix: true,
  preBlacken: true
}
const filter = await hexToCssFilterLibrary.fetchFilter('#42dead', options)
// filter: brightness(0) saturate(1) invert(66%) sepia(56%) saturate(416%) hue-rotate(110deg) brightness(98%) contrast(100%)
```

| Parameter  |  Type  | Description                             |
| ---------- | :----: | --------------------------------------- |
| `hexColor` | String | see [Hex Color Input](#hex-color-input) |

#### Options

| Name           |  Type   | Default | Description                                    |
| -------------- | :-----: | ------- | ---------------------------------------------- |
| `filterPrefix` | Boolean | `false` | flag for `filter:` inclusion                   |
| `preBlacken`   | Boolean | `false` | flag for `brightness(0) saturate(1)` inclusion |

### Fetch Color Record

```js
const colorRecord = await hexToCssFilterLibrary.fetchColorRecord('#42dead')
// {
//   id: 4382381,
//   invert: 66,
//   sepia: 56,
//   saturate: 416,
//   'hue-rotate': 110,
//   brightness: 98,
//   contrast: 100,
//   loss: 0.2578769732
// }

const options = { raw: true }
const rawColorRecord = await hexToCssFilterLibrary.fetchColorRecord('#42dead', options)
// [
//   [
//     { Name: 'id', Type: 4, Value: '4382381' },
//     { Name: 'invert', Type: 4, Value: '66' },
//     { Name: 'sepia', Type: 4, Value: '56' },
//     { Name: 'saturate', Type: 4, Value: '416' },
//     { Name: 'hue-rotate', Type: 4, Value: '110' },
//     { Name: 'brightness', Type: 4, Value: '98' },
//     { Name: 'contrast', Type: 4, Value: '100' },
//     { Name: 'loss', Type: 5, Value: '0.2578769732' }
//   ]
// ]
```

| Parameter  |  Type  | Description                             |
| ---------- | :----: | --------------------------------------- |
| `hexColor` | String | see [Hex Color Input](#hex-color-input) |

#### Options

| Name  |  Type   | Default | Description                                             |
| ----- | :-----: | ------- | ------------------------------------------------------- |
| `raw` | Boolean | `false` | flag for getting the raw response from the DBHub.io API |

### Query DB

```js
const sql = 'SELECT COUNT() FROM color'
const response = await hexToCssFilterLibrary.queryDb(sql)
// [ [ { Name: 'COUNT()', Type: 4, Value: '16777216' } ] ]

const options = { getFirstValue: true }
const response = await hexToCssFilterLibrary.queryDb(sql, options)
// 16777216
```

| Parameter |  Type  | Description  |
| --------- | :----: | ------------ |
| `sql`     | String | query to run |

#### Options

| Name            |  Type   | Default | Description                                                    |
| --------------- | :-----: | ------- | -------------------------------------------------------------- |
| `getFirstValue` | Boolean | `false` | flag for getting the value of the first record in the response |

## FAQ

- A filter isn't working/accurate, what's going on?

  - The filters in the database assume a starting color of black (#000000). If your HTML element isn't black, you'll need to use the [`preBlacken` option](#options-1).

- What if I'm not using JavaScript?

  - DBHub.io has [Python](https://github.com/LeMoussel/pydbhub) and [Go](https://github.com/sqlitebrowser/go-dbhub) libraries which can also be used to access the database.

- What if I don't want to rely on your DBHub.io database?

  - There's a few options...

    - Use the sister package, [hex-to-css-filter-library-with-db](https://github.com/blakegearin/hex-to-css-filter-library-with-db), which calls a local copy of the database.

    - The database has a [CC-BY-4.0 license](https://creativecommons.org/licenses/by/4.0/) so feel free to fork it on DBHub.io or host elsewhere. It's approximately 524 MB and you can use the [constructor options](#options) to change the DBHub.io default values.

## About Problem Domain

The current leading method to convert a hex color to a CSS filter is through trial & error with loss minimization.

- Search using [SPSA](https://en.wikipedia.org/wiki/Simultaneous_perturbation_stochastic_approximation) by [MultiplyByZer0 on Stack Overflow](https://stackoverflow.com/a/43960991/5988852)

- NPM package: [hex-to-css-filter](https://github.com/willmendesneto/hex-to-css-filter)

- Brute force with partial color coverage by [Dave on Stack Overflow](https://stackoverflow.com/a/43959856/5988852)

Instead of spending your own time & resources doing this, you can use this library to lookup already calculated [low loss](#loss-statistics) values. Currently all colors have less than **1%** loss.

I don't have plans to process lower values due to diminishing returns. If you are interested in doing this though, please get in touch and I can share my code.

## Database

There are 16,777,216 RGB hex colors. This is equal to 256<sup>3</sup>, with 256 values for red, green, and blue.

Field|Type|Description
-----|----|-----------
`id`|`INTEGER`|primary key, represents the hex color
`sepia`|`INTEGER`|percentage value for the [sepia filter function](https://developer.mozilla.org/en-US/docs/Web/CSS/filter-function/sepia)
`saturate`|`INTEGER`|percentage value for the [saturate filter function](https://developer.mozilla.org/en-US/docs/Web/CSS/filter-function/saturate)
`hue-rotate`|`INTEGER`|degree value for the [hue-rotate filter function](https://developer.mozilla.org/en-US/docs/Web/CSS/filter-function/hue-rotate)
`brightness`|`INTEGER`|percentage value for the [brightness filter function](https://developer.mozilla.org/en-US/docs/Web/CSS/filter-function/brightness)
`contrast`|`INTEGER`|percentage value for the [contrast filter function](https://developer.mozilla.org/en-US/docs/Web/CSS/filter-function/contrast)
`loss`|`REAL`|percentage value of the filter's loss (lower is better)

For reference: [SQLite datatypes](https://www.sqlite.org/datatype3.html)

### Loss Statistics

Average|Max|Min|0%|0.0%|0.1%|0.2%|0.3%|0.4%|0.5%|0.6%|0.7%|0.8%|0.9%|Total
-------|---|---|--|----|----|----|----|----|----|----|----|----|----|-----
0.40267|0.99999|0|8|1,233,492|2,944,170|3,259,251|2,388,299|1,716,667|1,323,179|1,106,540|987,981|920,722|896,907|16,777,216

```mermaid
pie showData
  "0% loss" : 8
  "0.0% loss" : 1233492
  "0.1% loss" : 2944170
  "0.2% loss" : 3259251
  "0.3% loss" : 2388299
  "0.4% loss" : 1716667
  "0.5% loss" : 1323179
  "0.6% loss" : 1106540
  "0.7% loss" : 987981
  "0.8% loss" : 920722
  "0.9% loss" : 896907
```
