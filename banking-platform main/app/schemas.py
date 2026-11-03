"""Shared wire schemas. Amounts use exact decimal strings, never floats."""
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class AmountRequest(BaseModel):
    account_id: str
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    request_id: UUID

    @field_validator("amount", mode="before")
    @classmethod
    def exact_money(cls, value):
        if isinstance(value, float):
            raise ValueError("Send money as a string to avoid binary float rounding")
        return value


class TransferRequest(BaseModel):
    from_account: str
    to_account: str
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    request_id: UUID

    @field_validator("amount", mode="before")
    @classmethod
    def exact_money(cls, value):
        if isinstance(value, float):
            raise ValueError("Send money as a string")
        return value

    @model_validator(mode="after")
    def distinct_accounts(self):
        if self.from_account == self.to_account:
            raise ValueError("Source and destination must differ")
        return self


class PrepareRequest(BaseModel):
    tx_id: UUID
    account_id: str
    role: Literal["DEBIT", "CREDIT"]
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=2)


class Phase2Request(BaseModel):
    tx_id: UUID

