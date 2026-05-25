from supabase import create_client
from dotenv import load_dotenv
import bcrypt
import os

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("=== Crear nuevo usuario ===")
nombre = input("Nombre: ").strip()
password = input("Contraseña: ").strip()

# Verificar que no exista ya
existe = supabase.table("usuarios").select("id").eq("nombre", nombre).execute()
if existe.data:
    print(f"❌ Ya existe un usuario con el nombre '{nombre}'")
else:
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    supabase.table("usuarios").insert({
        "nombre": nombre,
        "password_hash": password_hash,
        "descripcion": "",
        "foto_perfil": ""
    }).execute()
    print(f"✅ Usuario '{nombre}' creado exitosamente!")