// Pinned dataset release: mirrors serve the same bytes, each download is
// verified against these SHA-256 sums.
const DATASET_RELEASE = Object.freeze({
  snapshot: '2026.10.07',
  dbFile: 'hex-to-css-filter-covering-dataset-2026.10.07.sqlite3',
  gzFile: 'hex-to-css-filter-covering-dataset-2026.10.07.sqlite3.gz',
  gzSize: 482760063,
  gzSha256: 'a5b84e204d8e9369f0174a63f79cf50519ceb1c3d1dbd4a59059319b71034b9c',
  dbSize: 1837748224,
  dbSha256: 'bb2d6b5e1696adfa5f6d689fc41d5696868ed4bc37078e35227132f94dd5717a',
  urls: Object.freeze([
    'https://github.com/blakegearin/hex-to-css-filter-library/releases/download/dataset-2026.10.07/hex-to-css-filter-covering-dataset-2026.10.07.sqlite3.gz',
    'https://huggingface.co/datasets/blakegearin/hex-to-css-filter-covering-dataset/resolve/main/sqlite/hex-to-css-filter-covering-dataset-2026.10.07.sqlite3.gz',
    'https://data.blakegearin.com/2026.10.07/hex-to-css-filter-covering-dataset-2026.10.07.sqlite3.gz'
  ]),
  manualInstructions: Object.freeze([
    'Download manually, e.g.:',
    '  curl -sSfL -O https://github.com/blakegearin/hex-to-css-filter-library/releases/download/dataset-2026.10.07/CHECKSUMS.txt \\',
    '    -O https://github.com/blakegearin/hex-to-css-filter-library/releases/download/dataset-2026.10.07/hex-to-css-filter-covering-dataset-2026.10.07.sqlite3.gz',
    '  sha256sum -c CHECKSUMS.txt  (on macOS: shasum -a 256 -c CHECKSUMS.txt)',
    '  gunzip hex-to-css-filter-covering-dataset-2026.10.07.sqlite3.gz',
    'Then use your copy: new HexToCssFilterLibrary({ dbPath: \'/path/to/hex-to-css-filter-covering-dataset-2026.10.07.sqlite3\' })'
  ])
})

// Hugging Face Dataset Viewer API over the id-sorted Parquet mirror: the row
// offset is the color id; responses are validated by re-checking the id.
const REMOTE = Object.freeze({
  rowsEndpoint: 'https://datasets-server.huggingface.co/rows',
  dataset: 'blakegearin/hex-to-css-filter-covering-dataset',
  config: 'default',
  split: 'train'
})

export default Object.freeze({
  dbPath: null,
  cacheDir: null,
  datasetRelease: DATASET_RELEASE,
  remote: REMOTE,
  getFirstValue: false,
  fetchFunction: fetch
})
