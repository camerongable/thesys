"""Bounded parsers for untrusted evidence files."""

from __future__ import annotations

import multiprocessing
from dataclasses import dataclass

from app.core.config import Settings
from app.services import pdf_parser_worker


class PDFParserError(RuntimeError):
    pass


class PDFSecurityError(PDFParserError):
    pass


class PDFResourceLimitError(PDFParserError):
    pass


@dataclass(frozen=True)
class PDFExtraction:
    page_texts: list[str]


def extract_pdf(settings: Settings, *, body: bytes) -> PDFExtraction:
    """Inspect and extract a PDF outside the API process with bounded resources."""
    context = multiprocessing.get_context("spawn")
    parent_connection, child_connection = context.Pipe(duplex=False)
    process = context.Process(
        target=pdf_parser_worker.extract_pdf_in_worker,
        args=(
            child_connection,
            body,
            settings.max_pdf_pages,
            settings.max_extracted_text_chars,
            settings.pdf_extraction_memory_mb,
            settings.max_pdf_decompression_ratio,
        ),
    )
    process.start()
    child_connection.close()
    try:
        if not parent_connection.poll(settings.pdf_extraction_timeout_seconds):
            process.terminate()
            process.join()
            raise PDFResourceLimitError("PDF extraction exceeded the configured timeout.")
        try:
            result = parent_connection.recv()
        except EOFError as exc:
            raise PDFParserError("PDF parser worker exited unexpectedly.") from exc
    finally:
        parent_connection.close()
        process.join(timeout=0.1)
        if process.is_alive():
            process.terminate()
            process.join()

    kind = result.get("kind")
    if kind == "ok":
        return PDFExtraction(page_texts=result["page_texts"])
    if kind == "security":
        raise PDFSecurityError(result["reason"])
    if kind == "resource":
        raise PDFResourceLimitError(result["reason"])
    raise PDFParserError("PDF could not be parsed safely.")
