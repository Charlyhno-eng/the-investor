from typing import Literal

from pydantic import BaseModel, Field


class ImportRequest(BaseModel):
    symbol: str = Field(
        min_length=1, max_length=24, pattern=r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,23}$"
    )
    category: Literal["stock", "crypto"] = "stock"
