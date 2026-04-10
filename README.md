# PipeLovers — Dashboard de Reimplantação

Dashboard web para acompanhar o sucesso da reimplantação de clientes na nova plataforma PipeLovers.

🔗 **Live:** https://guiweissbock-cpu.github.io/reimplantacao-pipe/

---

## O que o dashboard mostra

| Aba | Descrição |
|-----|-----------|
| 📊 Overview | KPIs gerais + tabela de adoção por empresa |
| 🏢 Empresas | Cards visuais por empresa com barra de progresso |
| 👤 Por CSM | Performance de cada CSM (empresas, usuários, % adoção) |
| ✅ Acessaram | Usuários reimplantados que já entraram na plataforma |
| ⏳ Não Acessaram | Usuários reimplantados que ainda não acessaram |
| 🚫 Não Reimplantados | Usuários cadastrados mas ainda não migrados |
| ⚠️ Não Encontrados | Usuários no Members que não estão na base de usuários |
| 🎬 Aulas Assistidas | Consumo de conteúdo por empresa, CSM e conteúdo |

---

## Estrutura do repositório

```
reimplantacao-pipe/
├── index.html              ← Dashboard (gerado automaticamente, não editar)
├── gerar_data.py           ← Script que processa os CSVs e atualiza o index.html
├── members-report.csv      ← Export da plataforma: todos os membros cadastrados
├── usuarios.csv            ← Base de usuários ativos por empresa
├── clientes.csv            ← Base de clientes com CSM responsável
├── consumo.csv             ← Relatório de aulas assistidas
└── .github/
    └── workflows/
        └── atualizar.yml   ← Automação: roda gerar_data.py a cada push de CSV
```

---

## Como atualizar o dashboard

### Automático (recomendado)
1. Acesse o repositório no GitHub
2. Faça upload dos CSVs atualizados (**Add file → Upload files**)
3. O GitHub Actions roda automaticamente e atualiza o dashboard em ~1 minuto

> O workflow dispara quando qualquer um dos 4 CSVs é alterado.
> Você não precisa mexer no `index.html` — ele é gerado automaticamente.

### Manual (fallback)
```bash
# Na pasta do repositório local:
python gerar_data.py

# Depois sobe o index.html gerado:
git add index.html
git commit -m "update"
git push
```

---

## De onde vêm os CSVs

| Arquivo | Origem | Frequência sugerida |
|---------|--------|-------------------|
| `members-report.csv` | Export da plataforma Curseduca → Membros | Sempre que houver novos usuários |
| `usuarios.csv` | Base interna de usuários ativos por empresa | Sempre que adicionar usuários novos |
| `clientes.csv` | Base de clientes com CSM | Quando mudar CSM de conta |
| `consumo.csv` | Export Curseduca → Relatório de consumo | Sempre que quiser ver aulas atualizadas |

> ⚠️ Os CSVs podem ser exportados com vírgula (`,`) ou ponto e vírgula (`;`) — o script detecta automaticamente.

---

## Como o script funciona (gerar_data.py)

### Lógica de detecção de empresas reimplantadas
O script lê o campo `Turmas` do `members-report.csv`. Uma empresa é considerada **reimplantada** quando aparece na turma do usuário em um destes formatos:
- `1 - 038 - Becomex` → empresa: `Becomex`
- `52 - Totvs` → empresa: `Totvs`

Turmas genéricas são ignoradas: `Aplicativo`, `Full Pass`, `Pré-vendas`, `Gestão`, `Executivos`, `Canais`, `Class`.

### Lógica de CSM
O script cruza o nome da empresa com a coluna `CSM` do `clientes.csv`. Há um bloco de **overrides manuais** para casos ambíguos:

```python
CSM_OVERRIDES = {
    'totvs': 'Bárbara Cabrini',  # TOTVS BRASIL CENTRAL (Bárbara) vs TOTVS (Gustavo)
}
```

> Se surgir outra empresa com nome duplicado ou conflito de CSM, adicione aqui.

### Domínio PipeLovers
Usuários com e-mail `@pipelovers.net` ou `@curseduca.com` são tratados como empresa **PipeLovers** com CSM **Gunther Weissbock**.

### Não Encontrados
Usuários que estão no `members-report.csv` mas **não estão** no `usuarios.csv`. Isso significa que foram cadastrados na plataforma mas nunca foram adicionados à base de usuários — o CSM precisa inserir manualmente.

---

## Erros comuns e soluções

### ❌ `ParserError: Error tokenizing data`
**Causa:** O CSV foi exportado com ponto e vírgula (`;`) mas o script tentou ler com vírgula.
**Solução:** Já corrigido — o `gerar_data.py` detecta automaticamente o separador.

### ❌ `exit code 128` no GitHub Actions
**Causa:** O workflow não tinha permissão para fazer `git push`.
**Solução:** O `atualizar.yml` já tem `permissions: contents: write` e usa `GITHUB_TOKEN`.

### ❌ `exit code 1` no GitHub Actions
**Causa:** Erro no `gerar_data.py` — geralmente CSV faltando ou com formato inesperado.
**Solução:** Clica no job vermelho no Actions → expande "Gerar index.html" → lê o traceback.

### ❌ Dashboard mostra empresa com CSM errado
**Causa:** Dois clientes com nome parecido no `clientes.csv`.
**Solução:** Adicionar override manual em `CSM_OVERRIDES` no `gerar_data.py`.

### ❌ Empresa nova não aparece no dashboard
**Causa:** A turma da empresa usa um formato não reconhecido.
**Solução:** Verificar o campo `Turmas` no `members-report.csv` para essa empresa e checar se o padrão é `X - Nome` ou `X - NNN - Nome`.

---

## Configuração do GitHub Pages

**Settings → Pages → Source: Deploy from branch → Branch: main → / (root) → Save**

URL do dashboard: `https://[usuario].github.io/reimplantacao-pipe/`

---

## Histórico de decisões técnicas

- **Dashboard HTML autocontido:** os dados ficam embutidos no `index.html` para funcionar com GitHub Pages estático (sem servidor).
- **gerar_data.py:** processa os 4 CSVs e injeta os dados como variáveis JavaScript dentro do `index.html`.
- **GitHub Actions:** detecta push de qualquer CSV e roda o script automaticamente.
- **Detecção de separador:** CSVs exportados pela Curseduca às vezes usam `;` — o script testa os dois automaticamente.
- **CSM_OVERRIDES:** bloco de regras fixas para resolver ambiguidades de nome que o cruzamento automático não consegue resolver.

---

## Contato / Suporte

Em caso de dúvida, abra uma nova conversa no Claude (claude.ai) e cole o conteúdo deste README — ele contém contexto suficiente para qualquer assistente entender o projeto e ajudar.
