from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class Run:
    number: int
    date: date
    base_dir: Path = field(default_factory=lambda: Path("runs"))

    @property
    def id(self) -> str:
        return f"{self.number:04d}"

    @property
    def name(self) -> str:
        return f"{self.id}-{self.date.isoformat()}"

    @property
    def folder(self) -> Path:
        return self.base_dir / self.name

    @property
    def proposal_path(self) -> Path:
        return self.folder / "proposal.yaml"

    @property
    def plan_path(self) -> Path:
        return self.folder / "plan.yaml"

    @property
    def applied_path(self) -> Path:
        return self.folder / "applied.yaml"


def create_run(base_dir: Path) -> Run:
    base_dir.mkdir(parents=True, exist_ok=True)
    existing = list_runs(base_dir)
    number = max((r.number for r in existing), default=0) + 1
    run = Run(number=number, date=date.today(), base_dir=base_dir)
    run.folder.mkdir(parents=True, exist_ok=True)
    return run


def list_runs(base_dir: Path) -> list["Run"]:
    if not base_dir.exists():
        return []
    runs = [
        r
        for folder in sorted(base_dir.iterdir())
        if folder.is_dir() and not folder.name.startswith(".")
        for r in [_parse_folder(folder.name, base_dir)]
        if r is not None
    ]
    return sorted(runs, key=lambda r: r.number)


def resolve_run(identifier: str, base_dir: Path) -> Run:
    runs = list_runs(base_dir)
    if not runs:
        raise FileNotFoundError("No runs found. Start with: yt-org analyze")

    for run in runs:
        if run.name == identifier:
            return run

    try:
        number = int(identifier)
        for run in runs:
            if run.number == number:
                return run
    except ValueError:
        pass

    available = ", ".join(r.id for r in runs)
    raise FileNotFoundError(
        f"Run {identifier!r} not found. Available: {available}"
    )


def _parse_folder(name: str, base_dir: Path) -> Run | None:
    # Expected format: 0001-2026-05-22
    try:
        num_str, date_str = name.split("-", 1)
        return Run(number=int(num_str), date=date.fromisoformat(date_str), base_dir=base_dir)
    except (ValueError, AttributeError):
        return None
