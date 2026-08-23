#!/usr/bin/env python3
"""Generate the app icons. Pure stdlib - draws a tuner dial as a distance field
and writes the PNGs by hand, so there is no Pillow/node dependency."""
import zlib, struct, math

BG_TOP, BG_BOT = (16, 25, 34), (7, 10, 15)
RING_DIM      = (44, 58, 72)
GREEN         = (53, 208, 127)
NEEDLE        = (233, 240, 247)

def write_png(path, w, h, px):
    raw = b''.join(b'\x00' + bytes(px[y*w*4:(y+1)*w*4]) for y in range(h))
    def chunk(tag, data):
        body = tag + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xffffffff)
    out  = b'\x89PNG\r\n\x1a\n'
    out += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    out += chunk(b'IDAT', zlib.compress(raw, 9))
    out += chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(out)

def clamp01(v):
    return 0.0 if v < 0 else 1.0 if v > 1 else v

def render(S, scale=1.0):
    cx = cy = S / 2.0
    R      = 0.335 * S * scale          # ring radius
    band   = 0.072 * S * scale          # ring thickness
    L      = 0.300 * S * scale          # needle length
    wbase  = 0.030 * S * scale          # needle half width at the hub
    hubR   = 0.046 * S * scale
    feather = max(0.8, S / 340.0)
    span   = math.radians(120.0)        # ring spans +/- 120 deg
    zone   = math.radians(21.0)         # green "in tune" cap
    na     = math.radians(-19.0)        # needle sits slightly flat, like a real dial
    sn, cs = math.sin(na), math.cos(na)

    px = bytearray(S * S * 4)
    for y in range(S):
        t  = y / (S - 1.0)
        bg = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3))
        dy = y + 0.5 - cy
        for x in range(S):
            dx = x + 0.5 - cx
            r  = math.hypot(dx, dy)
            th = math.atan2(dx, -dy)            # 0 = straight up, + = clockwise
            ath = abs(th)

            col = list(bg)

            # soft green bloom behind the dial
            g = 0.11 * math.exp(-((r - R) / (0.20 * S)) ** 2)
            for i in range(3):
                col[i] += (GREEN[i] - col[i]) * g

            # gauge ring
            a_rad = clamp01((band / 2.0 - abs(r - R)) / feather + 0.5)
            if a_rad > 0:
                a_end = clamp01(((span - ath) * max(r, 1.0)) / feather + 0.5)
                a = a_rad * a_end
                if a > 0:
                    tint = GREEN if ath <= zone else RING_DIM
                    if ath <= zone:                     # feather the green/grey seam
                        m = 1.0
                    else:
                        m = clamp01(((zone - ath) * max(r, 1.0)) / feather + 0.5)
                    base = [RING_DIM[i] + (GREEN[i] - RING_DIM[i]) * m for i in range(3)]
                    for i in range(3):
                        col[i] += (base[i] - col[i]) * a

            # needle (tapered wedge from the hub)
            u =  dx * sn - dy * cs
            v =  dx * cs + dy * sn
            if -feather <= u <= L + feather:
                hw = wbase * (1.0 - 0.72 * clamp01(u / L))
                a = clamp01((hw - abs(v)) / feather + 0.5) * clamp01((L - u) / feather + 0.5) * clamp01((u + hubR) / feather + 0.5)
                for i in range(3):
                    col[i] += (NEEDLE[i] - col[i]) * a

            # hub
            a = clamp01((hubR - r) / feather + 0.5)
            for i in range(3):
                col[i] += (NEEDLE[i] - col[i]) * a

            o = (y * S + x) * 4
            px[o]   = max(0, min(255, int(col[0] + 0.5)))
            px[o+1] = max(0, min(255, int(col[1] + 0.5)))
            px[o+2] = max(0, min(255, int(col[2] + 0.5)))
            px[o+3] = 255
    return px

for size, name, sc in [(512, 'icon-512.png', 1.0),
                       (512, 'icon-512-maskable.png', 0.72),
                       (192, 'icon-192.png', 1.0),
                       (180, 'apple-touch-icon.png', 1.0)]:
    write_png(name, size, size, render(size, sc))
    print('wrote', name, size)
