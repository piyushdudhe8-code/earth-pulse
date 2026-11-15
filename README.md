# EARTH PULSE — Earth Systems Trend Detective

A Streamlit MVP for exploring long-term trends in NASA POWER monthly meteorological data. Built for a student hackathon prototype.

## Included

- Home / hook screen
- Four investigation modes: seasonal comparisons, latest available monthly observation, historical trends, and the interactive Location Mode
- City, manual-coordinate, place search, pilot-location, or opt-in browser-geolocation selection
- Hemisphere-based seasons plus India's winter, pre-monsoon, monsoon, and post-monsoon periods; month groups can be customized in the UI
- NASA POWER monthly point API integration
- Monthly NASA POWER variables: temperature (`T2M`), corrected precipitation (`PRECTOTCORR`), relative humidity (`RH2M`), wind speed (`WS10M`), and surface solar radiation (`ALLSKY_SFC_SW_DWN`)
- Missing-value handling and monthly data completeness
- Raw monthly chart + annual seasonality-reduced trend chart
- Hamed–Rao modified Mann–Kendall test (serial-correlation variance correction; implemented with SciPy)
- Sen's slope and 95% confidence interval
- Three clearly labelled synthetic guided demos, including seasonal Nagpur, Maharashtra; API failures never fall back to synthetic data
- A "Run a real investigation" path from Demo Lab to the NASA-backed investigation workflow
- Investigation results report the selected coordinates, NASA product/source metadata, requested and observed periods, latest valid observation, units, missing-observation count, coverage, spatial resolution, and analysis method
- Parameter-specific "What does this mean?" guidance distinguishes observed patterns from causes, impacts, and limitations
- Two-city comparison with Benjamini–Hochberg FDR adjustment
- Downloadable plain-text investigation report
- English / Hindi UI toggle
- Persistent Back navigation on inner pages
- Three.js raycasting sends clicked globe coordinates through a Streamlit custom component; Natural Earth polygons identify land countries and ocean clicks remain country-free
- Country estimates sample up to five points inside the selected boundary, deduplicate identical rounded request coordinates, and report the sample count and unweighted aggregation method
- Location Mode retains a selected marker, search/GPS/manual/pilot paths, six daily NASA POWER signals, and monthly plus annual historical charts
- The interactive globe keeps the existing Blue Marble base, loads Esri World Imagery tiles as zoom increases, and limits tile/camera zoom to the provider's published maximum level
- Six NASA POWER daily signals: air temperature, corrected precipitation, relative humidity, surface soil moisture, 10 m wind speed, and surface shortwave radiation
- Location-aware monthly charts, missing-data disclosure, grid/source metadata, and cautious trend results
- Optional audience context and session-only user feedback

## Important scientific choices

1. **NASA POWER is not a street-level weather station.** The meteorological series are gridded analysis-ready data derived primarily from NASA GMAO MERRA-2. Explain this in the pitch.
2. **The Real-Time mode is not instantaneous.** It displays the latest valid monthly observation returned by NASA POWER and separately reports when the app retrieved the response. Availability is periodically updated by NASA; it is not a live sensor reading.
3. **Seasonality:** the seasonal mode uses hemisphere-based meteorological month groupings. Monsoon is only offered for South Asia (June–September); tropical regions may use local wet/dry calendars not represented here. The trend test continues to use annual aggregates.
4. **Autocorrelation:** the trend test uses Hamed–Rao modified Mann–Kendall on the annual series. A lag-1 autocorrelation diagnostic is also shown. This is not a full model of every possible temporal dependency.
5. **Rainfall units:** NASA POWER's monthly `PRECTOTCORR` product is a mean daily precipitation rate. The app multiplies by the number of calendar days in each month to estimate monthly and seasonal totals.
6. **Statistical ≠ practical importance; correlation ≠ causation.** A non-significant result is not proof of no change.
7. **Demo data are synthetic.** They are labelled “Synthetic demonstration data — not actual environmental observations.” They must not be described as NASA observations, and a NASA request failure never switches to demo values.
8. **Compare mode:** Benjamini–Hochberg correction is applied to the two selected p-values.
9. **Location Mode:** daily observations are requested only after the user confirms a selected location. GPS is opt-in and refreshed without reusing a browser-cached fix. Place search and reverse geocoding use OpenStreetMap Nominatim; geocoding results are attributed.
10. **Country aggregates are estimates:** the app samples several request coordinates inside a Natural Earth country boundary and averages valid NASA POWER point estimates. It deduplicates only identical rounded request coordinates. NASA POWER point responses report the requested coordinate, not a snapped grid-cell center, so the app cannot verify whether samples resolve to distinct cells or whether a source cell straddles the boundary. This is not a one-point national result, an area-weighted statistic, or a substitute for subnational climate data. Small territories may not support a multi-point aggregate.
11. **Geographic resolution:** the bundled Natural Earth Admin-0 1:110m boundary polygons are generalized and are not suitable for disputed or detailed local borders. Country detection is polygon-based, not inferred from latitude/longitude ranges.
12. **Imagery:** the globe uses a Blue Marble base texture and Esri World Imagery tiles for closer views. Tile requests require an internet connection and are bounded by the maximum level published by the imagery service; the globe remains usable with the base texture if tiles are unavailable.
13. **Product compatibility:** the explorer uses NASA POWER `PRECTOTCORR` for precipitation and reports its source; NASA IMERG is a separate higher-resolution product and is not mixed into that series. Soil moisture uses `SFMC` only when NASA returns valid data; it is never filled from another soil-moisture product or fabricated before 2015.
14. **Resolution and coverage:** POWER point responses return the requested point coordinate and source metadata, not the underlying snapped grid-cell center. Meteorological data are generally on a 0.5° × 0.625° source grid, solar data on a 1° grid, and SMAP L4 soil moisture is about 9 km only when the response identifies SMAP. These are gridded estimates, not farm or station measurements.
15. **Solar trends:** solar observations are available, but neither the monthly historical workflow nor Location Mode reports a statistical trend for solar because POWER concatenates satellite products with source transitions that can affect long-term trend interpretation.
16. **Pilot locations:** [earth_pulse/pilot_locations.json](earth_pulse/pilot_locations.json) contains editable test points. They are candidates, not rankings or claims about operational agricultural holdings, commodity arrivals, or market prominence.

## Run on Windows (PowerShell)

Open PowerShell in this folder and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_and_run.ps1
```

The script uses the `python` command on your PATH to create `.venv`, install the dependencies, and launch the app.

Manual setup:

```powershell
python -m venv .venv
$venvScripts = (Resolve-Path ".\.venv\Scripts").Path
$env:Path = $venvScripts + ";" + $env:Path
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## NASA POWER endpoint used

`https://power.larc.nasa.gov/api/temporal/monthly/point`

The app makes one point request per selected variable and caches API results in the Streamlit process for 24 hours. Monthly `PRECTOTCORR` is a mean daily rate; EARTH PULSE estimates monthly accumulation by multiplying by the calendar-day count. NASA's returned sources, parameter metadata, fill value, time standard, and API version are retained with the series.

Official documentation: https://power.larc.nasa.gov/docs/services/api/temporal/monthly/

The additive Location Explorer uses `https://power.larc.nasa.gov/api/temporal/daily/point` with UTC time standard and a 24-hour in-process cache. It supports NASA POWER's daily `T2M`, `PRECTOTCORR`, `RH2M`, `SFMC`, `WS10M`, and `ALLSKY_SFC_SW_DWN` mappings. A parameter may return only fill values for a particular location or period; such data are reported as unavailable.

NASA methodology describes MERRA-2 meteorological source resolution as 0.5° × 0.625°, solar source resolution as 1° × 1°, SMAP L4 soil moisture as approximately 9 km from 2015 onward, and IMERG precipitation as 0.1° daily data. IMERG is not silently combined with POWER `PRECTOTCORR`; adding it requires a separately validated request pathway and source-aware chart metadata:

- https://power.larc.nasa.gov/docs/methodology/data/sources_meteorology/
- https://power.larc.nasa.gov/docs/methodology/data/sources_fluxes/
- https://power.larc.nasa.gov/docs/methodology/data/sources_hydrology/

Place search and reverse geocoding use OpenStreetMap Nominatim with a one-request-per-second process-wide limit and an identifying User-Agent. Search text is sent only after the user submits a search; device coordinates are used for reverse geocoding only after the user confirms that lookup. OpenStreetMap attribution is required when displaying geocoded results.
