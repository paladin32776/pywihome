from socket import *
import json
import threading
import time
import logging

logging.basicConfig(level=logging.INFO)

class WiHome(object):

    RX_BUF = 256
    TX_BUF = 256
    WIHOME_PORT = 24559
    WIHOME_FINDCLIENT_DELAY = 3

    def __init__(self):
        # Setup buffers and tables:
        self.rxq = []  # Receive queue
        self.txq = []  # Transmit queue
        self.devs = {}  # Device IP address<>WiHome name lookup-table
        self.fdevs = {}  # Table to memorize history of findclient requests sent
        # Setup UDP socket:
        self.so = socket(family=AF_INET, type=SOCK_DGRAM)
        self.so.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        self.so.bind(('', self.WIHOME_PORT))
        # RX callback event table:
        self.rx_callback_events = []

        # Starting separate thread for handling and queuing incomimg WiHome messages:
        logging.info('Starting WiHome background RX thread.')
        rxthread = threading.Thread(target=self.rxloop, args=())
        rxthread.daemon = True  # Daemonize thread
        rxthread.start()

        # Starting separate thread for launching rx handler function if RX queue contains message:
        logging.info('Starting WiHome background RX callback function thread.')
        rx_callback_thread = threading.Thread(target=self.rx_callback, args=())
        rx_callback_thread.daemon = True  # Daemonize thread
        rx_callback_thread.start()

        # Starting separate thread for sending queued outgoing WiHome messages:
        logging.info('Starting WiHome background TX thread.')
        txthread = threading.Thread(target=self.txloop, args=())
        txthread.daemon = True  # Daemonize thread
        txthread.start()

    def rxloop(self):
        while True:
            time.sleep(0.010)
            # Receive into self.rxq or fill device table:
            data, addr = self.so.recvfrom(4096)
            msg = json.loads(data.decode("utf-8"))
            ip = addr[0]
            logging.info('RX:(' + ip + '):' + json.dumps(msg))
            if 'cmd' in msg and msg['cmd'] == 'findhub':
                logging.info("Responding to findhub request.")
                msg['cmd'] = 'hubid'
                self._sendto(msg, ip)
                self.devs[msg['client']] = ip
            elif 'cmd' in msg and msg['cmd'] == 'clientid':
                logging.info("Received clientid.")
                self.devs[msg['client']] = ip
            elif 'cmd' in msg and msg['cmd'] == 'findclient':
                pass
            else:   # Any other command except findhub, findclient, and clientid goes to rx queue:
                self.rxq.append(msg)   # Add new entry to cmds queue.
                self.rxq = self.rxq[-self.RX_BUF:]   # Limiting queue to CMDS_MAX elements, disposing of oldest entries

    def rx_callback(self):
        while True:
            time.sleep(0.010)
            if self.isrx():
                msg = self.read()
                for rx_callback_event in self.rx_callback_events:
                    filters = rx_callback_event['filter']
                    callback = rx_callback_event['callback']
                    fits = all([fkey in msg and msg[fkey]==fvalue for fkey, fvalue in filters.items()])
                    if fits:
                        logging.info('RX callback to ' + callback.__name__ + '.')
                        callback(msg)

    def txloop(self):
        while True:
            time.sleep(0.010)
            # Transmit from self.txq:
            if len(self.txq) > 0:
                txq = []
                for msg in self.txq:
                    if msg['client'] not in self.devs:
                        self.send_findclient(msg['client'])
                        txq.append(msg)
                    else:
                        logging.info('TX:(' + self.devs[msg['client']] + '):' + json.dumps(msg))
                        self._sendto(msg, self.devs[msg['client']])
                self.txq = txq

    def attach_rx_event_callback(self, callback, filter={}):
        if hasattr(callback, '__call__'):
            self.rx_callback_events.append({'filter': filter, 'callback': callback})

    def _sendto(self, msg=None, ip=None):
        if ip is None:
            ip = '<broadcast>'
        self.so.sendto(str.encode(json.dumps(msg)), (ip, self.WIHOME_PORT))

    def send_findclient(self, client):
        if self.findclient_delay_passed(client):
            logging.info('Sending findclient command for %s.' % client)
            self._sendto({'cmd': 'findclient', 'client': client})

    def findclient_delay_passed(self, client):
        current_time = time.time()
        if client not in self.fdevs or current_time-self.fdevs[client] > self.WIHOME_FINDCLIENT_DELAY:
            self.fdevs[client] = current_time
            return True
        return False

    def isrx(self):
        return len(self.rxq) > 0

    def read(self):
        if self.isrx():
            return self.rxq.pop(0)
        else:
            return False

    def write(self, msg):
        if 'client' not in msg:
            return False
        self.txq.append(msg)
        logging.info(self.txq)
        return True


# def test_rx_callback(msg):
#     logging.info('test_rx_callback')
#     print(msg)
#
# wh = WiHome(test_rx_callback)
# t = time.time()
# while True:
#     pass
