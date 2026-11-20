from sqlalchemy import Column,Integer,String,JSON,DateTime,ForeignKey,Text,UniqueConstraint
from datetime import datetime,timezone
from src.config.database import Base
class User(Base):
    __tablename__='users'
    id=Column(Integer,primary_key=True);email=Column(String(120),unique=True,nullable=False);password=Column(String(300),nullable=False);role=Column(String(20),nullable=False)
class Relation(Base):
    __tablename__='relations'
    id=Column(Integer,primary_key=True);code=Column(String(80),unique=True,nullable=False);title=Column(String(160),nullable=False);attributes=Column(JSON,nullable=False);note=Column(String(300),default='')
class Dependency(Base):
    __tablename__='dependencies'
    id=Column(Integer,primary_key=True);relation_id=Column(Integer,ForeignKey('relations.id'),nullable=False);lhs=Column(JSON,nullable=False);rhs=Column(JSON,nullable=False);note=Column(String(300),default='')
class Report(Base):
    __tablename__='reports'
    id=Column(Integer,primary_key=True);name=Column(String(120),nullable=False);relation_id=Column(Integer,ForeignKey('relations.id'),nullable=False)
    status=Column(String(20),nullable=False,default='queued');input_snapshot=Column(JSON,nullable=False);result=Column(JSON,nullable=True);error=Column(Text,nullable=True)
    created_at=Column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class Audit(Base):
    __tablename__='audit_logs'
    id=Column(Integer,primary_key=True);actor=Column(String(120),nullable=False);action=Column(String(160),nullable=False);created_at=Column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class SampleRow(Base):
    __tablename__='sample_rows'
    id=Column(Integer,primary_key=True);report_id=Column(Integer,ForeignKey('reports.id'),nullable=False);subrelation=Column(Integer,nullable=False);values=Column('row_values',JSON,nullable=False)
class Correction(Base):
    __tablename__='corrections'
    id=Column(Integer,primary_key=True);report_id=Column(Integer,ForeignKey('reports.id'),nullable=False);row_id=Column(Integer,nullable=False);subrelation=Column(Integer,nullable=False)
    old_values=Column(JSON,nullable=True);new_values=Column(JSON,nullable=True);batch_id=Column(Integer,nullable=True);status=Column(String(20),nullable=False,default='pending')
    created_at=Column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class Assembly(Base):
    __tablename__='assemblies'
    __table_args__=(UniqueConstraint('report_id','version'),)
    id=Column(Integer,primary_key=True);report_id=Column(Integer,ForeignKey('reports.id'),nullable=False);version=Column(Integer,nullable=False)
    rows=Column('assembled_rows',JSON,nullable=False);sample_snapshot=Column(JSON,nullable=False);batch_id=Column(Integer,nullable=True)
    created_at=Column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class AssemblyBatch(Base):
    __tablename__='assembly_batches'
    id=Column(Integer,primary_key=True);report_id=Column(Integer,ForeignKey('reports.id'),nullable=False);base_version=Column(Integer,nullable=False)
    status=Column(String(20),nullable=False,default='processing');correction_ids=Column(JSON,nullable=False)
    created_at=Column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class AssemblyState(Base):
    __tablename__='assembly_states'
    report_id=Column(Integer,ForeignKey('reports.id'),primary_key=True);version=Column(Integer,nullable=False,default=0)
