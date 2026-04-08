"""
Structured field extraction from a logistics document.

Uses llama-3.1-8b-instant (faster, token-efficient) with a strict JSON prompt
applied to the full document text — not chunks — so no field is missed due to
retrieval boundary effects.

Extracted fields:
  shipment_id, shipper, consignee, pickup_datetime, delivery_datetime,
  equipment_type, mode, rate, currency, weight, carrier_name

Missing fields are returned as null.
"""

from __future__ import annotations

import json
import logging
import re

from groq import Groq

from backend.config import GROQ_API_KEY, GROQ_EXTRACT_MODEL, GROQ_MAX_TOKENS

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = [
    "shipment_id",
    "shipper",
    "consignee",
    "pickup_datetime",
    "delivery_datetime",
    "equipment_type",
    "mode",
    "rate",
    "currency",
    "weight",
    "carrier_name",
]

EXTRACTION_SYSTEM = """\
You are a structured data extractor for logistics documents.
Extract the requested fields from the document text.
Return ONLY a valid JSON object — no markdown, no explanation, no extra text.
Use null for any field not explicitly stated in the document.
Do not invent or infer values.
"""

EXTRACTION_USER = """\
Extract the following fields from the logistics document below.

Fields and their definitions:
- shipment_id:        Load ID, Reference ID, or shipment reference number
- shipper:            Full name and address of the shipping/sending party
- consignee:          Full name and address of the receiving party
- pickup_datetime:    Pickup date and time in ISO-8601 format (YYYY-MM-DDTHH:MM:SS). Null if not found.
- delivery_datetime:  Delivery date and time in ISO-8601 format. Null if not found.
- equipment_type:     Type of truck/trailer (e.g., Flatbed, Dry Van, Reefer)
- mode:               Shipment mode (e.g., FTL, LTL)
- rate:               Numeric rate/charge value only (e.g., 1000.00)
- currency:           Currency code (e.g., USD, CAD)
- weight:             Total cargo weight including unit (e.g., "56000 lbs")
- carrier_name:       Name of the transportation/carrier company

DOCUMENT TEXT:
{document_text}

JSON:"""


def extract_fields(full_text: str) -> dict:
    """
    Run structured extraction on the full document text.
    Returns a dict with REQUIRED_FIELDS keys; missing values are None.
    """
    prompt = EXTRACTION_USER.format(document_text=full_text[:6000])  # hard cap for Groq TPM

    try:
        client   = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GROQ_EXTRACT_MODEL,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=GROQ_MAX_TOKENS,
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("Groq extraction API error: %s", exc)
        raise

    data = _parse_json(raw)

    # Ensure all required fields are present; fill missing with None
    for field in REQUIRED_FIELDS:
        data.setdefault(field, None)

    # Return only the known fields in a stable order
    return {f: data.get(f) for f in REQUIRED_FIELDS}


def _parse_json(raw: str) -> dict:
    """
    Robustly parse JSON from LLM output.
    Handles markdown code fences and partial wrapping.
    """
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw.strip())

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try to extract the first JSON object in the response
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    logger.warning("Could not parse extraction JSON. Raw response: %s", raw[:200])
    return {}
