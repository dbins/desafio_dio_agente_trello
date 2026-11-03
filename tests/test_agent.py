import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
from agenttaskmanager.agent import (
    conectar_trello,
    normalizar_texto,
    ajustar_data,
    obter_quadro,
    listar_quadros,
    adicionar_tarefa,
    listar_tarefas,
    mudar_status_tarefa,
    remover_tarefa,
    get_temporal_context,
    STATUS_MAP,
    root_agent
)


class TestAgentTaskManager(unittest.TestCase):

    def test_normalizar_texto(self):
        self.assertEqual(normalizar_texto("Concluído"), "concluido")
        self.assertEqual(normalizar_texto("  A Fazer  "), "a fazer")
        self.assertEqual(normalizar_texto("EM ANDAMENTO"), "em andamento")
        self.assertEqual(normalizar_texto(""), "")
        self.assertEqual(normalizar_texto(None), "")

    def test_ajustar_data_offset_expert(self):
        # Data no formato ISO (YYYY-MM-DD): deve avançar 1 dia para corrigir fuso UTC do Trello
        self.assertEqual(ajustar_data("2026-11-03"), "2026-11-04T00:00:00")
        
        # Data com horário
        self.assertEqual(ajustar_data("2026-11-03 14:30:00"), "2026-11-04T14:30:00")

        # Data em formato brasileiro DD/MM/YYYY
        self.assertEqual(ajustar_data("03/11/2026"), "2026-11-04T00:00:00")

        # Nulos ou vazios devem retornar None
        self.assertIsNone(ajustar_data(None))
        self.assertIsNone(ajustar_data(""))
        self.assertIsNone(ajustar_data("null"))

    def test_status_map_variations(self):
        # Deve aceitar concluído com acento e variações
        self.assertEqual(STATUS_MAP.get(normalizar_texto("concluído")), "CONCLUÍDO")
        self.assertEqual(STATUS_MAP.get(normalizar_texto("concluido")), "CONCLUÍDO")
        self.assertEqual(STATUS_MAP.get(normalizar_texto("done")), "CONCLUÍDO")
        self.assertEqual(STATUS_MAP.get(normalizar_texto("finalizado")), "CONCLUÍDO")
        
        # A fazer e variações
        self.assertEqual(STATUS_MAP.get(normalizar_texto("a fazer")), "A FAZER")
        self.assertEqual(STATUS_MAP.get(normalizar_texto("to do")), "A FAZER")
        
        # Em andamento e variações
        self.assertEqual(STATUS_MAP.get(normalizar_texto("em andamento")), "EM ANDAMENTO")
        self.assertEqual(STATUS_MAP.get(normalizar_texto("doing")), "EM ANDAMENTO")

    @patch("agenttaskmanager.agent.os.getenv")
    def test_conectar_trello_credenciais_faltando(self, mock_getenv):
        mock_getenv.side_effect = lambda key: None
        with patch("agenttaskmanager.agent.API_KEY", None), patch("agenttaskmanager.agent.TOKEN", None):
            with self.assertRaises(ValueError):
                conectar_trello()

    @patch("agenttaskmanager.agent.TrelloClient")
    @patch("agenttaskmanager.agent.os.getenv")
    def test_conectar_trello_sucesso(self, mock_getenv, mock_client_cls):
        mock_getenv.side_effect = lambda key: "dummy_value" if "TRELLO" in key else None
        client = conectar_trello()
        self.assertIsNotNone(client)
        mock_client_cls.assert_called_once()

    def test_obter_quadro(self):
        mock_client = MagicMock()
        board1 = MagicMock(name="board1")
        board1.name = "DIO"
        board2 = MagicMock(name="board2")
        board2.name = "Pessoal"
        mock_client.list_boards.return_value = [board1, board2]

        # Busca pelo nome correto (com case-insensitive)
        quadro = obter_quadro(mock_client, "dio")
        self.assertEqual(quadro.name, "DIO")

        quadro_pessoal = obter_quadro(mock_client, "pessoal")
        self.assertEqual(quadro_pessoal.name, "Pessoal")

        # Quadro inexistente levanta erro informando os disponíveis
        with self.assertRaises(ValueError) as ctx:
            obter_quadro(mock_client, "Inexistente")
        self.assertIn("Quadro 'Inexistente' não encontrado", str(ctx.exception))

        # Mais de um quadro sem especificar nome levanta erro para perguntar ao usuário
        with self.assertRaises(ValueError) as ctx_multiple:
            obter_quadro(mock_client, None)
        self.assertIn("Existe mais de um quadro disponível", str(ctx_multiple.exception))

        # Se houver apenas 1 quadro, retorna-o diretamente se nenhum nome for fornecido
        mock_client.list_boards.return_value = [board1]
        quadro_unico = obter_quadro(mock_client, None)
        self.assertEqual(quadro_unico.name, "DIO")

        # Se não houver nenhum quadro
        mock_client.list_boards.return_value = []
        with self.assertRaises(ValueError) as ctx_empty:
            obter_quadro(mock_client, None)
        self.assertIn("Nenhum quadro (board) encontrado", str(ctx_empty.exception))

    @patch("agenttaskmanager.agent.conectar_trello")
    def test_listar_quadros(self, mock_conectar):
        mock_client = MagicMock()
        board1 = MagicMock()
        board1.name = "DIO"
        board2 = MagicMock()
        board2.name = "Estudos"
        mock_client.list_boards.return_value = [board1, board2]
        mock_conectar.return_value = mock_client

        resultado = listar_quadros()
        self.assertIn("DIO", resultado)
        self.assertIn("Estudos", resultado)

    @patch("agenttaskmanager.agent.conectar_trello")
    def test_listar_quadros_erro(self, mock_conectar):
        mock_conectar.side_effect = Exception("Falha de rede")
        res = listar_quadros()
        self.assertIn("❌ Erro ao listar quadros: Falha de rede", res)

    @patch("agenttaskmanager.agent.conectar_trello")
    def test_adicionar_tarefa_sucesso(self, mock_conectar):
        mock_client = MagicMock()
        mock_board = MagicMock()
        mock_board.name = "DIO"
        mock_lista = MagicMock()
        mock_lista.name = "A Fazer"
        mock_card = MagicMock()
        mock_card.name = "Estudar Gemini"
        mock_lista.add_card.return_value = mock_card
        mock_board.list_lists.return_value = [mock_lista]
        mock_client.list_boards.return_value = [mock_board]
        mock_conectar.return_value = mock_client

        # Adicionar tarefa passando data
        res = adicionar_tarefa(
            nome_da_task="Estudar Gemini",
            descricao_da_task="Aprender sobre ADK",
            due_date="2026-11-03",
            nome_do_quadro="DIO"
        )
        self.assertIn("✅ Tarefa 'Estudar Gemini' adicionada com sucesso", res)
        # Verifica se add_card foi chamado com data corrigida (+1 dia)
        mock_lista.add_card.assert_called_once_with(
            name="Estudar Gemini",
            desc="Aprender sobre ADK",
            due="2026-11-04T00:00:00"
        )

    @patch("agenttaskmanager.agent.conectar_trello")
    def test_adicionar_tarefa_sem_data(self, mock_conectar):
        mock_client = MagicMock()
        mock_board = MagicMock()
        mock_board.name = "DIO"
        mock_lista = MagicMock()
        mock_lista.name = "A Fazer"
        mock_card = MagicMock()
        mock_card.name = "Sem Data"
        mock_lista.add_card.return_value = mock_card
        mock_board.list_lists.return_value = [mock_lista]
        mock_client.list_boards.return_value = [mock_board]
        mock_conectar.return_value = mock_client

        res = adicionar_tarefa(nome_da_task="Sem Data", nome_do_quadro="DIO")
        self.assertIn("✅ Tarefa 'Sem Data' adicionada com sucesso", res)
        mock_lista.add_card.assert_called_once_with(
            name="Sem Data",
            desc="",
            due="null"
        )

    @patch("agenttaskmanager.agent.conectar_trello")
    def test_adicionar_tarefa_erro_multiplos_quadros_sem_especificar(self, mock_conectar):
        mock_client = MagicMock()
        board1 = MagicMock()
        board1.name = "DIO"
        board2 = MagicMock()
        board2.name = "Trabalho"
        mock_client.list_boards.return_value = [board1, board2]
        mock_conectar.return_value = mock_client

        res = adicionar_tarefa(nome_da_task="Tarefa Genérica")
        self.assertIn("❌ Erro ao adicionar tarefa", res)
        self.assertIn("Existe mais de um quadro disponível", res)

    @patch("agenttaskmanager.agent.conectar_trello")
    def test_listar_tarefas_filtro_concluido_com_acento(self, mock_conectar):
        mock_client = MagicMock()
        mock_board = MagicMock()
        mock_board.name = "DIO"
        
        lista_fazer = MagicMock()
        lista_fazer.name = "A Fazer"
        card1 = MagicMock()
        card1.id = "1"
        card1.name = "Tarefa 1"
        card1.desc = "Desc 1"
        card1.due = None
        lista_fazer.list_cards.return_value = [card1]

        lista_concluido = MagicMock()
        lista_concluido.name = "Concluído"
        card2 = MagicMock()
        card2.id = "2"
        card2.name = "Tarefa 2 Concluída"
        card2.desc = "Desc 2"
        card2.due = "2026-11-04T00:00:00"
        lista_concluido.list_cards.return_value = [card2]

        mock_board.list_lists.return_value = [lista_fazer, lista_concluido]
        mock_client.list_boards.return_value = [mock_board]
        mock_conectar.return_value = mock_client

        # Filtrar usando "concluído" com acento
        tarefas = listar_tarefas(status="concluído", nome_do_quadro="DIO")
        self.assertEqual(len(tarefas), 1)
        self.assertEqual(tarefas[0]["nome"], "Tarefa 2 Concluída")
        self.assertEqual(tarefas[0]["status"], "Concluído")
        self.assertEqual(tarefas[0]["quadro"], "DIO")

    @patch("agenttaskmanager.agent.conectar_trello")
    def test_listar_tarefas_todos_quadros(self, mock_conectar):
        mock_client = MagicMock()
        
        board1 = MagicMock()
        board1.name = "DIO"
        l1 = MagicMock()
        l1.name = "A Fazer"
        c1 = MagicMock()
        c1.id = "c1"
        c1.name = "DIO Task"
        c1.desc = ""
        c1.due = None
        l1.list_cards.return_value = [c1]
        board1.list_lists.return_value = [l1]

        board2 = MagicMock()
        board2.name = "Pessoal"
        l2 = MagicMock()
        l2.name = "A Fazer"
        c2 = MagicMock()
        c2.id = "c2"
        c2.name = "Personal Task"
        c2.desc = ""
        c2.due = None
        l2.list_cards.return_value = [c2]
        board2.list_lists.return_value = [l2]

        mock_client.list_boards.return_value = [board1, board2]
        mock_conectar.return_value = mock_client

        tarefas = listar_tarefas()
        self.assertEqual(len(tarefas), 2)
        quadros_retornados = {t["quadro"] for t in tarefas}
        self.assertEqual(quadros_retornados, {"DIO", "Pessoal"})

    @patch("agenttaskmanager.agent.conectar_trello")
    def test_listar_tarefas_erro(self, mock_conectar):
        mock_conectar.side_effect = Exception("Conexão expirada")
        res = listar_tarefas()
        self.assertIn("❌ Erro ao listar tarefas: Conexão expirada", res)

    @patch("agenttaskmanager.agent.conectar_trello")
    def test_mudar_status_tarefa_com_acento(self, mock_conectar):
        mock_client = MagicMock()
        mock_board = MagicMock()
        mock_board.name = "DIO"

        lista_fazer = MagicMock()
        lista_fazer.name = "A Fazer"
        card = MagicMock()
        card.name = "Estudar Python"
        lista_fazer.list_cards.return_value = [card]

        lista_concluido = MagicMock()
        lista_concluido.name = "Concluído"
        lista_concluido.id = "list_concluido_id"
        lista_concluido.list_cards.return_value = []

        mock_board.list_lists.return_value = [lista_fazer, lista_concluido]
        mock_client.list_boards.return_value = [mock_board]
        mock_conectar.return_value = mock_client

        res = mudar_status_tarefa(
            nome_da_task="Estudar Python",
            novo_status="concluído",
            nome_do_quadro="DIO"
        )
        self.assertIn("✅", res)
        self.assertIn("A Fazer → Concluído", res)
        card.change_list.assert_called_once_with("list_concluido_id")

    @patch("agenttaskmanager.agent.conectar_trello")
    def test_mudar_status_tarefa_status_invalido(self, mock_conectar):
        res = mudar_status_tarefa("Tarefa", "status_inexistente_xyz")
        self.assertIn("❌ Status inválido", res)

    @patch("agenttaskmanager.agent.conectar_trello")
    def test_mudar_status_tarefa_nao_encontrada(self, mock_conectar):
        mock_client = MagicMock()
        mock_board = MagicMock()
        mock_board.name = "DIO"
        lista = MagicMock()
        lista.list_cards.return_value = []
        mock_board.list_lists.return_value = [lista]
        mock_client.list_boards.return_value = [mock_board]
        mock_conectar.return_value = mock_client

        res = mudar_status_tarefa("Tarefa Inexistente", "concluído")
        self.assertIn("❌ Tarefa 'Tarefa Inexistente' não encontrada", res)

    @patch("agenttaskmanager.agent.conectar_trello")
    def test_remover_tarefa(self, mock_conectar):
        mock_client = MagicMock()
        mock_board = MagicMock()
        mock_board.name = "DIO"

        lista = MagicMock()
        lista.name = "A Fazer"
        card = MagicMock()
        card.name = "Tarefa para Deletar"
        lista.list_cards.return_value = [card]

        mock_board.list_lists.return_value = [lista]
        mock_client.list_boards.return_value = [mock_board]
        mock_conectar.return_value = mock_client

        res = remover_tarefa("Tarefa para Deletar", nome_do_quadro="DIO")
        self.assertIn("✅ Tarefa 'Tarefa para Deletar' removida com sucesso", res)
        card.delete.assert_called_once()

    @patch("agenttaskmanager.agent.conectar_trello")
    def test_remover_tarefa_inexistente(self, mock_conectar):
        mock_client = MagicMock()
        mock_board = MagicMock()
        mock_board.name = "DIO"

        lista = MagicMock()
        lista.list_cards.return_value = []
        mock_board.list_lists.return_value = [lista]
        mock_client.list_boards.return_value = [mock_board]
        mock_conectar.return_value = mock_client

        res = remover_tarefa("Tarefa Fantasma", nome_do_quadro="DIO")
        self.assertIn("❌ Tarefa 'Tarefa Fantasma' não encontrada para remoção", res)

    @patch("agenttaskmanager.agent.conectar_trello")
    def test_remover_tarefa_erro(self, mock_conectar):
        mock_conectar.side_effect = Exception("Erro de permissão no Trello")
        res = remover_tarefa("Tarefa", nome_do_quadro="DIO")
        self.assertIn("❌ Erro ao remover tarefa: Erro de permissão no Trello", res)

    def test_get_temporal_context(self):
        ctx = get_temporal_context()
        self.assertIsInstance(ctx, str)
        self.assertIn("/", ctx)
        self.assertIn(":", ctx)

    def test_root_agent_tools(self):
        tool_names = [t.__name__ for t in root_agent.tools]
        self.assertIn("get_temporal_context", tool_names)
        self.assertIn("listar_quadros", tool_names)
        self.assertIn("adicionar_tarefa", tool_names)
        self.assertIn("listar_tarefas", tool_names)
        self.assertIn("mudar_status_tarefa", tool_names)
        self.assertIn("remover_tarefa", tool_names)


if __name__ == "__main__":
    unittest.main()
