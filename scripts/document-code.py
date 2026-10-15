"""Build the searchable source-file responsibility index; optionally add missing headers.

Usage: python scripts/document-code.py [--add-headers]
Existing explanations and generated files are preserved. Review semantic comments when
changing a workflow; this catalog is navigation, not a replacement for design review.
"""

from __future__ import annotations

import ast
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {
    "node_modules",
    ".git",
    ".venv",
    ".next",
    ".turbo",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".trustlens-calls",
    ".trustlens-setup-lock",
    "dist",
    "build",
    "backups",
    "transfer-backups",
    ".trustlens-update-backups",
    ".trustlens-update-lock",
    "security-evidence",
}
CODE = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sh", ".sql"}


def files():
    """Walk source paths without following dependency symlinks or private configuration."""
    import os

    for directory, children, names in os.walk(ROOT):
        children[:] = sorted(
            name
            for name in children
            if name not in EXCLUDED and not Path(directory, name).is_symlink()
        )
        for name in sorted(names):
            path = Path(directory, name)
            if (
                name == ".trustlens-local-project"
                or path.is_symlink()
                or name.endswith((".pyc", ".tsbuildinfo"))
            ):
                continue
            if name.startswith(".env") and not name.endswith(".example"):
                continue
            yield path


def purpose(path: Path, source: str = "") -> str:
    """Infer module ownership from established layers; preserve author descriptions first."""
    rel = path.relative_to(ROOT).as_posix()
    if path.suffix == ".py":
        try:
            tree = ast.parse(source)
            doc = ast.get_docstring(tree)
            if doc:
                return doc.split("\n")[0].strip()
        except SyntaxError:
            pass
    header = re.match(r"\s*(?:[\'\"]use client[\'\"];\s*)?/\*\*?\s*([^\n*]+)", source)
    if header:
        return header.group(1).strip().rstrip("*/").strip()
    label = path.stem.replace("_", " ").replace("-", " ")
    if "schema.gen." in rel or rel == "docs/api/openapi.json":
        return "Generated API contract; regenerate from the API schema."
    if "/tests/" in rel or ".test." in rel or rel.startswith("testing/"):
        return f"Regression coverage and test support for {label}."
    if "database/migrations/versions/" in rel:
        return f"Ordered schema/data migration: {label}; preserve revision history."
    if "/domain/" in rel:
        return f"Framework-independent business definitions and rules for {label}."
    if "/application/" in rel:
        return f"Application use cases or port contracts for {label}."
    if "/repositories/" in rel:
        return f"Database query and persistence adapter for {label}."
    if "/models/" in rel:
        return f"Persistent model declarations for {label}."
    if "/routers/" in rel:
        return f"HTTP endpoints and authorization/dependency wiring for {label}."
    if "/schemas/" in rel:
        return f"Validated request/response contracts for {label}."
    if "/hooks/" in rel:
        return f"Feature state, queries or side-effect coordination for {label}."
    if "/components/" in rel or "/ui/src/" in rel:
        return f"Reusable UI rendering and interaction component: {label}."
    if "/app/" in rel:
        route = rel.split("/app/", 1)[1].rsplit("/", 1)[0]
        return f"Next.js route/layout composition for {route or 'the app root'}: {label}."
    if rel.startswith("apps/worker/"):
        return f"Background worker processing and recovery support for {label}."
    if rel.startswith("apps/ml/"):
        return f"Offline training/evaluation tooling for {label}; not runtime application code."
    if rel.startswith(("scripts/", "tools/")):
        return f"Operator/developer automation for {label}."
    if rel.startswith("docker/"):
        return f"Container setup, startup or infrastructure configuration for {label}."
    if "/public/" in rel:
        return f"Browser-served asset or worker resource: {path.name}."
    if path.suffix in {".md", ".pdf"}:
        return f"Project documentation: {label}."
    if path.suffix in {".json", ".yaml", ".yml", ".toml", ".ini"} or path.name.endswith(".example"):
        return f"Declarative configuration or data contract: {path.name}."
    if path.name.endswith(".lock") or path.name == "pnpm-lock.yaml":
        return "Pinned dependency resolution for repeatable installations."
    exports = re.findall(
        r"(?:export\s+(?:async\s+)?(?:function|class|interface|type|const)|def|class)\s+(\w+)",
        source,
    )
    names = ", ".join(dict.fromkeys(exports[:6]))
    return f"{label.capitalize()} module" + (
        f"; defines {names}." if names else f" in {path.parent.name}."
    )


def main():
    """Add only missing module headers, then write a deterministic Markdown index."""
    rows = []
    changed = 0
    for path in files():
        rel = path.relative_to(ROOT).as_posix()
        if rel == "docs/FILE_MAP.md":
            continue
        try:
            source = path.read_text(encoding="utf-8") if path.suffix in CODE else ""
        except UnicodeError:
            source = ""
        description = purpose(path, source)
        if "--add-headers" in sys.argv and source and ".gen." not in rel:
            comment = None
            if path.suffix == ".py" and not ast.get_docstring(ast.parse(source)):
                comment = '"""' + description.replace('"""', "") + '"""\n'
            elif path.suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"} and not re.search(
                r"/\*|//", source[:240]
            ):
                comment = "/** " + description.replace("*/", "") + " */\n"
            if comment:
                if source.startswith("#!"):
                    first, rest = source.split("\n", 1)
                    source = first + "\n" + comment + rest
                else:
                    source = comment + source
                path.write_text(source)
                changed += 1
        rows.append((rel, description.replace("|", "\\|").replace("\n", " ")))
    content = "# File responsibility index\n\nGenerated by `python scripts/document-code.py`. Lists source, configuration, documentation and shipped assets; excludes dependencies, caches, private config and runtime data. Module headers explain ownership; function comments explain important behavior. Generated contracts and JSON are documented here without adding unsupported comments.\n\n"
    content += f"Indexed files: **{len(rows)}**.\n\n| File | Purpose |\n| --- | --- |\n"
    content += "".join(f"| `{name}` | {description} |\n" for name, description in sorted(rows))
    (ROOT / "docs/FILE_MAP.md").write_text(content)
    print(f"FILE_INDEX={len(rows)}; MISSING_HEADERS_ADDED={changed}")


if __name__ == "__main__":
    main()
