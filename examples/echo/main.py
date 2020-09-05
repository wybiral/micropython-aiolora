# Continuously listen for LoRa messages and echo them back out (also prints
# them to the terminal).

from aiolora import LoRa
from machine import Pin, SPI
import uasyncio as asyncio

# SPI pins
SCK  = 14
MOSI = 13
MISO = 12
CS   = 32
# IRQ pin
IRQ  = 36

# Setup SPI
spi = SPI(
    1,
    baudrate=10000000,
    sck=Pin(SCK, Pin.OUT, Pin.PULL_DOWN),
    mosi=Pin(MOSI, Pin.OUT, Pin.PULL_UP),
    miso=Pin(MISO, Pin.IN, Pin.PULL_UP),
)
spi.init()

# Setup LoRa
lora = LoRa(
    spi,
    cs=Pin(CS, Pin.OUT),
    irq=Pin(IRQ, Pin.IN),
)

async def main():
    while True:
        # Receive data
        data = await lora.recv()
        # Print to terminal
        print(data)
        # Echo data
        await lora.send(data)

# Setup asyncio loop and start task
loop = asyncio.get_event_loop()
loop.create_task(main())
loop.run_forever()
