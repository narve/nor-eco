# Plan: «Norsk statsøkonomi – fra kildene» (static site, nor-eco)

## Context
The user is dissatisfied with how media report on the Norwegian state economy. The goal is a static website in Norwegian (bokmål) that presents three topics using **only official sources**, where every number has a citation:

1. **Statsbudsjettet**: income and expenses, with and without petroleum revenue.
2. **Statens/nasjonens økonomi**: BNP and exports, with and without oil and gas.
3. **Sysselsetting**: what actually counts as «sysselsatt» (uføre, students, tiltak, sick leave …), and how many people work for the state, directly and indirectly.

The repo `/home/narve/code/nor-eco` is empty (no commits). Implementation will be done by a multi-agent workflow afterwards, so the plan is split into workstreams that can run in parallel.

Decisions so far: language is Norwegian (bokmål). Data comes from fetch scripts into versioned data, then a static build. Hosting is GitHub Pages, with the user's VPS as fallback; the output is plain static files, so both work. The time span is 2000 to present where comparable. Showing fewer years, or only the latest year, is acceptable when the history is hard to get or the series break. «BA» means statsforetak and særlovsselskap. Indirect state employment covers all four rings: state-owned companies, the municipal sector, publicly funded private actors, and subsidised work programs (tiltak).

## Guiding principles (apply to every workstream)
- **Every displayed number traces to a source record.** No number is typed into a template by hand. Numbers come from `data/processed/*.json`, and each one carries `source_ids`.
- **Three levels of claim, marked visually:**
  - *Offisielt tall*: published as-is.
  - *Utledet*: our own arithmetic on official numbers, with the formula shown.
  - *Estimat*: our own method with assumptions. Shown with a dashed or hatched style and a method note.
- **Raw snapshots are kept.** Each fetch stores the raw response with the retrieval date, so a number can be reproduced even after the source revises it. Store `vintage` (publication date) separately from `retrieved` date.
- **Definitions are explicit.** Each chart has a «Hva telles?» box with the official definition, quoted and cited.
- **Neutral tone.** Each page gets a «Vanlige misforståelser» section that contrasts common claims with the definitions. It contains no political conclusions.
- Licences: SSB data is CC BY 4.0, regjeringen.no and NAV use NLOD. The site credits them per page and in the source list.

## Tech stack
- **Python 3.12 + uv**, with a minimal set of dependencies: `httpx`, `pyyaml`, `jinja2`, `openpyxl` (for Excel files from regjeringen and NAV), `pypdf` (fallback for tables only published as PDF), and `pytest`.
- **SSB data** comes from the PxWebApi via JSON-stat2. Use **API v2** (`https://data.ssb.no/api/pxwebapi/v2/`) if it is live, otherwise v0; verify at start. Write one shared helper, not a fetcher per table.
- **Templates:** Jinja2 renders to `site/`. No JS framework.
- **Charts:** d3 v7 (including d3-hierarchy and d3-sankey) for the hierarchical and flow views, and Observable Plot for the simple time series. Both are **vendored** into `site/assets/vendor/` at pinned versions, so there are no CDN dependencies on GitHub Pages. A small in-house view library (`assets/js/views/`) has one module per view type. Every module takes the same data contract (see «Datamodell for drill-down»). Each chart also gets a `<table>` fallback (accessibility, and the numbers can be copied) and a «Kilde:» line under it.
- **Deploy:** a GitHub Action builds and publishes `site/` to Pages. A second Action runs a scheduled monthly re-fetch and opens a PR when data changes. The VPS fallback is an rsync of `site/`.

## Repo layout
```
nor-eco/
  README.md                 # purpose, how to rebuild, source policy
  pyproject.toml
  sources/registry.yaml     # ALL sources: id, publisher, title, url, table_id, licence, notes
  definitions/*.yaml        # quoted official definitions with source_id (used in «Hva telles?» boxes)
  fetch/
    common.py               # http + caching, raw snapshot writer, JSON-stat2 parser, source record helper
    ssb.py                  # generic PxWeb fetch by table id + query
    regjeringen.py          # Gul bok / statsbudsjettet Excel downloads
    nav.py                  # NAV statistics (Excel/CSV/API)
    nbim.py, eierberetning.py, misc.py
  transform/
    budget.py  economy.py  employment.py  state_employment.py
  data/
    raw/<source_id>/<retrieved-date>.<ext>   # immutable snapshots (git-tracked; large ones LFS or gitignored + hash)
    processed/<topic>/<series>.json          # {series, unit, values[], source_ids[], derivation?, claim_level, notes}
  site_src/
    templates/ (base.html, page partials, chart macro, citation macro)
    pages/ index, statsbudsjett, okonomi, sysselsetting, staten-som-arbeidsgiver, begreper, kilder, metode
    assets/ css, js/charts.js, vendor/
  build.py                  # processed data + templates -> site/
  tests/                    # schema, consistency, reconciliation, link checks
  .github/workflows/ build-deploy.yml, refresh-data.yml
```

**Processed series schema**, defined in WS0 and used everywhere:
```json
{ "id": "budget.oljekorrigert_underskudd", "title": "...", "unit": "mrd. kr", "price_basis": "løpende|faste-2024",
  "claim_level": "offisiell|utledet|estimat", "derivation": "A - B (se metode)",
  "source_ids": ["fin-gulbok-2026", "ssb-12163"], "values": [{"period":"2024","value":...,"status":"regnskap|vedtatt|anslag"}],
  "notes": "...", "breaks": [{"period":"2017","note":"ny kontoplan"}] }
```

## Datamodell for drill-down (multiple hierarchies over the same data)
The main goal is to present the data **correctly**, and to let the reader choose how to look at it. That is why the data is stored as a **tidy fact table with dimensions**, not as ready-made charts:

```
data/processed/<topic>/<dataset>/
  facts.csv        # period, value, unit, status, <dim1_code>, <dim2_code>, ..., source_id
  dimensions.yaml  # per dimension: hierarchy of codes -> label, parent, definition, source_id
  dataset.yaml     # title, total, claim_level, allowed hierarchies, valid aggregations, notes
```

- A **dimension** is one way of splitting the data, for example *formål (COFOG)*, *forvaltningsnivå*, *art* or *kapittel/post*. Each dimension is a tree, so drill-down follows the tree.
- **The reader can switch dimension at any node.** Example: Helse → (by forvaltningsnivå) stat/helseforetak, fylke, kommune → (by funksjon) behandling, forebygging, forskning, administrasjon. The breadcrumb shows the path, for example «Utgifter › Helse [formål] › Spesialisthelsetjenesten [nivå] › …».
- **Each node sums to its parent.** If the source doesn't cover the whole parent, the gap is an explicit node, «Øvrig / ikke fordelt i kilden». It is never hidden.
- **Different sources mean different totals.** Statsbudsjettet (kapittel/post), offentlig forvaltning by COFOG (SSB) and the helseregnskapet (SHA: funksjon × tjenesteyter × finansiering) don't measure the same thing. They become separate datasets that are linked through a **reconciliation bridge**: a waterfall from total A to total B with named differences. This is central to «correct» presentation, because media often mix these totals.
- **Units are computed at view time** from the same facts: kr (løpende), kr (faste priser), % of total, % of BNP / BNP Fastland, per innbygger, per sysselsatt, or «av hver 100-lapp».
- **The URL holds the view state** (`?view=treemap&path=utg/07/nivå:stat&unit=per_innb&år=2025`). Every view can then be linked and cited exactly. The view also has a «Last ned data (CSV)» button for the current node.

**Planned drill-down dimensions per dataset** (WS1–4 verify which ones exist in the sources):
| Dataset | Dimensions |
|---|---|
| Statens utgifter (budsjett/regnskap) | programområde → kapittel → post; art (lønn/drift, overføring til kommuner, til husholdninger, investering, utlån/kapital); departement |
| Offentlige utgifter etter formål | COFOG 10 hovedområder → undergrupper; forvaltningsnivå (stat, helseforetak, fylke, kommune, trygd) |
| Helseutgifter | SHA funksjon (kurativ, rehabilitering, langtidspleie, forebygging, legemidler, administrasjon) × tjenesteyter (sykehus, kommunal omsorg, fastlege …) × finansiering (stat, kommune, egenbetaling); FoU helse from SSB FoU-statistikk |
| Statens inntekter | petroleum (skatt, SDØE, utbytte) vs ikke-petroleum (MVA, inntektsskatt, arbeidsgiveravgift, særavgifter …); skattyter type (personer, foretak) |
| BNP / eksport | næring (petroleum, industri, tjenester …); vare/tjeneste; mottakerland/region |
| Befolkning og sysselsetting | status (sysselsatt/ledig/utenfor) → undergrupper; alder; kjønn; definisjon (AKU / register / NAV); personer vs årsverk |
| Statlig sysselsetting | ring (1–7) → organisasjon/selskap; eierandel; Norge vs utland; personer vs årsverk |

## Visualiseringsalternativer (same data, several views; **all are implemented**)
The full catalogue, with drill-down behaviour, honesty risks and how to mitigate them, unit handling, mobile behaviour and complexity for each view, is in **`docs/VISUALIZATIONS.md`**. A background Fable agent drafted it. It has 35 views over 7 data types, built from 14 shared modules. Every topic page gets a «Vis som»-switcher, and `site/galleri/` shows all views side by side with the same data. The user then picks which views to keep, improve or remove (`site_src/views.yaml`).

Type: S = snapshot (single year), T = timeline, S/T = both. Size: S/M/L is implementation effort. ★ = proposed default view.

| Data type | Views (id: type, size) |
|---|---|
| 1. Statens utgifter | ★`utg-hier-bars` S/T,S · `utg-treemap` S,M · `utg-sunburst` S,M · `utg-icicle` S,M (shows mixed dimensions per node) · `utg-streamgraph` T,M · `utg-bump` T,S |
| 2. Inntekter med/uten petroleum | ★`innt-waterfall` S,M (inntekter → oljekorrigert → strukturelt underskudd vs 3 % SPU) · `innt-stacked-bars` S/T,S · `innt-timeline-gap` T,S · `innt-donut-pair` S,S · `innt-slope` T,S |
| 3. Pengestrømmer | ★`flow-sankey` S,L (gjennomstrømning as a separate ribbon) · `flow-waterfall-year` S,M · `flow-alluvial-time` T,L · `flow-stacked-timeline` T,S · `flow-receipt` S,M (kvittering per innbygger) |
| 4. Makro med/uten olje og gass | ★`makro-bnp-lines` T,S · `makro-export-stacked` T,S (handelsbalanse uten petroleum, diverging) · `makro-marimekko` S,M · `makro-spu-vs-bnp` T,S · `makro-donut-pair` S,S |
| 5. Befolkning og sysselsetting | ★`bef-waffle` S,M (definition toggle AKU/register/NAV; striped cells for overlaps) · `bef-euler` S,L (Euler ≤3 sets, otherwise UpSet) · `bef-sankey-status` S,L · `bef-stacked-timeline` T,S · `bef-dot-units` S,M · `bef-slope-persons-aarsverk` S,S |
| 6. Statlig sysselsetting | ★`ssys-cumulative-bars` S,S (ring checkboxes) · `ssys-rings` S,M (hero illustration, containment for helseforetak) · `ssys-waffle` S,S (partial cells = ownership share) · `ssys-timeline` T,M · `ssys-marimekko-eier` S,M |
| 7. Avstemming mellom kilder | ★`rec-bridge-waterfall` S,M (residual «ikke forklart» always visible) · `rec-parallel-bars` S,S · `rec-sankey-bridge` S,M · `rec-timeline-gap` T,S · `rec-euler-defs` S,M |

**Shared modules** (`assets/js/views/`):
`hier-bars` · `treemap` · `sunburst` (also donut) · `icicle` · `sankey` · `waterfall` · `waffle`/`unit-dots` · `timeseries` (line/area/stacked/100 %/diverging/bump, break markers, hatched budget years) · `small-multiples` · `slope` · `marimekko` · `euler-upset` · `rings` · `receipt`.

Each module takes `{node, dim, year, unit, status, claimStyle}` and emits `drill(path)` / `switchDim(path, dim)`, so views are interchangeable at any node.

**Shared controls:**
- breadcrumb with a dimension dropdown for each node, plus «Vis som»
- year picker/scrubber (regnskap vs vedtatt/anslag marked)
- status toggle (vedtatt/saldert/regnskap)
- unit selector (disabled where meaningless)
- definition selector (AKU/register/NAV, brutto/netto, full/eierandelsvektet, Norge/inkl. utland)
- claim-level legend + «skjul estimater»
- source footer + «vis tallene» table with CSV
- «Øvrig» always visible
- shared registry of break/reform markers
- permalink
- compare mode (pin a second year or source)
- a11y: keyboard, aria, palette safe for colour blindness, reduced motion

**Implementation order within WS5a:**
1. The S modules (`hier-bars`, `timeseries`, `slope`, `waffle`), which give every data type at least one working view quickly.
2. The M modules (`treemap`, `sunburst`, `icicle`, `waterfall`, `marimekko`, `rings`, `receipt`).
3. The L modules (`sankey` with keyed transitions, `euler-upset`).


## Tema (subtle, slightly futuristic; matches narve.github.io)
Taken from the CSS of https://narve.github.io, so the look is the same:
- **Fonts:** Space Grotesk (400/500/600) for body text and headings, JetBrains Mono (400/500) for labels, numbers, breadcrumbs, source lines and «mono» captions in uppercase with letter-spacing 0.08em. Both are **self-hosted woff2** files (SIL OFL) in `assets/fonts/`, with no Google dependency.
- **Tokens:** these are the same in `:root`. Dark is the default, and light comes from `prefers-color-scheme: light`, plus a manual toggle via `data-theme`.
  - Dark: `--bg #07090d`, `--bg-card rgba(18,24,33,.72)`, `--line rgba(120,200,230,.12)`, `--line-strong rgba(120,200,230,.32)`, `--text #d6dde6`, `--muted #7d8a99`, `--accent #6fd6e8`, `--accent-2 #b59cff`, `--grid rgba(111,214,232,.045)`, `--glow rgba(111,214,232,.08)`
  - Light: `--bg #f3f5f8`, `--text #18202b`, `--muted #5b6776`, `--accent #0b7f95`, `--accent-2 #6a4fd1`, and so on, exactly as on that site.
- **Effects, used sparingly:**
  - a 40px grid in the background, with a radial glow at the top
  - cards with a blurred background, a thin border, and corner brackets in the accent colour
  - h2 headings with a gradient line after them
  - a pulsing status dot in the header
  - the gradient accent → accent-2 on a key word in h1
- **Numbers in charts and key figures** are set in JetBrains Mono with `font-variant-numeric: tabular-nums`, in Norwegian format (`1 234,5 mrd. kr`).
- **Chart palette:**
  - The categorical palette builds on accent (cyan) and accent-2 (violet), with a few extra hues tested for colour blindness and contrast in both themes. Use the `dataviz` skill's validator.
  - Petroleum vs non-oil always gets the same pair of colours across all pages.
  - Claim levels: *offisiell* is solid, *utledet* is solid with a «ƒ» marker, and *estimat* is hatched or dashed.
- **Restraint:** the effects must never compete with the data. The plot area has no glow and no 3D, and the gridlines in charts use `--line`. Animation is only for drill-down transitions (≤300ms) and is turned off with `prefers-reduced-motion`.
- No tracking by default. The GoatCounter snippet from narve.github.io is only added if the user wants it.

## Pages and content

### 1. `index.html`: Oversikt
Key figures for the latest year, one tile per topic, each linking to its page. Includes a short explanation of the source policy and of the three claim levels.

### 2. `statsbudsjett.html`: Statsbudsjettet
- Total income and expenses for the state budget and statsregnskapet. Shows **vedtatt / saldert / regnskap** clearly, because media often mix budget figures with accounts.
- **With and without petroleum:**
  - petroleum revenue (skatt, SDØE, Equinor-utbytte), together forming «statens netto kontantstrøm fra petroleumsvirksomheten»
  - non-oil income
  - **oljekorrigert underskudd** and **strukturelt oljekorrigert underskudd**
  - the transfer from SPU (fondsuttaket)
- **Handlingsregelen:** the fund withdrawal as % of SPU (the 3% path), and the structural deficit as % of trend-BNP for Fastlands-Norge.
- **Expenses by main area**: folketrygden (pensjon, uføre, AAP, sykepenger …), helse, rammetilskudd to kommuner, utdanning, forsvar, samferdsel, and so on. Show «gjennomstrømning» separately: lending, capital injections and Statens pensjonsfond flows, which inflate the gross totals.
- Optional: general government according to the national accounts (SSB offentlig forvaltning) as an internationally comparable view, with a box explaining why it differs from statsbudsjettet.
- Candidate sources: Prop. 1 S Gul bok, Nasjonalbudsjettet (Meld. St. 1), Revidert nasjonalbudsjett, Statsregnskapet (Meld. St. 3), the «Statsbudsjettet i tall» Excel files on regjeringen.no, and SSB tables for offentlig forvaltningens inntekter og utgifter. The agent must verify table ids.

### 3. `okonomi.html`: Norges økonomi med og uten olje og gass
- BNP vs **BNP Fastlands-Norge**: nominal, real growth, and per capita. Show the petroleum share of BNP over time.
- **Exports:** total vs exports excluding crude oil and natural gas (and pipeline transport), split into goods and services. Show the trade balance with and without petroleum. Optionally the current account balance.
- **SPU:** market value, a breakdown of returns vs inflows vs currency effects, and value per capita.
- The state's net cash flow from petroleum activities (linked to the budget page).
- Candidate sources: SSB nasjonalregnskap (annual and quarterly), SSB utenrikshandel med varer and tjenester, NBIM annual reports and key figures, norskpetroleum.no (Energidepartementet/Sokkeldirektoratet), Norges Bank.

### 4. `sysselsetting.html`: Hva betyr «sysselsatt»? (core page)
- **«Befolkningsregnskap»:** a waterfall or sankey for the population aged 15–74 (and 20–66). Population splits into the labour force and those outside it. The labour force splits into employed and unemployed.
  - **The employed are split into:** full-time and part-time, temporarily absent (sick leave, parental leave, holiday, permitted), on **tiltak with wages**, students with jobs, and uføre or AAP recipients with partial work.
  - **Those outside are split into:** students, uføretrygdede, AAP, retirees, homemakers, others.
- **Comparison of definitions:** AKU (ILO: ≥1 hour of paid work in the reference week, includes the temporarily absent) vs register-based employment (a-ordningen) vs NAV's registered unemployment vs AKU unemployment. Explain why the numbers differ.
- **Hours and FTE:** sysselsatte persons vs **årsverk** and hours worked (nasjonalregnskapet). This shows how part-time work and absence change the picture.
- Number of people on health-related benefits (uføre, AAP, sykepenger) over time.
- Tiltak participants by type: those counted as employed, as unemployed, or as outside the labour force.
- Candidate sources: SSB AKU, SSB registerbasert sysselsetting, SSB nasjonalregnskap (timeverk/årsverk), NAV statistikk (helt ledige, arbeidssøkere på tiltak, AAP, uføretrygd, sykefravær), and SSB/NAV analyses of uføre in work. Use the definitions as stated in SSB's «Om statistikken».

### 5. `staten-som-arbeidsgiver.html`: Hvor mange jobber for staten?
Concentric rings, each counted separately and shown with an accumulated total. Duplicates are marked explicitly.
1. **Statsforvaltningen**: departements, directorates, universities, police, defence, and so on (SSB sector «statsforvaltningen», DFØ's statistics on statsansatte).
2. **Helseforetakene (RHF/HF)**: SSB counts these in statsforvaltningen, so show them as a sub-ring to avoid double counting.
3. **Statsforetak (SF) and særlovsselskap**: Statkraft SF, Statnett SF, Avinor, Bane NOR SF, Enova SF, and others. Employee counts come from **Statens eierberetning** (NFD) and the companies' annual reports.
4. **Wholly state-owned AS** (Vy, Posten Bring, …) and **partly state-owned ASA** (Equinor, Telenor, Kongsberg, Hydro, DNB …). Show the full employee count and an *estimat* weighted by ownership share. Show the Norwegian share vs the global group where available, because e.g. Equinor and Telenor have many employees abroad.
5. **Kommunesektoren**: kommuner and fylkeskommuner (SSB), with the share of their income from state transfers (rammetilskudd and earmarked grants).
6. **Publicly funded private actors** (*estimat*): private kindergartens, private schools, private and non-profit health and care providers on public contract, and so on. Sources: SSB barnehagestatistikk, Udir/GSI, SSB «Statistikk om helse- og omsorgstjenester», and SSB tables by sector and ownership. Any assumptions are shown openly.
7. **Subsidised work programs**: NAV tiltak with wage subsidies, VTA/varig tilrettelagt arbeid, and so on (NAV).
- Also SSB's own figures for employees in offentlig sektor vs offentlig eide foretak (sector statistics), as a reference point.
- Both employed **persons** and **årsverk** where available.
- Shares of all employed people for each ring, cumulatively.

### 6. `begreper.html`, `kilder.html`, `metode.html`
- `begreper.html`: a glossary built from `definitions/*.yaml`.
- `kilder.html`: generated from `sources/registry.yaml`. Each source has its publisher, URL, table id, retrieval date, licence, and the pages that use it.
- `metode.html`: all derivations and estimates, known breaks in the series, and choices such as nominal vs real values and how double counting is avoided.

## Workstreams (for the multi-agent workflow)
| WS | Content | Depends on |
|----|---------|-----------|
| **WS0 Fundament** | Repo layout, `pyproject`, the series schema plus validator, `fetch/common.py` (snapshots, JSON-stat2 parser, SSB API v2/v0 check), `build.py` skeleton, base template, chart and citation macros, vendored Plot/d3, GitHub Actions | none (runs first) |
| **WS1 Statsbudsjett** | Find, register and fetch the sources; transforms; page text; definitions | WS0 |
| **WS2 Økonomi** | Same, for BNP, exports, SPU and petroleum | WS0 |
| **WS3 Sysselsetting** | Same, for the population accounts, definition comparison and årsverk | WS0 |
| **WS4 Staten som arbeidsgiver** | Same, for the rings 1–7, including the list of state companies with ownership shares and employee counts | WS0 (shares definitions with WS3) |
| **WS5a Visningsbibliotek** | One JS module per view type (A–E above) against the shared data contract; the drill-down/dimension engine; URL state; units; table fallback and CSV export. Developed against **test data** that WS0 defines, so it doesn't wait for real data | WS0 (runs in parallel with WS1–4) |
| **WS5b Galleri** | **All proposals are implemented** (3–6 per data type, snapshot and timeline). `site/galleri/<datatype>/` shows each dataset in every view, side by side and with the same data. The topic pages get a view switcher with every view available. After user feedback, `site_src/views.yaml` marks the default, the views to keep, the views to improve and the views to remove | WS5a + the first real data from WS1–4 |
| **WS5c Design** | The theme as described under «Tema» (tokens, fonts, cards, grid background), the validated chart palette, claim-level styling, mobile (drill-down via tap and breadcrumb), index page. **WS0 delivers the tokens and base CSS first**, so WS5a/b use them from the start | WS0; finished last |
| **WS6 Verifisering** (independent agent) | For each page: sample the numbers and check them against the original sources by hand; check the definition quotes; cover reconciliation tests, the link checker, and Norwegian language and tone | WS1–5 |

Rules for WS1–4 agents:
- Register each source in the registry before using it.
- Never invent table ids or numbers. When a series can't be found, document the gap in `metode` instead of filling it in.
- Prefer machine-readable sources over PDF.
- Write page text in bokmål, in a neutral tone.

## Verification
- `uv run python -m fetch all && uv run python -m transform all && uv run python build.py` must run without errors from an empty `data/processed`.
- `pytest`:
  - **schema check:** every processed series has `source_ids` that exist in the registry, plus a `claim_level`.
  - **no orphan numbers:** templates may not contain hard-coded digits in number fields.
  - **reconciliation:**
    - income minus expenses matches the published result
    - non-oil income + petroleum income = total income
    - BNP Fastland + petroleum ≈ BNP (within the stated tolerance)
    - AKU employed + unemployed = labour force
    - the rings in WS4 do not double count (helseforetak inside statsforvaltningen)
    - **hierarchy sum:** every node in every dimension equals the sum of its children (including «Øvrig»), and every dimension gives the same total for the same dataset
    - **reconciliation bridges** close: total A + named differences = total B
  - **view consistency:** a JS test (node + jsdom, or Playwright) renders the same node in every view and checks that the numbers shown in the table fallback are identical
  - **headline check:** a short list of known headline numbers from Gul bok, AKU and SSB press releases is checked against our processed values.
- The link checker verifies that all source URLs in the registry return 200.
- Manual check: run `python -m http.server -d site` and inspect every page on desktop and mobile width, in light and dark mode. Every chart must have a source line and a table fallback.
- WS6 sample check: at least 5 numbers per page are traced by hand all the way to the original source.
- Deploy: the Action publishes to GitHub Pages. If that fails, rsync to the VPS.
