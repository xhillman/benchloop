from typing import Any

from pydantic import BaseModel, ConfigDict


class AuthenticatedPrincipal(BaseModel):
    subject: str
    claims: dict[str, Any]

    model_config = ConfigDict(extra="forbid")
