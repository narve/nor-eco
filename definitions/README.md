# Definitions

One YAML file per topic (`definitions/<topic>.yaml`), used for the «Hva telles?» boxes, the
«Ofte blandet sammen» sections and `begreper.html`:

```yaml
definitions:
  - id: aku-sysselsatt            # stable slug
    term: Sysselsatt (AKU)
    quote: "«…ordrett sitat fra kilden…»"
    source_id: ssb-aku-om         # must exist in sources/registry.yaml
    # optional: page, locator (section / "Om statistikken" heading)
```

Quotes are verbatim and in the source's own wording. Every entry needs a `source_id` whose registry
`url` points to the exact page or table.
