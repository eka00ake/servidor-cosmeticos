import os
import psycopg2
from flask import Flask, request, jsonify

app = Flask(__name__)

# Lista en memoria por si la base de datos de Render falla o no está configurada
PRODUCTOS_LOCALES = []

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

# 🚀 NUEVA FUNCIÓN: Lee los datos directamente desde la base de datos de Render
def obtener_de_postgres():
    url_base_datos = os.environ.get('DATABASE_URL')
    if not url_base_datos:
        return None

    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(url_base_datos)
        cursor = conn.cursor()
        
        # Leemos las columnas que necesita Android
        cursor.execute("SELECT codigo, nombre, inci, fecha_caducidad FROM cosmeticos;")
        filas = cursor.fetchall()
        
        # Transformamos los resultados a una lista de diccionarios (JSON)
        lista_productos = []
        for fila in filas:
            lista_productos.append({
                "codigo": fila[0],
                "nombre": fila[1],
                "inci": fila[2],
                "fecha_caducidad": fila[3]  # Clave compatible con el mapeo seguro de Android
            })
        return lista_productos
    except Exception as e:
        print(f"Error de conexión con PostgreSQL al leer: {e}")
        return None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


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
        # PLAN B: Si Postgres falla, lo guardamos en la memoria local
        nuevo_producto = {
            "codigo": codigo,
            "nombre": nombre,
            "inci": inci,
            "fecha_caducidad": fecha_cad
        }
        PRODUCTOS_LOCALES.append(nuevo_producto)
        print(f"Producto respaldado en memoria: {nombre}")
        return jsonify({"status": "ok", "mensaje": "Guardado temporal en memoria del servidor"}), 200

# 🚀 NUEVA RUTA: Responde a la petición GET /cosmeticos de la app móvil
@app.route('/cosmeticos', methods=['GET'])
def listar_cosmeticos():
    productos = obtener_de_postgres()
    
    if productos is not None:
        return jsonify(productos), 200
    else:
        # Si la base de datos falla, devuelve el respaldo temporal
        return jsonify(PRODUCTOS_LOCALES), 200

if __name__ == '__main__':
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)
