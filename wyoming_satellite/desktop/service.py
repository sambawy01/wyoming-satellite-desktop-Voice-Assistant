"""Autostart units for a desktop satellite.

The Pi installer writes **system** units (`/etc/systemd/system`). That is
wrong on a desktop: PulseAudio and PipeWire expose per-user sockets under
`$XDG_RUNTIME_DIR`, so a system service runs as the wrong user with no sound
server to talk to. Everything here is therefore user-scoped --
`~/.config/systemd/user` on Linux, a LaunchAgent on macOS -- and needs no
root.
"""

import shlex
from pathlib import Path
from typing import List, Optional
from xml.sax.saxutils import escape

SYSTEMD_USER_DIR = Path("~/.config/systemd/user").expanduser()
LAUNCH_AGENTS_DIR = Path("~/Library/LaunchAgents").expanduser()

SERVICE_NAME = "wyoming-satellite"
LAUNCHD_LABEL = "io.wyoming.satellite"


def systemd_user_unit(
    exec_args: List[str],
    description: str = "Wyoming satellite (desktop)",
    working_dir: Optional[Path] = None,
) -> str:
    """Render a systemd **user** unit that runs the satellite."""
    if not exec_args:
        raise ValueError("exec_args must not be empty")

    lines = [
        "[Unit]",
        f"Description={description}",
        # Ordering only: the sound server is socket-activated, and a hard
        # Requires= would take the satellite down with it on a restart.
        "After=pipewire.service pulseaudio.service sound.target",
        "",
        "[Service]",
        "Type=simple",
        # systemd honours shell-style quoting in ExecStart, but '%' is a
        # specifier it expands itself, so it has to be doubled. An ALSA PCM
        # name or a PulseAudio sink can contain one.
        f"ExecStart={shlex.join(exec_args).replace('%', '%%')}",
    ]

    if working_dir is not None:
        lines.append(f"WorkingDirectory={working_dir}")

    lines.extend(
        [
            "Restart=always",
            "RestartSec=3",
            "",
            "[Install]",
            # default.target, not multi-user.target: this is a user unit.
            "WantedBy=default.target",
            "",
        ]
    )

    return "\n".join(lines)


def launchd_plist(
    exec_args: List[str],
    label: str = LAUNCHD_LABEL,
    working_dir: Optional[Path] = None,
    log_path: Optional[Path] = None,
) -> str:
    """Render a macOS LaunchAgent plist that runs the satellite."""
    if not exec_args:
        raise ValueError("exec_args must not be empty")

    # Device names and paths reach the plist verbatim, so they are escaped:
    # one '&' in a sink name would otherwise produce invalid XML.
    args_xml = "\n".join(f"\t\t<string>{escape(arg)}</string>" for arg in exec_args)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
        '<plist version="1.0">',
        "<dict>",
        "\t<key>Label</key>",
        f"\t<string>{escape(label)}</string>",
        "\t<key>ProgramArguments</key>",
        "\t<array>",
        args_xml,
        "\t</array>",
        "\t<key>RunAtLoad</key>",
        "\t<true/>",
        "\t<key>KeepAlive</key>",
        "\t<true/>",
    ]

    if working_dir is not None:
        lines.extend(
            [
                "\t<key>WorkingDirectory</key>",
                f"\t<string>{escape(str(working_dir))}</string>",
            ]
        )

    if log_path is not None:
        lines.extend(
            [
                "\t<key>StandardOutPath</key>",
                f"\t<string>{escape(str(log_path))}</string>",
                "\t<key>StandardErrorPath</key>",
                f"\t<string>{escape(str(log_path))}</string>",
            ]
        )

    lines.extend(["</dict>", "</plist>", ""])
    return "\n".join(lines)


def install_systemd_user(
    exec_args: List[str],
    service_name: str = SERVICE_NAME,
    unit_dir: Path = SYSTEMD_USER_DIR,
    working_dir: Optional[Path] = None,
) -> Path:
    """Write the user unit and return its path (does not enable it)."""
    unit_dir.mkdir(parents=True, exist_ok=True)
    unit_path = unit_dir / f"{service_name}.service"
    unit_path.write_text(
        systemd_user_unit(exec_args, working_dir=working_dir), encoding="utf-8"
    )
    return unit_path


def install_launchd(
    exec_args: List[str],
    label: str = LAUNCHD_LABEL,
    agents_dir: Path = LAUNCH_AGENTS_DIR,
    working_dir: Optional[Path] = None,
    log_path: Optional[Path] = None,
) -> Path:
    """Write the LaunchAgent plist and return its path (does not load it)."""
    agents_dir.mkdir(parents=True, exist_ok=True)
    plist_path = agents_dir / f"{label}.plist"
    plist_path.write_text(
        launchd_plist(
            exec_args, label=label, working_dir=working_dir, log_path=log_path
        ),
        encoding="utf-8",
    )
    return plist_path
