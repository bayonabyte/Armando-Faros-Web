import math
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import mysql.connector
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)
app.config['SECRET_KEY'] = 'clave_segura'
app.permanent_session_lifetime = timedelta(days=6)

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="inventario"
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
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM productos")
    total_productos = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(DISTINCT id_marca) AS total FROM productos")
    total_marcas = cursor.fetchone()["total"]

    db.close()

    return render_template("index.html",
                           total_productos=total_productos,
                           total_marcas=total_marcas)

@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
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

                extension = os.path.splitext(imagen.filename)[1]
                nombre_imagen = secure_filename(codigo + extension)

                carpeta_uploads = os.path.join('static', 'uploads')
                os.makedirs(carpeta_uploads, exist_ok=True)

                ruta_guardado = os.path.join(carpeta_uploads, nombre_imagen)

                img = Image.open(imagen)
                img = img.convert('RGB')
                img.thumbnail((800, 800))

                img.save(ruta_guardado, format="WEBP", quality=70, method=6)

                cursor.execute("""
                                UPDATE productos SET imagen = %s
                                WHERE codigo = %s
                            """, (nombre_imagen, codigo))
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

    # 🔹 Obtener marcas (FALTABA ESTO)
    cursor.execute("SELECT id, nombre FROM marcas")
    marcas = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM tipos")
    tipos = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM almacenes")
    almacenes = cursor.fetchall()

    # QUERY PRINCIPAL
    query = """
    SELECT p.*, m.nombre AS marca, mo.nombre AS modelo, t.nombre AS tipo, po.nombre AS posicion,
    p.id_lado AS lado, al.id AS almacen
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

    # 🔹 Obtener marcas (FALTABA ESTO)
    cursor.execute("SELECT id, nombre FROM marcas")
    marcas = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM tipos")
    tipos = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM almacenes")
    almacenes = cursor.fetchall()

    # 🔹 RESUMEN DE ALMACENES (CAPACIDAD)
    cursor.execute("""
        SELECT 
            al.id,
            al.nombre,
            al.capacidad_total,
            COUNT(p.id) AS productos_actuales,
            IFNULL((COUNT(p.id) * 100.0 / al.capacidad_total), 0) AS porcentaje
        FROM almacenes al
        LEFT JOIN productos p ON p.id_almacen = al.id
        GROUP BY al.id
    """)

    resumen_almacenes = cursor.fetchall()

    # QUERY PRINCIPAL
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
    codigo = request.form["codigo"]
    cantidad = int(request.form["cantidad"])

    conexion = get_db()
    cursor = conexion.cursor(dictionary=True)

    # Obtener producto
    cursor.execute("SELECT stock, imagen FROM productos WHERE codigo = %s", (codigo,))
    producto = cursor.fetchone()

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
            ruta = os.path.join("static/uploads", producto["imagen"])
            if os.path.exists(ruta):
                os.remove(ruta)

    conexion.commit()
    conexion.close()

    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(debug=True)