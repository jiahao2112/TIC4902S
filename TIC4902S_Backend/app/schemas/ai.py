from typing import Literal, List, Union
from datetime import date

from pydantic import BaseModel, Field


class FieldType(BaseModel):
    type: str


class QuizRequest(BaseModel):
    country: str
    day: int

class JsonContent(BaseModel):
    type: str = "json"
    json_: QuizRequest = Field(alias="json")

class GeneratedLocation(BaseModel):
    destination: str
    longitude: float
    latitude: float


class GeneratedPlan(BaseModel):
    destinations: List[GeneratedLocation]

class LocationFormat(BaseModel):
    destination: FieldType = FieldType(type="string")
    longitude: FieldType = FieldType(type="number")
    latitude: FieldType = FieldType(type="number")

class ItemFormat(BaseModel):
    type: str = "object"
    properties: LocationFormat = LocationFormat()
    required: list[str] = list(LocationFormat.model_fields.keys())
    additionalProperties: bool = False

class ItemsFormat(BaseModel):
    type: str = "array"
    items: ItemFormat = ItemFormat()

class PlanFormat(BaseModel):
    destinations: ItemsFormat = ItemsFormat()

class Schema(BaseModel):
    type: str = "object"
    properties: PlanFormat = PlanFormat()
    additionalProperties: bool = False
    required: list[str] = list(PlanFormat.model_fields.keys())


class JsonSchema(BaseModel):
    name: str = "Generated_Plan"
    strict: bool = True
    schema_def: Schema = Field(default=Schema(), alias="schema")

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: Union[List[QuizRequest], str]

class SetupMessage(ChatMessage):
    role: str = "system"
    content: str = (
        "You are a helpful travel assistant. You will receive quiz-style input in JSON format (e.g. {\"country\": \"singapore\",\"day\":2}). Interpret this JSON as the user's request. Always respond ONLY with valid JSON that matches the schema below. For each day specified in the input, output exactly one destination object. If \"day\": 1, return 1 destination. If \"day\": 2, return 2 destination, etc.  Do not include any extra text, explanations, or formatting."
    )





class ChatResponse(BaseModel):
    content: List[GeneratedLocation]


class ChatResponseFormat(BaseModel):
    type: str = "json_schema"
    json_schema: JsonSchema = JsonSchema()


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: str = "qwen/qwen3.8-27b"
    temperature: float = 0.7
    max_tokens: int = 1_024
    response_format: ChatResponseFormat = ChatResponseFormat()
