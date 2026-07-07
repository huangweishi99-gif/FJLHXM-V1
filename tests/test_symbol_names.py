from fengji_core.symbol_names import a_stock_display, a_stock_name, domestic_display, futures_display, normalize_a_stock_symbol


def test_normalize_a_stock_symbol_short_codes():
    assert normalize_a_stock_symbol("2475") == "002475"
    assert normalize_a_stock_symbol("988") == "000988"
    assert normalize_a_stock_symbol("600522") == "600522"


def test_a_stock_name_and_display():
    assert a_stock_name("2475") == "立讯精密"
    assert a_stock_name("988") == "华工科技"
    assert a_stock_display("988") == "华工科技(000988)"


def test_futures_display_sa():
    assert futures_display("SA") == "纯碱(SA)"
    assert futures_display("SAUSDT") == "纯碱(SA)"


def test_domestic_display_routes_futures_and_astock():
    assert domestic_display("SA") == "纯碱(SA)"
    assert domestic_display("988") == "华工科技(000988)"

