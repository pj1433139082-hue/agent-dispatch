from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_install_mirrors_and_drops_stale_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    build = tmp_path / "dist" / "agent-dispatch-skill"
    (build / "scripts").mkdir(parents=True)
    (build / "SKILL.md").write_text("v2", encoding="utf-8")
    (build / "scripts" / "dispatch.py").write_text("print(1)", encoding="utf-8")

    target = tmp_path / "skills"
    installed = target / "agent-dispatch"
    (installed / "__pycache__").mkdir(parents=True)
    (installed / "stale.txt").write_text("old", encoding="utf-8")

    # 用真实的脚本，但把 ROOT 指到临时目录
    source = (ROOT / "scripts" / "install_skill.py").read_text(encoding="utf-8")
    source = source.replace('ROOT = Path(__file__).resolve().parents[1]', f'ROOT = Path(r"{tmp_path}")')
    script = tmp_path / "install_skill.py"
    script.write_text(source, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script), "--target", str(target)],
        text=True, capture_output=True, check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (installed / "SKILL.md").read_text(encoding="utf-8") == "v2"
    assert not (installed / "stale.txt").exists()
    assert not (installed / "__pycache__").exists()
