"""
Cryptoauthlib Library Management
"""
# (c) 2015-2018 Microchip Technology Inc. and its subsidiaries.
#
# Subject to your compliance with these terms, you may use Microchip software
# and any derivatives exclusively with Microchip products. It is your
# responsibility to comply with third party license terms applicable to your
# use of third party software (including open source software) that may
# accompany Microchip software.
#
# THIS SOFTWARE IS SUPPLIED BY MICROCHIP "AS IS". NO WARRANTIES, WHETHER
# EXPRESS, IMPLIED OR STATUTORY, APPLY TO THIS SOFTWARE, INCLUDING ANY IMPLIED
# WARRANTIES OF NON-INFRINGEMENT, MERCHANTABILITY, AND FITNESS FOR A
# PARTICULAR PURPOSE. IN NO EVENT WILL MICROCHIP BE LIABLE FOR ANY INDIRECT,
# SPECIAL, PUNITIVE, INCIDENTAL OR CONSEQUENTIAL LOSS, DAMAGE, COST OR EXPENSE
# OF ANY KIND WHATSOEVER RELATED TO THE SOFTWARE, HOWEVER CAUSED, EVEN IF
# MICROCHIP HAS BEEN ADVISED OF THE POSSIBILITY OR THE DAMAGES ARE
# FORESEEABLE. TO THE FULLEST EXTENT ALLOWED BY LAW, MICROCHIP'S TOTAL
# LIABILITY ON ALL CLAIMS IN ANY WAY RELATED TO THIS SOFTWARE WILL NOT EXCEED
# THE AMOUNT OF FEES, IF ANY, THAT YOU HAVE PAID DIRECTLY TO MICROCHIP FOR
# THIS SOFTWARE.

import os.path
import json
from ctypes import *
from ctypes.util import find_library
from .exceptions import LibraryLoadError
from .atcaenum import AtcaEnum

# Maps common name to the specific name used internally
ATCA_NAMES = {'i2c': 'i2c', 'hid': 'kithid', 'sha': 'sha204', 'ecc': 'eccx08'}

# Global cdll instance of the loaded compiled library
_CRYPTO_LIB = None

# List of basic ctypes by size
_CTYPES_BY_SIZE = {1: c_uint8, 2: c_uint16, 4:c_uint32}

class AtcaReference:
    """
    A simple wrapper to pass an immutable type to a function for return
    """
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return self.value == other

    def __ne__(self, other):
        return self.value != other

    def __lt__(self, other):
        return self.value < other

    def __le__(self, other):
        return self.value <= other

    def __gt__(self, other):
        return self.value > other

    def __ge__(self, other):
        return self.value >= other

    def __int__(self):
        return int(self.value)

    def __str__(self):
        return str(self.value)


def load_cryptoauthlib(lib=None):
    """
    Load CryptoAauthLib into Python environment
    raise LibraryLoadError if cryptoauthlib library can't be loaded
    """
    global _CRYPTO_LIB      # pylint: disable=global-statement
    if lib is not None:
        _CRYPTO_LIB = lib
    else:
        try:
            os.environ['PATH'] = os.path.dirname(__file__) + os.pathsep + os.environ['PATH']
            _CRYPTO_LIB = cdll.LoadLibrary(find_library('cryptoauth'))
        except:
            raise LibraryLoadError('Unable to find cryptoauthlib. You may need to reinstall')


def get_cryptoauthlib():
    """
    This is a helper function for the other python files in this module to use the loaded library
    """
    global _CRYPTO_LIB      # pylint: disable=global-statement
    return _CRYPTO_LIB


def get_device_name(revision):
    """
    Returns the device name based on the info byte array values returned by atcab_info
    """
    devices = {0x10: 'ATECC108A',
               0x50: 'ATECC508A',
               0x60: 'ATECC608',
               0x20: 'ECC204',
               0x00: 'ATSHA204A',
               0x02: 'ATSHA204A',
               0x40: 'ATSHA206A'}
    device_name = devices.get(revision[2], 'UNKNOWN')
    return device_name


def get_device_type_id(name):
    """
    Returns the ATCADeviceType value based on the device name
    """
    devices = {'ATSHA204A': 0,
               'ATECC108A': 1,
               'ATECC508A': 2,
               'ATECC608A': 3,
               'ATECC608B': 3,
               'ATECC608': 3,
               'ATSAH206A': 4,
               'ECC204': 5,
               'UNKNOWN': 0x20}
    return devices.get(name.upper())


def get_size_by_name(name):
    """
    Get the size of an object in the library using the name_size api from atca_utils_sizes.c
    """
    global _CRYPTO_LIB      # pylint: disable=global-statement
    return getattr(_CRYPTO_LIB, '{}_size'.format(name), lambda: 4)()


def get_ctype_by_name(name):
    """
    For known (atca_utils_sizes.c) types that are custom to the library retrieve the size
    """
    return _CTYPES_BY_SIZE.get(get_size_by_name(name))


def get_ctype_structure_instance(structure, value):
    """
    Internal Helper Function:  Convert a value into the correct ctypes structure for a given field
    :param value: Value to convert
    :param structure: Conversion Class (resulting type)
    :return:
    """
    # pylint: disable-msg=invalid-name
    if isinstance(value, dict):
        r = structure(**value)
    elif isinstance(value, int):
        r = structure.from_buffer_copy(c_uint(value))
    elif isinstance(value, AtcaEnum):
        r = structure.from_buffer_copy(c_uint(int(value)))
    elif not isinstance(value, structure):
        r = structure(value)
    else:
        r = value
    return r


def get_ctype_array_instance(array, value):
    """
    Internal Helper Function: Convert python list into ctype array
    :param value: Value to convert
    :param array: Conversion Class (resulting type)
    :return:
    """
    # pylint: disable-msg=invalid-name, protected-access
    t = array._type_
    if t is c_char:
        # Strings are special
        if isinstance(value, str):
            a = value.encode('ascii')
        else:
            a = bytes(value)
    else:
        a = array(*[get_ctype_structure_instance(t, e) for e in value])
    return a


class AtcaUnion(Union):
    """ An extended ctypes structure to accept complex inputs """
    # pylint: disable-msg=invalid-name, too-few-public-methods
    def __init__(self, *args, **kwargs):
        if kwargs is not None:
            for f in self._fields_:
                if f[0] in kwargs:
                    if isinstance(f[1](), Union):
                        kwargs[f[0]] = get_ctype_structure_instance(f[1], kwargs[f[0]])
                    elif isinstance(f[1](), Structure):
                        kwargs[f[0]] = get_ctype_structure_instance(f[1], kwargs[f[0]])
                    elif isinstance(f[1](), Array):
                        kwargs[f[0]] = get_ctype_array_instance(f[1], kwargs[f[0]])

        super(AtcaUnion, self).__init__(*args, **kwargs)


class AtcaStructure(Structure):
    """ An extended ctypes structure to accept complex inputs """
    # pylint: disable-msg=invalid-name, too-few-public-methods
    def __init__(self, *args, **kwargs):
        if kwargs is not None:
            for f in self._fields_:
                if f[0] in kwargs:
                    if isinstance(f[1](), Union):
                        kwargs[f[0]] = get_ctype_structure_instance(f[1], kwargs[f[0]])
                    elif isinstance(f[1](), Structure):
                        kwargs[f[0]] = get_ctype_structure_instance(f[1], kwargs[f[0]])
                    elif isinstance(f[1](), Array):
                        kwargs[f[0]] = get_ctype_array_instance(f[1], kwargs[f[0]])

        super(AtcaStructure, self).__init__(*args, **kwargs)

    def update_from_buffer(self, buffer):
        if len(buffer) < sizeof(self):
            raise ValueError
        memmove(addressof(self), buffer, sizeof(self))


def ctypes_to_bytes(obj):
    """
    Convert a ctypes structure/array into bytes. This is for python2 compatibility
    """
    buf = create_string_buffer(sizeof(obj))
    memmove(buf, addressof(obj), sizeof(obj))
    return buf.raw


def create_byte_buffer(init_or_size):
    if isinstance(init_or_size, int):
        buf = (c_uint8*init_or_size)()
    else:
        buf = (c_uint8*len(init_or_size))(*list(init_or_size))
    return buf


__all__ = ['ATCA_NAMES', 'AtcaReference', 'load_cryptoauthlib', 'get_device_name', 'get_device_type_id',
           'create_byte_buffer']
