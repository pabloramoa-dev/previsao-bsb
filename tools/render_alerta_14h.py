"""Plantão Brasília: utiliza o estúdio HyperFrames/Kokoro Bia existente."""
import json, sys
from pathlib import Path
from tools.alerta_14h import validar
from tools.alerta_14h_roteiro import batidas, texto_para_arquivo

def main():
    rel=validar(json.loads(Path("output/alertas/consulta.json").read_text()))
    import estudio.gerar_hf_bsb as hf
    nome=rel["eventos"][0]["local"]
    t=rel["temperaturas_reais"].get(nome)
    if not t:
        nome="Brasília"
        t=rel["temperaturas_reais"][nome]
    cidades=[{"nome":nome,"regiao":"Distrito Federal",
              "min":t["min"],"max":t["max"],"chuva_mm":0,
              "umidade":0,"vento_kmh":0,"nuvens":80,"horas":24}]
    beats=batidas(rel)
    # O gerador do DF aceita gancho/resumo/alerta/cta; adapta fala sem cartão
    # para aviso (sem atribuir milímetros ou vento inexistentes).
    for b in beats:
        if b["tipo"]=="frase":
            b["tipo"]="alerta"
            b["dados"]={"titulo":"ORIENTAÇÕES","detalhe":"DEFESA CIVIL 199"}
    hf.coletar=lambda *args: cidades
    hf.indice_destaque=lambda *args: 0
    hf.batidas=lambda *args: beats
    compositor=hf.compor
    hf.compor=lambda p: compositor(dict(p,hora="14:00",ceu="tempestade"))
    sys.argv=["estudio/gerar_hf_bsb.py","--personagem","bia",
              "--day-offset","0","--out","output/alertas/ALERTA.mp4"]
    hf.main()
    texto_para_arquivo(rel,"output/alertas/LEGENDA.txt")
    out=Path("output/alertas/ALERTA.mp4")
    if not out.exists() or out.stat().st_size<100000:
        raise RuntimeError("MP4 do DF incompleto")
    print("ALERTA DF:",out,out.stat().st_size)

if __name__=="__main__": main()
