"""Fontes oficiais lidas pela varredura."""
from .diario_estado_pr import DiarioEstadoPR
from .diario_municipios_pr import DiarioMunicipiosPR
from .bancas import Bancas
from .dou_inlabs import DouInlabs

FONTES = [DouInlabs, DiarioMunicipiosPR, DiarioEstadoPR, Bancas]
