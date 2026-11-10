# Previsão BSB — HyperFrames e Kokoro

**Pipeline atual de piloto (sem publicação):** [Piloto HyperFrames BSB — Bira e Bia](https://github.com/pabloramoa-dev/previsao-bsb/actions/workflows/piloto_hyperframes.yml).

- Bira às 6h: `pm_alex:0.82+pm_santa:0.18`; Bia às 18h: `pf_dora:0.85+af_heart:0.15`.
- Render pelo HyperFrames 0.8.96, GSAP 3.15.0 e TTS Kokoro, com sincronismo labial por amplitude; código-base original do RJ.
- Novo cenário ilustrado com Congresso Nacional, Esplanada e Catedral.
- Coleta real Open-Meteo de cinco regiões e rodízio de localidades, sem dados fabricados.
- Reel 1080 x 1920, áudio, cena animada, legendas e entrega em artifact MP4.
- No workflow, selecione `bira` para **hoje**, `bia` para **amanhã**. Nenhum piloto publica.
- **O workflow antigo `reels_instagram.yml` está integralmente desativado**; não ativar sem substituir por um publicador validado.

**Estado de validação:** arquivos e configuração adicionados ao GitHub, mas render do workflow, MP4 e QA não foram confirmados nesta sessão. Não confundir implementação do código com vídeo efetivamente renderizado ou publicado.

## Execução manual de piloto

GitHub Actions → **Piloto HyperFrames BSB — Bira e Bia** → Run workflow → Bira ou Bia. Conferir o artefato `PILOTO-HYPERFRAMES-BSB-<run_id>`, o MP4, `CAPA.jpg`, `LEGENDA.txt`, roteiro e pacote. Se a etapa falhar, consultar o log antes de liberar a publicação.

---

# Previsão BSB — @previsaobsb

Pipeline independente para **Reels automáticos sobre Brasília e as regiões administrativas do Distrito Federal**.

## Programação (horário de Brasília)

- **06h07** — Reel regional da manhã
- **18h07** — Reel com a previsão de **amanhã**

GitHub Actions usa UTC (09h07 e 21h07). O agendamento do GitHub pode atrasar alguns minutos. **A publicação agendada permanece travada até que a variável de repositório `BSB_AUTO_PUBLISH` seja definida como `true`.** Sem essa variável, as execuções programadas apenas geram o MP4. O comando manual `workflow_dispatch` começa em modo **não publicar**: gera MP4 e legenda para inspeção.

## Fluxo

1. `boletim.py`: consulta Open-Meteo com cinco áreas editoriais (Centro, Norte, Oeste, Sul e Leste), rodízio de localidades e números reais.
2. `render_reel.py`: cria quadros verticais 1080 × 1920, narração em português com espeak-ng e codificação H.264/AAC.
3. GitHub Actions: valida vídeo, salva MP4 e legenda como artefatos por três dias.
4. `publicar_reel.py`: utiliza o **upload resumível oficial da Meta**, aguarda o processamento do container, publica o Reel e recebe o permalink.
5. `publicados.json`: registra ID, permalink e turno para reduzir duplicações. GitHub Actions confirma o registro no repositório.

**Importante:** essa é a primeira versão funcional de vídeo; a estética e a narração ainda não reproduzem os personagens Bira e Bia nem o motor visual completo de Previsão RJ. Para alcançar essa qualidade, é necessária uma etapa adicional de portabilidade de personagens e vozes. A automação não depende de recursos privados do RJ.

## Configuração de conta profissional Instagram

No repositório, abra **Settings → Secrets and variables → Actions → New repository secret**. Adicione exclusivamente as credenciais do @previsaobsb:

- `INSTAGRAM_ACCESS_TOKEN`: token válido, com permissões para publicação no Instagram.
- `INSTAGRAM_USER_ID`: ID numérico da conta profissional do Instagram, não o nome de usuário.

Em **Variables**, opcionalmente defina `META_GRAPH_VERSION` (padrão `v24.0`). Depois de um teste manual de publicação bem-sucedido, crie a variável **`BSB_AUTO_PUBLISH` = `true`** para liberar as postagens agendadas.

A conta precisa estar corretamente configurada para publicação pela API Instagram Graph; confirme as permissões e, conforme o tipo de autenticação, a vinculação necessária com uma Página do Facebook. **Nunca coloque tokens no código ou em mensagens públicas.**

## Primeiro teste sem postar

Abra **Actions → Previsão BSB — Reels Instagram → Run workflow**, deixe **publicar** desligado e execute. Depois baixe o artefato `previsaobsb-reel-...`, assista ao MP4 e confira os números e a narração.

Para publicar um vídeo de teste, habilite `publicar` em uma execução manual após revisar o MP4 e confirmar os secrets. Os horários recorrentes só publicarão depois que `BSB_AUTO_PUBLISH=true`. Se a variável estiver ativa e as credenciais ausentes, o job falhará com mensagem de diagnóstico, sem publicar.

## Verificação operacional

- Abra **Actions** e veja o último trabalho e os logs de cada etapa.
- Confira a presença de `publicados.json` após uma publicação confirmada.
- Compare o permalink registrado com o Reel visível em @previsaobsb.
- Caso um job falhe após publicar mas antes de salvar o histórico, verifique a conta antes de tentar novamente para não duplicar o Reel.

## Executar localmente

No Ubuntu, com `ffmpeg`, `ffprobe`, `espeak-ng`, fontes DejaVu e Python 3.12:

```bash
pip install Pillow
python boletim.py
python render_reel.py --out output/previsaobsb.mp4 --caption output/legenda.txt
```

Apenas o comando de renderização não publica nada.

## Política de segurança

Tokens somente em GitHub Secrets; logs não devem imprimir tokens. Não compartilhar credenciais nem reutilizar ID do Instagram do RJ. Datas e horários da previsão devem corresponder ao fuso local, e publicações repetidas precisam de verificação do histórico.

## Migração obrigatória para o motor RJ (10/11/2026)

**A automação legada com espeak-ng e imagens estáticas foi rejeitada e está sem agendamento e sem publicação. NÃO ativar BSB_AUTO_PUBLISH nem rodar render_reel.py para produção.**

O projeto original analisado é `pabloramoa-dev/previsao-rj`, particularmente:
- `hyperframes/compor.py`: compositor HTML/GSAP de telejornal, avatares Bira/Bia em SVG com lip sync, cards e ticker;
- `hyperframes/gerar_hf.py`: pipeline de dados, roteiro, narração Kokoro, áudio e HyperFrames;
- `src/previsao_rj/render/characters/kokoro.py`: TTS neural local, vozes combinadas;
- `src/previsao_rj/render/characters/pipeline.py`: presets Bira `pm_alex:0.82+pm_santa:0.18` e Bia `pf_dora:0.85+af_heart:0.15`;
- `.github/actions/setup-hyperframes/action.yml`: instalação do renderizador.

**Já importados para análise e adaptação:** `hyperframes/compor.py` e `estudio/kokoro.py`. O compositor importado ainda requer o motor de timeline, assets GSAP, configuração HyperFrames, fontes, tratamento dos roteiros, amplitude para boca e QA; importá-lo isoladamente não produz MP4.

**Próxima implementação:** portar o gerador, as dependências e os assets do RJ; substituir a geografia, paisagem, rótulos e identidade do Rio por Brasília/DF; alimentar seis ou mais regiões administrativas a partir da Open-Meteo, com leitura diária e rodízio; preservar exatamente as vozes e personagens originais; renderizar vídeo piloto em artefato; executar testes técnicos e revisão visual; só então restaurar a publicação na Meta. Sem fallback silencioso para slides estáticos ou espeak-ng.
