import pytest

from backend_estudiantil.domain.models.trueque import Trueque

pytestmark = pytest.mark.unit


def test_no_se_puede_completar_un_trueque_no_confirmado():
    t = Trueque(id=1, usuario_propone_id=1, usuario_recibe_id=2)
    with pytest.raises(ValueError):
        t.completar()
    assert t.estado == "propuesto"


def test_flujo_valido_propuesto_confirmado_completado():
    t = Trueque(id=1, usuario_propone_id=1, usuario_recibe_id=2)
    t.confirmar()
    t.completar()
    assert t.estado == "completado"


def test_no_se_puede_completar_un_trueque_rechazado():
    t = Trueque(id=1, usuario_propone_id=1, usuario_recibe_id=2)
    t.rechazar()
    with pytest.raises(ValueError):
        t.completar()
