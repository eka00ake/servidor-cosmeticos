import os
import psycopg2
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Listas en memoria por si la base de datos de Render falla o no está configurada
PRODUCTOS_LOCALES = []
USUARIOS_LOCALES = {} # Respaldo rápido clave-valor para usuarios en memoria

# ==========================================
# 🔐 SECCIÓN: GESTIÓN DE USUARIOS EN POSTGRES
# ==========================================

def registrar_usuario_postgres(username, nombre_real, email, telefono, password):
    url_base_datos = os.environ.get('DATABASE_URL')
    if not url_base_datos:
        print("Falta DATABASE_URL. Guardando usuario en modo local temporal.")
        return False

    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(url_base_datos)
        cursor = conn.cursor()
        
        # 🆕 Creamos la tabla de usuarios si no existe con todas las columnas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                nombre_real VARCHAR(255),
                email VARCHAR(255),
                telefono VARCHAR(100),
                password VARCHAR(255) NOT NULL
            );
        """)
        
        # Encriptamos la contraseña por seguridad básica
        password_encriptada = generate_password_hash(password)
        
        cursor.execute(
            "INSERT INTO usuarios (username, nombre_real, email, telefono, password) VALUES (%s, %s, %s, %s, %s);",
            (username, nombre_real, email, telefono, password_encriptada)
        )
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error de conexión con PostgreSQL al registrar usuario: {e}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def verificar_usuario_postgres(username, password):
    url_base_datos = os.environ.get('DATABASE_URL')
    if not url_base_datos:
        return False

    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(url_base_datos)
        cursor = conn.cursor()
        
        cursor.execute("SELECT password FROM usuarios WHERE username = %s;", (username,))
        fila = cursor.fetchone()
        
        if fila:
            # Comparamos la contraseña encriptada
            return check_password_hash(fila[0], password)
        return False
    except Exception as e:
        print(f"Error al verificar usuario en Postgres: {e}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ==========================================
# 🧴 SECCIÓN: GESTIÓN DE COSMÉTICOS EXISTENTE
# ==========================================

def guardar_en_postgres(codigo, nombre, inci, fecha_cad):
    url_base_datos = os.environ.get('DATABASE_URL')
    if not url_base_datos:
        print("Falta la variable DATABASE_URL. Guardando en modo local temporal.")
        return False

    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(url_base_datos)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cosmeticos (
                id SERIAL PRIMARY KEY,
                codigo VARCHAR(100),
                nombre VARCHAR(255),
                inci TEXT,
                fecha_caducidad VARCHAR(100)
            );
        """)
        
        cursor.execute(
            "INSERT INTO cosmeticos (codigo, nombre, inci, fecha_caducidad) VALUES (%s, %s, %s, %s);",
            (codigo, nombre, inci, fecha_cad)
        )
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error de conexión con PostgreSQL al guardar: {e}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def obtener_de_postgres():
    url_base_datos = os.environ.get('DATABASE_URL')
    if not url_base_datos:
        return None

    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(url_base_datos)
        cursor = conn.cursor()
        
        cursor.execute("SELECT codigo, nombre, inci, fecha_caducidad FROM cosmeticos;")
        filas = cursor.fetchall()
        
        lista_productos = []
        for fila in filas:
            lista_productos.append({
                "codigo": fila[0],
                "nombre": fila[1],
                "inci": fila[2],
                "fecha_caducidad": fila[3]
            })
        return lista_productos
    except Exception as e:
        print(f"Error de conexión con PostgreSQL al leer: {e}")
        return None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ==========================================
# 🌐 ENDPOINTS / RUTAS DE LA API
# ==========================================

# 🆕 NUEVA RUTA: Recibe el registro completo desde Android
@app.route('/api/auth/register', methods=['POST'])
def api_registrar_usuario():
    datos = request.json
    if not datos:
        return jsonify({"status": "error", "mensaje": "JSON vacío"}), 400
        
    username = datos.get('username')
    nombre_real = datos.get('nombre_real')
    email = datos.get('email')
    telefono = datos.get('telefono')
    password = datos.get('password')
    
    exito = registrar_usuario_postgres(username, nombre_real, email, telefono, password)
    
    if exito:
        return jsonify({"status": "ok", "mensaje": "Usuario guardado en base de datos"}), 201
    else:
        # PLAN B: Si la DB falla, se guarda en el diccionario de memoria local
        USUARIOS_LOCALES[username] = password
        return jsonify({"status": "ok", "mensaje": "Registrado temporalmente en memoria"}), 201


# 🆕 NUEVA RUTA: Atiende el inicio de sesión desde Android
@app.route('/api/auth/login', methods=['POST'])
def api_iniciar_sesion():
    datos = request.json
    if not datos:
        return jsonify({"status": "error", "mensaje": "JSON vacío"}), 400
        
    username = datos.get('username')
    password = datos.get('password')
    
    # Intentamos validar con base de datos real
    autorizado = verificar_usuario_postgres(username, password)
    
    # Si no está en DB real, miramos en memoria local de respaldo
    if not autorizado and username in USUARIOS_LOCALES:
        autorizado = (USUARIOS_LOCALES[username] == password)
        
    if autorizado:
        return jsonify({"status": "ok", "mensaje": "Login correcto"}), 200
    else:
        return jsonify({"status": "error", "mensaje": "Credenciales inválidas"}), 401


@app.route('/guardar', methods=['POST'])
def guardar_cosmetico():
    datos = request.json
    if not datos:
        return jsonify({"status": "error", "mensaje": "JSON vacío"}), 400
        
    codigo = datos.get('codigo')
    nombre = datos.get('nombre')
    inci = datos.get('inci')
    fecha_cad = datos.get('fechaCaducidad')
    
    exito = guardar_en_postgres(codigo, nombre, inci, fecha_cad)
    
    if exito:
        return jsonify({"status": "ok", "mensaje": "Guardado en Postgres online"}), 200
    else:
        nuevo_producto = {
            "codigo": codigo,
            "nombre": nombre,
            "inci": inci,
            "fecha_caducidad": fecha_cad
        }
        PRODUCTOS_LOCALES.append(nuevo_producto)
        print(f"Producto respaldado en memoria: {nombre}")
        return jsonify({"status": "ok", "mensaje": "Guardado temporal en memoria del servidor"}), 200


@app.route('/cosmeticos', methods=['GET'])
def listar_cosmeticos():
    productos = obtener_de_postgres()
    if productos is not None:
        return jsonify(productos), 200
    else:
        return jsonify(PRODUCTOS_LOCALES), 200

if __name__ == '__main__':
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)
