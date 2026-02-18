from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.database import get_db
from app.models.form import Form, FormSubmission, FormStatus


router = APIRouter()


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


@router.delete("/delete/{form_id}")
def delete_form(form_id: int, db: Session = Depends(get_db)):
    """Delete a form"""

    form = db.query(Form).filter(Form.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")

    db.delete(form)
    db.commit()

    return {"success": True, "message": "Form deleted"}


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


class UpdateSubmissionStatus(BaseModel):
    status: str


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
