# Funcionalidades do Agente de Gerenciamento de Tarefas (Trello + Google ADK)

Este agente foi desenvolvido utilizando o **Google ADK (Agent Development Kit)** com o modelo **Gemini 2.5 Flash**, integrado à API oficial do **Trello** por meio da biblioteca `py-trello`.

O objetivo do agente é atuar como um assistente pessoal inteligente para organização de rotina, planejamento diário e gestão de tarefas em quadros do Trello.

---

## 🛠️ Ferramentas (Tools) do Agente

O agente conta com um conjunto completo de ferramentas para gerenciar o ciclo de vida das tarefas no Trello:

### 1. `get_temporal_context`
- **Descrição:** Obtém a data e hora atual do sistema no formato `YYYY/MM/DD HH:MM:SS`.
- **Finalidade:** O agente inicia a interação consultando o horário e a data atual para saudar o usuário e contextualizar o planejamento das atividades do dia.

### 2. `listar_quadros`
- **Descrição:** Consulta e lista todos os quadros (boards) disponíveis na conta do Trello associada ao token.
- **Finalidade:** Permite ao agente conhecer os quadros existentes e apresentá-los como opção ao usuário quando for necessário decidir onde criar ou consultar tarefas.

### 3. `adicionar_tarefa`
- **Descrição:** Cria um novo cartão (card) no Trello com:
  - Nome da tarefa;
  - Descrição detalhada;
  - Data de vencimento (`due_date`);
  - Quadro de destino (`nome_do_quadro`).
- **Ajuste de Fuso Horário (Desafio do Expert):** A API do Trello trabalha internamente com o fuso UTC, o que fazia com que datas sem horário chegassem com um dia a menos na interface local do usuário. A ferramenta implementa a correção automática, adicionando 1 dia (`+ timedelta(days=1)`) à data fornecida, garantindo que o vencimento seja exibido com exatidão no Trello.
- **Suporte a múltiplos quadros:** Caso nenhum quadro seja informado e o usuário possua mais de um board, a ferramenta orienta a escolha do quadro correto.

### 4. `listar_tarefas`
- **Descrição:** Lista as tarefas existentes com seus respectivos detalhes (ID, nome, descrição, vencimento, lista/status e nome do quadro).
- **Filtros flexíveis:**
  - **Por status:** Aceita `'todas'`, `'a fazer'`, `'em andamento'`, `'concluído'` (com ou sem acento, além de sinônimos como `'done'`, `'doing'`, `'to do'`, etc.).
  - **Por quadro:** Permite filtrar tarefas de um quadro específico (`nome_do_quadro`) ou listar tarefas consolidadas de todos os quadros acessíveis.

### 5. `mudar_status_tarefa`
- **Descrição:** Altera o status de uma tarefa movendo o card entre as listas correspondentes no quadro (ex: mover de "A Fazer" para "Em Andamento" ou "Concluído").
- **Tolerância a acentos e variações:** Aceita comandos com acentuação (`concluído`, `concluída`) e variações em português e inglês (`a fazer`, `fazendo`, `em andamento`, `concluido`, `done`, `finalizado`), normalizando os termos antes de pesquisar as listas equivalentes no quadro.
- **Busca inteligente:** Localiza o card pelo nome tanto no quadro informado quanto pesquisando nos quadros disponíveis na conta.

### 6. `remover_tarefa`
- **Descrição:** Remove (exclui permanentemente) um cartão de tarefa do Trello.
- **Finalidade:** Atende à promessa das instruções do agente, permitindo a limpeza de tarefas canceladas ou descartadas.

---

## 🚀 Melhorias Técnicas Implementadas

Em relação à versão inicial do código, foram realizadas as seguintes melhorias:

1. **Correção do offset de data de vencimento (+1 dia):** Implementada a função `ajustar_data()`, que interpreta diversos formatos de entrada (ISO 8601, formato brasileiro `DD/MM/YYYY`, etc.) e compensa o fuso horário UTC do Trello.
2. **Suporte a status acentuados e variações semânticas:** Implementada a função `normalizar_texto()` (remoção de diacríticos e padronização) aliada a dicionários de equivalência (`STATUS_MAP` e `STATUS_LISTAS_EQUIVALENTES`), eliminando o erro de status inválido para termos como `"concluído"`.
3. **Criação da ferramenta `remover_tarefa`:** Implementada a exclusão permanente de cards utilizando o método `card.delete()` da API do Trello.
4. **Tratamento de exceções com `try/except` generalizado:** Todas as ferramentas agora possuem blocos defensivos `try/except Exception as e`, retornando mensagens de erro claras e amigáveis para o usuário e para o modelo, prevenindo quebras de execução inesperadas.
5. **Conexão centralizada com o Trello (`conectar_trello`):** A inicialização repetitiva do `TrelloClient` em cada função foi substituída por uma função única e reutilizável, validando a presença das credenciais necessárias no ambiente.
6. **Gerenciamento de múltiplos quadros:** O quadro hardcoded (`'DIO'`) foi substituído por uma lógica dinâmica capaz de trabalhar com múltiplos quadros, listar quadros disponíveis e solicitar a definição do quadro de trabalho.
7. **Suíte de Testes Automatizados:** Implementados testes unitários cobrindo todas as ferramentas, validação de regras de fuso horário, normalização de status e múltiplos quadros (`tests/test_agent.py`).

---

## ⚙️ Variáveis de Ambiente Necessárias

O arquivo `.env` deve conter as seguintes chaves para a integração com o Trello e o Gemini:

```env
# Credenciais do Trello (Power-Up / Developer API)
TRELLO_API_KEY=sua_api_key_aqui
TRELLO_API_SECRET=seu_api_secret_aqui
TRELLO_TOKEN=seu_token_aqui

# Chave do modelo Google Gemini
GEMINI_API_KEY=sua_gemini_api_key_aqui
```
