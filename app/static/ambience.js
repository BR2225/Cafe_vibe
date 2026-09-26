// Mood music, synthesised live with the Web Audio API: no audio files, no licensing, zero download.
// Each mood has its own chord progression, tempo, timbre and groove.
(function () {
  const KEY = "cafe-sound";
  const MOODS = {
    home:   { name: "Café morning", bpm: 72, lead: "triangle", cutoff: 1500, arp: 0.45, perc: null,
              chords: [[60, 64, 67, 71], [57, 60, 64, 67], [53, 57, 60, 64], [55, 59, 62, 67]] },   // Cmaj7 Am7 Fmaj7 G
    work:   { name: "Focus lo-fi", bpm: 70, lead: "sine", cutoff: 1100, arp: 0.35, perc: "hat",
              chords: [[62, 65, 69, 72], [55, 59, 62, 65], [60, 64, 67, 71], [57, 60, 64, 67]] },   // Dm7 G7 Cmaj7 Am7
    meet:   { name: "Sunny bossa", bpm: 100, lead: "triangle", cutoff: 2600, arp: 0.65, perc: "shaker",
              chords: [[62, 66, 69, 73], [59, 62, 66, 69], [64, 67, 71, 74], [57, 61, 64, 67]] },   // Dmaj7 Bm7 Em7 A7
    unwind: { name: "Slow evening", bpm: 54, lead: "sine", cutoff: 800, arp: 0.2, perc: null,
              chords: [[57, 60, 64, 67], [53, 57, 60, 64], [50, 53, 57, 60], [52, 55, 59, 62]] },   // Am7 Fmaj7 Dm7 Em7
  };

  let ctx, master, filter, noise, timer;
  let mood = "home", playing = false, nextBar = 0, bar = 0;
  let enabled = true;
  try { enabled = localStorage.getItem(KEY) !== "off"; } catch { /* storage blocked: default on */ }

  const hz = (m) => 440 * Math.pow(2, (m - 69) / 12);

  function build() {
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    master = ctx.createGain();
    master.gain.value = 0;
    const comp = ctx.createDynamicsCompressor();
    master.connect(comp).connect(ctx.destination);

    filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = MOODS[mood].cutoff;
    filter.Q.value = 0.5;

    // Simple generated reverb for a warm, roomy café sound.
    const verb = ctx.createConvolver();
    const len = ctx.sampleRate * 2.6;
    const ir = ctx.createBuffer(2, len, ctx.sampleRate);
    for (let ch = 0; ch < 2; ch++) {
      const d = ir.getChannelData(ch);
      for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3);
    }
    verb.buffer = ir;
    const wet = ctx.createGain();
    wet.gain.value = 0.5;
    filter.connect(master);
    filter.connect(verb).connect(wet).connect(master);

    noise = ctx.createBuffer(1, ctx.sampleRate * 0.3, ctx.sampleRate);
    const nd = noise.getChannelData(0);
    for (let i = 0; i < nd.length; i++) nd[i] = Math.random() * 2 - 1;
  }

  function tone(midi, t, dur, { wave = "sine", vol = 0.04, attack = 0.02, detune = 0 } = {}) {
    const o = ctx.createOscillator();
    o.type = wave;
    o.frequency.value = hz(midi);
    o.detune.value = detune;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.linearRampToValueAtTime(vol, t + attack);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g).connect(filter);
    o.start(t);
    o.stop(t + dur + 0.05);
  }

  function hit(t, vol, freq, len) {
    const s = ctx.createBufferSource();
    s.buffer = noise;
    const hp = ctx.createBiquadFilter();
    hp.type = "highpass";
    hp.frequency.value = freq;
    const g = ctx.createGain();
    g.gain.setValueAtTime(vol, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + len);
    s.connect(hp).connect(g).connect(master);
    s.start(t);
    s.stop(t + len + 0.02);
  }

  function scheduleBar(t) {
    const m = MOODS[mood];
    const beat = 60 / m.bpm;
    const chord = m.chords[bar % m.chords.length];
    // Pad: two detuned layers with a slow swell.
    chord.forEach((n) => {
      tone(n, t, beat * 4.3, { wave: "sine", vol: 0.03, attack: beat * 1.3, detune: -7 });
      tone(n, t, beat * 4.3, { wave: "triangle", vol: 0.014, attack: beat * 1.3, detune: 7 });
    });
    // Bass on beats 1 and 3.
    tone(chord[0] - 12, t, beat * 1.9, { vol: 0.07, attack: 0.03 });
    tone(chord[mood === "meet" ? 2 : 0] - 12, t + beat * 2, beat * 1.9, { vol: 0.06, attack: 0.03 });
    // Gentle, randomised melody on 8th notes.
    for (let i = 0; i < 8; i++) {
      if (Math.random() < m.arp) {
        const n = chord[Math.floor(Math.random() * chord.length)] + 12;
        const swing = i % 2 ? beat * 0.08 : 0;
        tone(n, t + (i * beat) / 2 + swing, beat * 1.4, { wave: m.lead, vol: 0.028, attack: 0.012 });
      }
    }
    // Light percussion.
    if (m.perc === "hat") for (let i = 0; i < 4; i++) hit(t + i * beat + beat / 2, 0.025, 7000, 0.05);
    if (m.perc === "shaker") for (let i = 0; i < 8; i++) hit(t + (i * beat) / 2, i % 2 ? 0.02 : 0.012, 5000, 0.07);
    bar++;
  }

  function tick() {
    while (nextBar < ctx.currentTime + 0.8) {
      scheduleBar(nextBar);
      nextBar += (4 * 60) / MOODS[mood].bpm;
    }
  }

  function start() {
    if (playing) return;
    if (!ctx) build();
    ctx.resume();
    playing = true;
    nextBar = ctx.currentTime + 0.1;
    tick();
    timer = setInterval(tick, 200);
    master.gain.cancelScheduledValues(ctx.currentTime);
    master.gain.setTargetAtTime(0.9, ctx.currentTime, 0.8);
    render();
  }

  function stop() {
    if (!playing) return;
    playing = false;
    master.gain.cancelScheduledValues(ctx.currentTime);
    master.gain.setTargetAtTime(0, ctx.currentTime, 0.15);
    clearInterval(timer);
    setTimeout(() => { if (!playing) ctx.suspend(); }, 800);
    render();
  }

  function render() {
    const b = document.getElementById("soundBtn");
    if (!b) return;
    b.textContent = playing ? "🔊" : "🔇";
    b.setAttribute("aria-label", playing ? "Mute music" : "Play music");
    b.title = playing ? `Playing: ${MOODS[mood].name} (tap to mute)` : "Music off (tap to play)";
  }

  window.Ambience = {
    setMood(m) {
      mood = MOODS[m] ? m : "home";
      if (ctx) filter.frequency.setTargetAtTime(MOODS[mood].cutoff, ctx.currentTime, 1);
      render();
    },
    // Browsers only allow audio after a tap, so the page calls this on the first interaction.
    unlock() { if (enabled) start(); },
    toggle() {
      enabled = !playing;
      try { localStorage.setItem(KEY, enabled ? "on" : "off"); } catch { /* ignore */ }
      enabled ? start() : stop();
      return enabled;
    },
    get name() { return MOODS[mood].name; },
  };

  document.addEventListener("DOMContentLoaded", render);
})();
