from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable
import os
import secrets


@dataclass(frozen=True)
class TokenTemplate:
    key: str
    display: str
    default_filename: str
    make_bytes: Callable[[], bytes]


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _rand(n: int) -> bytes:
    return os.urandom(n)


def _sprinkle(blob: bytes, markers: list[bytes]) -> bytes:
    """
    Inject a few ASCII-ish markers into random spots so `strings` output
    looks plausibly relevant, while the file remains effectively unreadable/corrupt.
    """
    b = bytearray(blob)
    if len(b) < 64:
        return bytes(b)

    for m in markers:
        if len(m) >= len(b) - 1:
            continue
        off = secrets.randbelow(len(b) - len(m) - 1)
        b[off : off + len(m)] = m
    return bytes(b)


def _make_corrupt_pdf_invoice() -> bytes:
    # PDF signature + garbage + EOF marker (intentionally missing valid xref structure)
    head = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
    body = _rand(4096)
    body = _sprinkle(
        body,
        [
            b"/Producer (Acme Scan Service)\n",
            b"/Title (AP Invoices Q4)\n",
            b"/Author (Accounts Payable)\n",
            b"obj\n",
            b"stream\n",
            b"endstream\n",
        ],
    )
    tail = b"\n%%EOF\n"
    return head + body + tail


def _make_corrupt_xlsx_payroll() -> bytes:
    """
    XLSX files are ZIP containers. We include the ZIP local-file signature (PK..)
    so it looks right, but keep it invalid so unzip/Office recovery fails.
    """
    # ZIP local file header signature
    head = b"PK\x03\x04" + _rand(26)  # bogus header fields
    body = _rand(8192)
    body = _sprinkle(
        body,
        [
            b"[Content_Types].xml",
            b"xl/workbook.xml",
            b"xl/worksheets/sheet1.xml",
            b"Payroll",
            b"EmployeeID",
            b"Salary",
            b"Finance",
        ],
    )
    return head + body


def _make_corrupt_sqlite_cache() -> bytes:
    """
    SQLite magic header then junk pages.
    Many tools will still identify it as SQLite, but sqlite3 will refuse to open it.
    """
    head = b"SQLite format 3\x00"
    body = _rand(4096 * 2)
    body = _sprinkle(
        body,
        [
            b"token_cache",
            b"api_clients",
            b"updated_at",
            b"last_used_ip",
            b"redacted",
        ],
    )
    return head + body


TEMPLATES: list[TokenTemplate] = [
    TokenTemplate(
        key="corrupt_pdf_invoice",
        display="Invoice scans (PDF, corrupted)",
        default_filename=f"AP_Invoices_Q4_{_today()}.pdf",
        make_bytes=_make_corrupt_pdf_invoice,
    ),
    TokenTemplate(
        key="corrupt_xlsx_payroll",
        display="Payroll export (XLSX, corrupted)",
        default_filename=f"Payroll_Export_{_today()}.xlsx",
        make_bytes=_make_corrupt_xlsx_payroll,
    ),
    TokenTemplate(
        key="corrupt_sqlite_cache",
        display="Auth cache (SQLite, corrupted)",
        default_filename=f"auth_cache_{_today()}.sqlite",
        make_bytes=_make_corrupt_sqlite_cache,
    ),
]


def template_by_key(key: str) -> TokenTemplate:
    for t in TEMPLATES:
        if t.key == key:
            return t
    raise KeyError(key)

