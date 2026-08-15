"""Parametric ramp-scenario data builder for firmware V100R001C21SPC116
(see invforge/core/generator.py). Returns the same static:/timeseries:
shape a hand-written scenario YAML parses into -- Scenario itself can't
tell the difference between this and a loaded YAML.

Power for the ramp is derived from the rated capacity and the SoC delta
over the requested duration (constant-power discharge/charge assumption)
rather than a hand-picked constant -- physically consistent with the
SoC ramp it accompanies. Since only two timeseries samples are given
(start, end) as elsewhere in this profile's synthetic fixtures, the
reported power interpolates linearly from that constant value down to 0
over the ramp rather than staying flat until the very last instant -- an
accepted simplification; battery.charge tracking is the primary signal
these scenarios exercise, not power-reading fidelity.
"""

from __future__ import annotations

from invforge.core.generator import RampParams

_RATED_CAPACITY_KWH = 18.0  # matches this firmware's other synthetic fixtures' 30083 (gain 100 -> raw 1800)


def build_ramp_scenario_data(params: RampParams) -> dict[str, object]:
    energy_used_kwh = _RATED_CAPACITY_KWH * abs(params.start_pct - params.end_pct) / 100.0
    power_kw = energy_used_kwh / (params.duration_s / 3600.0)
    sign = -1 if params.direction == "drain" else 1
    power_raw = sign * round(power_kw * 1000)

    return {
        "static": {
            "unit_247": {
                30047: 8800,  # ess_avail_max_charge_power (gain 1000 -> 8.8 kW)
                30049: 9600,  # ess_avail_max_discharge_power (gain 1000 -> 9.6 kW)
                30064: 1800,  # ess_avail_max_charge_capacity (gain 100 -> 18.0 kWh)
                30066: 1800,  # ess_avail_max_discharge_capacity (gain 100 -> 18.0 kWh)
                30068: 8800,  # ess_rated_charge_power
                30070: 9600,  # ess_rated_discharge_power
                30083: 1800,  # ess_rated_energy_capacity (gain 100 -> 18.0 kWh)
                30085: 1000,  # ess_charge_cutoff_soc (gain 10 -> 100.0%)
                30086: 100,  # ess_discharge_cutoff_soc (gain 10 -> 10.0%)
                30087: 980,  # ess_soh (gain 10 -> 98.0%)
            },
            "unit_1": {
                30500: "SigenStor SYNTHETIC-GENERATED",
                30515: "SYNTH-GEN-0001",
                30525: "0.0.0-synthetic",
            },
        },
        "timeseries": [
            {
                "t": 0,
                30004: 1,  # grid_sensor_status
                30005: 0,  # grid_active_power
                30009: 1,  # on_off_grid_status (off-grid/EPS)
                30014: round(params.start_pct * 10),  # ess_soc
                30027: 0,
                30028: 0,
                30029: 0,
                30030: 0,
                30035: 0,  # pv_plant_power
                30037: power_raw,  # ess_power
                30051: 1,  # plant_running_state
                30072: 0,
                30280: 0,
            },
            {
                "t": params.duration_s,
                30014: round(params.end_pct * 10),  # ess_soc
                30037: 0,  # ess_power -- ramp complete, no further charge/discharge
            },
        ],
    }
