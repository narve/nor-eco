# Test fixtures

- `jsonstat2_ssb_07459_sample.json`: a real, tiny JSON-stat2 response from SSB table 07459
  (Befolkning, hele landet, alder 0 og 1 år, to siste år), fetched via PxWebApi v2. Used only to test
  the parser. Source: Statistisk sentralbyrå, CC BY 4.0.
- `synthetic/`: **syntetiske testdata, ikke ekte tall.** A small processed-data tree (series + hierarchical
  dataset with an «Øvrig» node, a series break and an estimat) plus its own source registry. Used by the
  schema, build and (later) view tests.
