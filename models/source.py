from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from database import Base

class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    articles = relationship("Article", back_populates="source_obj")
