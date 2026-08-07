# The build context for this image is the parent `projects/` directory, not
# this folder. That is deliberate: the API applies the database project's
# schema.sql itself on first boot (RUN_DB_BOOTSTRAP=true, see main.py), so the
# image has to contain that sibling file, and Docker cannot COPY from outside
# its build context. Both docker-compose.yml and render.yaml set the context
# accordingly.
FROM python:3.12-slim

WORKDIR /app

COPY aircraft-maintenance-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aircraft-maintenance-api/main.py .

# main.py resolves the schema relative to itself, at
# <parent of /app>/aircraft-maintenance-db/schema.sql, so it lands at /.
COPY aircraft-maintenance-db/schema.sql /aircraft-maintenance-db/schema.sql

EXPOSE 8000

# Render and most other hosts inject the port to bind on as $PORT. Fall back to
# 8000 for local runs, where nothing sets it.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
