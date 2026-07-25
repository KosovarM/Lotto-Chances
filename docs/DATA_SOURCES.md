# Data sources — Lotto 6aus49

## Primary (production fetch)

| Field | Value |
|-------|-------|
| Name | daowa89/lottery-archive |
| URL | https://github.com/daowa89/lottery-archive |
| Raw CSV | https://raw.githubusercontent.com/daowa89/lottery-archive/main/de/lotto_6aus49/results.csv |
| Format | `date,n1,n2,n3,n4,n5,n6,superzahl` |
| Coverage | 1955 → present (updated on draw days) |
| License | See upstream repository |

The app filters this file to the **last 365 days** and caches locally at `data/draws_cache.csv`.

## Fallback

| Name | URL |
|------|-----|
| LottoNumberArchive JSON | https://johannesfriedrich.github.io/LottoNumberArchive/Lottonumbers_tidy_complete.json |

## Official (manual) references

- [Sachsenlotto download archive](https://www.sachsenlotto.de/portal/zahlen-quoten/gewinnzahlen/download-archiv/gewinnzahlen_download.jsp)
- [WestLotto downloads](https://www.westlotto.de/service/downloads/downloads.html)

## Disclaimer

Historical frequency data is for statistics and learning only. Draws are independent; past results do not predict future outcomes.

See also: Obsidian vault `70 Documentation/Research/2026-07-25 — Lotto 6aus49 data sources.md`
