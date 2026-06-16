
import pytest
from src.ui.dashboard import _parse_slash_command, _build_strict_slash_query

def test_parse_slash_command():
    # Test Backslash
    assert _parse_slash_command(r"\uid:123") == {"mode": "uid", "value": "123"}
    assert _parse_slash_command(r"\p:John") == {"mode": "person", "value": "John"}
    assert _parse_slash_command(r"\loc:London") == {"mode": "location", "value": "London"}
    assert _parse_slash_command(r"\foo") == {"mode": "tag", "value": "foo"}

    # Test Forward Slash
    assert _parse_slash_command("/uid:123") == {"mode": "uid", "value": "123"}
    assert _parse_slash_command("/person:Doe") == {"mode": "person", "value": "Doe"}
    assert _parse_slash_command("/l:Paris") == {"mode": "location", "value": "Paris"}
    assert _parse_slash_command("/conf:Top Secret") == {"mode": "confidentiality", "value": "Top Secret"}
    assert _parse_slash_command("/genericTag") == {"mode": "tag", "value": "genericTag"}
    
    # Test Implicit
    assert _parse_slash_command("/ABC-12345678-ABCD")["mode"] == "uid"
    assert _parse_slash_command("/pdf")["mode"] == "ext"

def test_build_strict_slash_query_generic_tag():
    cmd = {"mode": "tag", "value": "Finance"}
    source_fields = ["file_name"]
    q = _build_strict_slash_query(cmd, source_fields, {}, 10)
    
    # Verify strict scoping: query should target specific fields, NOT main_content
    str_q = str(q)
    assert "main_content" not in str_q
    assert "ocr_content" not in str_q
    assert "category" in str_q
    assert "department" in str_q
    assert "key_names" in str_q  # Should now search key_names too

def test_build_strict_slash_query_explicit_person():
    cmd = {"mode": "person", "value": "Alice"}
    q = _build_strict_slash_query(cmd, [], {}, 10)
    str_q = str(q)
    
    assert "key_names" in str_q
    assert "location_mentioned" not in str_q
    assert "department" not in str_q

def test_build_strict_slash_query_explicit_location():
    cmd = {"mode": "location", "value": "London"}
    q = _build_strict_slash_query(cmd, [], {}, 10)
    str_q = str(q)
    
    assert "location_mentioned" in str_q
    assert "key_names" not in str_q
