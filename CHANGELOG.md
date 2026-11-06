# Changelog

## Unreleased

- Add desktop support (`wyoming_satellite.desktop`, `script/run_desktop`)
  - Auto-detects the host sound server and generates the matching
    `--mic-command`/`--snd-command`: PipeWire, PulseAudio/pipewire-pulse,
    ALSA, SoX, macOS avfoundation and Windows DirectShow
  - `--list-backends`, `--list-devices` and `--print-command` for inspection
  - `--install-service` writes a user-level systemd unit or macOS LaunchAgent
    (not a system unit, which cannot reach the user's audio socket)
  - New console script `wyoming-satellite-desktop`
  - See `docs/tutorial_desktop.md`

## 1.4.1

- Send `played` event to server

## 1.4.0

- Migrate to pyproject.toml

## 1.3.1

- Send audio-start to wake service after detect

## 1.3.0

- Bump to wyoming 1.5.4 (timers)
- Add support for voice timers
- Add `--timer-finished-wav` and `--timer-finished-wav-repeat`
- Add `--timer-started-command`
- Add `--timer-updated-command`
- Add `--timer-cancelled-command`
- Add `--timer-finished-command`

## 1.2.0

- Add `--tts-played-command`
- Add `--mic-seconds-to-mute-after-awake-wav` and `--mic-no-mute-during-awake-wav`
- Send preferred sound format to server

## 1.1.1

- Bump to wyoming 1.5.2 (package fix)

## 1.1.0

- Bump to wyoming 1.5.1
- Send wyoming-satellite version in `info` message
- Ping server if supported (faster awareness of disconnection)
- Support `pause-satellite` message
- Stop streaming/wake word detection as soon as `pause-satellite` is received or server disconnects
- Mute microphone when awake WAV is playing

## 1.0.0

- Initial release

