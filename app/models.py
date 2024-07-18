from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Process(Base):
    __tablename__ = "processes"

    id = Column(Integer, primary_key=True, index=True)
    container_name = Column(String, index=True)
    script_type = Column(String)
    result = Column(Text)

Base.metadata.create_all(bind=engine)
