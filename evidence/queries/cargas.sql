select
    id,
    empresa_id,
    archivo_nombre,
    filas_leidas,
    filas_insertadas,
    fecha_min,
    fecha_max,
    total_debe_ml,
    total_haber_ml,
    (total_debe_ml - total_haber_ml) as saldo_ml,
    creado_en
from postgres_finanzas_cargas_libro_diario
order by id desc