# Como contribuir

Obrigado pelo interesse! Bugs, ideias e pull requests são bem-vindos.

## Antes de começar

- **Encontrou um bug?** Abra uma [issue de bug](https://github.com/guhttps/lol-ai-coach/issues/new?template=bug_report.yml) com o log do terminal. Apague sua chave de API se ela aparecer.
- **Tem uma ideia?** Abra uma [sugestão](https://github.com/guhttps/lol-ai-coach/issues/new?template=feature_request.yml) antes de escrever muito código, para alinharmos o caminho.

## Ambiente de desenvolvimento

Requer Windows 10/11 e Python 3.11 ou mais recente.

```powershell
git clone https://github.com/guhttps/lol-ai-coach.git
cd lol-ai-coach
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements-dev.txt
copy .env.example .env   # e coloque sua chave
python main.py
```

## Testes e lint

```powershell
python -m unittest discover -s tests -v
ruff check .
```

Os testes não chamam serviços reais: Groq, Data Dragon, Live Client API e o loop principal são simulados com `unittest.mock`. Eles rodam em segundos e não precisam do LoL aberto. O CI roda as duas verificações em todo pull request, nas versões 3.11 a 3.14 do Python.

Mudanças no loop principal, na voz ou no overlay também merecem um teste em uma partida real (uma partida contra bots já serve).

## Onde mexer

| Quero mudar... | Arquivo |
|---|---|
| Quando o coach fala (limites, cooldowns, novos eventos) | `coach_engine.py` |
| O que e como ele fala (regras do prompt, personalidades) | `brain.py` |
| Os dados lidos da partida | `live_client.py` |
| Voz, transcrição e dicionário de termos de LoL | `voice.py` |
| A janela do overlay | `overlay.py` |
| Variáveis do `.env` e perfil | `config.py` |

## Convenções

- Textos para quem usa (mensagens, prompts, README) em português do Brasil.
- Mensagens de commit em inglês, no imperativo: `Add`, `Fix`, `Keep`...
- Toda correção de bug vem com um teste que falharia sem ela.
- Registre mudanças visíveis em `CHANGELOG.md`, na seção `[Unreleased]`.

## Gerar o executável

```powershell
.\scripts\build.ps1
```

O pacote fica em `dist/LoL_AI_Coach-<versão>-windows.zip`.

## Publicar uma versão (mantenedores)

1. Atualize `APP_VERSION` em `config.py`.
2. No `CHANGELOG.md`, renomeie `[Unreleased]` para `[X.Y.Z] - AAAA-MM-DD` e crie um `[Unreleased]` vazio acima.
3. Faça o commit na `main`, crie a tag e envie:
   ```powershell
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

O workflow de release confere se a tag corresponde a `APP_VERSION`, roda os testes, gera o `.zip` e publica a release com as notas do changelog.
