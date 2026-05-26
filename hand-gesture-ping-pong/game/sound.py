"""Sound management — fully procedural 8-bit / 16-bit chiptune engine.

All SFX and BGM are synthesised at runtime using square waves, triangle
waves, and noise — no external audio files required.

Waveform palette (authentic NES / Game Boy channels):
  • Square / pulse  – lead melody, SFX tones
  • Triangle        – bass line (sub-bass warmth)
  • White noise     – drums, noise sweeps
"""

import numpy as np
import pygame

_SR = 44100   # sample rate (Hz)

# ── Low-level waveform primitives ────────────────────────────────────────────

def _sq(t, freq, duty=0.25):
    """Pulse wave — duty < 0.5 gives the classic thin NES buzzy tone."""
    return np.where((t * freq) % 1.0 < duty, 1.0, -1.0)


def _tri(t, freq):
    """Triangle wave — softer, used for bass lines."""
    p = (t * freq) % 1.0
    return 2.0 * np.abs(2.0 * p - 1.0) - 1.0


def _noise(n):
    """Gaussian white noise burst."""
    return np.random.randn(n)


def _t(dur):
    """Time axis for a given duration (seconds)."""
    return np.linspace(0, dur, int(_SR * dur), endpoint=False)


def _make_sound(wave, rel_vol=1.0):
    """Normalize, apply relative volume, and wrap in a pygame Sound."""
    mx = np.max(np.abs(wave))
    if mx > 0:
        wave = wave / mx
    pcm = (wave * 28000 * np.clip(rel_vol, 0, 1)).astype(np.int16)
    return pygame.sndarray.make_sound(np.column_stack((pcm, pcm)))


# ── SFX generators ───────────────────────────────────────────────────────────

def _sfx_hit():
    """Paddle hit — short swept square wave + click."""
    dur = 0.075
    t = _t(dur)
    freq = 320 - 130 * (t / dur)           # 320 Hz → 190 Hz sweep
    ph = np.cumsum(freq / _SR) * 2 * np.pi
    body = np.sign(np.sin(ph)) * np.exp(-t * 22)
    click = _noise(len(t)) * np.exp(-t * 140) * 0.35
    return _make_sound(body + click, rel_vol=0.80)


def _sfx_wall():
    """Wall bounce — crisp high-pitched blip."""
    dur = 0.042
    t = _t(dur)
    return _make_sound(_sq(t, 560) * np.exp(-t * 38), rel_vol=0.55)


def _sfx_lose():
    """Miss — three descending square tones ('wah-wah-wah')."""
    freqs, dur_each = [294, 220, 165], 0.16  # D4 → A3 → E3
    waves = []
    for freq in freqs:
        t = _t(dur_each)
        waves.append(_sq(t, freq) * np.exp(-t * 5))
    return _make_sound(np.concatenate(waves), rel_vol=0.85)


def _sfx_combo():
    """Combo — ascending 3-note arpeggio (C5 E5 A5)."""
    notes, dur_each = [523, 659, 880], 0.072
    waves = [_sq(_t(dur_each), f, duty=0.25) * np.exp(-_t(dur_each) * 14)
             for f in notes]
    return _make_sound(np.concatenate(waves), rel_vol=0.75)


def _sfx_powerup():
    """Power-up — 6-note rising sparkle arpeggio (C4 → C6)."""
    notes = [262, 330, 392, 523, 659, 1047]
    dur_each = 0.062
    waves = []
    for i, f in enumerate(notes):
        t = _t(dur_each)
        duty = max(0.12, 0.5 - i * 0.06)   # duty narrows upward for sparkle
        waves.append(_sq(t, f, duty) * np.exp(-t * 9))
    return _make_sound(np.concatenate(waves), rel_vol=0.85)


def _sfx_gameover():
    """Game over — 4-note minor descending fanfare (G4 F4 D4 A3)."""
    notes, dur_each = [392, 349, 294, 220], 0.22
    waves = [_sq(_t(dur_each), f) * np.exp(-_t(dur_each) * 3.5) for f in notes]
    return _make_sound(np.concatenate(waves), rel_vol=0.90)


def _sfx_menu_tick():
    """Menu navigation tick — tiny 660 Hz blip."""
    dur = 0.026
    t = _t(dur)
    return _make_sound(_sq(t, 660) * np.exp(-t * 90), rel_vol=0.35)


def _sfx_start_jingle():
    """Game start — quick 4-note ascending fanfare (C5 E5 G5 C6)."""
    notes, dur_each = [523, 659, 784, 1047], 0.088
    waves = [_sq(_t(dur_each), f, duty=0.25) * np.exp(-_t(dur_each) * 11)
             for f in notes]
    return _make_sound(np.concatenate(waves), rel_vol=0.90)


# ── Lobby / attract-mode music ───────────────────────────────────────────────

def _generate_lobby_music():
    """Ambient 4-bar attract-mode loop for the start screen.

    Softer and slower than the game BGM — triangle waves, sustained pad,
    gentle arpeggios, no drums.  Designed to say "welcome, press start."
    """
    bpm    = 88
    beat   = 60.0 / bpm
    bars   = 4
    N      = int(_SR * bars * 4 * beat)
    mix    = np.zeros(N, dtype=np.float64)

    def put(segment, vol, start):
        end = min(start + len(segment), N)
        mix[start:end] += segment[:end - start] * vol

    # ── Pad: sustained Am chord tones, half-note rhythm ──────────────
    pad = [220, 261, 330, 261,   220, 261, 330, 440]   # A3 C4 E4 cycle
    for i, freq in enumerate(pad):
        s   = int(i * 2 * beat * _SR)
        if s >= N: break
        dur = beat * 2.15
        t   = _t(dur)
        env = np.minimum(t / 0.25, 1.0) * np.clip((dur - t) / 0.35, 0, 1)
        put(_tri(t, freq) * env * 0.16, vol=1.0, start=s)

    # ── Arpeggio: Am triad cycling every quarter note ─────────────────
    arp = [220, 261, 330, 440,  330, 261, 220, 330,
           220, 261, 330, 440,  330, 261, 440, 330]
    for i, freq in enumerate(arp):
        s = int(i * beat * _SR)
        if s >= N: break
        t = _t(beat * 0.78)
        put(_tri(t, freq) * np.exp(-t * 3.8) * 0.11, vol=1.0, start=s)

    # ── Lead: sparse high melody every 4 beats ────────────────────────
    leads = [(659, 0), (784, 4), (880, 8), (784, 12)]
    for freq, b in leads:
        s = int(b * beat * _SR)
        if s >= N: break
        dur = beat * 1.7
        t   = _t(dur)
        env = np.minimum(t / 0.04, 1.0) * np.exp(-t * 2.2)
        put(_sq(t, freq, duty=0.25) * env * 0.10, vol=1.0, start=s)

    # ── Sparkle ping on beat 1 of each bar ────────────────────────────
    for bar in range(bars):
        s = int(bar * 4 * beat * _SR)
        t = _t(0.25)
        put(_sq(t, 1047, duty=0.25) * np.exp(-t * 18) * 0.07, vol=1.0, start=s)

    mx = np.max(np.abs(mix))
    if mx > 0:
        mix = mix / mx * 0.24
    pcm = (mix * 32000).astype(np.int16)
    return pygame.sndarray.make_sound(np.column_stack((pcm, pcm)))


# ── BGM generator ────────────────────────────────────────────────────────────

def _generate_bgm():
    """8-bar looping chiptune track.

    Channels
    ────────
    Lead     square 25% duty  — A-minor pentatonic melody
    Bass     triangle         — root-note half-notes
    Chord    square 50% duty  — background arpeggio (low volume)
    Kick     sine sweep       — beat 1 & 3
    Snare    noise + tone     — beat 2 & 4
    Hi-hat   noise burst      — every 8th note
    """
    bpm     = 138
    beat    = 60.0 / bpm       # seconds per quarter note
    bars    = 8
    n_beats = bars * 4
    N       = int(_SR * n_beats * beat)
    mix     = np.zeros(N, dtype=np.float64)

    def put(segment, vol, start):
        end = min(start + len(segment), N)
        mix[start:end] += segment[:end - start] * vol

    # ── LEAD MELODY ───────────────────────────────────────────────────
    # A-minor pentatonic: A4=440 C5=523 D5=587 E5=659 G5=784 A5=880
    # 8 bars × 4 quarter-note slots = 32 slots; 0 = rest
    MELODY = [
        # Bar 1-2: rising run then bounce
        659, 587, 523, 587,   659, 659, 784, 659,
        # Bar 3-4: variation
        587, 523, 440, 523,   659, 784, 880, 0,
        # Bar 5-6: higher register echo
        880, 784, 659, 784,   880, 880, 784, 659,
        # Bar 7-8: resolve back down
        784, 659, 587, 523,   587, 440, 0,   0,
    ]
    pos = 0
    for freq in MELODY:
        if freq:
            t = _t(beat * 0.82)
            put(_sq(t, freq, duty=0.25) * np.exp(-t * 9) * 0.22,
                vol=1.0, start=pos)
        pos += int(_SR * beat)

    # ── BASS (triangle, half-note roots) ──────────────────────────────
    # Am / C / G / Em progression cycling
    BASS = [220, 261, 392, 165,   220, 261, 196, 220,
            220, 261, 392, 165,   294, 261, 220, 165]
    for i, freq in enumerate(BASS):
        s   = int(i * 2 * beat * _SR)    # half-note steps
        if s >= N: break
        dur = beat * 1.85
        t   = _t(dur)
        put(_tri(t, freq) * np.exp(-t * 3.0) * 0.20, vol=1.0, start=s)

    # ── CHORD ARPEGGIO (background texture) ──────────────────────────
    CHORD = [220, 261, 330, 261]   # A3 C4 E4 cycling
    for i in range(n_beats * 2):   # 8th-note grid
        s    = int(i * beat * _SR / 2)
        if s >= N: break
        freq = CHORD[i % 4]
        t    = _t(beat * 0.38)
        put(_sq(t, freq, duty=0.50) * np.exp(-t * 16) * 0.07, vol=1.0, start=s)

    # ── DRUMS ─────────────────────────────────────────────────────────
    def kick():
        dur = 0.14
        t   = _t(dur)
        sweep = 85 * np.exp(-t * 28)
        ph    = np.cumsum(sweep / _SR) * 2 * np.pi
        body  = np.sin(ph) * np.exp(-t * 24)
        clk   = _noise(len(t)) * np.exp(-t * 130) * 0.25
        return body + clk

    def snare():
        dur  = 0.11
        t    = _t(dur)
        body = _sq(t, 210) * np.exp(-t * 32) * 0.28
        n_p  = _noise(len(t)) * np.exp(-t * 30) * 0.72
        return body + n_p

    def hat(open_=False):
        dur = 0.14 if open_ else 0.055
        t   = _t(dur)
        dec = 9 if open_ else 35
        return _noise(len(t)) * np.exp(-t * dec) * 0.30

    kk = kick();  sn = snare()
    hh = hat();   oh = hat(open_=True)

    for bar in range(bars):
        bs = int(bar * 4 * beat * _SR)
        # kick: 1 & 3
        for b in [0, 2]:
            put(kk, 0.55, bs + int(b * beat * _SR))
        # snare: 2 & 4
        for b in [1, 3]:
            put(sn, 0.42, bs + int(b * beat * _SR))
        # hi-hat: every 8th note; open on "and of 2" and "and of 4"
        for e in range(8):
            h = oh if e in [3, 7] else hh
            put(h, 0.28, bs + int(e * beat * _SR / 2))

    # Normalize and return
    mx = np.max(np.abs(mix))
    if mx > 0:
        mix = mix / mx * 0.30
    pcm = (mix * 32000).astype(np.int16)
    return pygame.sndarray.make_sound(np.column_stack((pcm, pcm)))


# ── SoundManager ─────────────────────────────────────────────────────────────

class SoundManager:
    """Manages all game audio: procedural SFX and chiptune BGM."""

    def __init__(self):
        pygame.mixer.init(frequency=_SR, size=-16, channels=2, buffer=512)

        self._sfx_vol   = 0.70   # 0-1, independent of music
        self.bgm_playing = False
        self.enabled     = True

        # Generate SFX
        self.hit_sound      = _sfx_hit()
        self.wall_sound     = _sfx_wall()
        self.lose_sound     = _sfx_lose()
        self.combo_sound    = _sfx_combo()
        self.powerup_sound  = _sfx_powerup()
        self.gameover_sound = _sfx_gameover()
        self.menu_tick_sound = _sfx_menu_tick()
        self.start_sound    = _sfx_start_jingle()

        self._all_sfx = [
            self.hit_sound, self.wall_sound, self.lose_sound,
            self.combo_sound, self.powerup_sound, self.gameover_sound,
            self.menu_tick_sound, self.start_sound,
        ]

        # Generate BGM (game) and lobby music (start screen)
        self.bgm          = _generate_bgm()
        self.bgm_channel  = pygame.mixer.Channel(7)
        self.lobby_bgm    = _generate_lobby_music()
        self.lobby_channel = pygame.mixer.Channel(6)
        self.lobby_playing = False

    # ── Playback ──────────────────────────────────────────────────────

    def play_hit(self):
        if self.enabled: self.hit_sound.play()

    def play_lose(self):
        if self.enabled: self.lose_sound.play()

    def play_wall(self):
        if self.enabled: self.wall_sound.play()

    def play_powerup(self):
        if self.enabled: self.powerup_sound.play()

    def play_combo(self):
        if self.enabled: self.combo_sound.play()

    def play_gameover(self):
        if self.enabled: self.gameover_sound.play()

    def play_menu_tick(self):
        if self.enabled: self.menu_tick_sound.play()

    def play_start_jingle(self):
        if self.enabled: self.start_sound.play()

    # ── BGM control ───────────────────────────────────────────────────

    def start_bgm(self, volume_pct=50):
        self.stop_lobby_music()          # never overlap with lobby
        vol = max(0, min(100, volume_pct)) / 100.0 * 0.40
        self.bgm.set_volume(vol)
        self.bgm_channel.play(self.bgm, loops=-1)
        self.bgm_playing = True

    def stop_bgm(self):
        self.bgm_channel.stop()
        self.bgm_playing = False

    def start_lobby_music(self, volume_pct=50):
        if self.lobby_playing:
            return
        vol = max(0, min(100, volume_pct)) / 100.0 * 0.35
        self.lobby_bgm.set_volume(vol)
        self.lobby_channel.play(self.lobby_bgm, loops=-1)
        self.lobby_playing = True

    def stop_lobby_music(self):
        self.lobby_channel.stop()
        self.lobby_playing = False

    def set_bgm_volume(self, volume_pct):
        vol = max(0, min(100, volume_pct)) / 100.0 * 0.40
        self.bgm.set_volume(vol)
        # Lobby is slightly quieter than the game track
        self.lobby_bgm.set_volume(vol * 0.875)

    # ── Volume control ────────────────────────────────────────────────

    def set_sfx_volume(self, volume_pct):
        """Set SFX master volume (0-100). Applied to all sound effects."""
        self._sfx_vol = max(0, min(100, volume_pct)) / 100.0
        for snd in self._all_sfx:
            snd.set_volume(self._sfx_vol)

    def update_enabled(self, enabled):
        self.enabled = enabled
        if not enabled:
            if self.bgm_playing:
                self.stop_bgm()
            if self.lobby_playing:
                self.stop_lobby_music()

    def cleanup(self):
        self.stop_bgm()
        self.stop_lobby_music()
