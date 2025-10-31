# Utilise directement Python 3.12
FROM python:3.12-slim

# Définit le dossier de travail
WORKDIR /app

# Copie tout ton code
COPY . .

# Installe les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Commande de lancement
CMD ["python", "Hoshikuzu.py"]
