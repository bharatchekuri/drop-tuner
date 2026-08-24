// A real plucked string drifts a few cents while it decays. Feed the same
// signal through the old and new smoothing to count how often green flips.
const FPS = 25, SECS = 6, N = FPS*SECS, DT = 1000/FPS;
let seed = 12345;
const rnd = () => (seed = (seed*1103515245 + 12345) & 0x7fffffff) / 0x7fffffff - 0.5;

// cents offset of the played string over time: settles near +3, wobbles, plus noise
function centsAt(i){
  const t = i/FPS;
  const decay = Math.exp(-t/2.2);
  return 3 + 5.5*Math.sin(2*Math.PI*1.6*t)*decay + 4.0*Math.sin(2*Math.PI*0.4*t)*decay + 3.0*rnd();
}
const raw = Array.from({length: N}, (_, i) => centsAt(i));

function oldWay(){
  let s = null, green = false, flips = 0, greenFrames = 0;
  for(const c of raw){
    const lf = c/1200;
    if(s === null) s = lf; else s += (lf - s)*0.30;
    const cc = s*1200, g = Math.abs(cc) <= 5;
    if(g !== green){ flips++; green = g; }
    if(g) greenFrames++;
  }
  return {flips, pct: Math.round(100*greenFrames/N)};
}

function newWay(){
  let s = null, inTune = false, outSince = 0, flips = 0, greenFrames = 0, t = 0;
  const hist = [];
  for(const c of raw){
    t += DT;
    const lf = c/1200;
    hist.push(lf); if(hist.length > 5) hist.shift();
    const med = hist.slice().sort((a,b)=>a-b)[hist.length >> 1];
    if(s === null || Math.abs(med - s) > 0.06){ s = med; }
    else { const d = Math.abs(med - s); s += (med - s)*(d > 0.012 ? 0.30 : 0.10); }
    const cc = s*1200, abs = Math.abs(cc);
    if(!inTune){ if(abs <= 5){ inTune = true; outSince = 0; } }
    else if(abs > 9){ if(!outSince) outSince = t; if(t - outSince > 320){ inTune = false; outSince = 0; } }
    else outSince = 0;
    if(inTune !== green_prev){ flips++; green_prev = inTune; }
    if(inTune) greenFrames++;
  }
  return {flips, pct: Math.round(100*greenFrames/N)};
}
let green_prev = false;

const o = oldWay(), n = newWay();
console.log('raw input swing: ' + Math.min(...raw).toFixed(1) + ' to ' + Math.max(...raw).toFixed(1) + ' cents');
console.log('OLD  green flips: ' + o.flips + '   green ' + o.pct + '% of frames');
console.log('NEW  green flips: ' + n.flips + '   green ' + n.pct + '% of frames');
