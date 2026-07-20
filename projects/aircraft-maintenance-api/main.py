"""
Aircraft Maintenance Log API
Async FastAPI service for managing aircraft maintenance records.
Routes maintenance data through a real PostgreSQL backend with proper ORM, validation, and error handling.

Production-ready: connection pooling, transaction safety, proper HTTP semantics, openapi docs.
"""

from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import select, desc, func, ForeignKey, CheckConstraint, UniqueConstraint, Index, and_, or_, text
from sqlalchemy.types import String, Integer, Numeric, Date, DateTime, Boolean, Enum as SQLEnum
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import date, datetime
from typing import Optional, List, AsyncGenerator
import os
from enum import Enum as PyEnum

# =============================================================================
#  CONFIG & ENGINE
# =============================================================================

# Read DATABASE_URL from environment (format: postgresql+asyncpg://user:password@host:port/dbname)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/maintenance_log")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

# =============================================================================
#  ORM MODELS (sync with schema.sql)
# =============================================================================

class TechRoleEnum(str, PyEnum):
    Performer = "Performer"
    Inspector = "Inspector"
    Supervisor = "Supervisor"

class AircraftModel(Base):
    __tablename__ = "aircraft_model"
    model_id: Mapped[int] = mapped_column(primary_key=True)
    manufacturer: Mapped[str] = mapped_column(String(60), nullable=False)
    model_name: Mapped[str] = mapped_column(String(60), nullable=False)
    type_category: Mapped[str] = mapped_column(String(30), nullable=False)
    typical_seats: Mapped[Optional[int]] = mapped_column(Integer)
    __table_args__ = (
        UniqueConstraint('manufacturer', 'model_name'),
        CheckConstraint("type_category IN ('SEP','MEP','Turboprop','Jet','Helicopter')"),
    )

class PartCatalog(Base):
    __tablename__ = "part_catalog"
    part_number: Mapped[str] = mapped_column(String(40), primary_key=True)
    component_type: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(String(120), nullable=False)
    is_life_limited: Mapped[bool] = mapped_column(Boolean, default=False)
    default_life_limit_hours: Mapped[Optional[float]] = mapped_column(Numeric(10, 1))

class Aircraft(Base):
    __tablename__ = "aircraft"
    aircraft_id: Mapped[int] = mapped_column(primary_key=True)
    registration_number: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    model_id: Mapped[int] = mapped_column(ForeignKey('aircraft_model.model_id'), nullable=False)
    msn: Mapped[Optional[str]] = mapped_column(String(30), unique=True)
    total_airframe_hours: Mapped[float] = mapped_column(Numeric(10, 1), default=0.0)
    total_airframe_cycles: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default='Active')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    __table_args__ = (
        CheckConstraint("total_airframe_hours >= 0"),
        CheckConstraint("total_airframe_cycles >= 0"),
        CheckConstraint("status IN ('Active','In Maintenance','Stored','Retired')"),
    )

class Component(Base):
    __tablename__ = "component"
    component_id: Mapped[int] = mapped_column(primary_key=True)
    serial_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    part_number: Mapped[str] = mapped_column(ForeignKey('part_catalog.part_number'), nullable=False)
    current_aircraft_id: Mapped[Optional[int]] = mapped_column(ForeignKey('aircraft.aircraft_id'))
    time_since_new_hours: Mapped[float] = mapped_column(Numeric(10, 1), default=0.0)
    time_since_new_cycles: Mapped[int] = mapped_column(Integer, default=0)
    life_limit_hours: Mapped[Optional[float]] = mapped_column(Numeric(10, 1))
    status: Mapped[str] = mapped_column(String(20), default='In Stock')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    __table_args__ = (
        CheckConstraint("time_since_new_hours >= 0"),
        CheckConstraint("time_since_new_cycles >= 0"),
        CheckConstraint("life_limit_hours IS NULL OR life_limit_hours > 0"),
        CheckConstraint("status IN ('Installed','In Stock','Removed','Scrapped')"),
    )

class Technician(Base):
    __tablename__ = "technician"
    technician_id: Mapped[int] = mapped_column(primary_key=True)
    license_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    certification_type: Mapped[str] = mapped_column(String(40), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(120), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    __table_args__ = (
        CheckConstraint("certification_type IN ('A&P','IA','Avionics','Repairman')"),
    )

class MaintenanceEvent(Base):
    __tablename__ = "maintenance_event"
    event_id: Mapped[int] = mapped_column(primary_key=True)
    aircraft_id: Mapped[int] = mapped_column(ForeignKey('aircraft.aircraft_id'), nullable=False)
    component_id: Mapped[Optional[int]] = mapped_column(ForeignKey('component.component_id'))
    event_date: Mapped[date] = mapped_column(Date, default=func.current_date())
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    aircraft_hours_at_event: Mapped[float] = mapped_column(Numeric(10, 1), nullable=False)
    component_hours_at_event: Mapped[Optional[float]] = mapped_column(Numeric(10, 1))
    next_due_hours: Mapped[Optional[float]] = mapped_column(Numeric(10, 1))
    next_due_date: Mapped[Optional[date]] = mapped_column(Date)
    work_status: Mapped[str] = mapped_column(String(20), default='Completed')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    __table_args__ = (
        CheckConstraint("aircraft_hours_at_event >= 0"),
        CheckConstraint("component_hours_at_event IS NULL OR component_hours_at_event >= 0"),
        CheckConstraint("next_due_hours IS NULL OR next_due_hours >= 0"),
        CheckConstraint("component_id IS NOT NULL OR component_hours_at_event IS NULL"),
        CheckConstraint("event_type IN ('Scheduled Inspection','Unscheduled Repair','Overhaul','Replacement','Airworthiness Directive','Modification')"),
        CheckConstraint("work_status IN ('Open','Completed','Deferred')"),
    )

class EventTechnician(Base):
    __tablename__ = "event_technician"
    event_id: Mapped[int] = mapped_column(ForeignKey('maintenance_event.event_id'), primary_key=True)
    technician_id: Mapped[int] = mapped_column(ForeignKey('technician.technician_id'), primary_key=True)
    role: Mapped[TechRoleEnum] = mapped_column(SQLEnum(TechRoleEnum), nullable=False)

class ComponentInstallation(Base):
    __tablename__ = "component_installation"
    installation_id: Mapped[int] = mapped_column(primary_key=True)
    component_id: Mapped[int] = mapped_column(ForeignKey('component.component_id'), nullable=False)
    aircraft_id: Mapped[int] = mapped_column(ForeignKey('aircraft.aircraft_id'), nullable=False)
    position: Mapped[str] = mapped_column(String(40), nullable=False)
    installed_date: Mapped[date] = mapped_column(Date, default=func.current_date())
    installed_hours: Mapped[float] = mapped_column(Numeric(10, 1), nullable=False)
    removed_date: Mapped[Optional[date]] = mapped_column(Date)
    removed_reason: Mapped[Optional[str]] = mapped_column(String(120))
    __table_args__ = (
        CheckConstraint("removed_date IS NULL OR removed_date >= installed_date"),
        CheckConstraint("removed_date IS NOT NULL OR removed_reason IS NULL"),
        # Note: the real "one open installation per component" rule is enforced by a
        # PARTIAL UNIQUE INDEX in schema.sql (uq_component_open_install), not here —
        # SQLAlchemy's UniqueConstraint can't express a WHERE-filtered index portably,
        # so this ORM model relies on schema.sql as the source of truth for that rule.
    )

# =============================================================================
#  PYDANTIC SCHEMAS (request/response validation)
# =============================================================================

class AircraftBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    registration_number: str = Field(..., min_length=1, max_length=10)
    model_id: int
    msn: Optional[str] = Field(None, max_length=30)
    total_airframe_hours: float = Field(default=0.0, ge=0)
    total_airframe_cycles: int = Field(default=0, ge=0)
    status: str = Field(default='Active', pattern='^(Active|In Maintenance|Stored|Retired)$')

class AircraftCreate(AircraftBase):
    pass

class AircraftResponse(AircraftBase):
    aircraft_id: int
    created_at: datetime
    updated_at: datetime

class ComponentBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    serial_number: str = Field(..., min_length=1, max_length=40)
    part_number: str = Field(..., max_length=40)
    current_aircraft_id: Optional[int] = None
    time_since_new_hours: float = Field(default=0.0, ge=0)
    time_since_new_cycles: int = Field(default=0, ge=0)
    life_limit_hours: Optional[float] = Field(None, gt=0)
    status: str = Field(default='In Stock', pattern='^(Installed|In Stock|Removed|Scrapped)$')

class ComponentCreate(ComponentBase):
    pass

class ComponentResponse(ComponentBase):
    component_id: int
    created_at: datetime
    updated_at: datetime

class TechnicianBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    license_number: str = Field(..., max_length=30)
    first_name: str = Field(..., max_length=50)
    last_name: str = Field(..., max_length=50)
    certification_type: str = Field(..., pattern='^(A&P|IA|Avionics|Repairman)$')
    email: Optional[str] = Field(None, max_length=120)
    is_active: bool = Field(default=True)

class TechnicianCreate(TechnicianBase):
    pass

class TechnicianResponse(TechnicianBase):
    technician_id: int
    created_at: datetime

class MaintenanceEventBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    aircraft_id: int
    component_id: Optional[int] = None
    event_date: date
    event_type: str = Field(..., pattern='^(Scheduled Inspection|Unscheduled Repair|Overhaul|Replacement|Airworthiness Directive|Modification)$')
    description: str = Field(..., max_length=255)
    aircraft_hours_at_event: float = Field(..., ge=0)
    component_hours_at_event: Optional[float] = Field(None, ge=0)
    next_due_hours: Optional[float] = Field(None, ge=0)
    next_due_date: Optional[date] = None
    work_status: str = Field(default='Completed', pattern='^(Open|Completed|Deferred)$')

class MaintenanceEventCreate(MaintenanceEventBase):
    pass

class MaintenanceEventResponse(MaintenanceEventBase):
    event_id: int
    created_at: datetime

class FleetStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    aircraft_id: int
    registration_number: str
    manufacturer: str
    model_name: str
    type_category: str
    total_airframe_hours: float
    status: str
    open_work_items: int

class OverdueInspectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_id: int
    registration_number: str
    event_type: str
    description: str
    next_due_hours: Optional[float]
    total_airframe_hours: float
    hours_overdue: Optional[float]
    next_due_date: Optional[date]
    work_status: str

class ComponentLocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    component_id: int
    serial_number: str
    component_type: str
    description: str
    status: str
    current_aircraft: Optional[str]
    position: Optional[str]
    installed_date: Optional[date]
    installed_hours: Optional[float]

# =============================================================================
#  FASTAPI APP & ROUTES
# =============================================================================

app = FastAPI(
    title="Aircraft Maintenance Log API",
    description="Manage aircraft maintenance records, track components, and ensure airworthiness compliance.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

# ---- AIRCRAFT ----

@app.post("/aircraft", response_model=AircraftResponse, status_code=status.HTTP_201_CREATED, tags=["Aircraft"])
async def create_aircraft(aircraft: AircraftCreate, db: AsyncSession = Depends(get_db)):
    """Create a new aircraft."""
    db_aircraft = Aircraft(**aircraft.model_dump())
    db.add(db_aircraft)
    try:
        await db.commit()
        await db.refresh(db_aircraft)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return db_aircraft

@app.get("/aircraft/{aircraft_id}", response_model=AircraftResponse, tags=["Aircraft"])
async def get_aircraft(aircraft_id: int, db: AsyncSession = Depends(get_db)):
    """Retrieve an aircraft by ID."""
    result = await db.execute(select(Aircraft).where(Aircraft.aircraft_id == aircraft_id))
    aircraft = result.scalar_one_or_none()
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    return aircraft

@app.get("/aircraft", response_model=List[AircraftResponse], tags=["Aircraft"])
async def list_aircraft(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: AsyncSession = Depends(get_db)):
    """List all aircraft with pagination."""
    result = await db.execute(select(Aircraft).offset(skip).limit(limit))
    return result.scalars().all()

@app.put("/aircraft/{aircraft_id}", response_model=AircraftResponse, tags=["Aircraft"])
async def update_aircraft(aircraft_id: int, aircraft: AircraftCreate, db: AsyncSession = Depends(get_db)):
    """Update an aircraft."""
    result = await db.execute(select(Aircraft).where(Aircraft.aircraft_id == aircraft_id))
    db_aircraft = result.scalar_one_or_none()
    if not db_aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    for key, value in aircraft.model_dump().items():
        setattr(db_aircraft, key, value)
    try:
        await db.commit()
        await db.refresh(db_aircraft)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return db_aircraft

# ---- COMPONENTS ----

@app.post("/components", response_model=ComponentResponse, status_code=status.HTTP_201_CREATED, tags=["Components"])
async def create_component(component: ComponentCreate, db: AsyncSession = Depends(get_db)):
    """Create a new component (part)."""
    db_component = Component(**component.model_dump())
    db.add(db_component)
    try:
        await db.commit()
        await db.refresh(db_component)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return db_component

@app.get("/components/{component_id}", response_model=ComponentResponse, tags=["Components"])
async def get_component(component_id: int, db: AsyncSession = Depends(get_db)):
    """Retrieve a component by ID."""
    result = await db.execute(select(Component).where(Component.component_id == component_id))
    component = result.scalar_one_or_none()
    if not component:
        raise HTTPException(status_code=404, detail="Component not found")
    return component

@app.get("/components", response_model=List[ComponentResponse], tags=["Components"])
async def list_components(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: AsyncSession = Depends(get_db)):
    """List all components with pagination."""
    result = await db.execute(select(Component).offset(skip).limit(limit))
    return result.scalars().all()

# ---- TECHNICIANS ----

@app.post("/technicians", response_model=TechnicianResponse, status_code=status.HTTP_201_CREATED, tags=["Technicians"])
async def create_technician(technician: TechnicianCreate, db: AsyncSession = Depends(get_db)):
    """Create a new technician."""
    db_technician = Technician(**technician.model_dump())
    db.add(db_technician)
    try:
        await db.commit()
        await db.refresh(db_technician)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return db_technician

@app.get("/technicians/{technician_id}", response_model=TechnicianResponse, tags=["Technicians"])
async def get_technician(technician_id: int, db: AsyncSession = Depends(get_db)):
    """Retrieve a technician by ID."""
    result = await db.execute(select(Technician).where(Technician.technician_id == technician_id))
    technician = result.scalar_one_or_none()
    if not technician:
        raise HTTPException(status_code=404, detail="Technician not found")
    return technician

@app.get("/technicians", response_model=List[TechnicianResponse], tags=["Technicians"])
async def list_technicians(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: AsyncSession = Depends(get_db)):
    """List all technicians with pagination."""
    result = await db.execute(select(Technician).offset(skip).limit(limit))
    return result.scalars().all()

# ---- MAINTENANCE EVENTS ----

@app.post("/events", response_model=MaintenanceEventResponse, status_code=status.HTTP_201_CREATED, tags=["Events"])
async def create_event(event: MaintenanceEventCreate, db: AsyncSession = Depends(get_db)):
    """Record a maintenance event."""
    db_event = MaintenanceEvent(**event.model_dump())
    db.add(db_event)
    try:
        await db.commit()
        await db.refresh(db_event)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return db_event

@app.get("/events/{event_id}", response_model=MaintenanceEventResponse, tags=["Events"])
async def get_event(event_id: int, db: AsyncSession = Depends(get_db)):
    """Retrieve a maintenance event by ID."""
    result = await db.execute(select(MaintenanceEvent).where(MaintenanceEvent.event_id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

@app.get("/events", response_model=List[MaintenanceEventResponse], tags=["Events"])
async def list_events(aircraft_id: Optional[int] = None, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: AsyncSession = Depends(get_db)):
    """List maintenance events, optionally filtered by aircraft."""
    query = select(MaintenanceEvent)
    if aircraft_id:
        query = query.where(MaintenanceEvent.aircraft_id == aircraft_id)
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()

# ---- REPORTS (SQL VIEWS) ----

@app.get("/reports/fleet-status", response_model=List[FleetStatusResponse], tags=["Reports"])
async def fleet_status(db: AsyncSession = Depends(get_db)):
    """Fleet at a glance: each airframe, model, hours, open work count. Reuses v_fleet_status."""
    result = await db.execute(text("SELECT * FROM v_fleet_status ORDER BY aircraft_id"))
    return [dict(row._mapping) for row in result]

@app.get("/reports/overdue-inspections", response_model=List[OverdueInspectionResponse], tags=["Reports"])
async def overdue_inspections(db: AsyncSession = Depends(get_db)):
    """Overdue inspections: open/deferred work past hour or date threshold. Reuses v_overdue_inspections."""
    result = await db.execute(text("SELECT * FROM v_overdue_inspections ORDER BY event_id"))
    return [dict(row._mapping) for row in result]

@app.get("/reports/component-location", response_model=List[ComponentLocationResponse], tags=["Reports"])
async def component_location(db: AsyncSession = Depends(get_db)):
    """Where every component currently is (spares show NULL aircraft). Reuses v_component_location."""
    result = await db.execute(text("SELECT * FROM v_component_location ORDER BY component_id"))
    return [dict(row._mapping) for row in result]

# ---- HEALTH ----

@app.get("/health", tags=["Health"])
async def health(db: AsyncSession = Depends(get_db)):
    """API health check."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
