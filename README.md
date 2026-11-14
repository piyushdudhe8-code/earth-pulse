# EARTH PULSE — Earth Systems Trend Detective

A Streamlit MVP for exploring long-term trends in NASA POWER monthly meteorological data. Built for a student hackathon prototype.

## Included

- Home / hook screen
- Investigation form: variable, Indian city or custom coordinates, start year
- NASA POWER monthly point API integration
- Variables: temperature (`T2M`), corrected precipitation (`PRECTOTCORR`), relative humidity (`RH2M`), wind speed (`WS10M`)
- Missing-value handling and monthly data completeness
- Raw monthly chart + annual seasonality-reduced trend chart
- Hamed–Rao modified Mann–Kendall test (serial-correlation variance correction; implemented with SciPy)
- Sen's slope and 95% confidence interval
- Two clearly labelled synthetic guided demos and synthetic fallback if the API fails
- Two-city comparison with Benjamini–Hochberg FDR adjustment
- Downloadable plain-text investigation report
- English / Hindi UI toggle

## Important scientific choices

1. **NASA POWER is not a street-level weather station.** The meteorological series are gridded analysis-ready data derived primarily from NASA GMAO MERRA-2. Explain this in the pitch.
2. **Seasonality:** this MVP uses annual aggregates for the trend test instead of STL. Average variables are day-weighted within each year; rainfall totals are summed. This reduces the regular within-year seasonal cycle.
3. **Autocorrelation:** the trend test uses Hamed–Rao modified Mann–Kendall on the annual series. A lag-1 autocorrelation diagnostic is also shown. This is not a full model of every possible temporal dependency.
4. **Rainfall units:** NASA POWER's monthly `PRECTOTCORR` product is a mean daily precipitation rate. The app multiplies by the number of calendar days in each month to estimate a monthly total. The report explicitly records this conversion.
5. **Statistical ≠ practical importance; correlation ≠ causation.** A non-significant result is not proof of no change.
6. **Demo data are synthetic.** They are always marked `DEMO DATA` and must not be described as NASA observations.
7. **Compare mode:** Benjamini–Hochberg correction is applied to the two selected p-values.

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

The app makes one point request per selected variable and caches API results in the Streamlit process for 24 hours.

Official documentation: https://power.larc.nasa.gov/docs/services/api/temporal/monthly/
