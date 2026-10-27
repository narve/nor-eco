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

## URL state
`?view=<view-id>&year=<yyyy>&unit=<unit-id>&status=<status>&def=<definition-id>&path=<dim>:<code>/<dim>:<code>`
Each path segment means «split the previous node by this dimension, select this code».
