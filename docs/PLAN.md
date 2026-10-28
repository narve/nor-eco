# Plan: «Norsk statsøkonomi – fra kildene» (static site, nor-eco)

## Status (read this first)
The plan below is the original design. Where the implementation differs, this section wins.

| WS | State |
|----|-------|
| WS0 Fundament | Done |
| WS1 Statsbudsjett | Done. The fund (SPU) shows only the latest figures, by decision, labelled as such. A Finansdepartementet workbook (`kap_3_nb_2027.xlsx`, sheet Fig3-6) has yearly values back to 1996 if history is wanted later |
| WS2 Økonomi | Done |
| WS3 Sysselsetting | Done (register-based status, AKU, persons, årsverk, hours) |
| WS4 Staten som arbeidsgiver | Done in part, by design: employees in the state (SSB), sectors, companies with state ownership (Statens eierrapport 2025), four groups. Not covered, and stated on the page and in `metode`: publicly funded private providers, NAV tiltak, the Norway-versus-abroad split, companies outside category 1 and 2. The «ring 1–7» numbering of the original plan is not used on the page |
| WS5a/b/c Views, gallery, design | Done: every view in `site_src/views.yaml` is built. The shared controls are built except the ones listed below |
| WS6 Verifisering | See `docs/VERIFICATION.md` |

The gallery has a `flow` item kind (two datasets), so the sankey is shown there too.

Shared controls, as built: breadcrumb with a dimension switch per node, «Vis som», year, status, unit, claim-level marks, source line, table drawer, copy link, fullscreen.
Deliberately not built, with the reason:
- **Skjul estimater:** the only estimate dataset (`staten.selskaper_vektet`) is estimate as a whole, so a toggle would only empty the chart. The unweighted chart sits beside it.
- **Compare mode:** the «Før og nå» view takes two years; a second source is compared on the page itself by showing two charts.
- **Definition selector:** the alternative definitions (AKU, register) are separate datasets with their own charts and the same unit, so they are shown side by side instead of switched.
- **Bottom-sheet tooltips:** every view shows its details in a readout line on tap or click instead of a floating tooltip.

## Context
The user lacks clear presentations of the actual data on the Norwegian state economy, and wants to see exactly what is being measured and how the numbers relate. The intent of any third party is not relevant to the site. The goal is a static website in Norwegian (bokmål) that presents three topics using **only official sources**, where every number has a citation:

1. **Statsbudsjettet**: income and expenses, with and without petroleum revenue.
2. **Statens/nasjonens økonomi**: BNP and exports, with and without oil and gas.
3. **Sysselsetting**: what actually counts as «sysselsatt» (uføre, students, tiltak, sick leave …), and how many people work for the state, directly and indirectly.

The repo `/home/narve/code/nor-eco` holds only these docs so far (`docs/PLAN.md`, `docs/VISUALIZATIONS.md`); there is no code yet. Implementation will be done by a multi-agent workflow afterwards, so the plan is split into workstreams that can run in parallel.

Decisions so far: language is Norwegian (bokmål). Data comes from fetch scripts into versioned data, then a static build. Hosting is GitHub Pages, with the user's VPS as fallback; the output is plain static files, so both work. Historical depth is not critical: a series may start at the first year where it is clean and comparable, and a view may show only the latest year or a short range. Skip years or series whenever that makes implementation safer or the visualisation clearer, and note the choice in `metode`. No view or text may hard-code a start year; the range comes from the data. «BA» means statsforetak and særlovsselskap. Indirect state employment covers the state-owned companies, the municipal sector, publicly funded private actors, and subsidised work programs (tiltak), i.e. rings 3–7 on the «staten som arbeidsgiver» page. Helseforetak (ring 2) are a subset of ring 1 and add nothing to the cumulative total.
- **Relative links only.** Every internal link and asset path is relative (`../assets/...`, never `/assets/...`), so the same `site/` works on a GitHub Pages subpath and on a separate domain. A test fails the build on any root-absolute `href` or `src`.
- **Views are phased, and data decides.** First the ★ default view per data type plus the S-size modules; then the rest. A view is only built where its required data exists in the sources. Each view declares its required datasets and dimensions in `site_src/views.yaml`, and the build hides (or greys out with a short explanation) any view whose data is missing. Nothing is estimated just to fill a view.
- **Repo size policy:** every git-tracked file is under 5 MB (hard limit, enforced by CI). Raw files that are easily downloaded again from the source (PDFs, large Excel files, bulk downloads) are not committed. They are gitignored and listed in `data/raw/MANIFEST.yaml` (url, sha256, retrieved date, size), and `fetch` can re-download and verify them against the hash. Only small raw files that are hard to re-obtain exactly (for example API responses that the source later revises) are committed. If a dataset would exceed the limit, drop early years (or coarse-grain it) rather than split or compress the file. No LFS.
- **JS and mobile tests use Playwright only** (no jsdom).

## Guiding principles (apply to every workstream)
- **Every displayed number traces to a source record.** No number is typed into a template by hand. Numbers come from `data/processed/*.json`, and each one carries `source_ids`.
- **Three levels of claim, marked visually:**
  - *Offisielt tall*: published as-is.
  - *Utledet*: our own arithmetic on official numbers, with the formula shown. Hatched fill with a thin outline, and a «ƒ» marker on labels.
  - *Estimat*: our own method with assumptions. Dotted outline with no fill (or 40 % alpha), an «≈» prefix on labels, and a method note.
  - This encoding is the single definition; `docs/VISUALIZATIONS.md` and the design work use it unchanged.
- **Raw snapshots are kept.** Each fetch stores the raw response with the retrieval date, so a number can be reproduced even after the source revises it. Store `vintage` (publication date) separately from `retrieved` date.
- **Definitions are explicit.** Each chart has a «Hva telles?» box with the official definition, quoted and cited.
- **No downloads.** The site offers no download or export functionality (no CSV, Excel, image or PDF export buttons). It is not an official source and must not present itself as a distributor of official data. Readers get the numbers on screen and a link to the original source for each one. The `facts.csv` files are internal build inputs and are not linked from any page.
- **Neutral tone.** Page text describes definitions, numbers and how they relate. It never mentions media, politicians or other actors, never says anyone is wrong, and draws no political conclusions. Each page gets an «Ofte blandet sammen» section that sets pairs of definitions side by side (for example vedtatt vs regnskap, AKU vs register, oljekorrigert vs strukturelt underskudd), with the official definition of each. **Every entry must link to its sources**: the quoted definition of each side comes from `definitions/*.yaml` with a `source_id` and a link to the exact publication, table or «Om statistikken» page. Any statement about how the two differ (scope, reference period, population, what is included) is itself cited to such a source. An entry that cannot be sourced is left out. The pairs are listed in the page's YAML so the build can fail if an entry has no `source_ids`.
- Licences: SSB data is CC BY 4.0 (stated by SSB). For other publishers the registry records the licence as the publisher states it, or «ikke oppgitt» when the page states none; a licence is never assumed (regjeringen.no states none on its data pages, so it is recorded that way). The site credits sources per page and in the source list.

## Tech stack
- **Python 3.12 + uv**, with a minimal set of dependencies: `httpx`, `pyyaml`, `jinja2`, `openpyxl` (for Excel files from regjeringen and NAV), `pypdf` (fallback for tables only published as PDF), and `pytest`.
- **SSB data** comes from the PxWebApi via JSON-stat2. Use **API v2** (`https://data.ssb.no/api/pxwebapi/v2/`) if it is live, otherwise v0; verify at start. Write one shared helper, not a fetcher per table.
- **Templates:** Jinja2 renders to `site/`. No JS framework.
- **Charts:** d3 v7 (including d3-hierarchy and d3-sankey) for the hierarchical and flow views, and Observable Plot for the simple time series. Both are **vendored** into `site/assets/vendor/` at pinned versions, so there are no CDN dependencies on GitHub Pages. A small in-house view library (`assets/js/views/`) has one module per view type. Every module takes the same data contract (see «Datamodell for drill-down»). Each chart also gets a `<table>` fallback (accessibility, and a way to read the exact numbers) and a «Kilde:» line under it.
- **Build and deploy: everything is built locally.** Fetch, transform, build and all checks run on the developer's machine (or the agent's sandbox). The generated `data/processed/` and the built `site/` are committed and pushed to `main`. GitHub Actions does not build anything. One minimal workflow, `publish.yml`, uploads the committed `site/` folder as the Pages artifact and deploys it (Pages branch deploys only support `/` or `/docs`, and `docs/` holds the planning docs). The VPS fallback is an rsync of `site/`. The GitHub remote is `origin` = `git@github.com:narve/nor-eco.git`, so the Pages URL is a subpath (`https://narve.github.io/nor-eco/`), which is why relative links are mandatory.
- **Reproducible output:** because `site/` is committed, the build must be deterministic: no timestamps or random ids in the output, stable sort order, and the retrieval date shown only where it comes from the data. This keeps commits small and diffs reviewable. Rebuilt and committed together: a data change commits `data/raw` (small files), `data/processed` and `site/` in one commit.
- **Local gate:** a single command, `uv run python -m checks` (also installed as a git pre-push hook), runs the full pipeline checks: schema, reconciliation, size guard, relative links, link checker and Playwright tests. The Action does not rerun them. Data refresh is manual and run when wanted, for example monthly: `uv run python -m fetch all && uv run python -m transform all && uv run python build.py`.
- **Network access in the dev sandbox:** outbound requests are allowed for the sandbox, so fetch scripts and vendoring can reach the source sites directly. Fetch code still sets a descriptive User-Agent, caches responses, and rate-limits itself.

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
    raw/<source_id>/<retrieved-date>.<ext>   # immutable snapshots (git-tracked only if <5 MB and not easily re-downloadable; PDFs and other re-downloadable files are gitignored and listed in raw/MANIFEST.yaml with sha256)
    processed/<topic>/<series>.json          # {series, unit, values[], source_ids[], derivation?, claim_level, notes}
  site_src/
    templates/ (base.html, page partials, chart macro, citation macro)
    pages/ index, statsbudsjett, okonomi, sysselsetting, staten-som-arbeidsgiver, begreper, kilder, metode
    assets/ css, js/charts.js, vendor/
  build.py                  # processed data + templates -> site/ (committed)
  checks/                   # local gate: python -m checks
  tests/                    # schema, consistency, reconciliation, link checks
  .github/workflows/ publish.yml   # uploads the committed site/ to Pages; no build
```

**Two processed formats, one metadata model.** Plain time series use the series JSON below. Hierarchical datasets use the fact-table format in the next section. Both carry the same metadata (`source_ids`, `claim_level`, `breaks`, `notes`, `price_basis`), and WS0's validator covers both.

**Processed series schema**, defined in WS0, for plain time series:
```json
{ "id": "budget.oljekorrigert_underskudd", "title": "...", "unit": "mrd. kr", "price_basis": "løpende|faste|ikke-relevant", "base_year": 2024,
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
- **Different sources mean different totals.** Statsbudsjettet (kapittel/post), offentlig forvaltning by COFOG (SSB) and the helseregnskapet (SHA: funksjon × tjenesteyter × finansiering) don't measure the same thing. They become separate datasets that are linked through a **reconciliation bridge**: a waterfall from total A to total B with named differences. This is central to a correct presentation, because the totals have different scopes and must not be compared directly.
- **Units are computed at view time** from the same facts: kr (løpende), kr (faste priser), % of total, % of BNP / BNP Fastland, per innbygger, per sysselsatt, or «av hver 100-lapp».
- **The URL holds the view state**, with one grammar everywhere: `?chart=<chart-id>&view=<view-id>&year=<yyyy>&unit=<unit-id>&status=<vedtatt|saldert|regnskap>&def=<definition-id>&dim=<dimension>&path=<segment>/<segment>` (only the chart named by `chart` reads or writes the state, so one page can hold several charts). Each path segment is `<dimension>:<code>`, meaning «split the previous node by this dimension and select this code». Example: `?chart=utgifter&view=utg-treemap&year=2025&unit=per_innb&path=formaal:helse/niva:stat`. A dimension switch at a mid-path node just changes the dimension in the next segment. Every view can then be linked and cited exactly.

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

## View data contract (defined by WS0, used by WS5a/b)
Every view module receives a `Node` tree and a props object, and nothing else:
```
Node  = { path, dim, label, value, unit, status, claim_level, source_ids[], definition_id?,
          children: Node[], other?: Node /* «Øvrig / ikke fordelt» */, breaks?: [{period, note}] }
Props = { node, dim, year, unit, status, claimStyle }
Events: drill(path), switchDim(path, dim)
```
`value` is already in the chosen unit. Unit conversion happens in the dimension engine, never inside a view. WS0 also ships a small synthetic test dataset (hierarchy with an «Øvrig» node, a series with a break, an estimat node) so WS5a can develop and test without real data.

## Visualiseringsalternativer (same data, several views, built in phases)
The full catalogue, with drill-down behaviour, honesty risks and how to mitigate them, unit handling, mobile behaviour and complexity for each view, is in **`docs/VISUALIZATIONS.md`**. A background Fable agent drafted it. It has 35 views over 7 data types, built from 14 shared modules. Every topic page gets a «Vis som»-switcher listing the views available for that page's data, and `site/galleri/` shows the built views side by side with the same data. The user then picks which views to keep, improve or remove (`site_src/views.yaml`).

**Phasing:** phase 1 is the ★ default view per data type plus the other S-size views. Phase 2 is the M-size views. Phase 3 is the L-size views (`flow-sankey`, `bef-euler`, `bef-sankey-status`, `flow-alluvial-time`). A later phase starts only after the earlier one is reviewed, and each view only where its data exists (see `views.yaml` above).

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
- source footer + «vis tallene» table (view only)
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
  - Light: `--bg #f3f5f8`, `--text #18202b`, `--muted #5b6776`, `--accent #0b7f95`, `--accent-2 #6a4fd1`. The remaining light tokens are copied from the CSS of https://narve.github.io. WS0 fetches that CSS and commits the complete set to `site_src/assets/css/tokens.css`, so no later agent has to guess.
- **Effects, used sparingly:**
  - a 40px grid in the background, with a radial glow at the top
  - cards with a blurred background, a thin border, and corner brackets in the accent colour
  - h2 headings with a gradient line after them
  - a pulsing status dot in the header
  - the gradient accent → accent-2 on a key word in h1
- **Numbers in charts and key figures** are set in JetBrains Mono with `font-variant-numeric: tabular-nums`, in Norwegian format (`1 234,5 mrd. kr`).
- **Chart palette:**
  - The categorical palette is the `dataviz` skill's reference palette (8 hues, fixed order), validated with its `validate_palette.js` on this site's own surfaces in both themes; the sets and results are recorded in `site_src/assets/css/palette.json` and a test fails if `tokens.css` drifts from them. It does not reuse the brand cyan/violet because those fail the lightness, chroma and colour-blind gates. Light mode has a contrast warning for four hues, which the skill allows only with visible labels or a table view; every chart has a legend, a readout and a «Vis tallene» table. Increases and decreases use the blue/red polarity pair, sums use a neutral grey, and «Øvrig» is one fixed grey.
  - Petroleum vs non-oil always gets the same pair of colours across all pages.
  - Claim levels: as defined under «Guiding principles» (offisiell solid; utledet hatched with «ƒ»; estimat dotted outline with «≈»).
- **Restraint:** the effects must never compete with the data. The plot area has no glow and no 3D, and the gridlines in charts use `--line`. Animation is only for drill-down transitions (≤300ms) and is turned off with `prefers-reduced-motion`.
- **Visitor statistics: GoatCounter**, privacy-friendly and cookie-free, using the same snippet and endpoint as narve.github.io. It is the only third-party script on the site. The `path` function prefixes the host, so GitHub Pages and the separate domain are counted separately:
  ```html
  <script>window.goatcounter = { path: function(p) { return location.host + p } }</script>
  <script data-goatcounter="https://dv8.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>
  ```
  The `src` uses `https:` explicitly (not protocol-relative) so the pages also work when opened from disk. The snippet lives in `base.html` only, and `metode.html` states what is collected (page views, no cookies, no personal data). No other tracking.

## Responsivt og mobilvennlig
**The data and visualisations come first.** Navigation is secondary on a phone.
- **Mobile first.** Base CSS is written for ~360px, with breakpoints at about 640px (tablet) and 1024px (desktop). There is no horizontal scrolling on the page; only the inside of a chart may pan, and only where the chart asks for it.
- **Navigation:**
  - On desktop, a slim top bar holds the page links.
  - On mobile, a **collapsible hamburger** opens a panel that overlays the page. Plain `<details>`/`<button>` with `aria-expanded` and no framework. The top bar is low and becomes sticky only on scroll-up, so the chart gets the height.
  - The page's own sections are in an «I denne siden» list inside the same panel.
- **Charts get the full width.** On mobile the side margin is 12–16px, and each chart can be expanded to **fullscreen** (`requestFullscreen`, with a fallback to a fixed overlay), with a hint to rotate to landscape where that helps.
- **Each view module defines its mobile variant**, as described per view in `docs/VISUALIZATIONS.md`:
  - sankey, icicle and waterfall turn vertical
  - Marimekko becomes stacked bars
  - the treemap gets a list drawer
  - UpSet becomes a vertical list
- The modules take their size from a `ResizeObserver` on the container, not from the window, so the same component works in the gallery, on the pages and in fullscreen.
- **Interaction:**
  - Tap targets are at least 44px.
  - A tap selects and shows a tooltip, which is anchored as a **bottom sheet** on mobile, not following the finger. A second tap, or a button in the sheet, drills down.
  - The breadcrumb scrolls horizontally on its own line.
  - Back-swipe and the browser's back button move up one level, because the drill state is in the URL.
- **Controls** (year, unit, definition, status, «Vis som») collapse into one «Innstillinger»-row above the chart, which opens as a bottom sheet on mobile. The active choices are shown as small chips, so the reader can always see which unit, year and status are on screen.
- The «vis tallene» table drawer under each chart is the mobile fallback for dense charts. It is responsive, with a sticky first column and horizontal scrolling only inside the table.
- **Performance on mobile:**
  - Each page loads only the view modules and data it uses (ES modules + lazy `import()` per view).
  - The JSON is small per node.
  - Fonts are subsetted woff2 with `font-display: swap`.
  - The background grid and blur are switched off on weak devices and with `prefers-reduced-transparency`.

## Pages and content

### 1. `index.html`: Oversikt
Key figures for the latest year, one tile per topic, each linking to its page. Includes a short explanation of the source policy and of the three claim levels.

### 2. `statsbudsjett.html`: Statsbudsjettet
- Total income and expenses for the state budget and statsregnskapet. Shows **vedtatt / saldert / regnskap** clearly, because budget figures and accounts are different things.
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
Concentric rings, each counted separately and shown with an accumulated total. Duplicates are marked explicitly. **This list is the single source of truth for ring numbers**; `docs/VISUALIZATIONS.md` refers to these numbers. Ring 2 is a subset of ring 1 and adds 0 to the cumulative total. Ring 5 (kommunesektoren) is not employed by the state; it is shown as its own band labelled «finansiert i stor grad av staten», and the narrow cumulative total (rings 1, 3, 4) excludes it.
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
| **WS0 Fundament** | Repo layout, `pyproject`, the series schema plus validator, `fetch/common.py` (snapshots, JSON-stat2 parser, SSB API v2/v0 check), `build.py` skeleton, base template, chart and citation macros, vendored Plot/d3, `checks` command and pre-push hook, `publish.yml` | none (runs first) |
| **WS1 Statsbudsjett** | Find, register and fetch the sources; transforms; page text; definitions | WS0 |
| **WS2 Økonomi** | Same, for BNP, exports, SPU and petroleum | WS0 |
| **WS3 Sysselsetting** | Same, for the population accounts, definition comparison and årsverk | WS0 |
| **WS4 Staten som arbeidsgiver** | Same, for the rings 1–7, including the list of state companies with ownership shares and employee counts | WS0 (shares definitions with WS3) |
| **WS5a Visningsbibliotek** | One JS module per view type (A–E above) against the shared data contract; the drill-down/dimension engine; URL state; units; table fallback (no export). Developed against **test data** that WS0 defines, so it doesn't wait for real data | WS0 (runs in parallel with WS1–4) |
| **WS5b Galleri** | The proposals are implemented in the phases described under «Visualiseringsalternativer», and only where the data exists. `site/galleri/<datatype>/` shows each dataset in every built view, side by side and with the same data. The topic pages get a view switcher with every available view. After user feedback, `site_src/views.yaml` marks the default, the views to keep, the views to improve and the views to remove | WS5a + the first real data from WS1–4 |
| **WS5c Design** | The theme as described under «Tema» (tokens, fonts, cards, grid background), the validated chart palette, claim-level styling, responsive layout and hamburger navigation (see «Responsivt og mobilvennlig»), index page. **WS0 delivers the tokens and base CSS first**, so WS5a/b use them from the start | WS0; finished last |
| **WS6 Verifisering** (independent agent) | For each page: sample the numbers and check them against the original sources by hand; check the definition quotes; cover reconciliation tests, the link checker, and Norwegian language and tone | WS1–5 |

Rules for WS1–4 agents:
- Register each source in the registry before using it.
- Never invent table ids or numbers. When a series can't be found, document the gap in `metode` instead of filling it in.
- Prefer machine-readable sources over PDF.
- Write page text in bokmål, in a neutral tone: describe definitions and numbers only, and never refer to media, politicians or other actors.
- If a series is hard to get, has breaks, or is hard to compare across years, shorten it or show a single year instead of working around the problem.

## Verification
- `uv run python -m fetch all && uv run python -m transform all && uv run python build.py` must run without errors from an empty `data/processed`. This is run locally on demand (and before any change to fetch or transform), not on every push.
- `pytest`:
  - **schema check:** every processed series has `source_ids` that exist in the registry, plus a `claim_level`.
  - **no orphan numbers:** in templates, numbers are only rendered through the `fmt()` / `cite()` macros that take a processed value. A lint step flags digit sequences in template text outside an allow-list (years in headings, ring numbers, the 3 % rule).
  - **file size guard:** the local gate fails if any git-tracked file is larger than 5 MB, or if a tracked file under `data/raw/` has a `.pdf` extension. Re-downloadable raw files must be listed in `data/raw/MANIFEST.yaml` instead.
  - **relative links:** no root-absolute `href`/`src` in `site/`, and every relative link resolves.
  - **reconciliation:**
    - income minus expenses matches the published result
    - non-oil income + petroleum income = total income
    - BNP Fastland + petroleum ≈ BNP (within the stated tolerance)
    - AKU employed + unemployed = labour force
    - the rings in WS4 do not double count (helseforetak inside statsforvaltningen)
    - **hierarchy sum:** every node in every dimension equals the sum of its children (including «Øvrig»), and every dimension gives the same total for the same dataset
    - **reconciliation bridges** close: total A + named differences = total B
  - **view consistency:** a Playwright test renders the same node in every view and checks that the numbers shown in the table fallback are identical
  - **headline check:** a short list of known headline numbers from Gul bok, AKU and SSB press releases is checked against our processed values.
- The link checker verifies that all source URLs in the registry return 200.
- Manual check: run `python -m http.server -d site` and inspect every page at 360px, 768px and 1280px width, in light and dark mode. Every chart must have a source line and a table fallback.
- Mobile, automated: Playwright with an iPhone/Pixel profile renders every view in the gallery. It checks that there is no horizontal page scroll and that tap targets are at least 44px, takes screenshots, and confirms that drill-down + back works via tap and history.
- WS6 sample check: at least 5 numbers per page are traced by hand all the way to the original source.
- Deploy: after the push, `publish.yml` deploys the committed `site/` to GitHub Pages. If that fails, rsync to the VPS. Before pushing, confirm that `site/` is up to date with the sources (the gate rebuilds and fails on any diff in `site/`). Serving `site/` from a subpath (for example `python -m http.server` from the parent directory) must work identically to serving it from the root.
