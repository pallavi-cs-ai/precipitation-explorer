# Independent IFS GRIB2 validation

## Conclusion

The source-to-served-value checks found **no unit, geographic indexing, sampled-coordinate or UTC-boundary errors** at 14 tested locations (336 intervals). All served intervals exactly match independently computed differences **after the application’s negative-difference clipping rule**.

There is a real qualification: clipping negative packing differences to zero makes interval totals exceed the final cumulative field at some nearly dry points. Three of the four source-selected dry locations return a nonzero 72-hour total even though the source 72-hour field is zero. Therefore, **72-hour cumulative equality is not universally satisfied**. No application code was changed during this verification.

## Provenance and independence

- Audited run: `ifs-20261111T18Z-global1`, initialized 11 November 2026 at 18:00 UTC; horizon ends 14 November at 18:00 UTC.
- Downloaded the original 24 IFS `tp` forecast fields from ECMWF, explicitly pinned by date, initialization hour and steps 3–72. SHA-256 matches the live manifest exactly: `99fbdb2a2fa4b1071922813af1eca782aec97cb54a0748fbd12bb7cc21479723`.
- The earlier 12Z run was no longer retained by Render (404). This report validates the served 18Z run, not a potentially earlier CSV export.
- `scripts/validate_source_grib.py` imports **no application ingestion, transformation, rendering or sampling helpers**. It decodes GRIB directly with ecCodes, reconstructs the native grid from scan metadata, and calculates differences independently.
- API values are the values under test, not the reference. Reference values come from the downloaded GRIB2. Responses were captured from pinned run-specific endpoints; the report was then regenerated using those saved responses (`--cached`).
- As a second indexing check, ecCodes `codes_grib_find_nearest` independently found every sampled coordinate in every original field. Its raw values agreed with the metadata-derived row/column extraction exactly.

## Checks

1. **Units:** all source fields declare `m`. Multiplied by 1000 to obtain millimetres of water-equivalent precipitation. No rainfall-rate conversion was applied.
2. **Accumulation:** all fields declare `stepType=accum`, `startStep=0`; unique end steps are 3, 6, …, 72. The first interval is C(3)−0; each later interval is C(t)−C(t−3). Negative values are compared before and after clipping, rather than silently discarded by the audit.
3. **Grid:** native shape 721×1440, 0.25° increments, starting at 90°N/180°E, longitude increasing within north-to-south rows. Native row/column 2 and every fourth cell thereafter produce 1° centers at 89.5…−89.5° latitude and −179.5…179.5° longitude. This is subsampling, not a 1° area average.
4. **Sampling:** city requests map to independently calculated nearest 1° centers. East/west longitude normalization, both hemispheres and both sides of the date line were checked. Sampled coordinates matched all 14 API responses.
5. **Time:** initialization and GRIB validity date/time agree with UTC arithmetic. All 336 interval IDs, starts and ends match their three-hour windows, with no gaps or overlap. The first interval is 11 November 18:00–21:00 UTC; the last is 14 November 15:00–18:00 UTC.
6. **Numeric comparison:** maximum served-versus-independently-clipped interval difference = **0 mm**. Nearest-lookup-versus-row/column raw-source difference = **0 mm**. Wettest-interval amounts consequently match for these series; ties need not select a unique time.

## Point results

Signed coordinates are latitude, longitude. High/dry quadrant points were selected directly from the original 72-hour field among displayed 1° centers, not chosen using the API. Some are over oceans; they are geographic test points, not city forecasts.

| Location | Sampled coordinates | Source C(72), mm | Sum served intervals, mm | Difference, mm |
|---|---|---:|---:|---:|
| São Paulo | -23.5, -46.5 | 17.700195 | 17.700195 | +0.000000 |
| Fort William | 56.5, -5.5 | 2.563477 | 2.563477 | +0.000000 |
| Chennai | 13.5, 80.5 | 2.685547 | 2.685547 | +0.000000 |
| Sydney | -33.5, 151.5 | 7.324219 | 7.324219 | +0.000000 |
| Dateline east | 0.5, 179.5 | 16.113281 | 16.113281 | +0.000000 |
| Dateline west | 0.5, -179.5 | 12.817383 | 12.817383 | +0.000000 |
| High NE | 45.5, 14.5 | 210.083008 | 210.083008 | +0.000000 |
| Dry NE | 78.5, 18.5 | 0.000000 | 0.122070 | +0.122070 |
| High NW | 5.5, -131.5 | 181.274414 | 181.274414 | +0.000000 |
| Dry NW | 82.5, -82.5 | 0.000000 | 0.091553 | +0.091553 |
| High SE | -2.5, 85.5 | 164.916992 | 164.916992 | +0.000000 |
| Dry SE | -0.5, 47.5 | 0.000000 | 0.000000 | +0.000000 |
| High SW | -8.5, -158.5 | 323.364258 | 323.364258 | +0.000000 |
| Dry SW | -4.5, -33.5 | 0.000000 | 0.061035 | +0.061035 |

## Discrepancy: quantization and clipping

At dry NE, a late cumulative field decreases by 0.1220703125 mm; replacing that negative interval with zero produces a 0.1220703125 mm excess in the sum. The same mechanism produces 0.091552734375 mm at dry NW and 0.06103515625 mm at dry SW.

Across **all 64,800 retained grid centers and 24 steps**, the source scan contains 7,693 negative differences. The most negative is −0.1220703125 mm. Every decrease is within the sum of the adjacent GRIB packing-error bounds. Source packing error is 0.0152587890625–0.06103515625 mm per cumulative field.

Summing clipped differences can exceed C(72) by up to **0.213623046875 mm** on this complete sampled grid. This global maximum describes the mathematical effect of the current algorithm on the source, not a separate live-endpoint check at every cell. The 14 endpoint checks are listed above.

This is a packing-precision effect amplified by the nonnegative-difference rule, not a factor-of-1000 or wrong-location error. Nevertheless, small positive amounts should not be described as confidently wet when the final source accumulation is zero. A strict requirement that displayed 72-hour totals equal C(72) is currently unmet for these points. Correcting the reconstruction or explicitly disclosing this precision limit should be considered before claiming exact cumulative consistency. Neither option has been silently implemented during this verification.

## Reproduction and scope

Save a manifest and the matching pinned GRIB as `data/source-audit/manifest.json` and `source.grib2`. Run `.venv/bin/python scripts/validate_source_grib.py` while that run is served. `--cached` uses locally saved response snapshots from the same audit. The script fails on identity, geometry, time or conversion mismatches and separately reports total discrepancies caused by clipping.

`reports/source-grib-audit.json` contains field metadata and all 336 interval-level source/reference/served comparisons. Raw GRIB and downloaded API snapshots remain in ignored `data/`. This audit verifies data transformation for one real run; it is not an assessment of forecast accuracy against observations, nor verification of every map pixel or every future run.
