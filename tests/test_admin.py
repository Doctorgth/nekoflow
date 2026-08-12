from src.utils.admin import is_admin

def test_is_admin_returns_bool():
    res = is_admin()
    assert isinstance(res, bool)