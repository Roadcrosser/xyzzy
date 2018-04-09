"""
Quetzal file format parser.
Only parses the IFhd header, because that's all we need.
Loosely based off of the code here: https://github.com/sussman/zvm/blob/master/zvm/quetzal.py

Quetzal file format standard: http://inform-fiction.org/zmachine/standards/quetzal/index.html
"""

from typing import List, Union
from chunk import Chunk

import os

class HeaderData:
    def __init__(self, release, serial, checksum):
        self.release = release
        self.serial = serial
        self.checksum = checksum

    def __str__(self):
        return "HeaderData(release={}, serial={}, checksum={})".format(self.release, self.serial, self.checksum)

    def __repr__(self):
        return self.__str__()

def read_word(address: int, mem: List[int]) -> int:
    """Read's a 16-bit value at the specified address."""
    return (mem[address] << 8) + mem[address + 1]

def parse_quetzal(fp) -> HeaderData:
    """Reads a Quetzal save file, and returns information about the associated game."""
    if type(fp) != str and not hasattr(fp, 'read'):
        raise TypeError("file is not a string or a bytes-like object.")

    if type(fp) == str:
        if not os.path.isfile(fp):
            raise Exception("File provided isn't a file, or doesn't exist.")

        # Open file as bytes
        qzl = open(fp, 'rb')
    else:
        qzl = fp

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
    data = chunk.read(size).decode("latin_1")

    # Make sure first chunk is IFhd.
    if name != b"IFhd":
        raise Exception("File does not start with an IFhd chunk.")
    elif size != 13:
        raise Exception("Invalid size for IFhd chunk: " + str(size))

    try:
        # Bitwise magic to get data.
        release = (ord(data[0]) << 8) + ord(data[1])
        serial = int(data[2:8])
        checksum = (ord(data[8]) << 8) + ord(data[9])
        # pc = (ord(data[10]) << 16) + (ord(data[11]) << 8) + ord(data[12]) # This isn't needed rn, but it's commented just in case.
    except ValueError as e:
        print(data)
        print(release)
        print(data[2:8])
        print((ord(data[8]) << 8) + ord(data[9]))
        raise e

    return HeaderData(release, serial, checksum)

def parse_zcode(path: str) -> HeaderData:
    """Parses the header of a z-code game, and returns some information."""
    if type(path) != str:
        raise TypeError("path is not a string.")

    if not os.path.isfile(path):
        raise Exception("File provided isn't a file, or doesn't exist.")

    with open(path, encoding="latin_1") as zcode:
        mem = zcode.read()
        mem = [ord(x) for x in mem]

        # Byte magic
        release = read_word(2, mem)
        serial = int(''.join(chr(x) for x in mem[0x12:0x18]))
        checksum = read_word(0x1C, mem)

    return HeaderData(release, serial, checksum)

def compare_quetzal(quetzal: Union[str, HeaderData], game: Union[str, HeaderData]) -> bool:
    """Reads a Quetzal file and a game file, and determines if they match."""
    if not isinstance(quetzal, (HeaderData, str)):
        raise Exception("`quetzal` is not a HeaderData instance, or a string.")
    elif not isinstance(game, (HeaderData, str)):
        raise Exception("game_path is not a HeaderData instance, or a string.")

    if type(quetzal) == str:
        quetzal = parse_quetzal(quetzal)

    if type(game) == str:
        game = parse_zcode(game)

    if quetzal.release != game.release:
        return False
    elif quetzal.serial != game.serial:
        return False
    elif game.checksum != 0 and quetzal.checksum != game.checksum:
        return False

    return True