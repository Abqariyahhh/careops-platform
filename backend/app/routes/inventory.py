from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.inventory import InventoryItem


router = APIRouter()


@router.get("/all/{workspace_id}")
def get_all_inventory(workspace_id: int, db: Session = Depends(get_db)):
    """Get all inventory items for workspace"""
    
    items = db.query(InventoryItem).filter(
        InventoryItem.workspace_id == workspace_id
    ).order_by(InventoryItem.name).all()
    
    return [
        {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "quantity": item.quantity,
            "low_stock_threshold": item.low_stock_threshold,
            "unit": item.unit,
            "is_low_stock": item.quantity <= item.low_stock_threshold,
            "created_at": item.created_at.isoformat()
        }
        for item in items
    ]


class UpdateInventory(BaseModel):
    quantity: int


@router.patch("/{item_id}/quantity")
def update_inventory_quantity(
    item_id: int,
    update: UpdateInventory,
    db: Session = Depends(get_db)
):
    """Update inventory quantity"""
    
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    item.quantity = update.quantity
    db.commit()
    
    return {
        "success": True,
        "item_id": item.id,
        "quantity": item.quantity,
        "is_low_stock": item.quantity <= item.low_stock_threshold
    }


@router.delete("/{item_id}")
def delete_inventory_item(item_id: int, db: Session = Depends(get_db)):
    """Delete inventory item"""
    
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    db.delete(item)
    db.commit()
    
    return {"success": True, "message": "Item deleted"}
