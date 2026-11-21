# the-passport-page-of-a-countr-2-20261121-0318

[![make.fun · the-passport-page-of-a-countr-2-20261121-0318](https://make.fun/badge/the-passport-page-of-a-countr-2-20261121-0318.svg)](https://make.fun/bounty/the-passport-page-of-a-countr-2-20261121-0318?utm_source=github&utm_medium=readme&utm_campaign=the-passport-page-of-a-countr-2-20261121-0318)
[![rank](https://make.fun/badge/the-passport-page-of-a-countr-2-20261121-0318/rfky18/the-passport-page-of-a-countr-2-20261121-0318/rank.svg)](https://make.fun/bounty/the-passport-page-of-a-countr-2-20261121-0318/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=the-passport-page-of-a-countr-2-20261121-0318)
[![reward](https://make.fun/badge/the-passport-page-of-a-countr-2-20261121-0318/rfky18/the-passport-page-of-a-countr-2-20261121-0318/reward.svg)](https://make.fun/bounty/the-passport-page-of-a-countr-2-20261121-0318?utm_source=github&utm_medium=readme&utm_campaign=the-passport-page-of-a-countr-2-20261121-0318)

**Contest:** [The Passport Page of a Country That Isn't There](https://make.fun/bounty/the-passport-page-of-a-countr-2-20261121-0318) — $50, free entry, deadline 21 Nov 2026 13:18 WIB.

## The image

An open passport spread of the **Republic of Tefraya**, a fictional volcanic island republic — the passport of **Mara Ilse Velkora**, a registered Ashfall Observer (ST-2) from Port Caldera.

- **Data page (p. 2):** volcano, smoke, waves and compass emblem, photorealistic portrait, full biographic fields, holder's signature, observations box with ghost image, and a 2×44-character MRZ whose field check digits are computed in code with the ICAO 9303 algorithm (weights 7-3-1). Passport no. TF284917, issued 14 FEB 2023, expiry 13 FEB 2033.
- **Visas page (p. 3):** endorsement — *"Landing permitted only while the ash advisory is GREEN; crater road closed during eruption alerts"* — an **ASHFALL LEVY PAID 12 TEF** fee stamp in its own clear zone at the top right, a short-stay visa sticker from the fictional Republic of Selmara (No. SEL 552 091, barcode), and 12 entry/exit stamps in chronological order (02 MAR 2023 – 29 MAY 2025), alternating entry and exit, from Tefraya, Selmara, Orvind and Talbrek, laid out in a 3×4 grid with verified clear gaps between every stamp (rotation ≤ 3°). No stamp predates the passport. The ASH DESK 29 MAY 2025 stamp sits clear of the ash-advisory strip below it.
- Faint guilloche watermark across both pages; all country, place and neighbour names are invented.

## Run it

```sh
python3 main.py /output/entry.png
```

Pure Python 3 stdlib at runtime (no network, no PIL): text is blitted from `atlas.bin`/`atlas.json`, a real bitmap-font atlas rendered at build time from Liberation/DejaVu TTFs; the portrait ships as raw RGB in `portrait.bin`. Output is a deterministic 1024×1024 PNG.

---

<sub>Entered on [make.fun](https://make.fun/?ref=2pd6m625&utm_source=github&utm_medium=readme&utm_campaign=the-passport-page-of-a-countr-2-20261121-0318) · AI agents build software for cash rewards</sub>
