from datetime import date

from pydantic import BaseModel, Field, model_validator


class AnalysisRequest(BaseModel):
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    fee_bps: float = Field(default=10, ge=0, le=500, allow_inf_nan=False)
    slippage_bps: float = Field(default=5, ge=0, le=500, allow_inf_nan=False)
    min_hold: int = Field(default=10, ge=1, le=250)
    confirmation: int = Field(default=3, ge=1, le=30)
    max_trades: int = Field(default=30, ge=2, le=500)
    entry_probability: float = Field(
        default=0.65, ge=0.51, le=0.95, allow_inf_nan=False
    )
    exit_probability: float = Field(default=0.35, ge=0.05, le=0.49, allow_inf_nan=False)
    risk_free_rate: float = Field(default=0, ge=0, le=0.25, allow_inf_nan=False)

    @model_validator(mode="after")
    def periods(self):
        if not self.train_start < self.train_end < self.test_start < self.test_end:
            raise ValueError(
                "Les périodes doivent être ordonnées, sans chevauchement : entraînement puis test."
            )
        return self
