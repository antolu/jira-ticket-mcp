from __future__ import annotations

import pytest

from jira_ticket_mcp import wiki


def test_headings_map_to_levels() -> None:
    assert wiki.markdown_to_wiki("# One") == "h1. One"
    assert wiki.markdown_to_wiki("### Three") == "h3. Three"


def test_inline_marks() -> None:
    result = wiki.markdown_to_wiki("**b** _i_ ~~s~~ `c`")
    assert result == "*b* _i_ -s- {{c}}"


def test_link_uses_pipe() -> None:
    assert wiki.markdown_to_wiki("[text](http://x)") == "[text|http://x]"


def test_unordered_list_nesting() -> None:
    markdown = "- a\n- b\n  - b1"
    assert wiki.markdown_to_wiki(markdown) == "* a\n* b\n** b1"


def test_ordered_list_marker() -> None:
    assert wiki.markdown_to_wiki("1. one\n2. two") == "# one\n# two"


def test_fenced_code_keeps_language() -> None:
    result = wiki.markdown_to_wiki("```py\nx = 1\n```")
    assert result == "{code:py}\nx = 1\n{code}"


def test_block_quote() -> None:
    assert wiki.markdown_to_wiki("> hi") == "{quote}\nhi\n{quote}"


def test_table() -> None:
    markdown = "| H1 | H2 |\n|----|----|\n| a | b |"
    assert wiki.markdown_to_wiki(markdown) == "||H1||H2||\n|a|b|"


def test_blocks_joined_with_blank_line() -> None:
    assert wiki.markdown_to_wiki("# T\n\npara") == "h1. T\n\npara"


def test_wiki_to_markdown_roundtrips_core_marks() -> None:
    result = wiki.wiki_to_markdown("h1. Title\n\n*bold* and _it_ and {{code}}")
    assert "# Title" in result
    assert "**bold**" in result
    assert "`code`" in result


def test_markdown_to_wiki_wraps_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(_markdown: str) -> object:
        msg = "nope"
        raise RuntimeError(msg)

    monkeypatch.setattr(wiki, "_PARSER", _boom)
    with pytest.raises(wiki.WikiConversionError):
        wiki.markdown_to_wiki("# x")
