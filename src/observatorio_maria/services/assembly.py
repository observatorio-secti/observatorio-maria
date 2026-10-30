"""Montagem da resposta: divide o texto e posiciona gráficos e tabelas."""

import re
from dataclasses import dataclass
from typing import Any

from observatorio_maria.schemas import TextBlock

MARKER_OPEN = '[[bloco:'
MARKER = re.compile(r'\[\[bloco:(\d+)\]\]')
PARTIAL_END = re.compile(r'\d*\]?')


@dataclass(frozen=True)
class ContentDelta:
    """Fragmento de texto ou bloco completo da resposta."""

    index: int
    text: str | None = None
    type: str = 'text'
    block: dict[str, Any] | None = None


def held_start(text: str) -> int:
    """Posição a partir da qual o texto ainda pode virar um marcador."""
    start = text.rfind('[')
    if start > 0 and text[start - 1] == '[':
        start -= 1
    if start < 0:
        return len(text)
    tail = text[start:]
    if MARKER_OPEN.startswith(tail):
        return start
    rest = tail.removeprefix(MARKER_OPEN)
    if rest != tail and PARTIAL_END.fullmatch(rest):
        return start
    return len(text)


class ResponseAssembler:
    """Monta os blocos na ordem em que entram na resposta."""

    def __init__(self):
        self.blocks: list[dict[str, Any]] = []
        self._held = ''
        self._placed: set[int] = set()

    def _emit_text(self, text: str) -> list[ContentDelta]:
        if not text:
            return []
        if not self.blocks or self.blocks[-1]['type'] != 'text':
            self.blocks.append(TextBlock(text='').model_dump())
        self.blocks[-1]['text'] += text
        return [ContentDelta(index=len(self.blocks) - 1, text=text)]

    def _emit_block(self, block: dict[str, Any]) -> ContentDelta:
        self.blocks.append(block)
        return ContentDelta(
            index=len(self.blocks) - 1, type=block['type'], block=block
        )

    def add_text(
        self, text: str, pending: list[dict[str, Any]]
    ) -> list[ContentDelta]:
        """Recebe um fragmento e devolve o que já pode ir ao cliente."""
        self._held += text
        deltas: list[ContentDelta] = []
        while match := MARKER.search(self._held):
            deltas += self._emit_text(self._held[: match.start()])
            self._held = self._held[match.end() :]
            number = int(match[1])
            if 1 <= number <= len(pending) and number not in self._placed:
                self._placed.add(number)
                deltas.append(self._emit_block(pending[number - 1]))
        start = held_start(self._held)
        deltas += self._emit_text(self._held[:start])
        self._held = self._held[start:]
        return deltas

    def finish(self, pending: list[dict[str, Any]]) -> list[ContentDelta]:
        """Solta o texto retido, emite os blocos restantes e limpa o texto."""
        deltas = self._emit_text(self._held)
        self._held = ''
        for number, block in enumerate(pending, start=1):
            if number not in self._placed:
                deltas.append(self._emit_block(block))
        for block in self.blocks:
            if block['type'] == 'text':
                block['text'] = block['text'].strip()
        self.blocks = [
            b for b in self.blocks if b['type'] != 'text' or b['text']
        ]
        return deltas


def plain_text(text: str) -> str:
    """Texto da resposta sem os marcadores de posição."""
    return MARKER.sub('', text).strip()
