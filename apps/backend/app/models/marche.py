from sqlalchemy import Boolean, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Marche(Base):
    __tablename__ = "marches"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
    # server_default : le seed SQL insere sans preciser `actif`
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    langue: Mapped[str | None] = mapped_column(String(5))
    fuseau: Mapped[str | None] = mapped_column(String(50))
