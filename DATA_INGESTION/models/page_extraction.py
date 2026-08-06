from typing import List
from pydantic import BaseModel

from .visa_knowledge import VisaKnowledge


class PageExtraction(BaseModel):
    """
    Represents everything extracted from one webpage.
    """

    entities: List[VisaKnowledge]