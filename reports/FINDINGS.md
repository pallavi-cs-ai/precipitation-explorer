# IFS exploration findings — 10 November 2026

## Verified sample

- Source: ECMWF primary Open Data server, using the official Python client.
- Run: 10 November 2026, 06:00 UTC (11:30 IST).
- Parameter: total precipitation (`tp`, parameter 228).
- Forecast hours: 3, 6, 9, 12; valid at 09:00, 12:00, 15:00, 18:00 UTC.
- Grid: regular latitude/longitude, 1440 × 721 points, global 0.25°.
- Download: 1,238,539 bytes for four selected GRIB messages. Original discovery and fetch took about 3.8 seconds; this is one measurement, not an SLA. Subsequent runs may use the local cache.
- Units: metres of water equivalent; multiply by 1000 for millimetres.
- All messages report accumulation beginning at hour zero. No missing grid values were reported; decoded values were finite.
- Mumbai, Pune, Chennai and Delhi nearest-grid-point totals were zero throughout these four intervals. This is a short forecast sample, not a claim about observed weather or later days.
- The chart also includes the regional grid point with the greatest 12-hour cumulative precipitation. It is selected from the data, may be over the ocean, and is not a city.

## Processing discovery

Some differences between successive cumulative fields were slightly negative due to independently packed GRIB values. The script permits clipping only within the sum of the two messages' decoded packing errors; larger decreases fail validation. The JSON records the counts, minimum raw differences and tolerances. This demonstrates why blindly treating cumulative values as interval amounts, or blindly clipping every negative, would be incorrect.

For the first 0–3 hour interval, zero is the accumulation baseline because the metadata explicitly identifies a zero-hour accumulation start. For later intervals we difference adjacent fields from the same run. Units are checked, not assumed.

## What the UI can show

1. A precipitation grid for a specific three-hour interval, labelled in mm/3h.
2. A location time series with the selected grid coordinates disclosed.
3. A cumulative amount over the available forecast window.
4. Wettest intervals and spatial patterns, with an explicit model/run/valid-time label.
5. Dry conditions as valid zero values, distinct from missing data.

The initial plot is a geographic grid inspection, not a production basemap. The final web overlay will need appropriate projection. Small amounts are limited by packing precision; avoid excessive decimal places.

## Still to verify before extending scope

- A complete 72-hour retrieval and refresh across runs.
- Deployment memory, persistent storage, and scheduling.
- Optional rate/type/snowfall fields: none were downloaded in this probe.
- Model skill: this sample is not an accuracy evaluation; no observations were used.

AWS returned HTTP 503 during discovery; primary ECMWF succeeded. The client defaults to very long retries, so the probe explicitly limits retries. A production fetcher should retain the last complete run during outages.

Source documentation: https://www.ecmwf.int/en/forecasts/datasets/open-data
Data attribution: ECMWF Open Data, CC BY 4.0. Visualization and processing are derived work.
