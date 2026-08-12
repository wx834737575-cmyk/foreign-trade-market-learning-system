from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(project_root: Path, *, daily: bool = False) -> Path | None:
    root = project_root.resolve()
    data_dir = (root / "data").resolve()
    if data_dir.parent != root:
        raise ValueError("数据目录校验失败")
    database = data_dir / "decision_system.db"
    if not database.exists():
        return None
    backup_dir = data_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    if daily:
        existing = sorted(backup_dir.glob(f"{now:%Y-%m-%d}_*.zip"))
        if existing:
            return existing[-1]
    output = backup_dir / f"{now:%Y-%m-%d_%H%M%S}_decision-system.zip"

    with tempfile.TemporaryDirectory(prefix="ftds-backup-") as temp_name:
        snapshot = Path(temp_name) / "decision_system.db"
        with closing(sqlite3.connect(database)) as source, closing(sqlite3.connect(snapshot)) as target:
            source.backup(target)
        files: list[tuple[Path, str]] = [(snapshot, "database/decision_system.db")]
        raw_dir = data_dir / "raw"
        if raw_dir.exists():
            files.extend((path, path.relative_to(data_dir).as_posix()) for path in raw_dir.rglob("*") if path.is_file())
        manifest = {
            "createdAt": now.isoformat(timespec="seconds"),
            "project": "外贸与投资决策系统",
            "files": [{"path": archive_name, "sha256": _sha256(path)} for path, archive_name in files],
        }
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path, archive_name in files:
                archive.write(path, archive_name)
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return output


if __name__ == "__main__":
    result = create_backup(Path(__file__).resolve().parents[1])
    print(result or "数据库尚未创建，无需备份")
