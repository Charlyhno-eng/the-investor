from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class ImportRequest(BaseModel):
    symbol: str = Field(
        min_length=1, max_length=24, pattern=r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,23}$"
    )
    category: Literal["stock", "crypto"] = "stock"


class DividendStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_dividend: StrictBool
