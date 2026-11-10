"""Publicador oficial do @previsaobsb (Meta Graph API).

Diferenças em relação ao Previsão RJ:
  * o repositório é PRIVADO, então o MP4 NÃO é hospedado em Release público:
    vai direto para a Meta pelo upload resumível (rupload), sem URL pública;
  * o app "Previsao BSB bot" usa o login unificado (token EAA... em
    graph.facebook.com). Um token do login do Instagram (IG...) também funciona:
    o host é escolhido pelo prefixo do token, como no O Tempo SP.

Travas (nenhuma pode ser desligada por variável):
  1. a conta retornada pela Meta precisa ser exatamente @previsaobsb E ter o
     mesmo ID numérico do secret IG_USER_ID;
  2. um turno (data + manha/noite) só publica uma vez (data/publicacoes.json);
  3. legenda idêntica já presente no perfil bloqueia;
  4. Reel publicado no perfil há menos de 2 h bloqueia (retry após falha
     entre publicar e gravar o histórico).

Tokens nunca são impressos. Uso:
    python -m publicador.instagram_bsb verificar
    python -m publicador.instagram_bsb publicar --video output/REEL_BSB.mp4 \
        --legenda output/LEGENDA.txt --turno manha --data 2026-11-11 --publicar
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
ESTADO = ROOT / "data" / "publicacoes.json"
BRT = timezone(timedelta(hours=-3))
VERSAO_PADRAO = "v26.0"   # mesma versão validada em produção no Previsão RJ


class Bloqueio(RuntimeError):
    """Publicação recusada por uma trava de segurança."""


# ----------------------------------------------------------------- config

def cfg() -> dict:
    user = (os.environ.get("IG_USER_ID") or "").strip()
    token = (os.environ.get("IG_ACCESS_TOKEN") or "").strip()
    versao = (os.environ.get("META_GRAPH_VERSION") or VERSAO_PADRAO).strip()
    esperado = (os.environ.get("EXPECTED_IG_USERNAME") or "previsaobsb").lstrip("@").casefold()
    faltando = [n for n, v in (("IG_USER_ID", user), ("IG_ACCESS_TOKEN", token)) if not v]
    if faltando:
        raise Bloqueio("Secrets ausentes: " + ", ".join(faltando))
    if not user.isdecimal():
        raise Bloqueio("IG_USER_ID precisa ser o ID numérico da conta, não o @usuário")
    host = (os.environ.get("META_GRAPH_HOST") or
            ("graph.facebook.com" if token.startswith("EAA") else "graph.instagram.com"))
    return {"user": user, "token": token, "versao": versao, "esperado": esperado,
            "host": host, "base": f"https://{host}/{versao}"}


def _req(metodo: str, url: str, c: dict, **kw) -> dict:
    kw.setdefault("timeout", 60)
    params = dict(kw.pop("params", {}) or {})
    params["access_token"] = c["token"]
    r = requests.request(metodo, url, params=params, **kw)
    if r.status_code >= 400:
        # Corpo de erro da Meta não contém o token; ainda assim, nunca a URL.
        try:
            erro = r.json().get("error", {})
        except ValueError:
            erro = {"message": r.text[:300]}
        raise RuntimeError(f"Meta HTTP {r.status_code} em {metodo} {url.split('?')[0]}: "
                           f"{erro.get('type', '')} {erro.get('code', '')} {erro.get('message', '')}")
    return r.json()


# ------------------------------------------------------------ verificação

def verificar_destino(c: dict | None = None) -> dict:
    c = c or cfg()
    conta = _req("GET", f"{c['base']}/{c['user']}", c,
                 params={"fields": "id,username"})
    nome = (conta.get("username") or "").casefold()
    if nome != c["esperado"]:
        raise Bloqueio(f"DESTINO BLOQUEADO: a Meta devolveu @{nome or '?'}, esperado @{c['esperado']}")
    if str(conta.get("id")) != c["user"]:
        raise Bloqueio("DESTINO BLOQUEADO: ID devolvido difere do secret IG_USER_ID")
    return conta


def diagnostico() -> dict:
    """Checagem completa e segura (não publica nada)."""
    c = cfg()
    out = {"host": c["host"], "versao": c["versao"],
           "tipo_token": "EAA (login unificado)" if c["token"].startswith("EAA")
           else "IG (login do Instagram)" if c["token"].startswith("IG") else "desconhecido"}
    conta = verificar_destino(c)
    out["conta"] = {"id": conta["id"], "username": conta["username"]}
    try:
        lim = _req("GET", f"{c['base']}/{c['user']}/content_publishing_limit", c,
                   params={"fields": "quota_usage,config"})
        out["limite_publicacao"] = lim.get("data", [lim])[0]
    except RuntimeError as e:
        out["limite_publicacao"] = f"indisponível: {e}"
    if c["host"] == "graph.facebook.com":
        try:
            perms = _req("GET", f"{c['base']}/me/permissions", c)
            out["permissoes"] = sorted(p["permission"] for p in perms.get("data", [])
                                       if p.get("status") == "granted")
        except RuntimeError as e:
            out["permissoes"] = f"indisponível (token de usuário do sistema?): {e}"
        app_id = os.environ.get("META_APP_ID", "").strip()
        app_secret = os.environ.get("META_APP_SECRET", "").strip()
        if app_id and app_secret:
            dbg = requests.get(f"{c['base']}/debug_token", timeout=30, params={
                "input_token": c["token"], "access_token": f"{app_id}|{app_secret}"}).json().get("data", {})
            exp = dbg.get("expires_at") or 0
            out["token"] = {"valido": dbg.get("is_valid"), "app_id": dbg.get("app_id"),
                            "expira": "nunca" if not exp else
                            datetime.fromtimestamp(exp, timezone.utc).isoformat(),
                            "escopos": dbg.get("scopes")}
    precisa = {"instagram_basic", "instagram_content_publish"}
    if isinstance(out.get("permissoes"), list) and not precisa <= set(out["permissoes"]):
        raise Bloqueio(f"Faltam permissões: {sorted(precisa - set(out['permissoes']))}")
    return out


# ----------------------------------------------------------------- travas

def ler_estado() -> dict:
    return json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.exists() else {}


def gravar_estado(estado: dict) -> None:
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _norm(t: str) -> str:
    return " ".join((t or "").split()).casefold()


def checar_duplicidade(c: dict, chave: str, legenda: str, estado: dict) -> None:
    if estado.get(chave, {}).get("media_id"):
        raise Bloqueio(f"Turno {chave} já publicado (media_id {estado[chave]['media_id']})")
    recentes = _req("GET", f"{c['base']}/{c['user']}/media", c,
                    params={"fields": "id,caption,timestamp", "limit": "25"}).get("data", [])
    alvo = _norm(legenda)
    agora = datetime.now(timezone.utc)
    for m in recentes:
        if _norm(m.get("caption")) == alvo:
            raise Bloqueio(f"Legenda idêntica já publicada (media {m['id']})")
        ts = m.get("timestamp")
        if ts:
            quando = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")
            if agora - quando < timedelta(hours=2):
                raise Bloqueio(f"Reel publicado há menos de 2 h (media {m['id']}); "
                               "confira o perfil antes de repetir")


# --------------------------------------------------------------- publicar

def upload_resumivel(c: dict, video: Path, legenda: str, capa_ms: int) -> str:
    corpo = {"media_type": "REELS", "upload_type": "resumable",
             "caption": legenda, "share_to_feed": "true"}
    if capa_ms > 0:
        corpo["thumb_offset"] = str(capa_ms)
    cont = _req("POST", f"{c['base']}/{c['user']}/media", c, data=corpo)
    cid, uri = cont["id"], cont.get("uri")
    if not uri:
        uri = f"https://rupload.facebook.com/ig-api-upload/{c['versao']}/{cid}"
    tamanho = video.stat().st_size
    with video.open("rb") as fh:
        r = requests.post(uri, data=fh, timeout=600, headers={
            "Authorization": f"OAuth {c['token']}", "offset": "0",
            "file_size": str(tamanho), "Content-Type": "application/octet-stream"})
    if r.status_code >= 400 or not r.json().get("success", True):
        raise RuntimeError(f"Upload resumível falhou: HTTP {r.status_code} {r.text[:300]}")
    print(f"upload: {tamanho/1e6:.1f} MB enviados ao container {cid}")
    return cid


def aguardar_container(c: dict, cid: str, limite_s: int = 600) -> None:
    fim = time.time() + limite_s
    while time.time() < fim:
        st = _req("GET", f"{c['base']}/{cid}", c, params={"fields": "status_code,status"})
        estado = st.get("status_code")
        print("container:", estado)
        if estado == "FINISHED":
            return
        if estado in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"Container {estado}: {st.get('status')}")
        time.sleep(10)
    raise TimeoutError("A Meta não concluiu o processamento do Reel")


def publicar(video: Path, legenda_txt: Path, turno: str, data: str, capa_ms: int = 0,
             de_verdade: bool = False) -> dict:
    if turno not in {"manha", "noite"}:
        raise Bloqueio("turno deve ser manha ou noite")
    legenda = legenda_txt.read_text(encoding="utf-8").strip()
    if not legenda or not video.is_file() or video.stat().st_size < 100_000:
        raise Bloqueio("MP4 ou legenda ausente/vazio")
    c = cfg()
    conta = verificar_destino(c)
    print(f"destino confirmado: @{conta['username']}")
    chave = f"{data}:{turno}"
    estado = ler_estado()
    checar_duplicidade(c, chave, legenda, estado)
    if not de_verdade:
        print("Modo ensaio: travas aprovadas, nada enviado à Meta.")
        return {"ensaio": True, "chave": chave}

    cid = upload_resumivel(c, video, legenda, capa_ms)
    estado[chave] = {"status": "publicando", "container": cid,
                     "inicio": datetime.now(BRT).isoformat(timespec="seconds")}
    gravar_estado(estado)
    aguardar_container(c, cid)
    verificar_destino(c)  # última conferência antes do botão
    media_id = _req("POST", f"{c['base']}/{c['user']}/media_publish", c,
                    data={"creation_id": cid})["id"]
    info = {}
    for _ in range(6):
        try:
            info = _req("GET", f"{c['base']}/{media_id}", c,
                        params={"fields": "id,permalink,timestamp,media_type"})
            if info.get("permalink"):
                break
        except RuntimeError:
            pass
        time.sleep(5)
    estado[chave] = {"status": "publicado", "media_id": media_id,
                     "permalink": info.get("permalink"), "timestamp": info.get("timestamp"),
                     "conta": conta["username"],
                     "publicado_em": datetime.now(BRT).isoformat(timespec="seconds")}
    gravar_estado(estado)
    return estado[chave]


# -------------------------------------------------------------------- cli

def _resumo(texto: str) -> None:
    caminho = os.environ.get("GITHUB_STEP_SUMMARY")
    if caminho:
        with open(caminho, "a", encoding="utf-8") as fh:
            fh.write(texto + "\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="acao", required=True)
    sub.add_parser("verificar")
    q = sub.add_parser("publicar")
    q.add_argument("--video", type=Path, required=True)
    q.add_argument("--legenda", type=Path, required=True)
    q.add_argument("--turno", choices=["manha", "noite"], required=True)
    q.add_argument("--data", required=True, help="data da publicação (AAAA-MM-DD, Brasília)")
    q.add_argument("--capa-ms", type=int, default=0)
    q.add_argument("--publicar", action="store_true", help="sem isto é só ensaio")
    a = p.parse_args(argv)
    try:
        if a.acao == "verificar":
            d = diagnostico()
            print(json.dumps(d, ensure_ascii=False, indent=2))
            _resumo(f"### Meta verificada\n\n```json\n{json.dumps(d, ensure_ascii=False, indent=2)}\n```")
        else:
            r = publicar(a.video, a.legenda, a.turno, a.data, a.capa_ms, a.publicar)
            print(json.dumps(r, ensure_ascii=False, indent=2))
            if r.get("permalink"):
                _resumo(f"### Reel publicado em @previsaobsb\n\n- media_id: `{r['media_id']}`\n"
                        f"- permalink: {r['permalink']}")
    except Bloqueio as e:
        print(f"::error::{e}")
        _resumo(f"### Publicação bloqueada\n\n{e}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
