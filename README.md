# EV charging gap in Germany

Where does public charging infrastructure lag behind the number of electric cars? This project combines the Bundesnetzagentur charging point register with battery electric car numbers per district, models how many charging points each district would be expected to have, and ranks the districts with the largest gap. The result shows where a charging operator, a municipality or a carmaker could look first. It is a screening list and does not measure need.

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
| 8. Presentation | done, the slides are sent separately |

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

**To run the notebook:** open `notebooks/01_explore_data.ipynb` and select the kernel of the `.venv` in this folder. Sections 1 to 6 need only the downloaded raw files. **Section 7 needs the output of the pipeline, so run the pipeline first** (`uv run python -m ev_gap.pipeline`). Without `data/processed/districts.csv`, section 7 stops with an error that says so. The notebooks `02_model.ipynb` and `03_phev_sensitivity.ipynb` also need the pipeline output, `04_ranking_value.ipynb` also the model output, and `05_map_and_api.ipynb` the output of all steps up to the map.

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

A fourth file is used only to draw the map: a [TopoJSON file of the German districts](https://github.com/AliceWi/TopoJSON-Germany) (boundaries of 2017, built from GADM data, with a five digit key per district). It is downloaded by the script and not committed.

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
  download.py        download of the four raw files (three data files, one shape file)
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
  04_ranking_value.ipynb      ranked lists and the scale of the gap (needs the pipeline and model output)
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

How the project was built, step by step.

### Step 1: Data research

All three sources exist as free downloads. KBA table FZ 1.2 has battery electric cars (`Elektro (BEV)`) per Zulassungsbezirk as its own column, stock on 01.01.2026. Other KBA tables with fuel types are only per federal state.

### Step 2: Download script

`src/ev_gap/download.py` downloads the raw files to `data/raw/`. Existing files are skipped, and each file is written under a `.part` name first, so a failed download leaves no half-written file. The register link is read from the Bundesnetzagentur page, because the date in the file name changes with each update.

### Step 3: Exploration notebook

`notebooks/01_explore_data.ipynb` looks at the raw files and tests the join.

- The register has 119,048 stations with 214,453 charging points, 28.5% of them fast chargers. A station can have several points, so points are counted, not rows.
- KBA counts 2,031,870 battery electric cars, 4.11% of all passenger cars.
- Nationally there are 9.5 BEV per public charging point. Across districts the ratio ranges from 2.9 to 29.8 (median 9.8).
- BEV and charging points rise together (correlation of the logs 0.88), so a regression model is reasonable.

**Data issues found**

1. The register CSV has 10 lines of notes before the header, uses `;` as separator and a decimal comma, and is encoded in `cp1252`.
2. The register has district names, not keys. Matching on the name alone counted points twice for a city and a Landkreis with the same name (Passau, Rosenheim, Hof). These cities then looked like the best supplied places in Germany. The match now uses the type (city or rural district) together with the name.
3. KBA and Destatis differ in two places: Hanau (its own district at KBA) and Trier with Trier-Saarburg (merged at KBA). See A1 and A2.
4. 29 stations are "In Wartung", one coordinate lies outside Germany, and 231 stations report more than 400 kW. This is likely a station total for fast charging hubs. Not verified.

### Step 4: Cleaning pipeline (ETL)

`uv run python -m ev_gap.pipeline` reads the raw files, cleans them, maps the district keys and writes one row per district to `data/processed/districts.csv`.

- **ETL, not ELT.** The data is small and there is no warehouse. The hard parts (the Excel layout of the KBA file, matching free text names to official keys) are easier to write and test in pandas than in SQL.
- **Structure.** `extract.py` handles the file quirks, `keys.py` the key mapping, `transform.py` the cleaning and the join. The transform functions take and return DataFrames, so the tests use small made-up tables.
- **Totals check.** `check_totals` stops the pipeline if the join loses or double counts any car, resident or charging point.

Result: 399 districts, 2,031,870 BEV and 214,398 charging points (153,286 normal, 61,112 fast). The 55 points at stations in maintenance are not counted.

### Step 4b: Two insights from the data

Notebook 01, section 7. It needs the pipeline output. Straight lines fitted on log values, in-sample.

| Explaining charging points with | Elasticity | Share of variation explained (R²) |
|---|---|---|
| BEV only | 0.84 | 0.78 |
| Population only | 1.00 | 0.76 |
| BEV and population | 0.49 for BEV, 0.48 for population | 0.81 |

1. **Charging points follow residents about as much as electric cars.** With both inputs, each carries about half of the effect.
2. **The plain ratio "cars per charging point" is biased against large districts.** Points grow slower than cars (slope 0.84), so the ratio is 7.4 BEV per point in the smallest third of districts and 10.0 in the largest third.

A ranking by the plain ratio would flag large districts partly because they are large. This is the reason to model the expected number of points. BEV and population correlate at 0.89, so the split between them is rough.

### Step 4c: Leakage review

Every transform step was checked for leakage. No step learns a number from the data, so none has to move behind the train and test split. One problem was found and fixed: a column `bev_per_point` contained the target and was removed. `config.py` lists the target and the allowed inputs (`bev`, `population`, `density`), and tests check that no input is built from the target. Anything learned from the data, such as the national ratio of the baseline, is fitted on the training districts only.

### Step 5: Baseline and model

`uv run python -m ev_gap.model` or `notebooks/02_model.ipynb`. The model estimates how many public charging points a typical district with the same cars, residents and density has. The gap is (actual minus expected) divided by expected.

| Model | Role | Typical error, random folds | Typical error, folds by state |
|---|---|---|---|
| Baseline ratio | BEV divided by the BEV per point of the training districts | 26.6% | 28.2% |
| Gradient boosting | Comparison, 200 shallow trees, not tuned | 22.6% | 23.9% |
| Linear regression on logs | Main model, inputs BEV, population, density | 21.1% | 22.9% |

Typical error = median of |expected minus actual| divided by actual, from 5-fold cross validation. Every district is predicted by a model that did not see it. The second scheme holds out whole federal states.

- The linear model beats the baseline in all 5 folds and in 10 repeated splits, by 5.0 to 6.9 percentage points. Gradient boosting brings no clear gain and ranks the districts alike (rank correlation 0.92).
- Elasticities of the final model: BEV 0.48, population 0.45, density 0.07.
- No bias by size: in 5 size groups the average log residual lies between -0.02 and +0.02. The middle 80% of districts lie between 34% below and 50% above their expected value.
- State pattern: districts of Saarland are on average 35% below expected, Rheinland-Pfalz 24% below. Hamburg (+43%), Mecklenburg-Vorpommern (+32%) and Berlin (+27%) are above. The model does not know the state, so this pattern stays in the gaps. The causes are not in the data.

### Step 5b: Plug-in hybrids

`notebooks/03_phev_sensitivity.ipynb`. Plug-in hybrids were added as a separate input, or counted together with BEV. Neither lowers the error (21.1% for BEV only, 21.7% and 21.3% with plug-in hybrids) or changes the ranking (rank correlation 0.996 or higher). The share of plug-in hybrids is similar in most districts (median 35% of plug-in cars), so the two counts carry almost the same information. BEV stays the main input.

### Step 6: Ranking and value estimate

`uv run python -m ev_gap.ranking` (ranking and value estimate) or `notebooks/04_ranking_value.ipynb` (ranking only).

- **Clearly below:** more than 30% fewer charging points than expected, which lies above the typical error of 21%. **Robust:** gradient boosting agrees. 55 of 399 districts are clearly below, 42 of them robust.
- **Two views.** By percent, small districts lead: Kusel (-60%), Südwestpfalz (-58%), Germersheim (-54%), Wolfenbüttel (-52%), Altenkirchen (-50%). By missing points, large ones lead: München (1,817 missing, -37%), Rhein-Sieg-Kreis (476), Rhein-Neckar-Kreis (405), Euskirchen (363), Rhein-Erft-Kreis (355). Only 2 districts are in the top 15 of both lists.
- **Who is on the list.** Rheinland-Pfalz and Saarland are 35% of the 55 districts and 10% of all districts.
- **Scale.** 2,278 points are missing to reach 70% of the expected number, and 10,423 to reach the expected number. That is 0.8 and 3.5 months of the 2025 build rate (35,754 points, from the register).

**Value estimate** (assumptions A9 to A14). Low and high case use the low and high value of every assumption.

| Coverage | Missing points | Investment, million EUR (low to high, base) | Gross revenue per year, million EUR (low to high, base) |
|---|---|---|---|
| To 70% of expected | 2,278 | 21 to 54 (27) | 4 to 23 (11) |
| To the expected number | 10,423 | 98 to 249 (125) | 20 to 104 (51) |

Revenue is gross (price times energy) and is not profit. Investment leaves out grid expansion, VAT and subsidies. Whether new points would be used as assumed is not known. The estimate is an order of magnitude.

### Step 7: Prototype (map, API and page)

`uv run python -m ev_gap.mapping`, `uv run uvicorn ev_gap.api:create_app --factory`, or `notebooks/05_map_and_api.ipynb`.

- **Map.** One HTML file of about 6 MB that works offline (`reports/gap_map.html`), with a drop-down for three views: gap in percent, missing points, robust or not. The shapes come from a TopoJSON file with five digit keys. Four old shapes are merged to match the data (A15). The colour scale is capped so that München does not set it.
- **API (FastAPI).**

| Endpoint | Returns |
|---|---|
| `GET /districts` | all districts, for a drop-down menu |
| `GET /districts/{key}` | actual and expected charging points, gap, missing points, clearly below, robust, both ranks. The expected value is out of fold |
| `GET /expected?bev=&population=&density=` | what-if: expected charging points for these inputs, and the typical error of the model |
| `GET /health` | status, the typical error and the reference dates of the data |
| `GET /` and `GET /map` | the page and the map |
| `GET /docs` | the automatic documentation |

- Inputs are validated: invalid values return 422, an unknown district key 404. The what-if endpoint uses the linear model fitted on all 399 districts. The inputs of Kusel return 150.0 expected points. With twice the cars it returns 209.2, because the elasticity is about 0.5.
- **Page.** `GET /` shows a district lookup, a what-if form and the map.

### Step 7a: Docker

See "Run with Docker". The build stage runs the 83 tests and all analysis steps. The runtime stage holds only the finished files. The image is about 960 MB.

### Step 8: Presentation

A 15 minute talk in English. The slides are sent separately and are not part of this repository.

## Assumptions

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
| A15 | For the map, the shapes of four old districts are merged into the districts of our data: Göttingen and Osterode into Göttingen (2016), Trier-Saarburg into Trier (as in A2), Eisenach into Wartburgkreis (2021, from the author's knowledge, consistent with the Destatis list). The merged shapes are drawn side by side. | map |

## Limitations

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

## Extending the prototype (not built)

These are ideas for a larger version. None of them is part of the current code.

- **Outlook model and a switchable map (planned, not built).** A second model, next to the unchanged gap model, that predicts how fast the battery electric car stock grows in each district. The predicted future car count would go into the gap model, and the difference between the expected charging points then and now would be the additional need if the relationship stays as it is. The map would get a layer for it. It was designed and its data was looked at, but not built, because of the time budget.
  - **Data (a brief look, not part of the project).** The KBA table used here also exists for 1 January 2021 to 2025, which gives six yearly snapshots. The Bundeswahlleiterin publishes structure data per Kreis (income, GDP, age groups, education, foreign share, housing, employment, unemployment) and the results of the European election 2024 per Kreis, with the same five digit district keys. The licence is dl-de/by-2-0. One column of the structure file, the share of electric and hybrid cars on 1 January 2023, would leak the target and must not be used.
  - **Test design.** By time, in three parts: train on the growth steps 2022 to 2023 and 2023 to 2024, choose between feature combinations on 2024 to 2025, and keep 2025 to 2026 sealed for one final check of a pre-fixed combination. Exploring the data would use the years up to 2025 only. Baselines to beat: every district grows at the national rate, and every district repeats its own last growth. If the model does not beat them, the context variables add nothing, and this is reported.
  - **Switchable map.** A model is trained once for every combination of feature groups (for example voting, income and economy, age, education, foreign share, housing), 256 small models for 8 groups. The results are stored in a standalone HTML page, checkboxes select a combination, and the map recolours without a server. The page shows the quality of the selected combination next to the map (error on the validation and the test year, and the comparison with the baselines), and marks combinations that are not better than a baseline. This is meant to prevent picking the combination that gives the nicest story. Because the best of many combinations is optimistic on the data it was chosen on, the choice is made on the validation year and only the pre-fixed default is checked on the sealed year.
  - **Caveats.** Political variables would be context variables, not causes, and a sensitive basis for any decision about where to build. National growth changed a lot between the years: the battery electric stock grew by 243,000 into 2025 and by 382,000 into 2026 (sums of the KBA tables, own calculation). So the model should be judged on how it distributes growth across districts, with the national level as a separate scenario setting. The model would predict the growth of the car stock, not buying intentions.

- **Experiment tracking and model registry (MLflow).** Not used here on purpose. With three models and a few variants, a results table is enough, and the time budget is small. It would pay off when there are many runs. Every run would log its settings, scores and gap table, and a new model would only replace the current one after it beats it on the same cross validation.
- **Automated data refresh.** The register is updated regularly and KBA publishes once a year. A scheduled job would download the new files, run the pipeline and stop if a totals check fails.
- **Scheduled retraining with checks.** Retrain after each new release and compare with the previous model before it goes live.
- **Monitoring.** New charging points appear every month, so the relationship between cars and charging points changes. Track the typical error and the distribution of the gaps over time.
- **Better inputs.** Registration place is a weak stand-in for where cars charge. Commuter flows, traffic counts, or the location of each charging point would give a finer unit than the district. The register has coordinates, which are not used yet.
- **Regions instead of single districts.** Count the charging points of neighbouring districts as well, for example for a rural district next to a large city whose drivers commute and charge there. This could be a second input (charging points within a set distance) or a gap computed for groups of districts.
- **Service.** A build and test step on every change (CI), and the processed table in a database instead of a file.
- **Live retraining (second option for the switchable map).** The checkboxes would call the API, which retrains the outlook model on the selected features and returns new predictions. A regularised linear model on about 400 districts should take milliseconds. It needs a running server, so the standalone page would be the base.

## How AI tools were used

Claude Code (Anthropic) was used as a coding assistant. It helped write the pipeline, the models, the tests, the notebooks, the map, the API, the Dockerfile and this README.

**What the author decided and validated.**
- The question, the scope, and what to leave out for time (MLflow, the outlook model).
- The models: linear regression on logs as the main model, gradient boosting as the comparison, and the gap in percent.
- The extra checks: the leakage review, the plug-in hybrid test and the evaluation by federal state.
- Validation: the author ran the tests and the pipeline, checked the numbers, and opened the map and the service in a browser.
