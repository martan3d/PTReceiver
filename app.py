"""
Protothrottle Receiver Programmer App
"""

import toga
import asyncio
import time
from toga.style import Pack
from toga import Button, MultilineTextInput, Label, TextInput
from toga.style.pack import COLUMN, ROW, CENTER
from java import jclass
from android.content import Context

# Silicon Labs USB constants

CP210X_IFC_ENABLE         = 0x00
UART_ENABLE               = 0x0001
REQTYPE_HOST_TO_INTERFACE = 0x41
USB_READ_TIMEOUT_MILLIS   = 5000
USB_WRITE_TIMEOUT_MILLIS  = 5000
CP210X_SET_BAUDDIV        = 0x01
BAUD_RATE_GEN_FREQ        = 0x384000
DEFAULT_BAUDRATE          = 38400
DEFAULT_READ_BUFFER_SIZE  = 1024

# Android Java Class names, used for permissions

Intent = jclass('android.content.Intent')
PendingIntent = jclass('android.app.PendingIntent')


# Main App

class PTReceiver(toga.App):
    def startup(self):

        self.discover_button = Button(
            'Scan',
            on_press=self.start_discover,
            style=Pack(width=120, height=60, margin_top=6, background_color="#cccccc", color="#000000", font_size=12)
        )

        self.working_text = Label("", style=Pack(font_size=12, color="#000000"))

        scan_content = toga.Box(style=Pack(direction=COLUMN, alignment=CENTER, margin_top=5))
        scan_content.add(self.discover_button)
        scan_content.add(self.working_text)

        self.scroller = toga.ScrollContainer(content=scan_content)

        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self.scroller
        self.main_window.show()

        # Use Android java classes to query and control OTG USB port

        self.context = jclass('org.beeware.android.MainActivity').singletonThis
        self.usbmanager = self.context.getSystemService(self.context.USB_SERVICE)
        self.usbDevices = self.usbmanager.getDeviceList()

        # Check to see if Xbee device is connected, should only be one
        iterator = self.usbDevices.entrySet().iterator()
        while iterator.hasNext():
           entry = iterator.next()
           self.device = entry.getValue()

        # Check USB Permissions, get them if needed
        self.checkPermission()

        # open and configure as serial port
        self.openAndConfigureUSBPort()

        # test connection by sending a broadcast to all nodes, nothing special, not really needed
        self.sendTestMessage()


    # Send network discovery, all Xbees on this network return who they are
    def start_discover(self, widget):
        self.sendNetworkDiscovery()
        size, dataBuffer = self.readXbee()

        # may be several responses, turn data into list of xbee api frames
        responses = self.parseNodeData(size, dataBuffer)

        # for each message, pull out the mac address and ascii node id
        for r in responses:
            mac, id = self.getMacAndNodeID(r)
            print ("mac:", mac, "id:", id)


    # iterates through the data to turn it into a list of one or more messages, delimited by 0x7E
    def parseNodeData(self, size, data):
        messages = []
        msg = []
        if size > 0:
           msg.append(data[0])
        for i in range(1, size):
            if data[i] == 0x7e:
               messages.append(msg)
               msg = []
               msg.append(data[i])
            else:
               msg.append(data[i])
        messages.append(msg)
        return messages


    # parses through a list that is an API Node ID return fram and pulls out the mac address and name
    def getMacAndNodeID(self, data):
        mac = "" 
        id = ""
        if len(data) > 20:
            for i in range(11, 19):
                mac = mac + "{:02X}".format(data[i])
            for i in range(19, len(data)-2):
                id = id + chr(data[i])
        return mac, id



    # read any data from the Xbee
    def readXbee(self):
        buf = bytearray(DEFAULT_READ_BUFFER_SIZE)
        totalBytesRead = self.connection.bulkTransfer(
            self.readEndpoint,
            buf,
            DEFAULT_READ_BUFFER_SIZE,
            USB_READ_TIMEOUT_MILLIS,
        )
        return totalBytesRead, buf



    # General messages
    def sendTestMessage(self):
        buf = bytearray([0x7E, 0x00, 0x11, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0x00, 0x4D, 0x61, 0x72, 0x74, 0x69, 0x6E, 0x95])
        data_length = len(buf)
        status = self.connection.bulkTransfer(self.writeEndpoint, buf, data_length, USB_WRITE_TIMEOUT_MILLIS)

    def sendNetworkDiscovery(self):
        buf = bytearray([0x7E, 0x00, 0x04, 0x08, 0x01, 0x4E, 0x44, 0x64])
        data_length = len(buf)
        status = self.connection.bulkTransfer(self.writeEndpoint, buf, data_length, USB_WRITE_TIMEOUT_MILLIS)


    # open the USB port and configure it as a serial port to talk to the Xbee
    def openAndConfigureUSBPort(self):
        self.connection = self.usbmanager.openDevice(self.device)
        self.interface = self.device.getInterface(0)
        self.readEndpoint = self.interface.getEndpoint(0)
        self.writeEndpoint = self.interface.getEndpoint(1)

        buf = None

        result = self.connection.controlTransfer(
                 REQTYPE_HOST_TO_INTERFACE,
                 CP210X_IFC_ENABLE,
                 UART_ENABLE,
                 0,
                 buf,
                 (0 if buf is None else len(buf)),
                 USB_WRITE_TIMEOUT_MILLIS,
                 )

        result = self.connection.controlTransfer(
                 REQTYPE_HOST_TO_INTERFACE,
                 CP210X_SET_BAUDDIV,
                 int(BAUD_RATE_GEN_FREQ / DEFAULT_BAUDRATE),
                 0,
                 buf,
                 (0 if buf is None else len(buf)),
                 USB_WRITE_TIMEOUT_MILLIS,
                 )


    # check for permission from the user and wait if required
    def checkPermission(self):
        ACTION_USB_PERMISSION = "com.access.device.USB_PERMISSION"
        intent = Intent(ACTION_USB_PERMISSION)
        try:
           pintent = PendingIntent.getBroadcast(self.context, 0, intent, 0)
        except Exception:
           pintent = PendingIntent.getBroadcast(self.context, 0, intent, PendingIntent.FLAG_IMMUTABLE)
        
        self.usbmanager.requestPermission(self.device, pintent)

        hasPermission = self.usbmanager.hasPermission(self.device)
        while not hasPermission:
            hasPermission = self.usbmanager.hasPermission(self.device)


def main():
    return PTReceiver()
