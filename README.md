# LoL AI Coach v3.1 🎮🧠🗣️

Coach de League of Legends **por voz**, em português do Brasil. Ele acompanha a partida em tempo real, fala só quando tem algo útil a dizer e responde às suas perguntas por push-to-talk.

> Projeto de fã, sem vínculo com a Riot Games. *League of Legends* é marca registrada da Riot Games, Inc. O projeto usa apenas a Live Client Data API local do jogo, que mostra dados da sua própria partida.

## O que ele faz

- **Push-to-talk:** segure `ESPAÇO`, fale, solte. A fala é transcrita com Whisper (Groq), com o Google Speech Recognition como reserva, e há um dicionário que corrige termos de LoL ("gamba" → "gank", "flecha" → "flash"...).
- **Coach proativo:** detecta vida baixa, morte, renascimento, subida de nível, abates, ouro acumulado, pico de CS, itens novos dos inimigos e objetivos (dragão, barão, arauto, torres e inibidores).
- **Economia de IA:** regras locais (`coach_engine.py`) detectam os eventos primeiro, e a IA só é chamada para transformar o evento em uma frase. Há cooldown por tipo de evento e um cooldown global, para o coach não falar demais.
- **Memória curta** da conversa, para não repetir recomendações.
- **Voz neural** em pt-BR (Edge TTS), com fila, para a fala não travar o monitoramento.
- **Overlay** sempre no topo com o estado da partida e a última dica.
- **3 personalidades:** Debochado/Zueira, Analítico/Tryhard e Hype/Motivacional.
- **Perfil editável** em `player_profile.json` (nome, lane, campeões favoritos, nível, objetivo, tom).

## Requisitos

- Windows 10/11
- [Python 3.11+](https://www.python.org/downloads/) (marque **"Add Python to PATH"** na instalação)
- League of Legends instalado
- Microfone e internet (IA, transcrição e voz usam serviços online)
- Uma chave de API **gratuita** da Groq: https://console.groq.com/keys

## Instalação

1. Baixe ou clone o repositório:
   ```powershell
   git clone https://github.com/guhttps/lol-ai-coach.git
   cd lol-ai-coach
   ```
2. Copie `.env.example` para `.env` e coloque a sua chave:
   ```
   GROQ_API_KEY=sua_chave_aqui
   COACH_OVERLAY=true
   ```
3. (Opcional) Edite `player_profile.json` com o seu nome, lane e campeões favoritos.
4. Dê dois cliques em **`start_coach.bat`**. Na primeira vez ele cria o ambiente virtual e instala as dependências (leva alguns minutos).
5. Escolha a personalidade, abra o LoL e entre em uma partida.

Para instalar sem abrir o coach, use `INSTALAR_DEPENDENCIAS.bat`.

## Como usar

| Ação | Como |
|---|---|
| Falar com o coach | Segure `ESPAÇO`, fale e solte |
| Fechar o overlay | Feche a janelinha; o coach continua rodando |
| Encerrar | `Ctrl+C` no terminal |

Dicas:
- Jogue em **janela** ou **janela sem bordas**, pois em tela cheia exclusiva o overlay pode não aparecer.
- Se o push-to-talk não responder, execute o `start_coach.bat` **como administrador** (a biblioteca `keyboard` pode exigir isso no Windows).
- A tecla `ESPAÇO` também digita no chat do jogo se ele estiver aberto. Para mudar, altere `PUSH_TO_TALK_KEY` em `main.py`.

## Configuração

| Onde | O que muda |
|---|---|
| `.env` | `GROQ_API_KEY` e `COACH_OVERLAY` |
| `player_profile.json` | Nome, lane, campeões, nível, objetivo e tom |
| `main.py` | Tecla de push-to-talk, intervalo de leitura (3 s), tamanho do histórico |
| `coach_engine.py` | Limites e cooldowns de cada tipo de evento |
| `brain.py` | Regras do prompt, personalidades e modelos |
| `voice.py` | Voz e velocidade da fala |

## Estrutura

```
main.py            loop principal (push-to-talk + monitoramento)
brain.py           prompts, personalidades e chamadas à Groq
coach_engine.py    detecção local de eventos e cooldowns
live_client.py     leitura da Live Client Data API do LoL
item_data.py       identificação de itens finalizados
voice.py           transcrição (STT) e síntese de voz (TTS)
overlay.py         janela sempre no topo (Tkinter)
config.py          carregamento do perfil
```

## Limitações

A Live Client Data API não fornece posição no mapa, cooldowns inimigos, visão real nem intenção dos jogadores. O coach é instruído a **não inventar** o que não está nos dados e a responder `SILENCIO` quando não tem nada relevante a dizer.

## Privacidade e segurança

- O arquivo `.env` com a sua chave **não deve ser enviado** ao GitHub (já está no `.gitignore`).
- O áudio do microfone, enquanto você segura o botão, e o estado da sua partida são enviados à Groq. A voz do coach é gerada pelo serviço Edge TTS da Microsoft.
- Nenhum dado é guardado em servidor próprio. Tudo roda na sua máquina.

## Próximos passos possíveis

- Integração opcional com a Riot API (histórico e matchups)
- Detecção de lane/role
- Resumo pós-partida com pontos fortes e pontos a treinar
- Configuração gráfica de personalidade, frequência e volume
- Comandos de voz como "fica quieta" e "fala mais"

## Licença

[MIT](LICENSE)
