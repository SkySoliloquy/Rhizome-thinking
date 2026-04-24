"""Source type management API routes."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from rhizome.core.source_config import get_source_config_manager, SourceTypeConfig

router = APIRouter()


class SourceTypeResponse(BaseModel):
    """Response for a source type."""
    id: str
    name: str
    description: Optional[str] = None
    is_builtin: bool


class CreateSourceRequest(BaseModel):
    """Request to create a custom source type."""
    name: str = Field(..., min_length=1, max_length=50, description="来源类型名称")
    description: Optional[str] = Field(default=None, max_length=200, description="来源类型描述")


class UpdateSourceRequest(BaseModel):
    """Request to update a custom source type."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=50, description="新的来源类型名称")
    description: Optional[str] = Field(default=None, max_length=200, description="新的来源类型描述")


def _convert_to_response(source: SourceTypeConfig) -> SourceTypeResponse:
    """Convert SourceTypeConfig to response model."""
    return SourceTypeResponse(
        id=source.id,
        name=source.name,
        description=source.description,
        is_builtin=source.is_builtin
    )


@router.get("/sources", response_model=list[SourceTypeResponse])
async def get_all_sources():
    """Get all available source types (built-in + custom)."""
    manager = get_source_config_manager()
    sources = manager.get_all_sources()
    return [_convert_to_response(s) for s in sources]


@router.post("/sources", response_model=SourceTypeResponse)
async def create_custom_source(request: CreateSourceRequest):
    """Create a new custom source type.
    
    The ID will be auto-generated from the name.
    """
    manager = get_source_config_manager()
    try:
        source = manager.add_custom_source(
            name=request.name,
            description=request.description
        )
        return _convert_to_response(source)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/sources/{source_id}", response_model=SourceTypeResponse)
async def update_custom_source(source_id: str, request: UpdateSourceRequest):
    """Update an existing custom source type.
    
    Built-in source types cannot be modified.
    """
    manager = get_source_config_manager()
    try:
        source = manager.update_custom_source(
            source_id=source_id,
            name=request.name,
            description=request.description
        )
        if not source:
            raise HTTPException(status_code=404, detail=f"Source type '{source_id}' not found")
        return _convert_to_response(source)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/sources/{source_id}")
async def delete_custom_source(source_id: str):
    """Delete a custom source type.
    
    Built-in source types cannot be deleted.
    """
    manager = get_source_config_manager()
    try:
        deleted = manager.delete_custom_source(source_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Source type '{source_id}' not found")
        return {"message": f"Source type '{source_id}' deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
