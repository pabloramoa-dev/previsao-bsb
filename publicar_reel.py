"""Publicação oficial de Reel no Instagram por upload direto, sem CDN pública."""
import argparse
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

def request(url, data=None, headers=None):
    req = Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    try:
        with urlopen(req, timeout=180) as response:
            raw = response.read()
            return json.loads(raw or b"{}")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:1500]
        raise RuntimeError(f"Instagram HTTP {exc.code}: {body}") from exc

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--caption", required=True)
    parser.add_argument("--slot", required=True)
    parser.add_argument("--state", default="publicados.json")
    args = parser.parse_args()
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip()
    ig_id = os.environ.get("INSTAGRAM_USER_ID", "").strip()
    if not token or not ig_id:
        raise RuntimeError("Defina os secrets INSTAGRAM_ACCESS_TOKEN e INSTAGRAM_USER_ID no GitHub")
    video = Path(args.video)
    if not video.is_file() or video.stat().st_size < 10000:
        raise RuntimeError("MP4 inexistente ou inválido")
    caption = Path(args.caption).read_text(encoding="utf-8")[:2200]
    state_path = Path(args.state)
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    if args.slot in state:
        print(f"PUBLICAÇÃO JÁ REGISTRADA para {args.slot}: {state[args.slot]}")
        return
    version = os.environ.get("META_GRAPH_VERSION", "v24.0")
    base = f"https://graph.facebook.com/{version}"
    auth = {"access_token": token}
    payload = dict(auth, media_type="REELS", upload_type="resumable",
                   share_to_feed="true", caption=caption)
    container = request(f"{base}/{ig_id}/media", urlencode(payload).encode("utf-8"))
    container_id = container["id"]
    uri = container.get("uri", "")
    if urlparse(uri).hostname != "rupload.facebook.com" or not uri.startswith("https://"):
        raise RuntimeError("Meta não retornou uma URL segura de upload")
    upload = request(uri, video.read_bytes(), {
        "Authorization": "OAuth " + token,
        "offset": "0",
        "file_size": str(video.stat().st_size),
        "Content-Type": "application/octet-stream",
    })
    if upload.get("success") is not True:
        raise RuntimeError(f"Falha ao enviar vídeo ao Instagram: {upload}")
    for attempt in range(30):
        time.sleep(10)
        status = request(f"{base}/{container_id}?" + urlencode(dict(auth, fields="status_code,status")))
        code = status.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Processamento do Instagram falhou: {status}")
    else:
        raise RuntimeError("Instagram não concluiu o processamento em 5 minutos")
    published = request(f"{base}/{ig_id}/media_publish",
                        urlencode(dict(auth, creation_id=container_id)).encode("utf-8"))
    media_id = published["id"]
    info = request(f"{base}/{media_id}?" + urlencode(dict(auth, fields="permalink,timestamp")))
    state[args.slot] = {"id": media_id, "permalink": info.get("permalink", ""),
                        "timestamp": info.get("timestamp", "")}
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"PUBLICADO COM SUCESSO: {info.get('permalink', media_id)}")

if __name__ == "__main__":
    main()
