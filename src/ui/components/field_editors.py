from __future__ import annotations

from typing import Any, Iterable


def _parse_tokens(path: str) -> Iterable[str]:
    token = ""
    for ch in path:
        if ch == ".":
            if token:
                yield token
                token = ""
        else:
            token += ch
    if token:
        yield token


def set_deep(data: Any, path: str, value: Any) -> Any:
    """Set a dotted field path inside nested dict/list structures."""
    tokens = list(_parse_tokens(path))
    if not tokens:
        return data
    cursor = data
    for idx, token in enumerate(tokens):
        is_last = idx == len(tokens) - 1
        if token.endswith("]") and "[" in token:
            name, idx_str = token[:-1].split("[")
            index = int(idx_str)
            cursor = cursor.setdefault(name, [])
            while len(cursor) <= index:
                cursor.append({})
            if is_last:
                cursor[index] = value
            else:
                cursor = cursor[index]
        else:
            if is_last:
                if isinstance(cursor, dict):
                    cursor[token] = value
                else:
                    setattr(cursor, token, value)
            else:
                if isinstance(cursor, dict):
                    cursor = cursor.setdefault(token, {})
                else:
                    cursor = getattr(cursor, token)
    return data


def diff_dict(original: dict, updated: dict) -> dict:
    diff = {}
    for key, val in updated.items():
        if key not in original:
            diff[key] = {"old": None, "new": val}
        else:
            if isinstance(val, dict) and isinstance(original[key], dict):
                nested = diff_dict(original[key], val)
                if nested:
                    diff[key] = nested
            elif val != original[key]:
                diff[key] = {"old": original[key], "new": val}
    for key in original:
        if key not in updated:
            diff[key] = {"old": original[key], "new": None}
    return diff


__all__ = ["set_deep", "diff_dict"]
