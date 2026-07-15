import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


def sumar_meses(fecha_texto, meses):
    """Recibe una fecha en formato DD/MM/AAAA y le suma X meses, sin librerías extra."""
    try:
        fecha = datetime.strptime(fecha_texto, "%d/%m/%Y")
    except (ValueError, TypeError):
        return None

    mes_total = fecha.month - 1 + meses
    anio = fecha.year + mes_total // 12
    mes = mes_total % 12 + 1
    dia = fecha.day

    # Ajuste por si el día no existe en el mes resultante (ej. 31 de febrero)
    while True:
        try:
            return datetime(anio, mes, dia).strftime("%d/%m/%Y")
        except ValueError:
            dia -= 1

# ==========================================
# MODELOS (ahora sí, las 3 tablas de tu DBeaver)
# ==========================================
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    apellidos = db.Column(db.String(100))
    nombre_usuario = db.Column(db.String(100), unique=True, nullable=False)
    telefono = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password_hash = db.Column(db.String(255), nullable=False)

class ProductoMaestro(db.Model):
    __tablename__ = 'productos_maestros'
    id = db.Column(db.Integer, primary_key=True)
    codigo_barras = db.Column(db.String(100), unique=True)
    marca = db.Column(db.String(100))
    nombre_producto = db.Column(db.String(200))
    inci = db.Column(db.Text)
    imagen_url = db.Column(db.String(300))
    cantidad = db.Column(db.Integer)

class InventarioUsuario(db.Model):
    __tablename__ = 'inventario_usuarios'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    producto_id = db.Column(db.Integer, db.ForeignKey('productos_maestros.id'))
    fecha_caducidad_fabricante = db.Column(db.String(100))
    pao = db.Column(db.Integer)
    fecha_apertura = db.Column(db.String(100))
    fecha_caducidad_pao = db.Column(db.String(100))
    cantidad_ml = db.Column(db.Integer)
    es_acabado = db.Column(db.Boolean, default=False)
    fecha_acabado = db.Column(db.String(100))
    conclusiones = db.Column(db.Text)

# ==========================================
# AUTENTICACIÓN
# ==========================================
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON received"}), 400

    user_key = data.get('nombre_usuario')
    email_key = data.get('email')

    existe = Usuario.query.filter(
        (Usuario.nombre_usuario == user_key) | (Usuario.email == email_key)
    ).first()
    if existe:
        return jsonify({"error": "El usuario o email ya existe"}), 400

    nombre_completo = data.get('nombre_completo', '')
    partes = nombre_completo.split(' ', 1)
    nom = partes[0]
    ape = partes[1] if len(partes) > 1 else ''

    nuevo_usuario = Usuario(
        nombre=nom,
        apellidos=ape,
        nombre_usuario=user_key,
        telefono=data.get('telefono'),
        email=email_key,
        password_hash=generate_password_hash(data.get('password'))
    )

    try:
        db.session.add(nuevo_usuario)
        db.session.commit()
        return jsonify({"status": "ok", "message": "Usuario registrado", "usuario_id": nuevo_usuario.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    user_key = data.get('nombre_usuario')
    password = data.get('password')

    usuario = Usuario.query.filter_by(nombre_usuario=user_key).first()
    if usuario and check_password_hash(usuario.password_hash, password):
        # 🌟 Ahora sí devolvemos el id, la app lo necesita para guardar productos
        return jsonify({"status": "ok", "message": "Login correcto", "usuario_id": usuario.id}), 200

    return jsonify({"error": "Credenciales inválidas"}), 401

# ==========================================
# GUARDAR PRODUCTO (con buscar-o-crear en productos_maestros)
# ==========================================
@app.route('/guardar', methods=['POST'])
def guardar_producto():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No se recibieron datos JSON"}), 400

    codigo_barras = data.get('codigo_barras')
    if not codigo_barras:
        return jsonify({"error": "Falta el código de barras"}), 400

    usuario_id = data.get('usuario_id')
    if not usuario_id:
        return jsonify({"error": "Falta el usuario_id (¿el usuario no ha iniciado sesión?)"}), 400

    pao_limpio = str(data.get('pao', '12')).replace('M', '').replace('m', '').strip()
    pao_int = int(pao_limpio) if pao_limpio.isdigit() else 12
    unidades = int(data.get('unidades', 1))

    try:
        # 1) Buscar el producto por código de barras; si no existe, se crea.
        producto = ProductoMaestro.query.filter_by(codigo_barras=codigo_barras).first()
        if producto is None:
            producto = ProductoMaestro(
                codigo_barras=codigo_barras,
                marca=data.get('marca'),
                nombre_producto=data.get('nombre_producto'),
                inci=data.get('inci'),
                imagen_url=data.get('imagen_url'),
                cantidad=unidades
            )
            db.session.add(producto)
            db.session.flush()  # para obtener producto.id sin hacer commit todavía
        else:
            # 🌟 "cantidad" (contenido en ml del producto) y "numero_unidades" son el
            # mismo dato de origen: si el producto ya existía en productos_maestros,
            # se actualiza también aquí para que ambas tablas queden sincronizadas.
            producto.cantidad = unidades

        # 🌟 Ya NO se pone la fecha de hoy por defecto: si el usuario no ha
        # indicado fecha de apertura, se guarda vacía ("") y no se calcula la
        # fecha de caducidad PAO hasta que el propio usuario la indique más
        # adelante. Se usa "" en vez de None porque esas columnas de la BD
        # pueden tener restricción NOT NULL.
        fecha_apertura_final = data.get('fecha_apertura') or ""
        fecha_caducidad_pao = data.get('fecha_caducidad_pao') or ""
        if fecha_apertura_final and not fecha_caducidad_pao:
            fecha_caducidad_pao = sumar_meses(fecha_apertura_final, pao_int) or ""

        # 2) Insertar la fila de inventario del usuario, ya con el producto_id correcto.
        nuevo_item = InventarioUsuario(
            usuario_id=int(usuario_id),
            producto_id=producto.id,
            fecha_caducidad_fabricante=data.get('fecha_caducidad'),
            pao=pao_int,
            fecha_apertura=fecha_apertura_final,
            fecha_caducidad_pao=fecha_caducidad_pao,
            cantidad_ml=unidades,
            es_acabado=False,
            conclusiones=data.get('conclusiones')
        )
        db.session.add(nuevo_item)
        db.session.commit()
        return jsonify({"status": "ok", "message": "Guardado con éxito"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# OBTENER PRODUCTOS DE UN USUARIO (con datos del producto ya unidos)
# ==========================================
@app.route('/productos/<int:usuario_id>', methods=['GET'])
def obtener_productos(usuario_id):
    # 🌟 ?acabado=true devuelve los productos ya marcados como acabados;
    # por defecto (false) devuelve solo los activos.
    solo_acabados = request.args.get('acabado', 'false').lower() == 'true'
    try:
        resultados = (
            db.session.query(InventarioUsuario, ProductoMaestro)
            .join(ProductoMaestro, InventarioUsuario.producto_id == ProductoMaestro.id)
            .filter(
                InventarioUsuario.usuario_id == usuario_id,
                InventarioUsuario.es_acabado == solo_acabados
            )
            .all()
        )

        productos = []
        for inventario, producto in resultados:
            productos.append({
                "id_inventario": inventario.id,
                "codigo_barras": producto.codigo_barras,
                "marca": producto.marca,
                "nombre_producto": producto.nombre_producto,
                "inci": producto.inci,
                "imagen_url": producto.imagen_url,
                "fecha_caducidad_fabricante": inventario.fecha_caducidad_fabricante,
                "pao": inventario.pao,
                "fecha_apertura": inventario.fecha_apertura,
                "fecha_caducidad_pao": inventario.fecha_caducidad_pao,
                "numero_unidades": inventario.cantidad_ml,
                "conclusiones": inventario.conclusiones,
                "es_acabado": inventario.es_acabado,
                "fecha_acabado": inventario.fecha_acabado
            })

        return jsonify(productos), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# MARCAR UN PRODUCTO COMO ACABADO
# ==========================================
@app.route('/productos/<int:id_inventario>/acabado', methods=['PUT'])
def marcar_acabado(id_inventario):
    data = request.get_json() or {}
    item = InventarioUsuario.query.get(id_inventario)
    if not item:
        return jsonify({"error": "Producto no encontrado"}), 404

    try:
        item.es_acabado = True
        item.fecha_acabado = data.get('fecha_acabado')
        db.session.commit()
        return jsonify({"status": "ok", "message": "Producto marcado como acabado"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# GUARDAR / EDITAR LA FECHA DE APERTURA DE UN PRODUCTO YA EXISTENTE
# ==========================================
@app.route('/productos/<int:id_inventario>/apertura', methods=['PUT'])
def actualizar_apertura(id_inventario):
    data = request.get_json() or {}
    item = InventarioUsuario.query.get(id_inventario)
    if not item:
        return jsonify({"error": "Producto no encontrado"}), 404

    fecha_apertura = data.get('fecha_apertura')
    if not fecha_apertura:
        return jsonify({"error": "Falta la fecha de apertura"}), 400

    try:
        # La app ya envía la fecha de caducidad PAO calculada, pero si por
        # cualquier motivo no llegara, se recalcula aquí como respaldo
        # usando los meses de PAO ya guardados para este producto.
        fecha_caducidad_pao = data.get('fecha_caducidad_pao') or sumar_meses(fecha_apertura, item.pao or 0)

        item.fecha_apertura = fecha_apertura
        item.fecha_caducidad_pao = fecha_caducidad_pao
        db.session.commit()
        return jsonify({
            "status": "ok",
            "message": "Fecha de apertura actualizada",
            "fecha_apertura": item.fecha_apertura,
            "fecha_caducidad_pao": item.fecha_caducidad_pao
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# GUARDAR / EDITAR LAS NOTAS (CONCLUSIONES) DE UN PRODUCTO
# ==========================================
@app.route('/productos/<int:id_inventario>/notas', methods=['PUT'])
def actualizar_notas(id_inventario):
    data = request.get_json() or {}
    item = InventarioUsuario.query.get(id_inventario)
    if not item:
        return jsonify({"error": "Producto no encontrado"}), 404

    try:
        item.conclusiones = data.get('conclusiones', '')
        db.session.commit()
        return jsonify({
            "status": "ok",
            "message": "Notas actualizadas",
            "conclusiones": item.conclusiones
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# ELIMINAR UN PRODUCTO DEL INVENTARIO DEL USUARIO
# ==========================================
@app.route('/productos/<int:id_inventario>', methods=['DELETE'])
def eliminar_producto(id_inventario):
    # 🌟 Solo se borra la fila de inventario_usuarios (la del usuario). La ficha
    # en productos_maestros se deja intacta a propósito: la comparten todos los
    # usuarios que tengan ese mismo código de barras en su propio inventario.
    item = InventarioUsuario.query.get(id_inventario)
    if not item:
        return jsonify({"error": "Producto no encontrado"}), 404

    try:
        db.session.delete(item)
        db.session.commit()
        return jsonify({"status": "ok", "message": "Producto eliminado"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
