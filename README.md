# Norsk statsøkonomi – fra kildene

Statisk nettsted (bokmål) om statsbudsjettet, økonomien med og uten olje og gass, og sysselsetting.
Alle tall kommer fra offisielle kilder og har en kildehenvisning. Nettstedet er ikke en offisiell kilde
og tilbyr ingen nedlasting. Plan: [`docs/PLAN.md`](docs/PLAN.md). Visningskatalog:
[`docs/VISUALIZATIONS.md`](docs/VISUALIZATIONS.md). Dataformater: [`schema/README.md`](schema/README.md).

## Sider
`statsbudsjett`, `okonomi`, `sysselsetting` og `staten-som-arbeidsgiver`, pluss `begreper`, `kilder`, `metode` og `galleri/`
(alle visninger side om side, med samme data). Hvert diagram har en forklaring, en kildelinje og en tabell med tallene.
Ikke dekket, og oppgitt på sidene og i `metode`: offentlig finansierte private tilbydere og tiltak i NAV, ansatte i Norge
kontra utlandet, og SPU-historikk (bare siste tall vises). Verifiseringen er beskrevet i [`docs/VERIFICATION.md`](docs/VERIFICATION.md).

## Kommandoer

Krever [uv](https://docs.astral.sh/uv/) (Python ≥ 3.12). Alt bygges lokalt; `data/processed/` og
`site/` committes. GitHub Actions bygger ikke noe, den publiserer bare `site/`.

```sh
uv sync                                  # installer avhengigheter
uv run python -m fetch check             # hvilken SSB-API-versjon er oppe (v2 foretrekkes)
uv run python -m fetch all               # hent alle kilder -> data/raw
uv run python -m transform all           # data/raw -> data/processed
uv run python build.py                   # data/processed + templates -> site/
uv run python -m checks                  # hele den lokale porten (kjøres før push)
uv run python -m checks --install-hook   # kjør porten automatisk før git push
uv run pytest                            # enhetstester
uv run playwright install chromium       # én gang, for tests/e2e
uv run pytest tests/e2e                  # nettlesertester (360 px og 1280 px, under-sti)
python -m http.server -d site            # se resultatet lokalt
```

## Regler i korte trekk
- Hvert tall kommer fra `data/processed` og har `source_ids` som finnes i `sources/registry.yaml`.
- Tre nivåer: offisielt (heldekkende), utledet (skravert, «ƒ»), estimat (stiplet, «≈»).
- Bare relative lenker, slik at `site/` fungerer både på GitHub Pages (under-sti) og på eget domene.
- Filer i git er under 5 MB. PDF-er og andre filer som lett lastes ned igjen committes ikke; de står i
  `data/raw/MANIFEST.yaml` med sha256. Er et datasett for stort, droppes tidlige år.
- Byggingen er deterministisk (ingen tidsstempler), slik at `site/` bare endres når innholdet endres.
- Nøytral tone: sidetekst beskriver definisjoner og tall, ikke aktører.

## Struktur
```
sources/registry.yaml   alle kilder (id, utgiver, tittel, url, tabell-id, lisens)
definitions/            siterte offisielle definisjoner
fetch/                  common.py (http, snapshots, JSON-stat2), ssb.py (PxWebApi v2/v0)
transform/              schema.py (validering), format.py (norsk tallformat)
schema/                 JSON Schema + README om dataformatene og view-kontrakten
data/raw, data/processed
site_src/               templates, pages.yaml, assets (css, js, fonter, vendor/d3 + Plot)
site/                   bygget resultat (committes)
checks/                 lokal port: data, størrelse, tall i maler, lenker, ferskhet
tests/                  pytest + tests/e2e (Playwright) + fixtures (syntetiske testdata)
```
