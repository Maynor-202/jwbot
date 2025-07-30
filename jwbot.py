import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import schedule
import time
import hashlib
import json
import os

# === CONFIG ===
BOT_TOKEN = "7973440572:AAFBaUMR-2tteGF2HNqCkKemcV3DoleAb1A"
CHAT_ID = "@Jworgnoveda"  # Tu canal
ESTADO_ARCHIVO = "jworg_publicados.json"

# Sesión con cabeceras de navegador y reintentos
headers = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Mobile Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
    "Connection": "keep-alive",
}
s = requests.Session()
s.headers.update(headers)
s.mount("https://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=1, status_forcelist=[429,500,502,503,504])))

def cargar_estado():
    if os.path.exists(ESTADO_ARCHIVO):
        with open(ESTADO_ARCHIVO, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"hashes": []}

def guardar_estado(estado):
    with open(ESTADO_ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)

def hash_item(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()

def enviar_telegram(texto, enlace=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": texto if not enlace else f"{texto}\n{enlace}",
        "disable_web_page_preview": False,
    }
    r = requests.post(url, data=payload, timeout=60)
    r.raise_for_status()

def es_enlace_general(href: str) -> bool:
    """Evita publicar secciones genéricas (solo items concretos)."""
    # Normaliza
    u = href.rstrip("/")
    generales = {
        "/es/biblioteca", "/es/biblioteca/revistas", "/es/biblioteca/videos",
        "/es/noticias", "/es/noticias/región-mundial", "/es/publicaciones",
        "/es/biblioteca/libros", "/es/biblioteca/folletos", "/es/biblioteca/articulos"
    }
    # Si coincide exactamente con una sección general, descártalo
    if any(u == ("https://www.jw.org" + g) for g in generales):
        return True
    # También descarta si el path tiene muy pocos segmentos (p.ej. /es/noticias)
    try:
        path = u.split("://", 1)[1].split("/", 1)[1]  # después del dominio
        segmentos = [seg for seg in path.split("/") if seg]
        # ej: ["es","noticias"] => 2 segmentos => probablemente sección
        if len(segmentos) <= 2:
            return True
    except Exception:
        pass
    return False

def extraer_items(url):
    r = s.get(url, timeout=60, allow_redirects=True)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    candidatos = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        texto = (a.get_text(" ", strip=True) or "").strip()

        # Normaliza a absoluto
        if href.startswith("/"):
            href = "https://www.jw.org" + href

        # Filtros básicos
        if not href.startswith("https://www.jw.org"):
            continue
        if href.endswith("#"):
            continue
        if not texto or len(texto) < 4:
            continue

        # Interesa áreas de noticias/biblioteca/videos/publicaciones
        if any(seg in href for seg in ["/noticias", "/biblioteca", "/videos", "/publicaciones"]):
            # Evita secciones generales
            if es_enlace_general(href):
                continue
            candidatos.append((texto, href))

    # Quitar duplicados por enlace
    vistos = set()
    items = []
    for t, h in candidatos:
        if h not in vistos:
            vistos.add(h)
            items.append({"titulo": t, "enlace": h})

    return items

# === LISTA DE SECCIONES A VIGILAR (puedes ajustar) ===
URLS_A_MONITOREAR = [
    "https://www.jw.org/es/noticias/",
    "https://www.jw.org/es/biblioteca/videos/",
]

def revisar_y_publicar():
    estado = cargar_estado()
    publicados = set(estado.get("hashes", []))
    nuevos = []

    for url in URLS_A_MONITOREAR:
        try:
            items = extraer_items(url)
            for it in items:
                clave = hash_item(it["enlace"])
                if clave not in publicados:
                    nuevos.append(it)
        except Exception as e:
            print(f"[AVISO] Error al revisar {url}: {e}")

    # Publica nuevos
    for it in nuevos:
        try:
            enviar_telegram(it["titulo"], it["enlace"])
            publicados.add(hash_item(it["enlace"]))
            time.sleep(2)  # evita ráfagas
        except Exception as e:
            print(f"[AVISO] Error al publicar {it['enlace']}: {e}")

    estado["hashes"] = list(publicados)
    guardar_estado(estado)

def main():
    # Revisión inmediata
    revisar_y_publicar()
    # Luego cada 1 minuto (puedes subirlo a 15 o 60 cuando acabemos de probar)
    schedule.every(1).minutes.do(revisar_y_publicar)
    print("Bot corriendo… (CTRL+C para salir)")
    while True:
        schedule.run_pending()
        time.sleep(5)

if __name__ == "__main__":
    main()