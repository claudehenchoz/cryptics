# A Dataset of Cryptic Crossword Clues

> `cryptics.georgeho.org` is a dataset of cryptic crossword clues,
> collected from various blogs and digital archives.

This repository contains:

- The [`cryptics`](https://github.com/eigenfoo/cryptics/tree/main/cryptics)
  Python library to scrape various cryptic crossword blogs and parse the
  scraped blog posts into a structured dataset of cryptic crossword clues.
- The [`docs`](https://github.com/eigenfoo/cryptics/tree/main/docs),
  [`static`](https://github.com/eigenfoo/cryptics/tree/main/static) files and
  [`templates`](https://github.com/eigenfoo/cryptics/tree/main/templates)
  needed to generate the static site for documentation.
- Miscellaneous
  [`scripts`](https://github.com/eigenfoo/cryptics/tree/main/scripts) and
  [`queries`](https://github.com/eigenfoo/cryptics/tree/main/queries) to
  publish and deploy the Datasette instance.

For more information, please see [`cryptics.georgeho.org`](https://cryptics.georgeho.org/).

## Building the dataset locally

The clues themselves are not stored in this repository. To build a local
SQLite database (`cryptics.sqlite3`) and CSV exports:

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt   # venv\Scripts\pip on Windows
venv/bin/python -m cryptics.update all
```

This runs the following steps, each of which can also be run on its own
(`python -m cryptics.update --help`). Every step is resumable and only fetches
what is new, so re-running it later picks up newly published puzzles.

| Step         | What it does                                                                                                         |
| ------------ | -------------------------------------------------------------------------------------------------------------------- |
| `seed`       | Downloads the published [cryptics.georgeho.org](https://cryptics.georgeho.org/) dataset (~660k clues, up to July 2023). |
| `cryptonite` | Imports the [Cryptonite](https://github.com/aviaefrat/cryptonite) research dataset (~523k Times and Telegraph clues).   |
| `blogs`      | Scrapes and parses new posts from bigdave44, fifteensquared, Times for the Times, The Hindu Crossword Corner, etc.     |
| `guardian`   | Scrapes The Guardian's cryptic, prize, quiptic and Everyman crosswords (structured JSON, with answers).                |
| `export`     | Writes `exports/clues.csv.gz` (every clue) and `exports/clues-unique.csv.gz` (one row per distinct clue and answer). |

A full scrape takes many hours, because requests are rate-limited to about one
per second per site. Sources are on different hosts, so you can run them in
parallel, e.g. `python -m cryptics.update blogs --sources fifteensquared` and
`python -m cryptics.update guardian` in separate terminals. Use `--limit N` for
a quick trial run.

Note that the Cryptonite data is distributed for non-commercial research use
(CC BY-NC 4.0), and that the blog annotations belong to the blogs that wrote
them. See [`data/README.md`](data/README.md).

## License

This dataset is made available under the [Open Database License](http://opendatacommons.org/licenses/odbl/1.0/).
A human-readable summary is [available here](https://opendatacommons.org/licenses/odbl/summary/).
Any rights in individual contents of the database are licensed under the [Database Contents License](http://opendatacommons.org/licenses/dbcl/1.0/).

HTML and CSS code was modified from [`pandoc-markdown-css-theme`](https://github.com/jez/pandoc-markdown-css-theme),
which is licensed under the [Blue Oak Model License](https://blueoakcouncil.org/license/1.0.0).
The remainder of the code is licensed under the [MIT License](https://mit-license.org/).

## Colophon

`cryptics.georgeho.org` is written in a mix of Python, Bash and SQL
and is run on my personal laptop.

The data is published using [Datasette](https://datasette.io/) and deployed on
a [Fly Trial Plan](https://fly.io/). Datasette has been remarkably easy to work
with and a pleasure to use.

The documentation is a static site adapted from
[`pandoc-markdown-css-theme`](https://github.com/jez/pandoc-markdown-css-theme).
