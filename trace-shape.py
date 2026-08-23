#!/usr/bin/env python3
"""Trace the silhouette of an image into an SVG path.

    ./trace-shape.py headstock.png [--invert] [--eps 1.2] [--height 300]

Pure stdlib: sips converts whatever you give it to PNG, this decodes that PNG,
auto-thresholds it (Otsu), keeps the largest blob, walks its outline and
simplifies it. Prints an SVG path plus the numbers needed to place the tuners.
"""
import sys, zlib, subprocess, os, math, tempfile
from collections import deque

def to_png(src):
    out = os.path.join(tempfile.mkdtemp(), 'trace.png')
    subprocess.run(['sips', '-s', 'format', 'png', '-Z', '900', src, '--out', out],
                   check=True, capture_output=True)
    return out

def read_png(path):
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n', 'not a png'
    pos, idat, w = 8, b'', None
    while pos < len(d):
        ln = int.from_bytes(d[pos:pos+4], 'big'); typ = d[pos+4:pos+8]
        ck = d[pos+8:pos+8+ln]; pos += 12 + ln
        if typ == b'IHDR':
            w = int.from_bytes(ck[0:4], 'big'); h = int.from_bytes(ck[4:8], 'big')
            bd, ct, interlace = ck[8], ck[9], ck[12]
            assert interlace == 0, 'interlaced png unsupported'
            assert ct in (0, 2, 4, 6), 'palette png unsupported (ct=%d)' % ct
        elif typ == b'IDAT': idat += ck
        elif typ == b'IEND': break
    raw = zlib.decompress(idat)
    ch  = {0: 1, 2: 3, 4: 2, 6: 4}[ct]
    st  = 2 if bd == 16 else 1
    bpp, stride = ch * st, w * ch * st
    rows, prev, p = [], bytearray(stride), 0
    for _ in range(h):
        ft = raw[p]; p += 1
        ln = bytearray(raw[p:p+stride]); p += stride
        if ft == 1:
            for i in range(bpp, stride): ln[i] = (ln[i] + ln[i-bpp]) & 255
        elif ft == 2:
            for i in range(stride): ln[i] = (ln[i] + prev[i]) & 255
        elif ft == 3:
            for i in range(stride):
                a = ln[i-bpp] if i >= bpp else 0
                ln[i] = (ln[i] + ((a + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(stride):
                a = ln[i-bpp] if i >= bpp else 0
                b = prev[i]; c = prev[i-bpp] if i >= bpp else 0
                pa, pb, pc = abs(b-c), abs(a-c), abs(a+b-2*c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                ln[i] = (ln[i] + pr) & 255
        rows.append(bytes(ln)); prev = ln
    return w, h, ch, st, rows

def luma_alpha(rows, w, ch, st):
    L = [[0]*w for _ in rows]; A = [[255]*w for _ in rows]
    for y, r in enumerate(rows):
        for x in range(w):
            o = x*ch*st
            if ch in (1, 2):
                g = r[o]; rr = gg = bb = g
                a = r[o+st] if ch == 2 else 255
            else:
                rr, gg, bb = r[o], r[o+st], r[o+2*st]
                a = r[o+3*st] if ch == 4 else 255
            L[y][x] = (rr*299 + gg*587 + bb*114)//1000; A[y][x] = a
    return L, A

def otsu(L, A):
    hist = [0]*256; n = 0
    for row, arow in zip(L, A):
        for v, a in zip(row, arow):
            if a > 128: hist[v] += 1; n += 1
    total, sumB, wB, best, thr = sum(i*hist[i] for i in range(256)), 0.0, 0, -1.0, 128
    for t in range(256):
        wB += hist[t]
        if wB == 0 or wB == n: continue
        wF = n - wB; sumB += t*hist[t]
        mB, mF = sumB/wB, (total - sumB)/wF
        var = wB*wF*(mB-mF)**2
        if var > best: best, thr = var, t
    return thr

def largest_blob(mask, w, h):
    seen = [[False]*w for _ in range(h)]; best = []
    for sy in range(h):
        for sx in range(w):
            if mask[sy][sx] and not seen[sy][sx]:
                q = deque([(sx, sy)]); seen[sy][sx] = True; comp = []
                while q:
                    x, y = q.popleft(); comp.append((x, y))
                    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                        nx, ny = x+dx, y+dy
                        if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = True; q.append((nx, ny))
                if len(comp) > len(best): best = comp
    return best

def outline(comp):
    """Left and right extreme of each row -> a closed silhouette polygon."""
    rows = {}
    for x, y in comp:
        lo, hi = rows.get(y, (x, x))
        rows[y] = (min(lo, x), max(hi, x))
    ys = sorted(rows)
    left  = [(rows[y][0], y) for y in ys]
    right = [(rows[y][1], y) for y in reversed(ys)]
    return left + right

def rdp(pts, eps):
    if len(pts) < 3: return pts
    x1, y1 = pts[0]; x2, y2 = pts[-1]
    dx, dy = x2-x1, y2-y1
    n = math.hypot(dx, dy) or 1.0
    worst, idx = -1.0, 0
    for i in range(1, len(pts)-1):
        px, py = pts[i]
        d = abs(dy*px - dx*py + x2*y1 - y2*x1)/n
        if d > worst: worst, idx = d, i
    if worst <= eps: return [pts[0], pts[-1]]
    return rdp(pts[:idx+1], eps)[:-1] + rdp(pts[idx:], eps)

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(1)
    src = a[0]
    invert = '--invert' in a
    eps    = float(a[a.index('--eps')+1]) if '--eps' in a else 1.2
    targetH= float(a[a.index('--height')+1]) if '--height' in a else 300.0

    w, h, ch, st, rows = read_png(to_png(src))
    L, A = luma_alpha(rows, w, ch, st)
    thr = otsu(L, A)
    mask = [[1 if (A[y][x] > 128 and ((L[y][x] > thr) if invert else (L[y][x] < thr))) else 0
             for x in range(w)] for y in range(h)]
    comp = largest_blob(mask, w, h)
    if not comp:
        print('no shape found - try --invert'); sys.exit(2)
    print(f'# image {w}x{h}, threshold {thr}, blob {len(comp)}px '
          f'({100*len(comp)//(w*h)}% of frame)', file=sys.stderr)

    poly = rdp(outline(comp), eps)
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)
    s = targetH/(maxy-miny) if maxy > miny else 1.0
    norm = [((x-minx)*s, (y-miny)*s) for x, y in poly]

    d = 'M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x, y in norm) + ' Z'
    print(f'# {len(poly)} points, box {(maxx-minx)*s:.1f} x {(maxy-miny)*s:.1f}', file=sys.stderr)
    print(d)

main()
