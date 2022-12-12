# Hex to CSS Filter Library

A JavaScript library to access a [database](https://dbhub.io/blakegearin/hex-to-css-filter-db.sqlite3) of CSS filters to change HTML elements to any hex color code.

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

## Documentation

### Constructor

```js
// This is hardcoded but it's standard to set this as an environment variable
// Your key should be kept secret and not committed or made public
const apiKey = '...'
const hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey)

const options = {...}
const hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey, options)
```

| Name     |  Type  | Description           |
|----------|:------:|-----------------------|
| `apiKey` | String | generated by DBHub.io |

#### Options

| Name              |  Type   | Default                         | Description                                        |
|-------------------|:-------:|---------------------------------|----------------------------------------------------|
| `dbUrl`           | String  | `https://api.dbhub.io/v1/query` | URL for the DBHub.io API                           |
| `dbOwner`         | String  | `blakegearin`                   | owner of the database on DBHub.io                  |
| `dbName`          | String  | `hex-to-css-filter-db.sqlite3`  | name of the database on DBHub.io                   |
| `base64EncodeSql` | Boolean | `true`                          | the DBHub.io API requires SQL to be base64 encoded |

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

| Name       |  Type  | Description                                                         |
| ---------- | :----: | ------------------------------------------------------------------- |
| `hexColor` | String | case insensitive, valid formats: `#333333`, `#333`, `333`, `333333` |

#### Options

| Name           |  Type   | Default | Description                                    |
| -------------- | :-----: | ------- | ---------------------------------------------- |
| `filterPrefix` | Boolean | `false` | flag for `filter:` inclusion                   |
| `preBlacken`   | Boolean | `false` | flag for `brightness(0) saturate(1)` inclusion |

### Query DB

```js
const sql = 'SELECT COUNT() FROM color'
const filter = await hexToCssFilterLibrary.queryDb(sql)
// [ [ { Name: 'COUNT()', Type: 4, Value: '16777216' } ] ]

const options = {getFirstValue: true}
const filter = await hexToCssFilterLibrary.queryDb(sql, options)
// 16777216
```

| Name  |  Type  | Description  |
| ----- | :----: | ------------ |
| `sql` | String | query to run |

#### Options

| Name            |  Type   | Default                                        | Description                                                    |
| --------------- | :-----: | ---------------------------------------------- | -------------------------------------------------------------- |
| `getFirstValue` | Boolean | `false`                                        | flag for getting the value of the first record in the response |
| `requestBody`   | String  | `new FormData()` with appended DBHub.io values | `body` of the request                                            |

## FAQ

- A filter isn't working/accurate, what's going on?

  - The filters in the database assume a starting color of black (#000000). If your HTML element isn't black, you'll need to use the [`preBlacken` option](#options-1).

- What if I'm not using JavaScript?

  - DBHub.io has [Python](https://github.com/LeMoussel/pydbhub) and [Go](https://github.com/sqlitebrowser/go-dbhub) libraries which can also be used to access the database.

- What if I don't want to use DBHub.io?

  - The database has a [CC-BY-4.0 license](https://creativecommons.org/licenses/by/4.0/) so feel free to download it ([direct](https://dbhub.io/x/download/blakegearin/hex-to-css-filter-db.sqlite3), [API](https://api.dbhub.io/#download)) and host it wherever you like; it's approximately 524 MB and you can use the [constructor options](#options) to change the DBHub.io default values.

    ```js
    const hexToCssFilterLibrary = new HexToCssFilterLibrary(apiKey)

    // Get CSS filter
    const filter = await hexToCssFilterLibrary.fetchFilter('#42dead')
    // Get average loss
    const queryResponse = await hexToCssFilterLibrary.queryDb(`SELECT AVG(loss) FROM color`)
    //
    ```

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
