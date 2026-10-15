"""Health Canada's Daily Values, the one reference for every calculated %DV (F2, F3).

Shared by the whole-package calculation (#36) and the per-serving %DV
interpretation (#37), so both always use the same table and version.
"""

from __future__ import annotations

from types import MappingProxyType

DAILY_VALUES_TITLE = (
    "Table of Daily Values: Part 1, foods for adults and children 4 years of age or older"
)
DAILY_VALUES_URL = (
    "https://www.canada.ca/en/health-canada/services/technical-documents-labelling-requirements/"
    "table-daily-values/nutrition-labelling.html"
)
# The version adopted by the team (F3). The previous one is dated 2016-12-14.
DAILY_VALUES_VERSION = "2022-10-20"

# Model nutrient -> Daily Value in the nutrient's canonical unit (``CANONICAL_UNITS``).
# Calories, carbohydrate and protein have no Daily Value, so they never get a %DV.
# Health Canada gives one Daily Value for saturated and trans fat together; its %DV
# is reported on ``saturated_fat``, as on the printed label, and ``trans_fat`` has none.
DAILY_VALUES: MappingProxyType[str, float] = MappingProxyType(
    {
        "total_fat": 75,
        "saturated_fat": 20,
        "cholesterol": 300,
        "sodium": 2300,
        "fibre": 28,
        "sugars": 100,
    }
)

# Nutrients whose amounts are added up before comparing with their Daily Value.
COMBINED_DAILY_VALUES: MappingProxyType[str, tuple[str, ...]] = MappingProxyType(
    {"saturated_fat": ("saturated_fat", "trans_fat")}
)


def daily_value_percent(name: str, amounts: dict[str, float | None]) -> float | None:
    """Unrounded %DV of ``name`` from ``amounts`` (one basis, canonical units).

    None when the nutrient has no Daily Value, or when any amount its Daily Value
    covers is unknown: a combined %DV is never calculated from part of its sum.
    """
    reference = DAILY_VALUES.get(name)
    if reference is None:
        return None
    parts = [amounts.get(part) for part in COMBINED_DAILY_VALUES.get(name, (name,))]
    if any(part is None for part in parts):
        return None
    return sum(parts) / reference * 100
