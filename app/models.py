from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Product(Base):
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(primary_key=True)
    productname: Mapped[str | None] = mapped_column(String(45), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
