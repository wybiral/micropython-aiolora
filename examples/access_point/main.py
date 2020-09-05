# Creates a WiFi access point and relays LoRa messages to any clients connected
# to 192.168.4.1 (the Access Point server IP address). Messages are pushed to
# the client using a persistent connection so that there's no need to refresh
# the page.

from aiolora import LoRa
import gc
from machine import Pin, SPI
import network
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

# Setup WiFi Access Point
SSID = 'LoRa Gateway'
PASSWORD = 'CHANGE_THIS!!!'
ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(
    essid=SSID,
    authmode=network.AUTH_WPA_WPA2_PSK,
    password=PASSWORD,
)

# Holds current connections
CONNECTIONS = set()

# Main HTTP request handler
async def serve(reader, writer):
    # Process first line of HTTP request
    line = await reader.readline()
    if not line:
        await writer.wait_closed()
        return
    parts = line.split(b' ')
    if len(parts) < 3:
        await writer.wait_closed()
        return
    method = parts[0]
    path = parts[1]
    # Consuming remaining request headers
    while True:
        line = await reader.readline()
        if line == b'\r\n':
            break
    if method != b'GET':
        # Only allows GET requests
        await writer.awrite(b'HTTP/1.0 405 Not Allowed\r\n\r\nNot Allowed')
        await writer.wait_closed()
        return
    if path != b'/':
        # Only allow requests to the root path
        await writer.awrite(b'HTTP/1.0 404 Not Found\r\n\r\nNot Found')
        await writer.wait_closed()
        return
    writer.write(b'HTTP/1.0 200 OK\r\n')
    writer.write(b'Content-Type: text/html; charset=utf-8\r\n')
    await writer.awrite(b'\r\n')
    await writer.awrite(b'<html><body>\n')
    # Add writer to connection set
    CONNECTIONS.add(writer)

# Main LoRa receiver/broadcast loop
async def main():
    while True:
        # Receive data
        data = await lora.recv()
        # Print to terminal
        print(data)
        # Write data to all connections
        for w in CONNECTIONS:
            try:
                await w.awrite(b'<div>' + data + b'</div>')
            except:
                # If write fails, remove connection and close it
                print('Disconnected')
                CONNECTIONS.remove(w)
                w.close()
        gc.collect()

# Setup asyncio loop and start task
loop = asyncio.get_event_loop()
loop.create_task(asyncio.start_server(serve, "0.0.0.0", 80))
loop.create_task(main())
loop.run_forever()
