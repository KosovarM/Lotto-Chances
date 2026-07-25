from lotto.web.app import create_app


def test_index_loads():
    app = create_app()
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"Lotto 6aus49" in response.data


def test_german_language():
    app = create_app()
    client = app.test_client()
    response = client.get("/?lang=de")
    assert response.status_code == 200
    assert b"Statistik" in response.data


def test_latest_tab():
    app = create_app()
    client = app.test_client()
    response = client.get("/?tab=latest")
    assert response.status_code == 200
    assert b"Recent draws" in response.data or b"Letzte Ziehungen" in response.data


def test_latest_tab_german():
    app = create_app()
    client = app.test_client()
    response = client.get("/?tab=latest&lang=de")
    assert response.status_code == 200
    assert b"Letzte Gewinnzahlen" in response.data
    assert b"Letzte Ziehung" in response.data
