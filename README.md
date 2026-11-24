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
| 4c. Leakage review of the pipeline | done |
| 5. Baseline and model | done |
| 5b. Plug-in hybrid sensitivity check | next |
| 6. Ranking and value estimate | planned |
| 7. Prototype (map notebook, API) | planned |
| 8. Presentation | planned |

## How to run

Requirements: [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.13 or newer.

```bash
uv sync                           # create .venv and install packages
uv run python -m ev_gap.download  # download the three raw files into data/raw/
uv run python -m ev_gap.pipeline  # clean, join, write data/processed/districts.csv
uv run python -m ev_gap.model     # cross validation of the models, write data/processed/gaps.csv
uv run pytest                     # run the tests
```

**To run the notebook:** open `notebooks/01_explore_data.ipynb` and select the kernel of the `.venv` in this folder. Sections 1 to 6 need only the downloaded raw files. **Section 7 needs the output of the pipeline, so run the pipeline first** (`uv run python -m ev_gap.pipeline`). Without `data/processed/districts.csv`, section 7 stops with an error that says so.

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
  model.py           baseline, linear model on logs, gradient boosting, cross validation, gaps
notebooks/
  01_explore_data.ipynb   exploration only, not part of the pipeline
  02_model.ipynb          model comparison, residuals, gaps (needs the pipeline output)
tests/
  conftest.py        small made-up tables, one district per rule
  test_extract.py    layout parsing of the KBA and Destatis sheets
  test_keys.py       district key mapping
  test_transform.py  cleaning, key merges, join, totals check
  test_pipeline_integration.py   end to end on the real files (skipped if not downloaded)
  test_model.py      baseline learns from training districts only, no leakage of a district's own value, folds, gap
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
- `transform.py`: keeps stations that are in operation, counts charging points per district (normal and fast separately), sums cars, population and area where districts are merged, and adds the density. `check_totals` stops the pipeline if the join changed the total of BEV, plug-in hybrids, population or charging points.

**Result.** 399 districts. BEV 2,031,870. Plug-in hybrids are kept in the table (`phev`) for the sensitivity check. Charging points 214,398 (153,286 normal and 61,112 fast). 55 charging points at stations with status "In Wartung" are not counted. 9.5 BEV per charging point nationally, the same value as in the exploration notebook.

The output has 11 columns: `key`, `name`, `pkw_total`, `bev`, `phev`, `area_km2`, `population`, `density`, `points_normal`, `points_fast`, `charging_points`. A district with no charging points gets 0. There is none in the current data. See Step 4c for why cars per charging point is not a column.

**Tests (23).** The key mapping (city and Landkreis with the same name, Oldenburg, Mühldorf with different spacing, Hanau rule, unknown name, ambiguous names, merges), the sheet parsing, the cleaning rule, point counts per district, the Hanau and Trier merges, a district without points, the density, the totals check, and two leakage tests (no column is built from the target, the model features do not contain the target). One integration test runs the whole pipeline on the real files and is skipped if they are not downloaded.

### Step 4b: Two preliminary insights (notebook section 7)

Goal: find at least one insight about charging infrastructure that the data supports, and that explains why a model is needed.

**To reproduce this step, run the data pipeline first** (`uv run python -m ev_gap.pipeline`). The section reads the processed table from the pipeline (399 districts, 214,398 charging points) and fits straight lines on log values. It is an in-sample first look. The model step repeats it with cross validation.

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

### Step 4c: Leakage review of the transform steps

Question: can any step of the pipeline give the model information it should not have, so that the results look better than they are? This is called data leakage.

**Result of the review.** No transform step learns a number from the data (no mean, no scaling, no fill value). Each district row depends only on its own source rows and on fixed rules in `config.py`. So none of the steps has to move behind the train and test split.

**One problem found and fixed.** The table had a column `bev_per_point` (cars divided by charging points). Charging points are the target of the model, so this column contains the answer. If it were used as an input, the model would get the target for free. The column was removed from the pipeline. It is now computed only where it is needed for analysis (notebook section 7, and later the baseline). The columns `points_normal` and `points_fast` are parts of the target. They stay in the table for analysis, but they are never model input.

**Guard in the code.** `config.py` lists the model target (`charging_points`), the allowed input columns (`bev`, `population`, `density`) and the parts of the target. Two tests check that the table has no column built from the target and that the inputs do not contain the target.

**Rules for the model step.**
- Anything that learns a number from the data is fitted on the training districts only. This includes the national ratio of the baseline, any scaling and the choice of hyperparameters.
- The evaluation numbers come from cross validation. The in-sample numbers of section 7 are not performance numbers.
- Neighbouring districts are similar, so a random split may be a little optimistic. A split by federal state can test this. Not tested yet.

### Step 5: Baseline and model

**To reproduce this step, run the data pipeline first** (`uv run python -m ev_gap.pipeline`), then `uv run python -m ev_gap.model` or open `notebooks/02_model.ipynb`.

Goal: estimate how many public charging points a typical district with the same cars, residents and density has (the expected number), and report the gap of each district in percent: (actual minus expected) divided by expected.

**Models** (chosen by the author after a comparison of seven model types)

| Model | Role |
|---|---|
| Baseline ratio | Expected points = BEV divided by the BEV per charging point of the training districts |
| Linear regression on logs | Main model. Inputs: BEV, population, density. Works in percentages |
| Gradient boosting | Comparison model. Looks for curves and interactions. Small and fixed settings (200 shallow trees), not tuned |

**Evaluation.** 5-fold cross validation. Every district is predicted by a model that was trained without it, and the baseline ratio is also computed from the training districts only. A test checks that a district's own charging point count does not change its own expected value. A second evaluation holds out whole federal states, because neighbouring districts are similar.

**Results** (typical error = median of |expected minus actual| divided by actual)

| Model | Typical error, random folds | Typical error, folds by state |
|---|---|---|
| Baseline ratio | 26.6% | 28.2% |
| Gradient boosting | 22.6% | 23.9% |
| Linear regression on logs | 21.1% | 22.9% |

- The linear model has the lowest error in both schemes and on all three error measures. It beats the baseline in all 5 folds and in 10 repeated random splits (by 5.0 to 6.9 percentage points).
- Gradient boosting does not improve on it. The gap between the two (1.7 to 3.2 points in the repeated splits) is small next to the fold to fold spread of 2 to 5 points. The conclusion is "no clear gain from the flexible model".
- The two models rank the districts alike (rank correlation 0.92, 14 of the 20 most underserved districts are shared). The baseline ranks differently (rank correlation 0.82 with the linear model, 11 of 20 shared).
- Coefficients of the linear model fitted on all districts (elasticities): BEV 0.48, population 0.45, density 0.07.

**Residuals.** The model is not off in one part of the range: in 5 groups by expected points, the average log residual is between -0.02 and +0.02. The spread is wide. The middle 80% of districts lie between 34% below and 50% above their expected value.

**State pattern.** Federal states differ from what the model expects. On average the districts of Saarland are 35% below the expected value and those of Rheinland-Pfalz 24% below. Hamburg (+43%), Mecklenburg-Vorpommern (+32%) and Berlin (+27%) are above. Hamburg and Berlin are one district each. The data does not show why. The model does not know the state, so these patterns are part of the gaps. Many districts of Rheinland-Pfalz and Saarland are therefore at the top of the underserved list.

**Gaps.** 55 of 399 districts are more than 30% below their expected value and 24 are more than 40% below. The 5 districts furthest below: Kusel (-60%), Südwestpfalz (-58%), Germersheim (-54%), Wolfenbüttel (-52%), Altenkirchen (-50%). Above: Heilbronn (+157%), Oder-Spree (+151%), Ingolstadt (+147%). The gaps are written to `data/processed/gaps.csv` (out of fold expected values and gaps of all three models).

**What this does not show.**
- A typical error of about 21% is large. A gap of -20% is within normal noise. Only large gaps are worth attention.
- The model describes the current relationship. It does not show how many charging points are optimal.
- Whether a below-expected district really lacks charging points depends on things not in the data: company registrations, commuters, tourism, home charging, motorway charging.

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

1. **Sensitivity check with plug-in hybrids.** Add the plug-in hybrid count (`phev`, already loaded in the notebook) as a second feature or as a combined plug-in car count. Check whether the district ranking changes. BEV stays the main driver, because plug-in hybrids are often charged at home or at work. This is an assumption to test.
2. **Ranking and value estimate.** List of districts with the largest gap, as a percentage. Every value assumption is marked as an assumption. Because the typical model error is about 21%, only large gaps count.
3. **Prototype.** Notebook with a map (also saved as a standalone HTML file), and a small API that returns the gap for one district. A short screen recording of the demo as a backup for the presentation.
4. **Docker.** One Dockerfile for the API, written when the API works.
5. **Presentation.** 15 minutes, English.

## Extending the prototype (not built)

These are ideas for a larger version. None of them is part of the current code.

- **Experiment tracking and model registry (MLflow).** Not used here on purpose. With three models and a few variants, a results table is enough, and the time budget is small. It would pay off when there are many runs. Every run would log its settings, scores and gap table, and a new model would only replace the current one after it beats it on the same cross validation.
- **Automated data refresh.** The register is updated regularly and KBA publishes once a year. A scheduled job would download the new files, run the pipeline and stop if a totals check fails.
- **Scheduled retraining with checks.** Retrain after each new release and compare with the previous model before it goes live.
- **Monitoring.** New charging points appear every month, so the relationship between cars and charging points changes. Track the typical error and the distribution of the gaps over time.
- **Better inputs.** Registration place is a weak stand-in for where cars charge. Commuter flows, traffic counts, or the location of each charging point would give a finer unit than the district. The register has coordinates, which are not used yet.
- **Service.** The API in a container, a build and test step on every change (CI), and the processed table in a database instead of a file.

## How AI tools were used

Claude Code (Anthropic) was used in this project as a coding assistant. Per step so far:

- Step 1: web searches and page fetches to find the data sources. The KBA file was opened and read to check the BEV column.
- Step 2: the first version of the download script was written by the assistant.
- Step 3: the first version of the exploration notebook was written by the assistant. A join error (double counting of cities and Landkreise with the same name) was found while running the notebook and fixed. The check that the totals match was added because of it.
- Step 4: the pipeline modules and the 21 tests were written by the assistant, based on the logic of the notebook. The totals check reproduces the numbers of the notebook (2,031,870 BEV, 9.5 BEV per charging point). The 55 points in maintenance are the difference to the notebook's 214,453 points.
- Step 4b: the quick checks and the figures of section 7 were written by the assistant after a discussion of which insight to lead with. The assistant first judged the name matching problem to be a data quality example and not the main insight. Two chart problems (a truncated axis on the explained variation chart, a label on a reference line) were found by looking at the rendered figures and fixed.

- Step 4c: at the request of the author, the assistant reviewed every transform step for leakage, found the target-derived column `bev_per_point`, and removed it from the pipeline, the tests, the notebook and this README. The pipeline and notebook results did not change (same totals, same section 7 numbers). The tests now number 23.
- Step 5: the model code (`model.py`), 8 tests and the notebook `02_model.ipynb` were written by the assistant. The model choice (linear regression on logs as the main model, gradient boosting as the comparison, percent gap) was decided by the author after the assistant listed seven model types with arguments for and against. The assistant checked its own statement that the model fits the whole range: the plot suggested a bias at the small districts, a numeric check showed none, and the text was changed to say so. The state pattern in the residuals was found by the assistant while checking the residuals and is reported as a limitation.

The author is to complete this section: which results were reviewed or validated independently, and which decisions were taken by the author.
