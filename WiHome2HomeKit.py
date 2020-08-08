"""WiHome2Homekit V0.1
Gernot Fattinger
2020-08-07
"""
import logging
import signal
import random
import json
from pywihome import WiHome

from pyhap.accessory import Accessory, Bridge
from pyhap.accessory_driver import AccessoryDriver
from pyhap.const import (CATEGORY_FAN,
                         CATEGORY_LIGHTBULB,
                         CATEGORY_GARAGE_DOOR_OPENER,
                         CATEGORY_SENSOR,
                         CATEGORY_SWITCH)


logging.basicConfig(level=logging.INFO, format="[%(module)s] %(message)s")


# class TemperatureSensor(Accessory):
#     """Fake Temperature sensor, measuring every 3 seconds."""
#
#     category = CATEGORY_SENSOR
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#
#         serv_temp = self.add_preload_service('TemperatureSensor')
#         self.char_temp = serv_temp.configure_char('CurrentTemperature')
#
#     @Accessory.run_at_interval(3)
#     async def run(self):
#         self.char_temp.set_value(random.randint(18, 26))

# class GarageDoor(Accessory):
#     """Fake garage door."""
#
#     category = CATEGORY_GARAGE_DOOR_OPENER
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#
#         self.add_preload_service('GarageDoorOpener')\
#             .configure_char(
#                 'TargetDoorState', setter_callback=self.change_state)
#
#     def change_state(self, value):
#         logging.info("Bulb value: %s", value)
#         self.get_service('GarageDoorOpener')\
#             .get_characteristic('CurrentDoorState')\
#             .set_value(value)


def strip_prefix(string, prefix=''):
    """
    Helper function strip a prefix off a string
    """
    if string.startswith(prefix):
        return string[len(prefix):]
    return string


def pop_parameters_by_prefix(parameter_dict=None, prefix=None):
    """
    Helper function to extract all entries from a dictionary, where
    the key starts with the string in prefix.
    Entries are removed from original dict, and function returns a
    new dict with the extracted entries.
    """
    if prefix is None:
        return {}
    keys = [key for key in parameter_dict if key.startswith(prefix)]
    return {strip_prefix(key, prefix): parameter_dict.pop(key) for key in keys}


def wihome_parameters_valid(wihome):
    if 'instance' in wihome and 'client' in wihome and wihome['instance'] is not None and wihome['client'] is not None:
        return True
    return False


class WiHomeGateOpener(Accessory):
    # WiHome Gate Opener

    category = CATEGORY_GARAGE_DOOR_OPENER

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.add_preload_service('GarageDoorOpener')\
            .configure_char(
                'TargetDoorState', setter_callback=self.change_state)

    def change_state(self, value):
        logging.info("Bulb value: %s", value)
        self.get_service('GarageDoorOpener')\
            .get_characteristic('CurrentDoorState')\
            .set_value(value)


class WiHomeSwitch(Accessory):
    # WiHome Switch
    category = CATEGORY_SWITCH

    def __init__(self, *args, **kwargs):

        self.wihome = pop_parameters_by_prefix(kwargs, 'wihome_')
        super().__init__(*args, **kwargs)

        serv_switch = self.add_preload_service('Switch')
        self.display = serv_switch.configure_char('On', setter_callback=self.set_state)

        if wihome_parameters_valid(self.wihome):
            self.wihome['instance'].attach_rx_event_callback(callback=self.state_changed,
                                                             filter={'cmd': 'info',
                                                                     'parameter': 'relay',
                                                                     'channel': self.wihome['channel'],
                                                                     'client': self.wihome['client']})

    def set_state(self, value):
        if wihome_parameters_valid(self.wihome):
            self.wihome['instance'].write({'cmd': 'set',
                                           'parameter': 'relay',
                                           'channel': self.wihome['channel'],
                                           'value': value,
                                           'client': self.wihome['client']})
            logging.info("Set switch %s value: %d" % (self.wihome['client'], value))

    def state_changed(self, msg):
        self.get_service('Switch').get_characteristic('On').set_value(msg['value'])
        if wihome_parameters_valid(self.wihome):
            logging.info("Switch %s state changed: %d" % (self.wihome['client'], msg['value']))


def get_bridge(_driver, wihome=None):
    bridge = Bridge(driver, 'Bridge')

    f = open('wihome.json')
    accs = json.loads(f.read())
    f.close()

    for acc in accs:
        if acc['accessory'] == 'WiHomeSwitch':
            for inst in acc['instances']:
                bridge.add_accessory(WiHomeSwitch(_driver, inst['homekit_label'], wihome_instance=wihome,
                                                  wihome_client=inst['wihome_client'],
                                                  wihome_channel=inst['wihome_channel']))

    return bridge


wh = WiHome()

driver = AccessoryDriver(port=51826, persist_file='wihome.state')
driver.add_accessory(accessory=get_bridge(driver, wihome=wh))
signal.signal(signal.SIGTERM, driver.signal_handler)
driver.start()
