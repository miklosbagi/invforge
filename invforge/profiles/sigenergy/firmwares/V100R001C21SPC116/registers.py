"""Sigenergy SigenStor register table, unit 247 ("plant") and unit 1
("inverter"). Sourced from the official Sigenergy Modbus Protocol spec
(V2.5/V2.8/V2.9, see ../../../../../../sigennut/docs/register-map.md
and docs/vendor/ in that same repo for the full cross-version
verification) and cross-checked against real device captures (SigenStor
EC 12.0 TP, serial CMU110A144L0174, this firmware). Deliberately not the
full spec (~280 registers across both units, including PSS/PID/AC- and
DC-Charger sections, 24 smart loads, all 36 PV string slots) -- this is
the subset actually relevant to a UPS/battery-backup driver, matching
what this specific real installation has (3 PV strings, 2 battery
packs, 3-phase L1/L2/L3/N output, no smart-load metering, no grid CT
configured).

30281 (general_alarm7) is deliberately marked `dynamic` and included as
a real register -- earlier revisions of this table excluded it entirely
based on it always failing a solo (count=1) read. That conclusion was
wrong: the spec documents it as a real, independent register, and it
decodes real data (0xFFFF, an idle/no-alarm sentinel) when read as part
of a range starting at or before it. The actual firmware behavior --
confirmed empirically, unexplained by the spec text itself -- is that
this specific address is rejected as a read's *starting* address, even
though it's a legitimate register. See this profile's `__init__.py`,
which registers 30281 in `Profile.non_anchor_addresses` to reproduce
that quirk in the simulator rather than papering over it.
"""

from __future__ import annotations

from invforge.core.registers import DType, RegisterDef

PLANT_UNIT = 247
INVERTER_UNIT = 1
DEFAULT_UNIT = PLANT_UNIT

REGISTERS: list[RegisterDef] = [
    # ---- Unit 247 ("plant") -- static: ratings/config, unchanging within a scenario ----
    RegisterDef(30047, "ess_avail_max_charge_power", 2, DType.U32, PLANT_UNIT, gain=1000),
    RegisterDef(30049, "ess_avail_max_discharge_power", 2, DType.U32, PLANT_UNIT, gain=1000),
    RegisterDef(30064, "ess_avail_max_charge_capacity", 2, DType.U32, PLANT_UNIT, gain=100),
    RegisterDef(30066, "ess_avail_max_discharge_capacity", 2, DType.U32, PLANT_UNIT, gain=100),
    RegisterDef(30068, "ess_rated_charge_power", 2, DType.U32, PLANT_UNIT, gain=1000),
    RegisterDef(30070, "ess_rated_discharge_power", 2, DType.U32, PLANT_UNIT, gain=1000),
    RegisterDef(30083, "ess_rated_energy_capacity", 2, DType.U32, PLANT_UNIT, gain=100),
    RegisterDef(30085, "ess_charge_cutoff_soc", 1, DType.U16, PLANT_UNIT, gain=10),
    RegisterDef(30086, "ess_discharge_cutoff_soc", 1, DType.U16, PLANT_UNIT, gain=10),
    RegisterDef(30087, "ess_soh", 1, DType.U16, PLANT_UNIT, gain=10),
    # [Grid code] rated values -- configured/nameplate, NOT live measurements
    # (confirmed by spec text + cross-version diff, see register-map.md).
    RegisterDef(30276, "grid_code_rated_frequency", 1, DType.U16, PLANT_UNIT, gain=100),
    RegisterDef(30277, "grid_code_rated_voltage", 2, DType.U32, PLANT_UNIT, gain=100),
    # ---- Unit 247 ("plant") -- dynamic: worth varying over a scenario's timeseries ----
    RegisterDef(30004, "grid_sensor_status", 1, DType.U16, PLANT_UNIT, dynamic=True),
    RegisterDef(30005, "grid_active_power", 2, DType.S32, PLANT_UNIT, gain=1000, dynamic=True),
    RegisterDef(30009, "on_off_grid_status", 1, DType.U16, PLANT_UNIT, dynamic=True),
    RegisterDef(30014, "ess_soc", 1, DType.U16, PLANT_UNIT, gain=10, dynamic=True),
    RegisterDef(30027, "general_alarm1", 1, DType.U16, PLANT_UNIT, dynamic=True),
    RegisterDef(30028, "general_alarm2", 1, DType.U16, PLANT_UNIT, dynamic=True),
    RegisterDef(30029, "general_alarm3", 1, DType.U16, PLANT_UNIT, dynamic=True),
    RegisterDef(30030, "general_alarm4", 1, DType.U16, PLANT_UNIT, dynamic=True),
    RegisterDef(30035, "pv_plant_power", 2, DType.S32, PLANT_UNIT, gain=1000, dynamic=True),
    RegisterDef(30037, "ess_power", 2, DType.S32, PLANT_UNIT, gain=1000, dynamic=True),
    RegisterDef(30051, "plant_running_state", 1, DType.U16, PLANT_UNIT, dynamic=True),
    RegisterDef(30072, "general_alarm5", 1, DType.U16, PLANT_UNIT, dynamic=True),
    RegisterDef(30272, "pv_total_daily_generation", 2, DType.U32, PLANT_UNIT, gain=100, dynamic=True),
    RegisterDef(30274, "pv_total_generation_previous_day", 2, DType.U32, PLANT_UNIT, gain=100, dynamic=True),
    RegisterDef(30279, "current_control_command_value", 1, DType.U16, PLANT_UNIT, gain=100, dynamic=True),
    RegisterDef(30280, "general_alarm6", 1, DType.U16, PLANT_UNIT, dynamic=True),
    RegisterDef(30281, "general_alarm7", 1, DType.U16, PLANT_UNIT, dynamic=True),  # see module docstring
    RegisterDef(30282, "general_load_power", 2, DType.S32, PLANT_UNIT, gain=1000, dynamic=True),
    RegisterDef(30284, "total_load_power", 2, DType.S32, PLANT_UNIT, gain=1000, dynamic=True),
    RegisterDef(30286, "ess_average_cell_temperature", 1, DType.S16, PLANT_UNIT, gain=10, dynamic=True),
    # ---- Unit 1 ("inverter") -- identification strings ----
    RegisterDef(30500, "inverter_model_type", 15, DType.STRING, INVERTER_UNIT),
    RegisterDef(30515, "inverter_serial_number", 10, DType.STRING, INVERTER_UNIT),
    RegisterDef(30525, "inverter_firmware_version", 15, DType.STRING, INVERTER_UNIT),
    # ---- Unit 1 ("inverter") -- static: ratings/hardware inventory ----
    RegisterDef(30540, "inverter_rated_active_power", 2, DType.U32, INVERTER_UNIT, gain=1000),
    RegisterDef(31000, "rated_grid_voltage", 1, DType.U16, INVERTER_UNIT, gain=10),
    RegisterDef(31001, "rated_grid_frequency", 1, DType.U16, INVERTER_UNIT, gain=100),
    RegisterDef(31004, "output_type", 1, DType.U16, INVERTER_UNIT),
    RegisterDef(31024, "pack_count", 1, DType.U16, INVERTER_UNIT),
    RegisterDef(31025, "pv_string_count", 1, DType.U16, INVERTER_UNIT),
    RegisterDef(31026, "mppt_count", 1, DType.U16, INVERTER_UNIT),
    # ---- Unit 1 ("inverter") -- dynamic: live telemetry ----
    RegisterDef(30578, "inverter_running_state", 1, DType.U16, INVERTER_UNIT, dynamic=True),
    RegisterDef(30587, "inverter_active_power", 2, DType.S32, INVERTER_UNIT, gain=1000, dynamic=True),
    RegisterDef(30599, "ess_charge_discharge_power", 2, DType.S32, INVERTER_UNIT, gain=1000, dynamic=True),
    RegisterDef(30601, "ess_battery_soc", 1, DType.U16, INVERTER_UNIT, gain=10, dynamic=True),
    RegisterDef(30602, "ess_battery_soh", 1, DType.U16, INVERTER_UNIT, gain=10, dynamic=True),
    RegisterDef(30603, "ess_average_cell_temperature_inv", 1, DType.S16, INVERTER_UNIT, gain=10, dynamic=True),
    RegisterDef(30604, "ess_average_cell_voltage", 1, DType.U16, INVERTER_UNIT, gain=1000, dynamic=True),
    RegisterDef(30605, "inverter_alarm1", 1, DType.U16, INVERTER_UNIT, dynamic=True),
    RegisterDef(30606, "inverter_alarm2", 1, DType.U16, INVERTER_UNIT, dynamic=True),
    RegisterDef(30607, "inverter_alarm3", 1, DType.U16, INVERTER_UNIT, dynamic=True),
    RegisterDef(30608, "inverter_alarm4", 1, DType.U16, INVERTER_UNIT, dynamic=True),
    RegisterDef(30609, "inverter_alarm5", 1, DType.U16, INVERTER_UNIT, dynamic=True),
    RegisterDef(31002, "grid_frequency", 1, DType.U16, INVERTER_UNIT, gain=100, dynamic=True),  # live
    RegisterDef(31003, "pcs_internal_temperature", 1, DType.S16, INVERTER_UNIT, gain=10, dynamic=True),  # live
    RegisterDef(31011, "phase_a_voltage", 2, DType.U32, INVERTER_UNIT, gain=100, dynamic=True),
    RegisterDef(31013, "phase_b_voltage", 2, DType.U32, INVERTER_UNIT, gain=100, dynamic=True),
    RegisterDef(31015, "phase_c_voltage", 2, DType.U32, INVERTER_UNIT, gain=100, dynamic=True),
    RegisterDef(31017, "phase_a_current", 2, DType.S32, INVERTER_UNIT, gain=100, dynamic=True),
    RegisterDef(31019, "phase_b_current", 2, DType.S32, INVERTER_UNIT, gain=100, dynamic=True),
    RegisterDef(31021, "phase_c_current", 2, DType.S32, INVERTER_UNIT, gain=100, dynamic=True),
    # PV1-3 only: this real installation has pv_string_count=3 (31025).
    RegisterDef(31027, "pv1_voltage", 1, DType.S16, INVERTER_UNIT, gain=10, dynamic=True),
    RegisterDef(31028, "pv1_current", 1, DType.S16, INVERTER_UNIT, gain=100, dynamic=True),
    RegisterDef(31029, "pv2_voltage", 1, DType.S16, INVERTER_UNIT, gain=10, dynamic=True),
    RegisterDef(31030, "pv2_current", 1, DType.S16, INVERTER_UNIT, gain=100, dynamic=True),
    RegisterDef(31031, "pv3_voltage", 1, DType.S16, INVERTER_UNIT, gain=10, dynamic=True),
    RegisterDef(31032, "pv3_current", 1, DType.S16, INVERTER_UNIT, gain=100, dynamic=True),
    RegisterDef(31035, "pv_power", 2, DType.S32, INVERTER_UNIT, gain=1000, dynamic=True),
    RegisterDef(31037, "insulation_resistance", 1, DType.U16, INVERTER_UNIT, gain=1000, dynamic=True),
    RegisterDef(31509, "pv_daily_generation", 2, DType.U32, INVERTER_UNIT, gain=100, dynamic=True),
    RegisterDef(31511, "pv_total_generation", 2, DType.U32, INVERTER_UNIT, gain=100, dynamic=True),
]
