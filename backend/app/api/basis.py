import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models.basis_item import BasisItem
from app.models.scheme_type import SchemeType
from app.models.user import User
from app.schemas.basis import BasisCreate, BasisRead, BasisUpdate

router = APIRouter(prefix="/basis", tags=["basis"])


def _allocate_basis_id(db: Session) -> str:
    for _ in range(32):
        candidate = f"BASIS_{uuid.uuid4().hex[:12].upper()}"
        if db.query(BasisItem).filter(BasisItem.basis_id == candidate).first() is None:
            return candidate
    raise HTTPException(status_code=500, detail="无法生成依据ID")


@router.get("", response_model=list[BasisRead])
def list_basis(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[BasisItem]:
    return db.query(BasisItem).order_by(BasisItem.id).all()


@router.post("", response_model=BasisRead, status_code=status.HTTP_201_CREATED)
def create_basis(
    body: BasisCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> BasisItem:
    scheme = db.get(SchemeType, body.scheme_type_id) if body.scheme_type_id is not None else None
    if body.scheme_type_id is not None and scheme is None:
        raise HTTPException(status_code=404, detail="方案类型不存在")
    row = BasisItem(
        basis_id=_allocate_basis_id(db),
        doc_type=body.doc_type,
        standard_no=body.standard_no,
        doc_name=body.doc_name,
        effect_status=body.effect_status,
        is_mandatory=body.is_mandatory,
        scheme_type_id=body.scheme_type_id,
        scheme_category=scheme.category if scheme is not None else body.scheme_category,
        scheme_name=scheme.name if scheme is not None else body.scheme_name,
        remark=body.remark,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/{basis_pk}", response_model=BasisRead)
def get_basis(
    basis_pk: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> BasisItem:
    row = db.get(BasisItem, basis_pk)
    if row is None:
        raise HTTPException(status_code=404, detail="编制依据不存在")
    return row


@router.patch("/{basis_pk}", response_model=BasisRead)
def update_basis(
    basis_pk: int,
    body: BasisUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> BasisItem:
    row = db.get(BasisItem, basis_pk)
    if row is None:
        raise HTTPException(status_code=404, detail="编制依据不存在")
    data = body.model_dump(exclude_unset=True)
    if "scheme_type_id" in data and data["scheme_type_id"] is not None:
        scheme = db.get(SchemeType, data["scheme_type_id"])
        if scheme is None:
            raise HTTPException(status_code=404, detail="方案类型不存在")
        data["scheme_category"] = scheme.category
        data["scheme_name"] = scheme.name
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{basis_pk}", status_code=status.HTTP_204_NO_CONTENT)
def delete_basis(
    basis_pk: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    row = db.get(BasisItem, basis_pk)
    if row is None:
        raise HTTPException(status_code=404, detail="编制依据不存在")
    db.delete(row)
    db.commit()
