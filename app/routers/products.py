from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Product
from app.schemas import ProductCreate, ProductRead, ProductUpdate


router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    database: Session = Depends(get_db),
) -> Product:
    product = Product(
        productname=payload.productname,
        description=payload.description,
    )
    database.add(product)
    database.commit()
    database.refresh(product)
    return product


@router.get("", response_model=list[ProductRead])
def get_products(database: Session = Depends(get_db)) -> list[Product]:
    return list(database.scalars(select(Product).order_by(Product.id)).all())


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: int, database: Session = Depends(get_db)) -> Product:
    product = database.get(Product, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


@router.put("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    database: Session = Depends(get_db),
) -> Product:
    product = database.get(Product, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    product.productname = payload.productname
    product.description = payload.description
    database.commit()
    database.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, database: Session = Depends(get_db)) -> Response:
    product = database.get(Product, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    database.delete(product)
    database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)