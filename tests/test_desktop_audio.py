"""Tests for desktop audio backend command generation."""

import pytest

from wyoming_satellite.desktop.audio import (
    MIC_FORMAT,
    SND_FORMAT,
    AlsaBackend,
    AudioFormat,
    AvFoundationBackend,
    DirectShowBackend,
    PipeWireBackend,
    PulseAudioBackend,
    SoxBackend,
    UnsupportedFormatError,
    backends_for_platform,
    detect_backend,
    get_backend,
)
from wyoming_satellite.utils import split_command


def test_pulseaudio_passes_raw_explicitly() -> None:
    """parecord/paplay default to file-format mode, so --raw must be present.

    Without it the satellite reads a WAV header as audio.
    """
    backend = PulseAudioBackend()
    assert "--raw" in backend.record_args(MIC_FORMAT)
    assert "--raw" in backend.play_args(SND_FORMAT)


def test_pipewire_passes_raw_explicitly() -> None:
    """pw-record/pw-play to stdout wrap the stream in an AU container."""
    backend = PipeWireBackend()
    assert "--raw" in backend.record_args(MIC_FORMAT)
    assert "--raw" in backend.play_args(SND_FORMAT)


def test_pipewire_streams_to_stdout() -> None:
    backend = PipeWireBackend()
    assert backend.record_args(MIC_FORMAT)[-1] == "-"
    assert backend.play_args(SND_FORMAT)[-1] == "-"


def test_pulseaudio_format_and_rate() -> None:
    args = PulseAudioBackend().record_args(MIC_FORMAT)
    assert args[0] == "parecord"
    assert "--rate=16000" in args
    assert "--channels=1" in args
    assert "--format=s16le" in args


def test_pipewire_format_and_rate() -> None:
    args = PipeWireBackend().play_args(SND_FORMAT)
    assert args[0] == "pw-play"
    assert "--rate=22050" in args
    assert "--format=s16" in args


def test_alsa_raw_format() -> None:
    args = AlsaBackend().record_args(MIC_FORMAT)
    assert args[0] == "arecord"
    assert args[args.index("-t") + 1] == "raw"
    assert args[args.index("-f") + 1] == "S16_LE"
    assert args[args.index("-r") + 1] == "16000"


def test_device_is_passed_per_backend() -> None:
    assert "--target=alsa_input.usb" in PipeWireBackend().record_args(
        MIC_FORMAT, "alsa_input.usb"
    )
    assert "--device=my-source" in PulseAudioBackend().record_args(
        MIC_FORMAT, "my-source"
    )

    alsa_args = AlsaBackend().record_args(MIC_FORMAT, "plughw:CARD=USB,DEV=0")
    assert alsa_args[alsa_args.index("-D") + 1] == "plughw:CARD=USB,DEV=0"


def test_no_device_means_no_device_flag() -> None:
    args = PulseAudioBackend().record_args(MIC_FORMAT)
    assert not any(arg.startswith("--device") for arg in args)


@pytest.mark.parametrize(
    "backend",
    [PipeWireBackend(), PulseAudioBackend(), AlsaBackend(), SoxBackend()],
)
def test_non_16_bit_is_rejected(backend: object) -> None:
    """A backend must refuse a width it cannot express, not silently emit s16."""
    fmt = AudioFormat(rate=16000, width=4, channels=1)
    with pytest.raises(UnsupportedFormatError):
        backend.record_args(fmt)  # type: ignore[attr-defined]


def test_invalid_format_values_rejected() -> None:
    with pytest.raises(UnsupportedFormatError):
        AudioFormat(rate=0, width=2, channels=1)

    with pytest.raises(UnsupportedFormatError):
        AudioFormat(rate=16000, width=2, channels=0)


def test_sox_rejects_a_device() -> None:
    """SoX has no device flag; it must say so rather than ignore the request."""
    with pytest.raises(UnsupportedFormatError):
        SoxBackend().record_args(MIC_FORMAT, "some-device")


def test_sox_bit_depth_follows_width() -> None:
    args = SoxBackend().record_args(MIC_FORMAT)
    assert args[args.index("-b") + 1] == "16"


def test_avfoundation_audio_only_input() -> None:
    """avfoundation inputs are 'video:audio'; audio-only needs the empty half."""
    args = AvFoundationBackend().record_args(MIC_FORMAT)
    assert args[args.index("-i") + 1] == ":0"

    args = AvFoundationBackend().record_args(MIC_FORMAT, "2")
    assert args[args.index("-i") + 1] == ":2"


def test_dshow_requires_a_device() -> None:
    """DirectShow has no default capture device."""
    with pytest.raises(UnsupportedFormatError):
        DirectShowBackend().record_args(MIC_FORMAT)

    args = DirectShowBackend().record_args(MIC_FORMAT, "Microphone (USB)")
    assert args[args.index("-i") + 1] == "audio=Microphone (USB)"


def test_ffplay_playback_rejects_a_device() -> None:
    with pytest.raises(UnsupportedFormatError):
        AvFoundationBackend().play_args(SND_FORMAT, "out")


def test_ffmpeg_emits_raw_s16le() -> None:
    args = AvFoundationBackend().record_args(MIC_FORMAT)
    assert args[args.index("-f", args.index("-i")) + 1] == "s16le"
    assert args[-1] == "-"


@pytest.mark.parametrize(
    "backend",
    [
        PipeWireBackend(),
        PulseAudioBackend(),
        AlsaBackend(),
        SoxBackend(),
        AvFoundationBackend(),
    ],
)
def test_command_survives_the_satellites_own_parser(backend: object) -> None:
    """The satellite re-parses --mic-command with shlex, so quoting must hold.

    'Microphone (USB)' and 'plughw:CARD=USB,DEV=0' both contain characters
    that would split wrongly if the command were joined with spaces.
    """
    args = backend.record_args(MIC_FORMAT)  # type: ignore[attr-defined]
    command = backend.record_command(MIC_FORMAT)  # type: ignore[attr-defined]
    assert split_command(command) == args


def test_quoted_device_survives_round_trip() -> None:
    device = "Microphone (USB Audio Device)"
    backend = DirectShowBackend()
    command = backend.record_command(MIC_FORMAT, device)
    assert split_command(command) == backend.record_args(MIC_FORMAT, device)


def test_backends_for_platform_filters() -> None:
    linux = {b.name for b in backends_for_platform("Linux")}
    assert {"pipewire", "pulseaudio", "alsa", "sox"} <= linux
    assert "dshow" not in linux
    assert "avfoundation" not in linux

    darwin = {b.name for b in backends_for_platform("Darwin")}
    assert {"sox", "avfoundation"} <= darwin
    assert "pipewire" not in darwin

    windows = {b.name for b in backends_for_platform("Windows")}
    assert windows == {"dshow"}


def test_linux_prefers_shared_access_over_alsa() -> None:
    """ALSA grabs the device exclusively, so it must be the last resort."""
    names = [b.name for b in backends_for_platform("Linux")]
    assert names.index("pipewire") < names.index("alsa")
    assert names.index("pulseaudio") < names.index("alsa")


def test_detect_backend_picks_first_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    installed = {"parecord", "paplay"}
    monkeypatch.setattr(
        "wyoming_satellite.desktop.audio.shutil.which",
        lambda program: f"/usr/bin/{program}" if program in installed else None,
    )

    backend = detect_backend("Linux")
    assert backend is not None
    assert backend.name == "pulseaudio"


def test_detect_backend_skips_half_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """pw-record without pw-play is not a usable backend."""
    installed = {"pw-record", "arecord", "aplay"}
    monkeypatch.setattr(
        "wyoming_satellite.desktop.audio.shutil.which",
        lambda program: f"/usr/bin/{program}" if program in installed else None,
    )

    backend = detect_backend("Linux")
    assert backend is not None
    assert backend.name == "alsa"


def test_detect_backend_none_when_nothing_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "wyoming_satellite.desktop.audio.shutil.which", lambda program: None
    )
    assert detect_backend("Linux") is None


def test_get_backend_unknown_name_lists_options() -> None:
    with pytest.raises(KeyError) as excinfo:
        get_backend("coreaudio")

    assert "pulseaudio" in str(excinfo.value)
