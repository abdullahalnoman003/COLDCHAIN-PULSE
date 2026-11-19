from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, Role, User, Vehicle
from ..schemas import UserCreate, UserOut, VehicleCreate, VehicleOut
from ..security import client_ip, hash_secret, require_roles

router = APIRouter(tags=["users & vehicles"])


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, request: Request, admin: User = Depends(require_roles(Role.admin)),
                db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    u = User(email=email, name=data.name, role=data.role.value, password_hash=hash_secret(data.password))
    db.add(u)
    db.add(AuditLog(event="user_created", user_id=admin.id, email=email, ip=client_ip(request),
                    detail=f"role={data.role.value}"))
    db.commit()
    return u


@router.get("/users", response_model=list[UserOut])
def list_users(role: Role | None = None, _: User = Depends(require_roles(Role.admin, Role.dispatcher)),
               db: Session = Depends(get_db)):
    q = select(User).order_by(User.id)
    if role:
        q = q.where(User.role == role.value)
    return db.scalars(q).all()


@router.post("/vehicles", response_model=VehicleOut, status_code=201)
def create_vehicle(data: VehicleCreate, _: User = Depends(require_roles(Role.admin, Role.dispatcher)),
                   db: Session = Depends(get_db)):
    if db.scalar(select(Vehicle).where(Vehicle.plate == data.plate)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Plate already exists")
    v = Vehicle(plate=data.plate, label=data.label)
    db.add(v)
    db.commit()
    return v


@router.get("/vehicles", response_model=list[VehicleOut])
def list_vehicles(_: User = Depends(require_roles(Role.admin, Role.dispatcher, Role.auditor)),
                  db: Session = Depends(get_db)):
    return db.scalars(select(Vehicle).order_by(Vehicle.id)).all()
