from google.adk.agents.llm_agent import Agent
from trello import TrelloClient
from dotenv import load_dotenv
from datetime import datetime, timedelta
import os
import unicodedata

load_dotenv()

# Credenciais do Trello
API_KEY = os.getenv('TRELLO_API_KEY')
API_SECRET = os.getenv('TRELLO_API_SECRET')
TOKEN = os.getenv('TRELLO_TOKEN')


def conectar_trello() -> TrelloClient:
    """
    Função centralizada para conexão com a API do Trello.
    Garante reuso da inicialização do client em todas as ferramentas.
    """
    api_key = os.getenv('TRELLO_API_KEY') or API_KEY
    api_secret = os.getenv('TRELLO_API_SECRET') or API_SECRET
    token = os.getenv('TRELLO_TOKEN') or TOKEN

    if not api_key or not token:
        raise ValueError("Credenciais do Trello (TRELLO_API_KEY e TRELLO_TOKEN) não configuradas no ambiente (.env).")

    return TrelloClient(
        api_key=api_key,
        api_secret=api_secret,
        token=token
    )


def normalizar_texto(texto: str) -> str:
    """Remove acentos, converte para minúsculas e remove espaços extras."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize('NFKD', str(texto))
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower().strip()


def ajustar_data(due_date: str) -> str:
    """
    Corrige o fuso horário/offset do Trello adicionando 1 dia à data fornecida.
    (Ajuste solicitado pelo Expert da DIO devido à discrepância de fuso horário UTC na API do Trello).
    """
    if not due_date or str(due_date).strip().lower() in ['none', 'null', '']:
        return None

    due_str = str(due_date).strip()
    dt = None

    # Tenta parsing com ISO
    try:
        dt = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
    except Exception:
        pass

    # Tenta formatos comuns brasileiros e internacionais (dia primeiro para barras e traços)
    if dt is None:
        formatos = (
            "%d/%m/%Y", "%d/%m/%Y %H:%M:%S",
            "%Y/%m/%d", "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%d", "%Y-%m-%d %H:%M:%S",
            "%d-%m-%Y", "%d-%m-%Y %H:%M:%S"
        )
        for fmt in formatos:
            try:
                dt = datetime.strptime(due_str, fmt)
                break
            except ValueError:
                continue

    # Tenta parsing com dateutil (dayfirst=True para contexto em português)
    if dt is None:
        try:
            from dateutil import parser
            dt = parser.parse(due_str, dayfirst=True)
        except Exception:
            pass

    if dt is not None:
        dt_ajustada = dt + timedelta(days=1)
        return dt_ajustada.isoformat()

    return due_str


STATUS_MAP = {
    # A Fazer
    "a fazer": "A FAZER",
    "afazer": "A FAZER",
    "fazer": "A FAZER",
    "to do": "A FAZER",
    "todo": "A FAZER",
    "pendente": "A FAZER",
    "pendentes": "A FAZER",
    "backlog": "A FAZER",

    # Em Andamento
    "em andamento": "EM ANDAMENTO",
    "andamento": "EM ANDAMENTO",
    "doing": "EM ANDAMENTO",
    "in progress": "EM ANDAMENTO",
    "fazendo": "EM ANDAMENTO",

    # Concluído
    "concluido": "CONCLUÍDO",
    "concluida": "CONCLUÍDO",
    "concluidos": "CONCLUÍDO",
    "concluidas": "CONCLUÍDO",
    "concluído": "CONCLUÍDO",
    "concluída": "CONCLUÍDO",
    "concluídos": "CONCLUÍDO",
    "concluídas": "CONCLUÍDO",
    "done": "CONCLUÍDO",
    "finalizado": "CONCLUÍDO",
    "finalizada": "CONCLUÍDO",
    "pronto": "CONCLUÍDO",
    "pronta": "CONCLUÍDO",
    "terminado": "CONCLUÍDO",
    "terminada": "CONCLUÍDO",
    "completado": "CONCLUÍDO",
    "completo": "CONCLUÍDO"
}

STATUS_LISTAS_EQUIVALENTES = {
    "A FAZER": ["A FAZER", "TO DO", "TODO", "PENDENTE", "BACKLOG"],
    "EM ANDAMENTO": ["EM ANDAMENTO", "DOING", "IN PROGRESS", "FAZENDO"],
    "CONCLUÍDO": ["CONCLUÍDO", "CONCLUIDO", "DONE", "FINALIZADO", "PRONTO", "TERMINADO"]
}


def obter_quadro(client: TrelloClient, nome_do_quadro: str = None):
    """
    Localiza o quadro desejado no Trello.
    Se nome_do_quadro for fornecido, busca por correspondência exata ou parcial.
    Se não for fornecido e houver apenas 1 quadro, retorna-o.
    Se não for fornecido e houver mais de um quadro, levanta exceção orientando a perguntar ao usuário.
    """
    boards = client.list_boards()
    if not boards:
        raise ValueError("Nenhum quadro (board) encontrado na conta do Trello.")

    if nome_do_quadro:
        nome_norm = normalizar_texto(nome_do_quadro)
        for b in boards:
            if normalizar_texto(b.name) == nome_norm:
                return b
        for b in boards:
            if nome_norm in normalizar_texto(b.name):
                return b
        nomes_disponiveis = ", ".join([f"'{b.name}'" for b in boards])
        raise ValueError(f"Quadro '{nome_do_quadro}' não encontrado. Quadros disponíveis: {nomes_disponiveis}")

    if len(boards) == 1:
        return boards[0]

    nomes_disponiveis = ", ".join([f"'{b.name}'" for b in boards])
    raise ValueError(f"Existe mais de um quadro disponível ({nomes_disponiveis}). Por favor, pergunte ao usuário em qual quadro deseja inserir ou gerenciar a tarefa.")


def get_temporal_context() -> str:
    """Retorna a data e hora atual do sistema formatada."""
    try:
        now = datetime.now()
        return now.strftime('%Y/%m/%d %H:%M:%S')
    except Exception as e:
        return f"❌ Erro ao obter contexto temporal: {str(e)}"


def listar_quadros() -> str:
    """Lista todos os quadros (boards) disponíveis na conta do Trello."""
    try:
        client = conectar_trello()
        boards = client.list_boards()
        if not boards:
            return "Nenhum quadro encontrado na conta do Trello."
        nomes = [b.name for b in boards]
        return f"Quadros disponíveis no Trello: {', '.join(nomes)}"
    except Exception as e:
        return f"❌ Erro ao listar quadros: {str(e)}"


def adicionar_tarefa(nome_da_task: str, descricao_da_task: str = "", due_date: str = None, nome_do_quadro: str = None) -> str:
    """
    Adiciona uma nova tarefa (card) no quadro do Trello especificado.
    Se houver múltiplos quadros e o nome não for fornecido, informa para perguntar ao usuário.
    Aplica a correção de +1 dia na data de vencimento (due_date) para compensar o fuso horário da API.
    """
    try:
        client = conectar_trello()
        board = obter_quadro(client, nome_do_quadro)

        listas = board.list_lists()
        if not listas:
            return f"❌ O quadro '{board.name}' não possui listas."

        # Identifica a lista inicial de entrada ("A Fazer", "To Do", etc.)
        minha_lista = None
        for lista in listas:
            nome_lista_norm = normalizar_texto(lista.name)
            if nome_lista_norm in ["a fazer", "to do", "todo", "backlog", "pendente"]:
                minha_lista = lista
                break

        if not minha_lista:
            minha_lista = listas[0]

        data_ajustada = ajustar_data(due_date) if due_date else "null"

        card = minha_lista.add_card(
            name=nome_da_task,
            desc=descricao_da_task,
            due=data_ajustada if data_ajustada else "null"
        )

        return f"✅ Tarefa '{card.name}' adicionada com sucesso no quadro '{board.name}' (Lista: '{minha_lista.name}')!"
    except Exception as e:
        return f"❌ Erro ao adicionar tarefa: {str(e)}"


def listar_tarefas(status: str = "todas", nome_do_quadro: str = None):
    """
    Lista as tarefas existentes, permitindo filtrar por status ('todas', 'a fazer', 'em andamento', 'concluído' e variações)
    e opcionalmente por quadro (nome_do_quadro).
    """
    try:
        client = conectar_trello()
        boards = client.list_boards()
        if not boards:
            return "Nenhum quadro encontrado na conta do Trello."

        if nome_do_quadro:
            boards_para_listar = [obter_quadro(client, nome_do_quadro)]
        else:
            boards_para_listar = boards

        status_norm = normalizar_texto(status)
        tarefas = []

        for board in boards_para_listar:
            listas = board.list_lists()

            if status_norm in ["todas", "all", ""]:
                listas_filtradas = listas
            else:
                categoria = STATUS_MAP.get(status_norm)
                if categoria:
                    equivalentes = [normalizar_texto(eq) for eq in STATUS_LISTAS_EQUIVALENTES.get(categoria, [])]
                    listas_filtradas = [l for l in listas if normalizar_texto(l.name) in equivalentes]
                else:
                    # Tenta correspondência direta com o nome da lista
                    listas_filtradas = [l for l in listas if normalizar_texto(l.name) == status_norm]
                    if not listas_filtradas:
                        listas_filtradas = listas

            for lista in listas_filtradas:
                cards = lista.list_cards()
                for card in cards:
                    tarefas.append({
                        "id": card.id,
                        "nome": card.name,
                        "descricao": card.desc,
                        "vencimento": card.due,
                        "status": lista.name,
                        "quadro": board.name
                    })

        return tarefas
    except Exception as e:
        return f"❌ Erro ao listar tarefas: {str(e)}"


def mudar_status_tarefa(nome_da_task: str, novo_status: str, nome_do_quadro: str = None) -> str:
    """
    Move uma tarefa para uma nova lista de status (ex: 'a fazer', 'em andamento', 'concluído').
    Aceita variações com e sem acento e localiza o card no quadro especificado ou nos quadros disponíveis.
    """
    try:
        client = conectar_trello()

        status_norm = normalizar_texto(novo_status)
        categoria_padrao = STATUS_MAP.get(status_norm)

        if not categoria_padrao:
            return f"❌ Status inválido: '{novo_status}'. Use variações de: 'a fazer', 'em andamento' ou 'concluído'."

        if nome_do_quadro:
            boards_busca = [obter_quadro(client, nome_do_quadro)]
        else:
            boards_busca = client.list_boards()

        card_encontrado = None
        lista_origem = None
        board_encontrado = None

        for board in boards_busca:
            for lista in board.list_lists():
                cards = lista.list_cards()
                card = next((c for c in cards if c.name.lower() == nome_da_task.lower()), None)
                if card:
                    card_encontrado = card
                    lista_origem = lista
                    board_encontrado = board
                    break
            if card_encontrado:
                break

        if not card_encontrado:
            return f"❌ Tarefa '{nome_da_task}' não encontrada."

        # Identifica a lista de destino no board encontrado
        listas_board = board_encontrado.list_lists()
        equivalentes = [normalizar_texto(eq) for eq in STATUS_LISTAS_EQUIVALENTES.get(categoria_padrao, [categoria_padrao])]

        lista_destino = None
        for lista in listas_board:
            if normalizar_texto(lista.name) in equivalentes:
                lista_destino = lista
                break

        if not lista_destino:
            return f"❌ Lista correspondente a '{novo_status}' não encontrada no quadro '{board_encontrado.name}'."

        card_encontrado.change_list(lista_destino.id)
        return f"✅ '{card_encontrado.name}' no quadro '{board_encontrado.name}': {lista_origem.name} → {lista_destino.name}"
    except Exception as e:
        return f"❌ Erro ao mudar status da tarefa: {str(e)}"


def remover_tarefa(nome_da_task: str, nome_do_quadro: str = None) -> str:
    """
    Remove (exclui permanentemente) uma tarefa do Trello pelo nome.
    Se especificado, busca apenas no quadro indicado; caso contrário, busca nos quadros disponíveis.
    """
    try:
        client = conectar_trello()

        if nome_do_quadro:
            boards_busca = [obter_quadro(client, nome_do_quadro)]
        else:
            boards_busca = client.list_boards()

        card_encontrado = None
        board_encontrado = None

        for board in boards_busca:
            for lista in board.list_lists():
                cards = lista.list_cards()
                card = next((c for c in cards if c.name.lower() == nome_da_task.lower()), None)
                if card:
                    card_encontrado = card
                    board_encontrado = board
                    break
            if card_encontrado:
                break

        if not card_encontrado:
            return f"❌ Tarefa '{nome_da_task}' não encontrada para remoção."

        card_encontrado.delete()
        return f"✅ Tarefa '{card_encontrado.name}' removida com sucesso do quadro '{board_encontrado.name}'!"
    except Exception as e:
        return f"❌ Erro ao remover tarefa: {str(e)}"


root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='Agente Inteligente de Organização de Tarefas no Trello',
    instruction="""
        Você é um agente de organização de tarefas conectado ao Trello.     
        Sua função é gerenciar tarefas (cards) nos quadros (boards) do Trello do usuário.
        
        Diretrizes de conversação:
        1. Sempre inicie a conversa perguntando quais são as tarefas do dia e informe a data e hora atual obtidas pela ferramenta get_temporal_context.
        2. Vá perguntando se tem mais alguma tarefa, até que o usuário indique que finalizou.
        3. Suporte a múltiplos quadros: Sempre pergunte ao usuário em qual quadro a tarefa deve ser adicionada. Você pode consultar os quadros disponíveis no Trello usando a ferramenta listar_quadros e apresentá-los como opção.
        4. Sempre retorne respostas claras, confirmando o sucesso ou explicando eventuais erros das operações.
        
        Suas funções disponíveis:
        1. listar_quadros: Lista todos os quadros (boards) disponíveis na conta do Trello.
        2. adicionar_tarefa: Adiciona nova tarefa com nome, descrição, data de vencimento e quadro de destino (com compensação automática do fuso do Trello).
        3. listar_tarefas: Lista tarefas filtrando por status ('todas', 'a fazer', 'em andamento', 'concluído') e opcionalmente por quadro.
        4. mudar_status_tarefa: Atualiza o status da tarefa para 'a fazer', 'em andamento' ou 'concluído' (aceitando acentuações e variações).
        5. remover_tarefa: Remove/exclui uma tarefa do quadro no Trello.
        6. get_temporal_context: Informa a data e hora atual para contextualizar o planejamento do dia.
    """,
    tools=[
        get_temporal_context,
        listar_quadros,
        adicionar_tarefa,
        listar_tarefas,
        mudar_status_tarefa,
        remover_tarefa
    ],
)
