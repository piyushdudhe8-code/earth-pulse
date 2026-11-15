from __future__ import annotations

from typing import Any


PARAMETER_INTERPRETATIONS: dict[str, dict[str, str]] = {
    "T2M": {
        "measured": "Monthly mean air temperature about 2 metres above the surface.",
        "rising": "The monthly or annual average is increasing over the selected period.",
        "falling": "The monthly or annual average is decreasing over the selected period.",
        "matters": "Temperature patterns can provide context for heat exposure and environmental change.",
        "cannot_tell": "This trend alone cannot identify a cause, establish global warming, or describe every street-level condition.",
        "limitations": "NASA POWER is gridded model data, not a local thermometer; annual aggregation can hide extremes.",
    },
    "PRECTOTCORR": {
        "measured": "Corrected precipitation. Monthly values are estimated by multiplying NASA POWER's mean daily rate by calendar days.",
        "rising": "Estimated precipitation accumulation is increasing over the selected period.",
        "falling": "Estimated precipitation accumulation is decreasing over the selected period.",
        "matters": "Long-term precipitation patterns can help describe changes in water input to a region.",
        "cannot_tell": "A rainfall trend alone cannot predict floods, drought impacts, or the timing and intensity of individual storms.",
        "limitations": "Monthly totals smooth short intense events; values are estimates derived from a gridded product and are not gauge totals.",
    },
    "RH2M": {
        "measured": "Monthly mean relative humidity near 2 metres above the surface, expressed as a percentage.",
        "rising": "The air is, on average, closer to saturation relative to its temperature.",
        "falling": "The air is, on average, farther from saturation relative to its temperature.",
        "matters": "Relative humidity helps describe atmospheric moisture conditions and can add context to heat and comfort.",
        "cannot_tell": "Relative humidity alone does not measure the total amount of water vapour, rainfall, or drought.",
        "limitations": "Relative humidity depends on both water vapour and temperature; the series is gridded, not a local sensor record.",
    },
    "WS10M": {
        "measured": "Monthly mean wind speed about 10 metres above the surface.",
        "rising": "The average wind speed is increasing over the selected period.",
        "falling": "The average wind speed is decreasing over the selected period.",
        "matters": "Wind-speed patterns can provide context for atmospheric mixing and local environmental conditions.",
        "cannot_tell": "Mean speed does not describe wind direction, gusts, damaging events, or conditions at a specific site.",
        "limitations": "Monthly and annual averages smooth short-lived events; NASA POWER values are gridded estimates.",
    },
    "SFMC": {
        "measured": "NASA POWER's surface soil-moisture parameter, when the requested product returns valid values.",
        "rising": "The estimated surface layer is wetter on average over the selected period.",
        "falling": "The estimated surface layer is drier on average over the selected period.",
        "matters": "Surface moisture can describe near-surface environmental conditions.",
        "cannot_tell": "It does not establish root-zone water, field conditions, crop needs, or irrigation requirements.",
        "limitations": "Availability depends on the returned NASA product and period; missing values are not filled from another dataset.",
    },
    "ALLSKY_SFC_SW_DWN": {
        "measured": "Mean daily downward shortwave solar energy reaching the surface under all-sky conditions.",
        "rising": "The estimated daily solar energy reaching the surface is increasing over the selected period.",
        "falling": "The estimated daily solar energy reaching the surface is decreasing over the selected period.",
        "matters": "It describes surface solar-energy availability under observed sky conditions.",
        "cannot_tell": "It does not directly measure air temperature, electricity generation, or the cause of a change.",
        "limitations": "The NASA POWER solar record combines source products across time; transitions can affect long-term trend interpretation.",
    },
}


def parameter_interpretation(parameter: str) -> dict[str, str] | None:
    """Return plain-language context for a NASA POWER parameter."""
    details: Any = PARAMETER_INTERPRETATIONS.get(parameter)
    return details.copy() if details else None
