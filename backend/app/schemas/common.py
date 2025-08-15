from pydantic import BaseModel, field_validator
from enum import Enum

class DeadlineType(str, Enum):
    SECOND_SUNDAY = "second_sunday"
    FOURTH_SUNDAY = "fourth_sunday"

class EnumNormalizerMixin(BaseModel):
    @field_validator("*", mode='before')
    @classmethod
    def normalize_enum(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v
