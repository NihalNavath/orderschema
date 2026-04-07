from openenv.core.env_server.types import Action, Observation
from pydantic import Field


class OrderschemaAction(Action):
    message: str = Field(...)


class OrderschemaObservation(Observation):
    echoed_message: str = Field(default="")
    message_length: int = Field(default=0)

    target: list = Field(default_factory=list)
    prediction: list = Field(default_factory=list)

    model_config = {
        "extra": "allow"
    }