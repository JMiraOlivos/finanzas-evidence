# Finanzas Evidence

Monorepo para reportería financiera E&V:

- `etl/`: scripts Python para cargar libros diarios y mapping PNL a Neon Postgres.
- `evidence/`: proyecto Evidence conectado a Neon para visualizar PNL estructurado.

## Orden de ejecución

```powershell
cd etl
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env

python load_libro_diario.py "C:\ruta\diarioext.xls" --empresa "E&V Calera de Tango"
python load_pnl_mapping_from_config.py .\config\pnl_mapping_rules.json --replace

cd ..\evidence
npm install
npm run sources
npm run dev
```

## Evidence Team

Configurar:

- Repository: `JMiraOlivos/finanzas-evidence`
- Branch: `main`
- Project root: `evidence`
- Data source name: `postgres_finanzas`
- Type: PostgreSQL
- SSL: true

Las credenciales de Neon van en Evidence Team o en `.env` local, nunca en GitHub.
