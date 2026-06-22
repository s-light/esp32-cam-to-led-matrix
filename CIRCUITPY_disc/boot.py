import usb_hid
import usb_midi
import usb_cdc

# print("disable hid.")
# usb_hid.disable()
# print("disable midi.")
# usb_midi.disable()

print("""
in short: ESP32-S3 does not have enough endpoints.

https://learn.adafruit.com/customizing-usb-devices-in-circuitpython/how-many-usb-devices-can-i-have

However, other microcontrollers provide fewer than 8 pairs:

STM32F4 chips typically provide only 3 pairs, not counting pair 0. That means only CIRCUITPY and one CDC device will fit. If you want HID or MIDI on an STM32F4, you'll need to turn off CIRCUITPY or CDC.
ESP32-S2 and ESP32-S3 effectively provide only 4 pairs, not counting pair 0. (There are 6 pairs, but the hardware allows only 4 IN endpoints active at a time, not including pair 0.) So if you wanted both CDC console and data, you would have to turn everything else off, including CIRCUITPY.
Spresense provides 6 pairs but assigns its endpoints at build-time, so you can't turn on MIDI or an extra CDC device.
"""
)
# usb_cdc.enable(console=True, data=True)
