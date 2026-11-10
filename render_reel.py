"""Gera Reel vertical com dados reais do coletor regional existente."""
import argparse
from datetime import datetime
from pathlib import Path
import subprocess
import tempfile
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont
from boletim import boletim

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H = 1080, 1920

def f(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)

def run(*cmd):
    subprocess.run([str(x) for x in cmd], check=True)

def slide(path, title, line, number, total, date_label):
    im = Image.new("RGB", (W, H), (10, 23, 48))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((45, 72, 1035, 182), radius=34, fill=(24, 69, 121))
    d.text((85, 103), "PREVISÃO BSB  •  DISTRITO FEDERAL", font=f(37, True), fill="white")
    d.text((76, 315), title.upper(), font=f(92, True), fill=(111, 214, 250))
    d.rounded_rectangle((52, 505, 1028, 1125), radius=50, fill=(27, 51, 88))
    # Wrap sem cortes: adequar o texto pelo comprimento em pixels.
    words = line.split()
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if d.textbbox((0,0), candidate, font=f(54, True))[2] > 850 and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    for index, segment in enumerate(lines[:8]):
        d.text((95, 570 + index*85), segment, font=f(54, True), fill="white")
    d.text((76, 1400), "Dados: Open-Meteo", font=f(39), fill=(180, 203, 222))
    d.text((76, 1495), date_label, font=f(42), fill="white")
    d.rounded_rectangle((76, 1690, 1004, 1707), radius=8, fill=(58, 91, 122))
    d.rounded_rectangle((76, 1690, 76 + int(928*number/total), 1707), radius=8, fill=(94, 214, 237))
    d.text((76, 1755), "Manda pra quem mora nessa região!", font=f(42, True), fill=(255, 217, 129))
    im.save(path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="output/previsaobsb.mp4")
    parser.add_argument("--caption", default="output/legenda.txt")
    args = parser.parse_args()
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    lines = boletim(today).splitlines()
    areas = [line for line in lines if " · " in line]
    if len(areas) != 5:
        raise RuntimeError("Esperadas cinco regiões, conferência necessária")
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    Path(args.caption).parent.mkdir(parents=True, exist_ok=True)
    captions = [f"Previsão do Distrito Federal • {today:%d/%m/%Y}"] + areas + [
        "Manda pra quem precisa saber a previsão de hoje! #PrevisaoBSB #Brasilia #DistritoFederal #Tempo"]
    Path(args.caption).write_text("\n".join(captions), encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        segments = []
        for i, row in enumerate(areas, start=1):
            region, sentence = row.split(" · ", 1)
            image = tmp / f"{i:02d}.png"
            audio = tmp / f"{i:02d}.wav"
            video = tmp / f"{i:02d}.mp4"
            spoken = sentence.replace("°C", " graus").replace("mm", " milímetros").replace("%", " por cento")
            slide(image, region, sentence, i, len(areas), today.strftime("%d/%m/%Y"))
            run("espeak-ng", "-v", "pt-br", "-s", "145", "-w", audio, spoken)
            run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-loop", "1", "-framerate", "25", "-i", image, "-i", audio,
                "-vf", "scale=1080:1920,format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-r", "25",
                "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
                "-shortest", "-t", "16", "-movflags", "+faststart", video)
            segments.append(video)
        listing = tmp / "concat.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in segments))
        run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", listing,
            "-c", "copy", "-movflags", "+faststart", target)
    run("ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1", target)
    print(f"Vídeo gerado: {target}")

if __name__ == "__main__":
    main()
