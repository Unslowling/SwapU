import pytest
from fastapi import HTTPException

from backend_estudiantil.adapters.security.google_oauth2_authenticator import (
    GoogleOAuth2Authenticator,
)
from backend_estudiantil.adapters.security.facebook_oauth2_authenticator import (
    FacebookOAuth2Authenticator,
)
from backend_estudiantil.config.settings import settings

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("authenticator", "client_id_setting", "client_secret_setting", "provider"),
    [
        (
            GoogleOAuth2Authenticator(),
            "GOOGLE_CLIENT_ID",
            "GOOGLE_CLIENT_SECRET",
            "Google",
        ),
        (
            FacebookOAuth2Authenticator(),
            "FACEBOOK_CLIENT_ID",
            "FACEBOOK_CLIENT_SECRET",
            "Facebook",
        ),
    ],
)
async def test_social_login_requires_provider_credentials(
    monkeypatch, authenticator, client_id_setting, client_secret_setting, provider
):
    monkeypatch.setattr(settings, client_id_setting, "")
    monkeypatch.setattr(settings, client_secret_setting, "")

    with pytest.raises(HTTPException) as error:
        await authenticator.get_authorization_url()

    assert error.value.status_code == 503
    assert f"Inicio con {provider} no configurado" in error.value.detail
