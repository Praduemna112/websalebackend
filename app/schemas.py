from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    productname: str = Field(min_length=1, max_length=45)
    description: str | None = Field(default=None, max_length=255)


class ProductUpdate(BaseModel):
    productname: str = Field(min_length=1, max_length=45)
    description: str | None = Field(default=None, max_length=255)


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    productname: str | None
    description: str | None
