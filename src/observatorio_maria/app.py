from http import HTTPStatus

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from observatorio_maria.llm.registry import ModelConfigurationError
from observatorio_maria.routers import conversations, health, models
from observatorio_maria.schemas import Message

# Exporta o .env para os.environ: os SDKs dos provedores de LLM leem suas
# credenciais (ex.: OPENAI_API_KEY) diretamente do ambiente.
load_dotenv()

app = FastAPI(
    title='Observatório Maria',
    version='0.1.0',
    description='API do Observatório Maria',
)


@app.exception_handler(ModelConfigurationError)
async def model_configuration_error_handler(
    request: Request, exc: ModelConfigurationError
):
    return JSONResponse(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        content={'detail': f'Modelos de linguagem indisponíveis: {exc}'},
    )


app.include_router(health.router)
app.include_router(conversations.router)
app.include_router(models.router)


@app.get('/', status_code=HTTPStatus.OK, response_model=Message)
async def read_root():
    return Message(message='Olá Mundo!')
