# Edson Eletricista — app leve (serve o site + coletor de eventos + painel)
FROM python:3.12-slim
WORKDIR /srv
COPY app.py dashboard.html ./
COPY public/ ./public/
EXPOSE 80
ENV DB_PATH=/data/analytics.db PORT=80
CMD ["python", "-u", "app.py"]
