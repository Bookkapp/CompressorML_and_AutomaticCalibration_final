"""Explicit complete-day splits and reasoned Reference-only exclusions."""
from datetime import date,datetime
from pydantic import BaseModel,ConfigDict,Field,model_validator
from .automatic_reference import PreparationRequest


class Exclusion(BaseModel):
    model_config=ConfigDict(extra="forbid")
    module:int=Field(ge=1,le=8)
    start:datetime
    end:datetime
    reason:str=Field(min_length=8,max_length=1000)

    @model_validator(mode="after")
    def valid(self):
        if self.start.tzinfo or self.end.tzinfo or self.end<=self.start:
            raise ValueError("Exclusion uses ordered source-local times")
        if any(t.second or t.microsecond for t in (self.start,self.end)):
            raise ValueError("Exclusion must use minute boundaries")
        self.reason=self.reason.strip()
        if len(self.reason)<8: raise ValueError("Explain the exclusion in at least 8 characters")
        return self


class ContextPreparationRequest(PreparationRequest):
    reference_start:date|None=None
    shadow_start:date|None=None
    shadow_end:date|None=None
    parent_profile_id:str|None=Field(default=None,min_length=64,max_length=64)
    exclusions:list[Exclusion]=Field(default_factory=list,max_length=50)
    validation_only:bool=False

    @model_validator(mode="after")
    def split(self):
        values=(self.reference_start,self.shadow_start,self.shadow_end)
        if any(values) and not all(values): raise ValueError("Specify all three split dates")
        if all(values):
            if not 7<=(self.shadow_start-self.reference_start).days<=90:
                raise ValueError("Reference must span 7..90 complete days")
            if (self.shadow_end-self.shadow_start).days!=3:
                raise ValueError("Shadow must span three separate complete days")
        if self.exclusions and not self.parent_profile_id:
            raise ValueError("Inspect a saved Profile before excluding Reference intervals")
        if self.validation_only and (not self.parent_profile_id or self.exclusions or any(values)):
            raise ValueError("Validation uses a frozen reviewed Profile and the latest three complete future days")
        return self
