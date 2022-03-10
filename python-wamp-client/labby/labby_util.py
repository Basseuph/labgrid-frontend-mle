import asyncio
from asyncio import log
import sys
import serial
from serial import Serial
from typing import Generator, Optional, Dict

from labby.resource import NetworkSerialPort


def prepare_place(place_data: Dict,
                  place_name: Optional[str] = None,
                  exporter: Optional[str] = None,
                  power_state: Optional[bool] = None):
    place_data.update({
        "name": place_name,
        "exporter": exporter,
        "power_state": power_state
    })
    return place_data


def flatten(data: Dict, depth=1):
    """
    recursively flatten dictionary with given strategy
    """
    if depth == 0:
        return data
    res = {}
    for key, value in data.items():
        if isinstance(value, Dict):
            res.update(flatten(value, depth=depth-1))
        else:
            res[key] = value
    return res


async def asread(console: Serial) -> bytes:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, console.read)


async def aswrite(console: Serial, data: bytes) -> int:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda data=data: console.write(data))

