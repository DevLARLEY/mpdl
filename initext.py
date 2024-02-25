import base64
import binascii
import re
from itertools import zip_longest


# Extract pssh/key ids from init.mp4

def swap_endian(x):
    return ''.join(str(x) for x in list(reversed([b + j for b, j in zip_longest(x[::2], x[1::2], fillvalue='0')])))


def hex_to_ascii(x):
    return bytes.fromhex(x.replace("00", "")).decode("utf-8")


def ext(file) -> list:
    with open(file, "rb") as f:
        c = f.read()
    heX = binascii.hexlify(c).decode("utf-8")
    pssh = [m.start() for m in re.finditer("70737368", heX)]
    res = []
    for r in pssh:
        sysid = heX[r + 16:r + 48]
        if sysid == "edef8ba979d64acea3c827dcd51d21ed":
            s = int(heX[r - 8:r], 16) * 2
            if s < 100:
                continue
            f = heX[r + 56:r + 56 + s - 64]
            p = 0
            while p < len(f):
                h = f[p:p + 2]
                if h == "08":
                    p += 4
                elif h == "48":
                    p += 12
                else:
                    s2 = int(f[p + 2:p + 4], 16) * 2
                    if h == "12":
                        res.append(base64.b64encode(bytes.fromhex(heX[r - 8:r - 8 + s])).decode())
                        break
                    p += s2 + 4
    return res
