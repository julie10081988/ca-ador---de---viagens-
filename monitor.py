
#!/usr/bin/env python3
"""Caçador de Viagens: passagens internacionais e alertas Telegram."""

import datetime as dt
import json
import os
import pathlib
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent

DESTINOS = [
    ("CUR", "Curaçao"),
    ("BKK", "Bangkok, Tailândia"),
    ("HKT", "Phuket, Tailândia"),
    ("LIS", "Lisboa"),
    ("MIA", "Miami"),
    ("MAD", "Madri"),
    ("CDG", "Paris"),
    ("FCO", "Roma"),
    ("EZE", "Buenos Aires"),
    ("SCL", "Santiago"),
]

LIMITE = 4000


def consultar(url, dados=None):
    corpo = urllib.parse.urlencode(dados).encode() if dados is not None else None
    requisicao = urllib.request.Request(
        url,
        data=corpo,
        headers={"User-Agent": "CacadorViagens/1.0"},
    )
    with urllib.request.urlopen(requisicao, timeout=45) as resposta:
        return json.load(resposta)


def enviar_telegram(token, chat, mensagem):
    resultado = consultar(
        "https://api.telegram.org/bot" + token + "/sendMessage",
        {"chat_id": chat, "text": mensagem},
    )
    if not resultado.get("ok"):
        raise RuntimeError("Telegram não confirmou o envio")
    return resultado


def adicionar_meses(data, quantidade):
    import calendar

    mes_total = data.month - 1 + quantidade
    ano = data.year + mes_total // 12
    mes = mes_total % 12 + 1
    dia = min(data.day, calendar.monthrange(ano, mes)[1])
    return dt.date(ano, mes, dia)


def executar():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat = os.environ["TELEGRAM_CHAT_ID"]

    if os.getenv("TESTE_TELEGRAM") == "1":
        enviar_telegram(
            token,
            chat,
            "✈️ Teste do Caçador de Viagens! Telegram conectado com sucesso.",
        )
        print("Teste Telegram: True")
        return

    chave = os.environ["SERPAPI_KEY"]
    agora = dt.datetime.now(dt.timezone.utc)

    # Alterna destino e datas a cada janela de quatro horas.
    rodada = int(agora.timestamp() // (4 * 3600))
    codigo, destino = DESTINOS[rodada % len(DESTINOS)]

    hoje = agora.date()
    meses = 1 + ((rodada // len(DESTINOS)) % 5)
    partida = adicionar_meses(hoje, meses)
    partida += dt.timedelta(days=(rodada // 5) % 14)

    retorno = partida + dt.timedelta(days=10)

    limite_data = adicionar_meses(hoje, 6)
    if retorno > limite_data:
        retorno = limite_data
        partida = retorno - dt.timedelta(days=10)

    parametros = {
        "engine": "google_flights",
        "departure_id": "REC",
        "arrival_id": codigo,
        "outbound_date": partida.isoformat(),
        "return_date": retorno.isoformat(),
        "type": "1",
        "currency": "BRL",
        "hl": "pt",
        "gl": "br",
        "adults": "1",
        "api_key": chave,
    }

    url = "https://serpapi.com/search.json?" + urllib.parse.urlencode(parametros)
    resultado = consultar(url)

    if resultado.get("error"):
        raise RuntimeError("Erro SerpApi: " + str(resultado["error"]))

    voos = resultado.get("best_flights", []) + resultado.get("other_flights", [])
    ofertas_atuais = []

    for voo in voos:
        preco = voo.get("price")

        if not isinstance(preco, (int, float)):
            continue
        if not 0 < preco <= LIMITE:
            continue

        companhias = sorted({
            trecho.get("airline", "")
            for trecho in voo.get("flights", [])
            if trecho.get("airline")
        })

        ofertas_atuais.append({
            "origin": "REC",
            "destination": destino,
            "destination_code": codigo,
            "departure": partida.isoformat(),
            "return": retorno.isoformat(),
            "international": True,
            "type": "cash",
            "price_brl": preco,
            "currency": "BRL",
            "airline": ", ".join(companhias),
            "url": "https://www.google.com/travel/flights",
            "checked_at": agora.isoformat(),
        })

    arquivo = ROOT / "offers.json"
    arquivo.write_text(
        json.dumps({
            "checked_at": agora.isoformat(),
            "source_connected": True,
            "offers": ofertas_atuais,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    historico = ROOT / "seen.json"
    vistos = set()

    if historico.exists():
        vistos = set(json.loads(historico.read_text(encoding="utf-8")))

    enviados = 0

    for oferta in ofertas_atuais:
        identificador = "|".join(str(oferta[campo]) for campo in (
            "destination_code", "departure", "return", "price_brl"
        ))

        if identificador in vistos:
            continue

        mensagem = (
            f"✈️ Caçador de Viagens — oferta encontrada!\n"
            f"Recife ↔ {destino}\n"
            f"Ida: {partida:%d/%m/%Y}\n"
            f"Volta: {retorno:%d/%m/%Y}\n"
            f"R$ {oferta['price_brl']:,.0f} por pessoa, ida e volta.\n"
            f"Preço sujeito a alteração. Confira antes de comprar.\n"
            f"https://www.google.com/travel/flights"
        )

        enviar_telegram(token, chat, mensagem)
        vistos.add(identificador)
        enviados += 1

    historico.write_text(
        json.dumps(sorted(vistos), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Consulta concluída: REC-{codigo}, "
        f"{partida} a {retorno}, "
        f"{len(voos)} itinerários, "
        f"{len(ofertas_atuais)} ofertas elegíveis, "
        f"{enviados} alertas."
    )


if __name__ == "__main__":
    executar()
