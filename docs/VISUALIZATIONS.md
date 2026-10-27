# Visualiseringskatalog for nor-eco

Drafted by a background design agent (Fable) as input to `docs/PLAN.md`. The proposals are built in phases (S first, then M, then L; see PLAN.md) and only where the data exists, and appear in the gallery (`site/galleri/`). The user then chooses the defaults and which views to keep, improve or remove.

Conventions used below:
- **Claim levels** are encoded the same way everywhere:
  - *offisiell*: solid fill
  - *utledet*: hatched or lighter fill with a thin outline
  - *estimat*: dotted outline with no fill (or 40 % alpha), and an «≈» prefix on the label
- «Øvrig / ikke fordelt» always gets the same neutral grey and is never hidden.
- All hierarchical views bind to the same tidy fact table and the same `path` state in the URL (`?view=utg-treemap&path=formaal:helse/niva:stat&unit=pct-bnp&year=2024`; the grammar is defined in PLAN.md).

Type: snapshot = single year, timeline = over time. Complexity: S/M/L.

---

## 1. Statens utgifter (hierarchical, multi-dimension)

### `utg-hier-bars` — Nivåbasert søylevisning ★ default
- **type**: both
- **description**: One level at a time: sorted horizontal bars of the children of the current node, with the parent total as a thin reference bar on top. In timeline mode, each bar gets a small horizon strip or sparkline (full available range) next to the current-year value.
- **drill-down**: Click a bar and its children slide in from the right, while the clicked bar grows to become the new reference bar (d3 transition on the y-scale). A breadcrumb `Utgifter › Helse › Stat` sits on top. Each crumb has a dimension dropdown («vis etter: formål | nivå | art | kap/post»), so the dimension switch happens *at a node*. Back-swipe on mobile.
- **honesty**: Bars are the most accurately read encoding (length on a common baseline). Risk: the reader forgets the parent total. Mitigate with the reference bar and «= 100 % av Helse». Vedtatt and regnskap are shown as paired bars (vedtatt as outline, regnskap filled), so the statuses are never mixed silently. The remainder bar is always present.
- **unit handling**: all units; best for kr, % of parent and per innbygger. The reference bar makes «av hver 100-lapp» natural.
- **mobile**: native; horizontal bars scale to the width and labels go above the bars.
- **complexity**: S
- **reuse**: `hier-bars` (also serves inntekter, sysselsetting and statlig sysselsetting)

### `utg-treemap` — Flisekart
- **type**: snapshot (timeline only as an animated year scrubber)
- **description**: Squarified treemap of the current node's children, with two levels visible: the children, and the grandchildren as thin inner rectangles. Area = kr.
- **drill-down**: Click a tile for a zoomable treemap transition (d3.treemap with interpolated x/y scales, 600 ms). Switching dimension at the node via the breadcrumb dropdown crossfades and re-tiles. The year scrubber re-tiles with object constancy on code.
- **honesty**: Area comparison is poor for ratios; differences under 10 % can't be read. Mitigate by always printing value and % in the tile, and by offering «bytt til søyler» on the same node. Elongated tiles mislead, so use squarify with a ratio of about 1.6. Never mix vedtatt and regnskap in one treemap: status is a global toggle with a visible badge.
- **unit handling**: kr, % of parent, per innbygger. Poor for % BNP, where values like 1.2 % vs 1.4 % are hard to tell apart.
- **mobile**: works, but small tiles become unlabelled. A tap-to-list drawer shows the sorted values for the current level.
- **complexity**: M
- **reuse**: `treemap`

### `utg-sunburst` — Solstråle
- **type**: snapshot
- **description**: Sunburst with 2–3 rings showing formål → underformål. An optional outer ring is coloured by a second dimension (forvaltningsnivå), so the reader sees «within Helse, how much is stat vs kommune» in one picture.
- **drill-down**: Click an arc for a zoomable sunburst (d3.partition, arc interpolation). The centre shows the node name, value and unit, and clicking the centre goes up one level. A dimension switch changes what the *outer* ring encodes.
- **honesty**: Outer rings have more area for the same share, a classic distortion. Mitigate with angle-only encoding (angle = share) and numeric labels on hover. Good for showing «Øvrig» as a visible grey wedge at every level. Avoid more than 3 rings.
- **unit handling**: % of total and % of parent are the natural units, with kr on hover. Not suitable for comparing per innbygger across years.
- **mobile**: the square chart fits the width; labels move to a legend list below. Tap selects, a second tap zooms.
- **complexity**: M
- **reuse**: `sunburst` (also inntekter and befolkning)

### `utg-icicle` — Istapp (horisontal)
- **type**: snapshot
- **description**: Horizontal icicle (partition) with the root on the left and 3–4 levels to the right; rectangle height = share. The best overview of the whole tree at once, and it reads like a table of contents.
- **drill-down**: Click a rect to zoom so it fills the height (d3 partition zoom). A dimension switch inserts a *new column* at the chosen node. For example, «Helse» splits by nivå in column 3 while its siblings keep splitting by formål. This is exactly the «switch dimension at any node» model, and the icicle is the only shape that makes the mixed tree visible.
- **honesty**: Linear encoding (height), so no area distortion. Risk: readers may take mixed dimensions in sibling columns to be the same dimension. Mitigate by colouring the column header by dimension and drawing a dashed divider.
- **unit handling**: kr and %; labels print in the current unit.
- **mobile**: rotates to a vertical icicle (root on top); zoom on tap.
- **complexity**: M
- **reuse**: `icicle`

### `utg-streamgraph` — Utgiftsstrøm over tid
- **type**: timeline
- **description**: Stacked area (no wiggle offset, baseline at zero) of the current node's children over time, in faste priser or % BNP. Shows how the composition of e.g. Helse has shifted.
- **drill-down**: Click a stream and it becomes the new 100 %, splitting into its children: the others shrink to zero while the chosen one expands. Breadcrumb as before. Toggle «stablet | 100 %-stablet | separate linjer».
- **honesty**: Middle series in a stacked area are hard to read. Mitigate with a hover that isolates one series (the others drop to 15 % alpha) and with the «separate linjer» toggle. A break in the series where the classification changed (e.g. helseforetak in 2002) is drawn as a vertical dashed line with a note, never smoothed over. Regnskap for past years and vedtatt for the current year must look different, so the budget year is hatched.
- **unit handling**: faste priser, % BNP, % av total, per innbygger. Løpende kr is allowed, but with a warning badge.
- **mobile**: fine; the legend becomes a tappable list that highlights.
- **complexity**: M
- **reuse**: `timeseries` (stacked mode)

### `utg-bump` — Rangering over tid
- **type**: timeline
- **description**: Bump chart ranking the top-N formål by size per year; line thickness = share is optional. Answers «when did Helse overtake Forsvar?» without pretending to show magnitudes.
- **drill-down**: Click a line to re-rank that node's children. A dimension switch re-ranks by another dimension.
- **honesty**: Shows rank only, and the subtitle must say so («Rangering, ikke beløp»). Pair it with a hover tooltip giving kr and %.
- **unit handling**: unit-agnostic (rank). Ranking by % BNP vs faste priser can differ, so expose the ranking unit.
- **mobile**: works; limit to the top 8.
- **complexity**: S
- **reuse**: `timeseries` (rank mode)

---

## 2. Statens inntekter med og uten petroleum

### `innt-stacked-bars` — Inntekter med og uten petroleum
- **type**: both
- **description**: Two-column stacked bar for a year.
  - Left, «Uten petroleum»: skatt på inntekt/formue, mva, arbeidsgiveravgift, særavgifter, øvrig.
  - Right, «Petroleum»: petroleumsskatt, SDØE netto kontantstrøm, Equinor-utbytte.

  The timeline shows the same stacks per year over the available range.
- **drill-down**: Click a segment and it becomes the full bar, split by its children (same transition as `hier-bars`). Breadcrumb.
- **honesty**: Petroleum revenue for SDØE is net cash flow, not gross; label it exactly as SSB and Finansdep do. The Equinor dividend is offisiell, but counting it as «petroleum» is utledet, so it gets the hatch. Never add petroleum to the budget silently: the chart must state that petroleum goes to SPU.
- **unit handling**: kr løpende/faste, % BNP, and % BNP Fastland. The last matters: petroleum as a share of BNP Fastland is the honest ratio.
- **mobile**: vertical stacks fit; years scroll horizontally in timeline mode.
- **complexity**: S
- **reuse**: `hier-bars` (stacked mode), `timeseries`

### `innt-waterfall` — Fra inntekter til fondsuttak ★ default
- **type**: snapshot (timeline as small multiples)
- **description**: Two waterfall branches.
  - Main: inntekter uten petroleum → minus utgifter → *oljekorrigert underskudd* → ± konjunktur- og engangsjusteringer → *strukturelt oljekorrigert underskudd*, compared with 3 % av SPU (handlingsregelen) as a reference line.
  - Second: petroleumsinntekter → overføring til SPU → fondsuttak = oljekorrigert underskudd.
- **drill-down**: Click a step and the step bar expands into its components; e.g. «utgifter» opens the utgifter hierarchy in a side panel. The identity «uttak = oljekorrigert underskudd» is shown as an equals bridge.
- **honesty**: The clearest view of the chain from inntekter to fondsuttak. It shows that the *fondsuttak* is a residual, and that 3 % is a guideline against the *structural* deficit, not the actual withdrawal. Risks:
  - The structural adjustment is an estimate (Finansdep), so it is coloured as estimat.
  - Vedtatt vs regnskap must be chosen explicitly.
  - «3 % of SPU» uses the fund value at the start of the year, so print the date.
- **unit handling**: kr, % BNP Fastland (standard), % av SPU.
- **mobile**: vertical waterfall (steps top-down) with labels on the right.
- **complexity**: M
- **reuse**: `waterfall` (also pengestrømmer and reconciliation)

### `innt-timeline-gap` — Oljekorrigert underskudd og handlingsregelen over tid
- **type**: timeline
- **description**: Line chart of the strukturelt oljekorrigert underskudd, the actual fondsuttak, and 4 %/3 % av SPU as a step line (the rule changed in 2017). The band between uttak and the rule is shaded. A secondary line shows the SPU value, preferably in a separate panel rather than on a right axis.
- **drill-down**: Click a year to open `innt-waterfall` for that year.
- **honesty**:
  - Avoid dual axes; use two stacked panels sharing x.
  - Mark the 4 %→3 % change.
  - Values for the current year are vedtatt or anslag, so the area is hatched.
  - Revisions matter: offer «slik det var anslått i budsjettet» and «regnskap» as two lines.
- **unit handling**: % BNP Fastland (default), kr faste, % av SPU.
- **mobile**: panels stack vertically.
- **complexity**: S
- **reuse**: `timeseries`

### `innt-donut-pair` — Hver 100-lapp staten får inn
- **type**: snapshot
- **description**: Two donuts, «Alle inntekter inkl. petroleum» and «Inntekter uten petroleum», showing the share of each source. The centre shows the total.
- **drill-down**: Click a slice and the donut zooms to that slice's children (d3 arc tween); breadcrumb in the centre.
- **honesty**: Donuts are fine for 6 slices or fewer with large differences, so collapse smaller items into «Øvrig». Side-by-side donuts invite comparing slices by angle only, and the two donuts look equally big. Keep the radii equal and print the absolute totals.
- **unit handling**: «av hver 100-lapp» and %, with kr on hover.
- **mobile**: stack vertically.
- **complexity**: S
- **reuse**: `sunburst` (one ring)

### `innt-slope` — Inntektsmiks før og nå
- **type**: timeline (two points)
- **description**: Slope chart comparing the share of each source in year A vs year B (default: first and latest year in the data), in % BNP Fastland. Shows the petroleum swing directly.
- **drill-down**: Click a slope to show the children of that source as slopes.
- **honesty**: Cherry-picked years can mislead, so expose both year pickers and show a faint sparkline on hover.
- **unit handling**: shares, % BNP Fastland, per innbygger in faste priser.
- **mobile**: native.
- **complexity**: S
- **reuse**: `slope` (a small module, also used for sysselsetting)

---

## 3. Pengestrømmer

### `flow-sankey` — Pengestrømmen: petroleum → SPU → budsjett → formål ★ default
- **type**: snapshot
- **description**: Sankey with columns:
  1. Kilder: petroleum, skatter uten petroleum, øvrige inntekter
  2. SPU: a node with inflow, outflow and «beholdes i fondet»
  3. Statsbudsjettet
  4. Formål: top 8 + Øvrig

  Lending and kapitalinnskudd form a distinct «gjennomstrømning» ribbon that leaves the budget node for «Utlån og kapitaltransaksjoner». A dashed divider separates it from real spending.
- **drill-down**: Click a target node and the right column expands into its children: a new column slides in, d3-sankey is recomputed, and links transition by key. Breadcrumb per column. Dimension switch for the rightmost column (formål | nivå | art).
- **honesty**:
  - A sankey implies conservation, so state where the diagram balances and where it doesn't. SPU's return is not budget revenue; it stays in the fund.
  - Flow width is linear, which is honest, but many thin links become noise. Cap at 8 + Øvrig.
  - Brutto vs netto: SDØE inflows are net cash flow. Add a «brutto/netto» toggle with a note.
  - Years: regnskap only, or show the vedtatt badge.
- **unit handling**: kr (default), % BNP Fastland, «av hver 100-lapp».
- **mobile**: vertical sankey (top-down; d3-sankey supports swapping axes), with node labels inline.
- **complexity**: L
- **reuse**: `sankey` (also befolkning flows and reconciliation bridges)

### `flow-waterfall-year` — Årets kontantstrøm trinn for trinn
- **type**: snapshot
- **description**: Waterfall that starts at «Petroleumsinntekter» and steps down through «avsatt til SPU», «fondsavkastning» and «uttak» to «brutto utgifter». A final negative step, «hvorav utlån/kapitalinnskudd (gjennomstrømning)», gives «netto utgifter».
- **drill-down**: Each step opens its hierarchy in a side panel.
- **honesty**: Makes gross vs gjennomstrømning explicit; the gross budget total and the net spending differ by exactly this item. Avoid implying that lending is free: label it «utlån, tilbakebetales», with an estimat badge for the expected repayment.
- **unit handling**: kr, % BNP Fastland.
- **mobile**: vertical steps.
- **complexity**: M
- **reuse**: `waterfall`

### `flow-alluvial-time` — Strømmer år for år
- **type**: timeline
- **description**: Small multiples of a simplified 3-column sankey for a few selected years (default: evenly spaced across the available range, plus the latest), on the same scale, so the growth of the SPU-uttak ribbon relative to skatter is visible. Alternatively an animated sankey scrubbing through the years, with fixed node positions.
- **drill-down**: Click a multiple to open the full `flow-sankey` for that year.
- **honesty**: The same scale across years is essential; otherwise the growth disappears. Use faste priser or % BNP Fastland. The animation must keep the node order fixed to avoid false «movement».
- **unit handling**: faste priser, % BNP Fastland.
- **mobile**: the multiples stack; the animation gets a year slider.
- **complexity**: L
- **reuse**: `sankey` + `small-multiples`

### `flow-stacked-timeline` — Finansiering av budsjettet over tid
- **type**: timeline
- **description**: 100 % stacked area showing the share of budget expenditure financed by skatter uten petroleum vs fondsuttak, plus a line for «uttak i % av SPU».
- **drill-down**: Click the «skatter» area to split it by tax type.
- **honesty**: 100 % stacking hides growth, so pair it with an absolute-value toggle. Mark the regime changes from the shared break registry (for example the handlingsregel, the change to 3 %, covid), but only those that fall inside the plotted range.
- **unit handling**: %, % BNP Fastland, faste priser.
- **mobile**: fine.
- **complexity**: S
- **reuse**: `timeseries`

### `flow-receipt` — Din del av statsbudsjettet (kvittering)
- **type**: snapshot
- **description**: A «personal receipt» in scrollytelling, for one inhabitant (per innbygger) or per 100-lapp. It lists the income lines (skatt, petroleum→uttak), then the expenditure lines by formål, with a «herav utlån» footnote. Scrolling animates each line being added to the running total.
- **drill-down**: Tap a line to expand indented sub-lines, like a receipt with item details.
- **honesty**: Per innbygger averages hide the distribution, so say «gjennomsnitt per innbygger, ikke din faktiske skatt». Keep inntekter and utgifter clearly separate, and show the bridging line «finansiert av fondsuttak».
- **unit handling**: per innbygger kr, «av hver 100-lapp».
- **mobile**: designed for mobile first.
- **complexity**: M
- **reuse**: `receipt` (also utgifter)

---

## 4. Makroøkonomi med og uten olje og gass

### `makro-bnp-lines` — BNP og BNP Fastlands-Norge ★ default
- **type**: timeline
- **description**: Two lines in faste priser, BNP total and BNP Fastland, with the gap shaded and labelled «petroleumsvirksomhet og utenriks sjøfart». The panel below shows the gap as % of BNP.
- **drill-down**: Click the gap to split it into utvinning, rørtransport, tilknyttede tjenester and utenriks sjøfart.
- **honesty**: Make the definition of Fastlands-Norge explicit, since it excludes shipping as well. Faste priser for petroleum are volume-based and behave very differently from current prices, so offer both and explain the difference in a note. No dual axes.
- **unit handling**: kr faste/løpende, indexed (år X = 100), per innbygger.
- **mobile**: fine.
- **complexity**: S
- **reuse**: `timeseries`

### `makro-export-stacked` — Eksport med og uten råolje og gass
- **type**: timeline
- **description**: Stacked bars per year for råolje, naturgass, annen vareeksport and tjenesteeksport, with a line for import. The trade balance is a separate diverging bar panel; without petroleum it is often negative.
- **drill-down**: Click «annen vareeksport» to split it into SITC groups (fisk, metaller, maskiner …).
- **honesty**: The negative trade balance without petroleum is the key honest message. Show it in its own diverging panel with a zero line, not buried in a stack. Gas price spikes (2022) dominate the picture; the faste priser toggle separates volume from price.
- **unit handling**: kr løpende/faste, % BNP, % av total eksport.
- **mobile**: fine; the panels stack.
- **complexity**: S
- **reuse**: `timeseries` (stacked + diverging)

### `makro-marimekko` — Økonomien i ett bilde
- **type**: snapshot
- **description**: Marimekko where each column is a næring, with width = its share of BNP. Each column is split vertically into eksportandel vs innenlandsk. The petroleum column stands out as fairly narrow but almost entirely export.
- **drill-down**: Click a column to fill the chart with that næring's sub-industries.
- **honesty**: A Marimekko is hard for untrained readers, so add a «vis som søyler» fallback. The areas are honest (width × height), but the vertical split is a ratio, so print both numbers on hover.
- **unit handling**: % of BNP, kr.
- **mobile**: switches to stacked horizontal bars, one per næring.
- **complexity**: M
- **reuse**: `marimekko` (also statlig sysselsetting: persons × ownership share)

### `makro-spu-vs-bnp` — Oljefondet mot økonomien
- **type**: timeline
- **description**: SPU market value as a line, expressed as multiples of BNP Fastland (with gridlines at × 1, × 2, × 3). A stacked bar panel below breaks down the annual change into tilførsel, avkastning and kronekurs. Uses NBIM numbers.
- **drill-down**: Click a year's bar to see the return by asset class (equity, fixed income, real estate).
- **honesty**: The kronekurs effect is not «earned» and must have its own colour. The fund value is at year-end, while budget years use the start-of-year value; state both.
- **unit handling**: kr, × BNP Fastland, per innbygger.
- **mobile**: fine.
- **complexity**: S
- **reuse**: `timeseries`

### `makro-donut-pair` — Hva Norge eksporterer (ett år)
- **type**: snapshot
- **description**: Donut of the export composition. The «uten råolje og gass» toggle re-normalises the donut with an animation, so the reader sees fisk and metaller grow.
- **drill-down**: Click a slice to see its children.
- **honesty**: Re-normalising changes the denominator. Print «av 1 234 mrd» / «av 789 mrd» in the centre so the equal-size donuts don't fool the reader.
- **unit handling**: %, kr.
- **mobile**: fine.
- **complexity**: S
- **reuse**: `sunburst`

---

## 5. Befolkning og sysselsetting

### `bef-waffle` — Befolkningen 15–74 som 100 ruter ★ default
- **type**: snapshot
- **description**: A waffle grid of 10×10 cells (1 % each) or 20×20 (0.25 % each). Cells are coloured sysselsatt, arbeidsledig (AKU) or utenfor arbeidsstyrken. The «utenfor» cells are further coloured by subgroup: studenter, pensjonister, uføre, hjemmeværende, annet. A definition toggle (AKU | register | NAV registrert ledig) recolours the cells with an animation, showing exactly how many cells move.
- **drill-down**: Click a group and its cells spread to fill the waffle, split by subgroup; breadcrumb. Overlapping groups (uføre with a part-time job) are shown as *striped* two-colour cells. The waffle is one of the few shapes where overlap can be drawn literally.
- **honesty**: Rounding to whole cells loses small groups, so use 20×20 and print exact %. The definition toggle is the main honesty mechanism: it shows that unemployment is 3.x % in AKU vs 2.x % in NAV's count for the same people. For persons vs årsverk, a second waffle sits alongside, where each cell is 1 % of årsverk.
- **unit handling**: %, persons (on hover), per 100 personer.
- **mobile**: excellent; it's a square grid.
- **complexity**: M
- **reuse**: `waffle` (also statlig sysselsetting)

### `bef-euler` — Overlappende statuser
- **type**: snapshot
- **description**: Area-proportional Euler diagram of the sets sysselsatt, mottar uføretrygd/AAP, under utdanning, mottar alderspensjon, sykmeldt and på tiltak; with more than 3 sets it becomes an UpSet plot. The intersections are sized by SSB/NAV register counts.
- **drill-down**: Click an intersection for a bar list of its composition by age and sex. Click a set and the UpSet plot re-centres on that set.
- **honesty**: This is the only view that makes «a person can be uføre and employed» impossible to miss. Euler areas for more than 3 sets can't be solved exactly, so use UpSet there (bars for each combination, a dot matrix for membership) and label the Euler «arealet er omtrentlig». Where intersection counts aren't published, mark the cell estimat and show the range.
- **unit handling**: persons, % of the population 15–74.
- **mobile**: UpSet turns into a vertical list of combinations, each with a mini dot matrix.
- **complexity**: L
- **reuse**: `euler-upset`

### `bef-sankey-status` — Fra befolkning til status
- **type**: snapshot
- **description**: Sankey/alluvial: Befolkning 15–74 → I arbeidsstyrken / Utenfor → Sysselsatt / Ledig, with subgroups after each.
  - Sysselsatt: heltid, deltid, sykmeldt, permittert, på tiltak med lønn
  - Utenfor: student, pensjonist, ufør, annet

  For overlaps, each person counts in one primary status, with a thin dashed «also» ribbon to the secondary set, labelled explicitly.
- **drill-down**: Click a node to expand the next column by the chosen dimension (alder | kjønn | innvandrerbakgrunn | fylke).
- **honesty**: A sankey forces a one-to-one partition, so overlaps need the dashed ribbons plus a link to `bef-euler`. The definition switch (AKU/register) re-routes the flows with an animation and a changelog of what moved.
- **unit handling**: persons, %, årsverk (the toggle thickens or thins the ribbons; «utenfor» has no årsverk and is greyed out).
- **mobile**: vertical sankey.
- **complexity**: L
- **reuse**: `sankey`

### `bef-stacked-timeline` — Statusfordeling over tid
- **type**: timeline
- **description**: 100 % stacked area of the status shares over time, with a definition toggle. A separate line panel compares the three unemployment measures: AKU, registrert hos NAV, and bruttoledighet including tiltak.
- **drill-down**: Click an area to split it by subgroup over time.
- **honesty**: AKU breaks (2006, and the new EU regulation in 2021) must be drawn as discontinuities. Show each series only for the years where it exists (verify each series' start year in its source; the a-ordningen-based series is shorter) and never interpolate. Mark the covid permitteringer in 2020.
- **unit handling**: %, persons, per 1000 innbyggere.
- **mobile**: fine.
- **complexity**: S
- **reuse**: `timeseries`

### `bef-dot-units` — Hver prikk er 10 000 personer
- **type**: snapshot
- **description**: Unit chart with dots grouped in columns per status; dots that belong to two statuses are half-filled. In the scrollytelling variant, dots move from «befolkning» to their status step by step as the reader scrolls, then re-sort when the definition changes.
- **drill-down**: Click a group to re-cluster its dots by subgroup (force or grid layout transition).
- **honesty**: Dots are countable and concrete, but the rounding to 10 000 must be stated. The honesty payoff is the animation step «now switch to NAV's definition: 40 dots leave the ledig column».
- **unit handling**: persons. The årsverk toggle shrinks the dots (deltid = half a dot), which is intuitive but must be noted as a visual approximation.
- **mobile**: dots reflow to the width.
- **complexity**: M
- **reuse**: `unit-dots` (shares layout code with `waffle`)

### `bef-slope-persons-aarsverk` — Personer vs årsverk
- **type**: snapshot (two measures)
- **description**: Slope chart per group, with persons on the left axis and årsverk on the right, both as % of the total. Groups with a lot of deltid (helse, varehandel, uføre with a job) slope downward.
- **drill-down**: Click a group to see its subgroups.
- **honesty**: The two axes have different totals, so print both. A timeline isn't meaningful here, except as small multiples.
- **unit handling**: %, absolute.
- **mobile**: native.
- **complexity**: S
- **reuse**: `slope`

---

## 6. Statlig sysselsetting (rings)

### `ssys-rings` — Ringene rundt staten
- **type**: snapshot
- **description**: Concentric rings (nested circles or arcs) with ring 1 (statsforvaltningen) innermost. Each ring's *band width* is proportional to the persons it adds. Helseforetak are drawn inside ring 1 as a highlighted sector, not as a separate ring, to avoid double counting. The outer rings 5–7 use estimat styling. A faint outermost circle stands for alle sysselsatte, so the share is visible.
- **drill-down**: Click a ring to open it as `hier-bars`; e.g. ring 3 or 4 becomes a list of companies with the full count and the ownership-weighted count. Toggles: personer | årsverk; full count | eierandelsvektet; Norge | inkl. utlandet.
- **honesty**: Concentric rings encode by band *area*, which grows with the radius. Either make the band *width* proportional and print the cumulative numbers at each ring, or use an equal-area «target» layout with explicit numeric labels. In SSB, helseforetak are a subset of statsforvaltningen; draw that as containment, not addition. Kommunesektoren is not employed by the state, so label it «finansiert i stor grad av staten», with a visible gap or dashed ring between rings 4 and 5.
- **unit handling**: persons, årsverk, % av alle sysselsatte.
- **mobile**: square, with a legend list of cumulative totals below.
- **complexity**: M
- **reuse**: `rings` (a small special module built on `sunburst` arcs)

### `ssys-cumulative-bars` — Kumulativ: hvor mye er «offentlig»? ★ default
- **type**: snapshot
- **description**: Horizontal bars for each ring, plus a cumulative bar that grows step by step (waterfall style) to a total, against a reference bar for «alle sysselsatte». Each ring has two bars, full count and ownership-weighted. The estimat rings are hatched.
- **drill-down**: Click a ring to see its companies or units, sorted; dimension switch (næring | fylke | eierdepartement).
- **honesty**: The clearest shape for showing that «state-related employment» depends on which rings you include. Print the two cumulative totals (narrow and broad) explicitly. The reader picks rings with checkboxes, and the cumulative total updates.
- **unit handling**: all.
- **mobile**: native.
- **complexity**: S
- **reuse**: `waterfall` + `hier-bars`

### `ssys-waffle` — Av 100 sysselsatte
- **type**: snapshot
- **description**: 10×10 waffle of all employed people in Norway, with cells coloured by ring. Rings 3–4 (companies) use partially filled cells weighted by ownership (e.g. 67 % Equinor = a two-thirds filled cell). Toggle persons/årsverk.
- **drill-down**: Click a ring's cells to re-fill the waffle with that ring's breakdown.
- **honesty**: Partial fill makes the ownership weighting visible instead of hiding it in a footnote. Estimat rings get dotted borders.
- **unit handling**: %, «av 100 sysselsatte».
- **mobile**: excellent.
- **complexity**: S
- **reuse**: `waffle`

### `ssys-timeline` — Ringene over tid
- **type**: timeline
- **description**: Stacked area of rings 1, 3 and 4 as % of all employed over the available range (ring 2 is contained in ring 1 and not stacked), with ring 5 (kommunesektoren) as its own labelled band and rings 6–7 as a dashed estimat band on top. Vertical markers flag structural changes: the helseforetak reform in 2002, the conversions of Mesta, Posten and others, and the partial privatisation of Equinor.
- **drill-down**: Click a ring to see its subcomponents over time.
- **honesty**: Many of the breaks are reclassifications, not real changes in employment, so the markers and a hover note «omklassifisering» are mandatory. The ownership-weighted share over time depends on changes in the stakes, so show the weight line separately.
- **unit handling**: %, persons, årsverk.
- **mobile**: fine.
- **complexity**: M
- **reuse**: `timeseries`

### `ssys-marimekko-eier` — Selskaper: ansatte × eierandel
- **type**: snapshot
- **description**: Marimekko for rings 3–4 (statsforetak/særlov and AS/ASA). Column width = the company's employees (full count). Each column's height is split into the state's ownership share vs other owners, with Norway vs abroad as a second split. The area of the state's portion = ownership-weighted employment.
- **drill-down**: Click a company to see its subsidiaries or segments, if published (Statens eierberetning).
- **honesty**: Shows that Equinor dominates the full count, but much of it is abroad. Here the area (the weighted count) is genuinely meaningful. Companies that don't report the Norway/abroad split get an estimat hatch.
- **unit handling**: persons, weighted persons.
- **mobile**: falls back to stacked horizontal bars.
- **complexity**: M
- **reuse**: `marimekko`

---

## 7. Avstemming mellom kilder

### `rec-bridge-waterfall` — Avstemmingsbro ★ default
- **type**: snapshot
- **description**: Waterfall from Total A (e.g. statsbudsjettets utgifter) to Total B (offentlig forvaltning by COFOG), via named bridge items:
  - \+ kommuneforvaltning
  - \+ helseforetak
  - − overføringer mellom nivåer
  - − utlån
  - ± periodisering
  - \+ Øvrig/ikke forklart

  The residual is always its own grey step, «ikke forklart».
- **drill-down**: Click a bridge step for the detail list of what it consists of, with source citations. Click a total to open that source's hierarchy view.
- **honesty**: The core honesty device of the site. The unexplained residual must never be absorbed into another step, and its size is printed as % of the difference. Each bridge item carries its claim level.
- **unit handling**: kr; % of Total A.
- **mobile**: vertical steps.
- **complexity**: M
- **reuse**: `waterfall`

### `rec-parallel-bars` — Samme ting, tre kilder
- **type**: snapshot
- **description**: Side-by-side bars for the same concept, e.g. helseutgifter, from three sources: statsbudsjett, COFOG and the SHA helseregnskap. Each bar is segmented to show what it includes that the others don't, with the shared core in one colour and the additions specific to each source in others.
- **drill-down**: Click a segment for its definition and underlying items.
- **honesty**: Shows the definitions as the cause of the different numbers, rather than «one of them is wrong». The segments must map to the bridge items in `rec-bridge-waterfall` (same ids).
- **unit handling**: kr, % BNP.
- **mobile**: native.
- **complexity**: S
- **reuse**: `hier-bars` (stacked)

### `rec-sankey-bridge` — Fra kilde til kilde som strøm
- **type**: snapshot
- **description**: Two-column sankey with the categories of Source A on the left and those of Source B on the right. The ribbons show how the items of A map to items of B (many-to-many). Items in A with no counterpart in B flow to a «kun i A» sink, and vice versa.
- **drill-down**: Click a ribbon for the mapping table (kap/post → COFOG code).
- **honesty**: Exposes the crosswalk itself. Where the mapping is a crosswalk published by SSB it is offisiell; where it is the site's own allocation it is utledet (hatched ribbons).
- **unit handling**: kr.
- **mobile**: vertical.
- **complexity**: M
- **reuse**: `sankey`

### `rec-timeline-gap` — Avviket over tid
- **type**: timeline
- **description**: Lines for Total A and Total B over the available range, with the gap shaded. A lower panel breaks the gap down into the bridge items as a stacked area, with the residual on top in grey. For employment, the same compares AKU sysselsatte with register sysselsatte. There the gap breaks down into foreign commuters, the age bounds (15–74 vs 15–89), the reference week, and so on.
- **drill-down**: Click a year to open `rec-bridge-waterfall` for that year.
- **honesty**: Growth of the residual over time is information in itself (the crosswalk drifting). Show each line only where the series exists; don't extend it.
- **unit handling**: kr/persons, % of Total A.
- **mobile**: fine.
- **complexity**: S
- **reuse**: `timeseries`

### `rec-euler-defs` — Definisjonene som mengder
- **type**: snapshot
- **description**: Euler diagram of what each source *covers*, not of amounts. For example statsbudsjett ∩ offentlig forvaltning (COFOG) ∩ SHA, or AKU ∩ register ∩ registrert ledig hos NAV. Areas are scaled by kr or persons where available; otherwise the diagram is schematic and labelled «skjematisk».
- **drill-down**: Click a region to see the items that belong to it.
- **honesty**: Must be labelled schematic when it isn't proportional. A timeline isn't meaningful here.
- **unit handling**: kr, persons, or none.
- **mobile**: fine.
- **complexity**: M
- **reuse**: `euler-upset`

---

## (a) Shared generic view modules

| Module | Built on | Serves |
|---|---|---|
| `hier-bars` | Plot barX + d3 transitions, breadcrumb, paired vedtatt/regnskap, stacked mode | `utg-hier-bars`, `innt-stacked-bars`, `rec-parallel-bars`, `ssys-cumulative-bars` (detail); drill target for the side panels of the sankey, treemap, ring and waterfall views |
| `treemap` | zoomable d3.treemap | `utg-treemap` |
| `sunburst` | d3.partition arcs; a single ring = donut | `utg-sunburst`, `innt-donut-pair`, `makro-donut-pair`, `ssys-rings` (arc primitives) |
| `icicle` | d3.partition rects, mixed-dimension columns | `utg-icicle` |
| `sankey` | d3-sankey, horizontal/vertical, keyed transitions, dashed «also»/gjennomstrømning ribbons | `flow-sankey`, `flow-alluvial-time`, `bef-sankey-status`, `rec-sankey-bridge` |
| `waterfall` | Plot rects with running total, reference lines, residual step | `innt-waterfall`, `flow-waterfall-year`, `ssys-cumulative-bars`, `rec-bridge-waterfall` |
| `waffle` / `unit-dots` | grid layout, partial or striped cells, keyed re-layout | `bef-waffle`, `bef-dot-units`, `ssys-waffle` |
| `timeseries` | Plot lines/areas/stacked/100 %/diverging/rank (bump), break markers, hatched forecast years, linked panels | `utg-streamgraph`, `utg-bump`, `innt-timeline-gap`, `flow-stacked-timeline`, `makro-bnp-lines`, `makro-export-stacked`, `makro-spu-vs-bnp`, `bef-stacked-timeline`, `ssys-timeline`, `rec-timeline-gap` |
| `small-multiples` | facet wrapper for any module, with shared scales | `flow-alluvial-time`, timeline variants of waterfall |
| `slope` | two-axis slope | `innt-slope`, `bef-slope-persons-aarsverk` |
| `marimekko` | mosaic layout | `makro-marimekko`, `ssys-marimekko-eier` |
| `euler-upset` | Euler in the style of venn.js for 3 sets or fewer, UpSet for more | `bef-euler`, `rec-euler-defs` |
| `rings` | thin wrapper on `sunburst` arcs, with containment logic | `ssys-rings` |
| `receipt` | scroll-driven list with a running total | `flow-receipt` (and a variant for utgifter) |

Every module accepts the same props, `{node, dim, year, unit, status, claimStyle}`, and emits `drill(path)` and `switchDim(path, dim)`. That makes views interchangeable at any node («vis som: søyler | flisekart | solstråle | istapp»).

## (b) Recommended default view per data type

1. **Utgifter**: `utg-hier-bars`. It's the most accurate to read and the cheapest to build, and the breadcrumb dropdown for switching dimension is clearest here. The treemap is the «picture» alternative, one click away.
2. **Inntekter**: `innt-waterfall`. It's the one view that explains oljekorrigert underskudd, strukturelt underskudd and handlingsregelen as one chain, and it is the view that shows how these concepts relate.
3. **Pengestrømmer**: `flow-sankey`. A question about flows deserves a flow chart, and gjennomstrømning as a separate ribbon is the honesty win.
4. **Makro**: `makro-bnp-lines`. The gap with and without oil over time is the core message, and a line chart carries it without distortion.
5. **Befolkning og sysselsetting**: `bef-waffle`. Animating the cells with the definition toggle is the most honest and most mobile-friendly way to show AKU vs register vs NAV. Link prominently to `bef-euler` for overlaps.
6. **Statlig sysselsetting**: `ssys-cumulative-bars`. The rings are the metaphor, but the cumulative bar with ring checkboxes lets the reader see how the «state share» depends on the definition. Show `ssys-rings` as the hero illustration above it.
7. **Avstemming**: `rec-bridge-waterfall`, with named bridge items and an «ikke forklart» residual that is always visible.

## (c) Shared UI controls for all views

- **Breadcrumb with a dimension dropdown per node** (`Utgifter › Helse ▾ › Stat ▾`). This is the one control that implements «switch dimension at any node». The «Vis som» chart-type switcher sits in the same spot.
- **Year picker / scrubber**: a single year for snapshots and a range for timelines. It says explicitly which years are regnskap and which are vedtatt or anslag.
- **Status toggle**: vedtatt | saldert | regnskap, with a badge always visible on the chart.
- **Unit selector**: kr løpende | kr faste (base year shown) | % av total | % BNP | % BNP Fastland | per innbygger | av hver 100-lapp. Units that are meaningless for a view are disabled (e.g. per innbygger for ranks).
- **Definition selector** where relevant: AKU | register | NAV; brutto | netto; full count | eierandelsvektet; Norge | inkl. utlandet.
- **Claim-level legend** (offisiell / utledet / estimat), drawn the same way on every chart, plus a «skjul estimater» toggle.
- **Source footer** with the SSB table id or document for every number, and a «vis tallene» table drawer (sorted, view only; no download or export) under each chart. This is the ultimate honesty fallback, and the mobile fallback for dense charts.
- **«Øvrig / ikke fordelt» always visible**, with a tooltip explaining what it contains.
- **A shared registry of break and regime markers** (reform years, definition changes) used by all timelines.
- **Permalink / copy-link button** reflecting the full URL state. **Back** restores the previous node with a reverse animation.
- **Compare mode** (pin a second year or a second source), feeding the `slope`, `small-multiples` and `rec-*` views.
- **Accessibility**: keyboard navigation of nodes, an `aria-label` with value and unit for each mark, a categorical palette that is safe for colour blindness, and transitions that respect reduced motion.
