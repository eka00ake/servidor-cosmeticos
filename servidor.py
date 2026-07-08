# ==========================================
# MODELO EXACTO DE INVENTARIO (DBEAVER)
# ==========================================
class InventarioUsuario(db.Model):
    __tablename__ = 'inventario_usuarios'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, default=1) # Vinculado al usuario
    producto_id = db.Column(db.Integer, default=1) # ID del producto base
    fecha_caducidad_fabricante = db.Column(db.String(100)) # Date o String según formato
    pao = db.Column(db.Integer) # int4 en tu DBeaver
    fecha_apertura = db.Column(db.String(100))
    numero_unidades = db.Column(db.Integer) # int4 en tu DBeaver
    es_acabado = db.Column(db.Boolean, default=False)
    fecha_acabado = db.Column(db.String(100))
    conclusiones = db.Column(db.Text) # text en tu DBeaver

@app.route('/guardar', methods=['POST'])
def guardar_producto():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No se recibieron datos JSON"}), 400

    # Limpiamos el valor de PAO quitándole letras (ej: "12M" -> 12) para que Postgres no falle
    pao_limpio = data.get('pao', '12').replace('M', '').replace('m', '').strip()
    pao_int = int(pao_limpio) if pao_limpio.isdigit() else 12

    nuevo_item = InventarioUsuario(
        usuario_id=1, # Temporalmente asignado al primer usuario
        producto_id=int(data.get('codigo_producto_id', 1)), 
        fecha_caducidad_fabricante=data.get('fecha_caducidad'),
        pao=pao_int,
        fecha_apertura=data.get('fecha_apertura', '2026-07-08'),
        numero_unidades=int(data.get('unidades', 1)),
        es_acabado=False,
        conclusiones=data.get('conclusiones')
    )

    try:
        db.session.add(nuevo_item)
        db.session.commit()
        return jsonify({"status": "ok", "message": "Guardado en inventario_usuarios"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error al guardar producto: {e}")
        return jsonify({"error": str(e)}), 500
