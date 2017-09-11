"""
Quetzal file format parser.
Only parses the IFhd header, because that's all we need.
Loosely based off of the code here: https://github.com/sussman/zvm/blob/master/zvm/quetzal.py

Quetzal file format standard: http://inform-fiction.org/zmachine/standards/quetzal/index.html
"""

from typing import List
from chunk import Chunk
from collections import namedtuple

import os

HeaderData = namedtuple("HeaderData", ["release", "serial", "checksum"])

def read_word(address: int, mem: List[int]) -> int:
    """Read's a 16-bit value at the specified address."""
    return (mem[address] << 8) + mem[address + 1]

# TODO: Let this read file-like objects/bytes.
def parse_quetzal(path: str) -> HeaderData:
    """Reads a Quetzal save file, and returns information about the associated game."""
    if type(path) != str:
        raise TypeError("path is not a string.")

    if not os.path.isfile(path):
        raise Exception("File provided isn't a file, or doesn't exist.")

    # Open file as bytes
    with open(path, 'rb') as qzl:
        header = qzl.read(4)

        # Header checking yay.
        if header != b"FORM":
            raise Exception("Invalid file format.")

        qzl.read(4) # Skip some bytes we don't care about.

        ftype = qzl.read(4)

        # More header checking yay.
        if ftype != b"IFZS":
            raise Exception("Invalid file format.")

        chunk = Chunk(qzl)
        name = chunk.getname()
        size = chunk.getsize()
        data = chunk.read(size).decode("ansi")

        # Make sure first chunk is IFhd.
        if name != b"IFhd":
            raise Exception("File does not start with an IFhd chunk.")
        elif size != 13:
            raise Exception("Invalid size for IFhd chunk: " + str(size))

        # Bitwise magic to get data.
        release = (ord(data[0]) << 8) + ord(data[1])
        serial = int(data[2:8])
        checksum = (ord(data[8]) << 8) + ord(data[9])
        # pc = (ord(data[10]) << 16) + (ord(data[11]) << 8) + ord(data[12]) # This isn't needed rn, but it's commented just in case.

    return HeaderData(release, serial, checksum)

def parse_zcode(path: str) -> HeaderData:
    """Parses the header of a z-code game, and returns some information."""
    if type(path) != str:
        raise TypeError("path is not a string.")

    if not os.path.isfile(path):
        raise Exception("File provided isn't a file, or doesn't exist.")

    with open(path, encoding='ansi') as zcode:
        mem = zcode.read()
        mem = [ord(x) for x in mem]

        # Byte magic
        release = read_word(2, mem)
        serial = int(''.join(chr(x) for x in mem[0x12:0x18]))
        checksum = read_word(0x1C, mem)

    return HeaderData(release, serial, checksum)

def compare_quetzal(quetzal_path: str, game_path: str) -> bool:
    """Reads a Quetzal file and a game file, and determines if they match."""
    if type(quetzal_path) != str:
        raise Exception("quetzal_path is not a string.")
    elif type(game_path) != str:
        raise Exception("game_path is not a string.")

    qzl_data = parse_quetzal(quetzal_path)
    zcode_data = parse_zcode(game_path)

    if qzl_data.release != zcode_data.release:
        return False
    elif qzl_data.serial != zcode_data.serial:
        return False
    elif zcode_data.checksum != 0 and qzl_data.checksum != zcode_data.checksum:
        return False

    return True