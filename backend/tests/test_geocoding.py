"""
Тесты app/geocoding.py на моках httpx — реальный ключ/сеть не нужны.
Как только появится настоящий ключ, эти тесты продолжат работать (мок
подменяет транспорт, а не логику), плюс можно будет вручную дёрнуть
geocode_address() с реальным YANDEX_GEOCODER_API_KEY в окружении.
"""
import httpx
import pytest

from app import geocoding


YANDEX_OK_RESPONSE = {
    "response": {
        "GeoObjectCollection": {
            "featureMember": [
                {
                    "GeoObject": {
                        "Point": {"pos": "37.617698 55.755864"}  # Москва: lon lat
                    }
                }
            ]
        }
    }
}

YANDEX_EMPTY_RESPONSE = {
    "response": {"GeoObjectCollection": {"featureMember": []}}
}


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    """Каждый тест сам решает, задан ли ключ, и получает чистый кэш/клиент."""
    monkeypatch.delenv("YANDEX_GEOCODER_API_KEY", raising=False)
    geocoding.geocode_address.cache_clear()
    yield
    geocoding.geocode_address.cache_clear()


def _mock_client(json_body: dict, status_code: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=json_body)

    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def test_not_configured_without_api_key():
    assert geocoding.is_configured() is False
    assert geocoding.geocode_address("г. Москва, Кремль") is None


def test_empty_address_returns_none(monkeypatch):
    monkeypatch.setenv("YANDEX_GEOCODER_API_KEY", "test-key")
    assert geocoding.geocode_address("") is None
    assert geocoding.geocode_address("   ") is None


def test_successful_geocode(monkeypatch):
    monkeypatch.setenv("YANDEX_GEOCODER_API_KEY", "test-key")
    geocoding.set_client(_mock_client(YANDEX_OK_RESPONSE))

    coords = geocoding.geocode_address("г. Москва, Кремль")
    assert coords is not None
    assert coords.широта == pytest.approx(55.755864)
    assert coords.долгота == pytest.approx(37.617698)


def test_address_not_found_returns_none(monkeypatch):
    monkeypatch.setenv("YANDEX_GEOCODER_API_KEY", "test-key")
    geocoding.set_client(_mock_client(YANDEX_EMPTY_RESPONSE))

    assert geocoding.geocode_address("абракадабра несуществующий адрес") is None


def test_malformed_response_raises_geocoder_error(monkeypatch):
    monkeypatch.setenv("YANDEX_GEOCODER_API_KEY", "test-key")
    geocoding.set_client(_mock_client({"unexpected": "shape"}))

    with pytest.raises(geocoding.GeocoderError):
        geocoding.geocode_address("г. Москва, Кремль")


def test_http_error_raises_geocoder_error(monkeypatch):
    monkeypatch.setenv("YANDEX_GEOCODER_API_KEY", "test-key")
    geocoding.set_client(_mock_client({"error": "forbidden"}, status_code=403))

    with pytest.raises(geocoding.GeocoderError):
        geocoding.geocode_address("г. Москва, Кремль")


def test_geocode_many_isolates_errors(monkeypatch):
    """Один плохой адрес не должен обрушивать геокодинг остальных."""
    monkeypatch.setenv("YANDEX_GEOCODER_API_KEY", "test-key")

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json=YANDEX_OK_RESPONSE)

    geocoding.set_client(httpx.Client(transport=httpx.MockTransport(handler)))

    result = geocoding.geocode_many(["плохой адрес", "г. Москва, Кремль"])
    assert result["плохой адрес"] is None
    assert result["г. Москва, Кремль"] is not None


def test_haversine_zero_for_same_point():
    a = geocoding.Координаты(широта=55.75, долгота=37.61)
    assert geocoding.haversine_km(a, a) == pytest.approx(0.0, abs=1e-6)


def test_haversine_moscow_to_spb_roughly_correct():
    moscow = geocoding.Координаты(широта=55.755864, долгота=37.617698)
    spb = geocoding.Координаты(широта=59.938784, долгота=30.314997)
    dist = geocoding.haversine_km(moscow, spb)
    # По прямой Москва-СПб ~ 635 км; допускаем разумный допуск
    assert 600 <= dist <= 670
