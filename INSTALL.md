# Guia de instalação – ntsoft-orgfiles (PC da loja)

Este guia assume um PC com Windows 10/11.

## 1. Instalar Python

1. Baixe o Python 3.12+ no site oficial.
2. Durante a instalação, marque a opção **"Add Python to PATH"**.

## 2. Obter o código do projeto

Você tem duas opções:

- **Via Git** (recomendado):
  1. Instale o Git para Windows.
  2. Abra o PowerShell na pasta onde deseja colocar o projeto.
  3. Clone o repositório:

  ```powershell
  git clone https://github.com/nettocarrero/ntsoft_filesOrg.git
  cd ntsoft_filesOrg
  ```

- **Via cópia manual**:
  1. Copie a pasta do projeto do seu PC para o PC da loja (pen drive, rede, etc.).

## 3. Configurar o ambiente virtual

Na raiz do projeto (`ntsoft_filesOrg`), execute:

```powershell
setup_env.bat
```

Esse script irá:
- criar o ambiente virtual `.venv`;
- ativá-lo;
- atualizar o `pip`;
- instalar as dependências do `requirements.txt`.

## 4. Instalar Tesseract (OCR)

1. Baixe o instalador do **Tesseract OCR** para Windows (por exemplo, `tesseract-ocr-w64-setup.exe`).
2. Instale normalmente (recomenda-se deixar o caminho padrão, ex.: `C:\Program Files\Tesseract-OCR`).
3. Certifique-se de que `tesseract.exe` está no **PATH** do sistema ou anote o caminho completo.

Se preferir usar um caminho específico, você poderá configurá-lo depois em `config.local.json` (campo `ocr.tesseract_cmd`).

## 5. Instalar Poppler (para OCR em PDFs)

1. Baixe o pacote binário do **Poppler para Windows**.
2. Extraia para uma pasta, por exemplo: `C:\poppler`.
3. Adicione `C:\poppler\bin` ao **PATH** do sistema (Variáveis de Ambiente).

## 6. Abrir e configurar WhatsApp Desktop

1. Instale o **WhatsApp Desktop** (versão da Microsoft Store).
2. Entre com a conta do grupo desejado.
3. Envie/receba alguns arquivos (PDF/ZIP/RAR) para que a pasta `transfers` seja criada.
4. Localize a pasta interna de downloads (exemplo típico):

```text
C:\Users\<USUARIO>\AppData\Local\Packages\5319275A.WhatsAppDesktop_cv1g1gvanyjgm\LocalState\sessions\<SESSION_ID>\transfers
```

Anote esse caminho para usar na configuração local.

## 7. Criar arquivo de configuração local

Na raiz do projeto, crie um arquivo `config.local.json` com o conteúdo básico abaixo (ajuste os caminhos conforme o PC da loja):

```json
{
  "paths": {
    "input_dir": "C:/Projetos/ntsoft-orgfiles/input",
    "output_dir": "C:/Projetos/ntsoft-orgfiles/output",
    "temp_dir": "C:/Projetos/ntsoft-orgfiles/temp",
    "review_manual_dir": "C:/Projetos/ntsoft-orgfiles/review_manual",
    "reports_dir": "C:/Projetos/ntsoft-orgfiles/reports"
  },
  "processed_input": {
    "processed_dir": "C:/Projetos/ntsoft-orgfiles/processed_input",
    "action": "move"
  },
  "ocr": {
    "enabled": true,
    "tesseract_cmd": "C:/Program Files/Tesseract-OCR/tesseract.exe",
    "language": "por",
    "dpi": 200,
    "min_text_length_trigger": 50
  },
  "whatsapp_ingestion": {
    "enabled": true,
    "source_dir": "C:/Users/SEU_USUARIO/AppData/Local/Packages/5319275A.WhatsAppDesktop_cv1g1gvanyjgm/LocalState/sessions/SESSAO/transfers",
    "recursive": true,
    "startup_scan": true
  }
}
```

Observações:
- Use **barra normal `/`** ou escape as barras invertidas (`\\`) no JSON.
- Se não quiser OCR ou ingestão do WhatsApp, ajuste `enabled` para `false` nas seções correspondentes.

## 8. Verificar dependências

Com o ambiente virtual já criado (via `setup_env.bat`), execute:

```powershell
call .venv\Scripts\activate.bat
python check_dependencies.py
```

O script irá verificar:
- versão do Python;
- existência do `.venv`;
- pacotes Python principais;
- presença do Tesseract;
- presença do Poppler (`pdfinfo`/`pdftoppm`);
- existência das pastas de trabalho (`input`, `output`, etc.);
- caminho da pasta do WhatsApp (se ingestão estiver habilitada).

Verifique as saídas marcadas como **ERROR** ou **WARNING** e ajuste conforme instruções.

## 9. Execução em modo watch (recomendado)

Para deixar o sistema rodando continuamente e processando arquivos assim que chegam:

```powershell
run_watch.bat
```

Esse script:
- ativa o `.venv`;
- executa `python -m app.main --watch`;
- inicia:
  - o watcher da pasta `input/`;
  - o watcher da pasta do WhatsApp (se habilitado).

## 10. Execução pontual

Se quiser rodar o processamento apenas uma vez sobre o conteúdo atual da pasta `input/`:

```powershell
run_once.bat
```

## 11. Fluxo típico no PC da loja

1. WhatsApp Desktop baixa arquivos para sua pasta interna (`transfers`).
2. O watcher do WhatsApp detecta novos arquivos (`.pdf`, `.zip`, `.rar`), aguarda estabilização e copia para `input/`.
3. O watcher principal detecta novos arquivos em `input/` e executa o pipeline:
   - extração de PDF/ZIP/RAR;
   - OCR (se necessário);
   - classificação por loja e tipo;
   - organização em `output/` e `review_manual/`;
   - geração de relatórios em `reports/`;
   - movimentação dos arquivos de `input/` para `processed_input/<data>/`.

## 12. Itens que permanecem manuais

- Instalar/atualizar Python, Tesseract, Poppler e WhatsApp Desktop.
- Ajustar o `config.local.json` para cada PC (caminhos podem variar).
- Configurar o WhatsApp Desktop (entrar no grupo correto, garantir que está baixando anexos).
- Manter espaço em disco suficiente nas pastas `input/`, `output/`, `processed_input/` e `reports/`.

