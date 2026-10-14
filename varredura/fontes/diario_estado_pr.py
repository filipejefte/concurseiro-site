"""Diário Oficial do Estado do Paraná (DIOE-PR): esboço.

TODO: verificar formato e acesso antes de implementar.
  - Onde ficam as edições (portal do DIOE / Casa Civil) e se há PDF por data ou busca por matéria.
  - robots.txt e termos de uso do portal.
  - Como separar as matérias e qual link oficial usar para cada uma.
Enquanto isso, os concursos de órgãos estaduais do PR só entram se aparecerem em outra fonte.
"""
from .base import Fonte


class DiarioEstadoPR(Fonte):
    nome = "DIOE-PR"

    def listar_atos(self, desde, ate):
        raise NotImplementedError("DIOE-PR ainda não implementado: formato e acesso não verificados (ver TODO no arquivo).")
