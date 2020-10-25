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

for L in logging.Logger.manager.loggerDict:
    logging.getLogger(L).disabled = True

# logging.getLogger('pywihome').disabled = False

logger = logging.getLogger()
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)


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


class WiHomeGateOpenerSetup(Accessory):

    category = CATEGORY_LIGHTBULB

    def __init__(self, *args, **kwargs):

        self.wihome = pop_parameters_by_prefix(kwargs, 'wihome_')
        super().__init__(*args, **kwargs)

        # Homekit accessory setup: type and callbacks for Homekit events
        serv_setup = self.add_preload_service('Lightbulb', chars=['Brightness'])
        serv_setup.configure_char('On', setter_callback=self.set_on)
        serv_setup.configure_char('Brightness', setter_callback=self.set_brightness)

        # Store characteristics in class variables for easier access:
        self.On = serv_setup.get_characteristic('On')
        self.Value = serv_setup.get_characteristic('Brightness')

        # Callback function setup for WiHome events:
        if wihome_parameters_valid(self.wihome):
            self.wihome['instance'].attach_rx_event_callback(callback=self.parameters_received,
                                                             filter={'cmd': 'info',
                                                                     'client': self.wihome['client']})
            self.wihome['instance'].write({'cmd': 'get_parameters',
                                           'client': self.wihome['client']})

    def percent2value(self, percent):
        return self.wihome['scaling_0'] + (self.wihome['scaling_100'] - self.wihome['scaling_0']) * percent/100

    def value2percent(self, value):
        return (value - self.wihome['scaling_0'])  / (self.wihome['scaling_100'] - self.wihome['scaling_0']) * 100


    def set_on(self, value):
        logger.info('set_on %s: value=%d | on=%d | value=%d%% | scaled_value=%d' %
                     (self.wihome['parameter'],
                      value,
                      self.On.get_value(),
                      self.Value.get_value(),
                      self.percent2value(self.Value.get_value() * value)))
        if wihome_parameters_valid(self.wihome):
            self.wihome['instance'].write({'cmd': 'set',
                                           self.wihome['parameter']: self.percent2value(self.Value.get_value() * value),
                                           'client': self.wihome['client']})
            # logger.info("Set (On) %s=%d" % (self.wihome['parameter'], self.percent2value(self.Value.get_value() * value)))

    def set_brightness(self, value):
        logger.info('set_brightness %s: on=%d | value=%d%% | scaled_value=%d' %
                     (self.wihome['parameter'],
                      self.On.get_value(),
                      self.Value.get_value(),
                      self.percent2value(self.Value.get_value())))
        # if wihome_parameters_valid(self.wihome):
        #     self.wihome['instance'].write({'cmd': 'set',
        #                                    self.wihome['parameter']: self.percent2value(value),
        #                                    'client': self.wihome['client']})
        #     logger.info("Set (Brightness) %s=%d" % (self.wihome['parameter'], self.percent2value(value)))

    def parameters_received(self, msg):
        if self.wihome['parameter'] in msg:
            self.Value.set_value(self.value2percent(msg[self.wihome['parameter']]))
            self.On.set_value(self.Value.get_value()>0)
            logger.info('Parameter %s=%d: on=%d | value=%d%%' % (self.wihome['parameter'], msg[self.wihome['parameter']],
                                                                self.On.get_value(), self.Value.get_value()))

class WiHomeGateOpener(Accessory):
    # WiHome Gate Opener

    category = CATEGORY_GARAGE_DOOR_OPENER

    def __init__(self, *args, **kwargs):

        self.wihome = pop_parameters_by_prefix(kwargs, 'wihome_')
        super().__init__(*args, **kwargs)

        # Homekit accessory setup: type and callbacks for Homekit events
        self.serv_gate = self.add_preload_service('GarageDoorOpener')
        self.serv_gate.configure_char('TargetDoorState', setter_callback=self.set_state)

        # Store characteristics in class variables for easier access:
        self.CurrentDoorState = self.serv_gate.get_characteristic('CurrentDoorState')
        self.TargetDoorState = self.serv_gate.get_characteristic('TargetDoorState')
        self.ObstructionDetected = self.serv_gate.get_characteristic('ObstructionDetected')

        # Callback function setup for WiHome info command events:
        if wihome_parameters_valid(self.wihome):
            self.wihome['instance'].attach_rx_event_callback(callback=self.state_changed,
                                                             filter={'cmd': 'info',
                                                                     'client': self.wihome['client']})
            self.wihome['instance'].write({'cmd': 'get_status',
                                           'client': self.wihome['client']})

    def set_state(self, value):
        TargetDoorState = self.TargetDoorState.get_value()
        CurrentDoorState = self.CurrentDoorState.get_value()
        logger.info("set_state POS 1: TARGET=%d | CURRENT=%d |  VALUE=%d" %
                     (TargetDoorState, CurrentDoorState, value))
        if CurrentDoorState == 2:
            state = 0
            self.TargetDoorState.set_value(0)
            self.CurrentDoorState.set_value(4)
            self.ObstructionDetected.set_value(True)
        elif CurrentDoorState == 3:
            state = 0
            self.TargetDoorState.set_value(1)
            self.CurrentDoorState.set_value(4)
            self.ObstructionDetected.set_value(True)
        elif CurrentDoorState == 4:
            state = (TargetDoorState) * 2 - 1
            self.TargetDoorState.set_value(TargetDoorState)
            self.ObstructionDetected.set_value(False)
        else: #
            state = (1-CurrentDoorState) * 2 - 1
            self.TargetDoorState.set_value(1-CurrentDoorState)
            self.ObstructionDetected.set_value(False)

        logger.info("set_state POS 2: TARGET=%d | CURRENT=%d" %
                     (self.TargetDoorState.get_value(), self.CurrentDoorState.get_value()))

        if wihome_parameters_valid(self.wihome):
            self.wihome['instance'].write({'cmd': 'set',
                                           'state': state,
                                           'client': self.wihome['client']})

        logger.info("set_state POS 3: TARGET=%d | CURRENT=%d" %
                     (self.TargetDoorState.get_value(), self.CurrentDoorState.get_value()))

    def state_changed(self, msg):
        if 'state' in msg and 'position_percent' in msg:
            logger.info(
                "state_changed POS1: TARGET=%d | CURRENT=%d | OBSTRUCTION=%d" %
                (self.TargetDoorState.get_value(), self.CurrentDoorState.get_value(),
                 self.ObstructionDetected.get_value()))
            if msg['state'] == 0 and msg['position_percent'] == 0:
                # Homekit: open = 0
                self.CurrentDoorState.set_value(0)
                self.TargetDoorState.set_value(0)
                self.ObstructionDetected.set_value(False)
            elif msg['state'] == 0 and msg['position_percent'] == 100:
                # Homekit: closed = 1
                self.CurrentDoorState.set_value(1)
                self.TargetDoorState.set_value(1)
                self.ObstructionDetected.set_value(False)
            elif msg['state'] == 0 and msg['position_percent'] >0 and msg['position_percent']<100:
                # Homekit: stopped = 4
                self.CurrentDoorState.set_value(4)
                self.TargetDoorState.set_value(self.TargetDoorState.get_value())
                self.ObstructionDetected.set_value(True)
            elif msg['state'] == 1:
                #Homekit: closing = 3
                self.CurrentDoorState.set_value(3)
                self.TargetDoorState.set_value(1)
                self.ObstructionDetected.set_value(False)
            elif msg['state'] == -1:
                # Homekit: opening = 2
                self.CurrentDoorState.set_value(2)
                self.TargetDoorState.set_value(0)
                self.ObstructionDetected.set_value(False)
            else:
                return
            logger.info(
                "state_changed POS2: TARGET=%d | CURRENT=%d | OBSTRUCTION=%d" %
                (self.TargetDoorState.get_value(), self.CurrentDoorState.get_value(),
                 self.ObstructionDetected.get_value()))


class WiHomeSwitch(Accessory):
    # WiHome Switch
    category = CATEGORY_SWITCH

    def __init__(self, *args, **kwargs):

        self.wihome = pop_parameters_by_prefix(kwargs, 'wihome_')
        super().__init__(*args, **kwargs)

        # Homekit accessory setup: type and callbacks for Homekit events
        serv_switch = self.add_preload_service('Switch')
        serv_switch.configure_char('On', setter_callback=self.set_state)

        # Callback function setup for WiHome events:
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
            logger.info("Set switch %s value: %d" % (self.wihome['client'], value))

    def state_changed(self, msg):
        self.get_service('Switch').get_characteristic('On').set_value(msg['value'])
        if wihome_parameters_valid(self.wihome):
            logger.info("Switch %s state changed: %d" % (self.wihome['client'], msg['value']))


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
        elif acc['accessory'] == 'WiHomeGateOpener':
            for inst in acc['instances']:
                bridge.add_accessory(WiHomeGateOpener(_driver, inst['homekit_label'], wihome_instance=wihome,
                                                      wihome_client=inst['wihome_client']))
        elif acc['accessory'] == 'WiHomeGateOpenerSetup':
            for inst in acc['instances']:
                bridge.add_accessory(WiHomeGateOpenerSetup(_driver, inst['homekit_label'], wihome_instance=wihome,
                                                           wihome_parameter=inst['wihome_parameter'],
                                                           wihome_scaling_0=inst['wihome_scaling_0'],
                                                           wihome_scaling_100=inst['wihome_scaling_100'],
                                                           wihome_client=inst['wihome_client']))

    return bridge


wh = WiHome()

driver = AccessoryDriver(port=51826, persist_file='wihome.state')
driver.add_accessory(accessory=get_bridge(driver, wihome=wh))
signal.signal(signal.SIGTERM, driver.signal_handler)
driver.start()
