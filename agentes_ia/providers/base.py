"""Interfaz comun de los proveedores de LLM.

Cada proveedor concreto implementa `responder()` sobre una lista de mensajes en
formato OpenAI (`{'role': ..., 'content': ...}`) y devuelve un `RespuestaLLM`.

Se usa `requests` en vez de SDKs pesados: el proyecto debe arrancar en un VPS
modesto sin compilar dependencias, y todos los proveedores soportados exponen
HTTP/JSON.

Para agregar un proveedor:
  1. Crear `agentes_ia/providers/<nombre>.py` con `class <Nombre>Provider(BaseProvider)`.
  2. Registrarlo en `agentes_ia/providers/__init__.py` (`_PROVIDERS`).
  3. Agregar su id a `PROVEEDOR_CHOICES` en `agentes_ia/models.py`.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

TIMEOUT_LLM = 45
TIMEOUT_LLM_LOCAL = 120
TIMEOUT_LISTADO = 10


@dataclass
class RespuestaLLM:
    texto: str = ''
    tokens_entrada: int = 0
    tokens_salida: int = 0
    modelo: str = ''
    error: str = ''
    crudo: dict = field(default_factory=dict)

    @property
    def ok(self):
        return not self.error and bool(self.texto)


class BaseProvider(ABC):
    name: str = ''
    gratuito: bool = False
    requiere_apikey: bool = True

    @abstractmethod
    def default_model(self) -> str:
        ...

    @abstractmethod
    def responder(self, mensajes: list[dict], apikey: str = '', modelo: str = '',
                  temperatura: float = 0.3, max_tokens: int = 400,
                  base_url: str = '') -> RespuestaLLM:
        ...

    def listar_modelos(self, apikey: str = '', base_url: str = '') -> list[tuple[str, str]]:
        return [(self.default_model(), self.default_model())]

    def probar(self, apikey: str = '', modelo: str = '', base_url: str = '') -> RespuestaLLM:
        return self.responder(
            [{'role': 'user', 'content': 'Responde solamente: listo'}],
            apikey=apikey, modelo=modelo, max_tokens=20, base_url=base_url,
        )
