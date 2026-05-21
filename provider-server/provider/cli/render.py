from collections.abc import Mapping, Sequence
from typing import Any

from rich.console import Console
from rich.table import Table

from .admin_client import dump_json

console = Console()


def output(value: Any, *, json_out: bool = False, title: str | None = None) -> None:
    if json_out:
        console.print(dump_json(value))
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        print_table(list(value), title=title)
        return
    if isinstance(value, Mapping):
        print_mapping(value, title=title)
        return
    console.print(str(value))


def print_mapping(value: Mapping[str, Any], *, title: str | None = None) -> None:
    table = Table(title=title, show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    for key, item in value.items():
        table.add_row(str(key), _format_value(item))
    console.print(table)


def print_table(rows: list[Any], *, title: str | None = None) -> None:
    table = Table(title=title)
    if not rows:
        console.print(title or "No records.")
        return
    normalized = [_flatten_row(row) for row in rows]
    keys = list(normalized[0].keys())
    for row in normalized[1:]:
        for key in row.keys():
            if key not in keys:
                keys.append(key)
    for key in keys:
        table.add_column(str(key))
    for row in normalized:
        table.add_row(*[_format_value(row.get(key)) for key in keys])
    console.print(table)


def _flatten_row(row: Any) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    return {"value": row}


def _format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, Mapping):
        short = []
        for key, item in value.items():
            if isinstance(item, (Mapping, list, tuple)):
                continue
            short.append(f"{key}={item}")
        return ", ".join(short) if short else "{...}"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return f"{len(value)} item(s)"
    return str(value)
