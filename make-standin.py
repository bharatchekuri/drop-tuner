#!/usr/bin/env python3
"""Placeholder background that mimics the ALBUM ART's lighting - warm lamp-lit
paper falling off to near-black - so the mock shows honest contrast. Replace it
with the real artwork via ./set-art.sh <file>."""
import zlib, struct, math

W, H = 900, 1600
LIGHT = (214, 138, 58)     # lamp-lit paper
MID   = (128, 68, 22)
DARK  = (18, 10, 5)

def write_png(path, w, h, px):
    raw = b''.join(b'\x00' + bytes(px[y*w*4:(y+1)*w*4]) for y in range(h))
    def chunk(tag, data):
        b = tag + data
        return struct.pack('>I', len(data)) + b + struct.pack('>I', zlib.crc32(b) & 0xffffffff)
    out  = b'\x89PNG\r\n\x1a\n'
    out += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    out += chunk(b'IDAT', zlib.compress(raw, 9))
    out += chunk(b'IEND', b'')
    open(path, 'wb').write(out)

px = bytearray(W*H*4)
lx, ly, lr = W*0.46, H*0.34, W*0.92        # light source, upper-centre like the photo
for y in range(H):
    for x in range(W):
        d = math.hypot((x-lx), (y-ly)*0.86) / lr
        t = max(0.0, min(1.0, 1.0 - d))
        t = t*t*(3-2*t)                                  # smoothstep falloff
        if t > 0.55:
            k = (t-0.55)/0.45
            col = [MID[i] + (LIGHT[i]-MID[i])*k for i in range(3)]
        else:
            k = t/0.55
            col = [DARK[i] + (MID[i]-DARK[i])*k for i in range(3)]
        # paper tooth + a couple of soft creases so it is not a flat gradient
        g = (math.sin(x*0.7+y*1.3)*math.sin(x*1.9-y*0.4)) * 7
        g += math.sin((x*0.02 + y*0.011)) * 5
        crease = math.exp(-((x - y*0.42 - W*0.12)**2) / (2*(W*0.045)**2)) * 14
        for i in range(3):
            col[i] = col[i] + g - crease
        o = (y*W + x) * 4
        px[o]   = max(0, min(255, int(col[0])))
        px[o+1] = max(0, min(255, int(col[1])))
        px[o+2] = max(0, min(255, int(col[2])))
        px[o+3] = 255
write_png('band.jpg.png', W, H, px)
print('wrote stand-in', W, 'x', H)
