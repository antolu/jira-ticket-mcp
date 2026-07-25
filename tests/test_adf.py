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


def test_media_nodes_are_dropped_but_not_silently(load_fixture: LoadFixture) -> None:
    document = AdfDocument.model_validate_json(load_fixture("adf_exotic.json"))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        markdown = document.to_markdown()
    assert "MediaAltText" not in markdown
    assert any("mediaSingle" in str(item.message) for item in caught)


def test_document_serializes_back_to_the_raw_adf(load_fixture: LoadFixture) -> None:
    raw = json.loads(load_fixture("adf_description.json"))
    assert AdfDocument.model_validate(raw).model_dump() == raw
