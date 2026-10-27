from .base import ErrorAlta, Plataforma, ProveedorEnSitio, ResultadoAlta
from .fad import PlataformaFAD

# nombre de plataforma (config.MARKETPLACES[...]["plataforma"]) -> clase
PLATAFORMAS = {
    "fad": PlataformaFAD,
}
