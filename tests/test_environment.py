"""Tests: Environment/Broker profiles + SymbolProfile extension (Phase 1)."""
import unittest

from core.environment import (
    OBSERVED,
    UNKNOWN,
    UNKNOWN_TEXT,
    BrokerProfile,
    EnvironmentProfile,
    observed_test_environment,
)
from core.symbol_profile import SymbolProfile, builtin_profiles


class TestObservedEnvironment(unittest.TestCase):
    def test_observed_values_stored(self):
        env = observed_test_environment()
        self.assertEqual(env.platform, "MT5")
        self.assertEqual(env.broker, "XM Global")
        self.assertEqual(env.account_type, "Hedge")
        self.assertEqual(env.symbol, "GOLDmicro")
        self.assertEqual(env.timeframe, "M15")
        self.assertEqual(env.ea_version, "1.68")
        self.assertEqual(env.status, OBSERVED)

    def test_not_treated_as_universal(self):
        env = observed_test_environment()
        self.assertIn("OBSERVED TEST ENVIRONMENT", env.notes)
        self.assertIn("NOT a required timeframe", env.notes)
        self.assertIn("NOT a required broker", env.notes)
        self.assertIn("NOT a universal symbol", env.notes)

    def test_no_account_number_field(self):
        env = observed_test_environment()
        d = env.to_dict()
        self.assertNotIn("account_number", d)
        self.assertNotIn("account", d)
        self.assertNotIn("login", d)

    def test_missing_numeric_specs_stay_unknown(self):
        env = observed_test_environment()
        self.assertIsNone(env.leverage)
        self.assertIsNone(env.tick_value)
        fields = env.observed_fields()
        self.assertEqual(fields["leverage"], UNKNOWN_TEXT)
        self.assertEqual(fields["tick_value"], UNKNOWN_TEXT)

    def test_leverage_is_user_settable(self):
        env = observed_test_environment().from_dict(
            observed_test_environment().to_dict() | {"leverage": 888.0})
        self.assertEqual(env.leverage, 888.0)

    def test_roundtrip(self):
        env = observed_test_environment()
        env2 = EnvironmentProfile.from_dict(env.to_dict())
        self.assertEqual(env2.to_dict(), env.to_dict())


class TestBrokerProfile(unittest.TestCase):
    def test_defaults_unknown_not_fake(self):
        b = BrokerProfile(broker_name="XM Global")
        self.assertIsNone(b.leverage)
        self.assertEqual(b.commission_model, "")
        self.assertEqual(b.execution_model, "")

    def test_configurable(self):
        b = BrokerProfile(broker_name="X", leverage=500.0, margin_mode="Hedged")
        d = b.to_dict()
        self.assertEqual(d["leverage"], 500.0)
        b2 = BrokerProfile.from_dict(d)
        self.assertEqual(b2.margin_mode, "Hedged")


class TestSymbolProfileExtension(unittest.TestCase):
    def test_new_optional_fields_default_unknown(self):
        p = SymbolProfile()
        self.assertIsNone(p.tick_value)
        self.assertEqual(p.currency, "")
        self.assertEqual(p.quote_currency, "")
        self.assertEqual(p.base_currency, "")

    def test_roundtrip_keeps_new_fields(self):
        p = SymbolProfile(name="GOLDmicro", tick_value=1.0,
                          currency="USD", quote_currency="USD",
                          base_currency="XAU")
        p2 = SymbolProfile.from_dict(p.to_dict())
        self.assertEqual(p2.tick_value, 1.0)
        self.assertEqual(p2.quote_currency, "USD")

    def test_builtin_profiles_unchanged_core_values(self):
        """Regression guard: existing builtin profiles keep their values."""
        xau = [p for p in builtin_profiles() if p.name == "XAUUSD"][0]
        self.assertEqual(xau.contract_size, 100.0)
        self.assertEqual(xau.lot_step, 0.01)
        self.assertIsNone(xau.tick_value)      # still UNKNOWN, never invented


if __name__ == "__main__":
    unittest.main()
