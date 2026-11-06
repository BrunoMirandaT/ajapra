"""Cache em memória com escrita direta (write-through) sobre o armazenamento real.

Por que existe: o Firestore cobra por documento lido, e o sistema consulta coleções inteiras a cada tela.
Aqui cada coleção é lida do banco UMA vez e mantida em memória; criações, edições e exclusões são gravadas
no banco e aplicadas na cópia ao mesmo tempo. Depois da primeira carga, consultas custam zero leituras.

Premissa: só esta aplicação grava no banco, em UM processo (a mesma exigência da trava de adoção).
  - Mais de um processo/instância: defina CACHE_TTL_SECONDS (ex.: 300) para as cópias se renovarem.
  - Alterações feitas direto no console do Firebase só aparecem após reiniciar o serviço (ou após o TTL).
"""
from __future__ import annotations

import threading
import time


class CachedStore:
    def __init__(self, backend, ttl: float = 0):
        self.backend = backend
        self.ttl = ttl  # segundos; 0 = sem expiração
        self._cols: dict[str, dict[str, dict]] = {}
        self._loaded_at: dict[str, float] = {}
        self._lock = threading.RLock()

    # ---- carga ----
    def _fresh(self, col: str) -> bool:
        t = self._loaded_at.get(col)
        return t is not None and (self.ttl <= 0 or time.monotonic() - t < self.ttl)

    def _load(self, col: str) -> dict[str, dict]:
        if not self._fresh(col):
            self._cols[col] = {d["id"]: d for d in self.backend.list(col)}
            self._loaded_at[col] = time.monotonic()
        return self._cols[col]

    def refresh(self, col: str | None = None) -> None:
        """Descarta a cópia (de uma coleção ou de todas); a próxima consulta relê do banco."""
        with self._lock:
            for c in ([col] if col else list(self._cols)):
                self._cols.pop(c, None)
                self._loaded_at.pop(c, None)

    # ---- leitura (servida da memória; devolve cópias) ----
    def list(self, col: str) -> list[dict]:
        with self._lock:
            return [dict(d) for d in self._load(col).values()]

    def get(self, col: str, doc_id: str) -> dict | None:
        with self._lock:
            d = self._load(col).get(doc_id)
            return dict(d) if d is not None else None

    # ---- escrita (banco primeiro; a cópia só muda se o banco aceitou) ----
    def create(self, col: str, data: dict, doc_id: str | None = None) -> dict:
        with self._lock:
            rec = self.backend.create(col, data, doc_id) if doc_id else self.backend.create(col, data)
            if self._fresh(col):  # se ainda não foi carregada, a carga futura já trará o registro
                self._cols[col][rec["id"]] = dict(rec)
            return dict(rec)

    def update(self, col: str, doc_id: str, data: dict) -> dict | None:
        with self._lock:
            docs = self._load(col)
            cur = docs.get(doc_id)
            if cur is None:
                return None
            payload = {k: v for k, v in data.items() if k != "id"}
            if not self.backend.set_fields(col, doc_id, payload):  # removido por fora (ex.: console)
                docs.pop(doc_id, None)
                return None
            cur.update(payload)
            return dict(cur)

    def delete(self, col: str, doc_id: str) -> bool:
        with self._lock:
            docs = self._load(col)
            if doc_id not in docs:
                return False
            self.backend.remove(col, doc_id)
            docs.pop(doc_id, None)
            return True

    # ---- operações em lote (usadas por scripts de carga): invalidam a cópia ----
    def bulk_create(self, col: str, items: list[dict]) -> int:
        with self._lock:
            n = self.backend.bulk_create(col, items)
            self.refresh(col)
            return n

    def clear(self, col: str) -> None:
        with self._lock:
            self.backend.clear(col)
            self.refresh(col)
