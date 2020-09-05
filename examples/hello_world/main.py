# Send "Hello world!" over LoRa every second.

from aiolora import LoRa
from machine import Pin, SPI, I2C
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
    frequency=915.0,
    bandwidth=250000,
    spreading_factor=10,
    coding_rate=8,
)

async def main():
    while True:
        await lora.send('Hello world!')
        await asyncio.sleep(1)

# Setup asyncio loop and start task
loop = asyncio.get_event_loop()
loop.create_task(main())
loop.run_forever()
