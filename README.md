# ntsoft-orgfiles

Sistema local em Python para organizar automaticamente documentos financeiros recebidos (por enquanto) via pasta de entrada local, com foco em PDFs e arquivos compactados (ZIP e RAR).

## Objetivo do projeto

Organizar automaticamente documentos financeiros de quatro lojas diferentes, identificando:
- **loja de origem** (ubajara, ibiapina, são benedito, guaraciaba)
- **tipo de documento** (boleto, nota fiscal, nota de serviço, taxa, comprovante, desconhecido)

e movendo os arquivos para uma estrutura de pastas organizada, além de gerar relatórios de processamento.

## Problema que resolve

Hoje os documentos chegam misturados, muitas vezes com nomes de arquivo pouco descritivos, dentro de ZIPs com subpastas variadas. Alguém precisa abrir manualmente cada documento para descobrir:
- a qual **loja** pertence
- qual o **tipo** de documento

Este projeto automatiza a maior parte desse trabalho, deixando para revisão manual apenas os casos com baixa confiança.

## Estrutura de pastas principal

```text
project_root/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── logger.py
│   ├── models/
│   ├── services/
│   ├── utils/
│   └── data/
├── input/
├── output/
├── temp/
├── review_manual/
├── reports/
├── tests/
├── requirements.txt
├── pyproject.toml
└── .gitignore
```

### Pastas funcionais

- **`input/`**: onde o usuário coloca manualmente os arquivos de entrada (PDF, ZIP, RAR, etc.).
- **`output/`**: onde os arquivos classificados são organizados por loja e tipo de documento.
- **`temp/`**: usado para extração de ZIPs e arquivos de trabalho temporários.
- **`review_manual/`**: arquivos que não puderam ser classificados com confiança suficiente.
- **`reports/`**: relatórios em JSON e TXT de cada execução.

## Como instalar

1. Certifique-se de ter **Python 3.12+** instalado.
2. No diretório raiz do projeto, crie e ative um ambiente virtual:

```bash
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# ou (CMD)
.venv\Scripts\activate.bat
```

3. Instale as dependências:

```bash
pip install -r requirements.txt
```

## Como executar

1. Garanta que as pastas `input/`, `output/`, `temp`, `review_manual/`, `reports/` e `processed_input/` existam (o sistema tenta criá-las automaticamente).
2. Coloque arquivos **PDF**, **ZIP** e **RAR** dentro da pasta `input/`.
3. Execute o módulo principal (modo pontual):

```bash
python -m app.main
```

Ao final da execução, o sistema:
- organiza os arquivos em `output/` (e/ou `review_manual/`)
- gera um relatório JSON e um TXT em `reports/`
- exibe um resumo no terminal (total processado, de ZIP, enviados à revisão, etc.).

### Modo watch (monitoramento contínuo)

Para monitorar continuamente a pasta `input/` e processar novos arquivos automaticamente:

```bash
python -m app.main --watch
```

Neste modo:
- novos arquivos **PDF**, **ZIP** e **RAR** adicionados à pasta `input/` são detectados;
- o sistema aguarda o arquivo ficar “estável” (tamanho sem mudar por alguns instantes);
- então aciona o mesmo pipeline de processamento usado no modo pontual;
- após processamento bem-sucedido, o arquivo original é movido para `processed_input/` (comportamento padrão, configurável).

## Como rodar testes

Com o ambiente virtual ativo e dependências instaladas:

```bash
pytest
```

Os testes básicos cobrem:
- normalização de texto
- classificação por aliases de loja
- extração de ZIP
- leitura de PDF textual simples
- detecção de arquivos ZIP/RAR e fluxo de processamento de arquivos compactados
 - funções utilitárias de sanitização de caminhos e de monitoramento de arquivos

## Suporte a arquivos RAR

O projeto utiliza a biblioteca `rarfile` para lidar com arquivos `.rar`.  
**Importante**: o `rarfile` depende de um extrator de RAR instalado no sistema, como:

- `unrar`
- `rar`
- `bsdtar`

No Windows, recomenda-se:

- instalar o utilitário `unrar` ou `rar` e
- garantir que o executável esteja acessível no `PATH` do sistema.

Caso o extrator não esteja disponível, ao tentar processar um arquivo `.rar` o sistema:

- registrará um erro no log (`reports/app.log`), com mensagem explicando a ausência do extrator;
- marcará o processamento daquele RAR como erro no relatório JSON/TXT.

Para validar se o ambiente está pronto para RAR:

1. Instale o extrator de RAR.
2. Coloque um arquivo `.rar` de teste em `input/` contendo alguns PDFs.
3. Execute:

```bash
python -m app.main
```

4. Verifique no log e no relatório se:
   - o RAR foi detectado,
   - extraído com sucesso,
   - os PDFs internos foram processados normalmente.

## Suporte a OCR

O sistema tenta extrair texto de PDFs usando PyMuPDF.  
Se o texto retornado for insuficiente (muito curto ou vazio), e o OCR estiver habilitado, ele tenta extrair texto via OCR antes de classificar o documento.

Atualmente é usado:

- `pdf2image` para converter páginas em imagens;
- `pytesseract` como engine de OCR (Tesseract).

Dependências externas necessárias (especialmente no Windows):

- **Tesseract OCR** instalado (por exemplo, `tesseract-ocr-w64-setup.exe`);
- **Poppler** para Windows (para o `pdf2image` funcionar; é necessário apontar o caminho nas variáveis de ambiente ou instalar no `PATH`).

Se quiser apontar manualmente o executável do Tesseract, configure `tesseract_cmd` em `OCRConfig` (`app/config.py`).

No relatório JSON/TXT, cada documento inclui:

- `text_source`: `"pdf_text"` ou `"ocr"` ou `"none"`;
- `ocr_used`: se o OCR foi tentado;
- `ocr_success`: se o OCR retornou texto útil;
- `ocr_metadata`: metadados como páginas processadas, engine, tamanho do texto, etc.

## Limitações atuais

- **Sem integração com WhatsApp**: a entrada é exclusivamente via pasta local `input/`.
- **Modo watch opcional**: o monitoramento contínuo da pasta depende de executar explicitamente com `--watch` e requer a biblioteca `watchdog`.

## Próximos passos planejados

1. Melhorar heurísticas de acionamento de OCR (por tipo de documento, tamanho, etc.).
2. Monitoramento automático mais inteligente da pasta `input/` (filtros, priorização).
3. Interface gráfica simples para acompanhar o processamento e revisar documentos.
4. Integração com WhatsApp (ex.: baixar anexos de um grupo específico).
5. Feedback de correção manual alimentando um mecanismo de aprendizado simples (ajuste de palavras-chave, aliases, pesos).

## Notas de arquitetura

- Configurações (paths, pesos, limiares de confiança) centralizadas em `app/config.py`.
- Logging configurado em `app/logger.py`, com saída em console e arquivo.
- Serviços separados por responsabilidade:
  - scanner, zip, pdf, classifier, organizer, report.
- Modelos e enums em `app/models/`, facilitando evolução futura (OCR, novas lojas, novos tipos de documento).

