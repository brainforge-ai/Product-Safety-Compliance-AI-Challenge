from pathlib import Path

from app.domain.forbidden_list.repository import ForbiddenListRepository


def test_loads_real_sample_forbidden_list(fixtures_dir: Path) -> None:
    repo = ForbiddenListRepository.from_csv(fixtures_dir / "forbidden_ingredients.csv")

    entries = repo.get_all()

    assert len(entries) == 13
    assert "Coumarin" in entries
    assert "1,4-Dioxane" in entries  # quoted, comma-bearing CSV value


def test_replace_swaps_the_in_memory_list() -> None:
    repo = ForbiddenListRepository(["A", "B"])

    repo.replace(["C", "D", "E"])

    assert repo.get_all() == ["C", "D", "E"]


def test_get_all_returns_a_copy_not_the_internal_list() -> None:
    repo = ForbiddenListRepository(["A"])

    entries = repo.get_all()
    entries.append("B")

    assert repo.get_all() == ["A"]


def test_empty_csv_produces_empty_list(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("ingredient\n", encoding="utf-8")

    repo = ForbiddenListRepository.from_csv(path)

    assert repo.get_all() == []
