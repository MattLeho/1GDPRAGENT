"""
Grounded Extraction using LangExtract Patterns

Provides structured extraction with source text grounding following
LangExtract API patterns. Enables precise attribution of extractions
to source text spans.

Key Features:
- Schema-enforced extraction for GDPR domain
- Few-shot example support
- Multi-pass extraction for higher recall
- Source offset tracking for visualizationNote: This module can use LangExtract library if available, 
or fall back to Gemini-based extraction with similar patterns.

Source patterns: https://github.com/google/langextract
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field

from .schemas import GroundedEntity, EntityClass, TextChunk
from .chunker import chunk_text_with_offsets


# =============================================================================
# GDPR Extraction Schema
# =============================================================================

# Schema definition following LangExtract pattern
GDPR_EXTRACTION_SCHEMA = {
    "data_collection": {
        "description": "Information about data being collected",
        "attributes": ["collector", "data_type", "purpose", "legal_basis", "risk_level"]
    },
    "data_sharing": {
        "description": "Information about data being shared between parties",
        "attributes": ["from_entity", "to_entity", "data_type", "purpose"]
    },
    "data_right": {
        "description": "User rights regarding their data",
        "attributes": ["right_type", "description", "how_to_exercise"]
    },
    "third_party": {
        "description": "Third party with access to data",
        "attributes": ["name", "role", "location", "data_access"]
    },
    "personal_data": {
        "description": "Specific personal data item",
        "attributes": ["data_type", "sensitivity", "retention_period"]
    },
    "legal_basis": {
        "description": "Legal basis for data processing",
        "attributes": ["basis_type", "description", "applies_to"]
    },
}


# =============================================================================
# Example Data Structure
# =============================================================================

@dataclass
class ExampleExtraction:
    """Single extraction example for few-shot learning."""
    extraction_class: str
    extraction_text: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass 
class ExampleData:
    """Complete example with text and expected extractions."""
    text: str
    extractions: list[ExampleExtraction] = field(default_factory=list)


@dataclass
class ExtractionTask:
    """Definition of an extraction task."""
    description: str
    entity_classes: list[str]
    examples: list[ExampleData] = field(default_factory=list)


# =============================================================================
# Grounded Extractor Class
# =============================================================================

class GroundedExtractor:
    """
    Performs grounded extraction with source text attribution.
    
    Following LangExtract patterns for schema-enforced extraction
    with precise source grounding for UI visualization.
    
    Usage:
        extractor = GroundedExtractor(gemini_client)
        entities = await extractor.extract(text, task)
    """
    
    def __init__(
        self,
        gemini_client=None,
        model_id: str = "gemini-3-flash-preview",
        extraction_passes: int = 1,
        max_workers: int = 10,
    ):
        """
        Initialize grounded extractor.
        
        Args:
            gemini_client: GeminiClient instance
            model_id: Model identifier (for info/logging)
            extraction_passes: Number of extraction passes for recall
            max_workers: Max parallel extractions
        """
        self.client = gemini_client
        self.model_id = model_id
        self.extraction_passes = extraction_passes
        self.max_workers = max_workers
        self._langextract_available = self._check_langextract()
    
    def _check_langextract(self) -> bool:
        """Check if langextract library is available."""
        try:
            import langextract
            return True
        except ImportError:
            return False
    
    async def extract(
        self,
        text: str,
        task: Optional[ExtractionTask] = None,
        source_document: Optional[str] = None,
    ) -> list[GroundedEntity]:
        """
        Extract grounded entities from text.
        
        Args:
            text: Input text to extract from
            task: Extraction task definition
            source_document: Source document identifier
            
        Returns:
            List of GroundedEntity objects with source positions
        """
        task = task or self._default_gdpr_task()
        
        if self._langextract_available:
            return await self._extract_with_langextract(text, task, source_document)
        else:
            return await self._extract_with_gemini(text, task, source_document)
    
    def _default_gdpr_task(self) -> ExtractionTask:
        """Create default GDPR extraction task."""
        return ExtractionTask(
            description="Extract GDPR-relevant information including data collection, sharing, user rights, and third parties.",
            entity_classes=list(GDPR_EXTRACTION_SCHEMA.keys()),
            examples=self._load_gdpr_examples(),
        )
    
    def _load_gdpr_examples(self) -> list[ExampleData]:
        """Load GDPR-specific few-shot examples."""
        return [
            ExampleData(
                text="Google collects your browsing history to personalize advertisements and improve search results.",
                extractions=[
                    ExampleExtraction(
                        extraction_class="data_collection",
                        extraction_text="browsing history",
                        attributes={
                            "collector": "Google",
                            "data_type": "browsing history",
                            "purpose": "personalize advertisements, improve search results",
                            "risk_level": "medium"
                        }
                    )
                ]
            ),
            ExampleData(
                text="We share your email address with our advertising partners including Meta and TikTok.",
                extractions=[
                    ExampleExtraction(
                        extraction_class="data_sharing",
                        extraction_text="email address",
                        attributes={
                            "from_entity": "we",
                            "to_entity": "Meta, TikTok",
                            "data_type": "email address",
                            "purpose": "advertising"
                        }
                    ),
                    ExampleExtraction(
                        extraction_class="third_party",
                        extraction_text="Meta",
                        attributes={
                            "name": "Meta",
                            "role": "advertising partner",
                            "data_access": "email address"
                        }
                    ),
                    ExampleExtraction(
                        extraction_class="third_party",
                        extraction_text="TikTok",
                        attributes={
                            "name": "TikTok",
                            "role": "advertising partner",
                            "data_access": "email address"
                        }
                    )
                ]
            ),
            ExampleData(
                text="You have the right to request deletion of your personal data by emailing privacy@company.com.",
                extractions=[
                    ExampleExtraction(
                        extraction_class="data_right",
                        extraction_text="right to request deletion",
                        attributes={
                            "right_type": "right to erasure",
                            "description": "request deletion of personal data",
                            "how_to_exercise": "email privacy@company.com"
                        }
                    )
                ]
            ),
        ]
    
    async def _extract_with_langextract(
        self,
        text: str,
        task: ExtractionTask,
        source_document: Optional[str],
    ) -> list[GroundedEntity]:
        """
        Extract using langextract library.
        
        Uses official LangExtract API with CharInterval for source grounding.
        """
        import langextract as lx
        
        # Convert examples to langextract format
        lx_examples = []
        for example in task.examples:
            lx_extractions = []
            for ext in example.extractions:
                lx_extractions.append(lx.data.Extraction(
                    extraction_class=ext.extraction_class,
                    extraction_text=ext.extraction_text,
                    attributes=ext.attributes,
                ))
            lx_examples.append(lx.data.ExampleData(
                text=example.text,
                extractions=lx_extractions,
            ))
        
        # Run extraction using official API
        result = lx.extract(
            text_or_documents=text,
            prompt_description=task.description,
            examples=lx_examples,
            model_id=self.model_id,
            extraction_passes=self.extraction_passes,
            max_workers=self.max_workers,
        )
        
        # Convert to GroundedEntity using CharInterval pattern
        entities = []
        for doc in result.documents if hasattr(result, 'documents') else [result]:
            extractions = doc.extractions if hasattr(doc, 'extractions') else []
            for ext in extractions:
                # LangExtract uses CharInterval with start_pos/end_pos
                char_interval = getattr(ext, 'char_interval', None)
                if char_interval:
                    start = getattr(char_interval, 'start_pos', 0) or 0
                    end = getattr(char_interval, 'end_pos', len(ext.extraction_text)) or len(ext.extraction_text)
                else:
                    # Fallback: find text position
                    start = text.find(ext.extraction_text)
                    if start < 0:
                        start = 0
                    end = start + len(ext.extraction_text)
                
                entities.append(GroundedEntity(
                    entity_class=EntityClass(ext.extraction_class),
                    text=ext.extraction_text,
                    start_offset=start,
                    end_offset=end,
                    attributes=ext.attributes if hasattr(ext, 'attributes') and ext.attributes else {},
                    source_document=source_document,
                    confidence=getattr(ext, 'confidence', 1.0) or 1.0,
                ))
        
        return entities
    
    async def _extract_with_gemini(
        self,
        text: str,
        task: ExtractionTask,
        source_document: Optional[str],
    ) -> list[GroundedEntity]:
        """
        Extract using Gemini when langextract not available.
        
        Implements similar patterns with source grounding.
        """
        if not self.client:
            return []
        
        # Build prompt with examples
        examples_text = self._format_examples(task.examples)
        classes_text = ", ".join(task.entity_classes)
        
        prompt = f"""{task.description}

EXTRACTION CLASSES: {classes_text}

{examples_text}

TEXT TO EXTRACT FROM:
{text}

For each extraction, provide:
- class: One of [{classes_text}]
- text: The exact text span from the source (copy exactly)
- attributes: Relevant attributes as key-value pairs
- start_offset: Character position where the text starts (estimate if unsure)

Return a JSON array of extractions. Example format:
[
  {{
    "class": "data_collection",
    "text": "browsing history",
    "start_offset": 25,
    "attributes": {{"collector": "Google", "data_type": "browsing history"}}
  }}
]"""
        
        try:
            response = await self.client.extract_json(prompt)
            
            if not isinstance(response, list):
                return []
            
            entities = []
            for item in response:
                if not isinstance(item, dict):
                    continue
                
                ext_class = item.get("class", "")
                ext_text = item.get("text", "")
                
                if not ext_class or not ext_text:
                    continue
                
                # Try to find actual position in text
                start = item.get("start_offset", 0)
                if isinstance(start, str):
                    try:
                        start = int(start)
                    except ValueError:
                        start = 0
                
                # Verify/correct position by finding text
                actual_start = text.find(ext_text)
                if actual_start >= 0:
                    start = actual_start
                
                end = start + len(ext_text)
                
                # Map to EntityClass enum
                try:
                    entity_class = EntityClass(ext_class)
                except ValueError:
                    # Skip unknown classes
                    continue
                
                entities.append(GroundedEntity(
                    entity_class=entity_class,
                    text=ext_text,
                    start_offset=start,
                    end_offset=end,
                    attributes=item.get("attributes", {}),
                    source_document=source_document,
                    confidence=float(item.get("confidence", 0.8)),
                ))
            
            return entities
            
        except Exception:
            return []
    
    def _format_examples(self, examples: list[ExampleData]) -> str:
        """Format examples for prompt."""
        if not examples:
            return ""
        
        parts = ["EXAMPLES:"]
        for i, example in enumerate(examples[:3]):  # Max 3 examples
            parts.append(f"\nExample {i+1}:")
            parts.append(f"Text: \"{example.text[:200]}...\"" if len(example.text) > 200 else f"Text: \"{example.text}\"")
            parts.append("Extractions:")
            for ext in example.extractions[:3]:  # Max 3 per example
                attrs = ", ".join(f"{k}={v}" for k, v in list(ext.attributes.items())[:3])
                parts.append(f"  - [{ext.extraction_class}] \"{ext.extraction_text}\" ({attrs})")
        
        return "\n".join(parts)
    
    def export_jsonl(
        self,
        entities: list[GroundedEntity],
        output_path: Path,
    ) -> None:
        """
        Export extractions to JSONL format.
        
        Following LangExtract io pattern for visualization.
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            for entity in entities:
                record = {
                    "class": entity.entity_class.value,
                    "text": entity.text,
                    "start_offset": entity.start_offset,
                    "end_offset": entity.end_offset,
                    "attributes": entity.attributes,
                    "source_document": entity.source_document,
                    "confidence": entity.confidence,
                }
                f.write(json.dumps(record) + "\n")
    
    def generate_visualization_html(
        self,
        text: str,
        entities: list[GroundedEntity],
    ) -> str:
        """
        Generate interactive HTML visualization with highlighted extractions.
        
        Following LangExtract visualization pattern.
        """
        # Sort entities by start offset
        sorted_entities = sorted(entities, key=lambda e: e.start_offset)
        
        # Build highlighted HTML
        html_parts = ['<!DOCTYPE html><html><head>',
            '<style>',
            '.extraction { padding: 2px 4px; border-radius: 3px; cursor: pointer; }',
            '.data_collection { background: #e3f2fd; border: 1px solid #1976d2; }',
            '.data_sharing { background: #fff3e0; border: 1px solid #f57c00; }',
            '.data_right { background: #e8f5e9; border: 1px solid #388e3c; }',
            '.third_party { background: #fce4ec; border: 1px solid #c2185b; }',
            '.personal_data { background: #f3e5f5; border: 1px solid #7b1fa2; }',
            '.legal_basis { background: #e0f7fa; border: 1px solid #0097a7; }',
            '.tooltip { position: absolute; background: #333; color: white; padding: 8px; ',
            'border-radius: 4px; font-size: 12px; z-index: 1000; max-width: 300px; }',
            '</style>',
            '</head><body>',
            '<h2>GDPR Extraction Visualization</h2>',
            '<div id="content">']
        
        # Insert highlights
        last_end = 0
        for entity in sorted_entities:
            # Add text before this entity
            if entity.start_offset > last_end:
                html_parts.append(self._escape_html(text[last_end:entity.start_offset]))
            
            # Add highlighted entity
            attrs_str = "; ".join(f"{k}: {v}" for k, v in entity.attributes.items())
            html_parts.append(
                f'<span class="extraction {entity.entity_class.value}" '
                f'title="{entity.entity_class.value}: {attrs_str}">'
                f'{self._escape_html(entity.text)}</span>'
            )
            
            last_end = entity.end_offset
        
        # Add remaining text
        if last_end < len(text):
            html_parts.append(self._escape_html(text[last_end:]))
        
        html_parts.append('</div></body></html>')
        
        return ''.join(html_parts)
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace('\n', '<br>'))


# =============================================================================
# Convenience Functions
# =============================================================================

async def extract_grounded(
    text: str,
    gemini_client,
    entity_classes: Optional[list[str]] = None,
) -> list[GroundedEntity]:
    """
    Quick grounded extraction with default settings.
    """
    task = None
    if entity_classes:
        task = ExtractionTask(
            description="Extract GDPR-relevant information",
            entity_classes=entity_classes,
        )
    
    extractor = GroundedExtractor(gemini_client)
    return await extractor.extract(text, task)
