"""Async Modbus TCP client wrapper for the Venus 300."""

from __future__ import annotations

import asyncio

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from .registers import ReadBlock, Register, RegisterKind, decode_value


class Venus300ModbusError(Exception):
    """Raised when a Modbus request to the Venus 300 fails."""


class Venus300ModbusClient:
    """Serializes all Modbus TCP traffic to one Venus 300 unit."""

    def __init__(self, host: str, port: int, slave_id: int, timeout: float = 5.0) -> None:
        """Set up the underlying pymodbus client."""
        self._client = AsyncModbusTcpClient(host=host, port=port, timeout=timeout)
        self._slave_id = slave_id
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        """Return whether the TCP connection is currently up."""
        return self._client.connected

    async def connect(self) -> None:
        """Open the TCP connection."""
        async with self._lock:
            if not await self._client.connect():
                raise Venus300ModbusError(f"Could not connect to {self._client.comm_params.host}")

    def close(self) -> None:
        """Close the TCP connection."""
        self._client.close()

    async def read_block(self, block: ReadBlock) -> dict[str, int | float]:
        """Read a contiguous block of registers and decode every field in it."""
        reader = (
            self._client.read_input_registers
            if block.kind == RegisterKind.INPUT
            else self._client.read_holding_registers
        )
        async with self._lock:
            try:
                result = await reader(block.start, count=block.count, device_id=self._slave_id)
            except ModbusException as err:
                raise Venus300ModbusError(str(err)) from err
        if result.isError():
            raise Venus300ModbusError(
                f"Modbus error reading {block.kind} {block.start}-"
                f"{block.start + block.count - 1}"
            )
        return {
            register.key: decode_value(result.registers[block.offset_of(register)], register)
            for register in block.registers
        }

    async def read_register(self, register: Register) -> int | float:
        """Read a single, isolated register."""
        reader = (
            self._client.read_input_registers
            if register.kind == RegisterKind.INPUT
            else self._client.read_holding_registers
        )
        async with self._lock:
            try:
                result = await reader(register.address, count=1, device_id=self._slave_id)
            except ModbusException as err:
                raise Venus300ModbusError(str(err)) from err
        if result.isError():
            raise Venus300ModbusError(f"Modbus error reading {register.kind} {register.address}")
        return decode_value(result.registers[0], register)

    async def write_register(self, register: Register, value: int) -> None:
        """Write a single writable holding register."""
        if not register.writable:
            raise Venus300ModbusError(f"{register.key} is not a writable register")
        async with self._lock:
            try:
                result = await self._client.write_register(
                    register.address, value=value, device_id=self._slave_id
                )
            except ModbusException as err:
                raise Venus300ModbusError(str(err)) from err
        if result.isError():
            raise Venus300ModbusError(f"Modbus error writing {register.kind} {register.address}")
