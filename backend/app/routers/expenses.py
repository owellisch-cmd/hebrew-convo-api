from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Document, Expense, User
from app.schemas import DocumentOut, ExpenseIn, ExpenseOut, ExpenseSummary
from app.services.parsing import parse_expense_file

router = APIRouter(prefix="/expenses", tags=["expenses"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_expense_file(
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    try:
        items = parse_expense_file(file.filename or "upload", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not items:
        raise HTTPException(
            status_code=422,
            detail="Could not find any dollar amounts in this file. "
            "Try a CSV with an 'amount' column, or add expenses manually.",
        )

    document = Document(user_id=user.id, filename=file.filename or "upload", content_type=file.content_type)
    db.add(document)
    db.flush()

    for item in items:
        db.add(
            Expense(
                user_id=user.id,
                document_id=document.id,
                category=item["category"],
                amount=item["amount"],
                description=item.get("description"),
                incurred_on=item.get("incurred_on"),
            )
        )
    db.commit()
    db.refresh(document)
    return document


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Document).filter(Document.user_id == user.id).all()


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()


@router.get("", response_model=list[ExpenseOut])
def list_expenses(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Expense).filter(Expense.user_id == user.id).order_by(Expense.id.desc()).all()


@router.get("/summary", response_model=list[ExpenseSummary])
def expense_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    expenses = db.query(Expense).filter(Expense.user_id == user.id).all()
    totals: dict[str, float] = {}
    for expense in expenses:
        totals[expense.category] = totals.get(expense.category, 0) + expense.amount
    return [ExpenseSummary(category=cat, total=total) for cat, total in totals.items()]


@router.post("/manual", response_model=ExpenseOut, status_code=201)
def add_manual_expense(
    payload: ExpenseIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    expense = Expense(user_id=user.id, **payload.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/manual/{expense_id}", status_code=204)
def delete_manual_expense(
    expense_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    expense = (
        db.query(Expense)
        .filter(Expense.id == expense_id, Expense.user_id == user.id)
        .first()
    )
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()
