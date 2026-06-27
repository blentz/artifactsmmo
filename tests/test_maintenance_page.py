from artifactsmmo_cli.maintenance_page import extract_readable_text
from artifactsmmo_cli.server_unavailable_error import ServerUnavailableError


def test_extracts_title_and_body():
    html = "<html><head><title>Maintenance</title></head><body><p>Back at 5pm</p></body></html>"
    assert extract_readable_text(html) == "Maintenance\nBack at 5pm"


def test_strips_script_and_style():
    html = (
        "<html><head><style>body{color:red}</style></head>"
        "<body><script>var x=1;</script><p>Down for upkeep</p></body></html>"
    )
    assert extract_readable_text(html) == "Down for upkeep"


def test_decodes_entities_and_collapses_whitespace():
    html = "<body><p>Tom   &amp;\n\n  Jerry</p></body>"
    assert extract_readable_text(html) == "Tom & Jerry"


def test_empty_input_returns_empty():
    assert extract_readable_text("") == ""


def test_body_with_only_script_returns_empty():
    assert extract_readable_text("<body><script>noise()</script></body>") == ""


def test_server_unavailable_error_carries_text_and_url():
    err = ServerUnavailableError("Maintenance", url="https://api.example.com/")
    assert err.page_text == "Maintenance"
    assert err.url == "https://api.example.com/"
    assert str(err) == "Maintenance"
    assert isinstance(err, RuntimeError)
