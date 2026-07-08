import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Configuración de la Base de Datos desde el entorno de Render
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# MODELO EXACTO SEGÚN TU DBEAVER
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

class InventarioUsuario(db.Model):
    __tablename__ = 'inventario_usuarios'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, default=1)
    producto_id = db.Column(db.Integer, default=1)
    fecha_caducidad_fabricante = db.Column(db.String(100))
    pao = db.Column(db.Integer)
    fecha_apertura = db.Column(db.String(100))
    numero_unidades = db.Column(db.Integer)
    es_acabado = db.Column(db.Boolean, default=False)
    fecha_acabado = db.Column(db.String(100))
    conclusiones = db.Column(db.Text)

# ==========================================
# RUTAS CORREGIDAS (¡ADIÓS ERRATA!)
# ==========================================

@app.route('/api/auth/register', methods=['POST'])  # 🌟 ¡Corregido aquí 'methods'!
def register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON received"}), 400
        
    user_key = data.get('nombre_usuario')
    email_key = data.get('email')
    
    existe = Usuario.query.filter((Usuario.nombre_usuario == user_key) | (Usuario.email == email_key)).first()
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
        return jsonify({"status": "ok", "message": "Usuario registrado"}), 201
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
        return jsonify({"status": "ok", "message": "Login correcto"}), 200
        
    return jsonify({"error": "Credenciales inválidas"}), 401

@app.route('/guardar', methods=['POST'])
def guardar_producto():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No se recibieron datos JSON"}), 400

    pao_limpio = data.get('pao', '12').replace('M', '').replace('m', '').strip()
    pao_int = int(pao_limpio) if pao_limpio.isdigit() else 12

    nuevo_item = InventarioUsuario(
        usuario_id=1,
        producto_id=int(data.get('codigo_producto_id', 1)), 
        fecha_caducidad_fabricante=data.get('fecha_caducidad'),
        pao=pao_int,
        fecha_apertura='2026-07-08',
        numero_unidades=int(data.get('unidades', 1)),
        es_acabado=False,
        conclusiones=data.get('conclusiones')
    )

    try:
        db.session.add(nuevo_item)
        db.session.commit()
        return jsonify({"status": "ok", "message": "Guardado con éxito"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
