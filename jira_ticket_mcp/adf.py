from __future__ import annotations

import marklas
import pyadf
import pydantic

_DOC_TYPE = "doc"


class AdfConversionError(Exception):
    pass


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
        try:
            return pyadf.Document(self.root).to_markdown()
        except RecursionError as exc:
            msg = "ADF nesting too deep to convert"
            raise AdfConversionError(msg) from exc
        except Exception as exc:
            msg = f"could not convert ADF to markdown: {exc}"
            raise AdfConversionError(msg) from exc
