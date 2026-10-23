from http import HTTPStatus

from fastapi import FastAPI

from observatorio_maria.routers import health
from observatorio_maria.schemas import Message

app = FastAPI(
    title='Observatório Maria',
    version='0.1.0',
    description='API do Observatório Maria',
)

app.include_router(health.router)


@app.get('/', status_code=HTTPStatus.OK, response_model=Message)
def read_root():
    return Message(message='Olá Mundo!')
