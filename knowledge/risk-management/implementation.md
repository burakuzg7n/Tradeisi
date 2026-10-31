# Risk Management — Implementation

## Python Risk Engine Çekirdeği

```python
from dataclasses import dataclass
from enum import Enum

class KillSwitchReason(Enum):
    DAILY_LIMIT = "daily_loss_limit"
    WEEKLY_LIMIT = "weekly_loss_limit"
    MAX_DRAWDOWN = "max_drawdown"

@dataclass
class RiskConfig:
    risk_per_trade: float = 0.005      # %0.5
    min_rr: float = 2.0                # minimum 1:2 RR
    daily_loss_limit_r: float = 3.0    # -3R
    weekly_loss_limit_r: float = 8.0   # -8R
    max_drawdown_pct: float = 0.10     # %10

class RiskEngine:
    def __init__(self, config: RiskConfig, account_balance: float):
        self.config = config
        self.initial_balance = account_balance
        self.current_balance = account_balance
        self.peak_balance = account_balance
        self.daily_pnl_r = 0.0
        self.weekly_pnl_r = 0.0
        self.kill_switch_active = False
        self.kill_switch_reason = None

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_price: float
    ) -> dict:
        """Stop loss'a göre pozisyon büyüklüğü hesaplar."""
        risk_amount = self.current_balance * self.config.risk_per_trade
        stop_distance = abs(entry_price - stop_loss_price)

        if stop_distance == 0:
            raise ValueError("Stop loss entry ile aynı olamaz")

        position_size = risk_amount / stop_distance

        return {
            "position_size": position_size,
            "risk_amount": risk_amount,
            "risk_pct": self.config.risk_per_trade,
            "stop_distance": stop_distance,
            "r_value": risk_amount,
        }

    def validate_rr(self, entry: float, stop: float, target: float) -> bool:
        """RR oranının minimum eşiği karşılayıp karşılamadığını kontrol eder."""
        risk = abs(entry - stop)
        reward = abs(target - entry)
        if risk == 0:
            return False
        rr = reward / risk
        return rr >= self.config.min_rr

    def can_trade(self) -> tuple[bool, str]:
        """Kill switch aktifse veya limitler aşıldıysa trade izni vermez."""
        if self.kill_switch_active:
            return False, f"Kill switch aktif: {self.kill_switch_reason}"
        if self.daily_pnl_r <= -self.config.daily_loss_limit_r:
            self._activate_kill_switch(KillSwitchReason.DAILY_LIMIT)
            return False, "Günlük kayıp limiti aşıldı (-3R)"
        if self.weekly_pnl_r <= -self.config.weekly_loss_limit_r:
            self._activate_kill_switch(KillSwitchReason.WEEKLY_LIMIT)
            return False, "Haftalık kayıp limiti aşıldı (-8R)"
        return True, "OK"

    def record_trade_result(self, pnl_r: float, risk_amount: float | None = None):
        """Tamamlanan bir işlemin sonucunu kaydeder.

        risk_amount: işlem AÇILIRKEN hesaplanan 1R dolar değeri
        (calculate_position_size çıktısındaki 'risk_amount').
        1R işlem açılış anında sabitlenir; kapanış anındaki bakiyeden
        yeniden türetilirse açık işlem sırasında bakiye değiştiğinde
        P&L yanlış hesaplanır.
        """
        self.daily_pnl_r += pnl_r
        self.weekly_pnl_r += pnl_r
        if risk_amount is None:
            risk_amount = self.current_balance * self.config.risk_per_trade
        self.current_balance += pnl_r * risk_amount

        # Peak güncelle
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance

        # Drawdown kontrol
        current_dd = (self.peak_balance - self.current_balance) / self.peak_balance
        if current_dd >= self.config.max_drawdown_pct:
            self._activate_kill_switch(KillSwitchReason.MAX_DRAWDOWN)

    def reset_daily(self):
        self.daily_pnl_r = 0.0

    def reset_weekly(self):
        self.weekly_pnl_r = 0.0

    def _activate_kill_switch(self, reason: KillSwitchReason):
        self.kill_switch_active = True
        self.kill_switch_reason = reason.value

    @property
    def current_drawdown_pct(self) -> float:
        return (self.peak_balance - self.current_balance) / self.peak_balance
```

---

## Kullanım Örneği

```python
config = RiskConfig()
engine = RiskEngine(config, account_balance=1000.0)

# Trade öncesi kontrol
ok, msg = engine.can_trade()
if not ok:
    print(f"Trade yapılamaz: {msg}")
else:
    # Pozisyon büyüklüğü hesapla
    pos = engine.calculate_position_size(entry_price=50000, stop_loss_price=49500)
    print(f"Pozisyon: {pos['position_size']:.4f} BTC")
    print(f"Risk: ${pos['risk_amount']:.2f}")

    # RR kontrolü
    valid_rr = engine.validate_rr(entry=50000, stop=49500, target=51000)
    print(f"RR geçerli: {valid_rr}")  # 1:2 → True

# İşlem kapandıktan sonra kayıt — 1R açılışta sabitlendi
engine.record_trade_result(pnl_r=2.0, risk_amount=pos['risk_amount'])
engine.record_trade_result(pnl_r=-1.0, risk_amount=pos['risk_amount'])
```

---

## Veritabanı Şeması (Risk Snapshot)

```sql
CREATE TABLE risk_snapshots (
    id          SERIAL PRIMARY KEY,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    balance     NUMERIC(12,4) NOT NULL,
    peak_balance NUMERIC(12,4) NOT NULL,
    drawdown_pct NUMERIC(6,4) NOT NULL,
    daily_pnl_r  NUMERIC(8,4) NOT NULL,
    weekly_pnl_r NUMERIC(8,4) NOT NULL,
    kill_switch  BOOLEAN NOT NULL DEFAULT FALSE,
    kill_reason  VARCHAR(50)
);
```
