"""Transforma uma conta do painel em administradora (ou cria a conta, se ainda não existir).

Num servidor novo ninguém é administrador: dentro do painel, só um administrador consegue tornar outra conta
administradora. Este script cria o primeiro. Rode uma vez, no computador ou no servidor onde o painel está:

    python scripts/criar_admin.py email@exemplo.com
    docker compose exec painel python scripts/criar_admin.py email@exemplo.com     (com o Docker)

- Se a conta já existe (a pessoa já se cadastrou no painel), ela vira administradora.
- Se não existe, o script pede o nome e a senha e cria a conta já como administradora.
Sem e-mail, o script só mostra quem é administrador hoje.
"""
import getpass
import hashlib
import json
import os
import secrets
import sys

PASTA_USUARIOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "usuarios")
ARQ_USUARIOS = os.path.join(PASTA_USUARIOS, "usuarios_painel.json")


def resumo_senha(senha, sal):   # o mesmo do painel.py
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(sal), 200_000).hex()


def carregar():
    if not os.path.exists(ARQ_USUARIOS):
        return {}
    with open(ARQ_USUARIOS, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def salvar(usuarios):
    os.makedirs(PASTA_USUARIOS, exist_ok=True)
    with open(ARQ_USUARIOS, "w", encoding="utf-8") as arquivo:
        json.dump(usuarios, arquivo, ensure_ascii=False, indent=2)


def main():
    usuarios = carregar()
    if len(sys.argv) < 2:
        admins = [f"{dados['nome']} <{email}>" for email, dados in usuarios.items() if dados.get("admin")]
        print("Administradores hoje:", ", ".join(admins) if admins else "nenhum")
        print("Para tornar alguém administrador:  python scripts/criar_admin.py email@exemplo.com")
        return
    email = sys.argv[1].strip().lower()   # o painel guarda o e-mail em minúsculas
    if "@" not in email:
        sys.exit("Escreva um e-mail válido.")
    if email in usuarios:
        usuarios[email]["admin"] = True
        salvar(usuarios)
        print(f"Pronto: {usuarios[email]['nome']} <{email}> agora é administrador.")
        return
    print(f"Não existe conta com {email}. Vamos criar, já como administrador.")
    nome = input("Nome: ").strip()
    senha = getpass.getpass("Senha (pelo menos 6 caracteres, não aparece ao digitar): ")
    if not nome or len(senha) < 6:
        sys.exit("Preencha o nome e uma senha com pelo menos 6 caracteres. Nada foi criado.")
    if getpass.getpass("Repita a senha: ") != senha:
        sys.exit("As senhas não são iguais. Nada foi criado.")
    sal = secrets.token_hex(16)
    usuarios[email] = {"nome": nome, "sal": sal, "senha": resumo_senha(senha, sal), "favoritos": [], "admin": True}
    salvar(usuarios)
    print(f"Pronto: conta de {nome} <{email}> criada como administrador. Já pode entrar no painel.")


if __name__ == "__main__":
    main()
