"""Estúdio BSB: Open-Meteo -> roteiro -> Kokoro -> HyperFrames original RJ -> MP4."""
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
from urllib.request import urlopen
from zoneinfo import ZoneInfo

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
HF=ROOT/"hyperframes"
sys.path.insert(0,str(HF))
sys.path.insert(0,str(ROOT))
from compor import compor
from estudio.amplitude import gerar_cues
from boletim import REGIOES

VOZES={"bira":("pm_alex:0.82+pm_santa:0.18",1.04,0.22),
       "bia":("pf_dora:0.85+af_heart:0.15",1.02,0.24)}
DIAS=("SEGUNDA","TERÇA","QUARTA","QUINTA","SEXTA","SÁBADO","DOMINGO")
MESES=("","JANEIRO","FEVEREIRO","MARÇO","ABRIL","MAIO","JUNHO","JULHO","AGOSTO","SETEMBRO","OUTUBRO","NOVEMBRO","DEZEMBRO")

def run(*args):
    subprocess.run(list(map(str,args)), check=True, cwd=ROOT)

def coletar(dia):
    resultado=[]
    for indice,(regiao,locais) in enumerate(REGIOES.items()):
        nome,lat,lon=locais[(dia.toordinal()+indice)%len(locais)]
        campos=["temperature_2m_min","temperature_2m_max","precipitation_sum",
                "precipitation_probability_max","wind_gusts_10m_max"]
        url="https://api.open-meteo.com/v1/forecast?"+urlencode({
            "latitude":lat,"longitude":lon,"daily":",".join(campos),
            "timezone":"America/Sao_Paulo","start_date":str(dia),"end_date":str(dia)})
        with urlopen(url,timeout=35) as resp:
            data=json.load(resp)["daily"]
        if data["time"] != [str(dia)]:
            raise ValueError("Data meteorológica divergente para "+nome)
        vals=[data[key][0] for key in campos]
        if any(v is None or not isinstance(v,(int,float)) for v in vals):
            raise ValueError("Dado meteorológico faltando para "+nome)
        a,b,chuva,prob,vento=vals
        if a > b or not -10<=a<=50 or not -10<=b<=50:
            raise ValueError("Temperatura inconsistente para "+nome)
        resultado.append({"nome":nome,"regiao":regiao,"min":round(a),
            "max":round(b),"chuva_mm":round(chuva,1),
            "prob_chuva":round(prob),"vento_kmh":round(vento)})
    return resultado

def batidas(cidades,amanha):
    quando="amanhã" if amanha else "hoje"
    mais_quente=max(cidades,key=lambda x:x["max"])
    maior_chuva=max(cidades,key=lambda x:x["chuva_mm"])
    primeira={"fala":f"{mais_quente['nome']} pode chegar a {mais_quente['max']} graus {quando}. E como fica o restante do Distrito Federal?",
      "tipo":"gancho","dados":{"numero":f"{mais_quente['max']}°","sub":mais_quente["nome"].upper(),"titulo":"TEMPERATURA"}}
    resumo="; ".join(f"{c['nome']}, {c['min']} a {c['max']} graus" for c in cidades)
    quadro={"fala":f"Confira as cinco regiões. {resumo}.",
       "tipo":"resumo","dados":{"titulo":"TEMPERATURAS NO DF","cidades":cidades}}
    arr=[primeira,quadro]
    if maior_chuva["chuva_mm"] >= 2:
        arr.append({"fala":f"Maior volume previsto entre as localidades destacadas: {maior_chuva['nome']}, até {maior_chuva['chuva_mm']:g} milímetros de chuva.",
          "tipo":"alerta","dados":{"titulo":"ATENÇÃO À CHUVA","detalhe":f"{maior_chuva['nome']} • até {maior_chuva['chuva_mm']:g} mm"}})
    arr.append({"fala":f"Manda pra quem vai sair no Distrito Federal {quando}.",
                "tipo":"cta","dados":{"chamada":"MANDA PRA QUEM VAI SAIR","sub":"@previsaobsb"}})
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
    hoje=datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    dia=hoje+timedelta(days=args.day_offset)
    cidades=coletar(dia)
    beats=batidas(cidades,args.day_offset==1)
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
    audio_cama(dur,sr,assets/"trilha.wav")
    audio_cama(dur,sr,assets/"whoosh.wav")
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
    ceu="chuva" if clima["prob_chuva"]>=60 else ("nublado" if clima["prob_chuva"]>=40 else "sol")
    pacote={"dur":dur,"personagem":args.personagem,"formato":"amanha_no_rio" if args.day_offset else "rio_antes_de_sair",
        "data":str(hoje),"data_ext":data_ext,"data_previsao":str(dia),"hora":"18:00" if args.day_offset else "06:00",
        "ceu":ceu,"cidades":cidades,"batidas":beats,"cenas":cenas,"cortes":cuts,
        "transicoes":["whip-pan"]*len(cuts),"palavras":all_words,
        "boca":[[q["start"],q["value"]] for q in cues],"direcao":[],
        "dicas_praticas":["Previsão por região administrativa","Fonte: Open-Meteo"]}
    (work/"pacote.json").write_text(json.dumps(pacote,ensure_ascii=False,indent=2),encoding="utf-8")
    (HF/"index.html").write_text(compor(pacote),encoding="utf-8")
    (output.parent/"LEGENDA.txt").write_text(
        f"Previsão {'de amanhã' if args.day_offset else 'de hoje'} no DF • {dia:%d/%m/%Y}\n"+
        "\n".join(f"{c['nome']}: {c['min']}° a {c['max']}°" for c in cidades)+
        "\nManda pra quem mora no DF! #PrevisaoBSB #Brasilia #DF",encoding="utf-8")
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
