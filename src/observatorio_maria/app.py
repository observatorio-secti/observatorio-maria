from http import HTTPStatus
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from observatorio_maria.database import engine
from observatorio_maria.llm.registry import ModelConfigurationError
from observatorio_maria.observability.telemetry import setup_telemetry
from observatorio_maria.routers import conversations, health
from observatorio_maria.schemas import Message
from observatorio_maria.settings import Settings

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


def mount_demo(app: FastAPI, settings: Settings):
    """Página estática que demonstra a API (conversas, chat e blocos)."""
    if settings.DEMO_ENABLED:
        app.mount(
            '/demo',
            StaticFiles(directory=Path(__file__).parent / 'demo', html=True),
            name='demo',
        )


mount_demo(app, Settings())
setup_telemetry(app, engine)


@app.get('/', status_code=HTTPStatus.OK, response_model=Message)
async def read_root():
    return Message(message='Olá Mundo!')
