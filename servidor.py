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
def guardar_en_postgres(codigo, nombre, inci, fecha_cad):
    try:
        # 1. Tu conexión habitual (usando tu variable de entorno DATABASE_URL)
        # conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        cursor = conn.cursor()
        
        # 2. SEGURO DE VIDA: Si la tabla no existe o está mal, esto la crea perfecta
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cosmeticos (
                id SERIAL PRIMARY KEY,
                codigo VARCHAR(100),
                nombre VARCHAR(255),
                inci TEXT,
                fecha_caducidad VARCHAR(100)
            );
        """)
        
        # 3. Guardamos los datos asociando 'fecha_cad' a la columna 'fecha_caducidad'
        cursor.execute(
            "INSERT INTO cosmeticos (codigo, nombre, inci, fecha_caducidad) VALUES (%s, %s, %s, %s);",
            (codigo, nombre, inci, fecha_cad)
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error real en la base de datos: {e}") # Esto saldrá en los Logs de Render si falla
        return False
