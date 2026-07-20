from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum

class ThresholdType(str, Enum):
    FIXED_NUMERIC = "fixed_numeric"
    POINTS_BASED = "points_based"
    CASE_BY_CASE = "case_by_case"
    NOT_APPLICABLE = "not_applicable"


class VisaPurpose(str, Enum):
    STUDY = "study"
    WORK = "work"
    TOURIST = "tourist"
    FAMILY_REUNION = "family_reunion"
    BUSINESS = "business"
    PERMANENT_RESIDENCY = "permanent_residency"

class EligibilityGate(BaseModel):
    threshold_type: ThresholdType
    value: Optional[float] = None
    unit: Optional[str] = None
    points_required: Optional[int] = None
    verified: bool = False
    source_url: Optional[str] = None
    effective_date: Optional[str] = None
    notes: Optional[str] = None

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
    #purpose: str = Field(
    #    description="Purpose such as Work, Study, Tourist, Family Reunion, Business, PR")

    #topic: str = Field(
    #    description="High-level topic such as Visa, Immigration, Qualification Recognition, Living")

    # purpose: Optional[str] = None
    purpose: Optional[VisaPurpose] = None
    topic: Optional[str] = None

    visa_type: Optional[str] = None

    entry_type: Literal["overview", "detailed"] = "detailed"

    # ---------- Content ----------
    title: str
    summary: str

    # ---------- Requirements ----------
    eligibility: List[str] = []
    required_documents: List[str] = []

    # ---------- Hard filter fields (structured, for scoring engine) ----------
    min_income_threshold: Optional[EligibilityGate] = None
    min_education_level: Optional[Literal["none", "bachelor", "master", "phd"]] = None
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    required_language_test: Optional[str] = None
    min_language_score: Optional[str] = None
    points_required: Optional[int] = None
    mandatory_prerequisites: List[str] = []
    total_estimated_cost: Optional[float] = None
    cost_currency: Optional[str] = None

    # ---------- Soft scoring fields ----------
    processing_time_days_min: Optional[int] = None
    processing_time_days_max: Optional[int] = None
    pr_pathway_available: Optional[bool] = None
    pr_pathway_years: Optional[int] = None

    # ---------- Provenance / verification ----------
    source_tier: Literal[0, 1, 2, 3] = 3
    last_verified_date: Optional[str] = None

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