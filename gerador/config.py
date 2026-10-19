"""Configuração do site: site.toml na raiz (ver os comentários lá)."""
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "site.toml"


@dataclass
class Config:
    site_url: str
    base_path: str = "/"
    indexar: bool = False
    canal_whatsapp: str = ""
    canal_telegram: str = ""
    kit_form_id: str = ""
    email_contato: str = ""
    responsavel: str = ""
    razao_social: str = ""
    cnpj: str = ""
    quem_faz: str = ""
    foro: str = ""
    cloudflare_analytics_token: str = ""
    adsense_client: str = ""
    adsense_slot: str = ""
    afiliados: list = field(default_factory=list)

    def url(self, caminho="/"):
        """Endereço interno com o base_path: url("/concursos/") -> "/concurseiro-site/concursos/"."""
        return self.base_path + caminho.lstrip("/")

    def pendentes(self):
        """Campos que o site mostra como [A PREENCHER] enquanto estiverem vazios."""
        return [nome for nome in ("responsavel", "email_contato", "quem_faz", "foro") if not getattr(self, nome)]

    def absoluta(self, caminho="/"):
        """Endereço completo, para canonical, sitemap, Open Graph e os resumos dos canais."""
        return self.site_url + "/" + caminho.lstrip("/")


def ler(caminho=ARQUIVO, **trocas):
    """Lê o site.toml. `trocas` sobrescreve campos (usado nos testes e no --indexar)."""
    with open(caminho, "rb") as f:
        bruto = tomllib.load(f)
    bruto.update({k: v for k, v in trocas.items() if v is not None})
    conhecidos = set(Config.__dataclass_fields__)
    desconhecidos = set(bruto) - conhecidos
    if desconhecidos:
        raise SystemExit(f"site.toml: campo desconhecido: {', '.join(sorted(desconhecidos))}")
    c = Config(**bruto)
    c.site_url = c.site_url.rstrip("/")
    c.base_path = "/" + c.base_path.strip("/") + "/" if c.base_path.strip("/") else "/"
    if not c.site_url.startswith("https://") and not c.site_url.startswith("http://localhost"):
        raise SystemExit("site.toml: site_url precisa começar com https://")
    if not c.site_url.endswith(c.base_path.rstrip("/")):
        raise SystemExit(f"site.toml: site_url ({c.site_url}) precisa terminar com o base_path ({c.base_path})")
    for nome in ("canal_whatsapp", "canal_telegram"):
        valor = getattr(c, nome)
        if valor and not valor.startswith("https://"):
            raise SystemExit(f"site.toml: {nome} precisa ser uma URL https:// (ou vazio)")
    if c.kit_form_id and not c.kit_form_id.isdigit():
        raise SystemExit("site.toml: kit_form_id é só o número do formulário do Kit")
    if c.cnpj and not re.fullmatch(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}", c.cnpj):
        raise SystemExit("site.toml: cnpj no formato 00.000.000/0000-00 (ou vazio)")
    if re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", c.responsavel):
        raise SystemExit("site.toml: responsavel é só o nome; não publique CPF")
    for a in c.afiliados:
        if not (a.get("nome") and str(a.get("url", "")).startswith("https://") and (a.get("area") or a.get("banca"))):
            raise SystemExit("site.toml: cada [[afiliados]] precisa de nome, url https:// e area ou banca")
    return c
