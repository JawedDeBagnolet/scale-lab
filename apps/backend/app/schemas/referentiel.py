from pydantic import BaseModel


class NicheOut(BaseModel):
    id: int
    label: str
    model_config = {"from_attributes": True}


class MarcheOut(BaseModel):
    code: str
    label: str
    actif: bool
    langue: str | None
    fuseau: str | None
    model_config = {"from_attributes": True}
