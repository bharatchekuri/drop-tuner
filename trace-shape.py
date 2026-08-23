#!/usr/bin/env python3
"""Trace an image silhouette into an SVG path, pixel for pixel.

    ./trace-shape.py shape.png [--invert] [--eps 0.8] [--height 300]

Pure stdlib. sips converts the input to PNG, this decodes it, auto-thresholds
(Otsu), keeps the largest blob, walks its boundary with Moore-neighbour tracing
(so notches survive), simplifies with Douglas-Peucker, and reports any enclosed
holes - the tuner holes and inlays - as centre/radius.
"""
import sys, zlib, subprocess, os, math, tempfile
from collections import deque

def to_png(src, upscale=1):
    """Upscaling first gives sub-pixel edge positions: sips interpolates, so the
    threshold lands on the true edge instead of snapping to a whole source pixel.
    That is what turns a low-res diagonal from a staircase into a straight line."""
    out = os.path.join(tempfile.mkdtemp(), 'trace.png')
    args = ['sips', '-s', 'format', 'png']
    if upscale > 1:
        g = subprocess.run(['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', src],
                           check=True, capture_output=True, text=True).stdout
        dims = [int(t.split(':')[1]) for t in g.split(chr(10)) if 'pixel' in t]
        args += ['-Z', str(max(dims)*upscale)]
    subprocess.run(args + [src, '--out', out], check=True, capture_output=True)
    return out

def read_png(path):
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n', 'not a png'
    pos, idat, plte, trns = 8, b'', None, None
    while pos < len(d):
        ln = int.from_bytes(d[pos:pos+4], 'big'); typ = d[pos+4:pos+8]
        ck = d[pos+8:pos+8+ln]; pos += 12 + ln
        if typ == b'IHDR':
            w = int.from_bytes(ck[0:4], 'big'); h = int.from_bytes(ck[4:8], 'big')
            bd, ct, interlace = ck[8], ck[9], ck[12]
            assert interlace == 0, 'interlaced png unsupported'
            assert ct in (0, 2, 3, 4, 6), 'unsupported colour type %d' % ct
        elif typ == b'PLTE': plte = ck
        elif typ == b'tRNS': trns = ck
        elif typ == b'IDAT': idat += ck
        elif typ == b'IEND': break
    raw = zlib.decompress(idat)
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    st = 2 if bd == 16 else 1
    if ct == 3:
        stride = (w*bd + 7)//8            # indices may be packed below a byte
        bpp = 1
    else:
        bpp, stride = ch*st, w*ch*st
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

    if ct == 3:                            # expand palette indices to RGBA
        assert plte, 'palette png without PLTE'
        out = []
        for ln in rows:
            px = bytearray()
            for x in range(w):
                if bd == 8:   idx = ln[x]
                else:
                    per = 8//bd
                    idx = (ln[x//per] >> (8 - bd*(x % per + 1))) & ((1 << bd) - 1)
                px += bytes(plte[idx*3:idx*3+3])
                px.append(trns[idx] if (trns and idx < len(trns)) else 255)
            out.append(bytes(px))
        return w, h, 4, 1, out
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
    total = sum(i*hist[i] for i in range(256))
    sumB, wB, best, thr = 0.0, 0, -1.0, 128
    for t in range(256):
        wB += hist[t]
        if wB == 0 or wB == n: continue
        wF = n - wB; sumB += t*hist[t]
        var = wB*wF*((sumB/wB) - ((total-sumB)/wF))**2
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

def trace_contour(mask, w, h):
    """Moore-neighbour boundary walk - follows every notch instead of bridging it."""
    start = None
    for y in range(h):
        for x in range(w):
            if mask[y][x]: start = (x, y); break
        if start: break
    nb = [(-1,0),(-1,-1),(0,-1),(1,-1),(1,0),(1,1),(0,1),(-1,1)]      # clockwise from west
    contour, cur, prev = [start], start, (start[0]-1, start[1])
    guard = 8*w*h
    while guard > 0:
        guard -= 1
        d = (prev[0]-cur[0], prev[1]-cur[1])
        idx = nb.index(d) if d in nb else 0
        moved = False
        for k in range(1, 9):
            j = (idx + k) % 8
            nx, ny = cur[0]+nb[j][0], cur[1]+nb[j][1]
            if 0 <= nx < w and 0 <= ny < h and mask[ny][nx]:
                prev = (cur[0]+nb[(j-1) % 8][0], cur[1]+nb[(j-1) % 8][1])
                cur = (nx, ny); moved = True; break
        if not moved: break
        if cur == start and len(contour) > 2: break
        contour.append(cur)
    return contour

def find_holes(mask, w, h, min_px):
    """Background regions fully enclosed by the shape: tuner holes and inlays."""
    seen = [[False]*w for _ in range(h)]
    q = deque()
    def seed(x, y):
        if not mask[y][x] and not seen[y][x]:
            seen[y][x] = True; q.append((x, y))
    for x in range(w): seed(x, 0); seed(x, h-1)
    for y in range(h): seed(0, y); seed(w-1, y)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = x+dx, y+dy
            if 0 <= nx < w and 0 <= ny < h and not mask[ny][nx] and not seen[ny][nx]:
                seen[ny][nx] = True; q.append((nx, ny))
    holes, vis = [], [[False]*w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if (not mask[y][x]) and (not seen[y][x]) and (not vis[y][x]):
                comp = []; q = deque([(x, y)]); vis[y][x] = True
                while q:
                    cx, cy = q.popleft(); comp.append((cx, cy))
                    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                        nx, ny = cx+dx, cy+dy
                        if (0 <= nx < w and 0 <= ny < h and not mask[ny][nx]
                                and not seen[ny][nx] and not vis[ny][nx]):
                            vis[ny][nx] = True; q.append((nx, ny))
                if len(comp) >= min_px:
                    xs = [p[0] for p in comp]; ys = [p[1] for p in comp]
                    bw, bh = max(xs)-min(xs)+1, max(ys)-min(ys)+1
                    fill = len(comp)/(math.pi*(max(bw, bh)/2.0)**2)
                    holes.append({'cx': sum(xs)/len(comp), 'cy': sum(ys)/len(comp),
                                  'r': math.sqrt(len(comp)/math.pi),
                                  'round': abs(bw-bh) <= max(2, 0.3*max(bw, bh)) and fill > 0.6})
    return holes

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
    invert  = '--invert' in a
    eps     = float(a[a.index('--eps')+1])    if '--eps'    in a else 0.8
    up      = int(a[a.index('--upscale')+1])  if '--upscale' in a else 1
    targetH = float(a[a.index('--height')+1]) if '--height' in a else 300.0

    w, h, ch, st, rows = read_png(to_png(src, up))
    L, A = luma_alpha(rows, w, ch, st)
    thr = otsu(L, A)
    mask = [[1 if (A[y][x] > 128 and ((L[y][x] > thr) if invert else (L[y][x] < thr))) else 0
             for x in range(w)] for y in range(h)]
    comp = largest_blob(mask, w, h)
    if not comp:
        print('no shape found - try --invert'); sys.exit(2)
    print('# image %dx%d, threshold %d, blob %d px' % (w, h, thr, len(comp)), file=sys.stderr)

    cmask = [[0]*w for _ in range(h)]
    for x, y in comp: cmask[y][x] = 1

    poly  = rdp(trace_contour(cmask, w, h), eps)
    holes = find_holes(cmask, w, h, max(6, (w*h)//8000))

    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)
    s = targetH/(maxy-miny) if maxy > miny else 1.0
    N = lambda x, y: ((x-minx)*s, (y-miny)*s)

    print('# %d contour points, box %.1f x %.1f, %d holes'
          % (len(poly), (maxx-minx)*s, (maxy-miny)*s, len(holes)), file=sys.stderr)
    print('PATH M ' + ' L '.join('%.1f %.1f' % N(x, y) for x, y in poly) + ' Z')
    for hh in sorted(holes, key=lambda k: -k['cy']):
        cx, cy = N(hh['cx'], hh['cy'])
        print('HOLE %.1f %.1f %.1f %s' % (cx, cy, hh['r']*s, 'round' if hh['round'] else 'other'))

main()
