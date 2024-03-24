from collections import namedtuple
from pathlib import Path
from typing import List, Union

from elma.constants import INTERNAL_NAMES
from elma.constants import STATEDAT_NUM_LEVELS
from elma.constants import TOP10_SIZE
from elma.constants import STATEDAT_NUM_PLAYERS
from elma.constants import STATEDAT_PLAYER_STRUCT_SIZE
from elma.constants import STATEDAT_PLAYER_NAME_SIZE
from elma.constants import STATEDAT_LEVEL_NAME_SIZE


__all__ = ["null_padded", "format_time", "internal_name", "signed_mod",
           "crypt_top10", "crypt_statepiece", "crypt_state",
           "check_writable_file", "BoundingBox"]


def null_padded(string: str, length: int) -> bytes:
    """
    Force a string to a given length by right-padding it with zero-bytes,
    clipping the initial string if necessary.
    """
    return bytes(string[:length] + ('\0' * (length - len(string))), 'latin1')


def format_time(time_in_hundredths: int,
                pad: bool = True,
                sep: str = ':') -> str:
    """
    Return a time formatted as (hours:)minutes:seconds:hundredths.

    Args:
        time_in_hundredths (int): time in hundredths of a second.
        pad (bool): add leading zeroes to hours/minutes/seconds.
        sep (str): separator between hours, minutes, seconds and hundredths.

    Returns:
        The formatted time as a string.
    """
    secs, hundredths = divmod(time_in_hundredths, 100)
    mins, secs = divmod(secs, 60)
    hours, mins = divmod(mins, 60)
    if pad:
        hours_str = f'{hours:02d}{sep}' if hours > 0 else ''
        return f'{hours_str}{mins:02d}{sep}{secs:02d}{sep}{hundredths:02d}'
    else:
        hours_str = f'{hours}{sep}' if hours > 0 else ''
        mins_str = f'{mins}{sep}' if mins > 0 else ''
        secs_str = f'{secs:02d}{sep}' if mins > 0 else f'{secs}{sep}'
        return f'{hours_str}{mins_str}{secs_str}{hundredths:02d}'


def internal_name(number_0index: int,
                  include_number: bool = False,
                  sep: str = '.') -> str:
    """
    Return the name of an internal level.

    Args:
        number_0index (int): internal number - 1
            (0 = Warm Up, ..., 54 = More Levels).
        include_number (bool): include the internal number,
            e.g. "1. Warm Up" instead of "Warm Up".
        sep (str): separator after the number (followed by a space).

    Returns:
        The name of the internal level as a string.
    """
    prefix = f'{number_0index + 1}{sep} ' if include_number else ''
    return (f'{prefix}{INTERNAL_NAMES[number_0index]}'
            if number_0index in range(55) else '')


def signed_mod(a: int, b: int) -> int:
    """
    Signed modulo operation for level top10 encryption/decryption.
    """
    a = a & 0xFFFF
    r = a % b
    if a > 0x7FFF:
        return -b + (r - 0x10000) % b
    return r


def crypt_top10(buffer: bytes) -> bytes:
    """
    Encrypt or decrypt the raw top10 buffer containing both
    singleplayer and multiplayer top10s.
    """
    # Adapted from https://github.com/domi-id/across
    top10 = [b for b in buffer]
    a, b, c, d = [21, 9783, 3389, 31]
    top10[0] ^= a
    x = (b + a * c) * d + c
    for i in range(1, len(top10)):
        top10[i] ^= (x & 0xFF)
        x += signed_mod(x, c) * c * d
    return b''.join([bytes(chr(c), 'latin1') for c in top10])


def crypt_statepiece(buffer: bytes) -> List[int]:
    """
    Encrypt or decrypt a piece of the state.dat buffer.
    """
    statepiece = [b for b in buffer]
    a, b, c, d = [23, 9782, 3391, 31]
    statepiece[0] ^= a
    x = (b + a * c) * d + c
    for i in range(1, len(statepiece)):
        statepiece[i] ^= (x & 0xFF)
        x += signed_mod(x, c) * c * d
    return statepiece


def crypt_state(buffer: bytes) -> bytes:
    """
    Encrypt or decrypt the whole state.dat buffer (piece by piece).
    """
    statepieces = [
        4,  # version
        (STATEDAT_NUM_LEVELS * TOP10_SIZE),
        (STATEDAT_NUM_PLAYERS * STATEDAT_PLAYER_STRUCT_SIZE),
        4,  # player count
        STATEDAT_PLAYER_NAME_SIZE, STATEDAT_PLAYER_NAME_SIZE,
        4, 4, 4, 4, 4, 4, 4, 4,  # various options
        32, 32,  # player A keys, player B keys
        4, 4, 4,  # inc/dec screen size keys and screenshot key
        STATEDAT_LEVEL_NAME_SIZE, STATEDAT_LEVEL_NAME_SIZE
        ]

    curr = 0
    crypted = []
    for i in statepieces:
        crypted.extend(crypt_statepiece(buffer[curr:curr+i]))
        curr += i

    # registered/shareware marker at the end of the file is unencrypted
    crypted.extend(buffer[curr:curr+4])
    return b''.join([bytes(chr(c), 'latin1') for c in crypted])


def check_writable_file(file: Union[str, Path], exist_ok: bool = False, create_dirs: bool = False) -> None:
    """
    Check if file can be written to and optionally create non-existing parent
    directories.

    Args:
        file: path to the file
        exist_ok: if False, FileExistsError is raised if the file already exists
        create_dirs: create non-existing parent directories of the file

    Raises:
        FileExistsError: if file exists and exist_ok = False
        FileNotFoundError: if parent directory of the file does not exists
            and create_dirs = False
    """
    file = Path(file)
    if file.exists() and not exist_ok:
        raise FileExistsError(f"File {file} already exists.")
    parent = file.resolve().parent
    if create_dirs:
        parent.mkdir(parents=True, exist_ok=True)
    elif not parent.exists():
        raise FileNotFoundError(f"Directory {parent} not found")


BoundingBox = namedtuple('BoundingBox', ['min_x', 'max_x', 'min_y', 'max_y'])
