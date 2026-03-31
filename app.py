import math
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import mysql.connector
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
from PIL import Image
from dotenv import load_dotenv
import boto3
import uuid
from io import BytesIO

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'clave_segura'
app.permanent_session_lifetime = timedelta(days=6)

s3 = boto3.client(
    's3',
    endpoint_url=os.getenv("ENDPOINT"),
    aws_access_key_id=os.getenv("KEY_ID"),
    aws_secret_access_key=os.getenv("ACCESS_KEY"),
)

BUCKET = os.getenv("BUCKET_NAME")
ENDPOINT = os.getenv("ENDPOINT")

def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

def generar_url_imagen(nombre_imagen):
    if not nombre_imagen:
        return None

    return s3.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': BUCKET,
            'Key': f"productos/{nombre_imagen}"
        },
        ExpiresIn=3600  # 1 hora
    )

@app.route('/modelos')
def modelos():
    marca_id = request.args.get('marca_id')

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT id, nombre FROM modelos WHERE id_marca = %s ORDER BY nombre",
        (marca_id,)
    )

    resultados = cursor.fetchall()
    db.close()

    return jsonify(resultados)

@app.route('/', methods=['GET', 'POST'])
def login():
    if "usuario" in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        recordar = request.form.get('recordar')

        if usuario == "A123" and password == "B123":
            session.permanent = bool(recordar)
            session['usuario'] = usuario
            return redirect(url_for('index'))

        return render_template('login.html',
                           error="Usuario o contraseña incorrectas")
    return render_template('login.html')

@app.route("/index")
def index():
    if "usuario" not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT IFNULL(SUM(stock), 0) AS total FROM productos")
    total_productos = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(DISTINCT id_marca) AS total FROM productos")
    total_marcas = cursor.fetchone()["total"]

    db.close()

    return render_template("index.html",
                           total_productos=total_productos,
                           total_marcas=total_marcas)

@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if "usuario" not in session:
        return redirect(url_for('login'))
    db = get_db()
    cursor = db.cursor(dictionary=True)

    anio_actual = datetime.now().year
    mensaje_error = None

    cursor.execute("SELECT id, nombre FROM marcas")
    marcas = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM tipos")
    tipos = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM posiciones")
    posiciones = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM estados")
    estados = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM almacenes")
    almacenes = cursor.fetchall()

    codigo = None

    if request.method == 'POST':
        codigo = request.form['codigo']
        marca = request.form['marca']
        modelo = request.form['modelo']
        anio_inicio = request.form.get('anio_inicio') or None
        anio_fin = request.form.get('anio_fin') or None
        tipo = request.form['tipo']
        posicion = request.form.get('posicion') or None
        lado = request.form.get("lado") or None
        precio_compra = request.form['precio_compra']
        precio_venta = request.form['precio_venta']
        stock = request.form['stock']
        ubicacion = request.form['ubicacion'].upper().strip()
        imagen = request.files['imagen']
        estado = request.form['estado']
        almacen = request.form['almacen']

        fecha =  datetime.now()

        try:
            cursor.execute("""
                        INSERT INTO productos (codigo, id_marca, id_modelo, anio_inicio, anio_fin, id_tipo,
                        id_posicion, id_lado, precio_compra, precio_venta, stock, ubicacion, imagen, fecha_registro,
                        id_estado, id_almacen)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (codigo, marca, modelo, anio_inicio, anio_fin, tipo, posicion, lado, precio_compra,
                          precio_venta, stock, ubicacion, None, fecha, estado, almacen))

            db.commit()

            if imagen:
                nombre_imagen = f"{codigo}_{uuid.uuid4()}.webp"

                img = Image.open(imagen)
                img = img.convert('RGB')
                img.thumbnail((800, 800))

                buffer = BytesIO()
                img.save(buffer, format="WEBP", quality=70, method=6)
                buffer.seek(0)

                # 🔥 Subir al bucket
                s3.upload_fileobj(
                    buffer,
                    BUCKET,
                    f"productos/{nombre_imagen}",
                    ExtraArgs={'ContentType': 'image/webp', 'ACL': 'public-read'}
                )

                # 🔗 URL pública
                url_imagen = nombre_imagen

                cursor.execute("""
                    UPDATE productos SET imagen = %s
                    WHERE codigo = %s
                """, (url_imagen, codigo))

                db.commit()

            # Obtener nombres reales
            cursor.execute("SELECT nombre FROM marcas WHERE id=%s", (marca,))
            nombre_marca = cursor.fetchone()["nombre"]

            cursor.execute("SELECT nombre FROM modelos WHERE id=%s", (modelo,))
            nombre_modelo = cursor.fetchone()["nombre"]

            cursor.execute("SELECT nombre FROM tipos WHERE id=%s", (tipo,))
            nombre_tipo = cursor.fetchone()["nombre"]

            nombre_posicion = ""
            if posicion:
                cursor.execute("SELECT nombre FROM posiciones WHERE id=%s", (posicion,))
                nombre_posicion = cursor.fetchone()["nombre"]

            # Armar descripción bonita
            descripcion = f"{codigo} - {nombre_marca} {nombre_modelo} - {nombre_tipo}"

            if nombre_posicion:
                descripcion += f" - {nombre_posicion}"

            if lado:
                descripcion += f" ({lado})"

            cursor.execute("""
                INSERT INTO historial (tipo_accion, usuario, detalles, fecha)
                VALUES (%s, %s, %s, NOW())
            """, ("Registro", "Admin", descripcion))
            db.commit()

        except mysql.connector.IntegrityError:
            mensaje_error = "Ese producto ya existe en el inventario."
            codigo = None
        finally:
            db.close()

    return render_template('registrar.html',
                           codigo = codigo,
                           marcas=marcas,
                           anio_actual=anio_actual,
                           tipos=tipos,
                           posiciones=posiciones,
                           estados=estados,
                           almacenes=almacenes,
                           error=mensaje_error)

@app.route('/buscar', methods=['GET'])
def buscar():
    if "usuario" not in session:
        return redirect(url_for('login'))

    conexion = get_db()
    cursor = conexion.cursor(dictionary=True)

    anio_actual = datetime.now().year

    productos_por_pagina = 10
    pagina = request.args.get("page", 1, type=int)

    busqueda = request.args.get("busqueda", "").upper().strip()
    marca = request.args.get("marca", "")
    anio = request.args.get("anio", "")
    tipo = request.args.get("tipo", "")
    almacen = request.args.get("almacen", "")

    offset = (pagina - 1) * productos_por_pagina

    cursor.execute("SELECT id, nombre FROM marcas")
    marcas = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM tipos")
    tipos = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM almacenes")
    almacenes = cursor.fetchall()

    query = """
    SELECT p.*, m.nombre AS marca, mo.nombre AS modelo, t.nombre AS tipo, po.nombre AS posicion,
    p.id_lado AS lado, al.id AS almacen, al.nombre AS almacen
    FROM productos p
    LEFT JOIN marcas m ON p.id_marca = m.id
    LEFT JOIN modelos mo ON p.id_modelo = mo.id
    LEFT JOIN tipos t ON p.id_tipo = t.id
    LEFT JOIN posiciones po ON p.id_posicion = po.id
    LEFT JOIN almacenes al on p.id_almacen = al.id
    WHERE 1=1
    """
    params = []

    if busqueda:
        query += """
        AND (m.nombre LIKE %s OR mo.nombre LIKE %s OR p.codigo LIKE %s)
        """
        params.extend(["%" + busqueda + "%"] * 3)

    if marca:
        query += " AND p.id_marca = %s"
        params.append(marca)

    if anio:
        query += """
        AND NOT (p.anio_inicio IS NULL AND p.anio_fin IS NULL)
        AND (
            (p.anio_inicio IS NULL OR p.anio_inicio <= %s)
            AND
            (p.anio_fin IS NULL OR p.anio_fin >= %s)
        )
        """
        params.extend([anio, anio])

    if tipo:
        query += " AND p.id_tipo = %s"
        params.append(tipo)

    if almacen:
        query += " AND p.id_almacen = %s"
        params.append(almacen)

    # COUNT
    count_query = """
        SELECT COUNT(*) AS total
        FROM productos p
        LEFT JOIN marcas m ON p.id_marca = m.id
        LEFT JOIN modelos mo ON p.id_modelo = mo.id
        LEFT JOIN tipos t ON p.id_tipo = t.id
        LEFT JOIN posiciones po ON p.id_posicion = po.id
        LEFT JOIN almacenes al ON p.id_almacen = al.id
        LEFT JOIN estados e ON p.id_estado = e.id
        WHERE 1=1
    """
    count_params = []

    if busqueda:
        count_query += " AND (m.nombre LIKE %s OR mo.nombre LIKE %s OR p.codigo LIKE %s)"
        count_params.extend(["%" + busqueda + "%"] * 3)

    if marca:
        count_query += " AND p.id_marca = %s"
        count_params.append(marca)

    if anio:
        count_query += """
        AND NOT (p.anio_inicio IS NULL AND p.anio_fin IS NULL)
        AND (
            (p.anio_inicio IS NULL OR p.anio_inicio <= %s)
            AND
            (p.anio_fin IS NULL OR p.anio_fin >= %s)
        )
        """
        count_params.extend([anio, anio])

    if tipo:
        count_query += " AND p.id_tipo = %s"
        count_params.append(tipo)

    if almacen:
        count_query += " AND p.id_almacen = %s"
        count_params.append(almacen)

    cursor.execute(count_query, count_params)
    total_productos = cursor.fetchone()["total"]

    # PAGINACIÓN
    query += " LIMIT %s OFFSET %s"
    params.extend([productos_por_pagina, offset])

    cursor.execute(query, params)
    productos = cursor.fetchall()
    for p in productos:
        if p["imagen"]:
            p["imagen"] = generar_url_imagen(p["imagen"])

    total_paginas = max(1, math.ceil(total_productos / productos_por_pagina))

    conexion.close()

    return render_template(
        'buscar.html',
        productos=productos,
        marcas=marcas,
        tipos=tipos,
        tipo=tipo,
        anio_actual=anio_actual,
        pagina=pagina,
        total_paginas=total_paginas,
        busqueda=busqueda,
        marca=marca,
        anio=anio,
        almacen=almacen,
        almacenes=almacenes,
    )

@app.route("/almacen", methods=["GET"])
def almacen():
    if "usuario" not in session:
        return redirect(url_for('login'))
    conexion = get_db()
    cursor = conexion.cursor(dictionary=True)

    anio_actual = datetime.now().year

    productos_por_pagina = 10
    pagina = request.args.get("page", 1, type=int)

    busqueda = request.args.get("busqueda", "").upper().strip()
    marca = request.args.get("marca", "")
    anio = request.args.get("anio", "")
    tipo = request.args.get("tipo", "")
    almacen = request.args.get("almacen", "")

    offset = (pagina - 1) * productos_por_pagina

    cursor.execute("SELECT id, nombre FROM marcas")
    marcas = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM tipos")
    tipos = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM almacenes")
    almacenes = cursor.fetchall()

    cursor.execute("""
        SELECT 
            al.id,
            al.nombre,
            al.capacidad_total,
            IFNULL(SUM(p.stock), 0) AS productos_actuales,
            IFNULL((SUM(p.stock) * 100.0 / al.capacidad_total), 0) AS porcentaje
        FROM almacenes al
        LEFT JOIN productos p ON p.id_almacen = al.id
        GROUP BY al.id
    """)

    resumen_almacenes = cursor.fetchall()

    query = """
        SELECT p.*, 
           m.nombre AS marca, 
           mo.nombre AS modelo, 
           t.nombre AS tipo, 
           po.nombre AS posicion,
           p.id_lado AS lado, 
           al.nombre AS almacen,
           e.nombre AS estado
        FROM productos p
        LEFT JOIN marcas m ON p.id_marca = m.id
        LEFT JOIN modelos mo ON p.id_modelo = mo.id
        LEFT JOIN tipos t ON p.id_tipo = t.id
        LEFT JOIN posiciones po ON p.id_posicion = po.id
        LEFT JOIN almacenes al ON p.id_almacen = al.id
        LEFT JOIN estados e ON p.id_estado = e.id
        WHERE 1=1
        """
    params = []

    if busqueda:
        query += """
            AND (m.nombre LIKE %s OR mo.nombre LIKE %s OR p.codigo LIKE %s)
            """
        params.extend(["%" + busqueda + "%"] * 3)

    if marca:
        query += " AND p.id_marca = %s"
        params.append(marca)

    if anio:
        query += """
            AND NOT (p.anio_inicio IS NULL AND p.anio_fin IS NULL)
            AND (
                (p.anio_inicio IS NULL OR p.anio_inicio <= %s)
                AND
                (p.anio_fin IS NULL OR p.anio_fin >= %s)
            )
            """
        params.extend([anio, anio])

    if tipo:
        query += " AND p.id_tipo = %s"
        params.append(tipo)

    if almacen:
        query += " AND p.id_almacen = %s"
        params.append(almacen)

    # COUNT
    count_query = """
        SELECT COUNT(*) AS total
        FROM productos p
        LEFT JOIN marcas m ON p.id_marca = m.id
        LEFT JOIN modelos mo ON p.id_modelo = mo.id
        LEFT JOIN tipos t ON p.id_tipo = t.id
        LEFT JOIN posiciones po ON p.id_posicion = po.id
        LEFT JOIN almacenes al ON p.id_almacen = al.id
        LEFT JOIN estados e ON p.id_estado = e.id
        WHERE 1=1
    """
    count_params = []

    if busqueda:
        count_query += " AND (m.nombre LIKE %s OR mo.nombre LIKE %s OR p.codigo LIKE %s)"
        count_params.extend(["%" + busqueda + "%"] * 3)

    if marca:
        count_query += " AND p.id_marca = %s"
        count_params.append(marca)

    if anio:
        count_query += """
        AND NOT (p.anio_inicio IS NULL AND p.anio_fin IS NULL)
        AND (
            (p.anio_inicio IS NULL OR p.anio_inicio <= %s)
            AND
            (p.anio_fin IS NULL OR p.anio_fin >= %s)
        )
        """
        count_params.extend([anio, anio])

    if tipo:
        count_query += " AND p.id_tipo = %s"
        count_params.append(tipo)

    if almacen:
        count_query += " AND p.id_almacen = %s"
        count_params.append(almacen)

    cursor.execute(count_query, count_params)
    total_productos = cursor.fetchone()["total"]

    # PAGINACIÓN
    query += " LIMIT %s OFFSET %s"
    params.extend([productos_por_pagina, offset])

    cursor.execute(query, params)
    productos = cursor.fetchall()
    for p in productos:
        if p["imagen"]:
            p["imagen"] = generar_url_imagen(p["imagen"])

    total_paginas = max(1, math.ceil(total_productos / productos_por_pagina))

    conexion.close()
    return render_template("almacen.html",
                           productos=productos,
                           marcas=marcas,
                           tipos=tipos,
                           tipo=tipo,
                           anio_actual=anio_actual,
                           pagina=pagina,
                           total_paginas=total_paginas,
                           busqueda=busqueda,
                           marca=marca,
                           anio=anio,
                           almacen=almacen,
                           almacenes=almacenes,
                           resumen_almacenes=resumen_almacenes
                           )

@app.route("/retirar", methods=["POST"])
def retirar():
    if "usuario" not in session:
        return redirect(url_for('login'))
    codigo = request.form["codigo"]
    cantidad = int(request.form["cantidad"])

    conexion = get_db()
    cursor = conexion.cursor(dictionary=True)

    # Obtener producto
    cursor.execute("SELECT stock, imagen FROM productos WHERE codigo = %s", (codigo,))
    producto = cursor.fetchone()

    cursor.execute("""
        SELECT m.nombre AS marca, mo.nombre AS modelo
        FROM productos p
        LEFT JOIN marcas m ON p.id_marca = m.id
        LEFT JOIN modelos mo ON p.id_modelo = mo.id
        WHERE p.codigo = %s
    """, (codigo,))

    info = cursor.fetchone()
    nombre_producto = f"{info['marca']} {info['modelo']}" if info else codigo

    if not producto:
        conexion.close()
        return jsonify({"success": False, "error": "Producto no encontrado"})

    stock_actual = producto["stock"]

    if cantidad > stock_actual:
        conexion.close()
        return jsonify({"success": False, "error": "Stock insuficiente"})

    nuevo_stock = stock_actual - cantidad

    if nuevo_stock > 0:
        cursor.execute("""
            UPDATE productos 
            SET stock = %s 
            WHERE codigo = %s
        """, (nuevo_stock, codigo))

    else:
        cursor.execute("DELETE FROM productos WHERE codigo = %s", (codigo,))

        if producto["imagen"]:
            nombre = producto["imagen"].split("/")[-1]

            s3.delete_object(
                Bucket=BUCKET,
                Key=f"productos/{nombre}"
            )


    nombre_producto = f"{info['marca']} {info['modelo']}" if info else codigo

    if nuevo_stock > 0:
        descripcion = f"Retiro de {cantidad} unidad(es) de {nombre_producto} ({codigo}). Stock: {stock_actual} → {nuevo_stock}"
    else:
        descripcion = f"Producto {nombre_producto} ({codigo}) eliminado por retiro total de {cantidad} unidad(es)"

    cursor.execute("""
        INSERT INTO historial (tipo_accion, usuario, detalles, fecha)
        VALUES (%s, %s, %s, NOW())
    """, ("Retiro", "Admin", descripcion))

    conexion.commit()
    conexion.close()

    return jsonify({"success": True})

@app.route("/administrar", methods=["GET"])
def admin_inventario():
    if "usuario" not in session:
        return redirect(url_for('login'))
    conexion = get_db()
    cursor = conexion.cursor(dictionary=True)

    anio_actual = datetime.now().year

    productos_por_pagina = 10
    pagina = request.args.get("page", 1, type=int)

    busqueda = request.args.get("busqueda", "").upper().strip()
    marca = request.args.get("marca", "")
    anio = request.args.get("anio", "")
    tipo = request.args.get("tipo", "")
    almacen = request.args.get("almacen", "")

    offset = (pagina - 1) * productos_por_pagina

    cursor.execute("SELECT id, nombre FROM marcas")
    marcas = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM tipos")
    tipos = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM almacenes")
    almacenes = cursor.fetchall()

    query = """
       SELECT p.*, m.nombre AS marca, mo.nombre AS modelo, t.nombre AS tipo, po.nombre AS posicion,
       p.id_lado AS lado, al.id AS almacen, al.nombre AS almacen
       FROM productos p
       LEFT JOIN marcas m ON p.id_marca = m.id
       LEFT JOIN modelos mo ON p.id_modelo = mo.id
       LEFT JOIN tipos t ON p.id_tipo = t.id
       LEFT JOIN posiciones po ON p.id_posicion = po.id
       LEFT JOIN almacenes al on p.id_almacen = al.id
       WHERE 1=1
       """
    params = []

    if busqueda:
        query += """
           AND (m.nombre LIKE %s OR mo.nombre LIKE %s OR p.codigo LIKE %s)
           """
        params.extend(["%" + busqueda + "%"] * 3)

    if marca:
        query += " AND p.id_marca = %s"
        params.append(marca)

    if anio:
        query += """
           AND NOT (p.anio_inicio IS NULL AND p.anio_fin IS NULL)
           AND (
               (p.anio_inicio IS NULL OR p.anio_inicio <= %s)
               AND
               (p.anio_fin IS NULL OR p.anio_fin >= %s)
           )
           """
        params.extend([anio, anio])

    if tipo:
        query += " AND p.id_tipo = %s"
        params.append(tipo)

    if almacen:
        query += " AND p.id_almacen = %s"
        params.append(almacen)

    count_query = """
           SELECT COUNT(*) AS total
           FROM productos p
           LEFT JOIN marcas m ON p.id_marca = m.id
           LEFT JOIN modelos mo ON p.id_modelo = mo.id
           LEFT JOIN tipos t ON p.id_tipo = t.id
           LEFT JOIN posiciones po ON p.id_posicion = po.id
           LEFT JOIN almacenes al ON p.id_almacen = al.id
           LEFT JOIN estados e ON p.id_estado = e.id
           WHERE 1=1
       """
    count_params = []

    if busqueda:
        count_query += " AND (m.nombre LIKE %s OR mo.nombre LIKE %s OR p.codigo LIKE %s)"
        count_params.extend(["%" + busqueda + "%"] * 3)

    if marca:
        count_query += " AND p.id_marca = %s"
        count_params.append(marca)

    if anio:
        count_query += """
           AND NOT (p.anio_inicio IS NULL AND p.anio_fin IS NULL)
           AND (
               (p.anio_inicio IS NULL OR p.anio_inicio <= %s)
               AND
               (p.anio_fin IS NULL OR p.anio_fin >= %s)
           )
           """
        count_params.extend([anio, anio])

    if tipo:
        count_query += " AND p.id_tipo = %s"
        count_params.append(tipo)

    if almacen:
        count_query += " AND p.id_almacen = %s"
        count_params.append(almacen)

    cursor.execute(count_query, count_params)
    total_productos = cursor.fetchone()["total"]

    # PAGINACIÓN
    query += " LIMIT %s OFFSET %s"
    params.extend([productos_por_pagina, offset])

    cursor.execute(query, params)
    productos = cursor.fetchall()
    for p in productos:
        if p["imagen"]:
            p["imagen"] = generar_url_imagen(p["imagen"])

    total_paginas = max(1, math.ceil(total_productos / productos_por_pagina))


    # 📊 Patrimonio (costo total)
    cursor.execute("SELECT SUM(precio_compra * stock) AS patrimonio FROM productos")
    patrimonio = cursor.fetchone()["patrimonio"] or 0

    # 📊 Ventas (valor total)
    cursor.execute("SELECT SUM(precio_venta * stock) AS ventas FROM productos")
    ventas = cursor.fetchone()["ventas"] or 0

    # 📜 Historial
    cursor.execute("""
        SELECT tipo_accion, detalles, fecha
        FROM historial
        ORDER BY fecha DESC
        LIMIT 5
    """)
    historial = cursor.fetchall()

    conexion.close()

    return render_template(
        "administrar.html",
        patrimonio=patrimonio,
        ventas=ventas,
        productos=productos,
        historial=historial,
        marcas=marcas,
        tipos=tipos,
        tipo=tipo,
        anio_actual=anio_actual,
        pagina=pagina,
        total_paginas=total_paginas,
        busqueda=busqueda,
        marca=marca,
        anio=anio,
        almacen=almacen,
        almacenes=almacenes,
    )

@app.route("/historial")
def ver_historial():
    if "usuario" not in session:
        return redirect(url_for('login'))
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    historial_por_pagina = 20
    pagina = request.args.get("page", 1, type=int)

    offset = (pagina - 1) * historial_por_pagina

    cursor.execute("SELECT COUNT(*) AS total FROM historial")
    total_historial = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT tipo_accion, detalles, fecha
        FROM historial
        ORDER BY fecha DESC
        LIMIT %s OFFSET %s
    """, (historial_por_pagina, offset))

    historial = cursor.fetchall()

    total_paginas = max(1, math.ceil(total_historial / historial_por_pagina))


    conn.close()

    return render_template("admin/historial.html",
                           historial=historial,
                           pagina=pagina,
                           total_paginas=total_paginas)

@app.route("/producto/<int:id>")
def get_producto(id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT p.*, 
               m.nombre AS marca, 
               mo.nombre AS modelo
        FROM productos p
        LEFT JOIN marcas m ON p.id_marca = m.id
        LEFT JOIN modelos mo ON p.id_modelo = mo.id
        WHERE p.id = %s
    """, (id,))

    producto = cursor.fetchone()
    conn.close()

    return producto

@app.route("/admin/marca-modelo")
def vista_marca_modelo():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, nombre FROM marcas")
    marcas = cursor.fetchall()

    conn.close()

    return render_template("admin/marca_modelo.html", marcas=marcas)

@app.route("/admin/marca-modelo", methods=["POST"])
def guardar_marca_modelo():
    conn = get_db()
    cursor = conn.cursor()

    marca_id = request.form.get("marca_id")
    nueva_marca = (request.form.get("nueva_marca") or "").upper().strip()
    codigo_marca = (request.form.get("codigo_marca") or "").upper().strip()

    modelo = request.form.get("modelo").upper().strip()
    codigo_modelo = request.form.get("codigo_modelo").upper().strip()
    tipo = request.form.get("tipo")

    usuario = "Admin"

    if tipo == "marca_modelo":
        if not nueva_marca or not codigo_marca:
            conn.close()
            return "Debes ingresar una nueva marca o seleccionar una existente"

        cursor.execute("SELECT id FROM marcas WHERE LOWER(nombre)=LOWER(%s)", (nueva_marca,))
        existe = cursor.fetchone()

        if existe:
            marca_id = existe[0]
        else:
            cursor.execute("""
                INSERT INTO marcas (nombre, codigo)
                VALUES (%s, %s)
            """, (nueva_marca, codigo_marca))
            marca_id = cursor.lastrowid

    cursor.execute("""
        SELECT id FROM modelos 
        WHERE nombre=%s AND id_marca=%s
    """, (modelo, marca_id))

    if cursor.fetchone():
        conn.close()
        return "Este modelo ya existe para esa marca"

    cursor.execute("""
        INSERT INTO modelos (id_marca, nombre, codigo)
        VALUES (%s, %s, %s)
    """, (marca_id, modelo, codigo_modelo))

    if nueva_marca:
        descripcion = f"Marca {nueva_marca} con modelo {modelo} añadidos a la base de datos"
    else:
        cursor.execute("SELECT nombre FROM marcas WHERE id=%s", (marca_id,))
        nombre_marca = cursor.fetchone()[0]

        descripcion = f"Modelo {modelo} añadido a la marca {nombre_marca}"

    cursor.execute("""
        INSERT INTO historial (producto_id, tipo_accion, usuario, detalles)
        VALUES (NULL, 'Añadido', %s, %s)
    """, (usuario, descripcion))

    conn.commit()
    conn.close()
    return redirect(url_for("admin_inventario"))

@app.route("/editar_producto/<int:id>", methods=["GET", "POST"])
def editar_producto(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT id, nombre FROM marcas")
    marcas = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM tipos")
    tipos = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM posiciones")
    posiciones = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM estados")
    estados = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM almacenes")
    almacenes = cursor.fetchall()

    cursor.execute("SELECT * FROM productos WHERE id=%s", (id,))
    producto = cursor.fetchone()

    if not producto:
        return redirect(url_for("admin_inventario"))

    cursor.execute(
        "SELECT id, nombre FROM modelos WHERE id_marca=%s",
        (producto["id_marca"],)
    )
    modelos = cursor.fetchall()

    if request.method == "POST":

        codigo = request.form["codigo"]
        marca = request.form["marca"]
        modelo = request.form["modelo"]
        anio_inicio = request.form.get("anio_inicio") or None
        anio_fin = request.form.get("anio_fin") or None
        tipo = request.form["tipo"]
        posicion = request.form.get("posicion") or None
        lado = request.form.get("lado") or None
        precio_compra = request.form["precio_compra"]
        precio_venta = request.form["precio_venta"]
        stock = request.form["stock"]
        ubicacion = request.form["ubicacion"].upper().strip()
        estado = request.form["estado"]
        almacen = request.form["almacen"]
        imagen = request.files.get("imagen")

        anterior = dict(producto)

        cursor.execute("""
            UPDATE productos SET
            codigo=%s,
            id_marca=%s,
            id_modelo=%s,
            anio_inicio=%s,
            anio_fin=%s,
            id_tipo=%s,
            id_posicion=%s,
            id_lado=%s,
            precio_compra=%s,
            precio_venta=%s,
            stock=%s,
            ubicacion=%s,
            id_estado=%s,
            id_almacen=%s
            WHERE id=%s
        """, (
            codigo, marca, modelo,
            anio_inicio, anio_fin, tipo,
            posicion, lado,
            precio_compra, precio_venta,
            stock, ubicacion,
            estado, almacen,
            id
        ))

        cambios = []

        if str(anterior["codigo"]) != str(codigo):
            cambios.append(f"Código {anterior['codigo']} → {codigo}")

        if str(anterior["precio_venta"]) != str(precio_venta):
            cambios.append(f"Precio venta {anterior['precio_venta']} → {precio_venta}")

        if str(anterior["stock"]) != str(stock):
            cambios.append(f"Stock {anterior['stock']} → {stock}")

        if str(anterior["id_modelo"]) != str(modelo):
            cambios.append("Modelo cambiado")

        if str(anterior["id_tipo"]) != str(tipo):
            cambios.append("Tipo cambiado")

        if str(anterior["id_posicion"]) != str(posicion):
            cambios.append("Posición cambiada")

        if str(anterior["id_lado"]) != str(lado):
            cambios.append("Lado cambiado")

        if str(anterior["id_almacen"]) != str(almacen):
            cambios.append("Almacén cambiado")

        if imagen and imagen.filename != "":

            # 🔥 borrar imagen anterior del bucket
            if producto["imagen"]:
                nombre_anterior = producto["imagen"].split("/")[-1]

                s3.delete_object(
                    Bucket=BUCKET,
                    Key=f"productos/{nombre_anterior}"
                )

            nombre_imagen = f"{codigo}_{uuid.uuid4()}.webp"

            img = Image.open(imagen)
            img = img.convert("RGB")
            img.thumbnail((800, 800))

            buffer = BytesIO()
            img.save(buffer, format="WEBP", quality=70)
            buffer.seek(0)

            s3.upload_fileobj(
                buffer,
                BUCKET,
                f"productos/{nombre_imagen}",
                ExtraArgs={'ContentType': 'image/webp', 'ACL': 'public-read'}
            )

            url_imagen = nombre_imagen

            cursor.execute("""
                UPDATE productos SET imagen=%s WHERE id=%s
            """, (url_imagen, id))

            cambios.append("Imagen actualizada")

        descripcion = f"Producto {anterior['codigo']}\n"

        if cambios:
            descripcion += "\n".join(cambios)
        else:
            descripcion += "Sin cambios relevantes"

        cursor.execute("""
            INSERT INTO historial (tipo_accion, usuario, detalles, fecha)
            VALUES (%s, %s, %s, NOW())
        """, ("Edición", "Admin", descripcion))

        db.commit()

        return redirect(url_for("admin_inventario"))

    return render_template(
        "editar_producto.html",
        producto=producto,
        marcas=marcas,
        tipos=tipos,
        posiciones=posiciones,
        estados=estados,
        almacenes=almacenes,
        modelos=modelos
    )

@app.route('/eliminar_producto/<int:id>', methods=['POST'])
def eliminar_producto(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            p.codigo,
            p.imagen,
            m.nombre AS marca,
            mo.nombre AS modelo,
            t.nombre AS tipo
        FROM productos p
        JOIN marcas m ON p.id_marca = m.id
        JOIN modelos mo ON p.id_modelo = mo.id
        JOIN tipos t ON p.id_tipo = t.id
        WHERE p.id = %s
    """, (id,))

    producto = cursor.fetchone()

    if not producto:
        return jsonify({"success": False, "error": "Producto no encontrado"})

    # 2. BORRAR IMAGEN DEL SISTEMA
    if producto["imagen"]:
        nombre = producto["imagen"].split("/")[-1]

        s3.delete_object(
            Bucket=BUCKET,
            Key=f"productos/{nombre}"
        )

    descripcion = f"{producto['codigo']} - {producto['marca']} {producto['modelo']} - {producto['tipo']}"

    cursor.execute("DELETE FROM productos WHERE id = %s", (id,))

    cursor.execute("""
        INSERT INTO historial (tipo_accion, usuario, detalles, fecha)
        VALUES (%s, %s, %s, NOW())
    """, ("Eliminado", "Admin", descripcion))

    db.commit()
    cursor.close()
    db.close()

    return jsonify({"success": True})

#te amo katerine <3

if __name__ == '__main__':
    app.run(debug=True)