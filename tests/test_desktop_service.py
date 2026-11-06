"""Tests for desktop autostart units and satellite command composition."""

from pathlib import Path
from xml.etree import ElementTree

import pytest

from wyoming_satellite.desktop.__main__ import build_satellite_args
from wyoming_satellite.desktop.audio import PulseAudioBackend
from wyoming_satellite.desktop.service import (
    install_launchd,
    install_systemd_user,
    launchd_plist,
    systemd_user_unit,
)
from wyoming_satellite.utils import split_command

BACKEND = PulseAudioBackend()


def _value_of(args: list, flag: str) -> str:
    return args[args.index(flag) + 1]


def test_declared_mic_format_matches_the_mic_command() -> None:
    """The satellite trusts --mic-command-rate; a mismatch is silent corruption."""
    args = build_satellite_args(BACKEND, mic_rate=16000, python="python3")
    mic_command = split_command(_value_of(args, "--mic-command"))
    assert mic_command is not None

    assert _value_of(args, "--mic-command-rate") == "16000"
    assert "--rate=16000" in mic_command
    assert _value_of(args, "--mic-command-channels") == "1"
    assert "--channels=1" in mic_command
    assert _value_of(args, "--mic-command-width") == "2"


def test_declared_snd_format_matches_the_snd_command() -> None:
    args = build_satellite_args(BACKEND, snd_rate=22050, python="python3")
    snd_command = split_command(_value_of(args, "--snd-command"))
    assert snd_command is not None

    assert _value_of(args, "--snd-command-rate") == "22050"
    assert "--rate=22050" in snd_command


def test_non_default_rate_propagates_to_both_sides() -> None:
    args = build_satellite_args(BACKEND, mic_rate=48000, python="python3")
    mic_command = split_command(_value_of(args, "--mic-command"))
    assert mic_command is not None
    assert "--rate=48000" in mic_command
    assert _value_of(args, "--mic-command-rate") == "48000"


def test_invokes_the_satellite_module() -> None:
    args = build_satellite_args(BACKEND, python="python3")
    assert args[:3] == ["python3", "-m", "wyoming_satellite"]


def test_uri_and_name_defaults() -> None:
    args = build_satellite_args(BACKEND, python="python3")
    assert _value_of(args, "--uri") == "tcp://0.0.0.0:10700"
    # Falls back to the host name, which is never empty in the arg list.
    assert _value_of(args, "--name")


def test_wake_words_require_wake_uri() -> None:
    """--wake-word-name is meaningless to the satellite without --wake-uri."""
    args = build_satellite_args(BACKEND, wake_word_names=["ok_nabu"], python="python3")
    assert "--wake-word-name" not in args

    args = build_satellite_args(
        BACKEND,
        wake_uri="tcp://127.0.0.1:10400",
        wake_word_names=["ok_nabu", "hey_jarvis"],
        python="python3",
    )
    assert _value_of(args, "--wake-uri") == "tcp://127.0.0.1:10400"
    assert args.count("--wake-word-name") == 2


def test_optional_flags_are_omitted_at_defaults() -> None:
    """Noise suppression and gain need an optional extra, so 0 must not appear."""
    args = build_satellite_args(BACKEND, python="python3")
    for flag in (
        "--mic-noise-suppression",
        "--mic-auto-gain",
        "--mic-volume-multiplier",
        "--snd-volume-multiplier",
        "--vad",
        "--debug",
        "--no-zeroconf",
        "--area",
        "--awake-wav",
    ):
        assert flag not in args


def test_optional_flags_appear_when_set() -> None:
    args = build_satellite_args(
        BACKEND,
        area="Office",
        noise_suppression=2,
        auto_gain=5,
        mic_volume_multiplier=2.0,
        vad=True,
        no_zeroconf=True,
        debug=True,
        awake_wav=Path("/tmp/awake.wav"),
        done_wav=Path("/tmp/done.wav"),
        python="python3",
    )
    assert _value_of(args, "--area") == "Office"
    assert _value_of(args, "--mic-noise-suppression") == "2"
    assert _value_of(args, "--mic-auto-gain") == "5"
    assert _value_of(args, "--awake-wav") == "/tmp/awake.wav"
    assert _value_of(args, "--done-wav") == "/tmp/done.wav"
    assert "--vad" in args
    assert "--no-zeroconf" in args
    assert "--debug" in args


def test_extra_args_are_appended_last() -> None:
    args = build_satellite_args(
        BACKEND, extra_args=["--mic-channel-index", "1"], python="python3"
    )
    assert args[-2:] == ["--mic-channel-index", "1"]


def test_device_with_spaces_stays_one_argument() -> None:
    args = build_satellite_args(BACKEND, mic_device="My Input Device", python="python3")
    mic_command = split_command(_value_of(args, "--mic-command"))
    assert mic_command is not None
    assert "--device=My Input Device" in mic_command


def test_systemd_unit_is_user_scoped() -> None:
    """A system unit cannot reach the user's PipeWire/PulseAudio socket."""
    unit = systemd_user_unit(["/usr/bin/python3", "-m", "wyoming_satellite"])
    assert "WantedBy=default.target" in unit
    assert "multi-user.target" not in unit
    assert "User=" not in unit


def test_systemd_unit_does_not_hard_require_sound() -> None:
    """Requires= would take the satellite down with a sound server restart."""
    unit = systemd_user_unit(["/usr/bin/python3", "-m", "wyoming_satellite"])
    assert "After=" in unit
    assert "Requires=" not in unit


def test_systemd_unit_restarts() -> None:
    unit = systemd_user_unit(["/usr/bin/python3", "-m", "wyoming_satellite"])
    assert "Restart=always" in unit


def test_systemd_exec_start_is_quoted() -> None:
    unit = systemd_user_unit(["/usr/bin/python3", "--mic-command", "parecord --raw"])
    exec_line = next(
        line for line in unit.splitlines() if line.startswith("ExecStart=")
    )
    assert "'parecord --raw'" in exec_line


def test_systemd_unit_includes_working_dir() -> None:
    unit = systemd_user_unit(["/usr/bin/true"], working_dir=Path("/opt/sat"))
    assert "WorkingDirectory=/opt/sat" in unit


def test_empty_exec_args_rejected() -> None:
    with pytest.raises(ValueError):
        systemd_user_unit([])

    with pytest.raises(ValueError):
        launchd_plist([])


def test_launchd_plist_is_valid_xml() -> None:
    plist = launchd_plist(["/usr/bin/python3", "-m", "wyoming_satellite"])
    root = ElementTree.fromstring(plist)
    assert root.tag == "plist"


def test_launchd_plist_escapes_device_names() -> None:
    """A '&' in a sink name would otherwise produce invalid XML."""
    plist = launchd_plist(["/usr/bin/python3", "--snd-command", "play Mic & Speakers"])
    assert "&amp;" in plist

    root = ElementTree.fromstring(plist)
    strings = [el.text for el in root.iter("string")]
    assert "play Mic & Speakers" in strings


def test_launchd_plist_runs_at_load_and_keeps_alive() -> None:
    plist = launchd_plist(["/usr/bin/true"])
    root = ElementTree.fromstring(plist)
    keys = [el.text for el in root.iter("key")]
    assert "RunAtLoad" in keys
    assert "KeepAlive" in keys
    assert "ProgramArguments" in keys


def test_launchd_plist_preserves_argument_order() -> None:
    exec_args = ["/usr/bin/python3", "-m", "wyoming_satellite", "--uri", "tcp://x"]
    root = ElementTree.fromstring(launchd_plist(exec_args))
    array = root.find("./dict/array")
    assert array is not None
    assert [el.text for el in array] == exec_args


def test_install_systemd_user_writes_unit(tmp_path: Path) -> None:
    path = install_systemd_user(["/usr/bin/true"], unit_dir=tmp_path / "user")
    assert path.name == "wyoming-satellite.service"
    assert "ExecStart=/usr/bin/true" in path.read_text(encoding="utf-8")


def test_install_launchd_writes_plist(tmp_path: Path) -> None:
    path = install_launchd(["/usr/bin/true"], agents_dir=tmp_path / "agents")
    assert path.name == "io.wyoming.satellite.plist"
    ElementTree.fromstring(path.read_text(encoding="utf-8"))


def test_installed_unit_runs_the_real_command(tmp_path: Path) -> None:
    """The unit must carry the same command --print-command shows."""
    satellite_args = build_satellite_args(BACKEND, python="python3")
    path = install_systemd_user(satellite_args, unit_dir=tmp_path)
    unit = path.read_text(encoding="utf-8")
    assert "-m wyoming_satellite" in unit
    assert "parecord" in unit


def test_systemd_escapes_percent_specifier() -> None:
    """'%' is a systemd specifier; an unescaped one would be expanded away."""
    unit = systemd_user_unit(["/usr/bin/true", "--mic-device", "front:CARD=100%"])
    exec_line = next(
        line for line in unit.splitlines() if line.startswith("ExecStart=")
    )
    assert "100%%" in exec_line
    assert "100%'" not in exec_line
