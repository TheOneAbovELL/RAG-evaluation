import json

import pytest
from conftest import REAL_DATASET

from rag_workbench.datasets import DatasetError, load_dataset, parse_dataset, validate_file


def jsonl(*rows) -> bytes:
    return "\n".join(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False) for r in rows).encode("utf-8")


def test_real_dataset_is_valid():
    report = validate_file(REAL_DATASET)
    assert report.ok
    assert len(report.cases) == 20
    assert report.n_with_reference == 20
    assert report.cases[0].id == "q01"
    assert report.cases[0].question == "How many queens does a typical honeybee colony have?"


def test_ids_metadata_and_optional_reference():
    report = parse_dataset(jsonl({"id": 7, "question": "Q?", "metadata": {"topic": "drones"}},
                                 {"question": "R?", "expected_answer": "  "}), "d.jsonl")
    assert report.ok
    assert [c.id for c in report.cases] == ["7", "case-002"]
    assert report.cases[0].metadata == {"topic": "drones"}
    assert report.cases[1].expected_answer is None  # blank reference treated as missing
    assert any("no expected_answer" in str(w) for w in report.warnings)


def test_blank_lines_ignored_and_bom_accepted():
    data = b"\xef\xbb\xbf" + jsonl({"question": "Q?", "expected_answer": "A"}, "", "   ")
    report = parse_dataset(data, "d.jsonl")
    assert report.ok and len(report.cases) == 1


@pytest.mark.parametrize("rows,fragment", [
    (["{not json"], "invalid JSON"),
    (["[1, 2]"], "expected a JSON object"),
    ([{"expected_answer": "A"}], "missing or empty 'question'"),
    ([{"question": "   "}], "missing or empty 'question'"),
    ([{"question": "Q", "expected_answer": 3}], "'expected_answer' must be a string"),
    ([{"question": "Q", "metadata": [1]}], "'metadata' must be a JSON object"),
    ([{"question": "Q", "id": [1]}], "'id' must be a string or integer"),
    ([{"id": "a", "question": "Q1"}, {"id": "a", "question": "Q2"}], "duplicate id 'a'"),
])
def test_errors_are_reported_with_line_numbers(rows, fragment):
    report = parse_dataset(jsonl(*rows), "d.jsonl")
    assert not report.ok
    assert any(fragment in str(e) for e in report.errors), report.errors
    assert all(e.line for e in report.errors if "duplicate" in e.message or "JSON" in e.message)


def test_duplicate_questions_are_warnings_not_errors():
    report = parse_dataset(jsonl({"question": "Where?"}, {"question": "  where? "}), "d.jsonl")
    assert report.ok
    assert any("duplicate question" in str(w) for w in report.warnings)


def test_empty_dataset_is_an_error():
    report = parse_dataset(b"\n\n", "d.jsonl")
    assert not report.ok
    assert "no cases" in str(report.errors[0])


def test_limits():
    assert "limit" in str(parse_dataset(b"x" * 101, "d.jsonl", max_bytes=100).errors[0])
    many = jsonl(*({"question": f"Q{i}"} for i in range(5)))
    assert any("exceeds the limit of 3" in str(e) for e in parse_dataset(many, "d.jsonl", max_cases=3).errors)
    long = jsonl({"question": "Q" * 50})
    assert any("limit is 10" in str(e) for e in parse_dataset(long, "d.jsonl", max_field_chars=10).errors)


def test_non_utf8_and_unsupported_type():
    assert "not valid UTF-8" in str(parse_dataset(b"\xff\xfe\x00", "d.jsonl").errors[0])
    assert "unsupported file type" in str(parse_dataset(b"{}", "d.txt").errors[0])


def test_non_ascii_round_trip():
    report = parse_dataset(jsonl({"question": "Où vivent les abeilles ?", "expected_answer": "蜂巢"}), "d.jsonl")
    assert report.cases[0].question == "Où vivent les abeilles ?"
    assert report.cases[0].expected_answer == "蜂巢"


def test_csv_format_with_extra_columns_as_metadata():
    data = b"id,question,expected_answer,topic\nx1,What do drones do?,They mate,drones\nx2,Where?,,habitat\n"
    report = parse_dataset(data, "d.csv")
    assert report.ok
    assert report.cases[0].metadata == {"topic": "drones"}
    assert report.cases[1].expected_answer is None


def test_csv_requires_question_column():
    report = parse_dataset(b"query,answer\nQ,A\n", "d.csv")
    assert "must include a 'question' column" in str(report.errors[0])


def test_load_dataset_raises_with_summary(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"question": ""}\n', encoding="utf-8")
    with pytest.raises(DatasetError, match="missing or empty"):
        load_dataset(path)
    with pytest.raises(DatasetError, match="file not found"):
        load_dataset(tmp_path / "missing.jsonl")
