"""Reject empty source files/directories and tests placed in application code."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = ("backend", "frontend/src", "frontend/tests", "docs", "scripts")
IGNORED_DIRECTORIES = {"__pycache__", ".pytest_cache", ".ruff_cache"}


def inspect(directory: Path) -> list[str]:
    entries = [p for p in directory.iterdir() if p.name not in IGNORED_DIRECTORIES]
    issues = [] if entries else [f"Empty directory: {directory.relative_to(ROOT)}"]
    for path in entries:
        if path.is_dir():
            issues.extend(inspect(path))
        elif not path.read_bytes().strip():
            issues.append(f"Empty file: {path.relative_to(ROOT)}")
        if (
            path.is_file()
            and (
                path.is_relative_to(ROOT / "frontend/src")
                or path.is_relative_to(ROOT / "backend/investor")
            )
            and (
                path.name.startswith("test_")
                or path.name.endswith(
                    (".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")
                )
            )
        ):
            issues.append(f"Test inside application code: {path.relative_to(ROOT)}")
    return issues


def main() -> None:
    issues = [issue for source in SOURCE_ROOTS for issue in inspect(ROOT / source)]
    if issues:
        raise SystemExit("\n".join(issues))
    print("Source structure: no empty files/directories or colocated tests.")


if __name__ == "__main__":
    main()
