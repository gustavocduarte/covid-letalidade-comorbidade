# CLAUDE.md

Regras de trabalho para este repositório (pipeline de ETL do SIVEP-Gripe + dashboard Streamlit
de letalidade de COVID-19 por comorbidade).

## Idioma
- Responder sempre em português.

## Antes de qualquer tarefa
- Rodar `git pull` antes de começar.
- Confirmar no código antes de corrigir algo: ler o trecho real e reproduzir o problema, em vez de supor.

## Verificação
- Rodar `pytest` e `ruff check .` (e `mypy`, quando passar a existir) antes de propor um commit.
- Informar a contagem de testes pela diferença real desde o último commit (ex.: "10 → 14, +4"),
  contada a partir de uma execução, nunca de memória.

## Git
- Mostrar o diff e esperar a aprovação explícita antes de cada commit.
- Um commit por assunto. Nunca usar `--amend`.
- Mensagens de commit em português, sem trailer de atribuição (sem `Co-Authored-By`).
- Nunca usar `git stash` com trabalho não commitado; se precisar isolar, usar um worktree
  temporário em `%TEMP%`.

## Código
- Comentários curtos, explicando o porquê. Sem histórico de correções ("antes fazia X").
- Constantes (caminhos, URLs, listas de colunas, códigos de domínio) ficam num módulo de
  configuração em `src/`, não espalhadas pelos scripts.
- Nomes de funções, variáveis e textos do projeto em português, como no código existente.

## Testes
- Testes não acessam a rede nem gravam em `data/`; usar `tmp_path` e fixtures em `tests/fixtures/`.
- Testes que dependem dos dados brutos (~4,8 GB em `data/raw/`) rodam só localmente e são
  pulados no CI e quando `data/raw/` não existe.
- O teste golden roda só sob demanda (`pytest -m golden`): antes e depois de qualquer mudança
  no pipeline, e não nas verificações de rotina.
- Nunca mudar o valor esperado de um teste existente sem me perguntar antes; se uma mudança
  exigir isso, parar e explicar.
- Testes de interface do dashboard selecionam botões e campos pelo rótulo, não pela posição.

## Arquivos temporários
- Scripts, saídas e cópias temporárias vão em `%TEMP%`, nunca dentro do repositório.

## Dados
- `data/raw/` e caches grandes intermediários (ex.: `data/processed/casos_covid_detalhado.csv`)
  não vão para o git.
- Os CSVs pequenos de `data/processed/` e o GeoJSON são versionados, porque o dashboard
  publicado depende deles.

## Refatorações
- Refatorações não mudam os números gerados. O teste de regressão dourado (saídas do pipeline
  comparadas às versionadas) precisa continuar passando; mudar um número é decisão de
  metodologia e precisa de aprovação.

## Comandos
```bash
pip install -r requirements.txt   # dependências
pytest                            # testes
ruff check .                      # lint
python src/pipeline.py            # ETL completo (baixa ~4,9 GB na primeira vez)
streamlit run src/dashboard.py    # dashboard em http://localhost:8501
```
