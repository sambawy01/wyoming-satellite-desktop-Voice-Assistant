"""Run the satellite on an ordinary desktop.

A thin front end over `python -m wyoming_satellite` that works out the host's
sound server and writes the `--mic-command`/`--snd-command` lines for it, so
a desktop user does not have to know whether they are on PipeWire, PulseAudio
or CoreAudio.

Everything it does is visible: `--print-command` shows the exact satellite
command it would run, and that same command is what `--install-service`
writes into the autostart unit.
"""

import argparse
import logging
import os
import platform
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from .audio import (
    BACKENDS,
    MIC_CHANNELS,
    MIC_RATE,
    SND_CHANNELS,
    SND_RATE,
    SUPPORTED_WIDTH,
    AudioBackend,
    AudioFormat,
    backends_for_platform,
    detect_backend,
    get_backend,
)
from .service import install_launchd, install_systemd_user

_LOGGER = logging.getLogger("wyoming_satellite.desktop")

_PACKAGE_DIR = Path(__file__).parent.parent
DEFAULT_URI = "tcp://0.0.0.0:10700"


def find_sounds_dir() -> Optional[Path]:
    """Locate the bundled sounds/ directory, if this is a source checkout."""
    for candidate in (
        _PACKAGE_DIR.parent / "sounds",  # repository checkout
        _PACKAGE_DIR / "sounds",  # packaged alongside the module
    ):
        if candidate.is_dir():
            return candidate

    return None


def build_satellite_args(
    backend: AudioBackend,
    uri: str = DEFAULT_URI,
    name: str = "",
    area: Optional[str] = None,
    mic_device: Optional[str] = None,
    snd_device: Optional[str] = None,
    mic_rate: int = MIC_RATE,
    snd_rate: int = SND_RATE,
    mic_channels: int = MIC_CHANNELS,
    snd_channels: int = SND_CHANNELS,
    mic_volume_multiplier: float = 1.0,
    snd_volume_multiplier: float = 1.0,
    noise_suppression: int = 0,
    auto_gain: int = 0,
    wake_uri: Optional[str] = None,
    wake_word_names: Optional[List[str]] = None,
    vad: bool = False,
    awake_wav: Optional[Path] = None,
    done_wav: Optional[Path] = None,
    no_zeroconf: bool = False,
    debug: bool = False,
    extra_args: Optional[List[str]] = None,
    python: Optional[str] = None,
) -> List[str]:
    """Compose the full satellite command line. Pure: no I/O, no process."""
    mic_format = AudioFormat(
        rate=mic_rate, width=SUPPORTED_WIDTH, channels=mic_channels
    )
    snd_format = AudioFormat(
        rate=snd_rate, width=SUPPORTED_WIDTH, channels=snd_channels
    )

    args = [
        python or sys.executable,
        "-m",
        "wyoming_satellite",
        "--uri",
        uri,
        "--name",
        name or platform.node() or "Desktop Satellite",
        # Mic
        "--mic-command",
        backend.record_command(mic_format, mic_device),
        "--mic-command-rate",
        str(mic_format.rate),
        "--mic-command-width",
        str(mic_format.width),
        "--mic-command-channels",
        str(mic_format.channels),
        # Snd
        "--snd-command",
        backend.play_command(snd_format, snd_device),
        "--snd-command-rate",
        str(snd_format.rate),
        "--snd-command-width",
        str(snd_format.width),
        "--snd-command-channels",
        str(snd_format.channels),
    ]

    if area:
        args.extend(["--area", area])

    if mic_volume_multiplier != 1.0:
        args.extend(["--mic-volume-multiplier", str(mic_volume_multiplier)])

    if snd_volume_multiplier != 1.0:
        args.extend(["--snd-volume-multiplier", str(snd_volume_multiplier)])

    if noise_suppression:
        args.extend(["--mic-noise-suppression", str(noise_suppression)])

    if auto_gain:
        args.extend(["--mic-auto-gain", str(auto_gain)])

    if wake_uri:
        args.extend(["--wake-uri", wake_uri])
        for wake_word_name in wake_word_names or []:
            args.extend(["--wake-word-name", wake_word_name])

    if vad:
        args.append("--vad")

    if awake_wav is not None:
        args.extend(["--awake-wav", str(awake_wav)])

    if done_wav is not None:
        args.extend(["--done-wav", str(done_wav)])

    if no_zeroconf:
        args.append("--no-zeroconf")

    if debug:
        args.append("--debug")

    args.extend(extra_args or [])
    return args


def _print_backends(system: str) -> None:
    print(f"Audio backends for {system} (in preference order):")
    print()
    for backend in backends_for_platform(system):
        missing = backend.missing_programs()
        status = "available" if not missing else f"missing: {', '.join(missing)}"
        print(f"  {backend.name:<14} {backend.description}")
        print(f"  {'':<14} [{status}]")
        print()

    other = [b for b in BACKENDS if not b.supports_platform(system)]
    if other:
        print("Not applicable on this platform: " + ", ".join(b.name for b in other))


def _run_list_command(title: str, command: Optional[List[str]]) -> None:
    print(f"--- {title} ---")
    if not command:
        print("(this backend cannot list devices; see --list-backends for help)")
        print()
        return

    try:
        # Several of these tools report devices on stderr, so it is merged in.
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        print(completed.stdout.strip() or "(no output)")
    except FileNotFoundError:
        print(f"(command not found: {command[0]})")

    print()


def _resolve_backend(
    name: Optional[str], system: str, require_available: bool = True
) -> AudioBackend:
    """Pick the backend to use, failing with an actionable message.

    `require_available` is relaxed for --print-command, so a command can be
    generated on one machine for another.
    """
    if name:
        backend = get_backend(name)
        if not backend.supports_platform(system):
            _LOGGER.warning(
                "Backend '%s' is not normally used on %s", backend.name, system
            )

        missing = backend.missing_programs()
        if missing:
            message = (
                f"Backend '{backend.name}' needs these programs, "
                f"which are not on PATH: {', '.join(missing)}"
            )
            if require_available:
                raise SystemExit(message)

            _LOGGER.warning("%s", message)

        return backend

    detected = detect_backend(system)
    if detected is None and not require_available:
        # Nothing is installed, but we are only printing: fall back to this
        # platform's preferred backend so there is something to show.
        candidates = backends_for_platform(system)
        if candidates:
            _LOGGER.warning(
                "No audio backend is installed; showing '%s' for reference",
                candidates[0].name,
            )
            return candidates[0]

    if detected is None:
        candidates = backends_for_platform(system)
        hint = ", ".join(
            f"{b.name} (needs {' + '.join(b.missing_programs())})" for b in candidates
        )
        raise SystemExit(
            "No usable audio backend found on "
            f"{system}. Install one of: {hint or 'none known for this platform'}"
        )

    return detected


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="wyoming-satellite-desktop",
        description="Run a Wyoming satellite using desktop audio.",
    )

    parser.add_argument(
        "--backend",
        help="Audio backend to use (default: auto-detect). See --list-backends",
    )
    parser.add_argument(
        "--list-backends",
        action="store_true",
        help="List audio backends for this platform and exit",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List the backend's input/output devices and exit",
    )

    parser.add_argument("--mic-device", help="Backend-specific capture device")
    parser.add_argument("--snd-device", help="Backend-specific playback device")
    parser.add_argument(
        "--mic-rate",
        type=int,
        default=MIC_RATE,
        help=f"Microphone sample rate (default: {MIC_RATE})",
    )
    parser.add_argument(
        "--snd-rate",
        type=int,
        default=SND_RATE,
        help=f"Playback sample rate (default: {SND_RATE})",
    )
    parser.add_argument("--mic-volume-multiplier", type=float, default=1.0)
    parser.add_argument("--snd-volume-multiplier", type=float, default=1.0)
    parser.add_argument(
        "--noise-suppression",
        type=int,
        default=0,
        choices=(0, 1, 2, 3, 4),
        help="Noise suppression level (needs the 'noisegain' extra)",
    )
    parser.add_argument(
        "--auto-gain",
        type=int,
        default=0,
        choices=list(range(32)),
        help="Auto gain in dbFS (needs the 'noisegain' extra)",
    )

    parser.add_argument("--uri", default=DEFAULT_URI, help=f"default: {DEFAULT_URI}")
    parser.add_argument("--name", help="Satellite name (default: this host's name)")
    parser.add_argument("--area", help="Area name of the satellite")
    parser.add_argument(
        "--wake-uri",
        help="URI of a Wyoming wake word service, e.g. tcp://127.0.0.1:10400",
    )
    parser.add_argument(
        "--wake-word-name",
        action="append",
        default=[],
        help="Wake word to listen for (repeatable, requires --wake-uri)",
    )
    parser.add_argument(
        "--vad",
        action="store_true",
        help="Wait for speech before streaming (needs the 'vad' extra)",
    )
    parser.add_argument(
        "--no-sounds",
        action="store_true",
        help="Do not play the bundled awake/done sounds",
    )
    parser.add_argument("--no-zeroconf", action="store_true")

    parser.add_argument(
        "--print-command",
        action="store_true",
        help="Print the satellite command that would run, and exit",
    )
    parser.add_argument(
        "--install-service",
        action="store_true",
        help="Write a user-level autostart unit for this configuration and exit",
    )

    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    parser.add_argument(
        "satellite_args",
        nargs=argparse.REMAINDER,
        help="Extra arguments passed straight to wyoming_satellite (after --)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    system = platform.system()

    if args.list_backends:
        _print_backends(system)
        return

    backend = _resolve_backend(
        args.backend, system, require_available=not args.print_command
    )

    if args.list_devices:
        print(f"Backend: {backend.name} ({backend.description})")
        print(f"Devices: {backend.device_help}")
        print()
        _run_list_command("Capture", backend.list_sources_command)
        _run_list_command("Playback", backend.list_sinks_command)
        return

    awake_wav: Optional[Path] = None
    done_wav: Optional[Path] = None
    if not args.no_sounds:
        sounds_dir = find_sounds_dir()
        if sounds_dir is None:
            _LOGGER.debug("No bundled sounds directory found")
        else:
            for filename, attr in (("awake.wav", "awake"), ("done.wav", "done")):
                wav_path = sounds_dir / filename
                if not wav_path.is_file():
                    continue

                if attr == "awake":
                    awake_wav = wav_path
                else:
                    done_wav = wav_path

    # REMAINDER keeps the "--" separator; drop it so it is not passed on.
    extra_args = list(args.satellite_args)
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]

    if not (args.wake_uri or args.vad or extra_args):
        _LOGGER.warning(
            "Neither --wake-uri nor --vad given: the satellite will stream audio "
            "continuously. Point --wake-uri at a wake word service "
            "(e.g. openWakeWord on tcp://127.0.0.1:10400) for a hands-free "
            "assistant."
        )

    satellite_args = build_satellite_args(
        backend,
        uri=args.uri,
        name=args.name or "",
        area=args.area,
        mic_device=args.mic_device,
        snd_device=args.snd_device,
        mic_rate=args.mic_rate,
        snd_rate=args.snd_rate,
        mic_volume_multiplier=args.mic_volume_multiplier,
        snd_volume_multiplier=args.snd_volume_multiplier,
        noise_suppression=args.noise_suppression,
        auto_gain=args.auto_gain,
        wake_uri=args.wake_uri,
        wake_word_names=args.wake_word_name,
        vad=args.vad,
        awake_wav=awake_wav,
        done_wav=done_wav,
        no_zeroconf=args.no_zeroconf,
        debug=args.debug,
        extra_args=extra_args,
    )

    if args.print_command:
        print(shlex.join(satellite_args))
        return

    if args.install_service:
        if system == "Darwin":
            path = install_launchd(satellite_args)
            print(f"Wrote {path}")
            print(f"Enable with: launchctl load -w {path}")
        elif system == "Linux":
            path = install_systemd_user(satellite_args)
            print(f"Wrote {path}")
            print("Enable with:")
            print("  systemctl --user daemon-reload")
            print("  systemctl --user enable --now wyoming-satellite.service")
            print()
            print(
                "To keep it running when you are logged out: "
                "sudo loginctl enable-linger $USER"
            )
        else:
            raise SystemExit(
                f"--install-service is not supported on {system}. "
                "Use Task Scheduler with the command from --print-command."
            )

        return

    _LOGGER.info("Using %s backend", backend.name)
    _LOGGER.debug("Running: %s", shlex.join(satellite_args))

    # Replace this process so signals and exit codes reach the satellite
    # directly, with no wrapper in between for systemd to supervise.
    os.execv(satellite_args[0], satellite_args)


def run() -> None:
    """Console script entry point."""
    try:
        main()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
