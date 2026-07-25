from __future__ import annotations

import collections.abc
import json
import warnings

import pydantic
import pytest

from jira_ticket_mcp.adf import AdfConversionError, AdfDocument

LoadFixture = collections.abc.Callable[[str], str]

ROUNDTRIP_MARKDOWN = """## Release checklist

Restart is **mandatory** and *urgent* — run `systemctl restart` first.

```bash
kubectl rollout restart deploy/api
```

- Drain the connection pool

1. Verify the health endpoint

> Never skip the canary stage

[See the dashboard](https://grafana.example.com/d/api)
"""


def test_from_markdown_returns_doc_node() -> None:
    document = AdfDocument.from_markdown("# Title")
    assert document.root["type"] == "doc"
    assert "version" in document.root
    content = document.root["content"]
    assert isinstance(content, list)
    assert content


def test_to_markdown_reads_recorded_description(load_fixture: LoadFixture) -> None:
    document = AdfDocument.model_validate_json(load_fixture("adf_description.json"))
    assert "Deployment runbook" in document.to_markdown()


def test_roundtrip_preserves_every_convertible_construct() -> None:
    markdown = AdfDocument.from_markdown(ROUNDTRIP_MARKDOWN).to_markdown()
    assert "## Release checklist" in markdown
    assert "**mandatory**" in markdown
    assert "*urgent*" in markdown
    assert "`systemctl restart`" in markdown
    assert "kubectl rollout restart deploy/api" in markdown
    assert "```" in markdown
    assert "- Drain the connection pool" in markdown
    assert "1. Verify the health endpoint" in markdown
    assert "> Never skip the canary stage" in markdown
    assert "https://grafana.example.com/d/api" in markdown


@pytest.mark.parametrize("markdown", ["", "   \n  "])
def test_from_markdown_accepts_empty_input(markdown: str) -> None:
    document = AdfDocument.from_markdown(markdown)
    assert document.root["type"] == "doc"
    assert not document.to_markdown().strip()


@pytest.mark.parametrize("value", [{}, {"type": "not-a-doc"}])
def test_to_markdown_rejects_non_document(value: dict[str, pydantic.JsonValue]) -> None:
    with pytest.raises(AdfConversionError, match="doc"):
        AdfDocument(value).to_markdown()


def test_exotic_nodes_keep_their_text(load_fixture: LoadFixture) -> None:
    document = AdfDocument.model_validate_json(load_fixture("adf_exotic.json"))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        markdown = document.to_markdown()
    assert "PanelWarningText" in markdown
    assert "@MentionedPerson" in markdown
    assert "StatusInProgress" in markdown
    assert "TaskItemText" in markdown


def test_media_nodes_become_visible_placeholders(load_fixture: LoadFixture) -> None:
    document = AdfDocument.model_validate_json(load_fixture("adf_exotic.json"))
    markdown = document.to_markdown()
    assert "[attachment: MediaAltText]" in markdown


def test_media_only_description_is_not_empty() -> None:
    document = AdfDocument.model_validate({
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "mediaSingle",
                "content": [{"type": "media", "attrs": {"id": "abc", "type": "file"}}],
            }
        ],
    })
    assert document.to_markdown().strip() == "[attachment: abc]"


def test_media_substitution_does_not_mutate_the_document(
    load_fixture: LoadFixture,
) -> None:
    raw = json.loads(load_fixture("adf_exotic.json"))
    document = AdfDocument.model_validate(raw)
    document.to_markdown()
    assert document.model_dump() == raw


def test_document_serializes_back_to_the_raw_adf(load_fixture: LoadFixture) -> None:
    raw = json.loads(load_fixture("adf_description.json"))
    assert AdfDocument.model_validate(raw).model_dump() == raw
