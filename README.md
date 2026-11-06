# RCT Power integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![pre-commit][pre-commit-shield]][pre-commit]
[![Black][black-shield]][black]

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

[![Discord][discord-shield]][discord]
[![Community Forum][forum-shield]][forum]

**This component will set up the following platforms.**

| Platform | Description                   |
| -------- | ----------------------------- |
| `sensor` | Show info from RCT Power API. |

## Installation

### Via the HACS integration

1. Install the "RCT Power" integration using [HACS].
2. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "RCT Power"

### Via manual download

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `rct_power`.
4. Download _all_ the files from the `custom_components/rct_power/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant
7. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "RCT Power"

## Configuration

Upon installation the integration accepts the following configuration parameters:

- `Host name`: The local IP address or host name of the inverter.
- `Port`: The port of the inverter's API, defaults to `8899`.
- `Name`: This name is used as a prefix to the entities created by this integration and can be used to disambiguate multiple inverters.

After installation the integration allows for the following configuration parameters to be changed:

- `Frequent polling interval`: The polling interval in seconds for entities updated frequently, defaults to `30`.
- `Infrequent polling interval`: The polling interval in seconds for entities updated infrequently, defaults to `180`.
- `Static polling interval`: The polling interval in seconds for entities updated seldomly, defaults to `3600`.

## Usage with the built-in energy dashboard

You can use the entities provided by this integration on Home Assistant's
built-in energy dashboard. For that purpose, navigate to "Configuration" ->
"Energy" and choose the following entities.

Please note that the entity names in your installation are prefixed with the
inverter name chosen during installation of the integration, so interpret the
entity names mentioned below to be entity name suffixes.

Also note that after configuration the energy dashboard might take several hours
to show any data, because Home Assistant calculates the underlying statistics
only on an hourly basis.

### Electricity grid

| Configuration item | Entity name                             | Note                                                   |
| ------------------ | --------------------------------------- | ------------------------------------------------------ |
| Grid consumption   | `Grid Energy Consumption Total`         |                                                        |
| Return to grid     | `Grid Energy Production Absolute Total` | Make sure to use the "Absolute" variant of this entity |

### Solar panels

You can configure the two generator strings A and B separately or combined
depending on your preference.

#### Separate generator strings

| Configuration item | Entity name                           |
| ------------------ | ------------------------------------- |
| Solar Production   | `Generator A Energy Production Total` |
| Solar Production   | `Generator B Energy Production Total` |

#### Combined generator strings

| Configuration item | Entity name                              |
| ------------------ | ---------------------------------------- |
| Solar Production   | `All Generators Energy Production Total` |

### Home Battery Storage

| Configuration item                                 | Entity name             |
| -------------------------------------------------- | ----------------------- |
| Battery systems - Energy going into the battery    | `Battery Stored Energy` |
| Battery systems - Energy coming out of the battery | `Battery Used Energy`   |

## Most commonly used entities

:warning: This list is incomplete and the interpretations might be incorrect due to a lack of official documentation.

### Grid

| Entity name                                  | Unit | Description                                                                      | Polling frequency |
| -------------------------------------------- | ---- | -------------------------------------------------------------------------------- | ----------------- |
| Grid Frequency                               | Hz   | the instantaneous overall grid frequency                                         | frequent          |
| Grid Frequency P1/P2/P3                      | Hz   | the instantaneous grid frequency on phase 1/2/3                                  | frequent          |
| Grid Power                                   | W    | the instantaneous power consumed from (`> 0`) or fed into (`< 0`) the grid       | frequent          |
| Grid Power P1/P2/P3                          | W    | the instantaneous power consumed from or fed into the grid on phase 1/2/3        | frequent          |
| Grid Voltage P1/P2/P3                        | W    | the instantaneous grid voltage on phase 1/2/3                                    | frequent          |
| Grid Energy Consumption Day/Month/Year/Total | Wh   | the cumulative energy consumed from the grid                                     | infrequent        |
| Grid Energy Production Day/Month/Year/Total  | Wh   | the cumulative energy fed into the grid                                          | infrequent        |
| Grid Energy Production Absolute Total        | kWh  | the absolute value of the cumulative energy fed into the grid since installation | infrequent        |
| Grid Maximum Feed Power                      | W    | the maximum power the inverter is configured to feed into the grid               | static            |

### Battery

| Entity name                                   | Unit | Description                                                                   | Polling frequency |
| --------------------------------------------- | ---- | ----------------------------------------------------------------------------- | ----------------- |
| Battery Power                                 | W    | the instantaneous power consumed from (`> 0`) or fed into (`< 0`) the battery | frequent          |
| Battery Current                               | A    | the instantaneous current flowing from or to the battery                      | frequent          |
| Battery Voltage                               | V    | the instantaneous voltage of the battery                                      | frequent          |
| Battery Temperature                           | °C   | the instantaneous temperature of the battery                                  | frequent          |
| Battery Cycles                                |      | the recorded full charge/discharge cycles of the battery                      | infrequent        |
| Battery State of Charge                       | %    | the instantaneous state of charge of the battery                              | frequent          |
| Battery State of Charge Target                | %    | the state of charge of the battery aimed for by the system                    | frequent          |
| Battery Minimum State of Charge               | %    | the configured minimum state of charge of the battery for regular operation   | frequent          |
| Battery Minimum State of Charge (island)      | %    | the minimum state of charge of the battery to maintain as an island backup    | frequent          |
| Battery Maximum State of Charge               | %    | the maximum state of charge of the battery to aim for to improve battery life | frequent          |
| Battery State of Health                       | %    | the estimated state of health of the battery                                  | infrequent        |
| Battery Stored Energy                         | Wh   | the cumulative energy fed into the battery                                    | frequent          |
| Battery Used Energy                           | Wh   | the cumulative energy consumed from the battery                               | frequent          |
| Battery Status                                |      | the current battery status (incomplete)                                       | frequent          |
| Battery Maximum Charging Current              | A    | the charging current currently allowed by the BMS                             | frequent          |
| Battery Converter Maximum Charging Current    | A    | the charging current currently allowed by the inverter's battery converter    | frequent          |
| Battery Converter Maximum Discharging Current | A    | the discharging current currently allowed by the battery converter            | frequent          |
| Battery State of Charge Strategy              |      | the SOC target selection (e.g. 4 = internal, 2 = external)                    | infrequent        |
| Battery Efficiency                            | %    | the ratio of used to stored energy                                            | infrequent        |
| Next Battery Calibration Date                 |      | the date and time of the next planned battery calibration                     | infrequent        |

### Battery towers, modules and cells

An inverter can have two battery towers. The second tower shows up as a
separate device called "Battery Tower 2". Entities of the second tower are
prefixed with `Battery Tower 2` instead of `Battery`.

The second tower additionally has its own pack values: `Battery Tower 2 State
of Charge`, `Voltage`, `Current`, `Temperature`, `Charge Capacity`, `State of
Health` and `Maximum Charging/Discharging Current`.

| Entity name                           | Unit | Description                                                               | Polling frequency |
| ------------------------------------- | ---- | ------------------------------------------------------------------------- | ----------------- |
| Battery Max/Min Cell Voltage          | V    | the highest/lowest cell voltage of the tower as reported by its BMS       | frequent          |
| Battery Max/Min Cell Temperature      | °C   | the highest/lowest cell temperature of the tower as reported by its BMS   | frequent          |
| Battery Module N Cycles               |      | the recorded cycles of module N                                           | infrequent        |
| Battery Module N Max Cell Voltage     | V    | the highest cell voltage of module N, all cells in the attributes         | infrequent        |
| Battery Module N Min Cell Voltage     | V    | the lowest cell voltage of module N                                       | infrequent        |
| Battery Module N Mean Cell Voltage    | V    | the mean cell voltage of module N (disabled by default)                   | infrequent        |
| Battery Module N Cell Voltage Spread  | mV   | the difference between the highest and lowest cell voltage of module N    | infrequent        |
| Battery Module N Max Cell Temperature | °C   | the highest cell temperature of module N                                  | infrequent        |
| Battery Module N Min Cell Temperature | °C   | the lowest cell temperature of module N (disabled by default)             | infrequent        |
| Battery Module N Max Cell Resistance  | mΩ   | the highest internal cell resistance of module N, all cells in attributes | static            |
| Battery Module N Mean Cell Resistance | mΩ   | the mean internal cell resistance of module N                             | static            |

Each tower also has five sensors summarizing all of its cells, meant for
tracking cell health over months (they keep long-term statistics):

| Entity name                           | Unit | Description                                                                              | Polling frequency |
| ------------------------------------- | ---- | ---------------------------------------------------------------------------------------- | ----------------- |
| Battery Cell Voltage Spread           | mV   | the difference between the highest and lowest cell of the tower                          | infrequent        |
| Battery Weakest Cell Deviation        | mV   | how far the lowest cell is below the tower's median cell, position in `min_voltage_cell` | infrequent        |
| Battery Max Cell Resistance           | mΩ   | the highest internal cell resistance of the tower, position in `max_resistance_cell`     | static            |
| Battery Max Cell Resistance Deviation | %    | how much the highest cell resistance exceeds the tower's median                          | static            |
| Battery Flagged Cells                 |      | how many cells report a non-zero status byte, see below                                  | infrequent        |

Their attributes `module_cell_voltages` and `module_cell_resistances` hold all
cells of the tower (one list per module), which is enough to draw a heatmap
with a markdown card.

#### Tower connection, balancing and calibration

| Entity name                      | Type          | Description                                                                                          | Polling frequency |
| -------------------------------- | ------------- | ---------------------------------------------------------------------------------------------------- | ----------------- |
| Battery (Tower 2) Connection     | binary sensor | off when the tower voltage differs from the battery voltage measured by the inverter by 10 V or more | frequent          |
| Battery Balancing                | binary sensor | the balancing bit of the battery status                                                              | frequent          |
| Battery Calibration              | binary sensor | the battery status reports a calibration charge                                                      | frequent          |
| Battery Calibration Interval     | d             | how often the inverter runs a calibration charge                                                     | static            |
| Battery Calibration Charge Power | W             | the charging power used for the calibration                                                          | static            |

All towers of an inverter sit on the same DC bus, so a connected tower has
practically the bus voltage. When the BMS opens the contactor of a tower (for
example because it is deeply discharged) the tower keeps reporting its own
voltage, which then drifts away from the bus, and its cell data usually reads
as zeros. The `tower_voltage`, `bus_voltage` and `voltage_difference`
attributes show the values behind the decision. Without a reading the
connection is unknown.

The meaning of the per-cell status byte is not documented. It was 0 for every
cell in all snapshots so far, which were all taken on the flat part of the LFP
curve. It is expected to flag cells the BMS is balancing near the top of the
charge, e.g. during the calibration charge (`Next Battery Calibration Date`).
`Battery Flagged Cells` counts those cells and keeps long-term statistics, the
`flagged_cells` attribute lists their positions and raw status bytes.

The per-cell values (`cell_voltages`, `cell_temperatures`, `cell_status`,
`cell_resistances`) are exposed as attributes and are not recorded in the
history database. The lists are indexed by cell position, a cell without a
valid reading is `null`.

### Household consumers and producers

| Entity name                                      | Unit | Description                                                            | Polling frequency |
| ------------------------------------------------ | ---- | ---------------------------------------------------------------------- | ----------------- |
| Consumer Energy Consumption Day/Month/Year/Total | Wh   | the cumulative energy consumed by the household (from any source)      | infrequent        |
| Consumer Power                                   | W    | the instantaneous power consumed by the household                      | frequent          |
| Consumer Power P1/P2/P3                          | W    | the instantaneous power consumed by the household on phase 1/2/3       | frequent          |
| External Energy Production Day/Month/Year/Total  | Wh   | the cumulative energy produced by the external producer (if installed) | infrequent        |
| Externel Generator S0 Power                      | W    | the instantaneous power produced by external device connected to S0 in | frequent          |

### Photovoltaic generators

| Entity name                                        | Unit | Description                                                           | Polling frequency |
| -------------------------------------------------- | ---- | --------------------------------------------------------------------- | ----------------- |
| Generator A Energy Production Day/Month/Year/Total | Wh   | the cumulative energy produced by generator string A                  | infrequent        |
| Generator B Energy Production Day/Month/Year/Total | Wh   | the cumulative energy produced by generator string B                  | infrequent        |
| All Generators Energy Production Total             | Wh   | the sum of the cumulative energy produced by both generator strings   | infrequent        |
| Generator A Power                                  | W    | the instantaneous power produced by generator string A                | frequent          |
| Generator B Power                                  | W    | the instantaneous power produced by generator string B                | frequent          |
| All Generators Power                               | W    | the sum of the instantaneous power produced by both generator strings | frequent          |
| Generator A Voltage                                | V    | the instantaneous voltage produced by generator string A              | frequent          |
| Generator B Voltage                                | V    | the instantaneous voltage produced by generator string B              | frequent          |
| Generator Maximum Power                            | W    | the configured combined maximum power of both generator strings       | static            |
| Insulation Resistance                              | Ohm  |                                                                       | frequent          |
| Insulation Resistance Positive/Negative Input      | Ohm  |                                                                       | frequent          |
| Minimum Insulation Resistance                      | Ohm  |                                                                       | frequent          |

### Inverter

| Entity name                                     | Unit | Description                                                     | Polling frequency |
| ----------------------------------------------- | ---- | --------------------------------------------------------------- | ----------------- |
| Inverter AC Power                               | W    | the instantaneous AC power transmitted by the inverter          | frequent          |
| Inverter Energy Production Day/Month/Year/Total | Wh   | the cumulative energy produced by the inverter                  | infrequent        |
| Inverter Power P1/P2/P3                         | W    | the instantaneous power consumed or generated by the inverter   | frequent          |
| Inverter Serial Number                          |      | the serial number of the inverter                               | static            |
| Faults                                          |      | a bitmask of the failures reported by the inverter              | frequent          |
| Core Temperature                                | °C   | the instantaneous temperature of the invertor core              | frequent          |
| Heat Sink Temperature                           | °C   | the instantaneous temperature of the invertor heat sink         | frequent          |
| Heat Sink (battery actuator) Temperature        | °C   | the instantaneous temperature of the battery actuator heat sink | frequent          |

### Limiting the inverter output

The integration only reads from the inverter unless writing is allowed for a
config entry. To limit the output, open the options of the inverter that
controls the plant and has the grid power meter attached (the master in a
master/slave setup) and enable "Allow changing the power reduction of this inverter".
This adds the entity `number.<prefix>_external_power_reduction`
(`buf_v_control.power_reduction`), which limits the inverter to a percentage of
the solar plant peak power ("Generator Maximum Power"); 100 % means no
reduction.

Writing the feed-in limit in W (`buf_v_control.power_reduction_max_solar_grid`)
is not offered: the inverter accepts the value but it has no effect on the
output. It is still shown as the "Grid Maximum Feed Power" sensor.

The value is only written when it changes and the value read back from the
inverter is shown in the entity and the "External Power Reduction" sensor.
Avoid changing it every few seconds from an automation.

### Controlling the battery

Every inverter keeps its own battery settings, a slave does not take them
from the master. Enable "Allow changing the battery settings of this
inverter" in the options of each inverter with a battery to get:

- `select.<battery>_battery_state_of_charge_strategy` (`power_mng.soc_strategy`)
  chooses how the inverter sets the battery SOC target: `Internal` (the
  default, based on the solar forecast), `Constant`, `External`, `Schedule` or
  the undocumented `SOC target = SOC`. The undocumented `Middle battery
voltage` is not offered and shows as unknown.
- `number.<battery>_battery_state_of_charge_constant_target`
  (`power_mng.soc_target_set`) is the SOC target in % while the strategy is
  `Constant`.
- `number.<battery>_battery_external_power` (`power_mng.battery_power_extern`)
  is the battery power in W while the strategy is `External`; positive values
  discharge and negative values charge the battery. Charging from the grid with
  more than the maintenance charge power also needs "Utilize external Inverter
  energy" (`power_mng.use_grid_power_enable`) on the inverter.

The inverter keeps the strategy until it is changed again, so switch
back to `Internal` to return control to the inverter. Calibration and balancing
still charge the battery to 100 % regardless of the strategy.

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

## Credits

This would have been a lot more difficult if not for [@svalouch](https://github.com/svalouch)'s [`python-rctclient`](https://github.com/svalouch/python-rctclient) library. Thank you!

This project was generated from [@oncleben31](https://github.com/oncleben31)'s [Home Assistant Custom Component Cookiecutter](https://github.com/oncleben31/cookiecutter-homeassistant-custom-component) template.

Code template was mainly taken from [@Ludeeus](https://github.com/ludeeus)'s [integration_blueprint][integration_blueprint] template

---

[integration_blueprint]: https://github.com/custom-components/integration_blueprint
[black]: https://github.com/psf/black
[black-shield]: https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge
[buymecoffee]: https://www.buymeacoffee.com/weltenwort
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/weltenwort/home-assistant-rct-power-integration.svg?style=for-the-badge
[commits]: https://github.com/weltenwort/home-assistant-rct-power-integration/commits/main
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[discord]: https://discord.gg/Qa5fW2R
[discord-shield]: https://img.shields.io/discord/330944238910963714.svg?style=for-the-badge
[exampleimg]: example.png
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/weltenwort/home-assistant-rct-power-integration.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40weltenwort-blue.svg?style=for-the-badge
[pre-commit]: https://github.com/pre-commit/pre-commit
[pre-commit-shield]: https://img.shields.io/badge/pre--commit-enabled-brightgreen?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/weltenwort/home-assistant-rct-power-integration.svg?style=for-the-badge
[releases]: https://github.com/weltenwort/home-assistant-rct-power-integration/releases
[user_profile]: https://github.com/weltenwort
