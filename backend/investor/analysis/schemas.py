from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnalysisRequest(BaseModel):
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    fee_bps: float | None = Field(default=None, ge=0, le=500, allow_inf_nan=False)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def periods(self):
        if not self.train_start < self.train_end < self.test_start < self.test_end:
            raise ValueError(
                "Les périodes doivent être ordonnées, sans chevauchement : entraînement puis test."
            )
        return self
