from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

UFS = ("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO").split()
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def only_digits(s) -> str:
    return re.sub(r"\D", "", str(s or ""))


def norm(s) -> str:
    """Minúsculas e sem acentos (para buscas)."""
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def valid_cpf(cpf) -> bool:
    cpf = only_digits(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for n in (9, 10):
        total = sum(int(cpf[i]) * (n + 1 - i) for i in range(n))
        if (total * 10 % 11) % 10 != int(cpf[n]):
            return False
    return True


def parse_date(s) -> date | None:
    try:
        return datetime.strptime(str(s), "%Y-%m-%d").date()
    except ValueError:
        return None


def validate(schema: dict, data: dict, partial: bool = False) -> tuple[dict, dict]:
    clean, errors = {}, {}
    for field, rule in schema.items():
        raw = data.get(field)
        blank = raw is None or (isinstance(raw, str) and raw.strip() == "")
        if blank:
            if rule.get("required"):
                if not partial or field in data:
                    errors[field] = "Campo obrigatório."
            elif field in data:
                clean[field] = None if rule["type"] in ("int", "bool") else ""
            continue

        t = rule["type"]
        try:
            if t == "str":
                v = str(raw).strip()
                if len(v) > rule.get("max", 200):
                    raise ValueError(f"Máximo de {rule.get('max', 200)} caracteres.")
                if len(v) < rule.get("min", 0):
                    raise ValueError(f"Mínimo de {rule['min']} caracteres.")
            elif t == "int":
                try:
                    v = int(str(raw).strip())
                except ValueError:
                    raise ValueError("Informe um número inteiro.")
                if v < rule.get("min", 0) or v > rule.get("max", 10**9):
                    raise ValueError(f"Valor deve estar entre {rule.get('min', 0)} e {rule.get('max', 10**9)}.")
            elif t == "date":
                d = parse_date(raw)
                if d is None:
                    raise ValueError("Data inválida (use AAAA-MM-DD).")
                if rule.get("max_today") and d > date.today():
                    raise ValueError("A data não pode ser futura.")
                if d.year < 1990 or d.year > 2100:
                    raise ValueError("Data fora do intervalo permitido.")
                v = d.isoformat()
            elif t == "time":
                v = str(raw).strip()
                if not _TIME.match(v):
                    raise ValueError("Horário inválido (use HH:MM).")
            elif t == "enum":
                v = str(raw).strip()
                if v not in rule["choices"]:
                    raise ValueError("Opção inválida.")
            elif t == "email":
                v = str(raw).strip().lower()
                if not _EMAIL.match(v) or len(v) > 120:
                    raise ValueError("E-mail inválido.")
            elif t == "cpf":
                if not valid_cpf(raw):
                    raise ValueError("CPF inválido.")
                v = only_digits(raw)
            elif t == "phone":
                v = only_digits(raw)
                if len(v) not in (10, 11):
                    raise ValueError("Telefone inválido (informe DDD + número).")
            elif t == "uf":
                v = str(raw).strip().upper()
                if v not in UFS:
                    raise ValueError("UF inválida.")
            elif t == "bool":
                if isinstance(raw, bool):
                    v = raw
                elif str(raw).lower() in ("true", "1", "sim"):
                    v = True
                elif str(raw).lower() in ("false", "0", "nao", "não"):
                    v = False
                else:
                    raise ValueError("Valor inválido.")
            else:  # pragma: no cover
                raise ValueError("Tipo de campo desconhecido.")
            clean[field] = v
        except ValueError as exc:
            errors[field] = str(exc)
    return clean, errors
