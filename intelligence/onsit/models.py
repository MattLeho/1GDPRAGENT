"""
ONSIT Entity Models

Comprehensive entity types for OSINT discovery, following Flowsint patterns.
Source: https://github.com/reconurge/flowsint/tree/main/flowsint-types/src/flowsint_types

All entities inherit from ONSITEntity base class with:
- Pydantic validation
- Neo4j label resolution
- Automatic label computation for UI display
"""

from __future__ import annotations

import re
import hashlib
from abc import ABC
from enum import Enum
from typing import Optional, Any, Self
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator


# =============================================================================
# Entity Type Enumeration
# =============================================================================

class EntityType(str, Enum):
    """All supported ONSIT entity types for Neo4j labels."""
    # Network entities
    DOMAIN = "Domain"
    IP = "IP"
    ASN = "ASN"
    CIDR = "CIDR"
    DNS_RECORD = "DNSRecord"
    
    # Identity entities
    EMAIL = "Email"
    PHONE = "Phone"
    USERNAME = "Username"
    INDIVIDUAL = "Individual"
    ORGANIZATION = "Organization"
    
    # Social entities
    SOCIAL_ACCOUNT = "SocialAccount"
    GRAVATAR = "Gravatar"
    
    # Security entities
    CREDENTIAL = "Credential"
    BREACH = "Breach"
    LEAK = "Leak"
    
    # Web entities
    WEBSITE = "Website"
    URL = "URL"
    WEB_TRACKER = "WebTracker"
    
    # Financial entities
    WALLET = "Wallet"
    CREDIT_CARD = "CreditCard"
    BANK_ACCOUNT = "BankAccount"
    
    # Technical entities
    FILE = "File"
    DOCUMENT = "Document"
    DEVICE = "Device"
    SSL_CERTIFICATE = "SSLCertificate"
    
    # Meta entities
    FINDING = "Finding"
    WHOIS = "Whois"


# =============================================================================
# Base Entity Class (Flowsint Pattern)
# =============================================================================

class ONSITEntity(BaseModel):
    """
    Base class for all ONSIT entity types.
    
    Follows Flowsint pattern with:
    - label: UI-readable label for graph display
    - entity_type: Neo4j node label
    - Auto-generated ID based on primary fields
    """
    
    label: Optional[str] = Field(
        None, 
        description="UI-readable label for graph display"
    )
    source: Optional[str] = Field(
        None,
        description="Discovery source (crawler, enricher, etc.)"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score 0.0-1.0"
    )
    discovered_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this entity was discovered"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
    
    @property
    def entity_type(self) -> EntityType:
        """Return the entity type for Neo4j label."""
        raise NotImplementedError("Subclasses must define entity_type")
    
    @property
    def neo4j_label(self) -> str:
        """Neo4j node label."""
        return self.entity_type.value
    
    def to_neo4j_props(self) -> dict:
        """Convert to Neo4j node properties."""
        props = self.model_dump(exclude={"metadata"})
        props.update(self.metadata)
        return props
    
    class Config:
        extra = "allow"


# =============================================================================
# Network Entities
# =============================================================================

class Domain(ONSITEntity):
    """Represents a domain name."""
    
    domain: str = Field(
        ..., 
        description="Domain name",
        json_schema_extra={"primary": True}
    )
    root: Optional[bool] = Field(True, description="Is root domain")
    registrar: Optional[str] = None
    created_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    
    @property
    def entity_type(self) -> EntityType:
        return EntityType.DOMAIN
    
    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        # Handle URLs
        if "://" in v:
            from urllib.parse import urlparse
            v = urlparse(v).hostname or v
        v = v.lower().strip()
        if not re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError(f"Invalid domain: {v}")
        return v
    
    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.label = self.domain
        return self


class IP(ONSITEntity):
    """Represents an IP address (v4 or v6)."""
    
    address: str = Field(
        ..., 
        description="IP address",
        json_schema_extra={"primary": True}
    )
    version: int = Field(4, description="IP version (4 or 6)")
    asn: Optional[str] = None
    geo_country: Optional[str] = None
    geo_city: Optional[str] = None
    hostname: Optional[str] = None
    
    @property
    def entity_type(self) -> EntityType:
        return EntityType.IP
    
    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.label = self.address
        # Detect version
        self.version = 6 if ":" in self.address else 4
        return self


class ASN(ONSITEntity):
    """Represents an Autonomous System Number."""
    
    number: int = Field(..., description="ASN number", gt=0)
    name: Optional[str] = None
    country: Optional[str] = None
    description: Optional[str] = None
    
    @property
    def entity_type(self) -> EntityType:
        return EntityType.ASN
    
    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.label = f"AS{self.number}"
        return self


class CIDR(ONSITEntity):
    """Represents a CIDR range."""
    
    range: str = Field(..., description="CIDR notation (e.g., 192.168.0.0/24)")
    size: Optional[int] = None
    
    @property
    def entity_type(self) -> EntityType:
        return EntityType.CIDR
    
    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.label = self.range
        return self


# =============================================================================
# Identity Entities
# =============================================================================

class Email(ONSITEntity):
    """Represents an email address."""
    
    email: EmailStr = Field(
        ..., 
        description="Email address",
        json_schema_extra={"primary": True}
    )
    provider: Optional[str] = None
    verified: Optional[bool] = None
    
    @property
    def entity_type(self) -> EntityType:
        return EntityType.EMAIL
    
    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.label = self.email
        # Extract provider from domain
        if self.provider is None and "@" in self.email:
            self.provider = self.email.split("@")[1]
        return self


class Phone(ONSITEntity):
    """Represents a phone number."""
    
    number: str = Field(..., description="Phone number")
    country_code: Optional[str] = None
    carrier: Optional[str] = None
    line_type: Optional[str] = None  # mobile, landline, voip
    
    @property
    def entity_type(self) -> EntityType:
        return EntityType.PHONE
    
    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.label = self.number
        return self


class Username(ONSITEntity):
    """Represents a username on a platform."""
    
    username: str = Field(..., description="Username")
    platform: Optional[str] = None
    url: Optional[str] = None
    
    @property
    def entity_type(self) -> EntityType:
        return EntityType.USERNAME
    
    @model_validator(mode="after")
    def compute_label(self) -> Self:
        if self.platform:
            self.label = f"{self.username}@{self.platform}"
        else:
            self.label = self.username
        return self


class Individual(ONSITEntity):
    """Represents an individual person."""
    
    name: str = Field(..., description="Full name")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)
    date_of_birth: Optional[datetime] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    
    @property
    def entity_type(self) -> EntityType:
        return EntityType.INDIVIDUAL
    
    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.label = self.name
        return self


class Organization(ONSITEntity):
    """Represents an organization/company."""
    
    name: str = Field(..., description="Organization name")
    org_type: Optional[str] = None  # company, ngo, government
    industry: Optional[str] = None
    country: Optional[str] = None
    
    @property
    def entity_type(self) -> EntityType:
        return EntityType.ORGANIZATION
    
    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.label = self.name
        return self


# =============================================================================
# Social Entities
# =============================================================================

class SocialAccount(ONSITEntity):
    """Represents a social media account."""
    
    platform: str = Field(..., description="Platform name (twitter, linkedin, etc.)")
    username: str = Field(..., description="Username on platform")
    url: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    followers: Optional[int] = None
    following: Optional[int] = None
    verified: Optional[bool] = None
    profile_image_url: Optional[str] = None
    
    @property
    def entity_type(self) -> EntityType:
        return EntityType.SOCIAL_ACCOUNT
    
    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.label = f"{self.username}@{self.platform}"
        return self


class Gravatar(ONSITEntity):
    """Represents a Gravatar profile."""
    
    email_hash: str = Field(..., description="MD5 hash of email")
    display_name: Optional[str] = None
    profile_url: Optional[str] = None
    avatar_url: Optional[str] = None
    
    @property
    def entity_type(self) -> EntityType:
        return EntityType.GRAVATAR
    
    @classmethod
    def from_email(cls, email: str) -> "Gravatar":
        email_hash = hashlib.md5(email.lower().strip().encode()).hexdigest()
        return cls(
            email_hash=email_hash,
            profile_url=f"https://www.gravatar.com/{email_hash}",
            avatar_url=f"https://www.gravatar.com/avatar/{email_hash}",
        )
    
    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.label = self.display_name or self.email_hash[:8]
        return self


# =============================================================================
# Security Entities
# =============================================================================

class Credential(ONSITEntity):
    """Represents an exposed credential."""
    
    credential_type: str = Field(..., description="Type: password, hash, token, etc.")
    value: Optional[str] = Field(None, description="Credential value (redacted)")
    hash_type: Optional[str] = None  # md5, sha1, sha256, bcrypt
    source: Optional[str] = None  # breach name, paste, etc.
    
    @property
    def entity_type(self) -> EntityType:
        return EntityType.CREDENTIAL
    
    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.label = f"{self.credential_type}:{self.source or 'unknown'}"
        return self


class Breach(ONSITEntity):
    """Represents a data breach."""
    
    name: str = Field(..., description="Breach name")
    breach_date: Optional[datetime] = None
    description: Optional[str] = None
    data_classes: list[str] = Field(default_factory=list)
    is_verified: bool = True
    pwn_count: Optional[int] = None
    
    @property
    def entity_type(self) -> EntityType:
        return EntityType.BREACH
    
    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.label = self.name
        return self


# =============================================================================
# Web Entities
# =============================================================================

class Website(ONSITEntity):
    """Represents a website."""
    
    url: str = Field(..., description="Website URL")
    title: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)
    status_code: Optional[int] = None
    
    @property
    def entity_type(self) -> EntityType:
        return EntityType.WEBSITE
    
    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.label = self.title or self.url
        return self


class Wallet(ONSITEntity):
    """Represents a cryptocurrency wallet."""
    
    address: str = Field(..., description="Wallet address")
    blockchain: str = Field(..., description="Blockchain (bitcoin, ethereum, etc.)")
    balance: Optional[float] = None
    
    @property
    def entity_type(self) -> EntityType:
        return EntityType.WALLET
    
    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.label = f"{self.blockchain}:{self.address[:12]}..."
        return self


# =============================================================================
# Discovery/Scan Models
# =============================================================================

class Finding(ONSITEntity):
    """Represents a single ONSIT discovery finding."""
    
    finding_type: EntityType = Field(..., description="Type of entity found")
    value: str = Field(..., description="Raw value found")
    risk_level: str = Field("low", description="Risk level: low, medium, high, critical")
    
    @property
    def entity_type(self) -> EntityType:
        return EntityType.FINDING
    
    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.label = f"{self.finding_type.value}: {self.value[:50]}"
        return self


class ScanStatus(BaseModel):
    """Status of an ONSIT discovery scan."""
    
    scan_id: str
    status: str  # pending, running, completed, failed
    progress: float = Field(0.0, ge=0.0, le=1.0)
    findings_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class CrawlResult(BaseModel):
    """Result of a web crawl operation."""
    
    url: str
    status_code: int
    internal_urls: list[str] = Field(default_factory=list)
    external_urls: list[str] = Field(default_factory=list)
    intel: list[Finding] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    scripts: list[str] = Field(default_factory=list)


# =============================================================================
# Entity Registry
# =============================================================================

ENTITY_REGISTRY: dict[EntityType, type[ONSITEntity]] = {
    EntityType.DOMAIN: Domain,
    EntityType.IP: IP,
    EntityType.ASN: ASN,
    EntityType.CIDR: CIDR,
    EntityType.EMAIL: Email,
    EntityType.PHONE: Phone,
    EntityType.USERNAME: Username,
    EntityType.INDIVIDUAL: Individual,
    EntityType.ORGANIZATION: Organization,
    EntityType.SOCIAL_ACCOUNT: SocialAccount,
    EntityType.GRAVATAR: Gravatar,
    EntityType.CREDENTIAL: Credential,
    EntityType.BREACH: Breach,
    EntityType.WEBSITE: Website,
    EntityType.WALLET: Wallet,
    EntityType.FINDING: Finding,
}


def create_entity(entity_type: EntityType, **kwargs) -> ONSITEntity:
    """Factory function to create entities by type."""
    cls = ENTITY_REGISTRY.get(entity_type)
    if cls is None:
        raise ValueError(f"Unknown entity type: {entity_type}")
    return cls(**kwargs)
