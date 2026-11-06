"""Camada de persistência: Firebase Firestore.

Coleções: usuarios, animais, adotantes, adocoes, atividades.
Todo registro retornado é um dict que inclui o campo "id" (ID do documento).
"""
from __future__ import annotations


class FirestoreStore:
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

    def get(self, col: str, doc_id: str) -> dict | None:
        d = self.db.collection(col).document(doc_id).get()
        return {**d.to_dict(), "id": d.id} if d.exists else None

    def create(self, col: str, data: dict) -> dict:
        ref = self.db.collection(col).document()
        payload = {k: v for k, v in data.items() if k != "id"}
        ref.set(payload)
        return {**payload, "id": ref.id}

    def update(self, col: str, doc_id: str, data: dict) -> dict | None:
        ref = self.db.collection(col).document(doc_id)
        if not ref.get().exists:
            return None
        ref.update({k: v for k, v in data.items() if k != "id"})
        return self.get(col, doc_id)

    def delete(self, col: str, doc_id: str) -> bool:
        ref = self.db.collection(col).document(doc_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True


def make_store(cfg) -> FirestoreStore:
    return FirestoreStore(cfg.get("FIREBASE_CREDENTIALS", ""))
