from pydantic import BaseModel


class ImageUploadRead(BaseModel):
    url: str
