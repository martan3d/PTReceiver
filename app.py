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

# Receiver Message types

RETURNTYPE       = 37

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
        self.working_text.text = "Scanning for Receivers..."

        # broadcast - tell all Xbees to answer who they are
        self.sendNetworkDiscovery()

        # setup the screen buttons we will use for each receiver
        scan_content = toga.Box(style=Pack(direction=COLUMN, alignment=CENTER, margin_top=5))
        button_list = []

        # read the responses, if any, sometimes several scans are required
        size, dataBuffer = self.readXbee()
        self.working_text.text = ""

        scan_content.add(self.discover_button)
        scan_content.add(self.working_text)

        # may be several responses, turn data into list of xbee api frames
        responses = self.parseNodeData(size, dataBuffer)

        # for each message, pull out the mac address and ascii node id
        for r in responses:
            mac, id = self.getMacAndNodeID(r)
            print ("mac:", mac, "id:", id)
            if mac == "" or id == "": continue
            fmstring = "{} {}".format(mac, id)
            button_list.append([mac, id])
            scan_content.add(
                toga.Button(id=mac, text=fmstring,
                    on_press = self.connectToClient,
                    style=Pack(width=230, height=120, margin_top=12, background_color="#bbbbbb", color="#000000", font_size=16),
                )
            )

        self.scroller = toga.ScrollContainer(content=scan_content)
        self.main_window.content = self.scroller
        self.main_window.show()

    # after scan, all devices are displayed as buttons, pressing one of them sends query to that mac address
    def connectToClient(self, buttonid):
        address = self.buildAddress(buttonid)
        data = chr(RETURNTYPE) + "000000000000000000"
        messageFrame = self.buildXbeeTransmitData(address, data)

        self.sendXbeeRequest(messageFrame)
        print ("SEND MESSAGE size", len(messageFrame))
        hexString = ""
        for b in range(0, len(messageFrame)):
            hexString = hexString + hex(messageFrame[b]) + " "
        print (hexString)

        size, dataBuffer = self.readXbee()
        print ("RETURN MESSAGE size", size)
        hexString = ""
        for b in range(0, size):
            hexString = hexString + hex(dataBuffer[b]) + " "
        print (hexString)

    def buildAddress(self, adr):
        address = adr.id
        dest    = [0,0,0,0,0,0,0,0]
        dest[0] = int(address[:2], 16)           # very brute force way to pull this out!
        dest[1] = int(address[2:4], 16)
        dest[2] = int(address[4:6], 16)
        dest[3] = int(address[6:8], 16)
        dest[4] = int(address[8:10], 16)
        dest[5] = int(address[10:12], 16)
        dest[6] = int(address[12:14], 16)
        dest[7] = int(address[14:16], 16)
        return dest

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
            for i in range(10, 18):
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

    def sendXbeeRequest(self, buff):
        data_length = len(buff)
        print (data_length, buff)
        buffer = bytearray(buff)
        status = self.connection.bulkTransfer(self.writeEndpoint, buffer, data_length, USB_WRITE_TIMEOUT_MILLIS)

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


##
## Send Directed Message to an Xbee on the Network
##

    def buildXbeeTransmitData(self, dest, data):
        txdata = []
        dl = len(data)
        for d in data:     # make sure it's in valid bytes for transmit
            try:
               txdata.append(int(ord(d)))
            except:
               txdata.append(int(d))

        frame = []
        frame.append(0x7e)	# header
        frame.append(0)	        # our data is always < 256
        frame.append(dl+11)     # all data except header, length and checksum
        frame.append(0x00)      # TRANSMIT REQUEST 64bit (mac) address - send Query to Xbee module
        frame.append(0x01)      # frame ID for ack- 0 = disable

        frame.append(dest[0])   # 64 bit address (mac)
        frame.append(dest[1])
        frame.append(dest[2])
        frame.append(dest[3])
        frame.append(dest[4])
        frame.append(dest[5])
        frame.append(dest[6])
        frame.append(dest[7])

        frame.append(0x00)      # always reserved

        for i in txdata:        # move data to transmit buffer
            frame.append(i)
        frame.append(0)         # checksum position

        cks = 0;
        for i in range(3, dl+14):	# compute checksum
            cks += int(frame[i])

        i = (255-cks) & 0x00ff
        frame[dl+14] = i        # insert checksum in message

        return frame



def main():
    return PTReceiver()
