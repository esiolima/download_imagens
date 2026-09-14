"""
Proxy de imagens eFácil/Martins — resolve o bloqueio de CORS.

O navegador não consegue buscar (fetch) imagens direto em
www.efacil.com.br porque o servidor deles não libera CORS para
outros domínios. Este endpoint roda no seu próprio servidor,
busca a imagem no eFácil (servidor -> servidor, sem restrição de
CORS) e devolve para o navegador com o header
"Access-Control-Allow-Origin: *", liberando o uso pela ferramenta.

USO:
  GET /download-proxy/{codigo}_01.jpg
  GET /download-proxy/{codigo}_02.jpg

DEPLOY (duas opções):

1) Se já existe uma app FastAPI rodando em jornaltrade.cloud
   (ex.: a ferramenta de remoção de fundo), basta copiar a função
   `proxy_image` abaixo e o `@app.get(...)` para dentro dela,
   reaproveitando o `app` existente. Não precisa de um serviço novo.

2) Se preferir isolado, rode este arquivo como um serviço próprio
   (outra porta) e aponte um reverse proxy (nginx/Caddy) do
   Hostinger para ele no caminho /download-proxy/:

     pip install fastapi uvicorn httpx --break-system-packages
     uvicorn download_proxy:app --host 127.0.0.1 --port 8010

   Depois, no nginx do jornaltrade.cloud, adicione:

     location /download-proxy/ {
         proxy_pass http://127.0.0.1:8010/download-proxy/;
     }
"""
import re

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

app = FastAPI()

EFACIL_BASE = "https://www.efacil.com.br/wcsstore/ExtendedSitesCatalogAssetStore/Imagens/1000/"

# Só aceita nomes no formato CODIGO_01.jpg / CODIGO_02.jpg —
# evita que o proxy seja usado para buscar qualquer URL arbitrária.
FILENAME_RE = re.compile(r"^[A-Za-z0-9_-]+_(01|02)\.jpg$")


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
