from __future__ import annotations

import collections.abc

import jira2markdown
import mistune

_Node = collections.abc.Mapping[str, object]
_Nodes = collections.abc.Sequence[_Node]

_PARSER = mistune.create_markdown(renderer=None, plugins=["strikethrough", "table"])

_WRAP = {"strong": "*", "emphasis": "_", "strikethrough": "-"}


class WikiConversionError(Exception):
    pass


def _children(node: _Node) -> list[_Node]:
    kids = node.get("children")
    if isinstance(kids, list):
        return [child for child in kids if isinstance(child, collections.abc.Mapping)]
    return []


def _raw(node: _Node) -> str:
    value = node.get("raw")
    return value if isinstance(value, str) else ""


def _attr(node: _Node, key: str) -> object:
    attrs = node.get("attrs")
    return attrs.get(key) if isinstance(attrs, collections.abc.Mapping) else None


def _attr_str(node: _Node, key: str) -> str:
    value = _attr(node, key)
    return value if isinstance(value, str) else ""


def _inline(nodes: _Nodes) -> str:
    return "".join(_inline_node(node) for node in nodes)


def _inline_node(node: _Node) -> str:
    node_type = str(node.get("type"))
    if node_type in _WRAP:
        mark = _WRAP[node_type]
        return f"{mark}{_inline(_children(node))}{mark}"
    handler = _INLINE.get(node_type)
    return handler(node) if handler else _inline(_children(node))


_INLINE: dict[str, collections.abc.Callable[[_Node], str]] = {
    "text": _raw,
    "codespan": lambda node: "{{" + _raw(node) + "}}",
    "link": lambda node: (
        "[" + _inline(_children(node)) + "|" + _attr_str(node, "url") + "]"
    ),
    "image": lambda node: "!" + _attr_str(node, "url") + "!",
    "linebreak": lambda node: "\n",
    "softbreak": lambda node: " ",
}


def _heading(token: _Node) -> str:
    level = _attr(token, "level")
    level_int = level if isinstance(level, int) else 1
    return f"h{level_int}. " + _inline(_children(token))


def _paragraph(token: _Node) -> str:
    return _inline(_children(token))


def _block_code(token: _Node) -> str:
    info = _attr_str(token, "info").split()
    lang = info[0] if info else ""
    raw = _raw(token).rstrip("\n")
    header = f"{{code:{lang}}}" if lang else "{code}"
    return f"{header}\n{raw}\n{{code}}"


def _block_quote(token: _Node) -> str:
    inner = "\n".join(_block(child) for child in _children(token))
    return f"{{quote}}\n{inner}\n{{quote}}"


def _thematic_break(_token: _Node) -> str:
    return "----"


def _list_lines(token: _Node) -> list[str]:
    ordered = _attr(token, "ordered") is True
    depth = _attr(token, "depth")
    depth_int = depth if isinstance(depth, int) else 0
    marker = ("#" if ordered else "*") * (depth_int + 1)
    lines: list[str] = []
    for item in _children(token):
        text: list[str] = []
        nested: list[str] = []
        for child in _children(item):
            if child.get("type") == "list":
                nested.extend(_list_lines(child))
            elif child.get("type") in {"block_text", "paragraph"}:
                text.append(_inline(_children(child)))
            else:
                nested.append(_block(child))
        lines.append(f"{marker} {' '.join(text)}")
        lines.extend(nested)
    return lines


def _list(token: _Node) -> str:
    return "\n".join(_list_lines(token))


def _table(token: _Node) -> str:
    lines: list[str] = []
    for section in _children(token):
        if section.get("type") == "table_head":
            cells = [_inline(_children(cell)) for cell in _children(section)]
            lines.append("||" + "||".join(cells) + "||")
        elif section.get("type") == "table_body":
            for row in _children(section):
                cells = [_inline(_children(cell)) for cell in _children(row)]
                lines.append("|" + "|".join(cells) + "|")
    return "\n".join(lines)


_BLOCK: dict[str, collections.abc.Callable[[_Node], str]] = {
    "heading": _heading,
    "paragraph": _paragraph,
    "block_code": _block_code,
    "block_quote": _block_quote,
    "thematic_break": _thematic_break,
    "list": _list,
    "table": _table,
}


def _block(token: _Node) -> str:
    handler = _BLOCK.get(str(token.get("type")))
    return handler(token) if handler else _inline(_children(token))


def markdown_to_wiki(markdown: str) -> str:
    try:
        tokens = _PARSER(markdown)
        if not isinstance(tokens, list):
            return ""
        blocks = [
            _block(token)
            for token in tokens
            if isinstance(token, collections.abc.Mapping)
            and token.get("type") != "blank_line"
        ]
        return "\n\n".join(block for block in blocks if block)
    except Exception as exc:
        msg = f"could not convert markdown to wiki markup: {exc}"
        raise WikiConversionError(msg) from exc


def wiki_to_markdown(wiki: str) -> str:
    try:
        return jira2markdown.convert(wiki)
    except Exception as exc:
        msg = f"could not convert wiki markup to markdown: {exc}"
        raise WikiConversionError(msg) from exc
