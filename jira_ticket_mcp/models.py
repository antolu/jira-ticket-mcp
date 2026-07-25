from __future__ import annotations

import enum

import pydantic
import pydantic.alias_generators


class HttpMethod(enum.StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class JiraModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        alias_generator=pydantic.alias_generators.to_camel,
        populate_by_name=True,
        extra="ignore",
    )


class Myself(JiraModel):
    account_id: str
    display_name: str
    email_address: str | None = None
    active: bool
