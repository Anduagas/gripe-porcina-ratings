from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv
import bcrypt
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


# ── Helpers ────────────────────────────────────────────

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def calcular_promedio(tema_id):
    result = supabase.table("ratings").select("puntuacion").eq("tema_id", tema_id).execute()
    if not result.data:
        return None
    puntuaciones = [r["puntuacion"] for r in result.data]
    return round(sum(puntuaciones) / len(puntuaciones), 1)


# ── Auth ───────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        nombre = request.form["nombre"].strip()
        password = request.form["password"]
        resultado = supabase.table("usuarios").select("*").eq("nombre", nombre).execute()
        if resultado.data:
            usuario = resultado.data[0]
            if bcrypt.checkpw(password.encode(), usuario["password_hash"].encode()):
                session["usuario"] = usuario["nombre"]
                session["usuario_id"] = str(usuario["id"])
                session["color_nombre"] = usuario.get("color_nombre", "#ffffff")
                session["foto_perfil"] = usuario.get("foto_perfil", "")
                return redirect(url_for("index"))
            else:
                error = "Contraseña incorrecta"
        else:
            error = "Usuario no encontrado"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Index ──────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    ratings = supabase.table("ratings")\
        .select("*, usuarios(nombre, foto_perfil, color_nombre), temas(anime_nombre, tipo, numero, titulo_cancion, video_url, imagen_url)")\
        .order("updated_at", desc=True)\
        .limit(10)\
        .execute()

    mis_ratings = supabase.table("ratings")\
        .select("puntuacion, tema_id")\
        .eq("usuario_id", session["usuario_id"])\
        .execute()

    promedio_personal = None
    mis_tema_ids = [r["tema_id"] for r in mis_ratings.data]
    if mis_ratings.data:
        puntuaciones = [r["puntuacion"] for r in mis_ratings.data]
        promedio_personal = round(sum(puntuaciones) / len(puntuaciones), 1)

    # Temas pendientes: con votos pero no todos (menos de 10) y que el usuario no haya votado
    todos_temas = supabase.table("temas").select("*").execute()
    pendientes = []
    for tema in todos_temas.data:
        ratings_tema = supabase.table("ratings")\
            .select("puntuacion, usuario_id")\
            .eq("tema_id", tema["id"])\
            .execute()

        total_votos = len(ratings_tema.data)
        if total_votos >= 10:
            continue

        # Excluir si el usuario ya votó
        ya_voto = any(r["usuario_id"] == session["usuario_id"] for r in ratings_tema.data)
        if ya_voto:
            continue

        promedio = round(sum(r["puntuacion"] for r in ratings_tema.data) / total_votos, 1) if total_votos > 0 else None
        pendientes.append({
            **tema,
            "total_votos": total_votos,
            "promedio": promedio
        })

    pendientes.sort(key=lambda x: (x["total_votos"] is not None, x["total_votos"]), reverse=True)
    print(f"Total temas: {len(todos_temas.data)}, Pendientes encontrados: {len(pendientes)}")
    for p in pendientes:
        print(f"  - {p['anime_nombre']} {p['tipo']}{p['numero']}: {p['total_votos']} votos")

    return render_template("index.html",
        usuario=session["usuario"],
        actividad=ratings.data,
        total_ratings=len(mis_ratings.data),
        promedio_personal=promedio_personal,
        pendientes=pendientes[:40]
    )

# ── Temas ──────────────────────────────────────────────

@app.route("/temas")
@login_required
def temas():
    tipo = request.args.get("tipo", "todos")
    orden = request.args.get("orden", "alfabetico")

    query = supabase.table("temas").select("*")
    if tipo != "todos":
        query = query.eq("tipo", tipo)

    result = query.order("anime_nombre").execute()

    temas_data = []
    for tema in result.data:
        mi_rating = supabase.table("ratings")\
            .select("puntuacion")\
            .eq("tema_id", tema["id"])\
            .eq("usuario_id", session["usuario_id"])\
            .execute()
        temas_data.append({
            **tema,
            "mi_rating": mi_rating.data[0]["puntuacion"] if mi_rating.data else None
        })

    # Ordenar
    if orden == "mejor":
        temas_data.sort(key=lambda x: x["mi_rating"] or 0, reverse=True)
    elif orden == "peor":
        temas_data.sort(key=lambda x: x["mi_rating"] or 999)
    else:
        temas_data.sort(key=lambda x: x["anime_nombre"].lower())

    return render_template("temas.html", temas=temas_data, tipo=tipo, orden=orden)

@app.route("/temas/<tema_id>")
@login_required
def tema_detalle(tema_id):
    tema = supabase.table("temas").select("*").eq("id", tema_id).execute()
    if not tema.data:
        return redirect(url_for("temas"))
    tema = tema.data[0]
    promedio = calcular_promedio(tema_id)

    todos_ratings = supabase.table("ratings")\
        .select("*, usuarios(nombre, foto_perfil, color_nombre)")\
        .eq("tema_id", tema_id)\
        .order("updated_at", desc=True)\
        .execute()

    mi_rating = supabase.table("ratings")\
        .select("puntuacion")\
        .eq("tema_id", tema_id)\
        .eq("usuario_id", session["usuario_id"])\
        .execute()

    # Traer otras versiones del mismo OP/ED
    versiones = supabase.table("temas")\
        .select("id, video_url, nc, resolution, source, spoiler, tags, basename")\
        .eq("anime_slug", tema["anime_slug"])\
        .eq("tipo", tema["tipo"])\
        .eq("numero", tema["numero"])\
        .execute()

    return render_template("tema_detalle.html",
        tema=tema,
        promedio=promedio,
        todos_ratings=todos_ratings.data,
        mi_rating=mi_rating.data[0]["puntuacion"] if mi_rating.data else None,
        versiones=versiones.data
    )

@app.route("/temas/<tema_id>/rating", methods=["POST"])
@login_required
def guardar_rating(tema_id):
    puntuacion = float(request.form["puntuacion"])
    if puntuacion < 1 or puntuacion > 10:
        flash("Puntuación inválida.", "error")
        return redirect(url_for("tema_detalle", tema_id=tema_id))

    supabase.table("ratings").upsert({
        "tema_id": tema_id,
        "usuario_id": session["usuario_id"],
        "puntuacion": puntuacion,
        "updated_at": "now()"
    }, on_conflict="tema_id,usuario_id").execute()

    flash("¡Rating guardado!", "success")
    return redirect(url_for("tema_detalle", tema_id=tema_id))


# ── Agregar temas ──────────────────────────────────────

@app.route("/agregar")
@login_required
def agregar():
    return render_template("agregar.html")


@app.route("/api/buscar-anime")
@login_required
def buscar_anime():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    import requests
    url = "https://api.animethemes.moe/search"
    params = {
        "q": query,
        "include[anime]": "animethemes.animethemeentries.videos,animethemes.song,images",
        "page[limit]": 5
    }

    resp = requests.get(url, params=params, timeout=8)
    if resp.status_code != 200:
        return jsonify([])

    data = resp.json()
    resultados = []

    for anime in data.get("search", {}).get("anime", []):
        imagenes = anime.get("images", [])
        imagen_url = None
        for img in imagenes:
            if img.get("facet") == "Large Cover":
                imagen_url = img.get("link")
                break
        if not imagen_url and imagenes:
            imagen_url = imagenes[0].get("link")

        for tema in anime.get("animethemes", []):
            for entry in tema.get("animethemeentries", []):
                for video in entry.get("videos", []):
                    resultados.append({
                        "anime_nombre": anime["name"],
                        "anime_slug": anime["slug"],
                        "tipo": tema["type"],
                        "numero": tema.get("sequence") or 1,
                        "titulo_cancion": tema.get("song", {}).get("title", "") if tema.get("song") else "",
                        "video_url": video["link"],
                        "basename": video["basename"],
                        "imagen_url": imagen_url or "",
                        "nc": video.get("nc", False),
                        "resolution": video.get("resolution"),
                        "source": video.get("source", ""),
                        "subbed": video.get("subbed", False),
                        "lyrics": video.get("lyrics", False),
                        "spoiler": entry.get("spoiler", False),
                        "version": entry.get("version") or 1,
                        "episodes": entry.get("episodes", ""),
                        "tags": video.get("tags", "")
                    })

    return jsonify(resultados)


@app.route("/agregar/guardar", methods=["POST"])
@login_required
def guardar_tema():
    data = {
        "anime_nombre": request.form["anime_nombre"].strip(),
        "anime_slug": request.form["anime_slug"].strip(),
        "tipo": request.form["tipo"],
        "numero": int(request.form["numero"]),
        "titulo_cancion": request.form.get("titulo_cancion", "").strip(),
        "video_url": request.form["video_url"].strip(),
        "imagen_url": request.form.get("imagen_url", "").strip(),
        "nc": request.form.get("nc", "false").lower() == "true",
        "resolution": int(request.form["resolution"]) if request.form.get("resolution") else None,
        "source": request.form.get("source", "").strip(),
        "spoiler": request.form.get("spoiler", "false").lower() == "true",
        "version": int(request.form.get("version") or 1),
        "episodes": request.form.get("episodes", "").strip(),
        "agregado_por": session["usuario_id"],
        "basename": request.form.get("basename", "").strip()
    }

    # Todas las versiones del mismo OP/ED cuentan como el mismo tema
    existe = supabase.table("temas")\
        .select("id")\
        .eq("anime_slug", data["anime_slug"])\
        .eq("tipo", data["tipo"])\
        .eq("numero", data["numero"])\
        .execute()

    if existe.data:
        flash(f"Ya existe {data['anime_nombre']} {data['tipo']}{data['numero']} en la lista. Las diferentes versiones comparten calificación.", "error")
        return redirect(url_for("agregar"))

    supabase.table("temas").insert(data).execute()
    flash(f"{data['anime_nombre']} {data['tipo']}{data['numero']} agregado correctamente.", "success")
    return redirect(url_for("temas"))


# ── Rankings ───────────────────────────────────────────

@app.route("/rankings")
@login_required
def rankings():
    filtro = request.args.get("filtro", "promedio")
    tipo = request.args.get("tipo", "todos")
    usuario_filtro = request.args.get("usuario", "todos")

    temas_result = supabase.table("temas").select("*").execute()
    usuarios_result = supabase.table("usuarios").select("id, nombre, color_nombre").execute()

    ranking_data = []
    for tema in temas_result.data:
        if tipo != "todos" and tema["tipo"] != tipo:
            continue

        if usuario_filtro != "todos":
            ratings = supabase.table("ratings").select("puntuacion, usuario_id")\
                .eq("tema_id", tema["id"])\
                .eq("usuario_id", usuario_filtro)\
                .execute()
        else:
            ratings = supabase.table("ratings").select("puntuacion, usuario_id")\
                .eq("tema_id", tema["id"])\
                .execute()

        if not ratings.data:
            continue

        puntuaciones = [r["puntuacion"] for r in ratings.data]
        promedio = round(sum(puntuaciones) / len(puntuaciones), 1)
        ranking_data.append({
            **tema,
            "promedio": promedio,
            "total_votos": len(puntuaciones)
        })

    ranking_data.sort(key=lambda x: x["promedio"], reverse=True)

    return render_template("rankings.html",
        ranking=ranking_data,
        filtro=filtro,
        tipo=tipo,
        usuario_filtro=usuario_filtro,
        usuarios=usuarios_result.data
    )


# ── Listas ─────────────────────────────────────────────

@app.route("/listas")
@login_required
def listas():
    todas = supabase.table("listas")\
        .select("*, usuarios(nombre, foto_perfil, color_nombre)")\
        .order("created_at", desc=True)\
        .execute()
    return render_template("listas.html", listas=todas.data)


@app.route("/listas/nueva", methods=["GET", "POST"])
@login_required
def nueva_lista():
    if request.method == "POST":
        nombre = request.form["nombre"].strip()
        descripcion = request.form.get("descripcion", "").strip()
        temas_ids = request.form.getlist("temas_ids")

        lista = supabase.table("listas").insert({
            "usuario_id": session["usuario_id"],
            "nombre": nombre,
            "descripcion": descripcion
        }).execute()

        lista_id = lista.data[0]["id"]
        for i, tema_id in enumerate(temas_ids):
            supabase.table("lista_items").insert({
                "lista_id": lista_id,
                "tema_id": tema_id,
                "orden": i
            }).execute()

        flash("Lista creada correctamente.", "success")
        return redirect(url_for("ver_lista", lista_id=lista_id))

    todos_temas = supabase.table("temas").select("*").order("anime_nombre").execute()
    return render_template("nueva_lista.html", temas=todos_temas.data)


@app.route("/listas/<lista_id>")
@login_required
def ver_lista(lista_id):
    lista = supabase.table("listas")\
        .select("*, usuarios(nombre, foto_perfil, color_nombre)")\
        .eq("id", lista_id)\
        .execute()
    if not lista.data:
        return redirect(url_for("listas"))

    items = supabase.table("lista_items")\
        .select("*, temas(*)")\
        .eq("lista_id", lista_id)\
        .order("orden")\
        .execute()

    temas_con_rating = []
    for item in items.data:
        tema = item["temas"]
        mi_rating = supabase.table("ratings").select("puntuacion")\
            .eq("tema_id", tema["id"])\
            .eq("usuario_id", session["usuario_id"])\
            .execute()
        promedio = calcular_promedio(tema["id"])
        temas_con_rating.append({
            **tema,
            "mi_rating": mi_rating.data[0]["puntuacion"] if mi_rating.data else None,
            "promedio": promedio
        })

    return render_template("ver_lista.html",
        lista=lista.data[0],
        temas=temas_con_rating
    )


# ── Usuarios ───────────────────────────────────────────

@app.route("/usuarios")
@login_required
def usuarios():
    todos = supabase.table("usuarios")\
        .select("id, nombre, foto_perfil, descripcion, color_nombre, created_at")\
        .execute()
    return render_template("usuarios.html", usuarios=todos.data)


@app.route("/usuarios/<usuario_id>")
@login_required
def ver_usuario(usuario_id):
    usuario = supabase.table("usuarios")\
        .select("id, nombre, foto_perfil, descripcion, color_nombre, created_at")\
        .eq("id", usuario_id)\
        .execute()
    if not usuario.data:
        return redirect(url_for("usuarios"))

    sus_ratings = supabase.table("ratings")\
        .select("*, temas(anime_nombre, tipo, numero, titulo_cancion, imagen_url)")\
        .eq("usuario_id", usuario_id)\
        .order("updated_at", desc=True)\
        .execute()

    sus_listas = supabase.table("listas")\
        .select("*")\
        .eq("usuario_id", usuario_id)\
        .execute()

    promedio = None
    if sus_ratings.data:
        puntuaciones = [r["puntuacion"] for r in sus_ratings.data]
        promedio = round(sum(puntuaciones) / len(puntuaciones), 1)

    return render_template("ver_usuario.html",
        usuario=usuario.data[0],
        ratings=sus_ratings.data,
        listas=sus_listas.data,
        promedio=promedio
    )


# ── Perfil ─────────────────────────────────────────────

@app.route("/perfil")
@login_required
def perfil():
    datos = supabase.table("usuarios").select("*").eq("id", session["usuario_id"]).execute()
    return render_template("perfil.html", usuario=datos.data[0])


@app.route("/perfil/editar", methods=["GET", "POST"])
@login_required
def editar_perfil():
    datos = supabase.table("usuarios").select("*").eq("id", session["usuario_id"]).execute()
    usuario = datos.data[0]

    if request.method == "POST":
        nuevo_nombre = request.form["nombre"].strip()
        nueva_descripcion = request.form["descripcion"].strip()
        nueva_foto = request.form["foto_perfil"].strip()
        nuevo_color = request.form.get("color_nombre", "#ffffff").strip()
        password_actual = request.form["password_actual"]
        nueva_password = request.form["nueva_password"].strip()

        if not bcrypt.checkpw(password_actual.encode(), usuario["password_hash"].encode()):
            flash("La contraseña actual es incorrecta.", "error")
            return render_template("editar_perfil.html", usuario=usuario)

        actualizacion = {
            "nombre": nuevo_nombre,
            "descripcion": nueva_descripcion,
            "foto_perfil": nueva_foto,
            "color_nombre": nuevo_color,
        }

        if nueva_password:
            actualizacion["password_hash"] = bcrypt.hashpw(
                nueva_password.encode(), bcrypt.gensalt()
            ).decode()

        if nuevo_nombre != usuario["nombre"]:
            nombre_existe = supabase.table("usuarios").select("id").eq("nombre", nuevo_nombre).execute()
            if nombre_existe.data:
                flash("Ese nombre ya lo tiene otro usuario.", "error")
                return render_template("editar_perfil.html", usuario=usuario)

        supabase.table("usuarios").update(actualizacion).eq("id", session["usuario_id"]).execute()
        session["usuario"] = nuevo_nombre
        session["color_nombre"] = nuevo_color
        session["foto_perfil"] = nueva_foto
        flash("Perfil actualizado correctamente.", "success")
        return redirect(url_for("perfil"))

    return render_template("editar_perfil.html", usuario=usuario)

@app.route("/listas/<lista_id>/editar", methods=["GET", "POST"])
@login_required
def editar_lista(lista_id):
    lista = supabase.table("listas").select("*").eq("id", lista_id).execute()
    if not lista.data:
        return redirect(url_for("listas"))

    lista = lista.data[0]
    if lista["usuario_id"] != session["usuario_id"]:
        flash("No puedes editar una lista que no es tuya.", "error")
        return redirect(url_for("ver_lista", lista_id=lista_id))

    if request.method == "POST":
        nombre = request.form["nombre"].strip()
        descripcion = request.form.get("descripcion", "").strip()
        temas_ids = request.form.getlist("temas_ids")

        supabase.table("listas").update({
            "nombre": nombre,
            "descripcion": descripcion
        }).eq("id", lista_id).execute()

        # Borrar items actuales y reinsertar
        supabase.table("lista_items").delete().eq("lista_id", lista_id).execute()
        for i, tema_id in enumerate(temas_ids):
            supabase.table("lista_items").insert({
                "lista_id": lista_id,
                "tema_id": tema_id,
                "orden": i
            }).execute()

        flash("Lista actualizada correctamente.", "success")
        return redirect(url_for("ver_lista", lista_id=lista_id))

    items_actuales = supabase.table("lista_items")\
        .select("tema_id")\
        .eq("lista_id", lista_id)\
        .execute()
    temas_en_lista = [i["tema_id"] for i in items_actuales.data]
    todos_temas = supabase.table("temas").select("*").order("anime_nombre").execute()

    return render_template("editar_lista.html",
        lista=lista,
        temas=todos_temas.data,
        temas_en_lista=temas_en_lista
    )


@app.route("/listas/<lista_id>/borrar", methods=["POST"])
@login_required
def borrar_lista(lista_id):
    lista = supabase.table("listas").select("usuario_id").eq("id", lista_id).execute()
    if lista.data and lista.data[0]["usuario_id"] == session["usuario_id"]:
        supabase.table("listas").delete().eq("id", lista_id).execute()
        flash("Lista eliminada.", "success")
    return redirect(url_for("listas"))

@app.route("/agregar/guardar-ajax", methods=["POST"])
@login_required
def guardar_tema_ajax():
    try:
        data = {
            "anime_nombre": request.form["anime_nombre"].strip(),
            "anime_slug": request.form["anime_slug"].strip(),
            "tipo": request.form["tipo"],
            "numero": int(request.form["numero"]),
            "titulo_cancion": request.form.get("titulo_cancion", "").strip(),
            "video_url": request.form["video_url"].strip(),
            "imagen_url": request.form.get("imagen_url", "").strip(),
            "nc": request.form.get("nc", "false").lower() == "true",
            "resolution": int(request.form["resolution"]) if request.form.get("resolution") else None,
            "source": request.form.get("source", "").strip(),
            "spoiler": request.form.get("spoiler", "false").lower() == "true",
            "version": int(request.form.get("version") or 1),
            "episodes": request.form.get("episodes", "").strip(),
            "basename": request.form.get("basename", "").strip(),
            "tags": request.form.get("tags", "").strip(),
            "agregado_por": session["usuario_id"]
        }

        existe = supabase.table("temas")\
            .select("id")\
            .eq("anime_slug", data["anime_slug"])\
            .eq("tipo", data["tipo"])\
            .eq("numero", data["numero"])\
            .execute()

        if existe.data:
            return jsonify({
                "ok": False,
                "mensaje": f"{data['anime_nombre']} {data['tipo']}{data['numero']} ya existe en la lista."
            })

        supabase.table("temas").insert(data).execute()
        return jsonify({
            "ok": True,
            "mensaje": f"{data['anime_nombre']} {data['tipo']}{data['numero']} agregado correctamente."
        })

    except Exception as ex:
        return jsonify({"ok": False, "mensaje": str(ex)})

if __name__ == "__main__":
    app.run(debug=True)