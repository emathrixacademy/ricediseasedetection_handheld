# Railway build of the project page, from the REPOSITORY ROOT (see /railway.json).
# Only deploy/site is let into the build context (/.dockerignore): the image
# carries no source code, firmware or internal documents.
FROM python:3.12-slim
WORKDIR /site
COPY deploy/site /site
ENV PYTHONUNBUFFERED=1
CMD ["python", "/site/app.py"]
