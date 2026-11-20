from pathlib import Path

from alembic import command
from alembic.config import Config

from .config import ROOT


def upgrade(database_url: str, revision: str = "head") -> None:
    if database_url.startswith("sqlite:///") and not database_url.endswith(":memory:"):
        Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(ROOT / "migrations")))
    cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(cfg, revision)
