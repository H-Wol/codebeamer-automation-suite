from __future__ import annotations

import ast
from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"


class ImportBoundaryTest(unittest.TestCase):
    def test_source_modules_do_not_use_star_imports(self) -> None:
        violations: list[str] = []

        for source_path in SOURCE_ROOT.rglob("*.py"):
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
                    relative_path = source_path.relative_to(REPOSITORY_ROOT)
                    violations.append(f"{relative_path}:{node.lineno}")

        self.assertEqual(violations, [])

    def test_dependency_bag_modules_are_removed(self) -> None:
        removed_modules = [
            SOURCE_ROOT / "mapping_support.py",
            SOURCE_ROOT / "wizard_support.py",
        ]

        self.assertEqual(
            [path.relative_to(REPOSITORY_ROOT) for path in removed_modules if path.exists()],
            [],
        )


if __name__ == "__main__":
    unittest.main()
