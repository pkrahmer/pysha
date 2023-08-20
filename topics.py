import logging

import descriptions
from datetime import datetime
import json

NTC_MAPPING: [int] = [120, 120, 120, 120, 120, 120, 120, 120, 120, 120, 120, 120, 117, 114, 111, 108,
                      106, 103, 101, 99, 97, 95, 93, 92, 90, 88, 87, 86, 84, 83, 82, 80,
                      79, 78, 77, 76, 75, 74, 73, 72, 71, 70, 69, 68, 67, 66, 66, 65,
                      64, 63, 62, 62, 61, 60, 60, 59, 58, 58, 57, 56, 56, 55, 54, 54,
                      53, 53, 52, 51, 51, 50, 50, 49, 49, 48, 48, 47, 47, 46, 45, 45,
                      44, 44, 44, 43, 43, 42, 42, 41, 41, 40, 40, 39, 39, 38, 38, 38,
                      37, 37, 36, 36, 35, 35, 35, 34, 34, 33, 33, 32, 32, 32, 31, 31,
                      30, 30, 30, 29, 29, 28, 28, 28, 27, 27, 27, 26, 26, 25, 25, 25,
                      24, 24, 24, 23, 23, 22, 22, 22, 21, 21, 21, 20, 20, 19, 19, 19,
                      18, 18, 18, 17, 17, 17, 16, 16, 15, 15, 15, 14, 14, 14, 13, 13,
                      12, 12, 12, 11, 11, 11, 10, 10, 9, 9, 9, 8, 8, 8, 7, 7,
                      6, 6, 6, 5, 5, 4, 4, 4, 3, 3, 2, 2, 2, 1, 1, 0,
                      0, 0, -1, -1, -2, -2, -3, -3, -4, -4, -4, -5, -5, -6, -6, -7,
                      -7, -8, -8, -9, -9, -10, -10, -11, -12, -12, -13, -13, -14, -15, -15, -16,
                      -16, -17, -18, -18, -19, -20, -21, -21, -22, -23, -24, -25, -26, -27, -28, -29,
                      -30, -31, -32, -33, -35, -36, -38, -40, -41, -44, -46, -49, -53, -57, -64, -78]


class Topic:
    def __init__(self, name: str, unit: str = None, enum: [] = None, area: (float, float) = None,
                 decd: any = None, encd: any = None,
                 dflt: any = None, optn: bool = False,
                 help: str = None):
        self.raw_value = dflt
        self.name = name
        self.unit = unit
        self.decode_fnc = decd
        self.encode_fnc = encd
        self.enum = enum
        self.area = area
        self.since = None
        self.delegated: bool = True
        self.optional = optn
        self.help = help
        self.previous_value = None
        self.previous_duration = None
        pass

    def decode(self, packet_data: bytearray):
        if len(packet_data) == (20 if self.optional else 203):
            self.value = self.decode_fnc(packet_data)

    def encode(self, current_packet_data: bytearray, value) -> (int, int):
        return self.encode_fnc(current_packet_data, value)

    @property
    def writable(self) -> bool:
        return self.encode_fnc is not None

    def accepts(self, value: any) -> bool:
        if self.enum is None or len(self.enum) == 0:
            return True

        if self.area is not None:
            return is_int(value) and self.area[0] <= float(value) <= self.area[1]

        if self.enum is not None:
            if is_int(value):
                return 0 <= int(value) < len(self.enum)
            else:
                return value.lower() in (string.lower() for string in self.enum)

        return True

    def parse(self, value: any) -> int:
        if not self.accepts(value):
            raise ValueError

        if is_int(value):
            return int(value)
        elif self.enum is not None:
            for idx, string in enumerate(self.enum):
                if string.lower() == value.lower():
                    return idx

            raise ValueError
        else:
            return value

    @property
    def value(self) -> any:
        return self.raw_value

    @value.setter
    def value(self, value: any) -> None:
        new_value: int = self.parse(value)
        if new_value != self.raw_value:
            now = datetime.now()
            self.previous_value = self.raw_value
            if self.since is not None:
                self.previous_duration = (now - self.since).total_seconds()
            self.raw_value = new_value
            self.since = now
            self.delegated = False

    @property
    def description(self) -> str:
        if self.raw_value is None:
            return None
        elif self.enum is not None:
            return self.enum[self.raw_value]
        else:
            return str(self.raw_value) + ("" if self.unit is None else " " + self.unit)

    def __str__(self):
        return F"{self.name}={self.description}"

    def changed_since(self, since: datetime):
        return self.since is not None and (since is None or since < self.since)

    def to_json(self):
        o = {"value": self.value}
        if self.previous_duration is not None:
            o["previous"] = {"value": self.previous_value, "duration": self.previous_duration}
        if self.since is not None:
            o["since"] = self.since.isoformat()
        if self.description is not None:
            o["description"] = self.description
        if self.help is not None:
            o["info"] = self.help
        if self.unit is not None:
            o["unit"] = self.unit
        if self.enum is not None:
            o["enum"] = self.enum
        if self.area is not None:
            o["range"] = self.area
        if self.writable:
            o["writable"] = True

        return json.dumps(o)


topics = [
    Topic(name="Control/HeatpumpState",
          help="Heatpump state",
          enum=["Off", "On"],
          decd=lambda d: bits_7_and_8(d[4]),
          encd=lambda d, onoff: (4, 2 if onoff else 1)),
    Topic(name="Config/Pump/ServiceMode",
          help="Set Water Pump to service mode, max speed",
          enum=["Off", "On"],
          decd=lambda d: 1 if bits_5_and_6(d[4]) == 2 else 0,
          encd=lambda d, onoff: (4, 32 if onoff else 16)),
    Topic(name="Control/Reset",
          help="Perform a reset on the heat pump",
          enum=["Off", "On"],
          decd=lambda d: 0,
          encd=lambda d, onoff: (8, 1 if onoff else 0)),
    Topic(name="Status/Pump/Flow",
          help="Current pump flow rate",
          unit="l/min",
          area=(0, 256),
          decd=lambda d: get_pump_flow(d)),
    Topic(name="Control/DHW/Force",
          help="Enforce DHW heating operation to happen now",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_1_and_2(d[4]),
          encd=lambda d, onoff: (4, 128 if onoff else 64)),
    Topic(name="Control/OperatingMode",
          help="Operating mode of the heat pump, as settable on the remote control",
          enum=["Heat", "Cool", "Auto(heat)", "DHW", "Heat+DHW", "Cool+DHW",
                "Auto(heat)+DHW", "Auto(cool)", "Auto(cool)+DHW"],
          decd=lambda d: get_op_mode(d[6]),
          encd=lambda d, mode: (6, [18, 19, 24, 33, 34, 35, 40][mode] if mode < 7 else 0)),
    Topic(name="Status/Temp/Inlet",
          help="Inlet / return-flow water temperature measurement",
          unit="°C",
          area=(-128.75, 127.75),
          decd=lambda d: get_inlet_temp(d)),
    Topic(name="Status/Temp/Outlet",
          help="Outlet / forward-flow water temperature measurement",
          unit="°C",
          area=(-128.75, 127.75),
          decd=lambda d: get_outlet_temp(d)),
    Topic(name="Status/Temp/Target",
          help="Outlet target temperature",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[153])),
    Topic(name="Status/Compressor/Freq",
          help="Compressor frequency",
          unit="Hz",
          area=(-1, 254),
          decd=lambda d: int_minus_1(d[166])),
    Topic(name="Control/DHW/TargetTemp",
          help="Water tank target temperature",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[42]),
          encd=lambda d, temperature: (42, temperature + 128)),
    Topic(name="Status/Temp/DHW",
          help="Water tank temperature measurement",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[141])),
    Topic(name="Statistics/Usage/Runtime",
          unit="h",
          help="Total runtime of the compressor",
          area=(-1, 65534),
          decd=lambda d: (d[183]*256+d[182]) - 1),
    Topic(name="Statistics/Usage/Starts",
          help="Total number of compressor starts",
          area=(-1, 65534),
          decd=lambda d: (d[180]*256+d[179]) - 1),
    Topic(name="Control/MainSchedule",
          help="Main thermostat schedule used or not used",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_1_and_2(d[5]),
          encd=lambda d, onoff: (5, 128 if onoff else 64)),
    Topic(name="Status/Temp/Outside",
          help="Outside ambient temperature measurement",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[142])),
    Topic(name="Statistics/Energy/Production/Heat",
          help="Current thermal heat power production used for heating",
          unit="W",
          area=(-200, 50800),
          decd=lambda d: get_energy(d[194])),
    Topic(name="Statistics/Energy/Consumption/Heat",
          help="Current electrical power consumption used for heating",
          unit="W",
          area=(-200, 50800),
          decd=lambda d: get_energy(d[193])),
    Topic(name="Control/PowerfulMode",
          help="Powerful mode timeout",
          enum=["Off", "30min", "60min", "90min"],
          decd=lambda d: right_3_bits(d[7]),
          encd=lambda d, mode: (7, min(3, max(0, mode)) + 73)),  # fixme: does +73 make sense?
    Topic(name="Control/QuietMode/Schedule",
          help="Quiet mode schedule used or not used",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_1_and_2(d[7])),
    Topic(name="Control/QuietMode/Level",
          help="Level of quiet mode (the higher the quieter)",
          enum=["Off", "Level 1", "Level 2", "Level 3"],
          decd=lambda d: bits_3_to_5(d[7]),
          encd=lambda d, mode: (7, (min(3, max(0, mode)) + 1) * 8)),
    Topic(name="Control/HolidayMode",
          help="Whether holiday mode is off, active or scheduled",
          enum=["Off", "Scheduled", "Active"],
          decd=lambda d: bits_3_and_4(d[5]),
          encd=lambda d, onoff: (5, 32 if onoff else 16)),
    Topic(name="Status/ThreeWayValve",
          help="Switch state of three way valve, heating or DHW",
          enum=["Room", "DHW"],
          decd=lambda d: bits_7_and_8(d[111])),
    Topic(name="Status/Temp/Internal/OutsidePipe",
          help="Outside pipe temperature measurement",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[158])),
    Topic(name="Config/DHW/Delta",
          help="Hysteresis for DHW tank heating",
          unit="K",
          area=(-12, -2),
          decd=lambda d: int_minus_128(d[99]),
          encd=lambda d, delta: (99, delta + 128)),
    Topic(name="Config/Heating/Delta",
          help="Aimed outlet-inlet temperature delta when heating",
          unit="K",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[84]),
          encd=lambda d, delta: (84, delta + 128)),
    Topic(name="Config/Cooling/Delta",
          help="Aimed outlet-inlet temperature delta when cooling",
          unit="K",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[94]),
          encd=lambda d, delta: (94, delta + 128)),
    Topic(name="Config/DHW/HolidayShiftTemp",
          help="Holiday shift temperature for DHW tank heating",
          unit="K",
          area=(-15, +15),
          decd=lambda d: int_minus_128(d[44])),
    Topic(name="Status/Defrosting",
          help="Defrosting currently ongoing or not",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_5_and_6(d[111]),
          encd=lambda d, onoff: (8, 2 if onoff else 0)),
    Topic(name="Status/Temp/RoomThermostat",
          help="Remote control thermostat temperature measurement",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[156])),
    Topic(name="Config/Zones/1/Heat/RequestTemp",
          help="Heat Requested shift temp (-5 to 5) or direct heat temp (20 to max)",
          unit="°C",
          area=(-5, 127),
          decd=lambda d: int_minus_128(d[38]),
          encd=lambda d, temperature: (38, temperature + 128)),
    Topic(name="Config/Zones/1/Cool/RequestTemp",
          help="Cool Requested shift temp (-5 to 5) or direct cool temp (5 to 20)",
          unit="°C",
          area=(-5, 20),
          decd=lambda d: int_minus_128(d[39]),
          encd=lambda d, temperature: (39, temperature + 128)),
    Topic(name="Config/Zones/2/Heat/RequestTemp",
          help="Heat Requested shift temp (-5 to 5) or direct heat temp (20 to max)",
          unit="°C",
          area=(-5, 127),
          decd=lambda d: int_minus_128(d[40]),
          encd=lambda d, temperature: (40, temperature + 128)),
    Topic(name="Config/Zones/2/Cool/RequestTemp",
          help="Cool Requested shift temp (-5 to 5) or direct cool temp (5 to 20)",
          unit="°C",
          area=(-5, 20),
          decd=lambda d: int_minus_128(d[41]),
          encd=lambda d, temperature: (41, temperature + 128)),
    Topic(name="Status/Temp/Zones/1/Outlet",
          help="Zone 1 water outlet temperature measurement",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[145])),
    Topic(name="Status/Temp/Zones/2/Outlet",
          help="Zone 2 water outlet temperature measurement",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[146])),
    Topic(name="Statistics/Energy/Production/Cool",
          help="Thermal cooling power production",
          unit="W",
          area=(-200, 50800),
          decd=lambda d: get_energy(d[196])),
    Topic(name="Statistics/Energy/Consumption/Cool",
          help="Electrical power consumption for cooling",
          unit="W",
          area=(-200, 50800),
          decd=lambda d: get_energy(d[195])),
    Topic(name="Statistics/Energy/Production/DHW",
          help="Thermal heating power production for DHW",
          unit="W",
          area=(-200, 50800),
          decd=lambda d: get_energy(d[198])),
    Topic(name="Statistics/Energy/Consumption/DHW",
          help="Electrical power consumption for DHW",
          unit="W",
          area=(-200, 50800),
          decd=lambda d: get_energy(d[197])),
    Topic(name="Status/Temp/Zones/1/OutletTarget",
          help="Zone 1 water target temperature",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[147])),
    Topic(name="Status/Temp/Zones/2/OutletTarget",
          help="Zone 2 water target temperature",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[148])),
    Topic(name="Status/Error",
          help="Error code of the last error that happened",
          decd=lambda d: get_error_info(d)),
    Topic(name="Config/Heating/HolidayShiftTemp",
          help="Room heating Holiday shift temperature",
          unit="K",
          area=(-15, 15),
          decd=lambda d: int_minus_128(d[43])),
    Topic(name="Status/Temp/Buffer",
          help="Actual buffer temperature measurement",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[149])),
    Topic(name="Status/Temp/Solar",
          help="Actual solar temperature measurement",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[150])),
    Topic(name="Status/Temp/Pool",
          help="Actual pool temperature measurement",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[151])),
    Topic(name="Status/Temp/Internal/MainHexOutlet",
          help="Outlet 2, after heat exchanger water temperature measurement",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[154])),
    Topic(name="Status/Temp/Internal/Discharge",
          help="Discharge temperature measurement",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[155])),
    Topic(name="Status/Temp/Internal/InsidePipe",
          help="Inside pipe temperature measurement",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[157])),
    Topic(name="Status/Temp/Internal/Defrost",
          help="Defrost temperature",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[159])),
    Topic(name="Status/Temp/Internal/EvaOutlet",
          help="Eva Outlet temperature measurement",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[160])),
    Topic(name="Status/Temp/Internal/BypassOutlet",
          help="Bypass Outlet temperature measurement",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[161])),
    Topic(name="Status/Temp/Internal/IPM",
          help="Ipm temperature measurement",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[162])),
    Topic(name="Status/Temp/Zones/1/Actual",
          help="Zone 1 actual temperature",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[139])),
    Topic(name="Status/Temp/Zones/2/Actual",
          help="Zone 2 actual temperature",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[140])),
    Topic(name="Config/HeatingRod/DHW",
          help="When enabled, backup/booster heater can be used for DHW heating",
          enum=["Blocked", "Free"],
          decd=lambda d: bits_5_and_6(d[9])),
    Topic(name="Config/HeatingRod/Room",
          help="When enabled, backup/booster heater can be used for room heating",
          enum=["Blocked", "Free"],
          decd=lambda d: bits_7_and_8(d[9])),
    Topic(name="Status/HeatingRod/Internal",
          help="Internal backup heater state",
          enum=["Inactive", "Active"],
          decd=lambda d: bits_7_and_8(d[112])),
    Topic(name="Status/HeatingRod/External",
          help="External backup heater state",
          enum=["Inactive", "Active"],
          decd=lambda d: bits_5_and_6(d[112])),
    Topic(name="Status/Fan/1/Speed",
          help="Fan 1 Motor rotation speed",
          unit="r/min",
          area=(-10, 2540),
          decd=lambda d: int_minus_1_times_10(d[173])),
    Topic(name="Status/Fan/2/Speed",
          help="Fan 2 Motor rotation speed",
          unit="r/min",
          area=(-10, 2540),
          decd=lambda d: int_minus_1_times_10(d[174])),
    Topic(name="Status/Pressure/High",
          help="High pressure",
          unit="Kgf/cm2",
          area=(-0.2, 50.8),
          decd=lambda d: int_minus_1_div_5(d[163])),
    Topic(name="Status/Pump/Speed",
          help="Pump rotation speed",
          unit="r/min",
          area=(-50, 12700),
          decd=lambda d: int_minus_1_times_50(d[171])),
    Topic(name="Status/Pressure/Low",
          help="Low pressure",
          unit="Kgf/cm2",
          area=(-1, 254),
          decd=lambda d: int_minus_1(d[164])),
    Topic(name="Status/Compressor/Current",
          help="Compressor electrical current",
          unit="A",
          area=(-0.2, 50.8),
          decd=lambda d: int_minus_1_div_5(d[165])),
    Topic(name="Status/HeatingRod/Enforce",
          help="Force heating rod",
          enum=["Inactive", "Active"],
          decd=lambda d: bits_5_and_6(d[5])),
    Topic(name="Control/DHW/Sterilization",
          help="Sterilisation state",
          enum=["Inactive", "Active"],
          decd=lambda d: bits_5_and_6(d[117]),
          encd=lambda d, onoff: (8, 4 if onoff else 0)),
    Topic(name="Config/DHW/SterilizationTemp",
          help="Sterilisation temperature",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[100])),
    Topic(name="Config/DHW/SterilizationMaxTime",
          help="Sterilisation maximum time",
          unit="min",
          area=(-1, 254),
          decd=lambda d: int_minus_1(d[101])),
    Topic(name="Config/Zones/1/HeatCurve/TargetHigh",
          help="Target temperature at highest point on the heating curve",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[75]),
          encd=lambda d, temp: (75, temp + 128)),
    Topic(name="Config/Zones/1/HeatCurve/TargetLow",
          help="Target temperature at lowest point on the heating curve",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[76]),
          encd=lambda d, temp: (76, temp + 128)),
    Topic(name="Config/Zones/1/HeatCurve/OutsideHigh",
          help="Highest outside temperature on the heating curve",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[78]),
          encd=lambda d, temp: (78, temp + 128)),
    Topic(name="Config/Zones/1/HeatCurve/OutsideLow",
          help="Lowest outside temperature on the heating curve",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[77]),
          encd=lambda d, temp: (77, temp + 128)),
    Topic(name="Config/Zones/1/CoolCurve/TargetHigh",
          help="Target temperature at highest point on the cooling curve",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[86]),
          encd=lambda d, temp: (86, temp + 128)),
    Topic(name="Config/Zones/1/CoolCurve/TargetLow",
          help="Target temperature at highest point on the cooling curve",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[87]),
          encd=lambda d, temp: (87, temp + 128)),
    Topic(name="Config/Zones/1/CoolCurve/OutsideHigh",
          help="Highest outside temperature on the cooling curve",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[89]),
          encd=lambda d, temp: (89, temp + 128)),
    Topic(name="Config/Zones/1/CoolCurve/OutsideLow",
          help="Lowest outside temperature on the cooling curve",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[88]),
          encd=lambda d, temp: (88, temp + 128)),
    Topic(name="Config/Zones/2/HeatCurve/TargetHigh",
          help="Target temperature at highest point on the heating curve",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[79]),
          encd=lambda d, temp: (79, temp + 128)),
    Topic(name="Config/Zones/2/HeatCurve/TargetLow",
          help="Target temperature at lowest point on the heating curve",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[80]),
          encd=lambda d, temp: (80, temp + 128)),
    Topic(name="Config/Zones/2/HeatCurve/OutsideHigh",
          help="Highest outside temperature on the heating curve",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[82]),
          encd=lambda d, temp: (82, temp + 128)),
    Topic(name="Config/Zones/2/HeatCurve/OutsideLow",
          help="Lowest outside temperature on the heating curve",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[81]),
          encd=lambda d, temp: (81, temp + 128)),
    Topic(name="Config/Zones/2/CoolCurve/TargetHigh",
          help="Target temperature at highest point on the cooling curve",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[90]),
          encd=lambda d, temp: (90, temp + 128)),
    Topic(name="Config/Zones/2/CoolCurve/TargetLow",
          help="Target temperature at lowest point on the cooling curve",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[91]),
          encd=lambda d, temp: (91, temp + 128)),
    Topic(name="Config/Zones/2/CoolCurve/OutsideHigh",
          help="Highest outside temperature on the cooling curve",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[93]),
          encd=lambda d, temp: (93, temp + 128)),
    Topic(name="Config/Zones/2/CoolCurve/OutsideLow",
          help="Lowest outside temperature on the cooling curve",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[92]),
          encd=lambda d, temp: (92, temp + 128)),
    Topic(name="Config/Heating/Mode",
          help="Compensation curve or Direct mode for heating",
          enum=["Comp. Curve", "Direct"],
          decd=lambda d: bits_7_and_8(d[28])),
    Topic(name="Config/Heating/OffOutdoorTemp",
          help="Above this outdoor temperature all heating is turned off",
          unit="°C",
          area=(5, 35),
          decd=lambda d: int_minus_128(d[83])),
    Topic(name="Config/HeatingRod/OnOutdoorTemp",
          help="Below this temperature the backup heating rod is allowed to be used by heatpump heating logic",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[85])),
    Topic(name="Config/HeatToCoolTemp",
          help="Outdoor temperature to switch from heat to cool mode when in auto setting",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[95])),
    Topic(name="Config/CoolToHeatTemp",
          help="Outdoor temperature to switch from cool to heat mode when in auto setting",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[96])),
    Topic(name="Config/Cooling/Mode",
          help="Compensation curve or Direct mode for cooling",
          enum=["Comp. Curve", "Direct"],
          decd=lambda d: bits_5_and_6(d[28])),
    Topic(name="Statistics/Usage/HeatingRod/Room",
          help="Electric heater operating time for Room heating",
          unit="h",
          area=(-1, 65534),
          decd=lambda d: (d[186]*256+d[185]) - 1),
    Topic(name="Statistics/Usage/HeatingRod/DHW",
          help="Electric heater operating time for DHW",
          unit="h",
          area=(-1, 65534),
          decd=lambda d: (d[189]*256+d[188]) - 1),
    Topic(name="Model/ID",
          help="Heat pump model",
          area=(0, len(descriptions.Model) - 1),
          decd=lambda d: get_model(d)),
    Topic(name="Model/Name",
          help="Heat pump model",
          decd=lambda d: descriptions.Model[get_model(d)]),
    Topic(name="Status/Pump/Duty",
          help="Current pump duty",
          area=(-1, 254),
          decd=lambda d: int_minus_1(d[172])),
    Topic(name="Config/Zones/State",
          help="Zones connected to the device",
          enum=["Zone1 active", "Zone2 active", "Zone1 and zone2 active"],
          decd=lambda d: bits_1_and_2(d[6]),
          encd=lambda d, mode: (6, [64, 128, 192][mode] if mode < 3 else 0)),
    Topic(name="Config/Pump/MaxDuty",
          help="Maximum pump duty configured",
          area=(-1, 254),
          decd=lambda d: int_minus_1(d[45]),
          encd=lambda d, duty: (45, duty + 1)),
    Topic(name="Config/HeatingRod/DelayTime",
          help="Heater delay time (J-series only)",
          unit="min",
          area=(-1, 254),
          decd=lambda d: int_minus_1(d[104]),
          encd=lambda d, time: (104, time + 1)),
    Topic(name="Config/HeatingRod/StartDelta",
          help="Heater start delta (J-series only)",
          unit="K",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[105]),
          encd=lambda d, delta: (105, delta + 128)),
    Topic(name="Config/HeatingRod/StopDelta",
          help="Heater stop delta (J-series only)",
          unit="K",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[106]),
          encd=lambda d, delta: (106, delta + 128)),
    Topic(name="Config/Buffer/Installed",
          help="Buffer tank installed",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_5_and_6(d[24])),
    Topic(name="Config/DHW/Installed",
          help="Buffer DHW tank installed",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_7_and_8(d[24])),
    Topic(name="Config/Solar/Mode",
          help="Solar mode (disabled, to buffer, to DHW)",
          enum=["Disabled", "Buffer", "DHW"],
          decd=lambda d: bits_3_and_4(d[24])),
    Topic(name="Config/Solar/OnDelta",
          help="Solar heating delta on",
          unit="K",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[61])),
    Topic(name="Config/Solar/OffDelta",
          help="Solar heating delta off",
          unit="K",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[62])),
    Topic(name="Config/Solar/FrostProtection",
          help="Solar frost protection temperature",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[63])),
    Topic(name="Config/Solar/HighLimit",
          help="Solar max temperature limit",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[64])),
    Topic(name="Config/Pump/FlowRateMode",
          help="Mode of pump control",
          enum=["DeltaT", "Max flow"],
          decd=lambda d: bits_3_and_4(d[29])),
    Topic(name="Config/LiquidType",
          help="Type of liquid in system",
          enum=["Water", "Glycol"],
          decd=lambda d: bit_1(d[20])),
    Topic(name="Config/AltExternalSensor",
          help="If external outdoor sensor is used",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_3_and_4(d[20]),
          encd=lambda d, onoff: (20, 32 if onoff else 16)),
    Topic(name="Config/AntiFreezeMode",
          help="Is anti freeze mode enabled or disabled",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_5_and_6(d[20])),
    Topic(name="Config/OptionalPCB",
          help="If the optional PCB is enabled (if installed)",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_7_and_8(d[20])),
    Topic(name="Config/Sensor/Zones/1",
          help="Setting of the sensor for zone 1",
          enum=["Water Temperature", "External Thermostat", "Internal Thermostat", "Thermistor"],
          decd=lambda d: (d[22] & 0b1111) - 1),
    Topic(name="Config/Sensor/Zones/2",
          help="Setting of the sensor for zone 2",
          enum=["Water Temperature", "External Thermostat", "Internal Thermostat", "Thermistor"],
          decd=lambda d: (d[22] >> 4) - 1),
    Topic(name="Config/Buffer/Delta",
          help="Delta of buffer tank setting",
          unit="K",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[59]),
          encd=lambda d, delta: (59, delta + 128)),
    Topic(name="Config/ExternalPadHeater",
          help="If the external pad heater is enabled (if installed)",
          enum=["Disabled", "Type-A", "Type-B"],
          decd=lambda d: bits_3_and_4(d[25]),
          encd=lambda d, mode: (25, 48 if mode == 2 else 32 if mode == 1 else 16)),

    Topic(name="Actor/Zones/1/WaterPump",
          help="Zone 1 water pump action request",
          enum=["Off", "On"],
          decd=lambda d: d[4] >> 7,
          optn=True),
    Topic(name="Actor/Zones/1/MixingValve",
          help="Zone 1 mixing valve action request",
          enum=["Off", "Decrease", "Increase"],
          decd=lambda d: (d[4] >> 5) & 0b11,
          optn=True),
    Topic(name="Actor/Zones/2/WaterPump",
          help="Zone 2 water pump action request",
          enum=["Off", "On"],
          decd=lambda d: (d[4] >> 4) & 0b1,
          optn=True),
    Topic(name="Actor/Zones/2/MixingValve",
          help="Zone 2 mixing valve action request",
          enum=["Off", "Decrease", "Increase"],
          decd=lambda d: (d[4] >> 2) & 0b11,
          optn=True),
    Topic(name="Actor/Zones/Pool/WaterPump",
          help="Pool water pump action request",
          enum=["Off", "On"],
          decd=lambda d: (d[4] >> 1) & 0b1,
          optn=True),
    Topic(name="Actor/Solar/WaterPump",
          help="Solar water pump action request",
          enum=["Off", "On"],
          decd=lambda d: (d[4] >> 0) & 0b1,
          optn=True),
    Topic(name="Status/Alarm",
          help="Alarm state",
          enum=["Off", "On"],
          decd=lambda d: (d[5] >> 0) & 0b1,
          optn=True),

    Topic(name="Control/Optional/HeatCoolMode",
          help="Set device to heat or cool mode",
          enum=["Heat", "Cool"],
          decd=lambda d: (d[6] >> 7) & 0b1,
          encd=lambda d, onoff: (6, update_byte(d[6], 1 if onoff == 1 else 0, 0b1, 7)),
          optn=True),
    Topic(name="Control/Optional/CompressorState",
          help="Turn compressor on or off",
          enum=["Off", "On"],
          decd=lambda d: (d[6] >> 6) & 0b1,
          encd=lambda d, onoff: (6, update_byte(d[6], 1 if onoff == 1 else 0, 0b1, 6)),
          dflt=1,
          optn=True),
    Topic(name="Control/Optional/SmartGridMode",
          help="Select smart grid (SG) mode",
          enum=["Normal", "Off", "Capacity 1", "Capacity 2"],
          decd=lambda d: (d[6] >> 4) & 0b11,
          encd=lambda d, mode: (6, update_byte(d[6], 0 if mode < 0 else 3 if mode > 3 else mode, 0b11, 4)),
          optn=True),
    Topic(name="Control/Optional/ExternalThermostat1State",
          help="Action request of external thermostat 1",
          enum=["Off", "Heat", "Cool", "HeatAndCool"],
          decd=lambda d: (d[6] >> 2) & 0b11,
          encd=lambda d, mode: (6, update_byte(d[6], 0 if mode < 0 else 3 if mode > 3 else mode, 0b11, 2)),
          optn=True),
    Topic(name="Control/Optional/ExternalThermostat2State",
          help="Action request of external thermostat 2",
          enum=["Off", "Heat", "Cool", "HeatAndCool"],
          decd=lambda d: (d[6] >> 0) & 0b11,
          encd=lambda d, mode: (6, update_byte(d[6], 0 if mode < 0 else 3 if mode > 3 else mode, 0b11, 0)),
          optn=True),
    Topic(name="Control/Optional/DemandControl",
          help="Demand control setting",
          area=(0, 100),
          decd=lambda d: 0 if d[14] <= 43 else 100 if d[14] > 234 else (d[14]-34)/2,
          encd=lambda d, mode: (14, 0 if mode < 5 else (mode*2)+34),
          optn=True),
    Topic(name="Control/Optional/Sensors/PoolTemp",
          help="Pool temperature sensor reading",
          area=(NTC_MAPPING[-1], NTC_MAPPING[0]),
          decd=lambda d: NTC_MAPPING[d[7]],
          encd=lambda d, temp: (7, ntc_of_temp(temp)),
          optn=True),
    Topic(name="Control/Optional/Sensors/BufferTemp",
          help="Buffer temperature sensor reading",
          area=(NTC_MAPPING[-1], NTC_MAPPING[0]),
          decd=lambda d: NTC_MAPPING[d[8]],
          encd=lambda d, temp: (8, ntc_of_temp(temp)),
          optn=True),
    Topic(name="Control/Optional/Sensors/Zones/1/RoomTemp",
          help="Zone 1 room temperature sensor reading",
          area=(NTC_MAPPING[-1], NTC_MAPPING[0]),
          decd=lambda d: NTC_MAPPING[d[10]],
          encd=lambda d, temp: (10, ntc_of_temp(temp)),
          optn=True),
    Topic(name="Control/Optional/Sensors/Zones/1/WaterTemp",
          help="Zone 1 water temperature sensor reading",
          area=(NTC_MAPPING[-1], NTC_MAPPING[0]),
          decd=lambda d: NTC_MAPPING[d[16]],
          encd=lambda d, temp: (16, ntc_of_temp(temp)),
          optn=True),
    Topic(name="Control/Optional/Sensors/Zones/2/RoomTemp",
          help="Zone 2 room temperature sensor reading",
          area=(NTC_MAPPING[-1], NTC_MAPPING[0]),
          decd=lambda d: NTC_MAPPING[d[11]],
          encd=lambda d, temp: (11, ntc_of_temp(temp)),
          optn=True),
    Topic(name="Control/Optional/Sensors/Zones/2/WaterTemp",
          help="Zone 2 water temperature sensor reading",
          area=(NTC_MAPPING[-1], NTC_MAPPING[0]),
          decd=lambda d: NTC_MAPPING[d[15]],
          encd=lambda d, temp: (15, ntc_of_temp(temp)),
          optn=True),
    Topic(name="Control/Optional/Sensors/SolarTemp",
          help="Solar water temperature sensor reading",
          area=(NTC_MAPPING[-1], NTC_MAPPING[0]),
          decd=lambda d: NTC_MAPPING[d[13]],
          encd=lambda d, temp: (13, ntc_of_temp(temp)),
          optn=True),

]


def decode_and_update_topic(data: []) -> bool:
    if not len(data) in [20, 203]:
        logging.info(F"topics: invalid data len {len(data)}")
        return False

    if not valid_checksum(data):
        logging.info(F"topics: invalid checksum received {checksum(data[:-1])} != {data[-1]}")
        return False

    for topic in topics:
        topic.decode(data)

    return True


def find_topic(name: str):
    for topic in topics:
        if topic.name.lower() == name.lower():
            return topic
    return None


def checksum(data: []) -> int:
    chk = 0
    for b in data:
        chk += b
    chk = (chk ^ 0xFF) + 0x01
    return chk & 0xFF


def valid_checksum(data: []) -> bool:
    return checksum(data[:-1]) == data[-1]


def bit_1(value):
    return value >> 7


def bits_1_and_2(value):
    return (value >> 6) - 1


def bits_3_and_4(value):
    return ((value >> 4) & 0b11) - 1


def bits_5_and_6(value):
    return ((value >> 2) & 0b11) - 1


def bits_7_and_8(value):
    return (value & 0b11) - 1


def bits_3_to_5(value):
    return ((value >> 3) & 0b111) - 1


def left_5_bits(value):
    return (value >> 3) - 1


def right_3_bits(value):
    return (value & 0b111) - 1


def int_minus_1(value):
    return int(value) - 1


def int_minus_128(value):
    return int(value) - 128


def int_minus_1_div_5(value):
    value = ((float(value) - 1) / 5)
    return round(value, 1)


def int_minus_1_times_10(value):
    value = int(value) - 1
    return value * 10


def int_minus_1_times_50(value):
    value = int(value) - 1
    return value * 50


def get_op_mode(value):
    op_mode = int(value & 0b111111)
    if op_mode == 18:
        return "0"
    elif op_mode == 19:
        return "1"
    elif op_mode == 25:
        return "2"
    elif op_mode == 33:
        return "3"
    elif op_mode == 34:
        return "4"
    elif op_mode == 35:
        return "5"
    elif op_mode == 41:
        return "6"
    elif op_mode == 26:
        return "7"
    elif op_mode == 42:
        return "8"
    else:
        return "-1"


def get_energy(value):
    return (int(value) - 1) * 200


def get_model(data):
    model = [data[129], data[130], data[131], data[132], data[133], data[134], data[135], data[136], data[137],
             data[138]]
    for i in range(len(descriptions.knownModels)):
        if model == descriptions.knownModels[i]:
            return i
    return -1


def get_pump_flow(data):
    pump_flow1 = int(data[170])
    pump_flow2 = ((float(data[169]) - 1) / 256)
    pump_flow = pump_flow1 + pump_flow2
    return round(pump_flow, 2)


def get_error_info(data):
    error_type = int(data[113])
    error_number = int(data[114]) - 17
    if error_type == 177 - 128:
        return "F{:02X}".format(error_number)
    elif error_type == 161 - 128:
        return "H{:02X}".format(error_number)
    else:
        return "?{:02X}:{:02X}".format(error_type, error_number)


def get_inlet_temp(data):
    value = float(int_minus_128(data[143]))
    fractional = int(data[118] & 0b111)
    if fractional == 2:
        value += .25
    elif fractional == 3:
        value += .5
    elif fractional == 4:
        value += .75
    return value


def get_outlet_temp(data):
    value = float(int_minus_128(data[144]))
    fractional = int((data[118] >> 3) & 0b111)
    if fractional == 2:
        value += .25
    elif fractional == 3:
        value += .5
    elif fractional == 4:
        value += .75
    return value


def update_byte(current, val, base, bit):
    return (current & ~(base << bit)) | (val << bit)


def ntc_of_temp(temp: int) -> int:
    for idx, val in enumerate(NTC_MAPPING):
        if temp >= val:
            return idx
    return 255


def is_int(value: any) -> bool:
    try:
        int(value)
        return True
    except ValueError:
        return False

