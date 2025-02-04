[![License: CC0-1.0](https://img.shields.io/badge/License-CC0%201.0-lightgrey.svg)](http://creativecommons.org/publicdomain/zero/1.0/)

# `byconaut`

The `byconaut` package contains scripts for data processing for and based on the
`bycon` package. The main use cases are:

* generation of utility collections for the standard Progenetix data model
    - `collations`
    - `frequencymaps` provide binned CNV frequency values for samples belonging
      to a given collation code
* I/O & transformations for `bycon` generated files

## Installation

`byconaut` depends on the `bycon` package which can be downloaded from its
[repository](http://github.com/progenetix/bycon/). Please see the repository
and the corresponding [documentation site](http://bycon.progenetix.org).

While there is also a `pip` installation possible over `pip3 install bycon`
this will _not_ include the local configuration files necessary e.g. for
processing the databases.

## Database setup

### Option A: `examplez` from <rsrc/mongodump>

1. download <rsrc/mongodump/examplez.zip>
2. unpack somewhere & restore with (your paths etc.):
```
mongosh examplez --eval 'db.dropDatabase()'
mongorestore --db examplez ./rsrc/mongodump/examplez/
```
3. proceed w/ step 4 ... below

### Option B: Create your own databases

1. Create database and variants collection
2. update the local `bycon` installation for your database information andlocal parameters
    * database name(s)
    * `filter_definitions` for parameter mapping
3. Create metadata collections - `callsets`, `biosamples` and `individuals`
4. Create `statusmaps` and CNV statistics for the callsets collection
    * only relevant for CNV database use cases
5. Create the `collations` collection which uses `filter_definitions` and the
   corresponding values to aggregate information for query matching, term expansion ...
6. Create `frequencymaps` for binned CNV data
    * relies on existence of `statusmaps` in `callsets` and `collations`
    * only needed for CNV data

## Server `services`

Since version `1.0.55` (2023-06-22) additional "services" may be installed from
the [`byconaut`](https://github.com/progenetix/byconaut/) repository using the
[`install.py`](./install.py) utility script. Please edit the [`install.yaml`](./install.yaml) configuration accordingly.


## Data maintenance scripts

### `callsetsStatusmapsRefresher` (CNV)

The `callsetsStatusmapsRefresher` script creates CNV status data for binned
genomic intervals, for each CNV callset (_i.e._ the CNV data of all corresponding
variants from the same experiment/sample).


#### Examples

* `bin/callsetsStatusmapsRefresher.py -d examplez`

### `collationsCreator`

**`collations`** provide aggregate data for all samples etc. matching a given
classification, external reference or other entity code, including hierarchy
data for term expansion when matching the code. The hierarchy data is provided
in `rsrc/classificationTrees/__filterType__/numbered-hierarchies.tsv` as a list
of ordered branches in the format `code | label | depth | order`.

#### Examples

* `bin/collationsCreator.py -d examplez --collationtypes "icdom,icdot"`
* `bin/collationsCreator.py -d progenetix`

### `frequencymapsCreator` (CNV)

**`frequencymaps`** contain pre-computed frequencies for CNV data, aggregating
the binned statusmaps data from all callsets belonging to a given collation.

#### Examples

* `bin/frequencymapsCreator.py -d examplez`

## Utility apps

### `ISCNsegmenter`

#### Examples

* `bin/ISCNsegmenter.py -i imports/ccghtest.tab -o exports/cghtest-with-histo.pgxseg`
