import os
import psycopg2

def guardar_en_postgres(codigo, nombre, inci, fecha_cad):
    try:
        # 🌟 Obtiene la URL de conexión secreta que te da Render automáticamente
        url_base_datos = os.environ.get('DATABASE_URL')
        
        # Conectamos usando esa URL completa
        conn = psycopg2.connect(url_base_datos)
        cursor = conn.cursor()
        
        # Creamos la tabla si no existe
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cosmeticos (
                id SERIAL PRIMARY KEY,
                codigo VARCHAR(100),
                nombre VARCHAR(255),
                inci TEXT,
                fecha_caducidad VARCHAR(100)
            );
        """)
        
        # Insertamos los datos
        cursor.execute(
            "INSERT INTO cosmeticos (codigo, nombre, inci, fecha_caducidad) VALUES (%s, %s, %s, %s);",
            (codigo, nombre, inci, fecha_cad)
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error en la base de datos online: {e}")
        return False
