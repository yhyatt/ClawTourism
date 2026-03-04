"""PdfExtractor — extracts structured travel data from PDF attachments.

PREFERRED PATH (agent context):
    Use OpenClaw's native `pdf` tool directly — it routes to the model
    (Anthropic/Google native PDF support) and returns structured extraction
    far more accurately than regex on raw text.

    Example agent call:
        pdf(
            pdf="path/to/8FL7BG.pdf",
            prompt=PDF_EXTRACTION_PROMPT,
        )

FALLBACK PATH (Python-only / no agent context):
    PdfExtractor class uses pypdf for raw text extraction,
    then passes text to extractor.py regex parsers.

Booking confirmations we handle:
- El Al: 8FL7BG.pdf (booking confirmation)
- Club Med: CTR-Voucher_*.pdf (French + Hebrew voucher)
- MSC: e-ticket PDFs
- Generic boarding passes
"""

from __future__ import annotations

import base64
import io
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clawtourism.scanner import EmailAttachment


# ── Prompt for native PDF tool ────────────────────────────────────────────────

PDF_EXTRACTION_PROMPT = """
Extract all travel booking details from this PDF. Return a JSON object with these fields
(use null for any field not found):

{
  "booking_ref": "string — PNR / booking reference / confirmation number",
  "type": "flight | hotel | cruise | car | transfer | package",
  "passengers": [{"name": "string", "seat": "string|null", "meal": "string|null"}],
  "flights": [{
    "flight_number": "string",
    "origin": "IATA code",
    "destination": "IATA code",
    "departure_date": "YYYY-MM-DD",
    "departure_time": "HH:MM",
    "arrival_date": "YYYY-MM-DD",
    "arrival_time": "HH:MM",
    "class": "economy|business|first"
  }],
  "hotel": {
    "name": "string",
    "address": "string",
    "check_in": "YYYY-MM-DD",
    "check_out": "YYYY-MM-DD",
    "room_type": "string"
  },
  "cruise": {
    "ship": "string",
    "line": "string",
    "embarkation_port": "string",
    "embarkation_date": "YYYY-MM-DD",
    "disembarkation_port": "string",
    "disembarkation_date": "YYYY-MM-DD",
    "cabin": "string"
  },
  "total_price": "string",
  "currency": "string",
  "notes": "any other important info"
}

Return ONLY the JSON, no explanation.
""".strip()


# ── Native PDF tool wrapper (for use inside agent turns) ─────────────────────

def extract_with_native_tool(pdf_path: str) -> dict:
    """
    Placeholder documenting the preferred extraction path.

    In agent context, call the `pdf` tool directly:
        result = pdf(pdf=pdf_path, prompt=PDF_EXTRACTION_PROMPT)

    Then parse result as JSON and pass to store.py.
    This function is NOT called by Python code — it exists for documentation.
    """
    raise NotImplementedError(
        "Use the OpenClaw `pdf` tool from agent context instead of calling this directly. "
        "See PDF_EXTRACTION_PROMPT above for the prompt to use."
    )


# ── Fallback: pure-Python extraction (no model) ───────────────────────────────

@dataclass
class PdfContent:
    """Extracted content from a PDF (raw text, fallback path)."""
    filename: str
    text: str
    pages: int
    is_travel_document: bool


class PdfExtractor:
    """
    Fallback PDF text extractor for non-agent contexts (e.g. batch scanner).

    For structured data extraction in agent turns, use the native `pdf` tool
    with PDF_EXTRACTION_PROMPT instead — it's significantly more accurate.
    """

    TRAVEL_KEYWORDS = [
        "booking", "reservation", "confirmation", "itinerary",
        "e-ticket", "eticket", "ticket", "voucher",
        "flight", "departure", "arrival", "passenger", "pnr", "boarding",
        "check-in", "check-out", "hotel", "accommodation", "guest",
        "cruise", "cabin", "embark", "disembark", "port",
        "הזמנה", "טיסה", "נוסע", "מלון", "אישור",
        "réservation", "vol", "passager", "hébergement",
    ]

    def extract_text_from_bytes(self, pdf_bytes: bytes, filename: str = "") -> PdfContent:
        """Extract raw text from PDF bytes using pypdf."""
        text = ""
        pages = 0

        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(pdf_bytes))
            pages = len(reader.pages)
            text = "\n\n".join(
                p.extract_text() for p in reader.pages if p.extract_text()
            )
        except Exception:
            pass

        return PdfContent(
            filename=filename,
            text=text,
            pages=pages,
            is_travel_document=self._is_travel_document(text, filename),
        )

    def extract_text_from_base64(self, b64_data: str, filename: str = "") -> PdfContent:
        """Extract text from base64-encoded PDF."""
        if b64_data.startswith("data:"):
            _, b64_data = b64_data.split(",", 1)
        return self.extract_text_from_bytes(base64.b64decode(b64_data), filename)

    def extract_from_attachment(self, attachment: "EmailAttachment") -> PdfContent | None:
        """Extract text from an EmailAttachment if it's a PDF."""
        if not attachment.filename.lower().endswith(".pdf") or not attachment.data:
            return None
        return self.extract_text_from_bytes(attachment.data, attachment.filename)

    def _is_travel_document(self, text: str, filename: str) -> bool:
        combined = (text + " " + filename).lower()
        return sum(1 for kw in self.TRAVEL_KEYWORDS if kw.lower() in combined) >= 2

    def extract_booking_ref_from_filename(self, filename: str) -> str | None:
        match = re.match(r"^([A-Z0-9]{5,8})\.pdf$", filename, re.IGNORECASE)
        return match.group(1).upper() if match else None
