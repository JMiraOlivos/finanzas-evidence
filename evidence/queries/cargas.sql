select
    id,
    empresa,
    archivo_nombre,
    filas,
    fecha_min,
    fecha_max,
    debe_ml,
    haber_ml,
    saldo_ml,
    created_at
from postgres_finanzas_cargas_libro_diario
order by id desc
