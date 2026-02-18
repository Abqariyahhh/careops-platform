from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.database import get_db
from app.models.form import Form, FormSubmission, FormStatus



router = APIRouter()



# ─────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────

class FormFieldSchema(BaseModel):
    label: str
    field_type: str  # "text", "email", "phone", "date", "select", "textarea"
    required: bool = False
    options: Optional[List[str]] = None  # For select fields

class CreateFormSchema(BaseModel):
    name: str
    description: Optional[str] = None
    fields: List[FormFieldSchema]
    external_url: Optional[str] = None

class UpdateSubmissionStatus(BaseModel):
    status: str  # "pending", "completed", "overdue"



# ─────────────────────────────────────────
# FORM CRUD
# ─────────────────────────────────────────

@router.post("/create/{workspace_id}")
def create_form(workspace_id: int, form_data: CreateFormSchema, db: Session = Depends(get_db)):
    """Create a new form for workspace"""

    new_form = Form(
        workspace_id=workspace_id,
        name=form_data.name,
        description=form_data.description,
        fields=[f.dict() for f in form_data.fields],
        external_url=form_data.external_url,
        is_active=True,
        created_at=datetime.utcnow()
    )

    db.add(new_form)
    db.commit()
    db.refresh(new_form)

    return {
        "success": True,
        "form_id": new_form.id,
        "name": new_form.name,
        "fields": new_form.fields,
        "created_at": new_form.created_at.isoformat()
    }


@router.get("/all/{workspace_id}")
def get_all_forms(workspace_id: int, db: Session = Depends(get_db)):
    """Get all forms for workspace"""

    forms = db.query(Form).filter(
        Form.workspace_id == workspace_id
    ).all()

    return [
        {
            "id": f.id,
            "name": f.name,
            "description": f.description,
            "fields": f.fields,
            "external_url": f.external_url,
            "is_active": f.is_active,
            "created_at": f.created_at.isoformat()
        }
        for f in forms
    ]


@router.patch("/update/{form_id}")
def update_form(form_id: int, form_data: CreateFormSchema, db: Session = Depends(get_db)):
    """Update an existing form"""

    form = db.query(Form).filter(Form.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")

    form.name = form_data.name
    form.description = form_data.description
    form.fields = [f.dict() for f in form_data.fields]
    form.external_url = form_data.external_url

    db.commit()
    db.refresh(form)

    return {
        "success": True,
        "form_id": form.id,
        "name": form.name,
        "fields": form.fields
    }


@router.delete("/delete/{form_id}")
def delete_form(form_id: int, db: Session = Depends(get_db)):
    """Delete a form"""

    form = db.query(Form).filter(Form.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")

    db.delete(form)
    db.commit()

    return {"success": True, "message": f"Form '{form.name}' deleted"}



# ─────────────────────────────────────────
# SUBMISSIONS
# ─────────────────────────────────────────

@router.get("/submissions/{workspace_id}")
def get_all_submissions(workspace_id: int, db: Session = Depends(get_db)):
    """Get all form submissions for workspace"""

    submissions = db.query(FormSubmission).join(FormSubmission.form).filter(
        FormSubmission.form.has(workspace_id=workspace_id)
    ).order_by(FormSubmission.submitted_at.desc()).all()

    return [
        {
            "id": sub.id,
            "form_id": sub.form_id,
            "form_name": sub.form.name,
            "data": sub.form_data,
            "status": sub.status.value,
            "created_at": sub.submitted_at.isoformat()
        }
        for sub in submissions
    ]


@router.get("/submission/{submission_id}")
def get_submission_details(submission_id: int, db: Session = Depends(get_db)):
    """Get single submission details"""

    submission = db.query(FormSubmission).filter(FormSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    return {
        "id": submission.id,
        "form": {
            "id": submission.form.id,
            "name": submission.form.name,
            "description": submission.form.description
        },
        "data": submission.form_data,
        "status": submission.status.value,
        "created_at": submission.submitted_at.isoformat()
    }


@router.patch("/submission/{submission_id}/status")
def update_submission_status(
    submission_id: int,
    update: UpdateSubmissionStatus,
    db: Session = Depends(get_db)
):
    """Update submission status"""

    submission = db.query(FormSubmission).filter(FormSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if update.status == "pending":
        submission.status = FormStatus.PENDING
    elif update.status == "completed":
        submission.status = FormStatus.COMPLETED
    elif update.status == "overdue":
        submission.status = FormStatus.OVERDUE
    else:
        raise HTTPException(status_code=400, detail="Invalid status. Use: pending, completed, or overdue")

    db.commit()

    return {
        "success": True,
        "submission_id": submission.id,
        "status": submission.status.value
    }


@router.delete("/submission/{submission_id}")
def delete_submission(submission_id: int, db: Session = Depends(get_db)):
    """Delete submission"""

    submission = db.query(FormSubmission).filter(FormSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    db.delete(submission)
    db.commit()

    return {"success": True, "message": "Submission deleted"}
