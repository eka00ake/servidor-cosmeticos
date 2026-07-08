import os
from datetime import date
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

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
    numero_unidades = db.Column(db.Integer)
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

        # 2) Insertar la fila de inventario del usuario, ya con el producto_id correcto.
        nuevo_item = InventarioUsuario(
            usuario_id=int(usuario_id),
            producto_id=producto.id,
            fecha_caducidad_fabricante=data.get('fecha_caducidad'),
            pao=pao_int,
            fecha_apertura=str(date.today()),
            numero_unidades=unidades,
            es_acabado=False,
            conclusiones=data.get('conclusiones')
        )
        db.session.add(nuevo_item)
        db.session.commit()
        return jsonify({"status": "ok", "message": "Guardado con éxito"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
