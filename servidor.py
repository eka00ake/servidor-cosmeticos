from flask import Flask, request, jsonify
import psycopg2 # Cambiamos mysql por psycopg2
import os

app = Flask(__name__)

# Pega aquí la "External Connection String" que te dio la web de Render
URL_BASE_DATOS = "postgresql://usuario:contraseña@host/nombre_bd"

def guardar_en_postgres(codigo, nombre, inci, fecha_cad):
    try:
        # Nos conectamos directamente usando la URL de internet
        conexion = psycopg2.connect(URL_BASE_DATOS)
        cursor = conexion.cursor()
        
        # El comando es idéntico a MySQL, solo cambia %s por marcadores estándar si fuera necesario, pero en Postgres con psycopg2 se usa igual (%s)
        query = "INSERT INTO cosmeticos (Cod_Barras, Nombre, INCI, Fecha_cad) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (codigo, nombre, inci, fecha_cad))
        
        conexion.commit()
        return True
    except Exception as e:
        print(f"Error en la base de datos online: {e}")
        return False
    finally:
        if 'conexion' in locals():
            cursor.close()
            conexion.close()

@app.route('/guardar', methods=['POST'])
def guardar_cosmetico():
    datos = request.json
    codigo = datos.get('codigo')
    nombre = datos.get('nombre')
    inci = datos.get('inci')
    fecha_cad = datos.get('fechaCaducidad')
    
    exito = guardar_en_postgres(codigo, nombre, inci, fecha_cad)
    
    if exito:
        return jsonify({"status": "ok", "mensaje": "Guardado en la nube"}), 200
    else:
        return jsonify({"status": "error"}), 500

if __name__ == '__main__':
    # Render nos exige leer el puerto que ellos decidan dinámicamente
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)