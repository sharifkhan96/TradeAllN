from rest_framework import serializers

from .models import LedgerEntry, Order, Trade, TradingAccount


class OrderSerializer(serializers.ModelSerializer):
    symbol = serializers.CharField(source="stock.symbol", read_only=True)
    name = serializers.CharField(source="stock.name", read_only=True)

    class Meta:
        model = Order
        fields = ["id", "symbol", "name", "side", "type", "time_in_force", "quantity",
                  "limit_price", "stop_price", "stop_triggered", "filled_qty", "avg_fill_price",
                  "status", "reject_reason", "source", "extended_hours", "notional", "created_at",
                  "filled_at"]


class OrderCreateSerializer(serializers.Serializer):
    symbol = serializers.CharField(max_length=12)
    side = serializers.ChoiceField(choices=["buy", "sell"])
    type = serializers.ChoiceField(choices=[t for t, _ in Order.TYPES], default="market")
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6, required=False,
                                        allow_null=True)
    notional = serializers.DecimalField(max_digits=18, decimal_places=2, required=False,
                                        allow_null=True)
    limit_price = serializers.DecimalField(max_digits=18, decimal_places=4, required=False,
                                           allow_null=True)
    stop_price = serializers.DecimalField(max_digits=18, decimal_places=4, required=False,
                                          allow_null=True)
    time_in_force = serializers.ChoiceField(choices=["day", "gtc"], default="day")
    client_order_id = serializers.CharField(max_length=64, required=False, allow_null=True)
    extended_hours = serializers.BooleanField(default=False)


class TradeSerializer(serializers.ModelSerializer):
    symbol = serializers.CharField(source="stock.symbol")

    class Meta:
        model = Trade
        fields = ["id", "order", "symbol", "side", "quantity", "price", "commission",
                  "realized_pnl", "executed_at"]


class LedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ["id", "type", "amount", "balance_after", "reference", "created_at"]


class AccountSerializer(serializers.ModelSerializer):
    buying_power = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)

    class Meta:
        model = TradingAccount
        fields = ["id", "name", "type", "cash_balance", "reserved_cash", "buying_power",
                  "starting_cash", "created_at"]
