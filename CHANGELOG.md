# Changelog

Todas as mudanças relevantes do projeto ficam registradas aqui.
O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto usa [versionamento semântico](https://semver.org/lang/pt-BR/).

## [Unreleased]

## [3.3.0] - 2026-11-03

### Adicionado
- Resumo pós-partida: ao fim de cada partida, o coach salva na pasta `partidas` e abre no navegador uma página com resultado, K/D/A, participação em abates, CS por minuto e aos 10 minutos, placar de visão, itens finais, tempo com 1.800 de ouro ou mais sem gastar, gráficos de CS e ouro, linha do tempo com tudo o que o coach falou e uma análise da IA com 2 pontos fortes e 2 pontos a treinar. Os dados também ficam em um `.json`.
- Fechar o coach com `Ctrl+C` no meio da partida salva um resumo parcial.
- Novas configurações no `.env`: `POST_MATCH_REPORT` e `POST_MATCH_OPEN`.

### Corrigido
- O aviso de vida baixa nunca disparava: a vida era lida das entradas de `allPlayers`, que não trazem esse dado na Live Client API. Agora ela vem de `activePlayer`, e aliados e inimigos deixaram de ser enviados à IA com a vida zerada.

## [3.2.0] - 2026-11-03

### Adicionado
- Executável para Windows: cada release no GitHub traz um `.zip` pronto, sem precisar instalar Python.
- Suporte a qualquer provedor compatível com OpenAI Chat Completions (OpenAI, OpenRouter, Ollama local etc.) via `LLM_BASE_URL`, `LLM_API_KEY` e `LLM_MODEL`.
- Novas configurações no `.env`: `PUSH_TO_TALK_KEY`, `CHECK_INTERVAL_SECONDS`, `MAX_HISTORY_MESSAGES` e `COACH_PERSONALITY`.
- CI no GitHub Actions: lint com ruff e testes no Windows com Python 3.11 a 3.14.
- Visual escuro e semitransparente no overlay, com cor de status (em partida, aguardando ou fora da partida).

### Alterado
- As chamadas de IA rodam em segundo plano: o monitoramento da partida não trava enquanto a resposta é gerada, e perguntas faladas têm prioridade sobre dicas automáticas.
- Perguntas diretas por voz são sempre respondidas; só as dicas automáticas podem ficar em silêncio quando não há nada útil a dizer.
- Dicas automáticas pendentes usam o estado mais recente da partida, sem acumular orientações antigas.
- Mensagens de erro específicas para falhas de conexão, chave recusada, limite de uso e respostas inválidas da API.

### Corrigido
- O contexto da conversa é reiniciado entre partidas, inclusive em partidas seguidas com a mesma conta e o mesmo campeão.
- Quedas breves da Live Client API (até 12 segundos) não encerram mais a análise da partida.
- Eventos importantes não se perdem enquanto o cooldown global bloqueia a fala.
- O coach não confunde outro jogador com você durante o carregamento da partida.
- O catálogo de itens do Data Dragon é recarregado depois de uma falha temporária.
- O `.env` e o perfil são encontrados mesmo quando o coach é aberto a partir de outra pasta.
- A saída redirecionada para arquivo (`> log.txt`) não derruba mais o coach por causa dos emojis.
- Fechar o overlay não acumula mais mensagens em memória.

## [3.1.0] - 2026-10-07

Primeira versão publicada: coach por voz com push-to-talk, dicas proativas por eventos da partida, três personalidades, perfil editável e overlay.

[Unreleased]: https://github.com/guhttps/lol-ai-coach/compare/v3.3.0...HEAD
[3.3.0]: https://github.com/guhttps/lol-ai-coach/compare/v3.2.0...v3.3.0
[3.2.0]: https://github.com/guhttps/lol-ai-coach/compare/1dc919a...v3.2.0
[3.1.0]: https://github.com/guhttps/lol-ai-coach/commit/1dc919a
