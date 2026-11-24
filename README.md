# EV charging gap in Germany

Where does public charging infrastructure lag behind the number of electric cars? This project combines the Bundesnetzagentur charging point register with battery electric car numbers per district, models how many charging points each district would be expected to have, and ranks the districts with the largest gap. The result shows where a charging operator or a carmaker could look first when deciding where new charging points are most needed.

Unit of analysis: district (Kreis / Zulassungsbezirk), 399 districts after cleaning.

The model describes the current relationship between cars and charging points. It does not show how many charging points are optimal.

## Status

| Step | Status |
|---|---|
| 1. Data research | done |
| 2. Download script | done |
| 3. Exploration notebook | done |
| 4. Cleaning pipeline with tests | done |
| 4b. Preliminary insights in the notebook | done |
| 5. Baseline and model | next |
| 6. Ranking and value estimate | planned |
| 7. Prototype (map notebook, API) | planned |
| 8. Presentation | planned |

## How to run

Requirements: [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.13 or newer.

```bash
uv sync                           # create .venv and install packages
uv run python -m ev_gap.download  # download the three raw files into data/raw/
uv run python -m ev_gap.pipeline  # clean, join, write data/processed/districts.csv
uv run pytest                     # run the tests
```

The exploration notebook can be opened without the pipeline. Open `notebooks/01_explore_data.ipynb` and select the kernel of the `.venv` in this folder.

Running the download again is safe. Files that are already in `data/raw/` are skipped. Raw and processed data are not committed.

## Data sources

| Source | Content | Reference date | Link |
|---|---|---|---|
| Bundesnetzagentur Ladesäulenregister | Public charging stations with number of points, power, commissioning date, district name, coordinates. CSV, about 58 MB. Licence CC BY 4.0 | 12.11.2026 | [Bundesnetzagentur](https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/E-Mobilitaet/start.html) |
| Kraftfahrt-Bundesamt, table FZ 1.2 | Passenger cars per Zulassungsbezirk by fuel type, `Elektro (BEV)` and plug-in hybrid as separate columns. XLSX | 01.01.2026 | [KBA direct file](https://www.kba.de/SharedDocs/Downloads/DE/Statistik/Fahrzeuge/FZ1/fz1_2026.xlsx?__blob=publicationFile&v=2) |
| Destatis, Kreisfreie Städte und Landkreise | Area, population (Zensus 2022 basis) and density per Kreis. XLSX | 31.12.2024 | [Destatis page](https://www.destatis.de/DE/Themen/Laender-Regionen/Regionales/Gemeindeverzeichnis/Administrativ/04-kreise.html) |

The three reference dates differ. Cars are about 10 months older than the charging points, and the population is almost 2 years older. This is a limitation of the analysis.

BEV means battery electric vehicle: a car that runs on a battery only. Plug-in hybrids (PHEV) are a separate column in the KBA table and are not part of the BEV count.

## Project structure

```
data/raw/            downloaded files, not committed
data/processed/      cleaned tables, not committed
src/ev_gap/
  config.py          paths, source URLs, district key rules (settings only)
  download.py        download of the three raw files
  extract.py         read the raw files into clean tables (file quirks only)
  keys.py            map register district names to official district keys
  transform.py       clean the register, join the three sources, check the totals
  pipeline.py        run extract, transform and write data/processed/districts.csv
notebooks/
  01_explore_data.ipynb   exploration only, not part of the pipeline
tests/
  conftest.py        small made-up tables, one district per rule
  test_extract.py    layout parsing of the KBA and Destatis sheets
  test_keys.py       district key mapping
  test_transform.py  cleaning, key merges, join, totals check
  test_pipeline_integration.py   end to end on the real files (skipped if not downloaded)
```

## Step log

Each step is written down here as it is completed. The log is the base for the presentation.

### Step 1: Data research

Goal: find out which public data exists for charging points, electric cars and district size, and whether the three can be joined.

What was done:
- The Bundesnetzagentur register was confirmed as a CSV download. The file name contains the update date, so the link is read from the landing page.
- The KBA table with fuel types per Zulassungsbezirk was not found at first. A search found FZ 27 (fuel types, but only per federal state) and FZ 1 (per Zulassungsbezirk, no fuel type seen in a first summary). Opening the FZ 1 file itself showed sheet FZ 1.2: passenger cars per Zulassungsbezirk by fuel type, with `Elektro (BEV)` as its own column, stock on 01.01.2026.
- Destatis publishes one table with all Kreise, area and population.

Result: all three sources exist as free downloads, and BEV per district is available.

### Step 2: Download script

`src/ev_gap/download.py` downloads the three files to `data/raw/`.

Design choices:
- Existing files are skipped, so the script can run again without cost.
- A file is first written under a `.part` name and renamed when complete. A failed download leaves no half-written file.
- The register link is looked up on the Bundesnetzagentur page with a regular expression, because the date in the file name changes with each update.
- All URLs and file names are in `config.py`.

### Step 3: Exploration notebook

`notebooks/01_explore_data.ipynb` looks at the three raw files, tests whether they can be joined, and shows first patterns. It is exploration only. The cleaning code will be written as functions in `src/ev_gap/`.

**Observed in the data**

- The register has 119,048 stations with 214,453 charging points. Some stations have several points, so the number of points is the right count, not the number of rows. 28.5% of the points are fast chargers.
- KBA counts 2,031,870 battery electric cars, 4.11% of all passenger cars. The district rows add up exactly to the national total in the file.
- Across 399 districts there are 9.5 BEV per public charging point (ratio of the sums). The median district has 9.8, the range is 2.9 to 29.8. Highest values: Euskirchen (29.8), Südwestpfalz (23.2), Wolfenbüttel (22.7).
- BEV and charging points rise together. The correlation of the logarithms is 0.88. A regression model for the expected number of points is therefore reasonable.
- Cars per charging point show no clear trend with population density.
- Most charging points were commissioned in 2022 or later. The year 2026 is incomplete.

**Data issues found**

1. The register CSV has 10 lines of notes before the header, uses `;` as separator and a decimal comma. Reading it as UTF-8 fails, `cp1252` works.
2. The register has district names, not district keys. The match to the official keys must use the type (city or rural district) together with the name. Matching on the name alone counted points twice for pairs such as Passau, Rosenheim and Hof (city and surrounding Landkreis with the same name). With the type included, 400 of 401 names match. The extra name is `Kreisfreie Stadt Hanau`.
3. KBA Zulassungsbezirke and Destatis Kreise differ in two places. KBA lists Hanau as its own district, Destatis does not. KBA merges the city of Trier with Trier-Saarburg, Destatis lists them separately.
4. The register has 29 stations with status "In Wartung" and one coordinate outside Germany. 231 stations report more than 400 kW. This is likely a station total for fast charging hubs. Not verified.
5. The three reference dates differ (see Data sources).

**Check of the join**

After the fixes, the sum of charging points is 214,453 in the joined table and in the raw register. The BEV sum is 2,031,870 in both. No district was lost or counted twice.

### Step 4: Cleaning pipeline (ETL)

The pipeline reads the three raw files, cleans them, maps the district keys, joins everything to one table per district and writes `data/processed/districts.csv`. Run it with `uv run python -m ev_gap.pipeline`.

**ETL, not ELT.** The data is small (about 120,000 register rows and 400 districts) and there is no database or warehouse. The hard parts are the Excel layout of the KBA file and the match of free text district names to official keys. This is easier to write and test in pandas than in SQL. ELT would make sense for large raw data that is loaded into a warehouse first.

**Structure.** The same split as in the earlier bootcamp projects: settings in `config.py`, reading in `extract.py`, rules in `keys.py` and `transform.py`, and a thin `pipeline.py` that does the file input and output. The transform functions take and return DataFrames and know no file paths, so tests can use small made-up tables.

**What each stage does**
- `extract.py`: handles the file quirks only. Header lines, encoding, decimal comma, Excel header rows, subtotal rows. The KBA reader raises an error if the district rows do not add up to the national total in the file.
- `keys.py`: type-aware name match (city or rural district, plus normalised name). Raises an error for any register name without a key and if the official names are ambiguous. The manual rule for Hanau and the merge rules for Hanau and Trier-Saarburg are in `config.py`.
- `transform.py`: keeps stations that are in operation, counts charging points per district (normal and fast separately), sums cars, population and area where districts are merged, and adds density and BEV per charging point. `check_totals` stops the pipeline if the join changed the total of BEV, plug-in hybrids, population or charging points.

**Result.** 399 districts. BEV 2,031,870. Plug-in hybrids are kept in the table (`phev`) for the sensitivity check. Charging points 214,398 (153,286 normal and 61,112 fast). 55 charging points at stations with status "In Wartung" are not counted. 9.5 BEV per charging point nationally, the same value as in the exploration notebook.

The output has 12 columns: `key`, `name`, `pkw_total`, `bev`, `phev`, `area_km2`, `population`, `density`, `points_normal`, `points_fast`, `charging_points`, `bev_per_point`. A district with no charging points would get an empty `bev_per_point` instead of infinity. There is none in the current data.

**Tests (21).** The key mapping (city and Landkreis with the same name, Oldenburg, Mühldorf with different spacing, Hanau rule, unknown name, ambiguous names, merges), the sheet parsing, the cleaning rule, point counts per district, the Hanau and Trier merges, a district without points, derived columns, and the totals check. One integration test runs the whole pipeline on the real files and is skipped if they are not downloaded.

### Step 4b: Two preliminary insights (notebook section 7)

Goal: find at least one insight about charging infrastructure that the data supports, and that explains why a model is needed.

The section reads the processed table from the pipeline (399 districts, 214,398 charging points) and fits straight lines on log values. It is an in-sample first look. The model step repeats it with cross validation.

**Insight 1: charging points follow residents about as much as electric cars.**

| Explaining charging points with | Elasticity | Share of variation explained (R²) |
|---|---|---|
| BEV only | 0.84 | 0.78 |
| Population only | 1.00 | 0.76 |
| BEV and population | 0.49 for BEV, 0.48 for population | 0.81 |

The elasticity says by how many percent the charging points rise if the input is 10% higher. Population alone explains almost as much as BEV alone. With both in the model, each carries about half of the effect.

**Insight 2: the plain ratio "cars per charging point" is biased against large districts.** Points grow slower than cars (slope 0.84, below 1). The pooled ratio is 7.4 BEV per point in the smallest third of districts (by BEV), 9.4 in the middle and 10.0 in the largest third. The rank correlation of the ratio with the BEV count is 0.35. If the size effect is removed with a simple fit, 31 of the 40 districts with the highest ratio stay in the top 40, so 9 change.

Consequence: a ranking by the plain ratio would flag large districts partly because they are large. This is the reason to model the expected number of points instead.

Caveats:
- BEV and population correlate at 0.89. The two coefficients cannot be separated cleanly. Read them as "about half and half".
- The fit is in-sample.
- The data does not show why points follow residents. A slope below 1 can also come from a minimum infrastructure that every district needs.

**Data quality example from the join.** A first name match that ignored the type (city or rural district) counted charging points twice for pairs such as Passau, Rosenheim and Hof. These cities then looked like the best supplied districts in Germany, with 1 to 3 BEV per point. The totals check in the pipeline now catches this kind of error. The number of such name pairs has not been counted yet.

### Assumptions

These are decisions made by the author. They are not confirmed by official documentation.

| Id | Assumption | Where used |
|---|---|---|
| A1 | Hanau is part of Main-Kinzig-Kreis (06435). KBA and register values for Hanau are added to it. | district key mapping |
| A2 | The city of Trier and Trier-Saarburg are one district, as in the KBA file. Population, area and charging points are summed. | district key mapping |
| A3 | A charging point counts the same, whether it is a normal or a fast charger. | target definition |
| A4 | Cars are counted by the place of registration. This is taken as the place where the cars are used and charged. | all results |
| A5 | Stations with status "In Wartung" (29 stations, 55 points) are not counted. All other stations in the register have status "In Betrieb". | `clean_register` |

### Limitations known so far

- KBA counts cars by registration place. Company and leasing registrations can inflate a district.
- Through traffic, tourism and commuters are not in the data.
- The register lists only points whose notification process is complete, so it undercounts. This is stated by the Bundesnetzagentur.
- Reference dates differ between the three sources.
- Home and workplace charging is not in the data. Only public points are counted.

## Planned next

1. **Baseline.** BEV per charging point per district.
2. **Model.** Linear regression of charging points on BEV, population and density, with k-fold cross validation and a comparison to the baseline. Residual analysis. Gap = actual minus expected.
3. **Sensitivity check with plug-in hybrids.** Add the plug-in hybrid count (`phev`, already loaded in the notebook) as a second feature or as a combined plug-in car count. Check whether the district ranking changes. BEV stays the main driver, because plug-in hybrids are often charged at home or at work. This is an assumption to test.
4. **Ranking and value estimate.** List of districts with the largest gap. Every value assumption is marked as an assumption.
5. **Prototype.** Notebook with a map, and a small API that returns the gap for one district.
6. **Docker.** One Dockerfile for the API, written when the API works.
7. **Presentation.** 15 minutes, English.

## How AI tools were used

Claude Code (Anthropic) was used in this project as a coding assistant. Per step so far:

- Step 1: web searches and page fetches to find the data sources. The KBA file was opened and read to check the BEV column.
- Step 2: the first version of the download script was written by the assistant.
- Step 3: the first version of the exploration notebook was written by the assistant. A join error (double counting of cities and Landkreise with the same name) was found while running the notebook and fixed. The check that the totals match was added because of it.
- Step 4: the pipeline modules and the 21 tests were written by the assistant, based on the logic of the notebook. The totals check reproduces the numbers of the notebook (2,031,870 BEV, 9.5 BEV per charging point). The 55 points in maintenance are the difference to the notebook's 214,453 points.
- Step 4b: the quick checks and the figures of section 7 were written by the assistant after a discussion of which insight to lead with. The assistant first judged the name matching problem to be a data quality example and not the main insight. Two chart problems (a truncated axis on the explained variation chart, a label on a reference line) were found by looking at the rendered figures and fixed.

The author is to complete this section: which results were reviewed or validated independently, and which decisions were taken by the author.
