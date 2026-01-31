"""Message decoding functions, taken from pybookoo."""

from dataclasses import dataclass
import logging

from .const import WEIGHT_BYTE1, WEIGHT_BYTE2
from .exceptions import (
    BookooMessageError,
    BookooMessageTooLong,
    BookooMessageTooShort,
)

_LOGGER = logging.getLogger(__name__)


# -------------------------------------------------------------------
# MINI SCALE MESSAGE (EXISTING, UNCHANGED)
# -------------------------------------------------------------------
@dataclass
class BookooMessage:
    """Representation of the contents of a datapacket from a Bookoo scale."""

    def __init__(self, payload: bytearray) -> None:
        """Decode MINI scale payload."""

        self.timer: float | None = (
            int.from_bytes(payload[3:5], byteorder="big") / 1000.0
        )

        self.unit: int = payload[5]

        self.weight_symbol = -1 if payload[6] == 45 else 1
        self.weight: float | None = (
            int.from_bytes(payload[8:10], byteorder="big") / 100.0 * self.weight_symbol
        )

        self.flow_symbol = -1 if payload[10] == 45 else 1
        self.flow_rate = (
            int.from_bytes(payload[12:13], byteorder="big") / 100.0 * self.flow_symbol
        )

        self.battery = payload[13]
        self.standby_time = payload[14]
        self.buzzer_gear = payload[16]
        self.flow_rate_smoothing = payload[17]

        # Checksum
        checksum = 0
        for byte in payload[:-1]:
            checksum ^= byte

        if checksum != payload[-1]:
            raise BookooMessageError(payload, "Checksum mismatch")


# -------------------------------------------------------------------
# ULTRA SCALE SUPPORT (NEW)
# -------------------------------------------------------------------

def is_ultra_message(payload: bytearray) -> bool:
    """
    Detect Bookoo Themis Ultra packets.

    Ultra packets:
    - Are 20 bytes long
    - Start with 0x55 0xAA (per Ultra protocol)
    """
    return (
        len(payload) == 20
        and payload[0] == 0x55
        and payload[1] == 0xAA
    )


def decode_ultra_message(payload: bytearray):
    """
    Decode Bookoo Themis Ultra message.

    MINIMAL IMPLEMENTATION:
    - Decode weight only
    - Return BookooMessage-compatible object
    """

    try:
        # Ultra protocol (per BooKoo docs):
        # Weight stored as signed int, grams * 100
        raw_weight = int.from_bytes(payload[6:10], byteorder="big", signed=True)
        weight = raw_weight / 100.0

        msg = BookooMessage.__new__(BookooMessage)
        msg.weight = weight
        msg.timer = None
        msg.flow_rate = None
        msg.battery = payload[14]
        msg.buzzer_gear = payload[15]
        msg.standby_time = payload[16]
        msg.flow_rate_smoothing = None
        msg.unit = 0

        return (msg, bytearray())

    except Exception as ex:
        _LOGGER.warning("Failed to decode Ultra message: %s", ex)
        return (None, payload)


# -------------------------------------------------------------------
# DECODE ENTRY POINT
# -------------------------------------------------------------------
def decode(byte_msg: bytearray):
    """
    Decode incoming BLE notification.

    Returns:
    - (BookooMessage | None, remaining_bytes)
    """

    if len(byte_msg) < 20:
        raise BookooMessageTooShort(byte_msg)

    if len(byte_msg) > 20:
        raise BookooMessageTooLong(byte_msg)

    # ✅ Ultra FIRST
    if is_ultra_message(byte_msg):
        return decode_ultra_message(byte_msg)

    # ✅ Mini scale
    if byte_msg[0] == WEIGHT_BYTE1 and byte_msg[1] == WEIGHT_BYTE2:
        return (BookooMessage(byte_msg), bytearray())

    _LOGGER.debug("Unknown message format: %s", byte_msg)
    return (None, byte_msg)


