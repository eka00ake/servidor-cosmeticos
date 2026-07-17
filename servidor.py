import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import cloudinary
import cloudinary.uploader

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)


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

    while True:
        try:
            return datetime(anio, mes, dia).strftime("%d/%m/%Y")
        except ValueError:
            dia -= 1

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
    tipo_producto = db.Column(db.String(50), nullable=True)
    inci = db.Column(db.Text)
    imagen_url = db.Column(db.String(300))
    cantidad = db.Column(db.Integer)
    pao = db.Column(db.Integer)

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

class MensajeContacto(db.Model):
    __tablename__ = 'mensajes_contacto'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    nombre = db.Column(db.String(150))
    email = db.Column(db.String(150))
    mensaje = db.Column(db.Text, nullable=False)
    fecha_envio = db.Column(db.DateTime, default=datetime.utcnow)

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
        return jsonify({"status": "ok", "message": "Login correcto", "usuario_id": usuario.id}), 200

    return jsonify({"error": "Credenciales inválidas"}), 401

# ==========================================
# RECUPERACIÓN DE CONTRASEÑA
# ==========================================
@app.route('/api/auth/recuperar-password', methods=['POST'])
def recuperar_password():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON received"}), 400

    user_key = data.get('nombre_usuario')
    email_key = data.get('email')
    nueva_password = data.get('nueva_password')

    if not user_key or not email_key or not nueva_password:
        return jsonify({"error": "Faltan datos obligatorios"}), 400

    if len(nueva_password) < 6:
        return jsonify({"error": "La contraseña debe tener al menos 6 caracteres"}), 400

    usuario = Usuario.query.filter_by(nombre_usuario=user_key).first()

    if not usuario or (usuario.email or '').lower() != email_key.lower():
        return jsonify({"error": "Los datos no coinciden con ninguna cuenta"}), 404

    try:
        usuario.password_hash = generate_password_hash(nueva_password)
        db.session.commit()
        return jsonify({"status": "ok", "message": "Contraseña actualizada correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# GESTIÓN DE CUENTA
# ==========================================
@app.route('/api/usuarios/<int:usuario_id>', methods=['GET'])
def obtener_usuario(usuario_id):
    usuario = Usuario.query.get(usuario_id)
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404

    nombre_completo = (usuario.nombre or '').strip()
    if usuario.apellidos:
        nombre_completo = f"{nombre_completo} {usuario.apellidos}".strip()

    return jsonify({
        "id": usuario.id,
        "nombre_usuario": usuario.nombre_usuario,
        "nombre_completo": nombre_completo,
        "email": usuario.email,
        "telefono": usuario.telefono
    }), 200

@app.route('/api/usuarios/<int:usuario_id>', methods=['PUT'])
def actualizar_usuario(usuario_id):
    usuario = Usuario.query.get(usuario_id)
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON received"}), 400

    nuevo_nombre_usuario = data.get('nombre_usuario', usuario.nombre_usuario)
    nuevo_email = data.get('email', usuario.email)

    conflicto = Usuario.query.filter(
        Usuario.id != usuario_id,
        (Usuario.nombre_usuario == nuevo_nombre_usuario) | (Usuario.email == nuevo_email)
    ).first()
    if conflicto:
        return jsonify({"error": "El usuario o email ya está en uso por otra cuenta"}), 400

    nombre_completo = data.get('nombre_completo')
    if nombre_completo is not None:
        partes = nombre_completo.split(' ', 1)
        usuario.nombre = partes[0]
        usuario.apellidos = partes[1] if len(partes) > 1 else ''

    usuario.nombre_usuario = nuevo_nombre_usuario
    usuario.email = nuevo_email

    telefono = data.get('telefono', data.get('teléfono'))
    if telefono is not None:
        usuario.telefono = telefono

    nueva_password = data.get('password')
    if nueva_password:
        usuario.password_hash = generate_password_hash(nueva_password)

    try:
        db.session.commit()
        return jsonify({"status": "ok", "message": "Usuario actualizado"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/usuarios/<int:usuario_id>', methods=['DELETE'])
def eliminar_usuario(usuario_id):
    usuario = Usuario.query.get(usuario_id)
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404

    try:
        InventarioUsuario.query.filter_by(usuario_id=usuario_id).delete()
        db.session.delete(usuario)
        db.session.commit()
        return jsonify({"status": "ok", "message": "Cuenta eliminada"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# BUSCAR PRODUCTO POR CÓDIGO DE BARRAS
# ==========================================
@app.route('/productos/buscar/<codigo_barras>', methods=['GET'])
def buscar_producto_por_codigo(codigo_barras):
    producto = ProductoMaestro.query.filter_by(codigo_barras=codigo_barras).first()
    if not producto:
        return jsonify({"error": "Producto no encontrado"}), 404

    return jsonify({
        "id": producto.id,
        "codigo_barras": producto.codigo_barras,
        "marca": producto.marca,
        "nombre_producto": producto.nombre_producto,
        "inci": producto.inci,
        "imagen_url": producto.imagen_url,
        "cantidad": producto.cantidad,
        "pao": producto.pao,
        "tipo_producto": producto.tipo_producto  # 🌟 MODIFICADO: Ahora devuelve el tipo de producto
    }), 200

# ==========================================
# GUARDAR PRODUCTO
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
        producto = ProductoMaestro.query.filter_by(codigo_barras=codigo_barras).first()
        if producto is None:
            # 🌟 MODIFICADO: Guardar tipo_producto al crear el producto maestro nuevo
            producto = ProductoMaestro(
                codigo_barras=codigo_barras,
                marca=data.get('marca'),
                nombre_producto=data.get('nombre_producto'),
                inci=data.get('inci'),
                imagen_url=data.get('imagen_url'),
                cantidad=unidades,
                pao=pao_int,
                tipo_producto=data.get('tipo_producto')
            )
            db.session.add(producto)
            db.session.flush()
        else:
            # 🌟 MODIFICADO: Actualizar tipo_producto si ya existía el producto maestro
            producto.cantidad = unidades
            producto.pao = pao_int
            producto.tipo_producto = data.get('tipo_producto', producto.tipo_producto)
            if data.get('imagen_url'):
                producto.imagen_url = data.get('imagen_url')

        fecha_apertura_final = data.get('fecha_apertura') or ""
        fecha_caducidad_pao = data.get('fecha_caducidad_pao') or ""
        if fecha_apertura_final and not fecha_caducidad_pao:
            fecha_caducidad_pao = sumar_meses(fecha_apertura_final, pao_int) or ""

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
# OBTENER PRODUCTOS DE UN USUARIO
# ==========================================
@app.route('/productos/<int:usuario_id>', methods=['GET'])
def obtener_productos(usuario_id):
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
                "fecha_acabado": inventario.fecha_acabado,
                "tipo_producto": producto.tipo_producto # 🌟 OPCIONAL/EXTRA: También lo adjuntamos en el listado
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
# GUARDAR / EDITAR LA FECHA DE APERTURA
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
# GUARDAR / EDITAR LAS NOTAS (CONCLUSIONES)
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
# ELIMINAR UN PRODUCTO DEL INVENTARIO
# ==========================================
@app.route('/productos/<int:id_inventario>', methods=['DELETE'])
def eliminar_producto(id_inventario):
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

# ==========================================
# SUBIR FOTO DE PRODUCTO
# ==========================================
@app.route('/productos/foto', methods=['POST'])
def subir_foto_producto():
    if 'foto' not in request.files:
        return jsonify({"error": "No se recibió ningún archivo (campo 'foto')"}), 400

    archivo = request.files['foto']
    if archivo.filename == '':
        return jsonify({"error": "Archivo vacío"}), 400

    try:
        resultado = cloudinary.uploader.upload(
            archivo,
            folder="cosmeticos_productos",
            transformation=[{"width": 1024, "height": 1024, "crop": "limit"}]
        )
        return jsonify({"status": "ok", "imagen_url": resultado.get("secure_url")}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# CONTACTO / SOPORTE
# ==========================================
@app.route('/api/contacto', methods=['POST'])
def enviar_mensaje_contacto():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON received"}), 400

    mensaje = (data.get('mensaje') or '').strip()
    if not mensaje:
        return jsonify({"error": "El mensaje no puede estar vacío"}), 400

    nombre = (data.get('nombre') or '').strip()
    email = (data.get('email') or '').strip()

    if not nombre or not email:
        return jsonify({"error": "Faltan datos obligatorios"}), 400

    nuevo_mensaje = MensajeContacto(
        usuario_id=data.get('usuario_id'),
        nombre=nombre,
        email=email,
        mensaje=mensaje
    )

    try:
        db.session.add(nuevo_mensaje)
        db.session.commit()
        return jsonify({"status": "ok", "message": "Mensaje enviado correctamente"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
