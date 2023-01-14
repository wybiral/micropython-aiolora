from machine import Pin
import uasyncio as asyncio

TX_BASE_ADDR = 0x00
RX_BASE_ADDR = 0x00

PA_BOOST = 0x80
PA_OUTPUT_RFO_PIN = 0
PA_OUTPUT_PA_BOOST_PIN = 1

REG_FIFO = 0x00
REG_OP_MODE = 0x01
REG_FRF_MSB = 0x06
REG_FRF_MID = 0x07
REG_FRF_LSB = 0x08
REG_PA_CONFIG = 0x09
REG_LNA = 0x0c
REG_FIFO_ADDR_PTR = 0x0d
REG_FIFO_TX_BASE_ADDR = 0x0e
REG_FIFO_RX_BASE_ADDR = 0x0f
REG_FIFO_RX_CURRENT_ADDR = 0x10
REG_IRQ_FLAGS = 0x12
REG_RX_NB_BYTES = 0x13
REG_PKT_RSSI_VALUE = 0x1a
REG_PKT_SNR_VALUE = 0x1b
REG_MODEM_CONFIG_1 = 0x1d
REG_MODEM_CONFIG_2 = 0x1e
REG_PREAMBLE_MSB = 0x20
REG_PREAMBLE_LSB = 0x21
REG_PAYLOAD_LENGTH = 0x22
REG_MODEM_CONFIG_3 = 0x26
REG_DETECTION_OPTIMIZE = 0x31
REG_DETECTION_THRESHOLD = 0x37
REG_SYNC_WORD = 0x39
REG_DIO_MAPPING_1 = 0x40
REG_VERSION = 0x42

MODE_LORA = 0x80
MODE_SLEEP = 0x00
MODE_STDBY = 0x01
MODE_TX = 0x03
MODE_RX_CONTINUOUS = 0x05

IRQ_RX_DONE_MASK = 0x40
IRQ_TX_DONE_MASK = 0x08
IRQ_PAYLOAD_CRC_ERROR_MASK = 0x20

MAX_PKT_LENGTH = 255


class LoRa:

    def __init__(self, spi, **kw):
        self.spi = spi
        self.cs = kw['cs']
        self.irq = kw['irq']
        self._data = None
        self._recv_lock = asyncio.Lock()
        self._recv_event = asyncio.ThreadSafeFlag()
        self._send_lock = asyncio.Lock()
        self._send_event = asyncio.ThreadSafeFlag()
        if self._read(REG_VERSION) != 0x12:
            raise Exception('Invalid version or bad SPI connection')
        self._write(REG_OP_MODE, MODE_LORA | MODE_SLEEP)
        self.set_frequency(kw.get('frequency', 915.0))
        self.set_bandwidth(kw.get('bandwidth', 250000))
        self.set_spreading_factor(kw.get('spreading_factor', 10))
        self.set_coding_rate(kw.get('coding_rate', 8))
        self.set_preamble_length(kw.get('preamble_length', 4))
        self.set_crc(kw.get('crc', False))
        # set LNA boost
        self._write(REG_LNA, self._read(REG_LNA) | 0x03)
        # set AGC
        self._write(REG_MODEM_CONFIG_3, 0x04)
        self.set_tx_power(kw.get('tx_power', 24))
        self.set_sync_word(kw.get('sync_word', 0x12))
        self._write(REG_FIFO_TX_BASE_ADDR, TX_BASE_ADDR)
        self._write(REG_FIFO_RX_BASE_ADDR, RX_BASE_ADDR)
        self.irq.irq(handler=self._irq, trigger=Pin.IRQ_RISING)
        self._write(REG_DIO_MAPPING_1, 0x00)
        self._write(REG_OP_MODE, MODE_LORA | MODE_RX_CONTINUOUS)

    async def send(self, x):
        if isinstance(x, str):
            x = x.encode()
        async with self._send_lock:
            self._write(REG_OP_MODE, MODE_LORA | MODE_STDBY)
            self._write(REG_DIO_MAPPING_1, 0x40)
            self._write(REG_FIFO_ADDR_PTR, TX_BASE_ADDR)
            n = len(x)
            m = MAX_PKT_LENGTH - TX_BASE_ADDR
            if n > m:
                raise ValueError('Max payload length is ' + str(m))
            for i in range(n):
                self._write(REG_FIFO, x[i])
            self._write(REG_PAYLOAD_LENGTH, n)
            self._write(REG_OP_MODE, MODE_LORA | MODE_TX)
            await self._send_event.wait()

    async def recv(self):
        async with self._recv_lock:
            await self._recv_event.wait()
            return self._data

    def get_rssi(self):
        rssi = self._read(REG_PKT_RSSI_VALUE)
        if self._frequency >= 779.0:
            return rssi - 157
        return rssi - 164

    def get_snr(self):
        return self._read(REG_PKT_SNR_VALUE) * 0.25

    def set_tx_power(self, level, pin=PA_OUTPUT_PA_BOOST_PIN):
        if pin == PA_OUTPUT_RFO_PIN:
            level = min(max(level, 0), 14)
            self._write(REG_PA_CONFIG, 0x70 | level)
        else:
            level = min(max(level, 2), 17)
            self._write(REG_PA_CONFIG, PA_BOOST | (level - 2))

    def set_frequency(self, frequency):
        self._frequency = frequency
        hz = frequency * 1000000.0
        x = round(hz / 61.03515625)
        self._write(REG_FRF_MSB, (x >> 16) & 0xff)
        self._write(REG_FRF_MID, (x >> 8) & 0xff)
        self._write(REG_FRF_LSB, x & 0xff)

    def set_spreading_factor(self, sf):
        if sf < 6 or sf > 12:
            raise ValueError('Spreading factor must be between 6-12')
        self._write(REG_DETECTION_OPTIMIZE, 0xc5 if sf == 6 else 0xc3)
        self._write(REG_DETECTION_THRESHOLD, 0x0c if sf == 6 else 0x0a)
        reg2 = self._read(REG_MODEM_CONFIG_2)
        self._write(REG_MODEM_CONFIG_2, (reg2 & 0x0f) | ((sf << 4) & 0xf0))

    def set_bandwidth(self, bw):
        bws = (7800, 10400, 15600, 20800, 31250, 41700, 62500, 125000, 250000)
        i = 9
        for j in range(len(bws)):
            if bw <= bws[j]:
                i = j
                break
        x = self._read(REG_MODEM_CONFIG_1) & 0x0f
        self._write(REG_MODEM_CONFIG_1, x | (i << 4))

    def set_coding_rate(self, denom):
        denom = min(max(denom, 5), 8)
        cr = denom - 4
        reg1 = self._read(REG_MODEM_CONFIG_1)
        self._write(REG_MODEM_CONFIG_1, (reg1 & 0xf1) | (cr << 1))

    def set_preamble_length(self, n):
        self._write(REG_PREAMBLE_MSB, (n >> 8) & 0xff)
        self._write(REG_PREAMBLE_LSB, (n >> 0) & 0xff)

    def set_crc(self, crc=False):
        modem_config_2 = self._read(REG_MODEM_CONFIG_2)
        if crc:
            config = modem_config_2 | 0x04
        else:
            config = modem_config_2 & 0xfb
        self._write(REG_MODEM_CONFIG_2, config)

    def set_sync_word(self, sw):
        self._write(REG_SYNC_WORD, sw) 

    def _get_irq_flags(self):
        f = self._read(REG_IRQ_FLAGS)
        self._write(REG_IRQ_FLAGS, f)
        return f

    def _irq(self, event_source):
        f = self._get_irq_flags()
        if f & IRQ_TX_DONE_MASK:
            self._write(REG_DIO_MAPPING_1, 0x00)
            self._write(REG_OP_MODE, MODE_LORA | MODE_RX_CONTINUOUS)
            self._send_event.set()
        if f & IRQ_RX_DONE_MASK:
            if f & IRQ_PAYLOAD_CRC_ERROR_MASK == 0:
                addr = self._read(REG_FIFO_RX_CURRENT_ADDR)
                self._write(REG_FIFO_ADDR_PTR, addr)
                n = self._read(REG_RX_NB_BYTES)
                payload = bytearray(n)
                for i in range(n):
                    payload[i] = self._read(REG_FIFO)
                self._data = bytes(payload)
                self._recv_event.set()

    def _transfer(self, addr, x=0x00):
        resp = bytearray(1)
        self.cs.value(0)
        self.spi.write(bytes([addr]))
        self.spi.write_readinto(bytes([x]), resp)
        self.cs.value(1)
        return resp

    def _read(self, addr):
        x = self._transfer(addr & 0x7f) 
        return int.from_bytes(x, 'big')

    def _write(self, addr, x):
        self._transfer(addr | 0x80, x)
