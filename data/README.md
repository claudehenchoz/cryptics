# Manually Abstracted Data

This directory contains files of _ad hoc_ manual abstracted data.

- `new-yorker-urls.txt`: from November 2019 to June 2021, The New Yorker
  [republished an old cryptic crossword from their
  archive](https://www.newyorker.com/puzzles-and-games-dept/cryptic-crossword/reintroducing-the-new-yorkers-cryptic-crossword)
  (these cryptics were originally published between 1997 and 1999). This file
  contains the URLs of these republished cryptics.
- `cru-cryptics-pdf.csv`: clues from the three PDFs (`Cryptic217.pdf`,
  `Cryptic225.pdf` and `Cryptic235.pdf`) from the `cru_cryptics` archive,
  initially provided by [Michael F. Gill](https://bbtp.net/) and subsequently
  augmented by [George Ho](https://www.georgeho.org/).

# Downloaded Data

`python -m cryptics.update` downloads the following datasets into `downloads/`
(which is not checked in):

- `georgeho-data.db`: the published dataset from
  [cryptics.georgeho.org](https://cryptics.georgeho.org/data.db), made
  available under the [Open Database License](http://opendatacommons.org/licenses/odbl/1.0/).
  It is used to seed the local database.
- `cryptonite-official-split.zip`: the
  [Cryptonite](https://github.com/aviaefrat/cryptonite) dataset of ~523k
  cryptic clues from The Times and The Telegraph (2000-2020), by Efrat,
  Shaham, Kilman and Levy ([EMNLP 2021](https://aclanthology.org/2021.emnlp-main.344/)).
  Its [dataset card](https://huggingface.co/datasets/cryptonite) lists a
  CC BY-NC 4.0 license, so it should only be used non-commercially. Its clues
  are lowercased, and have no definitions or annotations.
