#
#    Copyright (c) 2012=2020 Will Page <compenguy@gmail.com>
#    and Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Classes and functions for interfacing with Oregon Scientific WMR89,

See 
  https://www.wxforum.net/index.php?topic=27581
for documentation on the serial protocol
"""

from __future__ import absolute_import
from __future__ import print_function

import binascii
import time

import serial
import weewx.drivers

DRIVER_NAME = 'WMR89'
DRIVER_VERSION = "1.0.0"
DEFAULT_PORT = '/dev/ttyS0'


def FtoC(x):
    return (x - 32.0) * 5.0 / 9.0

def loader(config_dict, engine):  # @UnusedVariable
    return WMR89(**config_dict[DRIVER_NAME])


def confeditor_loader():
    return WMR89ConfEditor()


try:
    # Test for new-style weewx logging by trying to import weeutil.logger
    import weeutil.logger
    import logging

    log = logging.getLogger(__name__)

    def logdbg(msg):
        log.debug(msg)

    def loginf(msg):
        log.info(msg)

    def logerr(msg):
        log.error(msg)

except ImportError:
    # Old-style weewx logging
    import syslog

    def logmsg(level, msg):
        syslog.syslog(level, 'wmr89: %s' % msg)

    def logdbg(msg):
        logmsg(syslog.LOG_DEBUG, msg)

    def loginf(msg):
        logmsg(syslog.LOG_INFO, msg)

    def logerr(msg):
        logmsg(syslog.LOG_ERR, msg)


class WMR89ProtocolError(weewx.WeeWxIOError):
    """Used to signal a protocol error condition"""


class SerialWrapper(object):
    """Wraps a serial connection returned from package serial"""

    # WMR89 specific settings
    serialconfig = {
        "baudrate": 128000,
        "bytesize": serial.EIGHTBITS,
        "parity": serial.PARITY_NONE,
        "stopbits": serial.STOPBITS_ONE,
        "timeout": 2,
        "xonxoff": False
    }

    def __init__(self, port):
        self.serial_port = serial.Serial(port, **SerialWrapper.serialconfig)
        logdbg("Opened up serial port %s" % port)

    def flush_input(self):
        self.serial_port.flushInput()

    def queued_bytes(self):
        return self.serial_port.inWaiting()

    def read(self, chars=1):
        _buffer = self.serial_port.read(chars)
        N = len(_buffer)
        if N != chars:
            raise weewx.WeeWxIOError("Expected to read %d chars; got %d instead" % (chars, N))
        return _buffer

    def readAll(self):
        _buffer = bytearray()
        while self.serial_port.inWaiting() > 0:
            _buffer += self.serial_port.read()
        return _buffer

    def inWaiting(self):
        return self.serial_port.inWaiting()

    def write(self, buf):
        self.serial_port.write(buf)

    def closePort(self):
        self.serial_port.close()
        self.serial_port = None


# ==============================================================================
#                           Class WMR89
# ==============================================================================

class WMR89(weewx.drivers.AbstractDevice):
    """Driver for the Oregon Scientific WMR89 console.

    The connection to the console will be open after initialization"""

    DEFAULT_MAP = {
        'barometer': 'barometer',
        'pressure': 'pressure',
        'windSpeed': 'wind_speed',
        'windDir': 'wind_dir',
        'windGust': 'wind_gust',
        'windGustDir': 'wind_gust_dir',
        'windBatteryStatus': 'battery_status_wind',
        'inTemp': 'temperature_in',
        'outTemp': 'temperature_out',
        'extraTemp1': 'temperature_1',
        'extraTemp2': 'temperature_2',
        'extraTemp3': 'temperature_3',
        'extraTemp4': 'temperature_4',
        'extraTemp5': 'temperature_5',
        'extraTemp6': 'temperature_6',
        'extraTemp7': 'temperature_7',
        'extraTemp8': 'temperature_8',
        'inHumidity': 'humidity_in',
        'outHumidity': 'humidity_out',
        'extraHumid1': 'humidity_1',
        'extraHumid2': 'humidity_2',
        'extraHumid3': 'humidity_3',
        'extraHumid4': 'humidity_4',
        'extraHumid5': 'humidity_5',
        'extraHumid6': 'humidity_6',
        'extraHumid7': 'humidity_7',
        'extraHumid8': 'humidity_8',
        'inTempBatteryStatus': 'battery_status_in',
        'outTempBatteryStatus': 'battery_status_out',
        'extraBatteryStatus1': 'battery_status_1',  # was batteryStatusTHx
        'extraBatteryStatus2': 'battery_status_2',  # or batteryStatusTx
        'extraBatteryStatus3': 'battery_status_3',
        'extraBatteryStatus4': 'battery_status_4',
        'extraBatteryStatus5': 'battery_status_5',
        'extraBatteryStatus6': 'battery_status_6',
        'extraBatteryStatus7': 'battery_status_7',
        'extraBatteryStatus8': 'battery_status_8',
        'inDewpoint': 'dewpoint_in',
        'dewpoint': 'dewpoint_out',
        'dewpoint0': 'dewpoint_0',
        'dewpoint1': 'dewpoint_1',
        'dewpoint2': 'dewpoint_2',
        'dewpoint3': 'dewpoint_3',
        'dewpoint4': 'dewpoint_4',
        'dewpoint5': 'dewpoint_5',
        'dewpoint6': 'dewpoint_6',
        'dewpoint7': 'dewpoint_7',
        'dewpoint8': 'dewpoint_8',
        'rain': 'rain',
        'rainTotal': 'rain_total',
        'rainRate': 'rain_rate',
        'hourRain': 'rain_hour',
        'rain24': 'rain_24',
        'yesterdayRain': 'rain_yesterday',
        'rainBatteryStatus': 'battery_status_rain',
        'windchill': 'windchill'}

    def __init__(self, **stn_dict):
        """Initialize an object of type WMR89.

        NAMED ARGUMENTS:

        model: Which station model is this? [Optional. Default is 'WMR89']

        port: The serial port of the WMR89. [Optional. Default is '/dev/ttyUSB0']

        sensor_map: Overrides to the default sensor mapping dictionary, WMR89.DEFAULT_MAP.
        """

        loginf('driver version is %s' % DRIVER_VERSION)
        self.model = stn_dict.get('model', 'WMR89')
        self.port = stn_dict.get('port', '/dev/ttyUSB0')
        self.sensor_map = dict(self.DEFAULT_MAP)
        if 'sensor_map' in stn_dict:
            self.sensor_map.update(stn_dict['sensor_map'])
        loginf('sensor map is %s' % self.sensor_map)
        self.last_rain_total = None

        # Create the specified port
        self.serial_wrapper = SerialWrapper(self.port)

    @property
    def hardware_name(self):
        return self.model

    def closePort(self):
        """Close the connection to the console. """
        self.serial_wrapper.closePort()

    def genLoopPackets(self):
        """Generator function that continuously returns loop packets"""

        while True:
            # request data 
            if self.serial_wrapper.inWaiting() == 0:
                self.serial_wrapper.write(b'\xd1\x00')
                time.sleep(0.5)

            # read data
            buf = self.serial_wrapper.readAll()

            if buf:
                # The start of each packet is demarcated with the hex sequence 0xf2f2. Separate them, while getting
                # rid of any zeros
                self.log_hex('buf', buf)
                raw_packets = [_f for _f in buf.split(b'\xf2\xf2') if _f]
                # Loop over each packet in the set
                for raw_packet in raw_packets:
                    if weewx.debug >= 2:
                        self.log_hex('raw_packet', raw_packet)

                    packet = None

                    if raw_packet[0] == 0xb0:  # date/time NOK
                        packet = self._wmr89_time_packet(raw_packet)
                    elif raw_packet[0] == 0xb1:  # Rain NOK
                        packet = self._wmr89_rain_packet(raw_packet)
                    elif raw_packet[0] == 0xb2:  # Wind OK
                        packet = self._wmr89_wind_packet(raw_packet)
                    elif raw_packet[0] == 0xb4:  # Pressure OK
                        packet = self._wmr89_pressure_packet(raw_packet)
                    elif raw_packet[0] == 0xb5:  # T/Hum  OK
                        packet = self._wmr89_temp_packet(raw_packet)
                    else:
                        logdbg("Invalid data packet (%s)." % raw_packet)

                    mapped_packet = self._sensors_to_fields(packet, self.sensor_map) if packet else None
                    if mapped_packet:
                        yield mapped_packet

    @staticmethod
    def _sensors_to_fields(oldrec, sensor_map):
        # map a record with observation names to a record with db field names
        if oldrec:
            newrec = dict()
            for k in sensor_map:
                if sensor_map[k] in oldrec:
                    newrec[k] = oldrec[sensor_map[k]]
            if newrec:
                newrec['dateTime'] = oldrec['dateTime']
                newrec['usUnits'] = oldrec['usUnits']
                return newrec
        return None

    # ==========================================================================
    #              Oregon Scientific WMR89 utility functions
    # ==========================================================================

    def log_hex(self, id, packet):
        """Log a bytearray as a hexadecimal string"""
        logdbg("%d, %s, '%s': %s" % (int(time.time() + 0.5), time.asctime(), id, binascii.hexlify(packet)))

    def _wmr89_wind_packet(self, packet):
        """Decode a wind packet. Wind speed will be in kph"""
        ## 0  1  2  3  4  5  6  7  8  9  10 
        ## b2 0b 00 00 00 00 00 02 7f 01 3e
        ##    ?     Wa    Wg    Wd Wc ?  CS?
        Wa = packet[3] * 0.36
        Wg = packet[5] * 0.36
        Wd = packet[7] * 22.5
        Wc = packet[8]
        if Wc < 125:
            Wc = FtoC(packet[8])
        elif Wc == 125:
            Wc = None
        elif Wc > 125:
            Wc = FtoC(Wc - 255)

        _record = {
            'wind_speed': Wa,
            'wind_dir': Wd,
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC,
            'wind_gust': Wg,
            'windchill': Wc
        }

        return _record

    def _wmr89_rain_packet(self, packet):
        ## 0  1  2  3  4  5  6  7    8  9  10 11 12 13 14 15 16
        ## b1 11 ff fe 00 08 00 22   00 48 0e 01 01 0d 18 03 66
        ## b1 11 ff fe 00 11 00 11   00 95 0e 01 01 0d 18 03 ab: 4,3 mm  / 11 = 17
        ## b1 11 ff fe 00 ca 00 db   00 5f 0e 01 01 0d 18 04 f8: 116,3 mm - 163,1 / db=219 / 
        ## b1 11 ff fe 00 2a 00 3b   00 be 0e 01 01 0d 18 04 17: 270,8mm - 309,6 / 3b=59 / 
        ##    ?  r/h-- rain  last24  Rtot  ?  ?  ?  ?  ?  ?  CS?
        # station units are inch and inch/hr while the internal metric units are
        # cm and cm/hr. 

        # byte 2-3: rain per hour  
        # fffe = no value
        if packet[2:4] == b'\xff\xfe':
            Rh = None
        else:
            Rh = (256 * packet[2] + packet[3]) * 2.54 / 100

        # byte 4-5: actual rain /100 in inch
        Ra = (256 * packet[4] + packet[5]) * 2.54 / 100
        # byte 6-7: last 24h  /100 in inch
        R24 = (256 * packet[6] + packet[7]) * 2.54 / 100
        # byte 8-9: tot /100 in inch
        Rtot = (256 * packet[8] + packet[9]) * 2.54 / 100

        _record = {
            'rain_rate': Ra,
            'rain_total': Rtot,
            'rain_hour': Rh,
            'rain_24': R24,
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC
        }

        _record['rain'] = weewx.wxformulas.calculate_rain(_record['rain_total'], self.last_rain_total)
        self.last_rain_total = _record['rain_total']

        return _record

    def _wmr89_temp_packet(self, packet):
        ## b50b01006c005408fd0286
        ## b50b027fff33ff7fff04f0
        ## b50b037fff33ff7fff04f1
        ## b50b0100da002f0afd02d1

        ## 0  1  2      3  4  5  6   7   8  9  10
        ## b5 0b 01     00 12 00 54  ff  fd 03 23
        ## b5 0b 01     00 d7 00 2e  0a  fd 02 cd <<-- batterie low
        ## b5 0b 01     00 d6 00 2e  09  fd 02 cb
        ##    ?  sensor temp  ?  hum dew ?  ?  ?
        temp = 256 * packet[3] + packet[4]
        if temp >= 32768:
            temp = temp - 65536
        temp *= 0.1

        # According to specifications the WMR89 humidity range are 25/95% 
        if packet[6] == 254:
            hum = 95
        elif packet[6] == 252:
            hum = 25
        else:
            hum = float(packet[6])

        dew = packet[7]
        if dew == 125:
            dew = None
        elif dew > 125:
            dew -= 256

        if packet[8] == 253:
            heatindex = None
        else:
            heatindex = float(packet[7])

        if packet[2] == 0:
            _record = {
                'humidity_in': hum,
                'temperature_in': float(temp),
                'dewpoint_in': dew,
                'dateTime': int(time.time() + 0.5),
                'usUnits': weewx.METRIC
            }
        elif packet[2] == 0x01:
            _record = {
                'humidity_out': hum,
                'temperature_out': float(temp),
                'dewpoint_out': dew,
                'dateTime': int(time.time() + 0.5),
                'usUnits': weewx.METRIC
            }
        elif packet[2] == 0x02:
            _record = {
                'humidity_1': hum,
                'temperature_1': float(temp),
                'dewpoint_1': dew,
                'dateTime': int(time.time() + 0.5),
                'usUnits': weewx.METRIC
            }
        elif packet[2] == 0x03:
            _record = {
                'humidity_2': hum,
                'temperature_2': float(temp),
                'dewpoint_2': dew,
                'dateTime': int(time.time() + 0.5),
                'usUnits': weewx.METRIC
            }
        else:
            _record = None

        return _record

    def _wmr89_pressure_packet(self, packet):
        ## 0  1  2  3  4  5  6  7  8
        ## b4 09 27 e9 27 e9 03 02 e0
        ## b4 09 27 ea 28 16 03 02 0f
        ##    ?  baro  press ?  ?  ?
        ## weather display? barometric compensation
        Pr = (256 * packet[2] + packet[3]) * 0.1
        bar = (256 * packet[4] + packet[5]) * 0.1

        _record = {
            'pressure': Pr,
            'barometer': bar,
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC
        }

        return _record

    def _wmr89_time_packet(self, packet):
        """The (partial) time packet is not used by weewx.
        However, the last time is saved in case getTime() is called."""
        # DateTime='20'+str(ord(packet[5])).zfill(2)+'/'+str(ord(packet[6])).zfill(2)+'/'+str(ord(packet[7])).zfill(2)+' '+str(ord(packet[8])).zfill(2)+':'+str(ord(packet[9])).zfill(2

        # min1, min10 = self._get_nibble_data(packet[1:])
        # minutes = min1 + ((min10 & 0x07) * 10)

        # cur = time.gmtime()
        # self.last_time = time.mktime(
        #    (cur.tm_year, cur.tm_mon, cur.tm_mday,
        #     cur.tm_hour, minutes, 0,
        #     cur.tm_wday, cur.tm_yday, cur.tm_isdst))
        return None


class WMR89ConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[WMR89]
    # This section is for the Oregon Scientific WMR89

    # Serial port such as /dev/ttyS0, /dev/ttyUSB0, or /dev/cuaU0
    port = /dev/ttyUSB0

    # The driver to use:
    driver = user.wmr89
    
    # Sensor map: map from sensor name to observation name
    [[sensor_map]]
"""

    def prompt_for_settings(self):
        print("Specify the serial port on which the station is connected, for")
        print("example /dev/ttyUSB0 or /dev/ttyS0.")
        port = self._prompt('port', '/dev/ttyUSB0')
        return {'port': port}


# Define a main entry point for basic testing without the weewx engine.
# Invoke this as follows from the weewx root dir:
#
#   PYTHONPATH=bin python bin/weewx/drivers/wmr89.py
#
if __name__ == '__main__':
    import optparse
    import syslog

    # Redefine these so they always use syslog. This ensures running the driver directly will work under
    # WeeWX V3 and V4.
    def logmsg(level, msg):
        syslog.syslog(level, 'wmr89: %s' % msg)

    def logdbg(msg):
        logmsg(syslog.LOG_DEBUG, msg)

    def loginf(msg):
        logmsg(syslog.LOG_INFO, msg)

    def logerr(msg):
        logmsg(syslog.LOG_ERR, msg)

    usage = """Usage: %prog --help
       %prog --version
       %prog [--port=PORT]"""

    syslog.openlog('wmr89', syslog.LOG_PID | syslog.LOG_CONS)
    syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
    weewx.debug = 2

    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--version', dest='version', action='store_true',
                      help='Display driver version')
    parser.add_option('--port', dest='port', metavar='PORT',
                      help='The port to use. Default is %s' % DEFAULT_PORT,
                      default=DEFAULT_PORT)

    options, args = parser.parse_args()

    if options.version:
        print("WMR89 driver version %s" % DRIVER_VERSION)
        exit(0)

    syslog.syslog(syslog.LOG_DEBUG, "wmr89: Running genLoopPackets()")

    stn = WMR89(port=options.port)

    for packet in stn.genLoopPackets():
        print(packet)
