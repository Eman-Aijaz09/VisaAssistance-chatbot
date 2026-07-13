from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class VisaKnowledge(BaseModel):
    """
    Represents one immigration knowledge entity extracted
    from an official webpage.

    One webpage can contain multiple VisaKnowledge objects.
    """

    # ---------- Metadata ----------
    country: str
    source_url: str
    page_title: str

    # ---------- Classification ----------
    purpose: str = Field(
        description="Purpose such as Work, Study, Tourist, Family Reunion, Business, PR"
    )

    topic: str = Field(
        description="High-level topic such as Visa, Immigration, Qualification Recognition, Living"
    )

    visa_type: Optional[str] = None

    # ---------- Content ----------
    title: str
    summary: str

    # ---------- Requirements ----------
    eligibility: List[str] = []
    required_documents: List[str] = []

    # ---------- Application ----------
    application_process: List[str] = []
    processing_time: Optional[str] = None
    application_fee: Optional[str] = None
    validity: Optional[str] = None

    # ---------- Supporting Information ----------
    official_links: List[str] = []
    important_notes: List[str] = []

    # ---------- Flexible ----------
    extra_information: Dict[str, Any] = {}