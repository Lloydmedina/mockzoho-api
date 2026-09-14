from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Record(Base):
    __tablename__ = "records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    module: Mapped[str] = mapped_column(String(64), index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_time: Mapped[str] = mapped_column(String(40))
    modified_time: Mapped[str] = mapped_column(String(40), index=True)

    def to_zoho(self) -> dict[str, Any]:
        payload = dict(self.data)
        payload["id"] = self.id
        payload["Created_Time"] = self.created_time
        payload["Modified_Time"] = self.modified_time
        return payload
