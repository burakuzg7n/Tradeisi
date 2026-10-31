# Execution — Implementation

## FastAPI Webhook Endpoint

```python
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator
import redis.asyncio as redis
import json

app = FastAPI()
security = HTTPBearer()

class SignalPayload(BaseModel):
    symbol: str
    direction: str          # "long" veya "short"
    entry: float
    stop_loss: float
    take_profit: float
    setup: str
    timeframe: str
    htf_bias: str
    session: str
    volume_ratio: float = 1.0
    timestamp: str

    @validator('direction')
    def validate_direction(cls, v):
        if v not in ('long', 'short'):
            raise ValueError('direction must be long or short')
        return v

    @validator('stop_loss')
    def validate_stop(cls, v, values):
        if 'direction' in values and 'entry' in values:
            if values['direction'] == 'long' and v >= values['entry']:
                raise ValueError('Stop loss must be below entry for long')
            if values['direction'] == 'short' and v <= values['entry']:
                raise ValueError('Stop loss must be above entry for short')
        return v

WEBHOOK_SECRET = "your-secret-token"  # env'den al

@app.post("/webhook")
async def receive_signal(
    payload: SignalPayload,
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    if credentials.credentials != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid token")

    r = redis.Redis(host='localhost', port=6379, db=0)
    await r.lpush("signals", json.dumps(payload.dict()))

    return {"status": "queued", "symbol": payload.symbol}
```

---

## Execution Engine (CCXT Async)

```python
import ccxt.async_support as ccxt
import asyncio
from typing import Optional

class ExecutionEngine:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'linear'},
        })
        if testnet:
            self.exchange.set_sandbox_mode(True)

    async def place_order(
        self,
        symbol: str,
        direction: str,
        position_size: float,
        entry: float,
        stop_loss: float,
        take_profit: float,
        order_type: str = 'limit'
    ) -> dict:
        """Pozisyon açar, SL ve TP koyar."""
        side = 'buy' if direction == 'long' else 'sell'

        # Ana order
        params = {
            'stopLoss': {'triggerPrice': stop_loss, 'orderType': 'Market'},
            'takeProfit': {'triggerPrice': take_profit, 'orderType': 'Limit'},
            'positionIdx': 0,  # one-way mode
        }

        try:
            order = await self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=position_size,
                price=entry if order_type == 'limit' else None,
                params=params
            )
            return {"status": "ok", "order_id": order['id'], "order": order}

        except ccxt.InsufficientFunds as e:
            return {"status": "error", "reason": "insufficient_funds", "detail": str(e)}
        except ccxt.RateLimitExceeded:
            await asyncio.sleep(1)
            return {"status": "retry"}
        except Exception as e:
            return {"status": "error", "reason": "unknown", "detail": str(e)}

    async def close(self):
        await self.exchange.close()
```

---

## Signal Consumer (Queue Worker)

```python
import asyncio
import redis.asyncio as redis
import json

async def process_signals(risk_engine, exec_engine):
    r = redis.Redis(host='localhost', port=6379, db=0)

    while True:
        # Queue'dan sinyal al (blocking, 1sn timeout)
        item = await r.brpop("signals", timeout=1)
        if item is None:
            continue

        signal = json.loads(item[1])

        # Risk kontrolü
        ok, msg = risk_engine.can_trade()
        if not ok:
            print(f"Trade reddedildi: {msg}")
            continue

        # Position sizing
        pos = risk_engine.calculate_position_size(
            entry_price=signal['entry'],
            stop_loss_price=signal['stop_loss']
        )

        # Order gönder
        result = await exec_engine.place_order(
            symbol=signal['symbol'],
            direction=signal['direction'],
            position_size=pos['position_size'],
            entry=signal['entry'],
            stop_loss=signal['stop_loss'],
            take_profit=signal['take_profit'],
        )

        # Journal'a kaydet
        print(f"Order result: {result}")
```
