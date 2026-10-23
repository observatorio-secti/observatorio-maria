from http import HTTPStatus

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from observatorio_maria.database import get_session
from observatorio_maria.schemas import HealthCheck

router = APIRouter(prefix='/health', tags=['health'])


@router.get('', status_code=HTTPStatus.OK, response_model=HealthCheck)
def check_health(session: Session = Depends(get_session)):
    session.execute(text('SELECT 1'))
    return HealthCheck(status='ok', database='connected')
