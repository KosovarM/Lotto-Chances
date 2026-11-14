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

## Results and payouts for the receipt check

`src/lotto/results.py` reads the numbers, Superzahl, Spiel 77 / Super 6 numbers and the payouts (Gewinnquoten) of a single draw from WestLotto's public info service, the XML behind the "Gewinnzahlen und Quoten" page on westlotto.de:

```
https://www.westlotto.de/wlinfo/WL_InfoService?gruppe=ZahlenUndQuoten&spielart=LOTTO&historie=ja&datum=DD.MM.YYYY
```

- This is not a documented API. Responses are checked: the draw date must match the date asked for (the service answers unknown dates with the latest draw), there must be six different numbers from 1 to 49, and so on.
- A result is cached in `data/results/` only once all nine payouts are published. Before that it is fetched again on each check.
- If the service can't be reached, the numbers come from the draw-history CSV and the payouts are shown as unknown.
- All results are without guarantee. The check at a lottery outlet is binding.
