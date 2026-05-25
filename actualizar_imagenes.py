from supabase import create_client
from dotenv import load_dotenv
import requests
import os

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

temas = supabase.table("temas").select("id, anime_slug, imagen_url").execute()

for tema in temas.data:
    if tema.get("imagen_url"):
        print(f"✅ {tema['anime_slug']} ya tiene imagen, saltando...")
        continue

    resp = requests.get(
        f"https://api.animethemes.moe/anime/{tema['anime_slug']}",
        params={"include": "images"},
        timeout=8
    )

    if resp.status_code != 200:
        print(f"❌ No se encontró {tema['anime_slug']}")
        continue

    data = resp.json()
    imagenes = data.get("anime", {}).get("images", [])

    imagen_url = None
    for img in imagenes:
        if img.get("facet") == "Large Cover":
            imagen_url = img.get("link")
            break
    if not imagen_url and imagenes:
        imagen_url = imagenes[0].get("link")

    if imagen_url:
        supabase.table("temas").update({"imagen_url": imagen_url}).eq("id", tema["id"]).execute()
        print(f"🖼️  {tema['anime_slug']} → imagen actualizada")
    else:
        print(f"⚠️  {tema['anime_slug']} no tiene imágenes en la API")