from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from observatorio_maria.database import get_session
from observatorio_maria.schemas import HealthCheck

router = APIRouter(prefix='/health', tags=['health'])


@router.get('', status_code=HTTPStatus.OK, response_model=HealthCheck)
async def check_health(
    session: Annotated[AsyncSession, Depends(get_session)],
):
    await session.execute(text('SELECT 1'))
    return HealthCheck(status='ok', database='connected')
