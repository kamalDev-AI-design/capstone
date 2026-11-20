import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "psit"


def imports(path: Path) -> set[str]:
    out = set()
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            out.add(n.module)
    return out


def test_domain_is_pure():
    for p in (SRC / "domain").rglob("*.py"):
        bad = {i for i in imports(p) if i.startswith(("psit", "sqlalchemy", "fastapi", "streamlit", "pydantic"))}
        assert not bad, (p, bad)


def test_only_ui_imports_streamlit():
    for p in SRC.rglob("*.py"):
        if "ui" in p.relative_to(SRC).parts[:1]:
            continue
        assert not {i for i in imports(p) if i.split(".")[0] == "streamlit"}, p


def test_ui_only_uses_contracts_and_http():
    for p in (SRC / "ui").rglob("*.py"):
        for i in imports(p):
            if i.startswith("psit."):
                assert i.startswith(("psit.contracts", "psit.ui")), (p, i)
            assert i.split(".")[0] not in {"sqlalchemy", "faiss", "alembic", "sqlite3"}, (p, i)
