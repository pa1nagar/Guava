"""
irrigation_calc.py — Deterministic irrigation runtime calculator.

Pure function; no database access.  All arithmetic that touches irrigation
scheduling happens here so it is trivially unit-testable.

Formula (Requirement 11.1):
    net_water   = ET0 × Kc × effective_area   (litres; 1 mm over 1 m² = 1 L)
    gross_water = net_water / system_efficiency
    total_flow  = emitter_count × emitter_flow
    runtime     = gross_water / total_flow

Validation (Requirements 11.3, 11.4):
    - Every required numeric input must be > 0.
    - system_efficiency must be in the open-closed interval (0, 1.0].
    - Any violation raises ValueError naming the offending field.

Functions
---------
compute_irrigation(inp: IrrigationInput) -> IrrigationResult
"""

from __future__ import annotations

from dataclasses import dataclass


FORMULA_VERSION = "1.0"


@dataclass
class IrrigationInput:
    """Inputs for the irrigation runtime calculation.

    Field ranges (Requirement 11.1):
        et0                0.01–25 mm/day   (reference evapotranspiration)
        kc                 0.10–2.00        (crop coefficient)
        effective_area     0.01–1000 m²     (effective canopy area)
        system_efficiency  (0, 1.0]         (drip system efficiency)
        emitter_count      1–10,000         (number of working emitters)
        emitter_flow       0.1–100 L/hour   (emitter flow rate)
    """

    et0: float                # Reference evapotranspiration (mm/day)
    kc: float                 # Crop coefficient
    effective_area: float     # Effective canopy area (m²)
    system_efficiency: float  # Drip system efficiency (0 < eff <= 1.0)
    emitter_count: int        # Number of emitters
    emitter_flow: float       # Emitter flow rate (litres/hour)
    formula_version: str = FORMULA_VERSION


@dataclass
class IrrigationResult:
    """Result of the irrigation runtime calculation.

    All inputs are echoed back alongside the intermediates (with units) and
    the final runtime so the caller can display every value transparently
    (Requirement 11.2).
    """

    # All inputs echoed back
    et0: float
    kc: float
    effective_area: float
    system_efficiency: float
    emitter_count: int
    emitter_flow: float
    # Intermediates (with units)
    net_water_litres: float            # ET0 × Kc × effective_area
    gross_water_litres: float          # net_water / system_efficiency
    total_flow_litres_per_hour: float  # emitter_count × emitter_flow
    # Final result
    runtime_hours: float               # gross_water / total_flow
    formula_version: str


def compute_irrigation(inp: IrrigationInput) -> IrrigationResult:
    """Compute irrigation runtime from measured field inputs.

    Raises ValueError when any required input is <= 0 or when
    system_efficiency is outside the interval (0, 1.0].
    The error message always names the offending field (Requirements 11.3, 11.4).
    """
    # ── Validate all required inputs (Requirement 11.3) ──────────────────────
    if inp.et0 <= 0:
        raise ValueError("et0 must be greater than 0")
    if inp.kc <= 0:
        raise ValueError("kc must be greater than 0")
    if inp.effective_area <= 0:
        raise ValueError("effective_area must be greater than 0")
    if inp.emitter_count <= 0:
        raise ValueError("emitter_count must be greater than 0")
    if inp.emitter_flow <= 0:
        raise ValueError("emitter_flow must be greater than 0")

    # ── Validate system_efficiency range (Requirement 11.4) ───────────────────
    # Must be in (0, 1.0] — greater than 0 and at most 1.0.
    if inp.system_efficiency <= 0 or inp.system_efficiency > 1.0:
        raise ValueError(
            "system_efficiency must be greater than 0 and at most 1.0"
        )

    # ── Compute intermediates (Requirement 11.1) ──────────────────────────────
    # 1 mm of water over 1 m² = 1 litre, so ET0 × Kc × area gives litres directly.
    net_water = inp.et0 * inp.kc * inp.effective_area
    gross_water = net_water / inp.system_efficiency
    total_flow = inp.emitter_count * inp.emitter_flow
    runtime = gross_water / total_flow

    return IrrigationResult(
        et0=inp.et0,
        kc=inp.kc,
        effective_area=inp.effective_area,
        system_efficiency=inp.system_efficiency,
        emitter_count=inp.emitter_count,
        emitter_flow=inp.emitter_flow,
        net_water_litres=net_water,
        gross_water_litres=gross_water,
        total_flow_litres_per_hour=total_flow,
        runtime_hours=runtime,
        formula_version=inp.formula_version,
    )
