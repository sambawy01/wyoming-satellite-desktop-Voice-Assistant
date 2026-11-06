# Desktop voice assistant

Run the satellite on an ordinary computer — Linux, macOS or Windows — using
the machine's own microphone and speakers, instead of Raspberry Pi audio
hardware. The result is the same thing a ReSpeaker satellite gives you: a
hands-free voice assistant that Home Assistant drives, just running on the
desktop you already own.

The other tutorials ([installer](tutorial_installer.md),
[2mic](tutorial_2mic.md), [docker](tutorial_docker.md)) all assume a Pi. This
one assumes nothing but a working sound setup.

## Why a desktop needs its own path

The satellite never touches sound hardware itself. `--mic-command` and
`--snd-command` name external programs that write and read **raw, headerless**
PCM on stdout/stdin, and the Pi tutorials fill those in with `arecord`/`aplay`
against a specific ALSA card.

That breaks down on a desktop for two reasons:

- **The device names are wrong and not portable.** `plughw:CARD=seeed2micvoicec`
  does not exist on your laptop, and the right answer differs between
  PipeWire, PulseAudio, CoreAudio and DirectShow.
- **ALSA takes the device exclusively.** On a Pi appliance that is fine. On a
  desktop it means the satellite and your browser fight over the microphone,
  and whichever starts second fails.

`wyoming_satellite.desktop` works out which sound server you actually run and
writes the right commands for it. Nothing in the satellite itself changed —
this is a front end that composes a command line, and it will show you exactly
what it came up with.

## Install

```sh
git clone https://github.com/sambawy01/wyoming-satellite-desktop-Voice-Assistant.git
cd wyoming-satellite-desktop-Voice-Assistant
python3 script/setup --vad --noisegain
```

`--vad` adds silence detection and `--noisegain` adds noise suppression and
automatic gain; both are optional, and both are worth having on a desktop mic
sitting a metre from your keyboard.

You also need the host audio tools for your platform:

| Platform | Install | Backend used |
| --- | --- | --- |
| Linux (PipeWire) | usually present; else your distro's `pipewire` tools | `pipewire` |
| Linux (PulseAudio) | `pulseaudio-utils` (Debian/Ubuntu) | `pulseaudio` |
| Linux (bare ALSA) | `alsa-utils` | `alsa` |
| macOS | `brew install sox` | `sox` |
| macOS (no SoX) | `brew install ffmpeg` | `avfoundation` |
| Windows | [ffmpeg](https://ffmpeg.org/download.html) on `PATH` | `dshow` |

PipeWire users: `pipewire-pulse` is normally installed too, so both the
`pipewire` and `pulseaudio` backends will work. Either is fine.

## Check what was detected

```sh
script/run_desktop --list-backends
```

```
Audio backends for Linux (in preference order):

  pipewire       PipeWire (pw-record/pw-play)
                 [available]

  pulseaudio     PulseAudio / pipewire-pulse (parecord/paplay)
                 [available]
...
```

Backends are tried in that order, and ALSA is deliberately last — see above.
Then look at your devices:

```sh
script/run_desktop --list-devices
```

Device identifiers are **not** interchangeable between backends: a PulseAudio
source name, an ALSA PCM name, an avfoundation index and a DirectShow
friendly-name are four different namespaces. `--list-devices` prints the
identifiers for the backend you are actually using, and explains the format.

## Run it

Start a wake word service first, so the satellite is hands-free rather than
streaming everything it hears:

```sh
pip install wyoming-openwakeword
python3 -m wyoming_openwakeword --uri tcp://127.0.0.1:10400 --preload-model ok_nabu
```

Then, in another terminal:

```sh
script/run_desktop \
  --wake-uri tcp://127.0.0.1:10400 \
  --wake-word-name ok_nabu \
  --name "Desk Satellite" \
  --area Office
```

Say "ok nabu" and you should hear the awake sound. If you start it with
neither `--wake-uri` nor `--vad`, it warns you: the satellite will stream
audio continuously, which works but sends everything to your server.

Useful options:

| Option | What it does |
| --- | --- |
| `--backend NAME` | Force a backend instead of auto-detecting |
| `--mic-device` / `--snd-device` | Pick a device (see `--list-devices`) |
| `--noise-suppression 2` | Noise suppression, 0–4 (needs `--noisegain`) |
| `--auto-gain 5` | Automatic gain in dbFS, 0–31 (needs `--noisegain`) |
| `--mic-volume-multiplier 2.0` | Software gain for a quiet mic |
| `--vad` | Only stream once speech starts (needs `--vad`) |
| `--no-sounds` | Don't play the bundled awake/done sounds |
| `--debug` | Log DEBUG, including the full satellite command |

Anything the desktop front end does not cover goes straight through after a
`--`:

```sh
script/run_desktop -- --mic-channel-index 1 --debug-recording-dir /tmp/rec
```

## See the real command

Nothing here is hidden. `--print-command` prints the exact satellite command
that would run:

```sh
script/run_desktop --backend pulseaudio --print-command
```

```
.../python -m wyoming_satellite --uri tcp://0.0.0.0:10700 --name desk \
  --mic-command 'parecord --raw --rate=16000 --channels=1 --format=s16le' \
  --mic-command-rate 16000 --mic-command-width 2 --mic-command-channels 1 \
  --snd-command 'paplay --raw --rate=22050 --channels=1 --format=s16le' \
  --snd-command-rate 22050 --snd-command-width 2 --snd-command-channels 1 ...
```

Use it to learn the flags, to adapt a command by hand, or to generate a
command for a different machine — `--print-command` works even when the audio
tools are not installed locally, and warns rather than failing.

### The `--raw` in there matters

Two mistakes are easy to make by hand and produce the same symptom — a
satellite that connects, streams, and is never understood:

- `paplay` and `parecord` default to **file-format mode, not raw**. Only their
  `pacat`/`parec` aliases default to raw. Without `--raw` the stream carries a
  WAV header that the satellite reads as audio.
- `pw-record`/`pw-play` writing to `-` wrap the stream in an **AU container**
  unless `--raw` is given.

The generated commands always pass `--raw`.

## Add it to Home Assistant

The satellite listens on `tcp://0.0.0.0:10700` by default and announces itself
over zeroconf, so **Settings → Devices & Services** should offer it as a
discovered *Wyoming Protocol* integration. If it does not, add that
integration by hand with the host and port `10700`.

Then assign it a voice assistant pipeline under **Settings → Voice
assistants**. Timers, `--awake-wav`/`--done-wav` and the event commands
described in [general.md](general.md) all work exactly as they do on a Pi.

To keep the satellite off the network entirely, pass `--no-zeroconf` and
`--uri tcp://127.0.0.1:10700` and point a local server at it.

## Start it automatically

```sh
script/run_desktop --wake-uri tcp://127.0.0.1:10400 --install-service
```

This writes a **user-level** unit for the configuration you passed, carrying
the same command `--print-command` shows, and tells you how to enable it. It
never needs root.

User-level is the important part. The Pi installer writes a *system* unit into
`/etc/systemd/system`, which cannot work on a desktop: PipeWire and PulseAudio
expose per-user sockets under `$XDG_RUNTIME_DIR`, so a system service runs as
the wrong user with no sound server to talk to.

### Linux

```sh
systemctl --user daemon-reload
systemctl --user enable --now wyoming-satellite.service
journalctl --user -u wyoming-satellite -f
```

By default a user service stops when you log out. To keep it running:

```sh
sudo loginctl enable-linger $USER
```

### macOS

```sh
launchctl load -w ~/Library/LaunchAgents/io.wyoming.satellite.plist
```

macOS will ask for microphone permission the first time. Grant it under
**System Settings → Privacy & Security → Microphone** for the terminal or app
that launches it, or the satellite records silence with no error.

### Windows

`--install-service` is not supported. Take the output of `--print-command` and
create a Task Scheduler task that runs it at logon.

## Troubleshooting

**"No usable audio backend found"** — none of the host tools are on `PATH`.
`--list-backends` names exactly which programs each backend wants.

**It records silence.** Check the input is not muted and is the right device
(`--list-devices`, then `--mic-device`). On macOS check the microphone
permission above. Add `--mic-volume-multiplier 2.0` for a quiet mic. To see
what is actually being captured, record straight from the backend's own
command — copy the `--mic-command` out of `--print-command` and run it into a
file.

**Wake word never triggers.** Confirm the wake service is up and that
`--wake-word-name` matches a model it preloaded. `--debug` logs detections.

**Choppy or robotic audio.** Another program holds the device exclusively —
most often this means you are on the `alsa` backend. Install the PulseAudio or
PipeWire tools and let it pick one of those instead.

**Echo: it hears its own replies.** Raise
`--mic-seconds-to-mute-after-awake-wav` (via `--`), move the mic away from the
speakers, or enable your sound server's echo cancellation
(`module-echo-cancel` on PulseAudio/PipeWire).

**It works in a terminal but not as a service.** Almost always the user/system
unit distinction above, or linger not enabled.
