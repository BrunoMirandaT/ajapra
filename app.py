"""Sistema de gestão da ONG AJAPRA — backend Flask (API REST + páginas)."""
from __future__ import annotations

import csv
import io
import secrets
import threading
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, Response, abort, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

import forecast as F
import validators as V
from config import Config
from store import make_store

# ----------------------------------------------------------------------------
# Esquemas de validação
# ----------------------------------------------------------------------------
ESPECIES = ("cachorro", "gato", "outro")
STATUS_ANIMAL = ("disponivel", "em_tratamento", "adotado")
TIPOS_ATIVIDADE = ("feira_adocao", "vacinacao", "castracao", "campanha", "arrecadacao", "reuniao", "outro")
STATUS_ATIVIDADE = ("planejada", "realizada", "cancelada")

ANIMAL = {
    "nome": {"type": "str", "required": True, "max": 80},
    "especie": {"type": "enum", "required": True, "choices": ESPECIES},
    "sexo": {"type": "enum", "required": True, "choices": ("macho", "femea")},
    "porte": {"type": "enum", "required": True, "choices": ("pequeno", "medio", "grande")},
    "idade_meses": {"type": "int", "min": 0, "max": 360},
    "cor": {"type": "str", "max": 40},
    "castrado": {"type": "enum", "choices": ("sim", "nao")},
    "status": {"type": "enum", "choices": STATUS_ANIMAL},
    "data_cadastro": {"type": "date", "max_today": True},
    "descricao": {"type": "str", "max": 500},
}
ADOTANTE = {
    "nome": {"type": "str", "required": True, "max": 120},
    "cpf": {"type": "cpf", "required": True},
    "email": {"type": "email"},
    "telefone": {"type": "phone", "required": True},
    "cidade": {"type": "str", "required": True, "max": 80},
    "uf": {"type": "uf"},
    "endereco": {"type": "str", "max": 200},
    "observacoes": {"type": "str", "max": 500},
}
ADOCAO = {
    "animal_id": {"type": "str", "required": True, "max": 64},
    "adotante_id": {"type": "str", "required": True, "max": 64},
    "data_adocao": {"type": "date", "required": True, "max_today": True},
    "observacoes": {"type": "str", "max": 500},
}
ATIVIDADE = {
    "titulo": {"type": "str", "required": True, "max": 120},
    "tipo": {"type": "enum", "required": True, "choices": TIPOS_ATIVIDADE},
    "data": {"type": "date", "required": True},
    "horario": {"type": "time"},
    "local": {"type": "str", "max": 120},
    "responsavel": {"type": "str", "max": 80},
    "status": {"type": "enum", "choices": STATUS_ATIVIDADE},
    "descricao": {"type": "str", "max": 500},
}
USUARIO = {
    "nome": {"type": "str", "required": True, "max": 80},
    "email": {"type": "email", "required": True},
    "perfil": {"type": "enum", "required": True, "choices": ("admin", "voluntario")},
    "ativo": {"type": "bool"},
    "senha": {"type": "str", "min": 8, "max": 128},
}

_DUMMY_HASH = generate_password_hash("senha-fantasma")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def hoje_iso() -> str:
    return date.today().isoformat()


def _csv_safe(v) -> str:
    """Evita injeção de fórmulas ao abrir CSV no Excel/Calc."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    if app.config.get("TRUST_PROXY"):  # atrás do proxy do Cloud Run/Render: usa o IP real do cliente
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    store = make_store(app.config)
    app.extensions["store"] = store
    adoption_lock = threading.Lock()  # evita 2 adoções simultâneas do mesmo animal (processo único)
    login_attempts: dict[str, list[float]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Utilitários de requisição
    # ------------------------------------------------------------------
    def json_error(msg: str, status: int = 400, campos: dict | None = None):
        return jsonify({"erro": msg, "campos": campos or {}}), status

    def paged(rows):
        """Sem ?pagina= devolve a lista inteira. Com ?pagina=N&por_pagina=M devolve só a página
        (máx. 200 por página); totais nos cabeçalhos X-Total-Count, X-Page, X-Per-Page e X-Total-Pages."""
        if request.args.get("pagina") is None:
            return jsonify(rows)
        try:
            page = max(int(request.args["pagina"]), 1)
            per = min(max(int(request.args.get("por_pagina", 25)), 1), 200)
        except ValueError:
            return json_error("Parâmetros de paginação inválidos.", 422)
        total = len(rows)
        pages = max(-(-total // per), 1)
        page = min(page, pages)  # página além do fim devolve a última
        resp = jsonify(rows[(page - 1) * per: page * per])
        resp.headers.update({"X-Total-Count": str(total), "X-Page": str(page),
                             "X-Per-Page": str(per), "X-Total-Pages": str(pages)})
        return resp

    def current_user():
        if "user" not in g:
            uid = session.get("uid")
            u = store.get("usuarios", uid) if uid else None
            g.user = u if u and u.get("ativo", True) else None
        return g.user

    def login_required(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if not current_user():
                if request.path.startswith("/api/"):
                    return json_error("Sessão expirada. Faça login novamente.", 401)
                return redirect(url_for("login", next=request.path))
            return fn(*a, **kw)
        return wrapper

    def admin_required(fn):
        @wraps(fn)
        @login_required
        def wrapper(*a, **kw):
            if current_user().get("perfil") != "admin":
                if request.path.startswith("/api/"):
                    return json_error("Apenas administradores podem executar esta ação.", 403)
                abort(403)
            return fn(*a, **kw)
        return wrapper

    @app.context_processor
    def inject_globals():
        return {"user": current_user()}

    @app.before_request
    def csrf_protect():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(24)
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token") or ""
            if not secrets.compare_digest(sent, session["csrf"]):
                if request.path.startswith("/api/"):
                    return json_error("Token de segurança inválido. Recarregue a página.", 400)
                abort(400)

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
        )
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    # ------------------------------------------------------------------
    # Autenticação
    # ------------------------------------------------------------------
    def throttled(ip: str) -> bool:
        cutoff = time.time() - 300
        login_attempts[ip] = [t for t in login_attempts[ip] if t > cutoff]
        return len(login_attempts[ip]) >= 5

    @app.route("/login", methods=["GET", "POST"])
    def login():
        erro = None
        if request.method == "POST":
            ip = request.remote_addr or "?"
            if throttled(ip):
                erro = "Muitas tentativas. Aguarde alguns minutos e tente novamente."
            else:
                email = (request.form.get("email") or "").strip().lower()
                senha = request.form.get("senha") or ""
                user = next((u for u in store.list("usuarios") if u.get("email") == email), None)
                hash_ = user["senha_hash"] if user else _DUMMY_HASH  # tempo de resposta uniforme
                if check_password_hash(hash_, senha) and user and user.get("ativo", True):
                    session.clear()
                    session["uid"] = user["id"]
                    session["csrf"] = secrets.token_urlsafe(24)
                    session.permanent = True
                    login_attempts.pop(ip, None)
                    nxt = request.args.get("next", "/")
                    if not nxt.startswith("/") or nxt.startswith("//"):
                        nxt = "/"
                    return redirect(nxt)
                login_attempts[ip].append(time.time())
                erro = "E-mail ou senha inválidos."
        return render_template("login.html", erro=erro)

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/api/me")
    @login_required
    def me():
        u = current_user()
        return jsonify({"id": u["id"], "nome": u["nome"], "perfil": u["perfil"]})

    # ------------------------------------------------------------------
    # Páginas (a interface consome a API REST via JavaScript)
    # ------------------------------------------------------------------
    def add_page(path, name, title, admin=False):
        def view():
            return render_template("page.html", page=name, title=title)
        view.__name__ = f"page_{name}"
        app.add_url_rule(path, view_func=(admin_required if admin else login_required)(view))

    add_page("/", "dashboard", "Painel")
    add_page("/animais", "animais", "Animais")
    add_page("/adotantes", "adotantes", "Adotantes")
    add_page("/adocoes", "adocoes", "Adoções")
    add_page("/atividades", "atividades", "Calendário de atividades")
    add_page("/relatorios", "relatorios", "Relatórios")
    add_page("/previsao", "previsao", "Previsão")
    add_page("/usuarios", "usuarios", "Usuários", admin=True)

    @app.errorhandler(403)
    @app.errorhandler(404)
    def http_error(e):
        if request.path.startswith("/api/"):
            return json_error("Recurso não encontrado." if e.code == 404 else "Acesso negado.", e.code)
        return render_template("erro.html", codigo=e.code), e.code

    @app.errorhandler(500)
    def server_error(e):
        if request.path.startswith("/api/"):
            return json_error("Erro interno do servidor.", 500)
        return render_template("erro.html", codigo=500), 500

    # ------------------------------------------------------------------
    # CRUD genérico
    # ------------------------------------------------------------------
    def register_crud(name, col, schema, *, filt, sort, enrich=None, before_save=None,
                      before_delete=None, after_create=None, after_delete=None, allow_update=True):
        def _out(rows):
            return enrich(rows) if enrich else rows

        @login_required
        def list_():
            rows = [r for r in _out(store.list(col)) if filt(r, request.args)]
            key, reverse = sort
            rows.sort(key=lambda r: (key(r), r["id"]), reverse=reverse)  # desempate por id: páginas estáveis
            return paged(rows)

        @login_required
        def get_(rid):
            rec = store.get(col, rid)
            return jsonify(_out([rec])[0]) if rec else json_error("Registro não encontrado.", 404)

        @login_required
        def create_():
            data = request.get_json(silent=True) or {}
            clean, errors = V.validate(schema, data)
            if not errors and before_save:
                errors = before_save(clean, None) or {}
            if errors:
                return json_error("Verifique os campos informados.", 422, errors)
            clean.update(criado_em=now_iso(), criado_por=current_user()["id"])
            rec = store.create(col, clean)
            if after_create:
                after_create(rec)
            return jsonify(_out([rec])[0]), 201

        @login_required
        def update_(rid):
            existing = store.get(col, rid)
            if not existing:
                return json_error("Registro não encontrado.", 404)
            data = request.get_json(silent=True) or {}
            clean, errors = V.validate(schema, data, partial=True)
            if not errors and before_save:
                errors = before_save(clean, existing) or {}
            if errors:
                return json_error("Verifique os campos informados.", 422, errors)
            clean.update(atualizado_em=now_iso(), atualizado_por=current_user()["id"])
            return jsonify(_out([store.update(col, rid, clean)])[0])

        @admin_required
        def delete_(rid):
            existing = store.get(col, rid)
            if not existing:
                return json_error("Registro não encontrado.", 404)
            if before_delete:
                msg = before_delete(existing)
                if msg:
                    return json_error(msg, 409)
            store.delete(col, rid)
            if after_delete:
                after_delete(existing)
            return jsonify({"ok": True})

        base = f"/api/{name}"
        rule = lambda suffix, fn, m: app.add_url_rule(  # noqa: E731
            base + suffix, endpoint=f"{name}_{fn.__name__}", view_func=fn, methods=[m])
        rule("", list_, "GET")
        rule("", create_, "POST")
        rule("/<rid>", get_, "GET")
        if allow_update:
            rule("/<rid>", update_, "PUT")
        rule("/<rid>", delete_, "DELETE")

    def text_match(item, q, keys):
        q = V.norm(q)
        return not q or any(q in V.norm(item.get(k, "")) for k in keys)

    # ---------------- Animais ----------------
    def animais_filter(r, a):
        return (text_match(r, a.get("q", ""), ("nome", "cor", "descricao"))
                and (not a.get("especie") or r.get("especie") == a["especie"])
                and (not a.get("status") or r.get("status") == a["status"])
                and (not a.get("porte") or r.get("porte") == a["porte"]))

    def animais_before_save(clean, existing):
        errors = {}
        for k in ("status", "data_cadastro"):  # em branco = usar o padrão / manter
            if clean.get(k) == "":
                clean.pop(k)
        new_status = clean.get("status")
        if existing is None:
            if new_status == "adotado":
                errors["status"] = "Para marcar como adotado, registre uma adoção."
            clean.setdefault("status", "disponivel")
            clean.setdefault("data_cadastro", hoje_iso())
        else:
            old = existing.get("status")
            if new_status and new_status != old:
                if new_status == "adotado":
                    errors["status"] = "Para marcar como adotado, registre uma adoção."
                elif old == "adotado":
                    errors["status"] = "Animal já adotado. Para alterar o status, exclua a adoção correspondente."
        return errors

    def animais_before_delete(rec):
        if any(a.get("animal_id") == rec["id"] for a in store.list("adocoes")):
            return "Este animal possui adoção registrada. Exclua a adoção antes de excluir o animal."

    register_crud("animais", "animais", ANIMAL, filt=animais_filter,
                  sort=(lambda r: (r.get("data_cadastro", ""), r.get("nome", "")), True),
                  before_save=animais_before_save, before_delete=animais_before_delete)

    # ---------------- Adotantes ----------------
    def adotantes_filter(r, a):
        q = a.get("q", "")
        qd = V.only_digits(q)
        by_text = text_match(r, q, ("nome", "email"))
        by_cpf = bool(qd) and qd in r.get("cpf", "")
        return ((by_text or by_cpf)
                and (not a.get("cidade") or V.norm(a["cidade"]) in V.norm(r.get("cidade", ""))))

    def adotantes_before_save(clean, existing):
        errors = {}
        if "cpf" in clean:
            own = existing["id"] if existing else None
            if any(x["id"] != own and x.get("cpf") == clean["cpf"] for x in store.list("adotantes")):
                errors["cpf"] = "Já existe um adotante cadastrado com este CPF."
        if existing is None:
            clean.setdefault("uf", "SC")
            if clean.get("uf") == "":
                clean["uf"] = "SC"
        return errors

    def adotantes_before_delete(rec):
        if any(a.get("adotante_id") == rec["id"] for a in store.list("adocoes")):
            return "Este adotante possui adoções registradas e não pode ser excluído."

    register_crud("adotantes", "adotantes", ADOTANTE, filt=adotantes_filter,
                  sort=(lambda r: V.norm(r.get("nome", "")), False),
                  before_save=adotantes_before_save, before_delete=adotantes_before_delete)

    # ---------------- Adoções ----------------
    def adocoes_enrich(rows):
        animais = {a["id"]: a for a in store.list("animais")}
        adotantes = {a["id"]: a for a in store.list("adotantes")}
        out = []
        for r in rows:
            an, ad = animais.get(r.get("animal_id"), {}), adotantes.get(r.get("adotante_id"), {})
            out.append({**r,
                        "animal_nome": an.get("nome", "(removido)"), "animal_especie": an.get("especie", ""),
                        "adotante_nome": ad.get("nome", "(removido)"), "cidade": ad.get("cidade", ""),
                        "uf": ad.get("uf", "")})
        return out

    def adocoes_filter(r, a):
        return (text_match(r, a.get("q", ""), ("animal_nome", "adotante_nome"))
                and (not a.get("cidade") or V.norm(a["cidade"]) in V.norm(r.get("cidade", "")))
                and (not a.get("especie") or r.get("animal_especie") == a["especie"])
                and (not a.get("de") or r.get("data_adocao", "") >= a["de"])
                and (not a.get("ate") or r.get("data_adocao", "") <= a["ate"]))

    def adocoes_before_save(clean, existing):
        errors = {}
        animal = store.get("animais", clean["animal_id"])
        if not animal:
            errors["animal_id"] = "Animal não encontrado."
        elif animal.get("status") != "disponivel":
            errors["animal_id"] = "Este animal não está disponível para adoção."
        elif clean["data_adocao"] < animal.get("data_cadastro", ""):
            errors["data_adocao"] = "A data da adoção não pode ser anterior ao cadastro do animal."
        if not store.get("adotantes", clean["adotante_id"]):
            errors["adotante_id"] = "Adotante não encontrado."
        return errors

    def adocoes_after_create(rec):
        store.update("animais", rec["animal_id"], {"status": "adotado", "atualizado_em": now_iso()})

    def adocoes_after_delete(rec):  # animal volta a ficar disponível
        if store.get("animais", rec["animal_id"]):
            store.update("animais", rec["animal_id"], {"status": "disponivel", "atualizado_em": now_iso()})

    register_crud("adocoes", "adocoes", ADOCAO, filt=adocoes_filter, enrich=adocoes_enrich,
                  sort=(lambda r: (r.get("data_adocao", ""), r.get("criado_em", "")), True),
                  before_save=adocoes_before_save, after_create=adocoes_after_create,
                  after_delete=adocoes_after_delete, allow_update=False)

    # A criação de adoção precisa ser serializada (checa disponibilidade e depois altera o animal)
    create_view = app.view_functions["adocoes_create_"]

    @wraps(create_view)
    def locked_create():
        with adoption_lock:
            return create_view()

    app.view_functions["adocoes_create_"] = locked_create

    # ---------------- Atividades ----------------
    def atividades_filter(r, a):
        return (text_match(r, a.get("q", ""), ("titulo", "local", "responsavel"))
                and (not a.get("tipo") or r.get("tipo") == a["tipo"])
                and (not a.get("status") or r.get("status") == a["status"])
                and (not a.get("de") or r.get("data", "") >= a["de"])
                and (not a.get("ate") or r.get("data", "") <= a["ate"]))

    def atividades_before_save(clean, existing):
        if existing is None:
            if not clean.get("status"):
                clean["status"] = "planejada"
        elif clean.get("status") == "":
            clean.pop("status")
        return {}

    register_crud("atividades", "atividades", ATIVIDADE, filt=atividades_filter,
                  sort=(lambda r: (r.get("data", ""), r.get("horario", "")), False),
                  before_save=atividades_before_save)

    # ---------------- Usuários (somente administradores) ----------------
    def _public_user(u):
        return {k: v for k, v in u.items() if k != "senha_hash"}

    def _admins_ativos(excluindo=None):
        return [u for u in store.list("usuarios")
                if u.get("perfil") == "admin" and u.get("ativo", True) and u["id"] != excluindo]

    @app.get("/api/usuarios")
    @admin_required
    def usuarios_list():
        rows = sorted(store.list("usuarios"), key=lambda u: V.norm(u.get("nome", "")))
        return paged([_public_user(u) for u in rows])

    @app.post("/api/usuarios")
    @admin_required
    def usuarios_create():
        clean, errors = V.validate(USUARIO, request.get_json(silent=True) or {})
        if not clean.get("senha") and "senha" not in errors:
            errors["senha"] = "Campo obrigatório."
        if "email" in clean and any(u.get("email") == clean["email"] for u in store.list("usuarios")):
            errors["email"] = "Já existe um usuário com este e-mail."
        if errors:
            return json_error("Verifique os campos informados.", 422, errors)
        clean["senha_hash"] = generate_password_hash(clean.pop("senha"))
        clean["ativo"] = clean.get("ativo") is not False
        clean["criado_em"] = now_iso()
        return jsonify(_public_user(store.create("usuarios", clean))), 201

    @app.put("/api/usuarios/<rid>")
    @admin_required
    def usuarios_update(rid):
        existing = store.get("usuarios", rid)
        if not existing:
            return json_error("Usuário não encontrado.", 404)
        clean, errors = V.validate(USUARIO, request.get_json(silent=True) or {}, partial=True)
        if clean.get("senha") == "":
            clean.pop("senha")
        if "email" in clean and any(u["id"] != rid and u.get("email") == clean["email"] for u in store.list("usuarios")):
            errors["email"] = "Já existe um usuário com este e-mail."
        loses_admin = (clean.get("perfil") == "voluntario" or clean.get("ativo") is False)
        if loses_admin and existing.get("perfil") == "admin" and not _admins_ativos(excluindo=rid):
            errors["perfil"] = "O sistema precisa de ao menos um administrador ativo."
        if errors:
            return json_error("Verifique os campos informados.", 422, errors)
        if "senha" in clean:
            clean["senha_hash"] = generate_password_hash(clean.pop("senha"))
        if clean.get("ativo") is None:
            clean.pop("ativo", None)
        return jsonify(_public_user(store.update("usuarios", rid, clean)))

    @app.delete("/api/usuarios/<rid>")
    @admin_required
    def usuarios_delete(rid):
        existing = store.get("usuarios", rid)
        if not existing:
            return json_error("Usuário não encontrado.", 404)
        if rid == current_user()["id"]:
            return json_error("Você não pode excluir o próprio usuário.", 409)
        if existing.get("perfil") == "admin" and not _admins_ativos(excluindo=rid):
            return json_error("O sistema precisa de ao menos um administrador ativo.", 409)
        store.delete("usuarios", rid)
        return jsonify({"ok": True})

    # ------------------------------------------------------------------
    # Painel, relatórios e exportação
    # ------------------------------------------------------------------
    def month_range(start_ym: str, end_ym: str, cap: int = 60) -> list[str]:
        out, m = [], start_ym
        while m <= end_ym and len(out) < cap:
            out.append(m)
            m = F.add_months(m, 1)
        return out

    @app.get("/api/dashboard")
    @login_required
    def dashboard():
        animais, adocoes = store.list("animais"), store.list("adocoes")
        hoje = date.today()
        atual = F.month_key(hoje)
        meses = month_range(F.add_months(atual, -11), atual)
        cad, ado = Counter(a.get("data_cadastro", "")[:7] for a in animais), Counter(a.get("data_adocao", "")[:7] for a in adocoes)
        status = Counter(a.get("status") for a in animais)
        proximas = sorted(
            (a for a in store.list("atividades") if a.get("data", "") >= hoje.isoformat() and a.get("status") == "planejada"),
            key=lambda a: (a["data"], a.get("horario", "")))[:6]
        return jsonify({
            "totais": {
                "animais": len(animais), "disponiveis": status["disponivel"],
                "em_tratamento": status["em_tratamento"], "adotados": status["adotado"],
                "adotantes": len(store.list("adotantes")),
                "adocoes_mes": ado[atual], "cadastros_mes": cad[atual],
            },
            "serie": {"meses": meses, "cadastros": [cad[m] for m in meses], "adocoes": [ado[m] for m in meses]},
            "proximas_atividades": proximas,
        })

    @app.get("/api/relatorios/adocoes")
    @login_required
    def relatorio_adocoes():
        hoje = date.today()
        de = request.args.get("de") or f"{F.add_months(F.month_key(hoje), -11)}-01"
        ate = request.args.get("ate") or hoje.isoformat()
        d1, d2 = V.parse_date(de), V.parse_date(ate)
        if not d1 or not d2:
            return json_error("Datas inválidas (use AAAA-MM-DD).", 422)
        if d1 > d2:
            return json_error("A data inicial não pode ser posterior à final.", 422)

        animais = {a["id"]: a for a in store.list("animais")}
        adotantes = {a["id"]: a for a in store.list("adotantes")}
        adocoes = [a for a in store.list("adocoes") if de <= a.get("data_adocao", "") <= ate]
        cadastros = [a for a in animais.values() if de <= a.get("data_cadastro", "") <= ate]

        meses = month_range(de[:7], ate[:7])
        por_mes_ado, por_mes_cad = Counter(a["data_adocao"][:7] for a in adocoes), Counter(a["data_cadastro"][:7] for a in cadastros)
        especies = Counter(animais.get(a["animal_id"], {}).get("especie", "outro") for a in adocoes)
        cidades = Counter(adotantes.get(a["adotante_id"], {}).get("cidade", "(sem cidade)") for a in adocoes)
        dias = []
        for a in adocoes:
            ent = V.parse_date(animais.get(a["animal_id"], {}).get("data_cadastro"))
            sai = V.parse_date(a["data_adocao"])
            if ent and sai and sai >= ent:
                dias.append((sai - ent).days)
        return jsonify({
            "periodo": {"de": de, "ate": ate},
            "total_adocoes": len(adocoes), "total_cadastros": len(cadastros),
            "tempo_medio_dias": round(sum(dias) / len(dias), 1) if dias else None,
            "cidades_distintas": len(cidades),
            "por_mes": {"meses": meses, "adocoes": [por_mes_ado[m] for m in meses], "cadastros": [por_mes_cad[m] for m in meses]},
            "por_especie": [{"nome": k, "valor": v} for k, v in especies.most_common()],
            "por_cidade": [{"nome": k, "valor": v} for k, v in cidades.most_common(10)],
        })

    EXPORTS = {
        "animais": ("animais", ["nome", "especie", "sexo", "porte", "idade_meses", "cor", "castrado", "status", "data_cadastro", "descricao"], False),
        "adotantes": ("adotantes", ["nome", "cpf", "email", "telefone", "cidade", "uf", "endereco", "observacoes"], True),
        "adocoes": ("adocoes", ["data_adocao", "animal_nome", "animal_especie", "adotante_nome", "cidade", "uf", "observacoes"], False),
    }

    @app.get("/api/export/<tipo>.csv")
    @login_required
    def export_csv(tipo):
        if tipo not in EXPORTS:
            abort(404)
        col, cols, admin_only = EXPORTS[tipo]
        if admin_only and current_user().get("perfil") != "admin":  # contém dados pessoais (LGPD)
            return json_error("Apenas administradores podem exportar dados pessoais.", 403)
        rows = store.list(col)
        if tipo == "adocoes":
            rows = [r for r in adocoes_enrich(rows) if adocoes_filter(r, request.args)]
            rows.sort(key=lambda r: r.get("data_adocao", ""), reverse=True)
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(cols)
        for r in rows:
            w.writerow([_csv_safe(r.get(c)) for c in cols])
        return Response("﻿" + buf.getvalue(), mimetype="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="ajapra_{tipo}_{hoje_iso()}.csv"'})

    # ------------------------------------------------------------------
    # Previsão (módulo de IA, executado sob demanda)
    # ------------------------------------------------------------------
    @app.get("/api/previsao")
    @login_required
    def previsao():
        try:
            meses = int(request.args.get("meses", 6))
        except ValueError:
            return json_error("Parâmetro 'meses' inválido.", 422)
        if not 1 <= meses <= 12:
            return json_error("Escolha entre 1 e 12 meses.", 422)
        datas = [a.get("data_cadastro", "") for a in store.list("animais")]
        try:
            return jsonify(F.forecast(datas, meses))
        except ValueError as exc:
            return json_error(str(exc), 422)

    return app


app = create_app()
