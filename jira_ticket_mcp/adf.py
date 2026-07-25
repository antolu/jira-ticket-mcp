from __future__ import annotations

import marklas
import pyadf
import pydantic

_DOC_TYPE = "doc"
_MEDIA_TYPES = frozenset({"media", "mediaSingle", "mediaGroup", "mediaInline"})
_MEDIA_LABEL_KEYS = ("alt", "id")


class AdfConversionError(Exception):
    pass


def _media_label(node: pydantic.JsonValue) -> str | None:
    if isinstance(node, list):
        return next(filter(None, map(_media_label, node)), None)
    if not isinstance(node, dict):
        return None
    attrs = node.get("attrs")
    if isinstance(attrs, dict):
        for key in _MEDIA_LABEL_KEYS:
            value = attrs.get(key)
            if isinstance(value, str) and value:
                return value
    return _media_label(node.get("content"))


def _substitute_media(node: pydantic.JsonValue) -> pydantic.JsonValue:
    if isinstance(node, list):
        return [_substitute_media(item) for item in node]
    if not isinstance(node, dict):
        return node
    if node.get("type") in _MEDIA_TYPES:
        label = _media_label(node)
        text = f"[attachment: {label}]" if label else "[attachment]"
        return {"type": "paragraph", "content": [{"type": "text", "text": text}]}
    if "content" in node:
        return {**node, "content": _substitute_media(node["content"])}
    return node


class AdfDocument(pydantic.RootModel[dict[str, pydantic.JsonValue]]):
    @classmethod
    def from_markdown(cls, markdown: str) -> AdfDocument:
        try:
            return cls(marklas.to_adf(markdown))
        except RecursionError as exc:
            msg = "markdown nesting too deep to convert"
            raise AdfConversionError(msg) from exc
        except Exception as exc:
            msg = f"could not convert markdown to ADF: {exc}"
            raise AdfConversionError(msg) from exc

    def to_markdown(self) -> str:
        node_type = self.root.get("type")
        if node_type != _DOC_TYPE:
            msg = f"expected an ADF node of type {_DOC_TYPE!r}, got {node_type!r}"
            raise AdfConversionError(msg)
        readable = _substitute_media(self.root)
        try:
            return pyadf.Document(readable).to_markdown()
        except RecursionError as exc:
            msg = "ADF nesting too deep to convert"
            raise AdfConversionError(msg) from exc
        except Exception as exc:
            msg = f"could not convert ADF to markdown: {exc}"
            raise AdfConversionError(msg) from exc
