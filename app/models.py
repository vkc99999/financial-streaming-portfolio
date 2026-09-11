from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Line(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=1, max_length=200)
    cost_center_id: str = Field(min_length=1, max_length=40)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class InvoiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supplier_id: str = Field(min_length=1, max_length=40)
    invoice_number: str = Field(min_length=1, max_length=80)
    issue_date: date
    due_date: date
    lines: list[Line] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def dates_ordered(self):
        if self.due_date < self.issue_date:
            raise ValueError("due_date cannot precede issue_date")
        return self


class DueDateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    due_date: date
