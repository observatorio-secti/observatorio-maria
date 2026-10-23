"""Exceções do pacote de validação e execução de consultas."""


class QueryValidationError(Exception):
    """Consulta recusada pelas regras do catálogo ou erro de sintaxe."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
