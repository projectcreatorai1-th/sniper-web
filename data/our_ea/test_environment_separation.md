# TEST ENVIRONMENT SEPARATION (§38)

DEVELOPMENT = this repository working tree
TEST        = unittest suites (tests/**) — no credentials, no broker
DEMO        = ModeController DEMO + DemoAdapter (controlled/simulated
              broker; real MT5 demo requires operator-supplied
              environment at deployment time)
PRODUCTION  = NOT DEPLOYED; LIVE permanently locked

Guarantees:
- no production credentials exist anywhere in the repository (secrets
  scan clean, §35)
- no test artifact can send a live order (LIVE unreachable in mode
  controller, config validation, adapter factory, execution module)
- demo credentials, when introduced, are supplied via environment at
  runtime and are never committed
