# warujie-prices

Daily MTG price history for 悪知恵 (warujie), published with GitHub Pages at https://luminarc7.github.io/warujie-prices/ and read by the site.

- `build_prices.py` builds the data (Scryfall: TCGplayer USD, Cardmarket EUR; MTGJSON: past prices and today's shop prices).
- `.github/workflows/update-prices.yml` runs it every day at 12:17 UTC and publishes the result. Nothing is committed, so the repository never grows.
