"""Gera o boletim regional do @previsaobsb para o dia local."""
import json
from datetime import date, datetime
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

# As 35 RAs oficiais (GDF), distribuídas em cinco setores editoriais.
# Coordenadas aproximadas de núcleos urbanos: não representam toda a RA.
# https://www.gdfsaude.df.gov.br/web/guest
REGIOES = {
    "Centro": [
        ("Plano Piloto", -15.79, -47.88),
        ("Guará", -15.83, -47.98),
        ("Cruzeiro", -15.79, -47.94),
        ("Sudoeste/Octogonal", -15.8, -47.93),
        ("Candangolândia", -15.85, -47.95),
        ("Núcleo Bandeirante", -15.87, -47.97),
        ("SIA", -15.81, -47.96),
        ("Águas Claras", -15.84, -48.02),
        ("Arniqueira", -15.86, -48.01),
    ],
    "Norte": [
        ("Sobradinho", -15.65, -47.79),
        ("Sobradinho II", -15.64, -47.8),
        ("Planaltina", -15.62, -47.65),
        ("Arapoanga", -15.65, -47.66),
        ("Fercal", -15.6, -47.87),
        ("Lago Norte", -15.74, -47.87),
        ("Varjão", -15.72, -47.87),
    ],
    "Oeste": [
        ("Ceilândia", -15.82, -48.11),
        ("Taguatinga", -15.83, -48.06),
        ("Brazlândia", -15.67, -48.2),
        ("Samambaia", -15.88, -48.09),
        ("Sol Nascente/Pôr do Sol", -15.82, -48.14),
        ("SCIA/Estrutural", -15.78, -47.98),
        ("Vicente Pires", -15.83, -48.01),
    ],
    "Sul": [
        ("Gama", -16.02, -48.06),
        ("Santa Maria", -16, -47.99),
        ("Recanto das Emas", -15.92, -48.06),
        ("Riacho Fundo", -15.89, -48.01),
        ("Riacho Fundo II", -15.91, -48.04),
        ("Park Way", -15.91, -47.94),
        ("Água Quente", -16.01, -48.17),
    ],
    "Leste": [
        ("Paranoá", -15.78, -47.78),
        ("São Sebastião", -15.9, -47.78),
        ("Jardim Botânico", -15.88, -47.82),
        ("Itapoã", -15.76, -47.76),
        ("Lago Sul", -15.84, -47.86),
    ],
}

INICIO_RODIZIO = date(2026, 11, 11)
TURNOS = ("manha", "noite")


def indice_slot(data_publicacao, turno):
    """Dois Reels por dia, com seleção estável mesmo em reexecuções."""
    if turno not in TURNOS:
        raise ValueError("Turno inválido: " + repr(turno))
    return (data_publicacao - INICIO_RODIZIO).days * 2 + TURNOS.index(turno)


def selecionar_localidades(data_publicacao, turno):
    """Um lugar por setor, sem repetir entre turnos nem na manhã seguinte."""
    slot = indice_slot(data_publicacao, turno)
    return [
        (setor, locais[(slot + 2 * indice) % len(locais)])
        for indice, (setor, locais) in enumerate(REGIOES.items())
    ]


def indice_destaque(data_publicacao, turno, quantidade=5):
    """Altera também o primeiro lugar falado, atravessando os cinco setores."""
    if quantidade < 1:
        raise ValueError("Nenhuma localidade para destacar")
    return indice_slot(data_publicacao, turno) % quantidade

def boletim(dia, turno='manha', data_publicacao=None):
    linhas = [f"@previsaobsb | Previsão para {dia:%d/%m/%Y}"]
    for setor, (nome, lat, lon) in selecionar_localidades(data_publicacao or dia, turno):
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
