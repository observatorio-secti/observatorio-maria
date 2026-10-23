from typing import Annotated

from fastapi import APIRouter, Depends

from observatorio_maria.llm.registry import ModelRegistry, get_model_registry
from observatorio_maria.schemas import ModelList

router = APIRouter(prefix='/models', tags=['models'])


@router.get('', response_model=ModelList)
async def list_models(
    registry: Annotated[ModelRegistry, Depends(get_model_registry)],
):
    return {
        'models': [
            {'tier': registered.tier, 'model_name': registered.name}
            for registered in registry.all()
        ]
    }
