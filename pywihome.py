from socket import *
import json
import threading
import time

CMDS_MAX = 256
WIHOME_PORT = 24559

class WiHome(object):

    def __init__(self):
        self.rxq = []  # Receive queue buffer
        self.txq = [] # Transmt queue buffer
        self.devs = {}  # Device IP address<>WiHome name lookup-table
        self.so = socket(family=AF_INET, type=SOCK_DGRAM)
        self.so.bind(('', WIHOME_PORT))

        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True  # Daemonize thread
        thread.start()

    def run(self):
        while True:
            # Receive into rxq or device table:
            data, addr = self.so.recvfrom(4096)
            msg = json.loads(data)
            print(msg)
            print(addr)
            if 'cmd' in msg and msg['cmd']=='findhub':
                print("Replying to findhub request")
                msg['cmd'] = 'hubid'
                self.so.sendto(str.encode(json.dumps(msg)),addr)
                self.devs[msg['client']] = addr[0]
                print("Device table:")
                print(self.devs)
            else:   # Any other command except findhub goes to cmds queue.
                self.rxq.append(msg)   # Add new entry to cmds queue.
                self.rxq = self.rxq[-CMDS_MAX:]   # Limiting queue to CMDS_MAX elements, disposing of oldest entries
            # Transmit from txq:
            for msg in txq:


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
        return True


wh = WiHome()
while True:
    time.sleep(4)
    while wh.isrx():
        print(["POP: ", wh.read()])
    pass
# UDPClientSocket.sendto(str.encode("{'cmd':'set','parameter':'relay','value':0}"), ("192.168.0.255", 24556))
