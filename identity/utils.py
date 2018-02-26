from neocore.UInt160 import UInt160
from neocore.Cryptography.Crypto import Crypto

def bytestr_to_str(bytestr):
    string = str(bytestr)
    return string[2:len(string)-1]


def parse_id_list(record_id_list_str):
    arr = record_id_list_str.split(':')
    res = []
    for item in arr:
        try:
            res.append(int(item))
        except:
            pass
    return res

def bytes_to_address(bytes):
    script_hash = UInt160(data=bytes)
    address = Crypto.ToAddress(script_hash)
    return address