import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: real environment variables win; blank values are ignored."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        if v:
            os.environ.setdefault(k.strip(), v)


_load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv("PSIT_DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'psit.db'}"))
    auto_migrate: bool = field(default_factory=lambda: os.getenv("PSIT_AUTO_MIGRATE", "1") == "1")
    model_profile: str = field(default_factory=lambda: os.getenv("PSIT_MODEL_PROFILE", "fast"))
    index_dir: str = field(default_factory=lambda: os.getenv("PSIT_INDEX_DIR", str(ROOT / "data" / "index")))
    rerank_threshold: float | None = field(
        default_factory=lambda: float(os.environ["PSIT_RERANK_THRESHOLD"]) if os.getenv("PSIT_RERANK_THRESHOLD") else None)
    app_version: str = "0.1.0"


def get_settings() -> Settings:
    return Settings()
