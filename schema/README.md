# Dataformater

Two processed formats share one metadata model (`source_ids`, `claim_level`, `derivation`, `breaks`,
`notes`, `price_basis`). `python -m checks` validates both against the schemas here.

## 1. Plain series: `data/processed/<topic>/<series>.json`
Schema: `series.schema.json`. For ordinary time series (BNP, SPU value, unemployment rate ...).

## 2. Hierarchical dataset: `data/processed/<topic>/<dataset>/`
- `dataset.yaml` (schema `dataset.schema.json`): title, unit, claim level, sources, ordered `dimensions`,
  optional `published_totals` to reconcile against.
- `dimensions.yaml` (schema `dimensions.schema.json`): one tree per dimension. A node with `other: true`
  is the explicit «Øvrig / ikke fordelt i kilden» node.
- `facts.csv`: columns `period,value,unit,status,<dimension ids...>,claim_level,source_id`.

Fact rules (enforced by `transform/schema.py`):
1. **Every row is fully specified**: one *leaf* code in every dimension. Dimensions that cannot be crossed
   with each other in the source belong in separate datasets (reconciled through a bridge), never as empty
   columns.
2. No duplicate key (period, status, all dimension codes).
3. All parent/child links resolve; each dimension is a single tree; `other` nodes are leaves.
4. Because rows are leaves, every node of every dimension automatically sums to its parent, and every
   dimension gives the same total. If `published_totals` is given, the sum per period/status must equal it
   within `tolerance`.
5. Every `source_id` exists in `sources/registry.yaml`.

## Published bundle: `site/data/<topic>/<dataset>.json`
`build.py` writes, per dataset: `{meta, dimensions, columns, rows}` where `rows` are arrays in `columns`
order (a compact columnar form of facts.csv). The dimension engine (WS5a) turns it into the `Node` tree
of `node.schema.json` for a given `path`, `dim`, `year`, `unit` and `status`. `facts.csv` itself is not
published or linked (the site offers no downloads).

## View contract
`node.schema.json` describes the `Node` every view receives. Props: `{node, dim, year, unit, status,
claimStyle}`. Events: `drill(path)` and `switchDim(path, dim)`.

## Time-series contract: `SeriesSet`
Timeline views receive `{title, unit, claim_level, series: [{id, label, other?, values: [{period, value, raw, status, claim}]}], breaks: [{period, note}], periods}`.
`engine.timeline()` builds it from a dataset (one series per child of the current node, split by the chosen
dimension); `engine.seriesSet()` builds it from plain series JSON. Gaps stay `null` and are never interpolated.

## Dimension engine (`site_src/assets/js/core/engine.js`)
View state is `{path, dim}`: `path` selects `dimension:code` filters (last code per dimension wins), `dim` is the
dimension the next level is split by. `nodeFor(ds, state)` returns the Node tree, `timeline(ds, state)` the SeriesSet,
`breadcrumb()` and `splittableDims()` feed the controls. Units: `raw`, `pct-parent`, `pct-total`, and `ratio`
units defined per chart (`% av BNP`, `kr per innbygger`) with a denominator series; a unit that does not apply
(for example `% av BNP` on fixed prices) is disabled with a reason.

## URL state
`?chart=<chart-id>&view=<view-id>&year=<yyyy>&unit=<unit-id>&status=<status>&def=<definition-id>&dim=<dim>&path=<dim>:<code>/<dim>:<code>`
Only the chart named by `chart` reads or writes the state, so a page can hold several charts.
Each path segment means «split the previous node by this dimension, select this code».

## Node fields beyond the basics
A node in `dimensions.yaml` may carry `other: true` (the explicit «Øvrig / ikke fordelt» leaf) or `overlap: [codes]`
(the leaf is a group that sits in the intersection of several named groups; the UpSet view draws it as a combination).
Node codes match `^[A-Za-z0-9_.-]+$`; source codes with other characters are mapped to a code in the transform.
Statuses are `regnskap`, `saldert`, `vedtatt`, `budsjett`, `forslag`, `anslag` and `foreløpig`; the engine indexes facts
by `period|status` and never adds statuses together. Preliminary values are drawn hatched.

## Chart config (`data-config` on `.chart-mount`)
Written in the page template through the `chart()` macro; `site_src/assets/js/mount.js` is the reference.
- `kind: dataset` (`url`), `series` (`urls[]`), `waterfall` (`steps[]`, each with `url`, `period`, `role`, optional `expected` checkpoint), or
  `flow` (`left`, `right` datasets, `mid` label, `gapLeft`/`gapRight` labels for the explicit difference band).
- `views[]`, `defaultView`, `units[]`, `unitDefs[]`, `denominators`, and for the marimekko `dim2` (the dimension that stacks the columns) and for the waffle `groups`.
- Every chart id must differ from every section id on the page (duplicate ids are caught by `checks/links.py`).
- Text nodes written into the DOM go through `fill()` or `put()` in `views/common.js`; passing `null` to `append()` writes the text «null».
