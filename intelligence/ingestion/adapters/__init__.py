"""Approved file-family adapters for the local ingestion pipeline."""

from .structured_text import StructuredTextAdapter
from .email_calendar import EmailCalendarAdapter
from .geospatial_database import GeospatialDatabaseAdapter
from .archives import ArchiveAdapter
from .media import MediaAdapter
from .documents import DocumentsAdapter

__all__=["StructuredTextAdapter","EmailCalendarAdapter","GeospatialDatabaseAdapter","ArchiveAdapter","MediaAdapter","DocumentsAdapter"]
