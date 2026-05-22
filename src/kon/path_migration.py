"""
Temporary legacy path migration for Kon's move away from ~/.kon.

TODO(migration): Remove this module and all ~/.kon fallback behavior after users have had
at least one release cycle to migrate to ~/.config/kon for Kon state/config and ~/.agents
for shared agent resources.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PathMigrationState:
    config_dir: Path
    legacy_config_dir: Path
    agents_dir: Path
    used_legacy_config: bool = False
    warnings: list[str] = field(default_factory=list)


_STATE: PathMigrationState | None = None


CONFIG_FILES = [
    "config.toml",
    "openai_auth.json",
    "copilot_auth.json",
    "prompt-history.jsonl",
]
CONFIG_DIRS = ["sessions", "bin"]


def legacy_config_dir() -> Path:
    return Path.home() / ".kon"


def preferred_config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "kon"
    return Path.home() / ".config" / "kon"


def agents_dir() -> Path:
    return Path.home() / ".agents"


def _merge_copy(src: Path, dst: Path) -> None:
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.iterdir():
            _merge_copy(child, dst / child.name)
        return
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _remove_if_empty(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        pass


def _migrate_legacy_paths(new_config: Path, old_config: Path, new_agents: Path) -> list[str]:
    warnings: list[str] = []
    moved_any = False

    for name in CONFIG_FILES:
        src = old_config / name
        if src.exists():
            _merge_copy(src, new_config / name)
            src.unlink()
            moved_any = True

    for name in CONFIG_DIRS:
        src = old_config / name
        if src.exists():
            _merge_copy(src, new_config / name)
            shutil.rmtree(src)
            moved_any = True

    old_skills = old_config / "skills"
    if old_skills.exists():
        _merge_copy(old_skills, new_agents / "skills")
        shutil.rmtree(old_skills)
        moved_any = True

    if moved_any:
        _remove_if_empty(old_config)
        if old_config.exists():
            warnings.append(
                "Kon successfully migrated legacy user data from ~/.kon to ~/.config/kon and ~/.agents, "
                "but ~/.kon still contains files Kon did not remove. Migration succeeded; you can remove ~/.kon manually "
                "after reviewing anything left there."
            )
        else:
            warnings.append(
                "Kon migrated legacy user data from ~/.kon to ~/.config/kon and ~/.agents. "
                "The old ~/.kon user location was removed; future versions will only use the new locations."
            )

    return warnings


def get_path_state() -> PathMigrationState:
    global _STATE
    if _STATE is not None:
        return _STATE

    new_config = preferred_config_dir()
    old_config = legacy_config_dir()
    new_agents = agents_dir()
    warnings: list[str] = []
    used_legacy = False

    if not new_config.exists() and old_config.exists():
        try:
            warnings.extend(_migrate_legacy_paths(new_config, old_config, new_agents))
        except Exception as exc:
            used_legacy = True
            warnings.append(
                f"Kon could not migrate legacy ~/.kon data to ~/.config/kon and ~/.agents: {exc}. "
                "Continuing with legacy ~/.kon paths for this session."
            )
    elif new_config.exists() and old_config.exists():
        warnings.append(
            "Kon is using the migrated ~/.config/kon and ~/.agents locations, but legacy ~/.kon still exists. "
            "Migration appears complete; you can remove ~/.kon manually after reviewing anything left there."
        )

    _STATE = PathMigrationState(
        config_dir=old_config if used_legacy else new_config,
        legacy_config_dir=old_config,
        agents_dir=new_agents,
        used_legacy_config=used_legacy,
        warnings=warnings,
    )
    return _STATE


def consume_path_migration_warnings() -> list[str]:
    state = get_path_state()
    warnings = state.warnings.copy()
    state.warnings.clear()
    return warnings


def reset_path_state() -> None:
    global _STATE
    _STATE = None
