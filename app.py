"""
Protothrottle Receiver Programmer App
"""

import toga
import asyncio
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
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

# Android Java Class names, used for permissions

Intent = jclass('android.content.Intent')
PendingIntent = jclass('android.app.PendingIntent')


# Main App

class PTReceiver(toga.App):
    def startup(self):

        main_box = toga.Box()

        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.show()

        # Use Android java classes to query and control OTG USB port

        self.context = jclass('org.beeware.android.MainActivity').singletonThis
        self.usbmanager = self.context.getSystemService(self.context.USB_SERVICE)
        self.usbDevices = self.usbmanager.getDeviceList()

        # Check to see if Xbee device is connected, we will do an iteration to be sure

        iterator = self.usbDevices.entrySet().iterator()
        while iterator.hasNext():
           entry = iterator.next()
           self.device = entry.getValue()

        # Check USB Permissions
        self.checkPermission()

        # open and configure as serial port
        self.openAndConfigureUSBPort()

        # Send a test broadcast message
        self.sendTestMessage()


    def sendTestMessage(self):
        buf = bytearray([0x7E, 0x00, 0x11, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0x00, 0x4D, 0x61, 0x72, 0x74, 0x69, 0x6E, 0x95])
        data_length = len(buf)
        status = self.connection.bulkTransfer(self.writeEndpoint, buf, data_length, USB_WRITE_TIMEOUT_MILLIS)

    def sendNetworkDiscovery(self):
        buf = bytearray([0x7E, 0x00, 0x04, 0x08, 0x01, 0x4E, 0x44, 0x64])
        data_length = len(buf)
        status = self.connection.bulkTransfer(self.writeEndpoint, buf, data_length, USB_WRITE_TIMEOUT_MILLIS)


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





    def checkPermission(self):
        hasPermission = self.usbmanager.hasPermission(self.device)
        while (hasPermission == False):
              ACTION_USB_PERMISSION = "com.access.device.USB_PERMISSION"
              intent = Intent(ACTION_USB_PERMISSION)
              try:
                 pintent = PendingIntent.getBroadcast(self.context, 0, intent, 0)
              except Exception:
                 pintent = PendingIntent.getBroadcast(self.context, 0, intent, PendingIntent.FLAG_IMMUTABLE)
                 self.usbmanager.requestPermission(self.device, pintent)

              hasPermission = self.usbmanager.hasPermission(self.device)



def main():
    return PTReceiver()
