"""
Protothrottle Receiver Programmer App
"""

import toga
import asyncio
import time
from toga.style import Pack
from toga import Button, MultilineTextInput, Label, TextInput
from toga.style.pack import COLUMN, ROW, CENTER, RIGHT, LEFT, START, END

if toga.platform.current_platform == 'android':
   from java import jclass
   from android.content import Context
else:
   import serial
   import serial.tools.list_ports

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

# Ids for buttons and text/numeric inputs

PTID = 1000
BASE = 1001
ADDR = 1002
CONS = 1003
COND = 1004
DECO = 1005
SRV0 = 1010
SRV1 = 1011
SRV2 = 1012
SRVM = 1013
SVR0 = 1014
SVR1 = 1015
SVR2 = 1016
SV0L = 1017
SV0H = 1018
SV1L = 1019
SV1H = 1020
SV2L = 1021
SV2H = 1022
SRVP = 1023
SRRP = 1024

SRVP0 = 1025
SRVP1 = 1026
SRVP2 = 1027

OUTX = 1040
OUTY = 1041
WDOG = 1050
BRAT = 1050
BFNC = 1061
ACCL = 1062
DECL = 1063



if toga.platform.current_platform == 'android':
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

        scan_content = toga.Box(style=Pack(direction=COLUMN, align_items=CENTER, margin_top=5))
        scan_content.add(self.discover_button)
        scan_content.add(self.working_text)

        self.scroller = toga.ScrollContainer(content=scan_content, style=Pack(direction=COLUMN, align_items=CENTER))

        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self.scroller
        self.main_window.show()

        # Use Android or PC code?
        if toga.platform.current_platform == 'android':
           self.setupAndroidSerialPort()
        else:
           self.setupPCSerialPort()


    # PC serial port
    def setupPCSerialPort(self):
        self.sp = None
        ports = serial.tools.list_ports.comports()
        for port, desc, hwid in sorted(ports):
            if 'Silicon Labs CP210' in desc:
               try:
                  sp = serial.Serial(port, 38400, timeout=0.25)
                  self.sp = sp
                  print ('xbee port opened')
                  return
               except:
                  print ('Silicon Labs CP210x USB Driver Not Found!')
                  pass

    def getStatus(self):
        return self.sp

    def close(self):
        self.sp.close()

    def clear(self):
        if self.sp != None:
           self.sp.reset_input_buffer()

    def xbeeReturnResult(self, datalength):
        return(self.sp.read(datalength))


    # Android serial port
    def setupAndroidSerialPort(self):
        # for now, Android
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
#        self.sendTestMessage()


    # Send network discovery, all Xbees on this network return who they are
    def start_discover(self, widget):
        self.working_text.text = "Scanning for Receivers..."

        # broadcast - tell all Xbees to answer who they are
        self.sendNetworkDiscovery()

        # setup the screen buttons we will use for each receiver
        scan_content = toga.Box(style=Pack(direction=COLUMN, align_items=CENTER, margin_top=5))
        self.buttonDict = {}

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
            fmstring = "{} {}".format(id, mac)
            self.buttonDict[mac] = id
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

#        self.sendXbeeRequest(messageFrame)
#        print ("SEND MESSAGE size", len(messageFrame))
#        hexString = ""
#        for b in range(0, len(messageFrame)):
#            hexString = hexString + hex(messageFrame[b]) + " "
#        print (hexString)

#        size, dataBuffer = self.readXbee()
#        print ("RETURN MESSAGE size", size)
#        hexString = ""
#        for b in range(0, size):
#            hexString = hexString + hex(dataBuffer[b]) + " "
#        print (hexString)

        scan_content = toga.Box(style=Pack(direction=COLUMN, margin=30))

        MARGINTOP = 2
        LNUMWIDTH = 64
        SNUMWIDTH = 32

        # Ascii ID and Mac at top of display
        idlabel  = toga.Label(self.buttonDict[buttonid.id], style=Pack(flex=1, color="#000000", align_items=CENTER, font_size=32))
        maclabel = toga.Label(buttonid.id, style=Pack(flex=1, color="#000000", align_items=CENTER, font_size=12))
        boxrowA  = toga.Box(children=[idlabel], style=Pack(direction=ROW, align_items=END, margin_top=4))
        boxrowB  = toga.Box(children=[maclabel], style=Pack(direction=ROW, align_items=END, margin_top=2))

        scan_content.add(boxrowA)
        scan_content.add(boxrowB)

        btn    = toga.Button(id=PTID, text="Prg", on_press = self.sendPrgCommand, style=Pack(width=55, height=55, margin_top=6, background_color="#bbbbbb", color="#000000", font_size=12))
        desc   = toga.Label("Protothrottle ID", style=Pack(width=275, align_items=END, font_size=18))
        entry  = toga.TextInput(on_change=self.change_ptid, style=Pack(flex=1, height=45, width=SNUMWIDTH, margin_bottom=2, font_size=18, background_color="#eeeeee", color="#000000"))
        boxrow = toga.Box(children=[desc, entry, btn], style=Pack(direction=ROW, align_items=END, margin_top=MARGINTOP))
        scan_content.add(boxrow)

        btn    = toga.Button(id=BASE, text="Prg", on_press = self.sendPrgCommand, style=Pack(width=55, height=55, margin_top=6, background_color="#bbbbbb", color="#000000", font_size=12))
        desc   = toga.Label("Base ID", style=Pack(width=275, align_items=END, font_size=18))
        entry  = toga.NumberInput(on_change=self.change_ptid, style=Pack(flex=1, height=45, width=SNUMWIDTH, margin_bottom=2, font_size=18, background_color="#eeeeee", color="#000000"))
        boxrow = toga.Box(children=[desc, entry, btn], style=Pack(direction=ROW, align_items=END, margin_top=MARGINTOP))
        scan_content.add(boxrow)

        btn    = toga.Button(id=ADDR, text="Prg", on_press = self.sendPrgCommand, style=Pack(width=55, height=55, margin_top=6, background_color="#bbbbbb", color="#000000", font_size=12))
        desc   = toga.Label("Loco Address", style=Pack(width=244, align_items=END, font_size=18))
        entry  = toga.NumberInput(on_change=self.change_ptid, min=0, max=9999, style=Pack(flex=1, height=48, width=LNUMWIDTH, margin_bottom=2, font_size=18, background_color="#eeeeee", color="#000000"))
        boxrow = toga.Box(children=[desc, entry, btn], style=Pack(direction=ROW, align_items=END, margin_top=MARGINTOP))
        scan_content.add(boxrow)

        btn0   = toga.Button(id=COND, text="OFF", on_press = self.sendPrgCommand, style=Pack(width=80, height=55, margin_top=6, background_color="#bbbbbb", color="#000000", font_size=14))
        btn1   = toga.Button(id=CONS, text="Prg", on_press = self.sendPrgCommand, style=Pack(width=55, height=55, margin_top=6, background_color="#bbbbbb", color="#000000", font_size=12))
        desc   = toga.Label("Consist Address", style=Pack(width=164, align_items=END, font_size=18))
        entry  = toga.NumberInput(on_change=self.change_ptid, min=0, max=9999, style=Pack(flex=1, height=48, width=LNUMWIDTH, font_size=18, background_color="#eeeeee", color="#000000"))
        boxrow = toga.Box(children=[desc, btn0, entry, btn1], style=Pack(direction=ROW, align_items=END, margin_top=MARGINTOP))
        scan_content.add(boxrow)
        
        btn    = toga.Button(id=DECO, text="Prg", on_press = self.sendPrgCommand, style=Pack(width=55, height=55, margin_top=10, background_color="#bbbbbb", color="#000000", font_size=12))
        desc   = toga.Label("DCC Addr", style=Pack(width=244, align_items=END, font_size=18))
        entry  = toga.NumberInput(on_change=self.change_ptid, min=0, max=9999, style=Pack(flex=1, height=48, width=LNUMWIDTH, font_size=18, background_color="#eeeeee", color="#000000"))
        boxrow = toga.Box(children=[desc, entry, btn], style=Pack(direction=ROW, align_items=END, margin_top=MARGINTOP))
        scan_content.add(boxrow)
 
       #############################################################  Servo Mode

        blank  = toga.Label("   ")
        boxrow = toga.Box(children=[blank, toga.Divider(), blank], style=Pack(direction=COLUMN, margin_top=20))
        scan_content.add(boxrow)

        btn    = toga.Button(id=SRVP, text="Prg", on_press = self.sendPrgCommand, style=Pack(width=55, height=55, margin_top=6, background_color="#bbbbbb", color="#000000", font_size=12))
        desc   = toga.Label("Servo Mode", style=Pack(width=273, align_items=END, margin_bottom=10, font_size=18))
        mode   = toga.Button(id=SRVM, text="ESC", on_press = self.sendPrgCommand, style=Pack(width=90, height=55, background_color="#bbbbbb", color="#000000", font_size=12))
        boxrow = toga.Box(children=[desc, mode], style=Pack(direction=ROW, align_items=END, margin_top=20))
        scan_content.add(boxrow)

       ############################################################# 

        boxrow = toga.Box(children=[blank, toga.Divider(), blank], style=Pack(direction=COLUMN, margin_top=20))
        scan_content.add(boxrow)

       ############################################################# Servo 0 Config

        desc   = toga.Label("Servo 0", style=Pack(width=270, align_items=END, font_size=18))
        rev    = toga.Switch("Reverse", id=SVR0, value=False, on_change=self.change_ptid)
        boxrow = toga.Box(children=[desc, rev], style=Pack(direction=ROW, align_items=END, margin_top=8))
        scan_content.add(boxrow)

        btn    = toga.Button(id=SRVP0, text="Prg", on_press = self.sendPrgCommand, style=Pack(width=55, height=55, margin_top=6, background_color="#bbbbbb", color="#000000", font_size=12))
        desc   = toga.Label("     Function Code", style=Pack(width=282, align_items=END, font_size=12))
        func   = toga.NumberInput(on_change=self.change_ptid, min=0, max=99, style=Pack(flex=1, height=48, width=24, font_size=12, background_color="#eeeeee", color="#000000"))
        boxrow = toga.Box(children=[desc, func, btn], style=Pack(direction=ROW, align_items=END, margin_top=1))
        scan_content.add(boxrow)

        desc   = toga.Label("     Low Limit", style=Pack(width=244, align_items=END, font_size=12))
        entry0 = toga.NumberInput(on_change=self.change_ptid, min=0, max=1000, style=Pack(flex=1, height=48, width=LNUMWIDTH, font_size=18, background_color="#eeeeee", color="#000000"))
        btn    = toga.Button(id=SV0L, text="Prg", on_press = self.sendPrgCommand, style=Pack(width=55, height=55, margin_top=6, background_color="#bbbbbb", color="#000000", font_size=12))
        boxrow = toga.Box(children=[desc, entry0, btn], style=Pack(direction=ROW, align_items=END, margin_top=1))
        scan_content.add(boxrow)

        desc   = toga.Label(" ", style=Pack(width=20, align_items=END, font_size=18))
        adj0   = toga.Slider(value=0, min=0, max=1000, on_change=self.setLimit, style=Pack(width=320, height=20))
        boxrow = toga.Box(children=[desc, adj0], style=Pack(direction=ROW, align_items=END))
        scan_content.add(boxrow)

        btn    = toga.Button(id=SV0H, text="Prg", on_press = self.sendPrgCommand, style=Pack(width=55, height=55, margin_top=6, background_color="#bbbbbb", color="#000000", font_size=12))
        desc   = toga.Label("     High Limit", style=Pack(width=244, align_items=END, font_size=12))
        entry1  = toga.NumberInput(on_change=self.change_ptid, min=0, max=9999, style=Pack(flex=1, height=48, width=LNUMWIDTH, font_size=18, background_color="#eeeeee", color="#000000"))
        boxrow = toga.Box(children=[desc, entry1, btn], style=Pack(direction=ROW, align_items=END, margin_top=1))
        scan_content.add(boxrow)

        desc   = toga.Label(" ", style=Pack(width=20, align_items=END, font_size=18))
        adj0   = toga.Slider(value=0, min=0, max=1000, on_change=self.setLimit, style=Pack(width=320, height=20))
        boxrow = toga.Box(children=[desc, adj0], style=Pack(direction=ROW, align_items=END))
        scan_content.add(boxrow)


############################################################# 

        boxrow = toga.Box(children=[blank, toga.Divider(), blank], style=Pack(direction=COLUMN, margin_top=20))
        scan_content.add(boxrow)

       ############################################################# Servo 1 Config

        desc   = toga.Label("Servo 1", style=Pack(width=270, align_items=END, font_size=18))
        rev    = toga.Switch("Reverse", id=SVR1, value=False, on_change=self.change_ptid)
        boxrow = toga.Box(children=[desc, rev], style=Pack(direction=ROW, align_items=END, margin_top=8))
        scan_content.add(boxrow)

        btn    = toga.Button(id=SRVP1, text="Prg", on_press = self.sendPrgCommand, style=Pack(width=55, height=55, margin_top=6, background_color="#bbbbbb", color="#000000", font_size=12))
        desc   = toga.Label("     Function Code", style=Pack(width=282, align_items=END, font_size=12))
        func   = toga.NumberInput(on_change=self.change_ptid, min=0, max=99, style=Pack(flex=1, height=48, width=24, font_size=12, background_color="#eeeeee", color="#000000"))
        boxrow = toga.Box(children=[desc, func, btn], style=Pack(direction=ROW, align_items=END, margin_top=1))
        scan_content.add(boxrow)

        desc   = toga.Label("     Low Limit", style=Pack(width=244, align_items=END, font_size=12))
        entry0 = toga.NumberInput(on_change=self.change_ptid, min=0, max=1000, style=Pack(flex=1, height=48, width=LNUMWIDTH, font_size=18, background_color="#eeeeee", color="#000000"))
        btn    = toga.Button(id=SV1L, text="Prg", on_press = self.sendPrgCommand, style=Pack(width=55, height=55, margin_top=6, background_color="#bbbbbb", color="#000000", font_size=12))
        boxrow = toga.Box(children=[desc, entry0, btn], style=Pack(direction=ROW, align_items=END, margin_top=1))
        scan_content.add(boxrow)

        desc   = toga.Label(" ", style=Pack(width=20, align_items=END, font_size=18))
        adj0   = toga.Slider(value=0, min=0, max=1000, on_change=self.setLimit, style=Pack(width=320, height=20))
        boxrow = toga.Box(children=[desc, adj0], style=Pack(direction=ROW, align_items=END))
        scan_content.add(boxrow)

        btn    = toga.Button(id=SV1H, text="Prg", on_press = self.sendPrgCommand, style=Pack(width=55, height=55, margin_top=6, background_color="#bbbbbb", color="#000000", font_size=12))
        desc   = toga.Label("     High Limit", style=Pack(width=244, align_items=END, font_size=12))
        entry1  = toga.NumberInput(on_change=self.change_ptid, min=0, max=9999, style=Pack(flex=1, height=48, width=LNUMWIDTH, font_size=18, background_color="#eeeeee", color="#000000"))
        boxrow = toga.Box(children=[desc, entry1, btn], style=Pack(direction=ROW, align_items=END, margin_top=1))
        scan_content.add(boxrow)

        desc   = toga.Label(" ", style=Pack(width=20, align_items=END, font_size=18))
        adj0   = toga.Slider(value=0, min=0, max=1000, on_change=self.setLimit, style=Pack(width=320, height=20))
        boxrow = toga.Box(children=[desc, adj0], style=Pack(direction=ROW, align_items=END))
        scan_content.add(boxrow)

############################################################# 

        boxrow = toga.Box(children=[blank, toga.Divider(), blank], style=Pack(direction=COLUMN, margin_top=20))
        scan_content.add(boxrow)

       ############################################################# Servo 2 Config

        desc   = toga.Label("Servo 2", style=Pack(width=270, align_items=END, font_size=18))
        rev    = toga.Switch("Reverse", id=SVR2, value=False, on_change=self.change_ptid)
        boxrow = toga.Box(children=[desc, rev], style=Pack(direction=ROW, align_items=END, margin_top=8))
        scan_content.add(boxrow)

        btn    = toga.Button(id=SRVP2, text="Prg", on_press = self.sendPrgCommand, style=Pack(width=55, height=55, margin_top=6, background_color="#bbbbbb", color="#000000", font_size=12))
        desc   = toga.Label("     Function Code", style=Pack(width=282, align_items=END, font_size=12))
        func   = toga.NumberInput(on_change=self.change_ptid, min=0, max=99, style=Pack(flex=1, height=48, width=24, font_size=12, background_color="#eeeeee", color="#000000"))
        boxrow = toga.Box(children=[desc, func, btn], style=Pack(direction=ROW, align_items=END, margin_top=1))
        scan_content.add(boxrow)

        desc   = toga.Label("     Low Limit", style=Pack(width=244, align_items=END, font_size=12))
        entry0 = toga.NumberInput(on_change=self.change_ptid, min=0, max=1000, style=Pack(flex=1, height=48, width=LNUMWIDTH, font_size=18, background_color="#eeeeee", color="#000000"))
        btn    = toga.Button(id=SV2L, text="Prg", on_press = self.sendPrgCommand, style=Pack(width=55, height=55, margin_top=6, background_color="#bbbbbb", color="#000000", font_size=12))
        boxrow = toga.Box(children=[desc, entry0, btn], style=Pack(direction=ROW, align_items=END, margin_top=1))
        scan_content.add(boxrow)

        desc   = toga.Label(" ", style=Pack(width=20, align_items=END, font_size=18))
        adj0   = toga.Slider(value=0, min=0, max=1000, on_change=self.setLimit, style=Pack(width=320, height=20))
        boxrow = toga.Box(children=[desc, adj0], style=Pack(direction=ROW, align_items=END))
        scan_content.add(boxrow)

        btn    = toga.Button(id=SV2H, text="Prg", on_press = self.sendPrgCommand, style=Pack(width=55, height=55, margin_top=6, background_color="#bbbbbb", color="#000000", font_size=12))
        desc   = toga.Label("     High Limit", style=Pack(width=244, align_items=END, font_size=12))
        entry1  = toga.NumberInput(on_change=self.change_ptid, min=0, max=9999, style=Pack(flex=1, height=48, width=LNUMWIDTH, font_size=18, background_color="#eeeeee", color="#000000"))
        boxrow = toga.Box(children=[desc, entry1, btn], style=Pack(direction=ROW, align_items=END, margin_top=1))
        scan_content.add(boxrow)

        desc   = toga.Label(" ", style=Pack(width=20, align_items=END, font_size=18))
        adj0   = toga.Slider(value=0, min=0, max=1000, on_change=self.setLimit, style=Pack(width=320, height=20))
        boxrow = toga.Box(children=[desc, adj0], style=Pack(direction=ROW, align_items=END))
        scan_content.add(boxrow)

############################################################# 

        boxrow = toga.Box(children=[blank, toga.Divider(), blank], style=Pack(direction=COLUMN, flex=1))
        scan_content.add(boxrow)

        btn    = toga.Button(id=WDOG, text="Prg", on_press = self.sendPrgCommand, style=Pack(width=55, height=55, margin_top=6, background_color="#bbbbbb", color="#000000", font_size=12))
        desc   = toga.Label("Watch Dog", style=Pack(width=282, align_items=END, font_size=12))
        func   = toga.NumberInput(on_change=self.change_ptid, min=0, max=99, style=Pack(flex=1, height=48, width=24, font_size=12, background_color="#eeeeee", color="#000000"))
        boxrow = toga.Box(children=[desc, func, btn], style=Pack(direction=ROW, align_items=END, margin_top=1))
        scan_content.add(boxrow)




        self.scroller = toga.ScrollContainer(content=scan_content)
        self.main_window.content = self.scroller
        self.main_window.show()

    def change_ptid(self, id):
        pass

    def sendPrgCommand(self, id):
        pass

    def setLimit(self, id):
        pass


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
        
        try:
           self.usbmanager.requestPermission(self.device, pintent)
           self.hasPermission = self.usbmanager.hasPermission(self.device)
        except:
           print ("no USB device")
           return False

        while not self.hasPermission:
            self.hasPermission = self.usbmanager.hasPermission(self.device)
            
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
