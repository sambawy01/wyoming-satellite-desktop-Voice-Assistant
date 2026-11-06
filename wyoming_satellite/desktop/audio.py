"""Desktop audio backends.

The satellite does not talk to sound hardware itself: `--mic-command` and
`--snd-command` name external programs that write/read **raw, headerless**
PCM on stdout/stdin. Desktop support is therefore entirely a matter of
generating the right command line for whatever sound server the host runs,
which is what this module does. Nothing in `wyoming_satellite` itself needed
to change to support a desktop.

Two traps are baked into the backends below, both of which produce the same
symptom -- a satellite that connects, streams, and is never understood:

1. `paplay`/`parecord` default to **file-format** mode, not raw (only their
   `pacat`/`parec` aliases default to raw), so `--raw` is passed explicitly.
   Without it the stream carries a WAV header the satellite reads as audio.
2. `pw-record`/`pw-play` with `-` and no `--raw` wrap the stream in an **AU
   container** for the same reason.

Device selection differs per backend rather than being normalised, because
the identifiers are not interchangeable: a PulseAudio source name, an ALSA
PCM name, an avfoundation index and a dshow friendly-name are four different
namespaces. `device_help` carries the per-backend explanation.
"""

import platform
import shlex
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Sample width (bytes) that every backend here speaks. The satellite's
# default is 2 and the Wyoming protocol is 16-bit throughout; a backend
# asked for anything else raises rather than quietly emitting s16.
SUPPORTED_WIDTH = 2

MIC_RATE = 16000
"""Rate wake word and speech-to-text services expect (hertz)."""

MIC_CHANNELS = 1

SND_RATE = 22050
"""Default rate for text-to-speech playback (hertz)."""

SND_CHANNELS = 1


class UnsupportedFormatError(ValueError):
    """Raised when a backend cannot express the requested audio format."""


@dataclass(frozen=True)
class AudioFormat:
    """Raw PCM format exchanged with a mic/snd program."""

    rate: int
    width: int
    channels: int

    def __post_init__(self) -> None:
        if self.rate <= 0:
            raise UnsupportedFormatError(f"Invalid sample rate: {self.rate}")

        if self.channels <= 0:
            raise UnsupportedFormatError(f"Invalid channel count: {self.channels}")

    def require_s16(self, backend_name: str) -> None:
        """Raise unless this format is 16-bit."""
        if self.width != SUPPORTED_WIDTH:
            raise UnsupportedFormatError(
                f"{backend_name} backend only supports "
                f"{SUPPORTED_WIDTH}-byte (16-bit) samples, got {self.width}"
            )


MIC_FORMAT = AudioFormat(rate=MIC_RATE, width=SUPPORTED_WIDTH, channels=MIC_CHANNELS)
SND_FORMAT = AudioFormat(rate=SND_RATE, width=SUPPORTED_WIDTH, channels=SND_CHANNELS)


class AudioBackend(ABC):
    """A pair of host programs that can record from and play to the desktop."""

    name: str = ""
    description: str = ""
    platforms: Tuple[str, ...] = ()
    """Values of platform.system() this backend can run on."""

    record_program: str = ""
    play_program: str = ""
    device_help: str = ""

    list_sources_command: Optional[List[str]] = None
    list_sinks_command: Optional[List[str]] = None

    @abstractmethod
    def record_args(self, fmt: AudioFormat, device: Optional[str] = None) -> List[str]:
        """Program + args that write raw PCM to stdout."""

    @abstractmethod
    def play_args(self, fmt: AudioFormat, device: Optional[str] = None) -> List[str]:
        """Program + args that read raw PCM from stdin."""

    def record_command(self, fmt: AudioFormat, device: Optional[str] = None) -> str:
        """Shell-quoted command for --mic-command."""
        return shlex.join(self.record_args(fmt, device))

    def play_command(self, fmt: AudioFormat, device: Optional[str] = None) -> str:
        """Shell-quoted command for --snd-command."""
        return shlex.join(self.play_args(fmt, device))

    def supports_platform(self, system: Optional[str] = None) -> bool:
        """True if this backend can run on the given platform.system()."""
        return (system or platform.system()) in self.platforms

    def missing_programs(self) -> List[str]:
        """Programs this backend needs that are not on PATH."""
        return [
            program
            for program in dict.fromkeys((self.record_program, self.play_program))
            if shutil.which(program) is None
        ]

    def is_available(self, system: Optional[str] = None) -> bool:
        """True if this backend can run here and its programs are installed."""
        return self.supports_platform(system) and not self.missing_programs()


class PipeWireBackend(AudioBackend):
    """Native PipeWire, via pw-record/pw-play (pw-cat)."""

    name = "pipewire"
    description = "PipeWire (pw-record/pw-play)"
    platforms = ("Linux",)
    record_program = "pw-record"
    play_program = "pw-play"
    device_help = (
        "A PipeWire node.name or object.serial, as shown by 'wpctl status'. "
        "pw-cat has no option to list targets; omit to use the default node."
    )
    # pw-cat cannot list targets itself, so listing borrows pipewire-pulse.
    list_sources_command = ["pactl", "list", "short", "sources"]
    list_sinks_command = ["pactl", "list", "short", "sinks"]

    def _args(self, program: str, fmt: AudioFormat, device: Optional[str]) -> List[str]:
        fmt.require_s16(self.name)
        args = [
            program,
            # Without --raw a stream to stdout/stdin is wrapped in an AU container.
            "--raw",
            f"--rate={fmt.rate}",
            f"--channels={fmt.channels}",
            "--format=s16",
        ]
        if device:
            args.append(f"--target={device}")

        args.append("-")
        return args

    def record_args(self, fmt: AudioFormat, device: Optional[str] = None) -> List[str]:
        return self._args(self.record_program, fmt, device)

    def play_args(self, fmt: AudioFormat, device: Optional[str] = None) -> List[str]:
        return self._args(self.play_program, fmt, device)


class PulseAudioBackend(AudioBackend):
    """PulseAudio, and PipeWire via pipewire-pulse."""

    name = "pulseaudio"
    description = "PulseAudio / pipewire-pulse (parecord/paplay)"
    platforms = ("Linux",)
    record_program = "parecord"
    play_program = "paplay"
    device_help = (
        "A source (record) or sink (playback) name from "
        "'pactl list short sources' / 'pactl list short sinks'."
    )
    list_sources_command = ["pactl", "list", "short", "sources"]
    list_sinks_command = ["pactl", "list", "short", "sinks"]

    def _args(self, program: str, fmt: AudioFormat, device: Optional[str]) -> List[str]:
        fmt.require_s16(self.name)
        args = [
            program,
            # parecord/paplay default to file-format mode, NOT raw.
            "--raw",
            f"--rate={fmt.rate}",
            f"--channels={fmt.channels}",
            "--format=s16le",
        ]
        if device:
            args.append(f"--device={device}")

        return args

    def record_args(self, fmt: AudioFormat, device: Optional[str] = None) -> List[str]:
        return self._args(self.record_program, fmt, device)

    def play_args(self, fmt: AudioFormat, device: Optional[str] = None) -> List[str]:
        return self._args(self.play_program, fmt, device)


class AlsaBackend(AudioBackend):
    """Bare ALSA, via arecord/aplay.

    Last resort on a desktop: ALSA devices are usually opened exclusively, so
    the satellite and the rest of the session fight over the microphone.
    """

    name = "alsa"
    description = "ALSA (arecord/aplay) - exclusive device access"
    platforms = ("Linux",)
    record_program = "arecord"
    play_program = "aplay"
    device_help = (
        "An ALSA PCM name from 'arecord -L' / 'aplay -L', e.g. 'default' or "
        "'plughw:CARD=USB,DEV=0'."
    )
    list_sources_command = ["arecord", "-L"]
    list_sinks_command = ["aplay", "-L"]

    def _args(self, program: str, fmt: AudioFormat, device: Optional[str]) -> List[str]:
        fmt.require_s16(self.name)
        args = [
            program,
            "-q",
            "-t",
            "raw",
            "-f",
            "S16_LE",
            "-r",
            str(fmt.rate),
            "-c",
            str(fmt.channels),
        ]
        if device:
            args.extend(["-D", device])

        return args

    def record_args(self, fmt: AudioFormat, device: Optional[str] = None) -> List[str]:
        return self._args(self.record_program, fmt, device)

    def play_args(self, fmt: AudioFormat, device: Optional[str] = None) -> List[str]:
        return self._args(self.play_program, fmt, device)


class SoxBackend(AudioBackend):
    """SoX, via its rec/play aliases.

    The cleanest option on macOS ('brew install sox'). SoX has no device flag;
    it reads the AUDIODEV environment variable instead.
    """

    name = "sox"
    description = "SoX (rec/play)"
    platforms = ("Darwin", "Linux")
    record_program = "rec"
    play_program = "play"
    device_help = (
        "SoX takes no device argument: set the AUDIODEV environment variable "
        "instead (and AUDIODRIVER to pick a driver, e.g. coreaudio)."
    )

    def _args(self, program: str, fmt: AudioFormat, device: Optional[str]) -> List[str]:
        fmt.require_s16(self.name)
        if device:
            raise UnsupportedFormatError(
                "sox backend takes no device argument; set AUDIODEV instead"
            )

        return [
            program,
            "-q",
            "-t",
            "raw",
            "-b",
            str(fmt.width * 8),
            "-e",
            "signed-integer",
            "-r",
            str(fmt.rate),
            "-c",
            str(fmt.channels),
            "-",
        ]

    def record_args(self, fmt: AudioFormat, device: Optional[str] = None) -> List[str]:
        return self._args(self.record_program, fmt, device)

    def play_args(self, fmt: AudioFormat, device: Optional[str] = None) -> List[str]:
        return self._args(self.play_program, fmt, device)


class _FfmpegBackend(AudioBackend):
    """Shared ffmpeg recording / ffplay playback.

    Subclasses supply the capture input device, which is the only part that
    differs between macOS and Windows. Playback goes through ffplay because
    ffmpeg has no portable output device on either platform.
    """

    record_program = "ffmpeg"
    play_program = "ffplay"
    capture_format = ""

    def _input_args(self, device: Optional[str]) -> List[str]:
        raise NotImplementedError

    def record_args(self, fmt: AudioFormat, device: Optional[str] = None) -> List[str]:
        fmt.require_s16(self.name)
        return (
            [
                self.record_program,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                self.capture_format,
            ]
            + self._input_args(device)
            + [
                "-f",
                "s16le",
                "-ar",
                str(fmt.rate),
                "-ac",
                str(fmt.channels),
                "-",
            ]
        )

    def play_args(self, fmt: AudioFormat, device: Optional[str] = None) -> List[str]:
        fmt.require_s16(self.name)
        if device:
            raise UnsupportedFormatError(
                "ffplay takes no output device argument; "
                "change the system default output instead"
            )

        return [
            self.play_program,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nodisp",
            "-autoexit",
            "-f",
            "s16le",
            "-ar",
            str(fmt.rate),
            "-ac",
            str(fmt.channels),
            "-i",
            "-",
        ]


class AvFoundationBackend(_FfmpegBackend):
    """macOS capture through avfoundation."""

    name = "avfoundation"
    description = "macOS avfoundation capture (ffmpeg) + ffplay playback"
    platforms = ("Darwin",)
    capture_format = "avfoundation"
    device_help = (
        "An audio device index, as listed by "
        "'ffmpeg -f avfoundation -list_devices true -i \"\"'. Defaults to 0."
    )
    list_sources_command = [
        "ffmpeg",
        "-hide_banner",
        "-f",
        "avfoundation",
        "-list_devices",
        "true",
        "-i",
        "",
    ]

    def _input_args(self, device: Optional[str]) -> List[str]:
        # avfoundation inputs are "video:audio"; an empty video half is
        # required for audio-only capture.
        return ["-i", f":{device if device else '0'}"]


class DirectShowBackend(_FfmpegBackend):
    """Windows capture through DirectShow."""

    name = "dshow"
    description = "Windows DirectShow capture (ffmpeg) + ffplay playback"
    platforms = ("Windows",)
    capture_format = "dshow"
    device_help = (
        "A DirectShow device name, as listed by "
        "'ffmpeg -f dshow -list_devices true -i dummy'. Required."
    )
    list_sources_command = [
        "ffmpeg",
        "-hide_banner",
        "-f",
        "dshow",
        "-list_devices",
        "true",
        "-i",
        "dummy",
    ]

    def _input_args(self, device: Optional[str]) -> List[str]:
        if not device:
            raise UnsupportedFormatError(
                "dshow has no default capture device: pass a device name "
                "(see 'ffmpeg -f dshow -list_devices true -i dummy')"
            )

        return ["-i", f"audio={device}"]


# Ordered by preference within each platform: share the device where we can,
# and fall back to exclusive access only when nothing else is installed.
BACKENDS: Tuple[AudioBackend, ...] = (
    PipeWireBackend(),
    PulseAudioBackend(),
    SoxBackend(),
    AvFoundationBackend(),
    DirectShowBackend(),
    AlsaBackend(),
)

BACKENDS_BY_NAME: Dict[str, AudioBackend] = {
    backend.name: backend for backend in BACKENDS
}


def backends_for_platform(system: Optional[str] = None) -> List[AudioBackend]:
    """Backends that could run on this platform, in preference order."""
    return [backend for backend in BACKENDS if backend.supports_platform(system)]


def get_backend(name: str) -> AudioBackend:
    """Look up a backend by name."""
    backend = BACKENDS_BY_NAME.get(name)
    if backend is None:
        raise KeyError(
            f"Unknown audio backend '{name}'. Available: "
            + ", ".join(sorted(BACKENDS_BY_NAME))
        )

    return backend


def detect_backend(system: Optional[str] = None) -> Optional[AudioBackend]:
    """First backend that can run here with its programs installed."""
    for backend in backends_for_platform(system):
        if not backend.missing_programs():
            return backend

    return None
