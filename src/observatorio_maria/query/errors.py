"""Exceções do pacote de validação e execução de consultas."""


class QueryValidationError(Exception):
    """Consulta recusada pelas regras do catálogo ou erro de sintaxe."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class QueryCostExceededError(QueryValidationError):
    """Consulta recusada por custo estimado excessivo no dry-run."""

    def __init__(self, total_cost: float, max_cost: float):
        self.total_cost = total_cost
        self.max_cost = max_cost
        message = (
            f'Custo estimado excessivo ({total_cost:.0f} > limite '
            f'{max_cost:.0f}). Refine os filtros usando colunas indexadas, '
            'anos específicos ou MATCH_TEXT para reduzir o espaço de busca.'
        )
        super().__init__(message)
