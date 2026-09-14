"""
Proxy de imagens eFácil/Martins — resolve o bloqueio de CORS.

O navegador não consegue buscar (fetch) imagens direto em
www.efacil.com.br porque o servidor deles não libera CORS para
outros domínios. Este serviço roda separado (Railway), busca a
imagem no eFácil servidor-a-servidor (sem restrição de CORS) e
devolve para o navegador com "Access-Control-Allow-Origin: *".

ROTAS:
  GET /                         -> health check (Railway usa pra saber se subiu)
  GET /download-proxy/{arquivo} -> ex.: /download-proxy/1704449_02.jpg

DEPLOY NO RAILWAY:
  1. Crie um repositório no GitHub só para este proxy (ex.:
     download_imagens_proxy) com estes 3 arquivos:
       - download_proxy.py
       - requirements.txt
       - Procfile
  2. No Railway: New Project -> Deploy from GitHub repo -> selecione
     esse repositório. O Railway detecta Python automaticamente,
     instala o requirements.txt e usa o Procfile pra subir.
  3. Depois do deploy, em Settings -> Networking -> Generate Domain,
     pegue a URL pública (algo como
     https://download-imagens-proxy-production.up.railway.app).
  4. No index.html da ferramenta (repo esiolima/download_imagens),
     atualize a constante IMAGE_BASE para:
       "<URL do Railway>/download-proxy/"
     e publique de novo (GitHub Pages ou onde a ferramenta estiver
     hospedada).
"""
import re

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

app = FastAPI()

EFACIL_BASE = "https://www.efacil.com.br/wcsstore/ExtendedSitesCatalogAssetStore/Imagens/1000/"

# Só aceita nomes no formato CODIGO_01.jpg / CODIGO_02.jpg —
# evita que o proxy vire uma porta aberta pra buscar qualquer URL.
FILENAME_RE = re.compile(r"^[A-Za-z0-9_-]+_(01|02)\.jpg$")


@app.get("/")
async def health():
    return {"status": "ok", "service": "download-imagens-proxy"}


@app.get("/download-proxy/{filename}")
async def proxy_image(filename: str):
    if not FILENAME_RE.fullmatch(filename):
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido")

    url = EFACIL_BASE + filename

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Erro ao contatar o servidor de origem")

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Imagem não encontrada")

    content_type = resp.headers.get("content-type", "")
    if resp.status_code != 200 or not content_type.startswith("image/"):
        raise HTTPException(status_code=502, detail="Resposta inválida do servidor de origem")

    return Response(
        content=resp.content,
        media_type=content_type,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=86400",
        },
    )
