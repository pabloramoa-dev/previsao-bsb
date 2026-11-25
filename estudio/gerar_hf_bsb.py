"""Estúdio BSB: MET Norway -> roteiro -> Kokoro -> HyperFrames original RJ -> MP4."""
import argparse
import json
import os
import re
import subprocess
import sys
import wave
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
HF=ROOT/"hyperframes"
sys.path.insert(0,str(HF))
sys.path.insert(0,str(ROOT))
from compor import APRESENTADOR, compor
from estudio.amplitude import gerar_cues
from boletim import indice_destaque, selecionar_localidades

MET_URL="https://api.met.no/weatherapi/locationforecast/2.0/complete"
MET_UA="PrevisaoBSB/1.0 (https://www.instagram.com/previsaobsb/)"
FUSO=ZoneInfo("America/Sao_Paulo")

VOZES={"bira":("pm_alex:0.82+pm_santa:0.18",1.04,0.22),
       "bia":("pf_dora:0.85+af_heart:0.15",1.02,0.24)}
DIAS=("SEGUNDA","TERÇA","QUARTA","QUINTA","SEXTA","SÁBADO","DOMINGO")
MESES=("","JANEIRO","FEVEREIRO","MARÇO","ABRIL","MAIO","JUNHO","JULHO","AGOSTO","SETEMBRO","OUTUBRO","NOVEMBRO","DEZEMBRO")

def run(*args):
    subprocess.run(list(map(str,args)), check=True, cwd=ROOT)

def coletar(dia, data_publicacao, turno):
    """MET Norway locationforecast/complete (gratuita, CC BY 4.0, uso comercial
    permitido com crédito). Agrega as horas locais do dia pedido. A MET não
    fornece probabilidade de chuva nem rajadas para o Brasil: usamos umidade
    máxima e vento máximo (sustentado), sem inventar nenhum número."""
    resultado=[]
    for regiao,(nome,lat,lon) in selecionar_localidades(data_publicacao, turno):
        url=MET_URL+"?"+urlencode({"lat":round(lat,4),"lon":round(lon,4)})
        with urlopen(Request(url,headers={"User-Agent":MET_UA}),timeout=45) as resp:
            serie=json.load(resp)["properties"]["timeseries"]
        horas=[]
        for ponto in serie:
            quando=datetime.fromisoformat(ponto["time"].replace("Z","+00:00")).astimezone(FUSO)
            if quando.date()==dia and "next_1_hours" in ponto["data"]:
                horas.append(ponto["data"])
        if len(horas)<8:
            raise ValueError("Previsão horária incompleta para "+nome)
        det=[h["instant"]["details"] for h in horas]
        temps=[d.get("air_temperature") for d in det]
        if any(not isinstance(t,(int,float)) for t in temps):
            raise ValueError("Temperatura faltando para "+nome)
        a,b=min(temps),max(temps)
        if not -10<=a<=50 or not -10<=b<=50:
            raise ValueError("Temperatura inconsistente para "+nome)
        chuva=sum(h["next_1_hours"]["details"].get("precipitation_amount",0) for h in horas)
        umid=max(d.get("relative_humidity",0) for d in det)
        vento=max(d.get("wind_speed",0) for d in det)*3.6
        nuvens=sum(d.get("cloud_area_fraction",0) for d in det)/len(det)
        resultado.append({"nome":nome,"regiao":regiao,"min":round(a),
            "max":round(b),"chuva_mm":round(chuva,1),"umidade":round(umid),
            "vento_kmh":round(vento),"nuvens":round(nuvens),"horas":len(horas)})
    return resultado

def fmt_mm(v):
    # Decimal brasileiro: 31.7 -> "31,7"; 12.0 -> "12"
    s=f"{round(float(v),1):g}"
    return s.replace(".",",")


def gancho_rotativo(locs, data, quando, *, ancora=None, canal=""):
    """Gancho de retenção por edição, com fatos validados e sem alarmismo."""
    from datetime import date, timedelta
    from math import isfinite
    def num(x):
        return isinstance(x, (int, float)) and not isinstance(x, bool) and isfinite(x)
    def valor(c, *keys):
        return next((c[k] for k in keys if num(c.get(k))), None)
    def nome(c):
        return c.get("name") or c.get("nome") or c.get("point")
    validos = [c for c in locs if nome(c) and valor(c, "max_c", "max") is not None]
    if not validos:
        return "Confira a previsão " + quando + "."
    try:
        dia = date.fromisoformat(str(data)[:10])
    except (ValueError, TypeError):
        dia = date.today()
    noite = quando == "amanhã"
    pub = dia - timedelta(days=int(noite))
    fase = sum(ord(ch) for ch in canal) % 12
    slot = pub.toordinal() * 2 + int(noite) + fase
    c = ancora if ancora in validos else validos[(slot // 2 + int(noite)) % len(validos)]
    n = nome(c)
    mx = round(valor(c, "max_c", "max"))
    mn0 = valor(c, "min_c", "min")
    mn = round(mn0) if mn0 is not None else None
    outros = [x for x in validos if nome(x) != n]
    outro = max(outros, key=lambda x: abs(valor(x, "max_c", "max") - mx), default=None)
    dif = round(valor(outro, "max_c", "max")) if outro else mx
    fato = f"{n}: {mx} graus {quando}."
    faixa = f"{n}: de {mn} a {mx} graus {quando}." if mn is not None else fato
    # 12 famílias: identificação, curiosidade, antecipação, contraste,
    # proteção, urgência, surpresa, pergunta, comparação, benefício,
    # informação específica e expectativa. Condições especiais têm gate.
    familias = {
        0: (f"Mora em {n}? {mx} graus {quando}.", f"Alô, {n}! Máxima de {mx} graus {quando}.", fato, f"{n}, sua máxima: {mx} graus {quando}."),
        1: (f"Quanto vai fazer em {n}? {mx} graus {quando}.", f"{n}: sabe qual a máxima {quando}? {mx} graus.", f"{fato} E na sua cidade?", f"{n}: como fica {quando}? {mx} graus."),
        2: (f"Planeje {quando}: {faixa}", f"Já se programe: {faixa}", f"Para {quando}, {faixa}", f"Antecipe seus planos: {fato}"),
        4: (f"Antes de sair, {fato}", f"Vai sair em {n}? {mx} graus {quando}.", f"Prepare-se: {faixa}", f"De olho na temperatura: {fato}"),
        7: (f"Vai fazer calor em {n}? {mx} graus {quando}.", f"Casaco ou roupa leve? {faixa}", f"Vai sair {quando}? {faixa}", f"Como se vestir em {n}? {faixa}"),
        8: (f"Compare as temperaturas: {fato}", f"Veja os números: {fato}", f"De cidade em cidade: {fato}", f"Compare com a sua rotina: {faixa}"),
        9: (f"Organize seu dia: {faixa}", f"Para planejar a rotina: {fato}", f"Seu dia em {n}: {mx} graus {quando}.", f"Programe sua saída: {fato}"),
        10: (fato, f"Máxima de {mx} graus em {n} {quando}.", faixa, f"{quando.capitalize()}, {n} pode chegar a {mx} graus."),
        11: (f"{fato} E as demais cidades?", f"{fato} Veja as outras temperaturas.", f"Começando por {n}: {mx} graus {quando}.", f"Primeiro, {fato}"),
    }
    if mn is not None and mx - mn >= 7:
        familias[3] = (f"De {mn} a {mx} graus em {n} {quando}.", f"{n}: mínima de {mn}, máxima de {mx} {quando}.", faixa, f"Do mínimo de {mn} ao máximo de {mx} graus em {n} {quando}.")
    if outro and abs(dif - mx) >= 4:
        familias[6] = (f"{n}: {mx} graus. {nome(outro)}: {dif} {quando}.", f"Olha a diferença {quando}: {n}, {mx}; {nome(outro)}, {dif} graus.", f"Temperaturas bem diferentes: {n}, {mx}; {nome(outro)}, {dif} graus {quando}.", f"{n} e {nome(outro)}: {mx} e {dif} graus {quando}.")
        familias[8] = familias[6][::-1]
    rajada = valor(c, "wind_gust_max_kmh", "gust_kmh", "wind_gust_kmh", "rajada_kmh")
    if rajada is not None and rajada >= 60:
        familias[5] = (f"Atenção em {n}: rajadas fortes {quando}.", f"Vento forte previsto em {n} {quando}.", f"{n}: cuidado com as rajadas {quando}.", f"De olho no vento forte em {n} {quando}.")
    elif mx >= 38:
        familias[5] = (f"Atenção em {n}: máxima de {mx} graus {quando}.", f"{n}: calor intenso, {mx} graus {quando}.", f"Cuidado com o calor em {n}: {mx} graus {quando}.", f"{mx} graus previstos em {n} {quando}: cuide-se.")
    # Se um fenômeno não existe, mantém a alternância sem fabricar o fato.
    k = slot % 12
    fallback = {3: 9, 5: 11, 6: 0}
    k = k if k in familias else fallback.get(k, 10)
    frase = familias[k][(slot // 12) % 4]
    # Mantém a abertura curta mesmo com nomes compostos.
    if len(frase.split()) > 12:
        frase = fato
    return frase


def engajamento_rotativo(data, quando, local="", canal=""):
    """Um pedido útil por edição, com rodízio independente do gancho."""
    from datetime import date, timedelta
    try:
        dia = date.fromisoformat(str(data)[:10])
    except (ValueError, TypeError):
        dia = date.today()
    noite = quando == "amanhã"
    pub = dia - timedelta(days=int(noite))
    slot = pub.toordinal() * 2 + int(noite) + sum(ord(ch) for ch in canal)
    familias = (
        ("Envie a previsão a quem vai sair.", "Compartilhe com quem mora na região.", "Manda pra quem precisa dessa previsão.", "Envie para quem vai viajar."),
        ("Qual sua cidade? Comente aqui.", "Como está o tempo aí? Comente.", "De qual bairro você nos acompanha?", "Qual cidade quer ver por aqui?"),
        ("Salve para consultar antes de sair.", "Guarde esta previsão para seu dia.", "Salve o boletim para planejar.", "Salve para conferir mais tarde."),
        ("Siga para acompanhar a previsão diária.", "Siga e acompanhe o tempo na região.", "Acompanhe o perfil para novos boletins.", "Siga para conferir a próxima previsão."),
    )
    if local and slot % len(familias) == 0:
        return (f"Envie a previsão para alguém de {local}.",
                f"Manda pra quem mora em {local} conferir a previsão.",
                f"Compartilhe com quem vai sair em {local}.",
                f"Envie para quem conhece alguém de {local}.")[(slot // len(familias)) % 4]
    return familias[slot % len(familias)][(slot // len(familias)) % 4]


def batidas(cidades,amanha,destaque_indice=0,data_previsao=None):
    quando="amanhã" if amanha else "hoje"
    destaque=cidades[destaque_indice]
    maior_chuva=max(cidades,key=lambda x:x["chuva_mm"])
    primeira={"fala":gancho_rotativo(cidades, data_previsao, quando, ancora=destaque, canal="bsb"),
      "tipo":"gancho","dados":{"numero":f"{destaque['max']}°","sub":destaque["nome"].upper(),"titulo":"TEMPERATURA"}}
    resumo="; ".join(f"{c['nome']}, {c['min']} a {c['max']} graus" for c in cidades)
    quadro={"fala":f"Confira as cinco regiões. {resumo}.",
       "tipo":"resumo","dados":{"titulo":"TEMPERATURAS NO DF","cidades":cidades}}
    arr=[primeira,quadro]
    if maior_chuva["chuva_mm"] >= 2:
        arr.append({"fala":f"Maior volume previsto entre as localidades destacadas: {maior_chuva['nome']}, até {fmt_mm(maior_chuva['chuva_mm'])} milímetros de chuva.",
          "tipo":"alerta","dados":{"titulo":"ATENÇÃO À CHUVA","detalhe":f"{maior_chuva['nome']} • até {fmt_mm(maior_chuva['chuva_mm'])} mm"}})
    arr.append({"fala":engajamento_rotativo(data_previsao, quando, destaque["nome"], "bsb"),
                "tipo":"cta","dados":{"chamada":"ACOMPANHE A PREVISÃO","sub":"@previsaobsb"}})
    return arr

def palavras(text,ini,fim):
    tokens=text.split()
    pesos=[max(1,len(re.findall("[aeiouáéíóúãõâêô]",w.lower()))) for w in tokens]
    total=sum(pesos) or 1
    t=ini
    out=[]
    for w,peso in zip(tokens,pesos):
        end=min(fim,t+(fim-ini)*peso/total)
        out.append({"w":w,"s":round(t,3),"e":round(end,3)})
        t=end
    return out

def audio_cama(dur,sr,path):
    n=int(dur*sr)
    x=np.zeros(n,dtype=np.float32)
    for freq in (146.83,220,329.63):
        t=np.arange(n,dtype=np.float32)/sr
        x+=0.016*np.sin(2*np.pi*freq*t)
    x[:min(12000,n)]*=np.linspace(0,1,min(12000,n))
    x[-min(14000,n):]*=np.linspace(1,0,min(14000,n))
    with wave.open(str(path),"wb") as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(sr)
        stereo=np.stack((x,x),axis=1)
        w.writeframes((stereo*32767).astype(np.int16).tobytes())

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--personagem",choices=VOZES,default="bira")
    ap.add_argument("--day-offset",choices=[0,1],type=int,default=0)
    ap.add_argument("--out",default="output/REEL_BSB.mp4")
    ap.add_argument("--so-html",action="store_true")
    args=ap.parse_args()
    if APRESENTADOR.get("bia", {}).get("nome") != "BIA":
        raise RuntimeError("O nome visual da apresentadora deve ser somente BIA")
    hoje=datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    dia=hoje+timedelta(days=args.day_offset)
    turno='manha' if args.personagem=='bira' else 'noite'
    cidades=coletar(dia,hoje,turno)
    abertura=indice_destaque(hoje,turno,len(cidades))
    beats=batidas(cidades,args.day_offset==1,abertura,dia.isoformat())
    output=Path(args.out).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    assets=HF/"assets"/"audio"
    assets.mkdir(parents=True,exist_ok=True)
    work=output.parent/"work_bsb"
    work.mkdir(parents=True,exist_ok=True)
    roteiro=work/"roteiro.txt"
    roteiro.write_text("\n".join(x["fala"] for x in beats),encoding="utf-8")
    voz,speed,gap=VOZES[args.personagem]
    raw=work/"raw.wav"
    seg_file=work/"segs.json"
    run(sys.executable,ROOT/"estudio"/"kokoro.py",roteiro,
       "--voz",voz,"--speed",str(speed),"--gap",str(gap),
       "--out",raw,"--seg-json",seg_file)
    segs=json.loads(seg_file.read_text(encoding="utf-8"))
    audio=assets/"narracao.wav"
    run("ffmpeg","-y","-v","error","-i",raw,"-af",
        "highpass=f=80,acompressor=threshold=-18dB:ratio=2:attack=8:release=180,volume=1.1",
        "-ar","44100","-ac","1",audio)
    with wave.open(str(audio),"rb") as w:
        sr=w.getframerate()
        samples=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float32)/32768
    dur=round(segs[-1]["fim"]+0.8,2)
    npad=max(0,int(dur*sr)-len(samples))
    samples=np.pad(samples,(0,npad))
    cues=gerar_cues(samples,sr,fps=30)
    cenas=[]
    tipos={"gancho":"numero","resumo":"quadro","alerta":"alerta","cta":"cta"}
    cuts=[]
    all_words=[]
    for i,(beat,seg) in enumerate(zip(beats,segs)):
        beat["legenda"]=beat["fala"]
        beat["ini"]=seg["ini"]
        beat["fim"]=seg["fim"]
        all_words.extend([dict(w,b=i) for w in palavras(beat["fala"],seg["ini"],seg["fim"])])
        cenas.append({"id":f"s{i}-{tipos[beat['tipo']]}","tipo":tipos[beat["tipo"]],
                      "ini":beat["ini"],"batidas":[i]})
        if i:cuts.append(max(.1,beat["ini"]-.18))
    data_ext=f"{DIAS[hoje.weekday()]}, {hoje.day} DE {MESES[hoje.month]}"
    clima=max(cidades,key=lambda x:x["chuva_mm"])
    ceu="chuva" if clima["chuva_mm"]>=2 else ("nublado" if sum(c["nuvens"] for c in cidades)/len(cidades)>=60 else "sol")
    pacote={"dur":dur,"personagem":args.personagem,"formato":"amanha_no_rio" if args.day_offset else "rio_antes_de_sair",
        "data":str(hoje),"data_ext":data_ext,"data_previsao":str(dia),"hora":"18:00" if args.day_offset else "06:00",
        "ceu":ceu,"cidades":cidades,"batidas":beats,"cenas":cenas,"cortes":cuts,
        "rodizio":{"data_publicacao":str(hoje),"turno":turno,
                  "localidade_abertura":cidades[abertura]["nome"],
                  "localidades":[c["nome"] for c in cidades]},
        "transicoes":["whip-pan"]*len(cuts),"palavras":all_words,
        "boca":[[q["start"],q["value"]] for q in cues],"direcao":[],
        "dicas_praticas":["Previsão por região administrativa","Fonte: MET Norway (CC BY 4.0)"]}
    (work/"pacote.json").write_text(json.dumps(pacote,ensure_ascii=False,indent=2),encoding="utf-8")
    (HF/"index.html").write_text(compor(pacote),encoding="utf-8")
    (output.parent/"LEGENDA.txt").write_text(
        f"Previsão {'de amanhã' if args.day_offset else 'de hoje'} no DF • {dia:%d/%m/%Y}\n"+
        "\n".join(f"{c['nome']}: {c['min']}° a {c['max']}°" for c in cidades)+
        "\nManda pra quem mora no DF!\nDados: MET Norway (CC BY 4.0)\n#PrevisaoBSB #Brasilia #DF",encoding="utf-8")
    if args.so_html:
        print("HTML HyperFrames produzido:",HF/"index.html")
        return
    cli=ROOT/"video"/"node_modules"/"hyperframes"/"bin"/"hyperframes.mjs"
    if not cli.is_file():raise FileNotFoundError("Execute npm ci --prefix video antes")
    env=dict(os.environ,HYPERFRAMES_NO_TELEMETRY="1",DO_NOT_TRACK="1")
    def node(*cmd):
        subprocess.run(["node",str(cli),*map(str,cmd)],check=True,cwd=HF,env=env)
    node("lint",HF)
    node("render",HF,"--output",output,"--quality","standard","--workers","2")
    run("ffprobe","-v","error","-show_entries","stream=codec_name,width,height",
        "-of","default=noprint_wrappers=1",output)
    if output.stat().st_size < 100000:raise RuntimeError("MP4 pequeno demais")
    run("ffmpeg","-y","-v","error","-ss","2","-i",output,
        "-frames:v","1",output.with_name("CAPA.jpg"))
    print("MP4 HyperFrames pronto:",output)

if __name__=="__main__":
    main()
