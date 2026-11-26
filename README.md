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
| 5b. Plug-in hybrid sensitivity check | done |
| 6. Ranking and value estimate | done |
| 7. Prototype: map, API and page | done |
| 7a. Dockerfile for the API | done |
| 7b. Outlook model and switchable map | not built, kept as a future plan (see "Extending the prototype") |
| 8. Presentation | draft done (PowerPoint and PDF), the demo is to be added |

## Key findings (summary for the presentation)

The details and the numbers behind each point are in the step log below. Step 7 (the prototype) is not done yet, so part 4 of the list is marked as open.

**1. Problem and relevance.** Electric cars are registered where people live, and charging points are built by many different operators. A district with few charging points compared with its cars is a place where a charging operator, a municipality or a carmaker could look first. The project asks where charging points lag behind what a typical district of the same size has.

**2. Data and method.**
- Three public sources: the Bundesnetzagentur charging register (214,398 charging points in operation), the KBA car stock per Zulassungsbezirk (2,031,870 battery electric cars) and Destatis area and population per Kreis. Result: one table with 399 districts.
- The hard part was the join. The register has district names and no keys. A city and its surrounding Landkreis often share a name, and a first match that ignored this made cities such as Passau, Rosenheim and Hof look like the best supplied places in Germany. The pipeline now checks that no car, person or charging point is lost or counted twice.
- Method: the expected number of charging points per district is estimated with a linear regression on logs (inputs: electric cars, residents, density). Gradient boosting and a simple ratio serve as comparisons. Everything is evaluated with cross validation, so no district is judged by a model that has seen it. The gap is the percentage difference between actual and expected.

**3. Results.**
- Insight: charging points follow the number of residents about as much as the number of electric cars (elasticity about 0.5 each). So the plain ratio "cars per charging point" is a biased yardstick: it flags large districts partly because they are large (7.4 cars per point in the smallest third of districts, 10.0 in the largest third). This is the reason for modelling the expected number instead.
- The linear model has a typical error of 21.1% (22.9% when whole federal states are held out). The simple ratio has 26.6% (28.2%). Gradient boosting does not improve on the linear model.
- Plug-in hybrids: counting them changes neither the error nor the ranking (rank correlation 0.996 or higher). The mix of battery electric and plug-in hybrid cars is similar in all districts.
- 55 of 399 districts are more than 30% below their expected number of charging points ("clearly below"), 24 are more than 40% below. For 42 of the 55, gradient boosting agrees. Furthest below in percent: Kusel (-60%), Südwestpfalz (-58%), Germersheim (-54%), Wolfenbüttel (-52%), Altenkirchen (-50%).
- Percent and absolute numbers give different lists: only 2 of the top 15 districts by percent are also in the top 15 by missing charging points. By points, München is first (1,817 missing, -37%), then Rhein-Sieg-Kreis, Rhein-Neckar-Kreis, Euskirchen and Rhein-Erft-Kreis.
- Federal states differ systematically: districts of Saarland are on average 35% below expected, Rheinland-Pfalz 24% below. Rheinland-Pfalz and Saarland are 35% of the 55 districts but 10% of all districts. The data does not show why.
- Scale: the missing points of the 55 districts are 2,278 to reach 70% of the expected number, and 10,423 to reach the expected number. That is 0.8 and 3.5 months of the 2025 build rate (35,754 points, from the register).
- Rough value, built from assumptions (A8 to A14): closing the gap to 70% of expected needs about 27 million EUR of investment (range 21 to 54) and brings about 11 million EUR of gross revenue per year (range 4 to 23). Closing it to the expected number needs about 125 million EUR (range 98 to 249) and brings about 51 million EUR per year (range 20 to 104). Revenue is before electricity and operating cost, so it is not profit. This is an order of magnitude, not a business case.

**4. Prototype.**
- An interactive map (`reports/gap_map.html`, one file, works offline) with a drop-down for three views: gap in percent, missing charging points of the clearly below districts, and robust or not. Hovering shows the district, actual and expected charging points, gap, and both ranks. The same maps as pictures are in `reports/` for the slides.
- A small web service (FastAPI) with the gap of one district and a what-if endpoint ("how many charging points does a typical district with these numbers have?"). Inputs outside plausible ranges are rejected. The page at `/` combines the map, a district lookup and the what-if form.
- A Docker image that builds the whole project from a fresh clone and runs the service (7a).
- Not built: a second model with a switchable map. It is described as a future plan under "Extending the prototype".

**5. Business implications, limitations and next steps.**
- Business use: a ranked list of districts to look at first, in two views (percent for "who lags behind its peers", missing points for "where to build"). The reader is a charging operator, secondary a municipality. It is a screening tool: it says where to look first, not where to build. The next step would be utilization data from operators.
- The value estimate (assumptions A8 to A14) gives an order of magnitude for the investment and the gross revenue. The biggest uncertainty is how much new points would be used, which the data cannot tell.
- A typical error of about 21% means only large gaps count. A gap of -20% is noise.
- The model describes the current relationship. It does not show how many charging points are optimal.
- What the data cannot tell: where cars are really charged (company registrations, commuters, tourism, home charging), and whether plug-in hybrid owners use public charging.
- Different reference dates: cars 01.01.2026, charging points 12.11.2026, population 31.12.2024.
- Next steps for a larger version: see "Extending the prototype".

**Where the figures are:** `notebooks/01_explore_data.ipynb` (data quality, section 7 for the two insights), `notebooks/02_model.ipynb` (model comparison, residuals, state pattern, gaps), `notebooks/03_phev_sensitivity.ipynb` (plug-in hybrids), `notebooks/04_ranking_value.ipynb` (ranked lists, who is on the list, scale, value estimate), `notebooks/05_map_and_api.ipynb` (maps and API calls).

## How to run

Requirements: [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.13 or newer.

```bash
uv sync                           # create .venv and install packages
uv run python -m ev_gap.download  # download the four raw files into data/raw/ (three data files, one district shape file)
uv run python -m ev_gap.pipeline  # clean, join, write data/processed/districts.csv
uv run python -m ev_gap.model     # cross validation of the models, write data/processed/gaps.csv
uv run python -m ev_gap.ranking   # ranking and value estimate, write ranking.csv and value_scenarios.csv
uv run python -m ev_gap.mapping   # interactive map reports/gap_map.html (works offline) and two pictures
uv run uvicorn ev_gap.api:create_app --factory   # the web service, then open http://127.0.0.1:8000 (or /docs)
uv run pytest                     # run the tests
```

**To run the notebook:** open `notebooks/01_explore_data.ipynb` and select the kernel of the `.venv` in this folder. Sections 1 to 6 need only the downloaded raw files. **Section 7 needs the output of the pipeline, so run the pipeline first** (`uv run python -m ev_gap.pipeline`). Without `data/processed/districts.csv`, section 7 stops with an error that says so. The notebooks `02_model.ipynb` and `03_phev_sensitivity.ipynb` also need the pipeline output.

Running the download again is safe. Files that are already in `data/raw/` are skipped.

### Run with Docker (service only)

The service can also be run without Python or uv on the machine. Only Docker is needed.

```bash
docker build -t ev-gap .
docker run --rm -p 8000:8000 ev-gap     # then open http://127.0.0.1:8000
```

What happens in the build (two stages, see the `Dockerfile`):
1. **Build stage.** Installs the locked dependencies, downloads the data, runs the tests, the pipeline, the model, the ranking and the map. The build stops if a test fails.
2. **Runtime stage.** A slim image with the code and the finished files only: the saved model, the ranking table, the map and the reference dates of the data. It does not contain the raw data, the notebooks or the dev tools. Nothing is trained when the container starts. The service runs as a normal user and has a health check.

Good to know:
- The first build needs internet (about 60 MB of downloads) and takes a while, because it installs all packages and runs the tests and the analysis steps. Later builds reuse the cache, so they do not download again. To refresh the data, build with `--no-cache`.
- The register is updated regularly. An image built later contains newer data, and the numbers differ slightly from the ones in this README. `GET /health` shows the reference dates of the data in the image.
- The model is trained inside the build, with the same locked versions that the service runs with, so the saved model always loads.
- The image is about 960 MB. It could be made smaller by moving the packages that only the analysis needs (plotly, matplotlib) to a separate dependency group.
- The notebooks, the tests and the analysis steps are not part of the image. For these, use the virtual environment above.

Raw and processed data are not committed in either way.

## Data sources

| Source | Content | Reference date | Link |
|---|---|---|---|
| Bundesnetzagentur Ladesäulenregister | Public charging stations with number of points, power, commissioning date, district name, coordinates. CSV, about 58 MB. Licence CC BY 4.0 | 12.11.2026 | [Bundesnetzagentur](https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/E-Mobilitaet/start.html) |
| Kraftfahrt-Bundesamt, table FZ 1.2 | Passenger cars per Zulassungsbezirk by fuel type, `Elektro (BEV)` and plug-in hybrid as separate columns. XLSX | 01.01.2026 | [KBA direct file](https://www.kba.de/SharedDocs/Downloads/DE/Statistik/Fahrzeuge/FZ1/fz1_2026.xlsx?__blob=publicationFile&v=2) |
| Destatis, Kreisfreie Städte und Landkreise | Area, population (Zensus 2022 basis) and density per Kreis. XLSX | 31.12.2024 | [Destatis page](https://www.destatis.de/DE/Themen/Laender-Regionen/Regionales/Gemeindeverzeichnis/Administrativ/04-kreise.html) |

A fourth file is used only to draw the map: a [TopoJSON file of the German districts](https://github.com/AliceWi/TopoJSON-Germany) (boundaries of 2017, built from GADM data, with a five digit key per district). It is downloaded by the script and not committed, because the GADM terms limit the use to non-commercial purposes. The repository's own licence statement was not checked.

The three reference dates differ. Cars are about 10 months older than the charging points, and the population is almost 2 years older. This is a limitation of the analysis.

BEV means battery electric vehicle: a car that runs on a battery only. Plug-in hybrids (PHEV) are a separate column in the KBA table and are not part of the BEV count.

## Project structure

```
Dockerfile           two stage build: build and test everything, then a slim image that runs the service
.dockerignore        keeps local data, models and the virtual environment out of the build
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
  ranking.py         ranking of the districts and the value estimate
  geometry.py        district shapes: decode the TopoJSON file, merge four old shapes
  mapping.py         interactive map (HTML, offline) and static pictures
  api.py             the web service (FastAPI)
  web/index.html     the page with the map, a district lookup and the what-if form
models/              the saved model for the API, not committed
reports/             the map file and pictures for slides
notebooks/
  01_explore_data.ipynb   exploration only, not part of the pipeline
  02_model.ipynb          model comparison, residuals, gaps (needs the pipeline output)
  03_phev_sensitivity.ipynb   does counting plug-in hybrids change the result (needs the pipeline output)
  04_ranking_value.ipynb      ranked lists, value estimate (needs the pipeline and model output)
  05_map_and_api.ipynb        maps of the gaps and examples of the API calls (needs the output of the steps above)
tests/
  conftest.py        small made-up tables, one district per rule
  test_extract.py    layout parsing of the KBA and Destatis sheets
  test_keys.py       district key mapping
  test_transform.py  cleaning, key merges, join, totals check
  test_pipeline_integration.py   end to end on the real files (skipped if not downloaded)
  test_model.py      baseline learns from training districts only, no leakage of a district's own value, folds, gap
  test_ranking.py    sort order, threshold, robust flag, missing points, value arithmetic
  test_geometry.py   TopoJSON decoding, merged shapes, missing shapes
  test_mapping.py    map views, offline file, static picture
  test_api.py        endpoints, errors, input limits
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

The output has 12 columns: `key`, `name`, `pkw_total`, `bev`, `phev`, `area_km2`, `population`, `density`, `points_normal`, `points_fast`, `charging_points`, `plugin_cars` (BEV plus plug-in hybrids, added in step 5b). A district with no charging points gets 0. There is none in the current data. See Step 4c for why cars per charging point is not a column.

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

### Step 5b: Sensitivity check with plug-in hybrids

**To reproduce this step, run the data pipeline first** (`uv run python -m ev_gap.pipeline`), then open `notebooks/03_phev_sensitivity.ipynb`.

Question: plug-in hybrids (PHEV) can also use public charging points. Does counting them change the model, its error or the list of underserved districts?

**Variants** (linear regression on logs, same cross validation as step 5):

| Variant | Inputs | Car count of the baseline ratio |
|---|---|---|
| BEV only (main model) | BEV, population, density | BEV |
| BEV and PHEV separate | BEV, PHEV, population, density | BEV |
| Plug-in cars combined | BEV + PHEV as one number, population, density | BEV + PHEV |

The sets are defined in `config.FEATURE_SETS`. A test checks that none of them contains the target or a part of it.

**Results**

| Typical error | Random folds | Folds by state |
|---|---|---|
| BEV only | 21.1% | 22.9% |
| BEV and PHEV separate | 21.7% | 22.2% |
| Plug-in cars combined | 21.3% | 23.4% |

- The error does not improve. In 10 repeated random splits the typical error is 20.6% (BEV only), 20.7% and 20.8%. The variants with plug-in hybrids are better than BEV only in only 2 of 10 splits each, and worse by 0.1 to 0.2 percentage points on average.
- The ranking of the districts stays almost the same. The rank correlation of the gaps with the main model is 0.998 (BEV and PHEV separate) and 0.996 (combined). 18 to 20 of the 20 most underserved districts and 52 to 53 of the 55 most underserved districts are the same.
- The districts whose gap changes most are well supplied ones (Wolfsburg, Stuttgart, Ingolstadt). They stay far above their expected value.
- The simple baseline ratio improves a little when it counts plug-in cars instead of BEV (26.6% to 25.0% with random folds). Plug-in cars follow the number of residents closely, so this is probably a better stand-in for district size. This was not tested.

**Why nothing changes.** The mix of BEV and PHEV is similar in most districts: plug-in hybrids are 29% to 42% of plug-in cars in 80% of the districts (median 35%). The two counts correlate at 0.96 (logs), so they carry almost the same information. In the variant with both, the PHEV coefficient is small and negative (-0.11). Because of the strong correlation this must not be read as "plug-in hybrids reduce charging points".

**Conclusion.** The main result does not depend on whether plug-in hybrids are counted. BEV stays the main input.

**Limit.** The check shows that districts with more plug-in hybrids have about as many charging points as their BEV counts suggest. It does not show whether plug-in hybrid owners use public charging. Home and workplace charging is not in the data.

**Code changes.** The pipeline table has a new column `plugin_cars` (BEV plus PHEV). `RatioBaseline` takes the car column as a parameter. `compare_feature_sets` in `model.py` runs the baseline and the linear model for each input set. 5 new tests (36 in total).

### Step 6: Ranking and value estimate

**To reproduce this step, run the pipeline and the model first** (`uv run python -m ev_gap.pipeline`, then `uv run python -m ev_gap.model`), then `uv run python -m ev_gap.ranking` or open `notebooks/04_ranking_value.ipynb`.

**Ranking.** The gap of the linear model (out of fold) sorts the districts. A district is **clearly below** if it has more than 30% fewer charging points than expected. 30% is chosen to lie above the typical model error of about 21%. It is **robust** if gradient boosting also puts it more than 30% below. Result: 55 of 399 districts are clearly below, 42 of them robust. Together they have 10.4 million residents and 277,593 BEV (13.7% of all BEV).

**Two views, two different lists.** Only 2 of the 15 districts at the top by percent gap are also in the top 15 by missing charging points.
- By percent: small districts, many in Rheinland-Pfalz and Saarland. Kusel (-60%, 90 missing points), Südwestpfalz (-58%, 122), Germersheim (-54%, 181), Wolfenbüttel (-52%, 160), Altenkirchen (-50%, 162).
- By missing points: large districts, many in Nordrhein-Westfalen. München is 37% below expected, only rank 30 by percent, but first by missing points (1,817). Then Rhein-Sieg-Kreis (476), Rhein-Neckar-Kreis (405), Euskirchen (363), Rhein-Erft-Kreis (355).
- The percent view fits a question such as "where does a district lag behind its peers". The points view fits "where would an operator build".

**Who is on the list.** Rheinland-Pfalz and Saarland are 35% of the 55 districts and 10% of all districts. Nordrhein-Westfalen has 13 of the 55 (24%, against 13% of all districts). Bayern has 5 (9%, against 24%). The model does not know the state, so this is partly a state pattern (see step 5).

**Scale from observed data (no assumptions).** According to the register, 35,754 charging points were commissioned in 2025 (stations still in the register). The missing points of the 55 districts are 2,278 to reach the edge of the band (70% of the expected number), which is 0.8 months of the 2025 build rate. To reach the expected number, 10,423 points are missing, which is 3.5 months.

**Value estimate.** Investment and gross revenue per year for closing the gap, in two coverages (to the edge of the band, to the expected number) and three cases (low, base, high). The low case uses the low value of every assumption, the high case the high value.

| Coverage | Missing points | Investment, million EUR (low to high, base) | Gross revenue per year, million EUR (low to high, base) |
|---|---|---|---|
| To the edge of the band | 2,278 | 21 to 54 (27) | 4 to 23 (11) |
| To the expected number | 10,423 | 98 to 249 (125) | 20 to 104 (51) |

Base case per new point: 11,950 EUR investment and 4,914 EUR gross revenue per year.

**What the estimate leaves out.**
- Revenue is gross (price times energy). The cost of electricity, operation, site rent, payment fees and tax are not subtracted. It is not profit. No margin is assumed because none could be sourced.
- Investment is hardware, planning and installation. Grid expansion, battery storage, VAT and subsidies are not included. It is probably a lower bound, because the base case uses 50 kW fast chargers.
- Whether new points would be used as assumed is not known. The data has no utilization numbers per district.

The estimate is an order of magnitude. The assumptions A8 to A14 below are all guesses, partly with a source.

**Code.** `rank_districts` and `estimate_value` in `ranking.py`, the assumptions in `config.py` with their sources next to them. 11 new tests (47 in total): sort order, threshold, robust flag, state from the key, missing points, the arithmetic of the value, and that the low, base and high assumptions are ordered.

### Step 7: Prototype (map, API and page)

**To reproduce this step, run the pipeline, the model and the ranking first** (see "How to run"), then `uv run python -m ev_gap.mapping` for the map and `uv run uvicorn ev_gap.api:create_app --factory` for the service. The notebook `05_map_and_api.ipynb` shows both.

**Map.** The shapes come from a public TopoJSON file with a five digit key per district. A small decoder turns it into coordinates (`geometry.py`, with tests). Four old shapes are merged to match our districts (A15), and the code stops with an error if one of the 399 districts has no shape. The result is checked: all 399 shapes load, and their coordinates lie within Germany (longitude 5.9 to 15.0, latitude 47.3 to 55.1).

The interactive map is a plotly map without background tiles (`white-bg`), saved in one HTML file of about 6 MB that contains the plotly library. It does not load anything from the internet. A drop-down switches between three views. The colour scale of the gap is capped at -60% and +60%, and the points view at 600, so that one district (München) does not set the scale. A line under the map says that the colour is not a measure of need.

An earlier version used plotly's world map type, which can fetch map files from the internet. It was replaced by the tile-less type because offline use matters for the presentation.

**What the maps show.** The districts below expected cluster in the south-west (Rheinland-Pfalz, Saarland) and in parts of Nordrhein-Westfalen and Hessen. By missing points, München is the largest single shortfall, followed by districts around Köln.

**API.** FastAPI, started with `uvicorn ev_gap.api:create_app --factory`:

| Endpoint | Returns |
|---|---|
| `GET /districts` | all districts, for a drop-down menu |
| `GET /districts/{key}` | actual and expected charging points, gap, missing points, clearly below, robust, both ranks. The expected value is out of fold |
| `GET /expected?bev=&population=&density=` | what-if: expected charging points for these inputs, from the final model, and the typical error of the model |
| `GET /health` | status, the typical error and the reference dates of the data (charging register, KBA car stock, Destatis population, and when the pipeline ran) |
| `GET /` and `GET /map` | the page and the map |
| `GET /docs` | the automatic documentation |

Inputs are validated: for example battery electric cars must be above 0 and at most 200,000, residents between 1,000 and 5 million, density at most 20,000 per km2. Invalid values return a 422 error. A district key must have five digits (422 for a wrong format, 404 for an unknown key). The service stops at start with a clear message if the saved model or the ranking file is missing. The response carries a note that the expected number is not the number of charging points a district needs.

The final model is the linear model on logs, fitted on all 399 districts and saved with joblib in `models/` together with its typical error. In a test call, the inputs of Kusel return 150.0 expected charging points, the same as the out of fold value (150.2). Doubling the electric cars from 1,262 to 2,524 gives 209.2, not 300, because the elasticity is about 0.5.

**Page.** `GET /` shows a district drop-down with its result, a what-if form and the map in a frame. It uses no outside libraries.

**Tests.** 32 new tests (79 in total): TopoJSON decoding (arcs, reversed arcs, closed rings, merges, missing shapes), the map (views, caps, offline file, picture) and the API (endpoints, errors, ranges). A smoke test with a started server returned the expected answers for health, a district, the what-if call, the map file and the page.

### Step 8: Presentation

The talk is 15 minutes in English. The slides (PowerPoint with speaker notes, and PDF) and the script that builds them are kept locally in `reports/presentation/` and are not part of this repository. The PDF is sent separately.

**Structure.** 18 main slides (about 14 minutes by the speaker notes) and 5 appendix slides. The main part follows the five parts the brief asks for, and each slide carries a small label with its part:
1. Problem and business relevance: the problem, and who can act on the result
2. Data and method: the data, the fair yardstick, the three models and their evaluation, then how the main model works (with an example)
3. Results: the main insight, the model comparison, the state pattern, where the gaps are (map)
4. Prototype: map, API and Docker, then the demo
5. Business implications, limits and next steps: how to use the result with the value in short, then the limits and extensions

The limits slide and the summary point out home charging: in rural districts many drivers may charge at home and use public points in the cities they commute to. A rural district below expected then does not automatically need more public points. This point came from a conversation with a friend of the author. It is not checked with data.

Before part 1 come the title and an agenda, after part 5 the slide on AI tools and a summary. The appendix has the value estimate in detail, the join problem, the data issues, the value assumptions with their sources, and the engineering.

**Where the content comes from.** Every number on the slides is taken from this README, the notebooks or a call of the running service (the demo slide). The model comparison and the state chart are native, editable charts. The scatter plot and the maps are pictures from the notebooks and from `reports/`.

**Checks.** The file passes a structural validation. All slides were rendered and looked at, and layout problems were fixed (text boxes with too much empty space, a chart that drew negative bars as positive ones in the renderer, a command that wrapped over two lines). The text contains no company name and no dashes used as punctuation.

**To do.** The demo slide shows the steps and the real answers of the service. Screenshots or a screen recording of the map and the page are to be added.

### Assumptions

These are decisions made by the author. They are not confirmed by official documentation.

| Id | Assumption | Where used |
|---|---|---|
| A1 | Hanau is part of Main-Kinzig-Kreis (06435). KBA and register values for Hanau are added to it. | district key mapping |
| A2 | The city of Trier and Trier-Saarburg are one district, as in the KBA file. Population, area and charging points are summed. | district key mapping |
| A3 | A charging point counts the same, whether it is a normal or a fast charger. | target definition |
| A4 | Cars are counted by the place of registration. This is taken as the place where the cars are used and charged. | all results |
| A5 | Stations with status "In Wartung" (29 stations, 55 points) are not counted. All other stations in the register have status "In Betrieb". | `clean_register` |
| A6 | Battery electric cars are the main input. Plug-in hybrids were tested as an alternative and change nothing (step 5b). | model inputs |
| A7 | The gap is reported in percent of the expected number, not in charging points. The number of missing points is also stored, for the value estimate. | gaps |
| A8 | A district is "clearly below" if it has more than 30% fewer charging points than expected. 30% is chosen above the typical model error of about 21%. | ranking |
| A9 | New charging points have the same mix of normal and fast chargers as the existing ones (28.5% fast, observed in the register). | value estimate |
| A10 | Investment per point, without VAT and grid expansion: normal 4,000 to 7,500 EUR (base 5,750), fast 23,000 to 65,000 EUR (base 27,500). Source: [Öko-Institut, EWI, FCN, 22.07.2022](https://www.oeko.de/fileadmin/oekodoc/ENSURE-II_Ladeinfrastruktur.pdf), table 2-1, public 22 kW and 50 kW. The high value for fast points is the lower bound of the 150 kW class. The prices are from 2021 and 2022 and are not updated. | value estimate |
| A11 | Charging sessions per point and day: 0.63 (normal) and 2.5 (fast), national average 2025. Seen in a search summary of a [Statista page](https://de.statista.com/statistik/daten/studie/1467870/umfrage/auslastung-ladepunkte). The page was not opened, so the numbers are unverified. | value estimate |
| A12 | New points are used at 50%, 75% or 100% (low, base, high) of the national average. Pure assumption. | value estimate |
| A13 | Energy per session: 10 / 15 / 20 kWh (normal) and 25 / 35 / 45 kWh (fast), low / base / high. Pure assumption. | value estimate |
| A14 | Price: average ad hoc prices of July 2026, 52.3 ct per kWh (AC) and 70.5 ct (DC) ([ACE](https://www.ace.de/elektromobilitaet/laden-wallbox/ladepreise/), seen in a search summary). Drivers are assumed to pay 70%, 85% or 100% of it (low, base, high). The factors are pure assumptions. | value estimate |
| A15 | For the map, the shapes of four old districts are merged into the districts of our data: Göttingen and Osterode into Göttingen (2016), Trier-Saarburg into Trier (as in A2), Eisenach into Wartburgkreis (2021, from my own knowledge, consistent with the Destatis list). The merged shapes are drawn side by side. | map |

### Limitations known so far

- KBA counts cars by registration place. Company and leasing registrations can inflate a district.
- Through traffic, tourism and commuters are not in the data.
- The register lists only points whose notification process is complete, so it undercounts. This is stated by the Bundesnetzagentur.
- Reference dates differ between the three sources.
- Home and workplace charging is not in the data. Only public points are counted. In rural districts many drivers may charge at home and use public points in the cities they commute to (not checked with data). A rural district below expected then does not automatically need more public points.
- The typical model error is about 21%. Gaps of a few tens of percent are within noise.
- The model does not know the federal state. State wide patterns (Saarland, Rheinland-Pfalz below, Hamburg, Berlin, Mecklenburg-Vorpommern above) are part of the gaps. Their causes are not in the data.
- Neighbouring districts are similar. Evaluation by federal state tests this and gives slightly higher errors.
- The data shows whether districts with more plug-in hybrids have more charging points. It does not show whether plug-in hybrid owners use public charging.
- Gradient boosting uses small fixed settings and was not tuned.
- The two insights of step 4b are in-sample and rest on log fits. BEV and population correlate strongly (0.89), so their separate coefficients are not stable.
- The value estimate rests on assumptions A8 to A14. Investment figures are from 2021 and 2022, two figures come from search summaries and were not opened, and four are guesses. Revenue is gross, with no electricity or operating cost subtracted.
- The percent ranking favours small districts, the points ranking favours large ones. Neither says that a district needs more charging points.
- There are no utilization numbers per district. They would be the most useful missing data for a business case.
- The map shapes are from 2017 and simplified (Lake Constance is missing). They are only used for drawing. Four shapes are merged to match the data (A15).
- The what-if endpoint uses a model fitted on all 399 districts, so it has no out of fold guarantee, and it is least reliable outside the range of the real districts. The district endpoint returns the stored out of fold values.
- The interactive map and the web page are covered by automatic checks of their content. The author also opened the map file and the page of the running service in a browser.

## Planned next

1. **Demo for the presentation.** Add screenshots or a short screen recording of the map and the page to the demo slide.
2. **Final check of the presentation and the README.** The section on AI tools is to be completed by the author.

## Extending the prototype (not built)

These are ideas for a larger version. None of them is part of the current code.

- **Outlook model and a switchable map (planned, not built).** A second model, next to the unchanged gap model, that predicts how fast the battery electric car stock grows in each district. The predicted future car count would go into the gap model, and the difference between the expected charging points then and now would be the additional need if the relationship stays as it is. The map would get a layer for it. It was designed and its data was looked at, but not built, because of the time budget.
  - **Data (a brief look, not part of the project).** The KBA table used here also exists for 1 January 2021 to 2025, which gives six yearly snapshots. The Bundeswahlleiterin publishes structure data per Kreis (income, GDP, age groups, education, foreign share, housing, employment, unemployment) and the results of the European election 2024 per Kreis, with the same five digit district keys. The licence is dl-de/by-2-0. One column of the structure file, the share of electric and hybrid cars on 1 January 2023, would leak the target and must not be used.
  - **Test design.** By time, in three parts: train on the growth steps 2022 to 2023 and 2023 to 2024, choose between feature combinations on 2024 to 2025, and keep 2025 to 2026 sealed for one final check of a pre-fixed combination. Exploring the data would use the years up to 2025 only. Baselines to beat: every district grows at the national rate, and every district repeats its own last growth. If the model does not beat them, the context variables add nothing, and this is reported.
  - **Switchable map.** A model is trained once for every combination of feature groups (for example voting, income and economy, age, education, foreign share, housing), 256 small models for 8 groups. The results are stored in a standalone HTML page, checkboxes select a combination, and the map recolours without a server. The page shows the quality of the selected combination next to the map (error on the validation and the test year, and the comparison with the baselines), and marks combinations that are not better than a baseline. This is meant to prevent picking the combination that gives the nicest story. Because the best of many combinations is optimistic on the data it was chosen on, the choice is made on the validation year and only the pre-fixed default is checked on the sealed year.
  - **Caveats.** Political variables would be context variables, not causes, and a sensitive basis for any decision about where to build. National growth changed a lot between the years: the battery electric stock grew by 243,000 into 2025 and by 382,000 into 2026 (sums of the KBA tables, my own calculation). So the model should be judged on how it distributes growth across districts, with the national level as a separate scenario setting. The model would predict the growth of the car stock, not buying intentions.

- **Experiment tracking and model registry (MLflow).** Not used here on purpose. With three models and a few variants, a results table is enough, and the time budget is small. It would pay off when there are many runs. Every run would log its settings, scores and gap table, and a new model would only replace the current one after it beats it on the same cross validation.
- **Automated data refresh.** The register is updated regularly and KBA publishes once a year. A scheduled job would download the new files, run the pipeline and stop if a totals check fails.
- **Scheduled retraining with checks.** Retrain after each new release and compare with the previous model before it goes live.
- **Monitoring.** New charging points appear every month, so the relationship between cars and charging points changes. Track the typical error and the distribution of the gaps over time.
- **Better inputs.** Registration place is a weak stand-in for where cars charge. Commuter flows, traffic counts, or the location of each charging point would give a finer unit than the district. The register has coordinates, which are not used yet.
- **Regions instead of single districts.** Count the charging points of neighbouring districts as well, for example for a rural district next to a large city whose drivers commute and charge there. This could be a second input (charging points within a set distance) or a gap computed for groups of districts.
- **Service.** A build and test step on every change (CI), and the processed table in a database instead of a file.
- **Live retraining (second option for the switchable map).** The checkboxes would call the API, which retrains the outlook model on the selected features and returns new predictions. A regularised linear model on about 400 districts should take milliseconds. It needs a running server, so the standalone page would be the base.

## How AI tools were used

Claude Code (Anthropic) was used in this project as a coding assistant. Per step so far:

- Step 1: web searches and page fetches to find the data sources. The KBA file was opened and read to check the BEV column.
- Step 2: the first version of the download script was written by the assistant.
- Step 3: the first version of the exploration notebook was written by the assistant. A join error (double counting of cities and Landkreise with the same name) was found while running the notebook and fixed. The check that the totals match was added because of it.
- Step 4: the pipeline modules and the 21 tests were written by the assistant, based on the logic of the notebook. The totals check reproduces the numbers of the notebook (2,031,870 BEV, 9.5 BEV per charging point). The 55 points in maintenance are the difference to the notebook's 214,453 points.
- Step 4b: the quick checks and the figures of section 7 were written by the assistant after a discussion of which insight to lead with. The assistant first judged the name matching problem to be a data quality example and not the main insight. Two chart problems (a truncated axis on the explained variation chart, a label on a reference line) were found by looking at the rendered figures and fixed.
- Step 4c: at the request of the author, the assistant reviewed every transform step for leakage, found the target-derived column `bev_per_point`, and removed it from the pipeline, the tests, the notebook and this README. The pipeline and notebook results did not change (same totals, same section 7 numbers). The tests now number 23.
- Step 5: the model code (`model.py`), 8 tests and the notebook `02_model.ipynb` were written by the assistant. The model choice (linear regression on logs as the main model, gradient boosting as the comparison, percent gap) was decided by the author after the assistant listed seven model types with arguments for and against. The assistant checked its own statement that the model fits the whole range: the plot suggested a bias at the small districts, a numeric check showed none, and the text was changed to say so. The state pattern in the residuals was found by the assistant while checking the residuals and is reported as a limitation.
- Step 5b: the code changes, 5 new tests and the notebook `03_phev_sensitivity.ipynb` were written by the assistant, after the author approved a plan that listed the three variants. The assistant planned the check as a function in `src/` plus a short notebook. While reviewing its own notebook it found three errors and fixed them: a sentence that gave the largest difference as 0.5 points when it was 0.8, a table with a repeated column name, and a legend that covered the bars. It also added that the plug-in variants are slightly worse in 8 of 10 splits. An identical mean absolute error of two variants in one table looked suspicious. It was checked and is a coincidence of the fold averages.
- Step 6: the ranking and value code, 11 tests and the notebook `04_ranking_value.ipynb` were written by the assistant. The assistant searched for sources for the cost and revenue assumptions. A subagent could not read the PDFs, so the assistant extracted the text itself and found the cost table (table 2-1 of the Öko-Institut study). No source was found for energy per session or for a margin, so these are marked as guesses, and no margin is assumed. The reader (charging operator), the definition of the value (investment and gross revenue) and the 30% threshold were set by the assistant as defaults and accepted by the author by asking to go ahead, they were not discussed in detail. The assistant fixed unformatted labels in a figure after looking at it.

- Step 7: the geometry, map and API modules, 32 tests, the page and the notebook `05_map_and_api.ipynb` were written by the assistant. The author asked for a map with switchable layers and an API like a taxi duration service. The assistant checked the available boundary files before planning. The first file it found (GADM based, 434 districts, no key) was unusable, and the second (TopoJSON, five digit key) matched 398 of 399 keys. A test fixture of the assistant was wrong (an open ring) and was fixed. A white spot in the points map was checked by drawing a labelled zoom: it is Bonn, correctly drawn inside the Rhein-Sieg-Kreis. The assistant could not open the interactive map in a browser, replaced the plotly map type that might fetch files from the internet by a tile-less one, and stated this as a manual check. The author then opened the map file and the page of the running service in a browser. The author later asked for a second, outlook model with a switchable map (step 7b). It was designed together, and a first data step was built and tested. The author then decided, because of the time budget, not to build it. The data step was removed again, and the design is kept as a future plan under "Extending the prototype". In the design, the assistant proposed to show the model quality next to the switchable map and to choose combinations on a validation year, to prevent picking the nicest combination.
- Step 7a: the Dockerfile, the `.dockerignore`, the reference dates in `/health` and 4 new tests (83 in total) were written by the assistant. The author chose to build the data and the model inside the Docker build. The assistant noticed that the first image was 1.47 GB, which was more than its own estimate of 600 to 800 MB. It found that uv's download cache was left in the image, switched it off, and the image became 960 MB. The container was tested by starting it and calling the endpoints.
- Step 8: the slides and the script that builds them were written by the assistant, from the key findings and the step log of this README. The author asked for a PDF and a PowerPoint file. The assistant rendered all slides and looked at them, and fixed layout problems: too much empty space in several cards, a chart in which negative bars were drawn as positive ones by the renderer (found by testing small variants of the chart), and a command that wrapped over two lines. The slide about AI tools was rewritten in the author's own wording: what the assistant did, and what the author decided and validated.

The author is to complete this section: which results were reviewed or validated independently, and which decisions were taken by the author.
