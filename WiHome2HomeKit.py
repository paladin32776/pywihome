"""Starts a fake fan, lightbulb, garage door and a TemperatureSensor
"""
import logging
import signal
import random
from pywihome import WiHome

from pyhap.accessory import Accessory, Bridge
from pyhap.accessory_driver import AccessoryDriver
from pyhap.const import (CATEGORY_FAN,
                         CATEGORY_LIGHTBULB,
                         CATEGORY_GARAGE_DOOR_OPENER,
                         CATEGORY_SENSOR,
                         CATEGORY_SWITCH)


logging.basicConfig(level=logging.INFO, format="[%(module)s] %(message)s")


class TemperatureSensor(Accessory):
    """Fake Temperature sensor, measuring every 3 seconds."""

    category = CATEGORY_SENSOR

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        serv_temp = self.add_preload_service('TemperatureSensor')
        self.char_temp = serv_temp.configure_char('CurrentTemperature')

    @Accessory.run_at_interval(3)
    async def run(self):
        self.char_temp.set_value(random.randint(18, 26))

class GarageDoor(Accessory):
    """Fake garage door."""

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
        self.wihome = None
        if 'wihome' in kwargs:
            self.wihome = kwargs.pop('wihome')
        self.client = None
        if 'client' in kwargs:
            self.client = kwargs.pop('client')
        self.channel = 0
        if 'channel' in kwargs:
            self.channel = kwargs.pop('channel')
        super().__init__(*args, **kwargs)

        serv_switch = self.add_preload_service('Switch')
        self.display = serv_switch.configure_char(
            'On', setter_callback=self.set_state)

        if self.wihome is not None and self.client is not None:
            self.wihome.attach_rx_event_callback(callback=self.state_changed,
                                                 filter={'client': self.client, 'cmd':'info',
                                                         'parameter': 'relay', 'channel': self.channel})

    def set_state(self, value):
        if self.wihome is not None and self.client is not None:
            self.wihome.write({'client': self.client, 'cmd': 'set',
                               'parameter': 'relay', 'channel': self.channel,
                               'value': value})
        logging.info("Set switch %s value: %d" % (self.client, value))

    def state_changed(self, msg):
        self.get_service('Switch').get_characteristic('On').set_value(msg['value'])
        logging.info("Switch %s state changed: %d" % (self.client, msg['value']))

def get_bridge(driver, wihome=None):
    bridge = Bridge(driver, 'Bridge')

    # bridge.add_accessory(LightBulb(driver, 'Lightbulb'))
    # bridge.add_accessory(FakeFan(driver, 'Big Fan'))
    # bridge.add_accessory(GarageDoor(driver, 'Garage'))
    # bridge.add_accessory(TemperatureSensor(driver, 'Sensor'))
    bridge.add_accessory(WiHomeSwitch(driver,'Switch1', wihome=wihome, client='wihomeDEV2', channel=0))
    bridge.add_accessory(WiHomeSwitch(driver, 'Switch2', wihome=wihome, client='wihomeDEV2', channel=1))

    return bridge


wh = WiHome()

driver = AccessoryDriver(port=51826, persist_file='wihome.state')
driver.add_accessory(accessory=get_bridge(driver, wihome=wh))
signal.signal(signal.SIGTERM, driver.signal_handler)
driver.start()