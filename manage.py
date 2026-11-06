#!/usr/bin/env python3
"""Utilitário de administração.

  python manage.py createuser --nome "Nome" --email a@b.com --perfil admin
      cria um usuário (a senha é pedida de forma segura, sem aparecer na tela)

Requer as mesmas variáveis de ambiente do servidor (SECRET_KEY e, se necessário, FIREBASE_CREDENTIALS).
"""
import argparse
import getpass
import sys
from datetime import datetime

from werkzeug.security import generate_password_hash

import validators as V
from app import app


def cmd_createuser(args):
    store = app.extensions["store"]
    clean, errors = V.validate(
        {"nome": {"type": "str", "required": True, "max": 80},
         "email": {"type": "email", "required": True},
         "perfil": {"type": "enum", "required": True, "choices": ("admin", "voluntario")}},
        {"nome": args.nome, "email": args.email, "perfil": args.perfil})
    if errors:
        print("Erro:", errors)
        return 1
    if any(u.get("email") == clean["email"] for u in store.list("usuarios")):
        print("Já existe um usuário com este e-mail.")
        return 1
    senha = getpass.getpass("Senha (mín. 8 caracteres): ")
    if len(senha) < 8 or senha != getpass.getpass("Repita a senha: "):
        print("Senha curta demais ou não confere.")
        return 1
    store.create("usuarios", {**clean, "ativo": True, "senha_hash": generate_password_hash(senha),
                              "criado_em": datetime.now().isoformat(timespec="seconds")})
    print("Usuário criado.")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("createuser", help="cria usuário")
    u.add_argument("--nome", required=True)
    u.add_argument("--email", required=True)
    u.add_argument("--perfil", choices=("admin", "voluntario"), default="voluntario")
    u.set_defaults(fn=cmd_createuser)
    args = p.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
