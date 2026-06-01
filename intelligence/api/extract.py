"""
File Extraction API Endpoint (LangExtract-powered)

Provides REST API for extracting structured GDPR-relevant information
from uploaded file content using Google LangExtract.

This is SEPARATE from the ONSIT extraction pipeline in intelligence/extraction/.
It specifically handles file upload processing from the frontend.
"""

import asyncio
import os
import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(prefix="/extract", tags=["File Extraction"])


# =============================================================================
# Request/Response Models
# =============================================================================

class FileExtractionRequest(BaseModel):
    """Request body for file content extraction."""
    content: str = Field(..., description="Extracted text content from the file")
    file_name: str = Field(..., description="Original file name")
    file_id: Optional[str] = Field(None, description="Database file ID")
    request_id: Optional[str] = Field(None, description="Associated request UUID")
    company_name: Optional[str] = Field(None, description="Company name for context")
    extraction_passes: int = Field(default=2, description="Number of LangExtract passes")


class TextExtractionRequest(BaseModel):
    """Request body for raw text extraction."""
    content: str = Field(..., description="Text to extract from")
    context: Optional[str] = Field(None, description="Additional context")
    extraction_passes: int = Field(default=1, description="Number of extraction passes")


class ExtractionEntity(BaseModel):
    """Single extracted entity."""
    entity_class: str
    text: str
    start_offset: int = 0
    end_offset: int = 0
    attributes: dict = {}
    confidence: float = 1.0


class ExtractionResponse(BaseModel):
    """Response from extraction."""
    success: bool
    file_name: Optional[str] = None
    entities: list[ExtractionEntity] = []
    entity_count: int = 0
    classes_found: list[str] = []
    error: Optional[str] = None


# =============================================================================
# GDPR Extraction Configuration (LangExtract-specific)
# =============================================================================

def _get_langextract():
    """Import and return langextract module, or None if unavailable."""
    try:
        import langextract as lx
        return lx
    except ImportError:
        return None


def _build_gdpr_examples(lx):
    """Build GDPR-specific few-shot examples for LangExtract."""
    return [
        lx.data.ExampleData(
            text="Google collects your browsing history and location data to personalize advertisements and improve search results.",
            extractions=[
                lx.data.Extraction(
                    extraction_class="data_collection",
                    extraction_text="browsing history and location data",
                    attributes={
                        "collector": "Google",
                        "data_type": "browsing history, location data",
                        "purpose": "personalize advertisements, improve search results",
                        "risk_level": "high",
                    },
                ),
            ],
        ),
        lx.data.ExampleData(
            text="We share your email address with our advertising partners including Meta and TikTok for targeted marketing.",
            extractions=[
                lx.data.Extraction(
                    extraction_class="data_sharing",
                    extraction_text="email address",
                    attributes={
                        "from_entity": "we",
                        "to_entity": "Meta, TikTok",
                        "data_type": "email address",
                        "purpose": "targeted marketing",
                    },
                ),
                lx.data.Extraction(
                    extraction_class="third_party",
                    extraction_text="Meta",
                    attributes={
                        "name": "Meta",
                        "role": "advertising partner",
                        "data_access": "email address",
                    },
                ),
                lx.data.Extraction(
                    extraction_class="third_party",
                    extraction_text="TikTok",
                    attributes={
                        "name": "TikTok",
                        "role": "advertising partner",
                        "data_access": "email address",
                    },
                ),
            ],
        ),
        lx.data.ExampleData(
            text="You have the right to request deletion of your personal data by emailing privacy@company.com within 30 days.",
            extractions=[
                lx.data.Extraction(
                    extraction_class="data_right",
                    extraction_text="right to request deletion",
                    attributes={
                        "right_type": "right to erasure",
                        "description": "request deletion of personal data",
                        "how_to_exercise": "email privacy@company.com",
                        "timeframe": "30 days",
                    },
                ),
            ],
        ),
        lx.data.ExampleData(
            text="We retain your payment information for 7 years to comply with tax regulations.",
            extractions=[
                lx.data.Extraction(
                    extraction_class="personal_data",
                    extraction_text="payment information",
                    attributes={
                        "data_type": "payment information",
                        "sensitivity": "high",
                        "retention_period": "7 years",
                    },
                ),
                lx.data.Extraction(
                    extraction_class="legal_basis",
                    extraction_text="comply with tax regulations",
                    attributes={
                        "basis_type": "legal obligation",
                        "description": "tax regulation compliance",
                        "applies_to": "payment information",
                    },
                ),
            ],
        ),
    ]


GDPR_PROMPT = """\
Extract GDPR-relevant information from the document in order of appearance.
Use exact text from the source for extractions. Do not paraphrase.

Entity classes to extract:
- data_collection: Information about data being collected (collector, data_type, purpose, legal_basis, risk_level)
- data_sharing: Information about data shared between parties (from_entity, to_entity, data_type, purpose)
- data_right: User rights regarding their data (right_type, description, how_to_exercise)
- third_party: Third parties with access to data (name, role, location, data_access)
- personal_data: Specific personal data items (data_type, sensitivity, retention_period)
- legal_basis: Legal basis for data processing (basis_type, description, applies_to)

Provide meaningful attributes for each entity to add GDPR context.\
"""


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/file", response_model=ExtractionResponse)
async def extract_from_file_content(body: FileExtractionRequest):
    """
    Extract GDPR entities from uploaded file content using LangExtract.
    
    This endpoint processes text extracted from uploaded files
    through the LangExtract pipeline for structured GDPR extraction.
    """
    lx = _get_langextract()
    if lx is None:
        raise HTTPException(
            status_code=503,
            detail="langextract library not installed. Run: pip install langextract",
        )

    if not body.content or len(body.content.strip()) < 10:
        return ExtractionResponse(
            success=True,
            file_name=body.file_name,
            entities=[],
            entity_count=0,
            classes_found=[],
        )

    # Build context-aware prompt
    prompt = GDPR_PROMPT
    if body.company_name:
        prompt += f"\n\nCompany context: {body.company_name}"

    examples = _build_gdpr_examples(lx)

    try:
        # LangExtract's extract() is synchronous — run in thread pool
        result = await asyncio.to_thread(
            lx.extract,
            text_or_documents=body.content[:50000],  # Cap at 50k chars
            prompt_description=prompt,
            examples=examples,
            model_id="gemini-2.5-flash",
            extraction_passes=body.extraction_passes,
            max_workers=10,
            max_char_buffer=1000,
            context_window_chars=500,
            show_progress=False,
            fetch_urls=False,
        )

        # Convert LangExtract result to our response format
        entities = []
        docs = result if isinstance(result, list) else [result]

        for doc in docs:
            extractions = getattr(doc, "extractions", []) or []
            source_text = getattr(doc, "text", body.content) or body.content

            for ext in extractions:
                char_interval = getattr(ext, "char_interval", None)
                if char_interval:
                    start = getattr(char_interval, "start_pos", 0) or 0
                    end = getattr(char_interval, "end_pos", 0) or 0
                else:
                    start = source_text.find(ext.extraction_text)
                    if start < 0:
                        start = 0
                    end = start + len(ext.extraction_text)

                entities.append(ExtractionEntity(
                    entity_class=ext.extraction_class,
                    text=ext.extraction_text,
                    start_offset=start,
                    end_offset=end,
                    attributes=ext.attributes if hasattr(ext, "attributes") and ext.attributes else {},
                    confidence=getattr(ext, "confidence", 1.0) or 1.0,
                ))

        classes_found = list(set(e.entity_class for e in entities))

        return ExtractionResponse(
            success=True,
            file_name=body.file_name,
            entities=entities,
            entity_count=len(entities),
            classes_found=classes_found,
        )

    except Exception as e:
        return ExtractionResponse(
            success=False,
            file_name=body.file_name,
            error=str(e),
        )


@router.post("/text", response_model=ExtractionResponse)
async def extract_from_text(body: TextExtractionRequest):
    """
    Extract GDPR entities from raw text using LangExtract.
    
    Lightweight endpoint for quick text extraction without file context.
    """
    file_req = FileExtractionRequest(
        content=body.content,
        file_name="<text_input>",
        extraction_passes=body.extraction_passes,
    )
    return await extract_from_file_content(file_req)


@router.get("/health")
async def extract_health():
    """Check LangExtract availability and configuration."""
    lx = _get_langextract()
    api_key = os.environ.get("LANGEXTRACT_API_KEY") or os.environ.get("GOOGLE_AI_API_KEY")

    return {
        "langextract_available": lx is not None,
        "langextract_version": getattr(lx, "__version__", "unknown") if lx else None,
        "api_key_configured": bool(api_key),
        "recommended_model": "gemini-2.5-flash",
    }
