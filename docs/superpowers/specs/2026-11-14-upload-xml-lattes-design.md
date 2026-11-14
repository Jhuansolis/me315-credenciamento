# Upload do XML do Lattes — design curto

Data: 2026-11-14. Muda o não-objetivo "upload de XML" da spec
[2026-11-13-motor-regras-streamlit-design.md](2026-11-13-motor-regras-streamlit-design.md):
agora ele entra no escopo.

## Intenção

O docente consegue exportar o próprio currículo em XML pela Plataforma Lattes. Esse arquivo
é mais fácil de obter do que o HTML (não tem captcha nem Ctrl+S) e mais confiável de ler
(ISSN, ano e DOI vêm em atributos próprios, sem raspar texto). O app passa a aceitar **HTML
ou XML**, e a nota tem de ser a mesma qualquer que seja o formato.

## Objetivos, não-objetivos, anti-objetivos

- **Objetivos:** um só campo de upload que aceita `.html`, `.htm`, `.xml` e `.zip` (o XML
  compactado, como o Lattes costuma entregar); mesmo resultado de nota para o mesmo currículo;
  lembrete no painel do Artigo Y com as licenças e o PcD registrados no XML; o comando
  `python -m lattes_rank` também lê XML.
- **Não-objetivos:** preencher sozinho os campos do Artigo Y; ler do XML outras seções além de
  artigos publicados, cabeçalho, licenças e PcD; guardar o arquivo enviado.
- **Anti-objetivos (seria falha mesmo funcionando):** ler, mostrar ou registrar em log os
  dados pessoais do XML (CPF, passaporte, RG, filiação, endereço, data de nascimento); fazer
  commit de um XML real no repositório; ranking ou regras com ramificações "se veio de XML".

## Abordagens

- **A (escolhida):** um leitor de XML dentro do `lattes_rank`, ao lado do leitor de HTML,
  gerando o mesmo `Curriculo`/`Artigo`, com uma função de entrada única que detecta o formato
  pelo conteúdo. Fica um modelo de dados só, o ranking, as regras e o relatório não mudam, e o
  comando de terminal ganha o XML sem esforço extra.
- **B:** um leitor em `src/lattes.py` (onde há um TODO), só para o app, devolvendo
  dicionários. Descartada: ficariam dois formatos de artigo no projeto, e o comando de
  terminal ficaria sem XML.
- **Converter o XML em HTML falso:** descartada, porque é mais frágil e dá mais trabalho.

## O que foi decidido

- **Leitura (`lattes_rank`):** novo leitor de XML. Por artigo, lê os atributos de
  `ARTIGO-PUBLICADO`: `ANO-DO-ARTIGO`, `TITULO-DO-ARTIGO` e `DOI` (em `DADOS-BASICOS-DO-ARTIGO`),
  e `TITULO-DO-PERIODICO-OU-REVISTA` e `ISSN` (em `DETALHAMENTO-DO-ARTIGO`). O ISSN passa por
  `normalizar_issn`, como no HTML. Do cabeçalho: `NUMERO-IDENTIFICADOR` (ID Lattes),
  `NOME-COMPLETO` e `DATA-ATUALIZACAO` (`DDMMAAAA` → `DD/MM/AAAA`). A codificação é a que o
  próprio XML declara (ISO-8859-1 no exemplo).
- **Lembrete do Artigo Y:** o `Curriculo` ganha a lista de licenças (`TIPO-LICENCA`, início e
  fim) e o PcD declarado (atributo `PCD` de `DADOS-GERAIS`). Do HTML esses campos vêm vazios. O
  app mostra um aviso informativo no painel do Artigo Y, por exemplo "O XML registra 2 licenças
  (PATERNIDADE: 10/03/2022–29/03/2022; …)". Os campos continuam manuais e o sistema não decide
  se uma licença conta.
- **Detecção:** pelo conteúdo, não pela extensão. Se for ZIP, abre e usa o único `.xml` de
  dentro. Se for XML, raiz `CURRICULO-VITAE`. Caso contrário, trata como HTML (comportamento
  atual). XML de outra coisa ou malformado vira mensagem de erro clara, sem traceback.
- **App:** um só `file_uploader` (`html`, `htm`, `xml`, `zip`). O texto de ajuda explica os
  dois caminhos (salvar a página ou exportar o XML).
- **Limpeza:** `src/lattes.py` (stub vazio) é apagado.
- **Testes:** uma fixture XML **sintética** (pessoa fictícia, poucos artigos, com acento em
  ISO-8859-1, uma licença e PcD), uma versão `.zip` montada dentro do teste, casos de XML
  inválido e de ZIP sem XML, e um teste de integração no app com upload de XML.
- **Documentação:** README (raiz e `lattes_rank`) e o não-objetivo da spec anterior
  atualizados.

## Fica a critério de quem implementa

- O nome do módulo e da função de entrada única, e como `ler_html` em `src/integracao.py` se
  adapta (renomear ou criar uma função ao lado).
- A numeração `sequencia` dos artigos do XML (sugestão: ordem no arquivo, de 1 a N).
- A proteção contra XML malicioso sem dependência nova (sugestão: recusar `<!DOCTYPE`/`<!ENTITY`,
  que o Lattes não usa) e um limite de tamanho ao descompactar o ZIP.
- Como reorganizar o `app.py` para o lembrete aparecer no painel do Artigo Y, que hoje vem
  antes da leitura do arquivo.
