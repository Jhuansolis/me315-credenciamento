# Como contribuir

## Regra de ouro

A `main` é a versão oficial e está protegida. **Todo trabalho entra por Pull Request (PR) com pelo menos 1 aprovação.**

## O ciclo de uma tarefa

1. **Pegue uma Issue** no quadro (coluna "A fazer"), atribua a si mesmo e mova para "Fazendo".
2. **Atualize a main e crie uma branch:**
   ```bash
   git checkout main
   git pull
   git checkout -b percentil-por-area
   ```
3. **Trabalhe e faça commits pequenos:**
   ```bash
   git add src/percentil.py
   git commit -m "Calcula percentil invertendo a posição do Scimago"
   ```
4. **Envie e abra o PR:**
   ```bash
   git push -u origin percentil-por-area
   ```
   O GitHub mostra um botão "Compare & pull request". Preencha o modelo e escreva `Closes #N` (N = número da issue).
5. **Revisão:** outra pessoa revisa em até **24–48 h**, roda o caso de teste pedido e aprova ou pede ajustes.
6. **Merge:** aprovado, clique em "Squash and merge" e apague a branch.
7. **Todos atualizam:** `git checkout main && git pull`.

## Regras combinadas

- **PRs pequenos:** um PR resolve uma coisa só.
- **Revisão de verdade:** o PR deve pedir algo concreto, ex.: "rode `pytest tests/test_percentil.py` e confira se dá 0,75".
- **Cada um é dono de um módulo.** Os módulos conversam pelas funções descritas nos docstrings ("contratos"). Mudou um contrato? Avise no PR.
- **Fora do repositório:** CSVs grandes (`data/`), outros bancos `.db` (exceção: `scimago_etl/scimago.db`, versionado para o deploy; ao regenerá-lo, commite junto com a mudança do ETL), senhas. Senhas vão nos *secrets* do Streamlit Cloud.
- **Nomes de branch:** curtos, em minúsculas, com hífen (`leitura-lattes`, `tela-upload`).

## Conflitos

Se o Git avisar de conflito ao atualizar sua branch:

```bash
git checkout main && git pull
git checkout minha-branch
git merge main
# abra os arquivos marcados, escolha a versão certa entre <<<<<<< e >>>>>>>
git add arquivo.py
git commit
```

Na dúvida, peça ajuda no grupo antes de forçar qualquer coisa. **Nunca use `git push --force` na `main`.**
