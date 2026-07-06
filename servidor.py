import os
import psycopg2
from flask import Flask, request, jsonify

app = Flask(__name__)

def guardar_en_postgres(codigo, nombre, inci, fecha_cad):
    conn = None
    cursor = None
    try:
        # 🌟 Lee la URL de la base de datos que te da Render de forma automática
        url_base_datos = os.environ.get('DATABASE_URL')
        
        # Conexión limpia usando la URL
        conn = psycopg2.connect(url_base_datos)
        cursor = conn.cursor()
        
        # Crear la tabla automáticamente si no existiera
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cosmeticos (
                id SERIAL PRIMARY KEY,
                codigo VARCHAR(100),
                nombre VARCHAR(255),
                inci TEXT,
                fecha_caducidad VARCHAR(100)
            );
        """)
        
        # Insertar el cosmético vinculando fecha_cad a la columna fecha_caducidad
        cursor.execute(
            "INSERT INTO cosmeticos (codigo, nombre, inci, fecha_caducidad) VALUES (%s, %s, %s, %s);",
            (codigo, nombre, inci, fecha_cad)
        )
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error interno en la base de datos: {e}")
        return False
        
    finally:
        # Cerramos conexiones de forma segura para no saturar la base de datos
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/guardar', methods=['POST'])
def guardar_cosmetico():
    datos = request.json
    if not datos:
        return jsonify({"status": "error", "mensaje": "No se recibieron datos JSON"}), 400
        
    codigo = datos.get('codigo')
    nombre = datos.get('nombre')
    inci = datos.get('inci')
    fecha_cad = datos.get('fechaCaducidad')
    
    # Llamamos a la función de guardado segura
    exito = guardar_en_postgres(codigo, nombre, inci, fecha_cad)
    
    if exito:
        return jsonify({"status": "ok", "mensaje": "Guardado en la nube"}), 200
    else:
        return jsonify({"status": "error", "mensaje": "Error interno en el servidor de base de datos"}), 500

# Asegura el arranque nativo si se ejecuta directamente
if __name__ == '__main__':
    # 🌟 OBLIGATORIO PARA RENDER: Lee el puerto dinámico del sistema. 
    # Si no existe (local), usa el 5000 por defecto.
    puerto = int(os.environ.get("PORT", 5000))
    
    # 🌟 OBLIGATORIO: host='0.0.0.0' le dice a Flask que escuche peticiones externas (como tu móvil)
    app.run(host='0.0.0.0', port=puerto)
