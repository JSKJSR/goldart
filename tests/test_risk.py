from goldart.services.risk import calculate

def test_calculate_long():
    # Test a LONG trade
    # entry=2000, sl=1950, risk=50 -> dist=50
    # lot = 50 / (50 * 100) = 0.01
    result = calculate(2000.0, 1950.0, "LONG")
    assert result["lot_size"] == 0.01
    assert result["tp"] == 2100.0  # RR 1:2 by default

def test_calculate_short():
    # Test a SHORT trade
    result = calculate(2000.0, 2050.0, "SHORT")
    assert result["lot_size"] == 0.01
    assert result["tp"] == 1900.0

def test_calculate_error():
    # Test error case
    result = calculate(2000.0, 2000.0, "LONG")
    assert "error" in result
