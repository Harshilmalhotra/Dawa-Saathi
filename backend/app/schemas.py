from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

FoodTiming = Literal["before_food", "after_food", "with_food", "empty_stomach", "any"]

class MedicineExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source_text: str = ""
    drug_name: str | None = None
    drug_name_conf: float = Field(ge=0, le=1)
    strength: str | None = None
    strength_conf: float = Field(ge=0, le=1)
    frequency_code: str | None = None
    frequency_conf: float = Field(ge=0, le=1)
    as_needed: bool
    food_timing: FoodTiming | None = None
    food_timing_conf: float = Field(ge=0, le=1)
    duration_days: int | None = Field(default=None, ge=0)
    duration_conf: float = Field(ge=0, le=1)
    uncertain_fields: list[str]

class PrescriptionExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    medicines: list[MedicineExtraction]

class StripExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    printed_drug_name: str | None = None
    printed_drug_name_conf: float = Field(ge=0, le=1)
    printed_strength: str | None = None
    printed_strength_conf: float = Field(ge=0, le=1)

class CaseCreate(BaseModel):
    language: Literal["en", "hi", "mr"] = "en"
    consent_given: bool

