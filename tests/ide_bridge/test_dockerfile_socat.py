"""
Test that the Dockerfile installs socat in the unconditional base apt-get layer.

PRD F3-AC1: every freshly built image must contain socat.
ADR-1: socat must be in the base layer, NOT behind the VOICE_ENABLED conditional.
"""

import re
from pathlib import Path

DOCKERFILE = Path(__file__).parent.parent.parent / "docker" / "Dockerfile"


def _read_dockerfile() -> str:
    return DOCKERFILE.read_text()


def _base_apt_block(content: str) -> str:
    """Extract the unconditional base apt-get install block."""
    match = re.search(
        r"(RUN apt-get update && apt-get install -y --no-install-recommends.*?&& rm -rf /var/lib/apt/lists/\*)",
        content,
        re.DOTALL,
    )
    assert match, "Could not find unconditional base apt-get install block in Dockerfile"
    return match.group(1)


def _voice_block(content: str) -> str:
    """Extract the VOICE_ENABLED conditional block."""
    match = re.search(
        r"(ARG VOICE_ENABLED=0\nRUN if \[ \"\$VOICE_ENABLED\".*?fi)",
        content,
        re.DOTALL,
    )
    assert match, "Could not find VOICE_ENABLED conditional block in Dockerfile"
    return match.group(1)


def test_socat_present_in_base_apt_block():
    """socat must appear in the unconditional base apt-get install block (PRD F3-AC1, ADR-1)."""
    content = _read_dockerfile()
    base_block = _base_apt_block(content)
    assert "socat" in base_block, (
        "socat is missing from the unconditional base apt-get install block. "
        "ADR-1 requires socat to be always present regardless of feature flags."
    )


def test_socat_not_in_voice_conditional_block():
    """socat must NOT be installed inside the VOICE_ENABLED conditional (ADR-1)."""
    content = _read_dockerfile()
    voice_block = _voice_block(content)
    assert "socat" not in voice_block, (
        "socat must not appear inside the VOICE_ENABLED conditional block. "
        "ADR-1: base layer only, not behind a conditional ARG."
    )


def test_base_apt_block_appears_before_voice_block():
    """The base apt-get block must come before the VOICE_ENABLED block (structural sanity)."""
    content = _read_dockerfile()
    base_match = re.search(
        r"RUN apt-get update && apt-get install -y --no-install-recommends",
        content,
    )
    voice_match = re.search(r"ARG VOICE_ENABLED=0", content)
    assert base_match and voice_match
    assert base_match.start() < voice_match.start(), (
        "Base apt-get block should appear before the VOICE_ENABLED block."
    )


def test_dockerfile_version_bumped():
    """Dockerfile version must be at least 0.4.0 after adding socat."""
    content = _read_dockerfile()
    match = re.search(r"# version: (\d+\.\d+\.\d+)", content)
    assert match, "Could not find '# version: X.Y.Z' in Dockerfile header"
    version = tuple(int(x) for x in match.group(1).split("."))
    assert version >= (0, 4, 0), (
        f"Dockerfile version {match.group(1)} is below 0.4.0. "
        "Version must be bumped to 0.4.0 when socat is added."
    )
