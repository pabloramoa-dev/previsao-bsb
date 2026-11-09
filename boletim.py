"""Gera o boletim regional do @previsaobsb para o dia local."""
import json
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

# Agrupamentos editoriais. Coordenadas aproximadas dos núcleos urbanos.
REGIOES = {
    "Centro": [("Plano Piloto", -15.79, -47.88), ("Guará", -15.83, -47.98)],
    "Norte": [("Sobradinho", -15.65, -47.79), ("Planaltina", -15.62, -47.65)],
    "Oeste": [("Ceilândia", -15.82, -48.11), ("Taguatinga", -15.83, -48.06), ("Brazlândia", -15.67, -48.20)],
    "Sul": [("Gama", -16.02, -48.06), ("Santa Maria", -16.00, -47.99)],
    "Leste": [("Paranoá", -15.78, -47.78), ("São Sebastião", -15.90, -47.78)],
}

def boletim(dia):
    linhas = [f"@previsaobsb | Previsão para {dia:%d/%m/%Y}"]
    for setor, locais in REGIOES.items():
        nome, lat, lon = locais[dia.toordinal() % len(locais)]
        campos = ["temperature_2m_min", "temperature_2m_max", "precipitation_sum", "relative_humidity_2m_min"]
        query = urlencode(dict(latitude=lat, longitude=lon, daily=",".join(campos),
                               timezone="America/Sao_Paulo", start_date=str(dia), end_date=str(dia)))
        with urlopen("https://api.open-meteo.com/v1/forecast?" + query, timeout=30) as resposta:
            dados = json.load(resposta)["daily"]
        if dados["time"] != [str(dia)]:
            raise ValueError(f"Data inválida para {nome}")
        minima, maxima, chuva, umidade = [dados[campo][0] for campo in campos]
        linhas.append(f"{setor} · {nome}: {minima:.0f} a {maxima:.0f} °C, chuva prevista {chuva:g} mm, umidade mínima {umidade:.0f}%.")
    return "\n".join(linhas + ["Fonte: Open-Meteo."])

if __name__ == "__main__":
    print(boletim(datetime.now(ZoneInfo("America/Sao_Paulo")).date()))
