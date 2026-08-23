# Drop Tuner

A chromatic guitar/bass tuner that runs entirely in the browser. Drop D, Drop C,
DADGAD, open tunings, bass, ukulele and custom tunings — all free, because it is
just a web page. No account, no network calls, no subscription.

## Testing it on your phone

The microphone **will not work over plain HTTP**. iOS (and Chrome on Android)
only expose `getUserMedia` on `https://` or `localhost`, so opening
`http://192.168.x.x:8643` from your phone fails silently. You need an HTTPS URL.

Pick one — both are free and take under a minute:

**Vercel** (you already have an account)

```bash
cd ~/Desktop/guitar-tuner && npx --yes vercel deploy --prod --yes
```

**GitHub Pages**

```bash
cd ~/Desktop/guitar-tuner && gh repo create drop-tuner --public --source=. --push && gh api -X POST repos/:owner/drop-tuner/pages -f "source[branch]=main" -f "source[path]=/"
```

Then open the resulting `https://…` URL on your iPhone **in Safari**, tap
**Start listening**, and allow the microphone when prompted.

## Add it to your home screen

1. Open the HTTPS URL in **Safari** (not Chrome — only Safari can install to the
   home screen on iOS).
2. Tap the **Share** button → **Add to Home Screen** → **Add**.
3. It launches fullscreen with its own icon, no address bar, and works offline.

If the mic prompt never appears when launched from the home-screen icon, delete
the `apple-mobile-web-app-capable` meta tag in `index.html` and re-add the
shortcut — it will then open in a normal Safari tab, where the mic always works.

## Using it

- Pick a tuning from the dropdown. It is remembered on the device.
- Play a string. The nearest string **in that tuning** is targeted automatically,
  so while you drop the low E down to D it keeps pointing at D rather than
  flipping to Eb the way a plain chromatic tuner does.
- Tap a string chip to lock onto it; tap again to go back to auto.
- **Edit** nudges any string ♭/♯ a semitone to build a tuning that isn't listed.
- `A440` steps the reference pitch between 415 and 466 Hz.
- Green means within ±5 cents.

## How the pitch detection works

1. Mic → highpass → two lowpass biquads → `AnalyserNode` (8192 samples).
2. Boxcar-decimated to ~8 kHz, which is plenty for a 30–1250 Hz search and makes
   the autocorrelation cheap enough to run at 25 Hz on a phone.
3. **McLeod Pitch Method** (normalised square difference + *first* key maximum
   above 0.9 × peak). The "first key maximum" rule is what stops a fat low E
   from reading an octave down.
4. **Fundamental refinement.** Real strings are inharmonic — partial *n* sits at
   `n·f₀·√(1+B·n²)` — so a period fitted to the whole harmonic stack lands 4–9
   cents sharp of the fundamental you actually tune. The final frequency comes
   from the phase advance of the fundamental between two Hann-windowed
   overlapping halves of the buffer, which ignores the stretch above it. If the
   fundamental is too weak to measure, it falls back to the MPM estimate.

Accuracy against synthetic strings with realistic inharmonicity: **worst error
0.45 cents** across 25 cases from B0 (30.9 Hz) to E4.

## Dev

```bash
open "index.html?selftest"   # runs the detector against synthetic strings, prints a report
open "index.html?test"       # test-tone mode: drive it with a slider, no mic needed
python3 make-icons.py        # regenerate the app icons
```

Bump `CACHE` in `sw.js` whenever you change a file, or phones will keep serving
the cached copy.
