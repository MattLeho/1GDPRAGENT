"""
ONSIT Intel Extractors

Regex patterns for extracting intelligence from web content.
Ported from Photon: https://github.com/s0md3v/Photon/blob/master/core/regex.py

Patterns handle:
- Standard and defanged URLs
- IPv4/IPv6 addresses
- Email addresses with defangs
- Hash values (MD5, SHA1, SHA256, SHA512)
- Credit card numbers (Luhn validated)
- High-entropy secrets (API keys)
- YARA rules
"""

import re
import math
from dataclasses import dataclass
from typing import Optional
from enum import Enum

from .models import EntityType, Finding


# =============================================================================
# Photon Regex Patterns (ported verbatim)
# Source: https://github.com/s0md3v/Photon/blob/master/core/regex.py
# =============================================================================

# Reusable end punctuation regex
END_PUNCTUATION = r"[\.\?>\"\'\)!,}:;\u201d\u2019\uff1e\uff1c\]]*"

# Reusable regex for symbols commonly used to defang
SEPARATOR_DEFANGS = r"[\(\)\[\]{}<>\\]"

# Split URLs on some characters that may be valid but may also be garbage
URL_SPLIT_STR = r"[>\"\'\),};]"


# URL Patterns
GENERIC_URL = re.compile(r"""
    (
        # Scheme
        [fhstu]\S\S?[px]s?
        # One of these delimiters/defangs
        (?:
            :\/\/|
            :\\\\|
            :?__
        )
        # Any number of defang characters
        (?:
            \x20|
            """ + SEPARATOR_DEFANGS + r"""
        )*
        # Domain/path characters
        \w
        \S+?
        # CISCO ESA style defangs followed by domain/path characters
        (?:\x20[\/\.][^\.\\/\s]\S*?)*
    )
    """ + END_PUNCTUATION + r"""
    (?=\s|$)
""", re.IGNORECASE | re.VERBOSE | re.UNICODE)

BRACKET_URL = re.compile(r"""
    \b
    (
        [\.:\\/\w\[\]\(\)-]+
        (?:
            \x20?
            [\(\[]
            \x20?
            \.
            \x20?
            [\]\)]
            \x20?
            \S*?
        )+
    )
    """ + END_PUNCTUATION + r"""
    (?=\s|$)
""", re.VERBOSE | re.UNICODE)

BACKSLASH_URL = re.compile(r"""
    \b
    (
        [:\\/\w\[\]\(\)-]+
        (?:
            \x20?
            \\?\.
            \x20?
            \S*?
        )*?
        (?:
            \x20?
            \\\.
            \x20?
            \S*?
        )
        (?:
            \x20?
            \\?\.
            \x20?
            \S*?
        )*
    )
    """ + END_PUNCTUATION + r"""
    (?=\s|$)
""", re.VERBOSE | re.UNICODE)

HEXENCODED_URL = re.compile(r"""
    (
        [46][86]
        (?:[57]4)?
        [57]4[57]0
        (?:[57]3)?
        3a2f2f
        (?:[2356def]|3[0-9adf]|[46][0-9a-f]|[57][0-9af])+
    )
    (?:[046]0|2[0-2489a-c]|3[bce]|[57][b-e]|[8-f][0-9a-f]|0a|0d|09|[
        \x5b-\x5d\x7b\x7d\x0a\x0d\x20
    ]|$)
""", re.IGNORECASE | re.VERBOSE)

URLENCODED_URL = re.compile(r"""
    (s?[hf]t?tps?%3A%2F%2F\w[\w%-]*?)(?:[^\w%-]|$)
""", re.IGNORECASE | re.VERBOSE)

B64ENCODED_URL = re.compile(r"""
    (
        (?:
            [\x2b\x2f-\x39A-Za-z]\s*[\x2b\x2f-\x39A-Za-z]\s*[\x31\x35\x39BFJNRVZdhlptx]\s*[Gm]\s*[Vd]\s*[FH]\s*[A]\s*\x36\s*L\s*y\s*[\x2b\x2f\x38-\x39]\s*|
            [\x2b\x2f-\x39A-Za-z]\s*[\x2b\x2f-\x39A-Za-z]\s*[\x31\x35\x39BFJNRVZdhlptx]\s*[Io]\s*[Vd]\s*[FH]\s*[R]\s*[Qw]\s*[O]\s*i\s*\x38\s*v\s*[\x2b\x2f-\x39A-Za-z]\s*|
            [\x2b\x2f-\x39A-Za-z]\s*[\x2b\x2f-\x39A-Za-z]\s*[\x31\x35\x39BFJNRVZdhlptx]\s*[Io]\s*[Vd]\s*[FH]\s*[R]\s*[Qw]\s*[Uc]\s*[z]\s*o\s*v\s*L\s*[\x2b\x2f-\x39w-z]\s*|
            [RZ]\s*[ln]\s*[R]\s*[Qw]\s*[O]\s*i\s*\x38\s*v\s*[\x2b\x2f-\x39A-Za-z]\s*|
            [Sa]\s*[FH]\s*[R]\s*[\x30U]\s*[Uc]\s*[D]\s*o\s*v\s*L\s*[\x2b\x2f-\x39w-z]\s*|
            [Sa]\s*[FH]\s*[R]\s*[\x30U]\s*[Uc]\s*[FH]\s*[M]\s*\x36\s*L\s*y\s*[\x2b\x2f\x38-\x39]\s*
        )
        [A-Za-z0-9+/=\s]{1,357}
    )
    (?=[^A-Za-z0-9+/=\s]|$)
""", re.VERBOSE)


# IP Address Patterns
IPV4 = re.compile(r"""
    (?:^|
        (?![^\d\.])
    )
    (?:
        (?:[1-9]?\d|1\d\d|2[0-4]\d|25[0-5])
        [\[\(\\]*?\.[\]\)]*?
    ){3}
    (?:[1-9]?\d|1\d\d|2[0-4]\d|25[0-5])
    (?:(?=[^\d\.])|$)
""", re.VERBOSE)

IPV6 = re.compile(r"""
    \b(?:[a-f0-9]{1,4}:|:){2,7}(?:[a-f0-9]{1,4}|:)\b
""", re.IGNORECASE | re.VERBOSE)


# Email Pattern (handles defangs)
EMAIL = re.compile(r"""
    (
        [a-z0-9_.+-]+
        [\(\[\{\x20]*
        (?:@|\Wat\W)
        [\)\]\}\x20]*
        [a-z0-9-]+
        (?:
            (?:
                (?:
                    \x20*
                    """ + SEPARATOR_DEFANGS + r"""
                    \x20*
                )*
                \.
                (?:
                    \x20*
                    """ + SEPARATOR_DEFANGS + r"""
                    \x20*
                )*
                |
                \W+dot\W+
            )
            [a-z0-9-]+?
        )+
    )
    """ + END_PUNCTUATION + r"""
    (?=\s|$)
""", re.IGNORECASE | re.VERBOSE | re.UNICODE)


# Hash Patterns
MD5 = re.compile(r"(?:[^a-fA-F\d]|\b)([a-fA-F\d]{32})(?:[^a-fA-F\d]|\b)")
SHA1 = re.compile(r"(?:[^a-fA-F\d]|\b)([a-fA-F\d]{40})(?:[^a-fA-F\d]|\b)")
SHA256 = re.compile(r"(?:[^a-fA-F\d]|\b)([a-fA-F\d]{64})(?:[^a-fA-F\d]|\b)")
SHA512 = re.compile(r"(?:[^a-fA-F\d]|\b)([a-fA-F\d]{128})(?:[^a-fA-F\d]|\b)")

# Credit Card Pattern (Luhn validation done separately)
CREDIT_CARD = re.compile(r"[0-9]{4}[ ]?[-]?[0-9]{4}[ ]?[-]?[0-9]{4}[ ]?[-]?[0-9]{4}")

# YARA Rule Pattern
YARA_PARSE = re.compile(r"""
    (?:^|\s)
    (
        (?:
            \s*?import\s+?"[^\r\n]*?[\r\n]+|
            \s*?include\s+?"[^\r\n]*?[\r\n]+|
            \s*?//[^\r\n]*[\r\n]+|
            \s*?/\*.*?\*/\s*?
        )*
        (?:
            \s*?private\s+|
            \s*?global\s+
        )*
        rule\s*?
        \w+\s*?
        (?:
            :[\s\w]+
        )?
        \s+\{
        .*?
        condition\s*?:
        .*?
        \s*\}
    )
    (?:$|\s)
""", re.MULTILINE | re.DOTALL | re.VERBOSE)


# Script/Link Extraction
SCRIPT_SRC = re.compile(r'<(script|SCRIPT).*(src|SRC)=([^\s>]+)')
HREF = re.compile(r'<[aA].*(href|HREF)=([^\s>]+)')
ENDPOINT = re.compile(r'[\'\"](\\/.*?)[\'\"]\|[\'\"](http.*?)[\'\"]')

# High-Entropy String (potential API keys/secrets)
ENTROPY_STRING = re.compile(r'[\w-]{16,45}')


# =============================================================================
# Pattern Registry
# =============================================================================

@dataclass
class IntelPattern:
    """Represents an intelligence extraction pattern."""
    name: str
    pattern: re.Pattern
    entity_type: EntityType
    risk_level: str = "low"
    validator: Optional[callable] = None


# All patterns in order of specificity
INTEL_PATTERNS: list[IntelPattern] = [
    IntelPattern("GENERIC_URL", GENERIC_URL, EntityType.URL, "low"),
    IntelPattern("BRACKET_URL", BRACKET_URL, EntityType.URL, "low"),
    IntelPattern("BACKSLASH_URL", BACKSLASH_URL, EntityType.URL, "low"),
    IntelPattern("HEXENCODED_URL", HEXENCODED_URL, EntityType.URL, "medium"),
    IntelPattern("URLENCODED_URL", URLENCODED_URL, EntityType.URL, "medium"),
    IntelPattern("B64ENCODED_URL", B64ENCODED_URL, EntityType.URL, "medium"),
    IntelPattern("IPV4", IPV4, EntityType.IP, "low"),
    IntelPattern("IPV6", IPV6, EntityType.IP, "low"),
    IntelPattern("EMAIL", EMAIL, EntityType.EMAIL, "medium"),
    IntelPattern("MD5", MD5, EntityType.CREDENTIAL, "high"),
    IntelPattern("SHA1", SHA1, EntityType.CREDENTIAL, "high"),
    IntelPattern("SHA256", SHA256, EntityType.CREDENTIAL, "high"),
    IntelPattern("SHA512", SHA512, EntityType.CREDENTIAL, "high"),
    IntelPattern("CREDIT_CARD", CREDIT_CARD, EntityType.CREDIT_CARD, "critical"),
    IntelPattern("YARA", YARA_PARSE, EntityType.FILE, "low"),
]


# =============================================================================
# Entropy Calculation (for secret detection)
# =============================================================================

def calculate_entropy(data: str) -> float:
    """
    Calculate Shannon entropy of a string.
    High entropy (> 4.5) often indicates secrets/API keys.
    """
    if not data:
        return 0.0
    
    entropy = 0.0
    for x in set(data):
        p_x = data.count(x) / len(data)
        entropy -= p_x * math.log2(p_x)
    
    return entropy


def is_high_entropy(value: str, threshold: float = 4.5) -> bool:
    """Check if string has high entropy (potential secret)."""
    return calculate_entropy(value) > threshold


# =============================================================================
# Luhn Algorithm (Credit Card Validation)
# =============================================================================

def luhn_checksum(card_number: str) -> bool:
    """
    Validate credit card number using Luhn algorithm.
    """
    digits = [int(d) for d in card_number if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    
    return checksum % 10 == 0


# =============================================================================
# Main Extractor Class
# =============================================================================

class IntelExtractor:
    """
    Extracts intelligence from text content using Photon-derived patterns.
    
    Usage:
        extractor = IntelExtractor()
        findings = extractor.extract_all("Some text with user@example.com")
    """
    
    def __init__(self, include_patterns: Optional[list[str]] = None):
        """
        Initialize extractor with optional pattern filter.
        
        Args:
            include_patterns: List of pattern names to use (None = all)
        """
        if include_patterns:
            self.patterns = [
                p for p in INTEL_PATTERNS 
                if p.name in include_patterns
            ]
        else:
            self.patterns = INTEL_PATTERNS
    
    def extract_all(self, text: str, source: str = "extractor") -> list[Finding]:
        """
        Extract all intelligence from text.
        
        Args:
            text: Content to analyze
            source: Source identifier for findings
            
        Returns:
            List of Finding objects
        """
        findings = []
        seen_values = set()  # Dedupe
        
        for pattern in self.patterns:
            matches = pattern.pattern.findall(text)
            
            for match in matches:
                # Handle tuple matches (from grouped patterns)
                value = match[0] if isinstance(match, tuple) else match
                value = value.strip()
                
                if not value or value in seen_values:
                    continue
                
                # Validate specific patterns
                if pattern.name == "CREDIT_CARD":
                    if not luhn_checksum(value):
                        continue
                
                seen_values.add(value)
                findings.append(Finding(
                    finding_type=pattern.entity_type,
                    value=value,
                    risk_level=pattern.risk_level,
                    source=source,
                    metadata={"pattern": pattern.name}
                ))
        
        # Also check for high-entropy strings (secrets)
        for match in ENTROPY_STRING.findall(text):
            if match not in seen_values and is_high_entropy(match):
                seen_values.add(match)
                findings.append(Finding(
                    finding_type=EntityType.CREDENTIAL,
                    value=match,
                    risk_level="high",
                    source=source,
                    metadata={"pattern": "HIGH_ENTROPY"}
                ))
        
        return findings
    
    def extract_urls(self, text: str) -> list[str]:
        """Extract all URL variants from text."""
        urls = set()
        for pattern in [GENERIC_URL, BRACKET_URL, BACKSLASH_URL]:
            for match in pattern.findall(text):
                value = match[0] if isinstance(match, tuple) else match
                urls.add(value.strip())
        return list(urls)
    
    def extract_emails(self, text: str) -> list[str]:
        """Extract all email addresses from text."""
        emails = set()
        for match in EMAIL.findall(text):
            value = match[0] if isinstance(match, tuple) else match
            # Clean up defangs
            cleaned = value.replace(" ", "").replace("[.]", ".").replace("[@]", "@")
            emails.add(cleaned.strip())
        return list(emails)
    
    def extract_ips(self, text: str) -> list[str]:
        """Extract all IP addresses from text."""
        ips = set()
        for match in IPV4.findall(text):
            # Clean up defangs
            cleaned = match.replace("[.]", ".").replace("(", "").replace(")", "")
            ips.add(cleaned)
        for match in IPV6.findall(text):
            ips.add(match)
        return list(ips)
    
    def extract_hashes(self, text: str) -> dict[str, list[str]]:
        """Extract all hash values from text."""
        return {
            "md5": [m for m in MD5.findall(text)],
            "sha1": [m for m in SHA1.findall(text)],
            "sha256": [m for m in SHA256.findall(text)],
            "sha512": [m for m in SHA512.findall(text)],
        }
    
    def extract_scripts(self, html: str) -> list[str]:
        """Extract script sources from HTML."""
        scripts = []
        for match in SCRIPT_SRC.findall(html):
            if len(match) >= 3:
                src = match[2].strip('"\'')
                scripts.append(src)
        return scripts
    
    def extract_links(self, html: str) -> list[str]:
        """Extract href links from HTML."""
        links = []
        for match in HREF.findall(html):
            if len(match) >= 2:
                href = match[1].strip('"\'')
                links.append(href)
        return links


# =============================================================================
# Convenience Functions
# =============================================================================

def extract_intel(text: str, source: str = "unknown") -> list[Finding]:
    """Quick extraction using default extractor."""
    return IntelExtractor().extract_all(text, source)


def defang_url(url: str) -> str:
    """Convert URL to defanged format for safe display."""
    return url.replace("http", "hxxp").replace(".", "[.]")


def refang_url(url: str) -> str:
    """Convert defanged URL back to normal format."""
    return url.replace("hxxp", "http").replace("[.]", ".").replace("[:]", ":")
