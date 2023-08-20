import logging

import descriptions
from datetime import datetime


def is_int(value: any) -> bool:
    try:
        int(value)
        return True
    except ValueError:
        return False


class Topic:
    def __init__(self, name: str, unit: str = None, enum: [] = None, area: (float, float) = None,
                 decd: any = None, encd: any = None,
                 dflt: any = None, optn: bool = False):
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
        pass

    def decode(self, packet_data: bytearray):
        if len(packet_data) == (20 if self.optional else 203):
            self.value = self.decode_fnc(packet_data)

    def encode(self, value) -> (int, int):
        return self.encode_fnc(value)

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
            self.raw_value = new_value
            self.since = datetime.now()
            self.delegated = False

    @property
    def description(self) -> str:
        if self.raw_value is None:
            return None
        elif self.enum is not None:
            return self.enum[self.raw_value]
        else:
            return str(self.raw_value) + ("" if self.unit is None else " " + self.unit)

    @property
    def writable(self) -> bool:
        return self.encode_fnc is not None

    def __str__(self):
        return F"{self.name}={self.description}"

    def changed_since(self, since: datetime):
        return self.since is not None and (since is None or since < self.since)


topics = [
    Topic(name="Heatpump/State",
          enum=["Off", "On"],
          decd=lambda d: bits_7_and_8(d[4]),
          encd=lambda onoff: (4, 2 if onoff else 1)),
    Topic(name="Pump/ServiceMode",
          enum=["Off", "On"],
          decd=lambda d: 1 if bits_5_and_6(d[4]) == 2 else 0,
          encd=lambda onoff: (4, 32 if onoff else 16)),
    Topic(name="Heatpump/Reset",
          enum=["Off", "On"],
          decd=lambda d: 0,
          encd=lambda onoff: (8, 1 if onoff else 0)),
    Topic(name="Pump/Flow",
          unit="l/min",
          area=(0, 256),
          decd=lambda d: get_pump_flow(d)),
    Topic(name="DHW/Force",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_1_and_2(d[4]),
          encd=lambda onoff: (4, 128 if onoff else 64)),
    Topic(name="Heatpump/OperatingMode",
          enum=["Heat", "Cool", "Auto(heat)", "DHW", "Heat+DHW", "Cool+DHW",
                "Auto(heat)+DHW", "Auto(cool)", "Auto(cool)+DHW"],
          decd=lambda d: get_op_mode(d[6]),
          encd=lambda mode: (6, [18, 19, 24, 33, 34, 35, 40][mode] if mode < 7 else 0)),
    Topic(name="Main/InletTemp",
          unit="°C",
          area=(-128.75, 127.75),
          decd=lambda d: get_inlet_temp(d)),
    Topic(name="Main/OutletTemp",
          unit="°C",
          area=(-128.75, 127.75),
          decd=lambda d: get_outlet_temp(d)),
    Topic(name="Main/TargetTemp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[153])),
    Topic(name="Heatpump/CompressorFreq",
          unit="Hz",
          area=(-1, 254),
          decd=lambda d: int_minus_1(d[166])),
    Topic(name="DHW/TargetTemp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[42]),
          encd=lambda temperature: (42, temperature + 128)),
    Topic(name="DHW/Temp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[141])),
    Topic(name="Heatpump/OperationsHours",
          unit="h",
          area=(-1, 65534),
          decd=lambda d: (d[183]*256+d[182]) - 1),
    Topic(name="Heatpump/OperationsCounter",
          area=(-1, 65534),
          decd=lambda d: (d[180]*256+d[179]) - 1),
    Topic(name="Heatpump/MainSchedule",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_1_and_2(d[5]),
          encd=lambda onoff: (5, 128 if onoff else 64)),
    Topic(name="Status/Temp/Outside",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[142])),
    Topic(name="Energy/Production/Heat",
          unit="W",
          area=(-200, 50800),
          decd=lambda d: get_energy(d[194])),
    Topic(name="Energy/Consumption/Heat",
          unit="W",
          area=(-200, 50800),
          decd=lambda d: get_energy(d[193])),
    Topic(name="Heatpump/PowerfulModeTime",
          enum=["Off", "30min", "60min", "90min"],
          decd=lambda d: right_3_bits(d[7]),
          encd=lambda mode: (7, min(3, max(0, mode)) + 73)),  # fixme: does +73 make sense?
    Topic(name="Heatpump/QuietMode/Schedule",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_1_and_2(d[7])),
    Topic(name="Heatpump/QuietMode/Level",
          enum=["Off", "Level 1", "Level 2", "Level 3"],
          decd=lambda d: bits_3_to_5(d[7]),
          encd=lambda mode: (7, (min(3, max(0, mode)) + 1) * 8)),
    Topic(name="Heatpump/HolidayMode",
          enum=["Off", "Scheduled", "Active"],
          decd=lambda d: bits_3_and_4(d[5]),
          encd=lambda onoff: (5, 32 if onoff else 16)),
    Topic(name="Heatpump/ThreeWayValve",
          enum=["Room", "DHW"],
          decd=lambda d: bits_7_and_8(d[111])),
    Topic(name="Status/Temp/OutsidePipe",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[158])),
    Topic(name="DHW/HeatDelta",
          unit="K",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[99]),
          encd=lambda delta: (99, delta + 128)),
    Topic(name="Heating/Delta",
          unit="K",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[84]),
          encd=lambda delta: (84, delta + 128)),
    Topic(name="Cooling/Delta",
          unit="K",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[94]),
          encd=lambda delta: (94, delta + 128)),
    Topic(name="DHW/HolidayShiftTemp",
          unit="K",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[44])),
    Topic(name="Heatpump/DefrostingState",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_5_and_6(d[111]),
          encd=lambda onoff: (8, 2 if onoff else 0)),
    Topic(name="Room/ThermostatTemp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[156])),
    Topic(name="Zones/1/Heat/RequestTemp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[38]),
          encd=lambda temperature: (38, temperature + 128)),
    Topic(name="Zones/1/Cool/RequestTemp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[39]),
          encd=lambda temperature: (39, temperature + 128)),
    Topic(name="Zones/2/Heat/RequestTemp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[40]),
          encd=lambda temperature: (40, temperature + 128)),
    Topic(name="Zones/2/Cool/RequestTemp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[41]),
          encd=lambda temperature: (41, temperature + 128)),
    Topic(name="Zones/1/WaterTemp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[145])),
    Topic(name="Zones/2/WaterTemp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[146])),
    Topic(name="Energy/Production/Cool",
          unit="W",
          area=(-200, 50800),
          decd=lambda d: get_energy(d[196])),
    Topic(name="Energy/Consumption/Cool",
          unit="W",
          area=(-200, 50800),
          decd=lambda d: get_energy(d[195])),
    Topic(name="Energy/Production/DHW",
          unit="W",
          area=(-200, 50800),
          decd=lambda d: get_energy(d[198])),
    Topic(name="Energy/Consumption/DHW",
          unit="W",
          area=(-200, 50800),
          decd=lambda d: get_energy(d[197])),
    Topic(name="Zones/1/WaterTargetTemp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[147])),
    Topic(name="Zones/2/WaterTargetTemp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[148])),
    Topic(name="Heatpump/Error",
          decd=lambda d: get_error_info(d)),
    Topic(name="Room/HolidayShiftTemp",
          unit="K",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[43])),
    Topic(name="Buffer/Temp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[149])),
    Topic(name="Solar/Temp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[150])),
    Topic(name="Pool/Temp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[151])),
    Topic(name="Status/Temp/MainHexOutlet",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[154])),
    Topic(name="Status/Temp/Discharge",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[155])),
    Topic(name="Status/Temp/InsidePipe",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[157])),
    Topic(name="Status/Temp/Defrost",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[159])),
    Topic(name="Status/Temp/EvaOutlet",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[160])),
    Topic(name="Status/Temp/BypassOutlet",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[161])),
    Topic(name="Status/Temp/IPM",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[162])),
    Topic(name="Zones/1/Temp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[139])),
    Topic(name="Zones/2/Temp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[140])),
    Topic(name="DHW/HeaterState",
          enum=["Blocked", "Free"],
          decd=lambda d: bits_5_and_6(d[9])),
    Topic(name="Heating/HeaterState",
          enum=["Blocked", "Free"],
          decd=lambda d: bits_7_and_8(d[9])),
    Topic(name="Status/InternalHeater",
          enum=["Inactive", "Active"],
          decd=lambda d: bits_7_and_8(d[112])),
    Topic(name="Status/ExternalHeater",
          enum=["Inactive", "Active"],
          decd=lambda d: bits_5_and_6(d[112])),
    Topic(name="Status/Fan1",
          unit="r/min",
          area=(-10, 2540),
          decd=lambda d: int_minus_1_times_10(d[173])),
    Topic(name="Status/Fan2",
          unit="r/min",
          area=(-10, 2540),
          decd=lambda d: int_minus_1_times_10(d[174])),
    Topic(name="Status/High_Pressure",
          unit="Kgf/cm2",
          area=(-0.2, 50.8),
          decd=lambda d: int_minus_1_div_5(d[163])),
    Topic(name="Pump/Speed",
          unit="r/min",
          area=(-50, 12700),
          decd=lambda d: int_minus_1_times_50(d[171])),
    Topic(name="Status/LowPressure",
          unit="Kgf/cm2",
          area=(-1, 254),
          decd=lambda d: int_minus_1(d[164])),
    Topic(name="Energy/CompressorCurrent",
          unit="A",
          area=(-0.2, 50.8),
          decd=lambda d: int_minus_1_div_5(d[165])),
    Topic(name="Heating/ForceHeater",
          enum=["Inactive", "Active"],
          decd=lambda d: bits_5_and_6(d[5])),
    Topic(name="DHW/Sterilization",
          enum=["Inactive", "Active"],
          decd=lambda d: bits_5_and_6(d[117]),
          encd=lambda onoff: (8, 4 if onoff else 0)),
    Topic(name="DHW/SterilizationTemp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[100])),
    Topic(name="DHW/SterilizationMaxTime",
          unit="min",
          area=(-1, 254),
          decd=lambda d: int_minus_1(d[101])),
    Topic(name="Zones/1/HeatCurve/TargetHigh",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[75]),
          encd=lambda temp: (75, temp + 128)),
    Topic(name="Zones/1/HeatCurve/TargetLow",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[76]),
          encd=lambda temp: (76, temp + 128)),
    Topic(name="Zones/1/HeatCurve/OutsideHigh",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[78]),
          encd=lambda temp: (78, temp + 128)),
    Topic(name="Zones/1/HeatCurve/OutsideLow",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[77]),
          encd=lambda temp: (77, temp + 128)),
    Topic(name="Zones/1/CoolCurve/TargetHigh",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[86]),
          encd=lambda temp: (86, temp + 128)),
    Topic(name="Zones/1/CoolCurve/TargetLow",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[87]),
          encd=lambda temp: (87, temp + 128)),
    Topic(name="Zones/1/CoolCurve/OutsideHigh",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[89]),
          encd=lambda temp: (89, temp + 128)),
    Topic(name="Zones/1/CoolCurve/OutsideLow",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[88]),
          encd=lambda temp: (88, temp + 128)),
    Topic(name="Zones/2/HeatCurve/TargetHigh",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[79]),
          encd=lambda temp: (79, temp + 128)),
    Topic(name="Zones/2/HeatCurve/TargetLow",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[80]),
          encd=lambda temp: (80, temp + 128)),
    Topic(name="Zones/2/HeatCurve/OutsideHigh",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[82]),
          encd=lambda temp: (82, temp + 128)),
    Topic(name="Zones/2/HeatCurve/OutsideLow",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[81]),
          encd=lambda temp: (81, temp + 128)),
    Topic(name="Zones/2/CoolCurve/TargetHigh",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[90]),
          encd=lambda temp: (90, temp + 128)),
    Topic(name="Zones/2/CoolCurve/TargetLow",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[91]),
          encd=lambda temp: (91, temp + 128)),
    Topic(name="Zones/2/CoolCurve/OutsideHigh",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[93]),
          encd=lambda temp: (93, temp + 128)),
    Topic(name="Zones/2/CoolCurve/OutsideLow",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[92]),
          encd=lambda temp: (92, temp + 128)),
    Topic(name="Heating/Mode",
          enum=["Comp. Curve", "Direct"],
          decd=lambda d: bits_7_and_8(d[28])),
    Topic(name="Heating/OffOutdoorTemp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[83])),
    Topic(name="Heating/OnOutdoorTemp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[85])),
    Topic(name="Heating/HeatToCoolTemp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[95])),
    Topic(name="Cooling/CoolToHeatTemp",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[96])),
    Topic(name="Cooling/Mode",
          enum=["Comp. Curve", "Direct"],
          decd=lambda d: bits_5_and_6(d[28])),
    Topic(name="Heatpump/RoomHeaterOperationsHours",
          unit="h",
          area=(-1, 65534),
          decd=lambda d: (d[186]*256+d[185]) - 1),
    Topic(name="Heatpump/DHWHeaterOperationsHours",
          unit="h",
          area=(-1, 65534),
          decd=lambda d: (d[189]*256+d[188]) - 1),
    Topic(name="Heatpump/Model",
          enum=descriptions.Model,
          decd=lambda d: get_model(d)),
    Topic(name="Pump/Duty",
          area=(-1, 254),
          decd=lambda d: int_minus_1(d[172])),
    Topic(name="Zones/State",
          enum=["Zone1 active", "Zone2 active", "Zone1 and zone2 active"],
          decd=lambda d: bits_1_and_2(d[6]),
          encd=lambda mode: (6, [64, 128, 192][mode] if mode < 3 else 0)),
    Topic(name="Pump/MaxDuty",
          area=(-1, 254),
          decd=lambda d: int_minus_1(d[45]),
          encd=lambda duty: (45, duty + 1)),
    Topic(name="Heating/DelayTime",
          unit="min",
          area=(-1, 254),
          decd=lambda d: int_minus_1(d[104]),
          encd=lambda time: (104, time + 1)),
    Topic(name="Heating/StartDelta",
          unit="K",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[105]),
          encd=lambda delta: (105, delta + 128)),
    Topic(name="Heating/StopDelta",
          unit="K",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[106]),
          encd=lambda delta: (106, delta + 128)),
    Topic(name="Buffer/Installed",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_5_and_6(d[24])),
    Topic(name="DHW/Installed",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_7_and_8(d[24])),
    Topic(name="Solar/Mode",
          enum=["Disabled", "Buffer", "DHW"],
          decd=lambda d: bits_3_and_4(d[24])),
    Topic(name="Solar/OnDelta",
          unit="K",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[61])),
    Topic(name="Solar/OffDelta",
          unit="K",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[62])),
    Topic(name="Solar/FrostProtection",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[63])),
    Topic(name="Solar/HighLimit",
          unit="°C",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[64])),
    Topic(name="Config/PumpFlowRateMode",
          enum=["DeltaT", "Max flow"],
          decd=lambda d: bits_3_and_4(d[29])),
    Topic(name="Config/LiquidType",
          enum=["Water", "Glycol"],
          decd=lambda d: bit_1(d[20])),
    Topic(name="Config/AltExternalSensor",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_3_and_4(d[20]),
          encd=lambda onoff: (20, 32 if onoff else 16)),
    Topic(name="Config/AntiFreezeMode",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_5_and_6(d[20])),
    Topic(name="Config/OptionalPCB",
          enum=["Disabled", "Enabled"],
          decd=lambda d: bits_7_and_8(d[20])),
    Topic(name="Config/Sensor/Zones/1",
          enum=["Water Temperature", "External Thermostat", "Internal Thermostat", "Thermistor"],
          decd=lambda d: (d[22] & 0b1111) - 1),
    Topic(name="Config/Sensor/Zones/2",
          enum=["Water Temperature", "External Thermostat", "Internal Thermostat", "Thermistor"],
          decd=lambda d: (d[22] >> 4) - 1),
    Topic(name="Config/Buffer/TankDelta",
          unit="K",
          area=(-128, 127),
          decd=lambda d: int_minus_128(d[59]),
          encd=lambda delta: (59, delta + 128)),
    Topic(name="Config/ExternalPadHeater",
          enum=["Disabled", "Type-A", "Type-B"],
          decd=lambda d: bits_3_and_4(d[25]),
          encd=lambda mode: (25, 48 if mode == 2 else 32 if mode == 1 else 16)),

    Topic(name="Zones/1/WaterPump",
          enum=["Off", "On"],
          decd=lambda d: d[4] >> 7,
          optn=True),
    Topic(name="Zones/1/MixingValve",
          enum=["Off", "Decrease", "Increase"],
          decd=lambda d: (d[4] >> 5) & 0b11,
          optn=True),
    Topic(name="Zones/2/WaterPump",
          enum=["Off", "On"],
          decd=lambda d: (d[4] >> 4) & 0b1,
          optn=True),
    Topic(name="Zones/2/MixingValve",
          enum=["Off", "Decrease", "Increase"],
          decd=lambda d: (d[4] >> 2) & 0b11,
          optn=True),
    Topic(name="Pool/WaterPump",
          enum=["Off", "On"],
          decd=lambda d: (d[4] >> 1) & 0b1,
          optn=True),
    Topic(name="Solar/WaterPump",
          enum=["Off", "On"],
          decd=lambda d: (d[4] >> 0) & 0b1,
          optn=True),
    Topic(name="Heatpump/AlarmState",
          enum=["Off", "On"],
          decd=lambda d: (d[5] >> 0) & 0b1,
          optn=True),

#    Topic(name="SetHeatCoolMode",
#          enco=self.set_heat_cool_mode,
#    Topic(name="SetCompressorState": self.set_compressor_state,
#    Topic(name="SetSmartGridMode": self.set_smart_grid_mode,
#    Topic(name="SetExternalThermostat1State": self.set_external_thermostat_1_state,
#    Topic(name="SetExternalThermostat2State": self.set_external_thermostat_2_state,
#    Topic(name="SetDemandControl": self.set_demand_control,
#    Topic(name="SetPoolTemp": self.set_pool_temp,
#    Topic(name="SetBufferTemp": self.set_buffer_temp,
#    Topic(name="SetZ1RoomTemp": self.set_z1_room_temp,
#    Topic(name="SetZ1WaterTemp": self.set_z1_water_temp,
#    Topic(name="SetZ2RoomTemp": self.set_z2_room_temp,
#    Topic(name="SetZ2WaterTemp": self.set_z2_water_temp,
#    Topic(name="SetSolarTemp": self.set_solar_temp,
#    Topic(name="SetOptPCBByte9": self.set_byte_9
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
