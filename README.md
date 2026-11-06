# wyoming-satellite

[![CI](https://github.com/florian-asche/wyoming-satellite/actions/workflows/docker-build-release.yml/badge.svg)](https://github.com/florian-asche/wyoming-satellite/actions/workflows/docker-build-release.yml) [![GitHub Package Version](https://img.shields.io/github/v/tag/florian-asche/wyoming-satellite?label=version)](https://github.com/florian-asche/wyoming-satellite/pkgs/container/wyoming-satellite) [![GitHub License](https://img.shields.io/github/license/florian-asche/wyoming-satellite)](https://github.com/florian-asche/wyoming-satellite/blob/main/LICENSE.md) [![GitHub last commit](https://img.shields.io/github/last-commit/florian-asche/wyoming-satellite)](https://github.com/florian-asche/wyoming-satellite/commits) [![GitHub Container Registry](https://img.shields.io/badge/Container%20Registry-GHCR-blue)](https://github.com/florian-asche/wyoming-satellite/pkgs/container/wyoming-satellite)

Remote voice satellite using the [Wyoming protocol](https://github.com/rhasspy/wyoming).

## Features

- Works with [Home Assistant](https://www.home-assistant.io/integrations/wyoming)
- Runs as a **desktop voice assistant** on Linux, macOS or Windows, using the computer's own microphone and speakers (PipeWire, PulseAudio, ALSA, CoreAudio, DirectShow) - see [tutorial_desktop.md](docs/tutorial_desktop.md)
- Local wake word detection using [Wyoming services](https://github.com/rhasspy/wyoming#wyoming-projects) like for example openwakeword.
- Audio enhancements using [webrtc](https://github.com/rhasspy/webrtc-noise-gain/)
- Voice activity detection using [pysilero-vad]
- Pre-built Docker image for Wyoming Satellite
- Supports multiple architectures (linux/amd64 and linux/aarch64)
- Automated builds with artifact attestation for security
- Easy integration with voice assistants

This repository also provides a Docker image for [Wyoming Satellite](https://github.com/rhasspy/wyoming-satellite), a voice assistant service that can be used with various voice assistants. The image is designed to be easily integrated into your home automation setup.

## Usage

### Hardware

You can use for example the Raspberry Pi Zero 2W with the Respeaker Lite or the Respeaker 2Mic_Hat.

For more specific information about what hardware, you can look here: [piCompose: hardware.md](https://github.com/florian-asche/PiCompose/blob/main/docs/hardware.md)

No dedicated hardware is required if you just want to run this on a computer you already have: see [tutorial_desktop.md](docs/tutorial_desktop.md).

### Software

#### Run it on a desktop (no special hardware):

See [tutorial_desktop.md](docs/tutorial_desktop.md)

```sh
python3 script/setup --vad --noisegain
script/run_desktop --list-backends
script/run_desktop --wake-uri tcp://127.0.0.1:10400 --wake-word-name ok_nabu
```

#### Use a prebuild Raspberry Pi Image with Docker:

See [tutorial_docker.md](docs/tutorial_docker.md)

#### Use installer on selfinstalled hardware (old method):

See [tutorial_installer.md](docs/tutorial_installer.md) and [tutorial_2mic.md](docs/tutorial_2mic.md)

Video tutorials:

* [Wyoming Voice Satellite with ChatGPT](https://www.youtube.com/watch?v=eTKgc0YDCwE)
* [Local ChatGPT Voice Assistant](https://www.youtube.com/watch?v=pAKqKTkx5X4)

## Build Information

Image builds can be tracked in this repository's `Actions` tab, and utilize [artifact attestation](https://docs.github.com/en/actions/security-guides/using-artifact-attestations-to-establish-provenance-for-builds) to certify provenance.

The Docker images are built using GitHub Actions, which provides:

- Automated builds for different architectures
- Artifact attestation for build provenance verification
- Regular updates and maintenance
