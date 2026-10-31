# Backtesting — Implementation

> NOT: Üretim motoru `tradebot/backtest.py` içindedir (maker/taker ayrımı,
> muhafazakâr aynı-bar kuralları, Monte Carlo dahil). Buradaki kod eğitim
> amaçlı sadeleştirilmiş referanstır.

## Python: Basit Backtest Engine

```python
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import numpy as np

@dataclass
class BacktestConfig:
    initial_balance: float = 10_000.0
    risk_per_trade: float = 0.005
    commission_rate: float = 0.00055   # taker fee (her yön)
    slippage_rate: float = 0.0001
    min_rr: float = 2.0

@dataclass
class Trade:
    entry: float
    stop: float
    target: float
    direction: str          # "long" veya "short"
    entry_index: int
    exit_index: Optional[int] = None
    exit_price: Optional[float] = None
    pnl_r: Optional[float] = None
    pnl_usd: Optional[float] = None
    is_win: Optional[bool] = None

@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)

    @property
    def total_trades(self): return len(self.trades)

    @property
    def wins(self): return [t for t in self.trades if t.is_win]

    @property
    def losses(self): return [t for t in self.trades if t.is_win is False]

    @property
    def win_rate(self):
        if not self.trades: return 0
        return len(self.wins) / len(self.trades)

    @property
    def profit_factor(self):
        gross_profit = sum(t.pnl_usd for t in self.wins if t.pnl_usd)
        gross_loss = abs(sum(t.pnl_usd for t in self.losses if t.pnl_usd))
        if gross_loss == 0: return float('inf')
        return gross_profit / gross_loss

    @property
    def max_drawdown(self):
        if not self.equity_curve: return 0
        peak = self.equity_curve[0]
        max_dd = 0
        for val in self.equity_curve:
            if val > peak: peak = val
            dd = (peak - val) / peak
            if dd > max_dd: max_dd = dd
        return max_dd

    @property
    def expectancy_r(self):
        if not self.trades: return 0
        return sum(t.pnl_r for t in self.trades if t.pnl_r) / len(self.trades)

    @property
    def sharpe_ratio(self):
        pnls = [t.pnl_r for t in self.trades if t.pnl_r is not None]
        if len(pnls) < 2: return 0
        mean = np.mean(pnls)
        std = np.std(pnls)
        if std == 0: return 0
        return mean / std * np.sqrt(252)  # annualized

    def summary(self) -> dict:
        return {
            "total_trades": self.total_trades,
            "win_rate": f"{self.win_rate:.1%}",
            "profit_factor": f"{self.profit_factor:.2f}",
            "max_drawdown": f"{self.max_drawdown:.1%}",
            "expectancy_r": f"{self.expectancy_r:.3f}R",
            "sharpe_ratio": f"{self.sharpe_ratio:.2f}",
            "final_balance": self.equity_curve[-1] if self.equity_curve else 0,
        }


class Backtester:
    def __init__(self, config: BacktestConfig):
        self.config = config

    def run(self, df: pd.DataFrame, signals: list[dict]) -> BacktestResult:
        """
        signals: [{"index": int, "direction": "long/short",
                   "entry": float, "stop": float, "target": float}]
        """
        result = BacktestResult()
        balance = self.config.initial_balance
        result.equity_curve.append(balance)

        for sig in signals:
            if sig['index'] >= len(df):
                continue

            # Slippage HER ZAMAN aleyhe uygulanır:
            # long → daha pahalı alırsın, short → daha ucuza satarsın.
            # (Eski sürüm short'ta da fiyatı yukarı kaydırıyordu → short
            # entry'leri LEHTE slippage alıyordu, sonuçlar iyimserdi.)
            if sig['direction'] == 'long':
                entry = sig['entry'] * (1 + self.config.slippage_rate)
            else:
                entry = sig['entry'] * (1 - self.config.slippage_rate)
            stop = sig['stop']
            target = sig['target']

            # RR kontrolü
            risk = abs(entry - stop)
            reward = abs(target - entry)
            if risk == 0 or reward / risk < self.config.min_rr:
                continue

            # Position sizing
            risk_amount = balance * self.config.risk_per_trade
            position_size = risk_amount / risk

            # Komisyon
            entry_cost = entry * position_size * self.config.commission_rate
            exit_cost_win = target * position_size * self.config.commission_rate
            exit_cost_loss = stop * position_size * self.config.commission_rate

            # Simülasyon: gelecek mumlara bak
            future = df.iloc[sig['index'] + 1:]
            hit_target = False
            hit_stop = False
            exit_price = None
            exit_idx = None

            for i, (idx, row) in enumerate(future.iterrows()):
                if sig['direction'] == 'long':
                    if row['low'] <= stop:
                        hit_stop = True
                        exit_price = stop
                        exit_idx = sig['index'] + 1 + i
                        break
                    if row['high'] >= target:
                        hit_target = True
                        exit_price = target
                        exit_idx = sig['index'] + 1 + i
                        break
                else:  # short
                    if row['high'] >= stop:
                        hit_stop = True
                        exit_price = stop
                        exit_idx = sig['index'] + 1 + i
                        break
                    if row['low'] <= target:
                        hit_target = True
                        exit_price = target
                        exit_idx = sig['index'] + 1 + i
                        break

            if not (hit_target or hit_stop):
                continue

            if hit_target:
                pnl_usd = reward * position_size - entry_cost - exit_cost_win
                pnl_r = pnl_usd / risk_amount
                is_win = True
            else:
                pnl_usd = -risk_amount - entry_cost - exit_cost_loss
                pnl_r = -1.0
                is_win = False

            balance += pnl_usd

            trade = Trade(
                entry=entry,
                stop=stop,
                target=target,
                direction=sig['direction'],
                entry_index=sig['index'],
                exit_index=exit_idx,
                exit_price=exit_price,
                pnl_r=pnl_r,
                pnl_usd=pnl_usd,
                is_win=is_win,
            )
            result.trades.append(trade)
            result.equity_curve.append(balance)

        return result
```

---

## Kullanım

```python
config = BacktestConfig(initial_balance=10_000)
backtester = Backtester(config)

# Sinyalleri strateji motorundan üret
signals = generate_signals(df)  # kendi sinyal üretim fonksiyonun

result = backtester.run(df, signals)
print(result.summary())
```
