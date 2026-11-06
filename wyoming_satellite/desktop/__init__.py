"""Desktop support for the Wyoming satellite.

Runs the satellite against an ordinary desktop sound server (PipeWire,
PulseAudio, ALSA, CoreAudio, DirectShow) instead of Raspberry Pi audio
hardware. See `python -m wyoming_satellite.desktop --help`.
"""

from .audio import (
    BACKENDS,
    BACKENDS_BY_NAME,
    AlsaBackend,
    AudioBackend,
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
from .service import (
    install_launchd,
    install_systemd_user,
    launchd_plist,
    systemd_user_unit,
)

__all__ = [
    "AlsaBackend",
    "AudioBackend",
    "AudioFormat",
    "AvFoundationBackend",
    "BACKENDS",
    "BACKENDS_BY_NAME",
    "DirectShowBackend",
    "PipeWireBackend",
    "PulseAudioBackend",
    "SoxBackend",
    "UnsupportedFormatError",
    "backends_for_platform",
    "detect_backend",
    "get_backend",
    "install_launchd",
    "install_systemd_user",
    "launchd_plist",
    "systemd_user_unit",
]
