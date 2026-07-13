"""Deterministic privacy-feature extraction primitives."""

from .classification import ServicePathDataClassDetector, classify_data_classes, classify_service_path
from .dictionaries import (
    DEFAULT_KEY_DICTIONARIES,
    DICTIONARY_VERSION,
    KeyCategory,
    match_schema_key,
    match_schema_keys,
    normalize_schema_key,
)
from .identifiers import (
    IdentifierObservation,
    IdentifierFeatureDetector,
    IdentifierType,
    aggregate_identifier_candidates,
    analyze_opaque_identifiers,
    detect_identifier,
    shannon_entropy,
)
from .density import DensityCooccurrenceDetector, aggregate_density_features
from .geospatial import (
    ExplicitInteractionFeatureDetector,
    GeospatialFeatureDetector,
    GeospatialPrecision,
    InteractionAction,
    extract_explicit_interactions,
    extract_geospatial_features,
)
from .inference_language import detect_inference_language
from .pipeline import (
    FeatureDetector,
    FeatureExtractionResult,
    extract_features,
    extract_partition_features,
    load_activity_event_partitions,
)
from .temporal import (
    TemporalNormalisation,
    normalise_temporal,
    normalize_temporal,
    temporal_feature_candidate,
)
from .url import URLDecomposition, URLQueryValueCandidate, decompose_url, url_feature_candidate

__all__ = [
    "DEFAULT_KEY_DICTIONARIES",
    "DICTIONARY_VERSION",
    "IdentifierObservation",
    "IdentifierFeatureDetector",
    "IdentifierType",
    "DensityCooccurrenceDetector",
    "ExplicitInteractionFeatureDetector",
    "FeatureDetector",
    "FeatureExtractionResult",
    "GeospatialFeatureDetector",
    "GeospatialPrecision",
    "InteractionAction",
    "KeyCategory",
    "ServicePathDataClassDetector",
    "aggregate_identifier_candidates",
    "aggregate_density_features",
    "analyze_opaque_identifiers",
    "classify_data_classes",
    "classify_service_path",
    "detect_identifier",
    "detect_inference_language",
    "decompose_url",
    "extract_explicit_interactions",
    "extract_features",
    "extract_geospatial_features",
    "extract_partition_features",
    "load_activity_event_partitions",
    "match_schema_key",
    "match_schema_keys",
    "normalize_schema_key",
    "normalise_temporal",
    "normalize_temporal",
    "shannon_entropy",
    "TemporalNormalisation",
    "temporal_feature_candidate",
    "URLDecomposition",
    "URLQueryValueCandidate",
    "url_feature_candidate",
]
