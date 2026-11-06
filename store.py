"""Camada de persistência: Firebase Firestore (acesso direto) + cache em memória (cache.py).

Coleções: usuarios, animais, adotantes, adocoes, atividades.
Todo registro retornado é um dict que inclui o campo "id" (ID do documento).
"""
from __future__ import annotations

from cache import CachedStore


class FirestoreStore:
    """Acesso direto ao Firestore. Use através de CachedStore (ver make_store)."""

    def __init__(self, credentials_path: str = ""):
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            if credentials_path:
                cred = credentials.Certificate(credentials_path)
            else:  # credenciais padrão do ambiente (ex.: conta de serviço anexada no Cloud Run)
                cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()

    def list(self, col: str) -> list[dict]:
        return [{**d.to_dict(), "id": d.id} for d in self.db.collection(col).stream()]

    def create(self, col: str, data: dict) -> dict:
        ref = self.db.collection(col).document()
        payload = {k: v for k, v in data.items() if k != "id"}
        ref.set(payload)
        return {**payload, "id": ref.id}

    def set_fields(self, col: str, doc_id: str, data: dict) -> bool:
        """Atualiza campos sem ler o documento antes. False se o documento não existir."""
        from google.api_core.exceptions import NotFound

        try:
            self.db.collection(col).document(doc_id).update(data)
            return True
        except NotFound:
            return False

    def remove(self, col: str, doc_id: str) -> None:
        self.db.collection(col).document(doc_id).delete()


def make_store(cfg) -> CachedStore:
    return CachedStore(FirestoreStore(cfg.get("FIREBASE_CREDENTIALS", "")), ttl=cfg.get("CACHE_TTL_SECONDS", 0))
