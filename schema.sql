CREATE TABLE IF NOT EXISTS cargas (
    id_carga INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_carga TEXT UNIQUE NOT NULL,
    fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archivo_origen TEXT,
    registros_totales INTEGER
);

CREATE TABLE IF NOT EXISTS transacciones (
    id_transaccion INTEGER PRIMARY KEY AUTOINCREMENT,
    id_carga INTEGER NOT NULL,
    codunicocli_13_enc TEXT NOT NULL,
    tipo_marca TEXT,
    delito TEXT,
    destipdocumento TEXT,
    destipbanca TEXT,
    segmento TEXT,
    act_economica TEXT,
    codunicocli_13 TEXT,
    ctacomercial TEXT,
    codproducto TEXT,
    moneda TEXT,
    fecapertura DATE,
    feccierre DATE,
    mtoapertura REAL,
    fecha DATE,
    hora TIME,
    fechaproc DATE,
    glosa TEXT,
    glosa_limpia TEXT,
    grupo TEXT,
    canal TEXT,
    codagencia TEXT,
    agencia TEXT,
    monto REAL,
    i_e TEXT,
    terminal TEXT,
    operador TEXT,
    numsecuencial TEXT,
    numreg TEXT,
    FOREIGN KEY (id_carga) REFERENCES cargas(id_carga) ON DELETE CASCADE
);

CREATE INDEX idx_cliente ON transacciones(codunicocli_13_enc);
CREATE INDEX idx_carga ON transacciones(id_carga);
CREATE INDEX idx_fecha ON transacciones(fecha);
CREATE INDEX idx_monto ON transacciones(monto);
CREATE INDEX idx_glosa ON transacciones(glosa_limpia);

CREATE TABLE IF NOT EXISTS casos (
    id_caso INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_caso TEXT UNIQUE NOT NULL,
    descripcion TEXT,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS caso_involucrados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_caso INTEGER NOT NULL,
    codunicocli_13_enc TEXT NOT NULL,
    fecha_agregado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_caso) REFERENCES casos(id_caso) ON DELETE CASCADE,
    UNIQUE(id_caso, codunicocli_13_enc)
);

CREATE TABLE IF NOT EXISTS reportes_generados (
    id_reporte INTEGER PRIMARY KEY AUTOINCREMENT,
    id_caso INTEGER NOT NULL,
    tipo_reporte TEXT NOT NULL,
    configuracion TEXT,
    fecha_generacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    incluir_en_pdf BOOLEAN DEFAULT 0,
    resultado_json TEXT,
    FOREIGN KEY (id_caso) REFERENCES casos(id_caso) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS configuracion_sistema (
    clave TEXT PRIMARY KEY,
    valor TEXT,
    descripcion TEXT
);
