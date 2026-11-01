"""The instance shows the host's local time (#202).

The container got no time zone and ran on UTC, and the note-facing timestamps
were built from UTC directly. These tests run the real code under a fixed TZ.
Machine timestamps stay UTC and are asserted to.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "tomo" / "scripts"
TEMPLATE = REPO / "scripts" / "lib" / "begin-tomo.sh.template"
DOCKERFILE = REPO / "docker" / "Dockerfile"
TOKYO = "Asia/Tokyo"  # UTC+9, no daylight saving: a stable offset for assertions


def _helper() -> str:
    text = TEMPLATE.read_text(encoding="utf-8")
    return text[text.index("_zone_from_localtime_link() {") : text.index("HOST_TZ=")]


def _resolve(tz, link: str) -> str:
    env = {k: v for k, v in os.environ.items() if k != "TZ"}
    if tz is not None:
        env["TZ"] = tz
    script = _helper() + f'_host_timezone "{link}"\n'
    return subprocess.run(
        ["/bin/bash", "-c", script], env=env, capture_output=True, text=True, check=True
    ).stdout


@pytest.mark.parametrize(
    "tz,link,expected",
    [
        (None, "/var/db/timezone/zoneinfo/Europe/Berlin", "Europe/Berlin"),
        (None, "/usr/share/zoneinfo/America/New_York", "America/New_York"),
        ("Asia/Tokyo", "/usr/share/zoneinfo/Europe/Berlin", "Asia/Tokyo"),
        (":/etc/localtime", "/usr/share/zoneinfo/Europe/Berlin", "Europe/Berlin"),
        ("", "/usr/share/zoneinfo/Europe/Berlin", "Europe/Berlin"),
        (None, "", "UTC"),
        (None, "/etc/some-file", "UTC"),
    ],
)
def test_host_timezone_resolution(tz, link, expected):
    assert _resolve(tz, link) == expected


def test_launcher_passes_the_zone_into_the_container():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert '-e "TZ=$HOST_TZ" \\' in text[text.index("docker run -it --rm") :]


def test_image_carries_zone_data_and_old_images_rebuild():
    assert re.search(r"^\s+tzdata \\$", DOCKERFILE.read_text(encoding="utf-8"), re.M)
    text = TEMPLATE.read_text(encoding="utf-8")
    assert '--label "tomo.has_tzdata=1"' in text
    assert 'elif [ -z "$_IMAGE_TZDATA_STATE" ]; then' in text


def _python(code: str, *argv: str, cwd=None) -> str:
    env = {**os.environ, "TZ": TOKYO, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, "-c", code, *argv], env=env, cwd=cwd,
        capture_output=True, text=True, check=True,
    ).stdout


LOAD = (
    "import importlib.util, sys\n"
    f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
    "def load(name):\n"
    f"    spec = importlib.util.spec_from_file_location('m', {str(SCRIPTS)!r} + '/' + name)\n"
    "    mod = importlib.util.module_from_spec(spec)\n"
    "    spec.loader.exec_module(mod)\n"
    "    return mod\n"
)


def test_note_tokens_use_local_time_and_date_iso_stays_utc():
    out = _python(
        LOAD
        + "from datetime import datetime, timezone\nimport json\n"
        + "t = load('token-render.py')\n"
        + "print(json.dumps(t.resolve_generated_tokens("
        + "datetime(2026, 11, 1, 20, 30, 15, tzinfo=timezone.utc))))\n"
    )
    assert json.loads(out) == {
        "uuid": "20261102053015",
        "datestamp": "2026-11-02",
        "updated": "2026-11-02 05:30",
        "date_iso": "2026-11-01T20:30:15Z",
    }


def test_upload_name_is_local_time():
    out = _python(
        LOAD + "print(load('upload-rendered.py')._derive_timestamp('2026-11-01T20:30:15Z'))\n"
    )
    assert out.strip() == "2026-11-02_0530"


def test_render_stamps_local_prefix_and_keeps_generated_in_utc(tmp_path):
    (tmp_path / "parsed.json").write_text(
        json.dumps({"confirmed_items": [], "skipped": [{"stem": "x", "reason": "kept"}],
                    "daily_updates": [], "generated": "2026-10-24T00:00:00Z"}),
        encoding="utf-8",
    )
    env = {**os.environ, "TZ": TOKYO, "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run(
        [sys.executable, str(SCRIPTS / "instruction-render.py"), "--suggestions", "parsed.json",
         "--output-dir", "out", "--run-id", "x"],
        cwd=tmp_path, env=env, capture_output=True, text=True, check=True,
    )
    doc = json.loads((tmp_path / "out" / "instructions.json").read_text(encoding="utf-8"))
    assert doc["generated"].endswith("Z")
    uploaded = _python(
        LOAD + "print(load('upload-rendered.py')._derive_timestamp(sys.argv[1]))\n",
        doc["generated"],
    ).strip()
    # The .json names its .md peer; upload must write that exact name.
    assert doc["md_peer"] == f"{uploaded}_instructions"
