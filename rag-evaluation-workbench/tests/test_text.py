import pytest

from rag_workbench.text import (
    content_tokens,
    is_abstention,
    normalize_whitespace,
    split_sentences,
    squad_normalize,
    stem,
    tokenize,
)


@pytest.mark.parametrize("word,expected", [
    ("workers", "worker"), ("colonies", "colony"), ("boxes", "box"), ("grass", "grass"),
    ("status", "status"), ("analysis", "analysis"), ("sea", "sea"), ("2024", "2024"), ("feathers", "feather"),
])
def test_stem(word, expected):
    assert stem(word) == expected


def test_tokenize_is_unicode_aware():
    assert tokenize("Abejas RÉINE 蜜蜂!") == ["abejas", "réine", "蜜蜂"]


def test_content_tokens_drop_stopwords_and_stem():
    assert content_tokens("What do the workers build?") == ["worker", "build"]


def test_squad_normalize_matches_reference_behaviour():
    assert squad_normalize("The  Queen's diet: ROYAL, jelly!") == "queens diet royal jelly"


def test_normalize_whitespace_collapses_newlines():
    assert normalize_whitespace(" a\nb\r\n\tc  ") == "a b c"


def test_split_sentences():
    assert split_sentences("Bees fly. They make honey! Do they sleep? Yes.") == [
        "Bees fly.", "They make honey!", "Do they sleep?", "Yes."]
    assert split_sentences("") == []
    assert split_sentences("e.g. lowercase continues here.") == ["e.g. lowercase continues here."]


@pytest.mark.parametrize("answer,expected", [
    ("The PDF does not provide enough information to answer the question.", True),
    ("There is not enough information in the document.", True),
    ("This cannot be answered from the context.", True),
    ("Bees make honey.", False),
])
def test_is_abstention(answer, expected):
    assert is_abstention(answer) is expected


def test_squad_normalize_drops_unicode_punctuation():
    assert squad_normalize("The queen’s diet — “jelly”…") == "queens diet jelly"
    assert squad_normalize("colony’s cells — mostly") == squad_normalize("colony's cells - mostly")
