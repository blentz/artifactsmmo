"""Grand Exchange trading commands."""

import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.utils.formatters import (
    format_cooldown_message,
    format_error_message,
    format_success_message,
    format_table,
)
from artifactsmmo_cli.utils.helpers import handle_api_error, handle_api_response
from artifactsmmo_cli.utils.validators import (
    validate_character_name,
    validate_item_code,
    validate_quantity,
)

app = typer.Typer(help="Grand Exchange trading commands")
console = Console()


# Market Analysis Helper Functions
def calculate_price_stats(orders: List) -> Dict[str, float]:
    """Calculate price statistics from orders."""
    if not orders:
        return {"min": 0, "max": 0, "avg": 0, "median": 0}

    prices = [order.price for order in orders if hasattr(order, "price")]
    if not prices:
        return {"min": 0, "max": 0, "avg": 0, "median": 0}

    return {"min": min(prices), "max": max(prices), "avg": statistics.mean(prices), "median": statistics.median(prices)}


def calculate_volume_stats(orders: List) -> Dict[str, int]:
    """Calculate volume statistics from orders."""
    if not orders:
        return {"total_quantity": 0, "total_orders": 0, "avg_quantity": 0}

    quantities = [order.quantity for order in orders if hasattr(order, "quantity")]
    total_quantity = sum(quantities) if quantities else 0

    return {
        "total_quantity": total_quantity,
        "total_orders": len(orders),
        "avg_quantity": int(total_quantity / len(orders)) if orders else 0,
    }


def find_arbitrage_opportunities(all_orders: List, min_profit_margin: float = 0.1) -> List[Dict]:
    """Find potential arbitrage opportunities."""
    opportunities = []

    # Group orders by item code
    items = defaultdict(list)
    for order in all_orders:
        if hasattr(order, "code") and hasattr(order, "price"):
            items[order.code].append(order)

    for item_code, orders in items.items():
        if len(orders) < 2:
            continue

        prices = [order.price for order in orders]
        min_price = min(prices)
        max_price = max(prices)

        profit_margin = (max_price - min_price) / min_price if min_price > 0 else 0

        if profit_margin >= min_profit_margin:
            opportunities.append(
                {
                    "item": item_code,
                    "min_price": min_price,
                    "max_price": max_price,
                    "profit_margin": profit_margin,
                    "potential_profit": max_price - min_price,
                }
            )

    return sorted(opportunities, key=lambda x: x["profit_margin"], reverse=True)


def format_market_analysis_table(item_code: str, orders: List, history: List) -> Table:
    """Format market analysis data into a rich table."""
    table = Table(title=f"Market Analysis: {item_code}")

    # Price analysis
    price_stats = calculate_price_stats(orders)
    volume_stats = calculate_volume_stats(orders)

    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Current Orders", str(volume_stats["total_orders"]))
    table.add_row("Total Quantity", str(volume_stats["total_quantity"]))
    table.add_row("Min Price", f"{price_stats['min']:.0f} gold")
    table.add_row("Max Price", f"{price_stats['max']:.0f} gold")
    table.add_row("Average Price", f"{price_stats['avg']:.0f} gold")
    table.add_row("Median Price", f"{price_stats['median']:.0f} gold")

    if history:
        recent_sales = len(history)
        table.add_row("Recent Sales (7d)", str(recent_sales))

        if recent_sales > 0:
            avg_sale_price = statistics.mean([h.price for h in history if hasattr(h, "price")])
            table.add_row("Avg Sale Price (7d)", f"{avg_sale_price:.0f} gold")

    return table


def format_price_table(item_code: str, orders: List) -> Table:
    """Format current prices into a table."""
    table = Table(title=f"Current Prices: {item_code}")
    table.add_column("Price", style="cyan")
    table.add_column("Quantity", style="green")
    table.add_column("Seller", style="yellow")
    table.add_column("Created", style="magenta")

    # Sort by price (ascending for buy orders)
    sorted_orders = sorted(orders, key=lambda x: x.price if hasattr(x, "price") else 0)

    for order in sorted_orders[:10]:  # Show top 10
        created_date = ""
        if hasattr(order, "created_at"):
            try:
                created_date = datetime.fromisoformat(order.created_at.replace("Z", "+00:00")).strftime("%m/%d %H:%M")
            except:
                created_date = "Unknown"

        table.add_row(
            f"{getattr(order, 'price', 0)} gold",
            str(getattr(order, "quantity", 0)),
            getattr(order, "seller", "Unknown"),
            created_date,
        )

    return table


def format_opportunities_table(opportunities: List) -> Table:
    """Format arbitrage opportunities into a table."""
    table = Table(title="Trading Opportunities")
    table.add_column("Item", style="cyan")
    table.add_column("Min Price", style="green")
    table.add_column("Max Price", style="red")
    table.add_column("Profit Margin", style="yellow")
    table.add_column("Potential Profit", style="magenta")

    for opp in opportunities[:10]:  # Show top 10
        table.add_row(
            opp["item"],
            f"{opp['min_price']:.0f}g",
            f"{opp['max_price']:.0f}g",
            f"{opp['profit_margin']:.1%}",
            f"{opp['potential_profit']:.0f}g",
        )

    return table


@app.command("ge-buy")
def buy_from_ge(
    character: str = typer.Argument(..., help="Character name"),
    order_id: str = typer.Argument(..., help="Grand Exchange order ID"),
    quantity: int = typer.Argument(..., help="Quantity to buy"),
) -> None:
    """Buy items from Grand Exchange."""
    try:
        character = validate_character_name(character)
        quantity = validate_quantity(quantity)

        client = ClientManager().client

        # Import the GE buy order schema and API function
        from artifactsmmo_api_client.api.my_characters import action_ge_buy_item_my_name_action_grandexchange_buy_post
        from artifactsmmo_api_client.models.ge_buy_order_schema import GEBuyOrderSchema

        buy_data = GEBuyOrderSchema(id=order_id, quantity=quantity)
        response = action_ge_buy_item_my_name_action_grandexchange_buy_post.sync(
            client=client, name=character, body=buy_data
        )

        cli_response = handle_api_response(response, f"Bought {quantity} items from GE order {order_id}")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Purchase completed"))
        elif cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or "Purchase failed"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("ge-sell")
def sell_on_ge(
    character: str = typer.Argument(..., help="Character name"),
    item_code: str = typer.Argument(..., help="Item code to sell"),
    quantity: int = typer.Argument(..., help="Quantity to sell"),
    price: int = typer.Argument(..., help="Price per unit"),
) -> None:
    """Create a sell order on Grand Exchange."""
    try:
        character = validate_character_name(character)
        item_code = validate_item_code(item_code)
        quantity = validate_quantity(quantity)

        if price <= 0:
            raise ValueError("Price must be greater than 0")

        client = ClientManager().client

        # Import the GE order creation schema and API function
        from artifactsmmo_api_client.api.my_characters import (
            action_ge_create_sell_order_my_name_action_grandexchange_sell_post,
        )
        from artifactsmmo_api_client.models.ge_order_creationr_schema import GEOrderCreationrSchema

        sell_data = GEOrderCreationrSchema(code=item_code, quantity=quantity, price=price)
        response = action_ge_create_sell_order_my_name_action_grandexchange_sell_post.sync(
            client=client, name=character, body=sell_data
        )

        cli_response = handle_api_response(
            response, f"Created sell order for {quantity}x {item_code} at {price} gold each"
        )
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Sell order created"))
        elif cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or "Sell order failed"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("ge-orders")
def list_ge_orders() -> None:
    """List your current Grand Exchange orders."""
    try:
        client = ClientManager().client

        # Import the API function
        from artifactsmmo_api_client.api.my_account import get_ge_sell_orders_my_grandexchange_orders_get

        response = get_ge_sell_orders_my_grandexchange_orders_get.sync(client=client)

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            # Format orders as a table
            orders = cli_response.data
            if hasattr(orders, "data") and orders.data:
                headers = ["Order ID", "Item", "Quantity", "Price", "Status"]
                rows = []
                for order in orders.data:
                    rows.append(
                        [
                            getattr(order, "id", "N/A"),
                            getattr(order, "code", "N/A"),
                            str(getattr(order, "quantity", 0)),
                            str(getattr(order, "price", 0)),
                            getattr(order, "status", "N/A"),
                        ]
                    )
                output = format_table(headers, rows, title="Grand Exchange Orders")
                console.print(output)
            else:
                console.print(format_error_message("No orders found"))
        else:
            console.print(format_error_message(cli_response.error or "Could not retrieve orders"))

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("ge-cancel")
def cancel_ge_order(
    character: str = typer.Argument(..., help="Character name"),
    order_id: str = typer.Argument(..., help="Order ID to cancel"),
) -> None:
    """Cancel a Grand Exchange sell order."""
    try:
        character = validate_character_name(character)

        client = ClientManager().client

        # Import the GE cancel order schema and API function
        from artifactsmmo_api_client.api.my_characters import (
            action_ge_cancel_sell_order_my_name_action_grandexchange_cancel_post,
        )
        from artifactsmmo_api_client.models.ge_cancel_order_schema import GECancelOrderSchema

        cancel_data = GECancelOrderSchema(id=order_id)
        response = action_ge_cancel_sell_order_my_name_action_grandexchange_cancel_post.sync(
            client=client, name=character, body=cancel_data
        )

        cli_response = handle_api_response(response, f"Cancelled GE order {order_id}")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Order cancelled"))
        elif cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or "Cancel failed"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("prices")
def show_item_prices(
    item_code: str = typer.Argument(..., help="Item code to check prices for"),
) -> None:
    """Show current buy/sell prices for an item."""
    try:
        item_code = validate_item_code(item_code)
        client = ClientManager().client

        # Import the API function for getting all orders
        from artifactsmmo_api_client.api.grand_exchange import get_ge_sell_orders_grandexchange_orders_get

        response = get_ge_sell_orders_grandexchange_orders_get.sync(client=client, code=item_code, size=50)

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            orders = cli_response.data.data if hasattr(cli_response.data, "data") else []

            if orders:
                table = format_price_table(item_code, orders)
                console.print(table)

                # Show summary stats
                price_stats = calculate_price_stats(orders)
                volume_stats = calculate_volume_stats(orders)

                summary = Panel(
                    f"[cyan]Orders:[/cyan] {volume_stats['total_orders']} | "
                    f"[green]Total Qty:[/green] {volume_stats['total_quantity']} | "
                    f"[yellow]Price Range:[/yellow] {price_stats['min']:.0f} - {price_stats['max']:.0f}g | "
                    f"[magenta]Avg:[/magenta] {price_stats['avg']:.0f}g",
                    title="Market Summary",
                )
                console.print(summary)
            else:
                console.print(format_error_message(f"No active orders found for '{item_code}' in the Grand Exchange"))
        else:
            console.print(
                format_error_message(cli_response.error or f"Failed to retrieve market data for '{item_code}'")
            )

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("orders")
def show_item_orders(
    item: Optional[str] = typer.Option(None, "--item", help="Filter by item code"),
    seller: Optional[str] = typer.Option(None, "--seller", help="Filter by seller"),
    page: int = typer.Option(1, "--page", help="Page number"),
    size: int = typer.Option(20, "--size", help="Page size"),
) -> None:
    """Show all orders for specific item or all orders."""
    try:
        if item:
            item = validate_item_code(item)

        client = ClientManager().client

        # Import the API function for getting all orders
        from artifactsmmo_api_client.api.grand_exchange import get_ge_sell_orders_grandexchange_orders_get

        response = get_ge_sell_orders_grandexchange_orders_get.sync(
            client=client, code=item, seller=seller, page=page, size=size
        )

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            orders = cli_response.data.data if hasattr(cli_response.data, "data") else []

            if orders:
                # Create table for orders
                headers = ["Item", "Quantity", "Price", "Seller", "Created"]
                rows = []

                for order in orders:
                    created_date = ""
                    if hasattr(order, "created_at"):
                        try:
                            created_date = datetime.fromisoformat(order.created_at.replace("Z", "+00:00")).strftime(
                                "%m/%d %H:%M"
                            )
                        except:
                            created_date = "Unknown"

                    rows.append(
                        [
                            getattr(order, "code", "N/A"),
                            str(getattr(order, "quantity", 0)),
                            f"{getattr(order, 'price', 0)}g",
                            getattr(order, "seller", "Unknown"),
                            created_date,
                        ]
                    )

                title = f"Grand Exchange Orders"
                if item:
                    title += f" - {item}"
                if seller:
                    title += f" - Seller: {seller}"

                output = format_table(headers, rows, title=title)
                console.print(output)

                # Show pagination info
                total = getattr(cli_response.data, "total", 0)
                pages = getattr(cli_response.data, "pages", 0)
                console.print(f"\n[dim]Page {page} of {pages} | Total orders: {total}[/dim]")
            else:
                console.print(format_error_message("No orders found"))
        else:
            console.print(format_error_message(cli_response.error or "Could not retrieve orders"))

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("history")
def show_trading_history(
    character: Optional[str] = typer.Argument(None, help="Character name (optional, shows your history if provided)"),
    item: Optional[str] = typer.Option(None, "--item", help="Filter by item code"),
    page: int = typer.Option(1, "--page", help="Page number"),
    size: int = typer.Option(20, "--size", help="Page size"),
) -> None:
    """Show recent trading history."""
    try:
        if character:
            character = validate_character_name(character)
        if item:
            item = validate_item_code(item)

        client = ClientManager().client

        if character:
            # Show personal trading history
            from artifactsmmo_api_client.api.my_account import get_ge_sell_history_my_grandexchange_history_get

            response = get_ge_sell_history_my_grandexchange_history_get.sync(
                client=client, code=item, page=page, size=size
            )
        else:
            # Show public trading history for an item
            if not item:
                console.print(format_error_message("Item code is required when not showing personal history"))
                raise typer.Exit(1)

            from artifactsmmo_api_client.api.grand_exchange import get_ge_sell_history_grandexchange_history_code_get

            response = get_ge_sell_history_grandexchange_history_code_get.sync(
                client=client, code=item, page=page, size=size
            )

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            history = cli_response.data.data if hasattr(cli_response.data, "data") else []

            if history:
                # Create table for history
                headers = ["Item", "Quantity", "Price", "Seller", "Buyer", "Sold At"]
                rows = []

                for sale in history:
                    sold_date = ""
                    if hasattr(sale, "sold_at"):
                        try:
                            sold_date = datetime.fromisoformat(sale.sold_at.replace("Z", "+00:00")).strftime(
                                "%m/%d %H:%M"
                            )
                        except:
                            sold_date = "Unknown"

                    rows.append(
                        [
                            getattr(sale, "code", "N/A"),
                            str(getattr(sale, "quantity", 0)),
                            f"{getattr(sale, 'price', 0)}g",
                            getattr(sale, "seller", "Unknown"),
                            getattr(sale, "buyer", "Unknown"),
                            sold_date,
                        ]
                    )

                title = "Trading History (Last 7 Days)"
                if character:
                    title += f" - {character}"
                if item:
                    title += f" - {item}"

                output = format_table(headers, rows, title=title)
                console.print(output)

                # Show pagination info
                total = getattr(cli_response.data, "total", 0)
                pages = getattr(cli_response.data, "pages", 0)
                console.print(f"\n[dim]Page {page} of {pages} | Total sales: {total}[/dim]")
            else:
                console.print(format_error_message("No trading history found"))
        else:
            console.print(format_error_message(cli_response.error or "Could not retrieve trading history"))

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("analyze")
def analyze_item_market(
    item_code: str = typer.Argument(..., help="Item code to analyze"),
) -> None:
    """Market analysis with supply/demand info."""
    try:
        item_code = validate_item_code(item_code)
        client = ClientManager().client

        # Get current orders
        from artifactsmmo_api_client.api.grand_exchange import (
            get_ge_sell_orders_grandexchange_orders_get,
            get_ge_sell_history_grandexchange_history_code_get,
        )

        # Fetch current orders
        orders_response = get_ge_sell_orders_grandexchange_orders_get.sync(client=client, code=item_code, size=100)

        # Fetch recent history
        history_response = get_ge_sell_history_grandexchange_history_code_get.sync(
            client=client, code=item_code, size=100
        )

        orders_cli_response = handle_api_response(orders_response)
        history_cli_response = handle_api_response(history_response)

        orders = []
        history = []

        if orders_cli_response.success and orders_cli_response.data:
            orders = orders_cli_response.data.data if hasattr(orders_cli_response.data, "data") else []

        if history_cli_response.success and history_cli_response.data:
            history = history_cli_response.data.data if hasattr(history_cli_response.data, "data") else []

        if not orders and not history:
            console.print(format_error_message(f"No market data found for {item_code}"))
            return

        # Display comprehensive analysis
        analysis_table = format_market_analysis_table(item_code, orders, history)
        console.print(analysis_table)

        # Show current order book if available
        if orders:
            console.print("\n")
            price_table = format_price_table(item_code, orders[:10])
            console.print(price_table)

        # Market insights
        insights = []

        if orders:
            price_stats = calculate_price_stats(orders)
            volume_stats = calculate_volume_stats(orders)

            if price_stats["max"] > price_stats["min"] * 1.5:
                insights.append("🔥 High price variance - potential arbitrage opportunity")

            if volume_stats["total_quantity"] > 100:
                insights.append("📈 High supply available")
            elif volume_stats["total_quantity"] < 10:
                insights.append("📉 Low supply - prices may be volatile")

        if history:
            recent_volume = sum(h.quantity for h in history if hasattr(h, "quantity"))
            if recent_volume > 50:
                insights.append("💰 High trading activity")
            elif recent_volume < 5:
                insights.append("😴 Low trading activity")

        if insights:
            console.print("\n[bold cyan]Market Insights:[/bold cyan]")
            for insight in insights:
                console.print(f"  {insight}")

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("trending")
def show_trending_items(
    limit: int = typer.Option(10, "--limit", help="Number of items to show"),
) -> None:
    """Show items with most trading activity."""
    try:
        client = ClientManager().client

        # Get all recent orders to analyze activity
        from artifactsmmo_api_client.api.grand_exchange import get_ge_sell_orders_grandexchange_orders_get

        response = get_ge_sell_orders_grandexchange_orders_get.sync(client=client, size=100)

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            orders = cli_response.data.data if hasattr(cli_response.data, "data") else []

            if orders:
                # Count orders by item
                item_activity = defaultdict(lambda: {"orders": 0, "total_quantity": 0, "avg_price": 0})

                for order in orders:
                    code = getattr(order, "code", "unknown")
                    quantity = getattr(order, "quantity", 0)
                    price = getattr(order, "price", 0)

                    item_activity[code]["orders"] += 1
                    item_activity[code]["total_quantity"] += quantity
                    item_activity[code]["avg_price"] = (
                        item_activity[code]["avg_price"] * (item_activity[code]["orders"] - 1) + price
                    ) / item_activity[code]["orders"]

                # Sort by number of orders (activity)
                trending = sorted(item_activity.items(), key=lambda x: x[1]["orders"], reverse=True)[:limit]

                # Create table
                headers = ["Item", "Active Orders", "Total Quantity", "Avg Price"]
                rows = []

                for item, stats in trending:
                    rows.append(
                        [item, str(stats["orders"]), str(stats["total_quantity"]), f"{stats['avg_price']:.0f}g"]
                    )

                output = format_table(headers, rows, title="Trending Items (Most Active)")
                console.print(output)
            else:
                console.print(format_error_message("No orders found"))
        else:
            console.print(format_error_message(cli_response.error or "Could not retrieve market data"))

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("opportunities")
def show_trade_opportunities(
    min_margin: float = typer.Option(0.2, "--min-margin", help="Minimum profit margin (0.2 = 20%)"),
    limit: int = typer.Option(10, "--limit", help="Number of opportunities to show"),
) -> None:
    """Find profitable trade opportunities."""
    try:
        client = ClientManager().client

        # Get all current orders
        from artifactsmmo_api_client.api.grand_exchange import get_ge_sell_orders_grandexchange_orders_get

        response = get_ge_sell_orders_grandexchange_orders_get.sync(client=client, size=100)

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            orders = cli_response.data.data if hasattr(cli_response.data, "data") else []

            if orders:
                opportunities = find_arbitrage_opportunities(orders, min_margin)

                if opportunities:
                    table = format_opportunities_table(opportunities[:limit])
                    console.print(table)

                    console.print(
                        f"\n[dim]Showing top {min(len(opportunities), limit)} opportunities with ≥{min_margin:.0%} margin[/dim]"
                    )
                else:
                    console.print(format_error_message(f"No opportunities found with ≥{min_margin:.0%} profit margin"))
            else:
                console.print(format_error_message("No orders found"))
        else:
            console.print(format_error_message(cli_response.error or "Could not retrieve market data"))

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("spread")
def show_price_spreads(
    limit: int = typer.Option(10, "--limit", help="Number of items to show"),
) -> None:
    """Show items with best buy/sell spreads."""
    try:
        client = ClientManager().client

        # Get all current orders
        from artifactsmmo_api_client.api.grand_exchange import get_ge_sell_orders_grandexchange_orders_get

        response = get_ge_sell_orders_grandexchange_orders_get.sync(client=client, size=100)

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            orders = cli_response.data.data if hasattr(cli_response.data, "data") else []

            if orders:
                # Group by item and calculate spreads
                item_spreads = {}
                items = defaultdict(list)

                for order in orders:
                    code = getattr(order, "code", "unknown")
                    price = getattr(order, "price", 0)
                    items[code].append(price)

                for item, prices in items.items():
                    if len(prices) >= 2:
                        min_price = min(prices)
                        max_price = max(prices)
                        spread = max_price - min_price
                        spread_pct = (spread / min_price * 100) if min_price > 0 else 0

                        item_spreads[item] = {
                            "min_price": min_price,
                            "max_price": max_price,
                            "spread": spread,
                            "spread_pct": spread_pct,
                        }

                # Sort by spread percentage
                sorted_spreads = sorted(item_spreads.items(), key=lambda x: x[1]["spread_pct"], reverse=True)[:limit]

                if sorted_spreads:
                    # Create table
                    headers = ["Item", "Min Price", "Max Price", "Spread", "Spread %"]
                    rows = []

                    for item, data in sorted_spreads:
                        rows.append(
                            [
                                item,
                                f"{data['min_price']:.0f}g",
                                f"{data['max_price']:.0f}g",
                                f"{data['spread']:.0f}g",
                                f"{data['spread_pct']:.1f}%",
                            ]
                        )

                    output = format_table(headers, rows, title="Best Price Spreads")
                    console.print(output)
                else:
                    console.print(format_error_message("No items with multiple price points found"))
            else:
                console.print(format_error_message("No orders found"))
        else:
            console.print(format_error_message(cli_response.error or "Could not retrieve market data"))

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)
