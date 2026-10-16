"""Diário Oficial do Estado do Paraná (DIOE-PR): ainda não implementado.

Verificação de 16/10/2026 (prompt 01 do lançamento): não foi possível checar o formato nem o acesso.
A sessão rodou num contêiner na nuvem cuja rede bloqueia os domínios .pr.gov.br, e a busca na web não
trouxe a estrutura atual das edições. O que se sabe por fontes do próprio governo do PR:
  - a consulta pública do DIOE é gratuita e online, por caderno, período ou número da edição, e por
    palavra-chave dentro de um intervalo de até 6 meses;
  - a Casa Civil contratou uma plataforma nova de publicação, então endereços antigos podem ter mudado.

Para implementar (no notebook do Filipe, com rede):
  1. Abrir o portal do DIOE e achar a consulta pública: há PDF por data e caderno (Executivo) ou página por matéria?
  2. Ler o robots.txt e os termos de uso do portal. Se proibirem leitura automática, não implementar.
  3. Achar o link estável de cada matéria (ou da página do PDF) para usar como url do ato.
  4. Escrever listar_atos(desde, ate) como na AMP: um ato por matéria, com fonte="DIOE-PR", e testes com um
     trecho real em tests/test_varredura.py (como test_materias_da_amp).
Enquanto isso, concurso de órgão estadual do PR só entra se aparecer em outra fonte oficial lida.
"""
from .base import Fonte


class DiarioEstadoPR(Fonte):
    nome = "DIOE-PR"

    def listar_atos(self, desde, ate):
        raise NotImplementedError("DIOE-PR ainda não implementado: formato e acesso não verificados (ver o arquivo).")
