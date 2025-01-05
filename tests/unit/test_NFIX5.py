import pytest
from unittest.mock import MagicMock
from datetime import datetime
from NostalgiaForInfinityX5 import NostalgiaForInfinityX5


@pytest.fixture
def mock_config(tmp_path):
  class RunModeMock:
    def __init__(self, value):
      self.value = value

  return {
    "exchange": {
      "name": "binance",
      "ccxt_config": {
        "apiKey": "dummy_key",
        "secret": "dummy_secret",
        "password": None,
      },
      "pair_whitelist": ["BTC/USDT"],
      "pair_blacklist": [],
    },
    "stake_currency": "USDT",
    "stake_amount": 10,
    "dry_run": True,
    "timeframe": "5m",
    "max_open_trades": 10,
    "user_data_dir": tmp_path,  # Use pytest's temporary directory
    "runmode": RunModeMock("backtest"),  # Simulate the execution mode
  }


# Define a mock trade object
class MockTrade:
  def __init__(self, is_short, enter_tag, fee_open=0.001, fee_close=0.001):
    self.is_short = is_short
    self.enter_tag = enter_tag
    self.open_rate = 100.0
    self.max_rate = 110.0
    self.min_rate = 90.0
    self.entry_side = "buy"
    self.exit_side = "sell"
    self.fee_open = fee_open
    self.fee_close = fee_close

  def select_filled_orders(self, side):
    # Simulate returning an empty list of filled orders for the test
    return [
      MagicMock(average=100.0, amount=1.0),  # Example filled order
    ]


@pytest.mark.parametrize(
  "trade, expected_function",
  [
    # Rebuy and grind only tags
    (MockTrade(False, "61"), "long_rebuy_adjust_trade_position"),  # Long rebuy tag
    (MockTrade(False, "120"), "long_grind_adjust_trade_position"),  # Long grind tag
    # Other tags
    (MockTrade(True, "620"), "short_grind_adjust_trade_position"),  # Short grind tag
    (MockTrade(False, "161"), "long_grind_adjust_trade_position"),  # Long derisk tag
    (MockTrade(False, "6"), "long_grind_adjust_trade_position"),  # Long normal tag
    (MockTrade(False, "81"), "long_grind_adjust_trade_position"),  # Long high profit tag
    (MockTrade(False, "41"), "long_grind_adjust_trade_position"),  # Long quick tag
    (MockTrade(False, "101"), "long_grind_adjust_trade_position"),  # Long rapid tag
    (MockTrade(False, "141"), "long_grind_adjust_trade_position"),  # Long top coins tag
    (MockTrade(False, "999"), "long_grind_adjust_trade_position"),  # Long unknown tag
    # Rebuy + grind tags
    (MockTrade(False, "61 120"), "long_rebuy_adjust_trade_position"),  # Long rebuy + long grind tags
    (MockTrade(False, "120 61"), "long_rebuy_adjust_trade_position"),  # Long grind + long rebuy tags
    # (Rebuy or grind) + other tags
    (MockTrade(False, "120 6"), "long_grind_adjust_trade_position"),  # Long grind + long normal tag
    (MockTrade(False, "61 6"), "long_grind_adjust_trade_position"),  # Long rebuy + long normal tag
    # No tags!
    (MockTrade(False, ""), "long_rebuy_adjust_trade_position"),  # Empty enter_tags
  ],
)
def test_adjust_trade_position(mock_config, mocker, trade, expected_function):
  """Test that adjust_trade_position calls the correct function."""
  strategy = NostalgiaForInfinityX5(mock_config)
  strategy.position_adjustment_enable = True

  # Mock adjustment functions
  strategy.long_rebuy_adjust_trade_position = mocker.MagicMock()
  strategy.long_grind_adjust_trade_position = mocker.MagicMock()
  strategy.short_grind_adjust_trade_position = mocker.MagicMock()

  # Derive enter_tags from trade.enter_tag
  enter_tags = trade.enter_tag.split()

  # Call adjust_trade_position
  strategy.adjust_trade_position(
    trade,
    current_time=None,
    current_rate=0.0,
    current_profit=0.0,
    min_stake=None,
    max_stake=10.0,
    current_entry_rate=0.0,
    current_exit_rate=0.0,
    current_entry_profit=0.0,
    current_exit_profit=0.0,
  )

  # Verify correct function call
  if expected_function:
    getattr(strategy, expected_function).assert_called_once_with(
      trade,
      enter_tags,
      None,
      0.0,
      0.0,
      None,
      10.0,
      0.0,
      0.0,
      0.0,
      0.0,
    )
  else:
    called_functions = []
    for func_name, func in [
      ("long_rebuy_adjust_trade_position", strategy.long_rebuy_adjust_trade_position),
      ("long_grind_adjust_trade_position", strategy.long_grind_adjust_trade_position),
      ("short_grind_adjust_trade_position", strategy.short_grind_adjust_trade_position),
    ]:
      if func.called:
        called_functions.append(f"{func_name} called with: {func.call_args_list}")

    if called_functions:
      pytest.fail(f"Unexpected function calls: {called_functions}")


@pytest.mark.parametrize(
  "trade, expected_function",
  [
    (MockTrade(False, "1"), "long_exit_normal"),  # Long normal mode
    (MockTrade(False, "21"), "long_exit_pump"),   # Long pump mode
    (MockTrade(False, "41"), "long_exit_quick"),  # Long quick mode
    (MockTrade(True, "500"), "short_exit_normal"),  # Short normal mode
    (MockTrade(True, "521"), "short_exit_pump"),  # Short pump mode
    (MockTrade(False, "999"), "long_exit_normal"),  # Unknown tag, long normal mode
  ],
)
def test_custom_exit_calls_correct_function(mock_config, mocker, trade, expected_function):
  """Test to validate that custom_exit calls the correct exit function."""
  # Instantiate the real strategy
  strategy = NostalgiaForInfinityX5(mock_config)

  # Ensure the `dp` attribute exists before mocking
  strategy.dp = MagicMock()
  mocker.patch.object(strategy.dp, "get_analyzed_dataframe", return_value=(
    MagicMock(
      iloc=MagicMock(
        side_effect=[
          MagicMock(squeeze=lambda: {"close": 105.0}),
          MagicMock(squeeze=lambda: {"close": 104.0}),
          MagicMock(squeeze=lambda: {"close": 103.0}),
          MagicMock(squeeze=lambda: {"close": 102.0}),
          MagicMock(squeeze=lambda: {"close": 101.0}),
          MagicMock(squeeze=lambda: {"close": 100.0}),
        ]
      )
    ),
    None,
  ))

  # Mock exit functions to track their calls using mocker
  mocker.patch.object(strategy, "long_exit_normal", return_value=(True, "long_exit_normal"))
  mocker.patch.object(strategy, "long_exit_pump", return_value=(True, "long_exit_pump"))
  mocker.patch.object(strategy, "long_exit_quick", return_value=(True, "long_exit_quick"))
  mocker.patch.object(strategy, "short_exit_normal", return_value=(True, "short_exit_normal"))
  mocker.patch.object(strategy, "short_exit_pump", return_value=(True, "short_exit_pump"))

  # Generic values for required parameters
  pair = "BTC/USDT"
  current_time = datetime(2023, 1, 1)  # Arbitrary date
  current_rate = 105.0  # Example current rate
  current_profit = 0.05  # Example profit

  # Call the real custom_exit function
  strategy.custom_exit(
    pair=pair,
    trade=trade,
    current_time=current_time,
    current_rate=current_rate,
    current_profit=current_profit,
  )

  # Verify that only the expected function was called
  for func_name in [
    "long_exit_normal",
    "long_exit_pump",
    "long_exit_quick",
    "short_exit_normal",
    "short_exit_pump",
  ]:
    func = getattr(strategy, func_name)
    if func_name == expected_function:
      func.assert_called_once()  # Ensure the expected function was called exactly once
    else:
      func.assert_not_called()  # Ensure no other function was called


def test_update_signals_from_config(mock_config):
  """Test that the update_signals_from_config function correctly updates signals"""
  strategy = NostalgiaForInfinityX5(mock_config)  # mock_config is injected by pytest

  # Test setup with actual signals
  test_config = {
    "long_entry_signal_params": {
      "long_entry_condition_1_enable": False,
      "long_entry_condition_2_enable": True,
      "long_entry_condition_3_enable": False,
      "long_entry_condition_4_enable": True,
      "long_entry_condition_5_enable": False,
      "long_entry_condition_6_enable": True,
      "long_entry_condition_41_enable": False,
      "long_entry_condition_42_enable": True,
      "long_entry_condition_43_enable": False,
      "long_entry_condition_120_enable": True,
      "long_entry_condition_141_enable": False,
      "long_entry_condition_142_enable": True,
      "long_entry_condition_143_enable": False,
    },
    "short_entry_signal_params": {"short_entry_condition_501_enable": False},
  }

  # Save initial state of the signals
  initial_signals = {
    "long": dict(strategy.long_entry_signal_params),
    "short": dict(strategy.short_entry_signal_params),
  }

  strategy.update_signals_from_config(test_config)

  # Verify that the long signals were updated correctly
  for signal_name, value in test_config["long_entry_signal_params"].items():
    assert strategy.long_entry_signal_params[signal_name] == value, (
      f"Mismatch in {signal_name}: " f"expected {value}, got {strategy.long_entry_signal_params[signal_name]}"
    )

  # Verify that the short signals were updated correctly
  for signal_name, value in test_config["short_entry_signal_params"].items():
    assert strategy.short_entry_signal_params[signal_name] == value

  # Verify that signals not included in the config retain their original values
  for signal_name in initial_signals["long"]:
    if signal_name not in test_config["long_entry_signal_params"]:
      assert strategy.long_entry_signal_params[signal_name] == initial_signals["long"][signal_name]

  for signal_name in initial_signals["short"]:
    if signal_name not in test_config["short_entry_signal_params"]:
      assert strategy.short_entry_signal_params[signal_name] == initial_signals["short"][signal_name]

  # Test with partial configuration
  partial_config = {"long_entry_signal_params": {"long_entry_condition_1_enable": True}}

  strategy.update_signals_from_config(partial_config)
  assert strategy.long_entry_signal_params["long_entry_condition_1_enable"] is True
  # Verify that other signals remain unchanged
  assert strategy.long_entry_signal_params["long_entry_condition_2_enable"] is True
